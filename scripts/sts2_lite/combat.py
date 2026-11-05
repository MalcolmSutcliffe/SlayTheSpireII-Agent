from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatState

from sts2_lite.creature import Creature
from sts2_lite.player import Player
from sts2_lite.enemy import Enemy
from sts2_lite.card import TargetType, CardType, Card, CardId, STRIKE_CARDS
from sts2_lite.damage import modify_damage, base_from_displayed
from sts2_lite import rng
from sts2_lite.events import EventType
from sts2_lite.relic import RelicId, PER_TURN_FLAG, ALWAYS_REPORTED, after_card_played, release_card, fire_relics, upgraded_after_play

from sts2_lite.status import StatusId, StatusBehaviour, STATUS_HANDLERS
from sts2_lite.enemy_moves import SUMMONS

# what the bridge calls each kind of hand selection
HAND_SELECT_MODES = {"upgrade_select" : "upgrade"}

class PendingChoice:
    """A card the player must pick before anything else can happen."""
    def __init__(self, kind : str, indices : list[int], pile : str = "hand", amount : int = 0):
        self.kind = kind            # what the pick does, see CombatSimulator._apply_choice
        self.indices = indices      # positions in the pile that may be picked
        self.pile = pile            # "hand" or "discard"
        self.amount = amount        # cards to draw once the pick is made (Burning Pact)

    def deepcopy(self) -> PendingChoice:
        return PendingChoice(self.kind, list(self.indices), self.pile, self.amount)

class CombatState:
    player : Player
    energy : int
    max_energy : int
    enemies : list[Enemy]
    turn_number : int
    ascension : int = 0

    def __init__(self):
        self.enemies = []
        self.cards_played = 0   # this player turn
        self.revivals = []      # (monster, slot) killed enemies that return after the enemy turn
        self.pending_choice = None

    @classmethod
    def from_dict(cls, combat_state : dict):
        if "enemies" not in combat_state and "battle" in combat_state:
            # a card-selection screen nests the fight under "battle" and has no top-level energy
            battle = combat_state["battle"]
            combat_state = {**combat_state, "enemies": battle["enemies"], "round": battle["round"],
                            "energy": battle["player"]["energy"], "max_energy": battle["player"]["max_energy"]}
        cs = cls()
        cs.player = Player.from_dict(combat_state["player"])
        cs.player.remove_displayed_tangled()
        cs.enemies = []
        ascension = combat_state.get("context", {}).get("ascension", 0)
        cs.ascension = ascension
        for enemy in combat_state["enemies"]:
            cs.enemies.append(Enemy.from_dict(enemy, ascension))
        cs.turn_number = combat_state["round"]
        for enemy, raw in zip(cs.enemies, combat_state["enemies"]):
            if enemy.num_attacks > 0:
                enemy.attack_damage = base_from_displayed(enemy.attack_damage, enemy, cs.player)
            enemy.identify_move(raw["intents"], cs.turn_number)
        cs._infer_revivals()
        cs._infer_ringing_play()
        cs.energy = combat_state["energy"]
        cs.max_energy = combat_state["max_energy"]
        if combat_state.get("decision") == "hand_select":
            cs._load_hand_select(combat_state)
        return cs

    def _load_hand_select(self, state : dict):
        """The game is waiting for a hand card to be picked; the picks it lists become the choice."""
        kind = HAND_SELECT_MODES.get(state["mode"])
        if kind is None:
            raise ValueError(f"unknown card selection mode {state['mode']}")
        hand = self.player.hand
        indices, seen = [], set()
        for c in state["cards"]:
            card = hand[c["index"]]
            key = (card.card_id, card.is_upgraded, card.energy_cost)
            if key not in seen:
                seen.add(key)
                indices.append(c["index"])
        self.pending_choice = PendingChoice(kind, indices)

    def carry_turn_counters(self, previous : CombatState | None):
        """The bridge reports no history, so a state loaded mid-turn restarts the per-turn counters
        (attacks played, block gains, exhausts, HP lost). Pass the simulated state from after the last
        action to keep them; nothing is carried into a different turn."""
        if previous is None or previous.turn_number != self.turn_number:
            return
        old, new = previous.player, self.player
        new.attacks_played_this_turn = old.attacks_played_this_turn
        new.card_blocks_this_turn = old.card_blocks_this_turn
        new.cards_exhausted_this_turn = old.cards_exhausted_this_turn
        new.lost_hp_this_turn = old.lost_hp_this_turn
        for relic_id, relic in new.relics.items():
            kept = old.relics.get(relic_id)
            if kept is not None:
                relic.value = kept.value        # Beating Remnant's damage so far this turn, the card types seen (Rainbow Ring)
                if relic_id in PER_TURN_FLAG and kept.used:
                    relic.used = True
        self.cards_played = max(self.cards_played, previous.cards_played)

    def carry_combat_counters(self, previous : CombatState | None):
        """Counters that last the whole fight and that the bridge does not report: the times the player has lost
        HP (Tear Asunder) and the times Inferno was played. Unlike the turn counters they carry across turns."""
        if previous is None:
            return
        old, new = previous.player, self.player
        new.hp_loss_events = max(new.hp_loss_events, old.hp_loss_events)
        for relic_id, relic in new.relics.items():
            kept = old.relics.get(relic_id)
            if kept is not None and kept.used and relic_id not in PER_TURN_FLAG and relic_id not in ALWAYS_REPORTED:
                relic.used = True       # the bridge does not say that a once-only relic has been spent
        if StatusId.INFERNO in new.status and old.inferno_plays > 0:
            new.inferno_plays = old.inferno_plays

    def carry_known_top(self, previous : CombatState | None):
        """The bridge lists the draw pile in no particular order, so the cards the agent put on top (Headbutt)
        are not marked. Pass the simulated state from after the last action to put them back on top, in order.
        Unlike the turn counters this holds across turns. If any of them is missing from the loaded draw pile
        (it was reshuffled, or the game disagreed), the knowledge is dropped."""
        new = self.player
        new.known_top = 0
        if previous is None or previous.player.known_top <= 0:
            return
        old = previous.player
        wanted = old.draw_pile[len(old.draw_pile) - old.known_top:]
        rest = list(new.draw_pile)
        top = []
        for card in wanted:
            match = next((i for i, c in enumerate(rest) if c.card_id == card.card_id and c.is_upgraded == card.is_upgraded), None)
            if match is None:
                return
            top.append(rest.pop(match))
        new.draw_pile = rest + top
        new.known_top = len(top)

    def _infer_ringing_play(self):
        """Ringing with nothing in hand playable: the one card was already played this turn."""
        hand = self.player.hand
        if StatusId.RINGING not in self.player.status or any(not c.is_unplayable for c in hand):
            return
        candidates = [c for c in hand if c.type != CardType.Status]
        if candidates:
            self.cards_played = 1
            for c in candidates:
                c.is_unplayable = False

    def _infer_revivals(self):
        """A summoned monster missing from the bridge state, after its summoner has used the
        summoning move, was killed this turn and will return."""
        for enemy in self.enemies:
            summon = SUMMONS.get(enemy.enemy_id.rpartition("_")[0])
            if summon is None or enemy.moves is None or enemy.move_id in (None, summon[0]):
                continue
            monster, slot = summon[1], summon[2]
            if not any(e.enemy_id == f"{monster}_{slot}" for e in self.enemies):
                self.revivals.append((monster, slot))

    @classmethod
    def deepcopy(cls, combat_state : CombatState) -> CombatState:
        new_cs = cls()
        new_cs.player = Player.deepcopy(combat_state.player)
        new_cs.enemies = []
        for enemy in combat_state.enemies:
            new_cs.enemies.append(Enemy.deepcopy(enemy))
        new_cs.max_energy = combat_state.max_energy
        new_cs.energy = combat_state.energy
        new_cs.turn_number = combat_state.turn_number
        new_cs.ascension = combat_state.ascension
        new_cs.revivals = list(combat_state.revivals)
        new_cs.cards_played = combat_state.cards_played
        new_cs.pending_choice = combat_state.pending_choice.deepcopy() if combat_state.pending_choice else None
        return new_cs
        
    def readable(self) -> str:
        output = ""
        output += "Turn : " + str(self.turn_number) + "\n"
        output += "Energy : " + str(self.energy) + "\n"
        output += "Player : \n" + self.player.readable()
        output += "Enemies : \n"
        for enemy in self.enemies:
            output += enemy.readable()
        return output

class IllegalActionError(ValueError):
    """Raised when an action is not legal in the current state."""

class _CardInPlay:
    """Context manager behind CombatSimulator._playing; a plain class because it runs on every card played."""
    __slots__ = ("simulator", "card", "previous")

    def __init__(self, simulator : CombatSimulator, card : Card):
        self.simulator = simulator
        self.card = card

    def __enter__(self):
        self.previous = self.simulator.card_in_play
        self.simulator.card_in_play = self.card

    def __exit__(self, *exc):
        self.simulator.card_in_play = self.previous


class CombatSimulator:
    combat_state : CombatState
    is_over : bool = False
    ethereal_exhaust : bool = False     # set while the hand is discarded at end of turn
    in_enemy_turn : bool = False        # set while the enemies act
    _announced_block : int | None = None    # block given through gain_block while the player's turn starts

    def __init__(self, combat_state : CombatState):
        self.combat_state = combat_state
        self.card_in_play = None        # the card whose effect is being resolved, for relics that care which card dealt damage
        combat_state.player.draw_hook = self._card_drawn
        combat_state.player.shuffle_hook = self._shuffled
        self._check_is_over()

    ###
    ### Events
    ###

    def gain_energy(self, amount : int):
        """Energy gained during a turn. Expect a Fight stops it for the rest of the turn."""
        if StatusId.NO_ENERGY_GAIN in self.combat_state.player.status:
            return
        self.combat_state.energy += amount

    def fire(self, event : EventType, *args):
        """Call the status handler for each (status, event) pair in the state."""
        cs = self.combat_state
        if event == EventType.CARD_EXHAUSTED and args and args[0].card_id == CardId.DRUM_OF_BATTLE:
            self.gain_energy(3 if args[0].is_upgraded else 2)
        for creature in [cs.player, *cs.enemies]:
            for status_id, inst in list(creature.status.items()):  # copy: handlers add statuses
                handler = STATUS_HANDLERS.get((status_id, event))
                if handler is not None:
                    handler(self, creature, inst.amount, *args)
        if cs.player.relics:
            fire_relics(self, event, *args)

    ###
    ### Interface points
    ###

    def perform_action(self, action: dict):
        if self.is_over:
            return
        if action["action"] == "end_turn":
            self.end_turn()
            return
        if action["action"] == "play_card":
            self.play_card(action["card_index"], action["target"])
            return
        if action["action"] == "choose_card":
            self.choose_card(action["card_index"])
            return

    def _pile(self, name : str) -> list[Card]:
        player = self.combat_state.player
        return player.discard_pile if name == "discard" else player.hand

    def request_choice(self, kind : str, indices : list[int], pile : str = "hand", amount : int = 0):
        """Ask the player to pick one of the cards at `indices` of a pile. Cards that are the same count
        once, and a lone option is taken without asking. With no option the pick is skipped."""
        cards = self._pile(pile)
        seen, options = set(), []
        for i in indices:
            key = (cards[i].card_id, cards[i].is_upgraded, cards[i].energy_cost)
            if key not in seen:
                seen.add(key)
                options.append(i)
        if len(options) == 1:
            self._apply_choice(PendingChoice(kind, options, pile, amount), options[0])
        elif options:
            self.combat_state.pending_choice = PendingChoice(kind, options, pile, amount)
        elif amount:
            self.combat_state.player.draw_cards(amount)

    def choose_card(self, card_index : int):
        pending = self.combat_state.pending_choice
        if pending is None:
            raise IllegalActionError("no card choice is waiting")
        if card_index not in pending.indices:
            raise IllegalActionError(f"card_index {card_index} is not one of {pending.indices}")
        self.combat_state.pending_choice = None
        self._apply_choice(pending, card_index)

    def _apply_choice(self, choice : PendingChoice, index : int):
        player = self.combat_state.player
        card = self._pile(choice.pile)[index]
        if choice.kind == "upgrade":
            player.upgrade_card(card)
        elif choice.kind == "exhaust":
            player.exhaust_card(card)
            self.fire(EventType.CARD_EXHAUSTED, card)
            player.draw_cards(choice.amount)
        elif choice.kind == "to_draw_pile":
            player.discard_pile.remove(card)
            player.put_on_top(card)                 # the end of the list is the top

    def play_card(self, card_index : int, target_index : int):
        if self.is_over:
            return
        if self.combat_state.pending_choice is not None:
            raise IllegalActionError("a card choice must be made first")
        
        hand = self.combat_state.player.hand
        if not 0 <= card_index < len(hand):
            raise IllegalActionError(f"card_index {card_index} not in hand of {len(hand)}")
        card = hand[card_index]
        hp_loss_mark = self.combat_state.player.hp_loss_events
        if not card.can_play_card(self, target_index):
            raise IllegalActionError(f"{card.name} cannot be played (energy {self.combat_state.energy})")

        # the card leaves the hand first; it reaches its pile after the card-played hooks
        hand.pop(card_index)
        emptied = not hand
        original, card = card, self.private_copy(card)
        try:
            with self._playing(card):
                card.play_card(self, target_index)
        except ValueError:
            hand.insert(card_index, original)
            release_card(self.combat_state.player)
            raise
        self.combat_state.cards_played += 1
        if emptied:
            self.fire(EventType.HAND_EMPTIED)         # after the play succeeded: a refused play must not draw

        self._finish_card_play(card, hp_loss_mark)

    def _playing(self, card : Card) -> _CardInPlay:
        """Marks `card` as the one being played (cards can play other cards, so the previous one is put back)."""
        return _CardInPlay(self, card)

    @staticmethod
    def private_copy(card : Card) -> Card:
        """Cards that grow when played (Rampage, Thrash) are played as a copy: card objects are shared between
        simulated states, so the played one must not be changed in place. The copy goes to the discard pile."""
        return Card.create_copy(card) if card.card_id in (CardId.RAMPAGE, CardId.THRASH) else card

    def _shuffled(self):
        self.fire(EventType.SHUFFLED)

    def _sync_hp(self):
        """Relics that react to hit points hear about what happened since the last time (they cannot react on the spot: the
        creature that loses the hit points knows nothing about the fight)."""
        player = self.combat_state.player
        if not player.relics:
            return
        lost, player.hp_lost_log = player.hp_lost_log, []
        if player.current_hp > 0:
            for amount in lost:
                self.fire(EventType.HP_LOST, amount)
        self.fire(EventType.HP_CHANGED)

    def _card_drawn(self, card : Card):
        """Hellraiser plays a Strike the moment it is drawn."""
        player = self.combat_state.player
        if StatusId.HELLRAISER in player.status and card.card_id in STRIKE_CARDS and not self.is_over \
                and any(c is card for c in player.hand):
            self.auto_play(card)

    def _finish_card_play(self, card : Card, hp_loss_mark : int, force_exhaust : bool = False):
        player = self.combat_state.player
        if card.type == CardType.Attack:
            player.attacks_played_this_turn += 1
            player.reduce_stomp_costs()
        if player.relics:
            after_card_played(player, card)
        self.fire(EventType.CARD_PLAYED, card)
        if player.relics:
            card = upgraded_after_play(player, card)        # Razor Tooth
        self._move_played_card(card, force_exhaust)
        self._after_hp_loss(hp_loss_mark)

        self.resolve_deaths()
        self._check_is_over()

    def auto_play(self, card : Card, force_exhaust : bool = False):
        """Play a card from any pile for free, at a random target if it needs one."""
        cs = self.combat_state
        player = cs.player
        living = [i for i, e in enumerate(cs.enemies) if e.current_hp > 0]
        if card.target_type == TargetType.AnyEnemy:
            if not living:
                return
            target = living[0] if len(living) == 1 else rng.choice(living)
        else:
            target = 0
        if card in player.hand:
            player.hand.remove(card)
        elif card in player.draw_pile:
            player.remove_from_draw_pile(card)
        elif card in player.discard_pile:
            player.discard_pile.remove(card)
        elif card in player.exhaust_pile:
            player.exhaust_pile.remove(card)
        hp_loss_mark = player.hp_loss_events
        card = self.private_copy(card)
        with self._playing(card):
            card.play_card(self, target, free=True)
        self._finish_card_play(card, hp_loss_mark, force_exhaust)

    def _rupture(self, hp_loss_mark : int):
        """Strength for each time hit points were lost since the mark."""
        player = self.combat_state.player
        lost = player.hp_loss_events - hp_loss_mark
        if lost > 0 and StatusId.RUPTURE in player.status:
            player.apply_status(StatusId.STRENGTH, player.status_amount(StatusId.RUPTURE) * lost)

    def _after_hp_loss(self, hp_loss_mark : int):
        """Everything that reacts to the player losing HP on their own turn."""
        self._sync_hp()
        self._rupture(hp_loss_mark)
        self._inferno(hp_loss_mark)

    def _inferno(self, hp_loss_mark : int):
        """Inferno hurts every enemy each time the player loses HP on their own turn."""
        player = self.combat_state.player
        lost = player.hp_loss_events - hp_loss_mark
        if lost <= 0 or StatusId.INFERNO not in player.status:
            return
        for _ in range(lost):
            for enemy in [e for e in self.combat_state.enemies if e.current_hp > 0]:
                enemy.apply_damage(player.status_amount(StatusId.INFERNO))
        self.resolve_deaths()

    def gain_block(self, creature : Creature, amount : int):
        """Block that has already been through Dexterity and Frail (or never is)."""
        creature.apply_block(amount)
        if amount > 0:
            if self._announced_block is not None and creature is self.combat_state.player:
                self._announced_block += amount
            self.fire(EventType.BLOCK_GAINED, creature, amount)

    def _move_played_card(self, card : Card, force_exhaust : bool = False):
        player = self.combat_state.player
        if card.type == CardType.Power or card in player.exhaust_pile:
            return
        corrupted = card.type == CardType.Skill and StatusId.CORRUPTION in player.status
        if card.exhausts or force_exhaust or corrupted:
            player.exhaust_card(card)
            self.fire(EventType.CARD_EXHAUSTED, card)
        else:
            player.discard_pile.append(card)

    def end_turn(self):
        if self.is_over:
            return
        if self.combat_state.pending_choice is not None:
            raise IllegalActionError("a card choice must be made first")

        hp_loss_mark = self.combat_state.player.hp_loss_events
        self.fire(EventType.PLAY_PHASE_END)
        self.resolve_deaths()
        for card in [c for c in self.combat_state.player.exhaust_pile if c.card_id == CardId.HOWL_FROM_BEYOND]:
            if not self.is_over:
                self.auto_play(card)            # Howl from Beyond plays itself from the exhaust pile
        self.fire(EventType.END_TURN)
        self.resolve_deaths()
        for card in list(self.combat_state.player.hand):
            card.on_turn_end_in_hand(self)
        self._after_hp_loss(hp_loss_mark)
        self._check_is_over()
        if self.is_over:
            return

        self._discard_hand()
        self.fire(EventType.PLAYER_TURN_ENDED)
        self.resolve_deaths()
        self._check_is_over()
        if self.is_over:
            return
        player = self.combat_state.player
        player.status.pop(StatusId.NO_DRAW, None)           # Battle Trance and Expect a Fight last
        player.status.pop(StatusId.NO_ENERGY_GAIN, None)    # until the end of the player's turn
        player.restore_free_cards()
        self._return_temporary_strength(player)
        before = set(self.combat_state.player.status)
        self._play_enemy_turn()
        for enemy in self.combat_state.enemies:
            self._return_temporary_strength(enemy)
        self._decrease_statuses(self.combat_state.player, skip=set(self.combat_state.player.status) - before)
        for e in self.combat_state.enemies:
            self._decrease_statuses(e)
        self.combat_state.turn_number += 1
        self._check_is_over()
        self._start_player_turn()

    ###
    ### Helper functions
    ###

    @staticmethod
    def _return_temporary_strength(creature : Creature):
        """Setup Strike and Mangle: the Strength they gave or took is returned when the creature's turn ends."""
        for marker, sign in ((StatusId.SETUP_STRIKE, 1), (StatusId.MANGLE, -1)):
            amount = creature.status.pop(marker, None)
            if amount is not None:
                creature.apply_status(StatusId.STRENGTH, -sign * amount.amount, bypass_artifact=True)

    def _discard_hand(self):
        player = self.combat_state.player
        exhausted = 0
        for card in list(player.hand):
            if card.ethereal:
                player.exhaust_card(card)
                self.ethereal_exhaust = True
                self.fire(EventType.CARD_EXHAUSTED, card)
                self.ethereal_exhaust = False
                exhausted += 1
        if not (RelicId.RINGING_TRIANGLE in player.relics and self.combat_state.turn_number <= 1):
            player.discard_pile.extend(player.hand)     # Ringing Triangle keeps the hand after the first turn
            player.hand.clear()
        if exhausted:
            self.fire(EventType.ETHEREAL_EXHAUSTED, exhausted)

    def _start_player_turn(self):
        player = self.combat_state.player
        if RelicId.ICE_CREAM in player.relics and self.combat_state.turn_number > 1:
            self.combat_state.energy += self.combat_state.max_energy        # Ice Cream: unspent energy is kept
        else:
            self.combat_state.energy = self.combat_state.max_energy
        self.combat_state.cards_played = 0
        self.fire(EventType.BEFORE_PLAYER_TURN)
        retained_block = player.block_kept_at_turn_start()
        hp_loss_mark = player.hp_loss_events
        self._announced_block = 0
        player.turn_start()
        # Plating and Crimson Mantle gave block without anyone being told; block given through gain_block (The Abacus,
        # when the draw shuffles) has already been announced
        self.gain_block(player, player.block - retained_block - self._announced_block)
        self._announced_block = None
        self._after_hp_loss(hp_loss_mark)
        self.fire(EventType.PLAYER_TURN_START)
        self._check_is_over()           # Mercury Hourglass can end the fight
        for enemy in self.combat_state.enemies:
            enemy.turn_start()

    def _decrease_statuses(self, creature : Creature, skip : set[StatusId] = frozenset()):
        """Tick durations. `skip`: debuffs an enemy applied this turn, which start counting next turn."""
        to_remove : list[StatusId] = []
        for s in creature.status.values():
            if s.status_id in skip:
                continue
            if s.behaviour == StatusBehaviour.STATIC:
                continue
            elif s.behaviour == StatusBehaviour.DECREASE_BY_ONE:
                s.amount = s.amount -1
                if s.amount <= 0:
                    to_remove.append(s.status_id)
            elif s.behaviour == StatusBehaviour.RESET_TO_ZERO:
                s.amount = 0
        for s in to_remove:
            del creature.status[s]

    def _play_enemy_turn(self):
        self.in_enemy_turn = True
        try:
            for enemy in list(self.combat_state.enemies):     # enemies summoned now act next turn
                enemy.perform_turn(self)
                self.resolve_deaths()        # an attacker can die to Flame Barrier
                self._sync_hp()
            self.fire(EventType.ENEMY_TURN_END)
        finally:
            self.in_enemy_turn = False
        self._revive()

    def _revive(self):
        revivals, self.combat_state.revivals = self.combat_state.revivals, []
        if all(e.is_minion for e in self.combat_state.enemies):
            return      # minions do not come back without their leader
        for monster, slot in revivals:
            self.summon(Enemy.spawn(monster, slot, self.combat_state.ascension), front=True)
    
    def resolve_deaths(self):
        """Remove dead enemies and run their death effects. Cards with several hits call this
        between hits so that enemies summoned by a death can be hit by the later ones."""
        while True:
            dead = [e for e in self.combat_state.enemies if e.current_hp <= 0]
            if not dead:
                return
            self.combat_state.enemies = [e for e in self.combat_state.enemies if e.current_hp > 0]
            for enemy in dead:
                self._fire_death(enemy)
                self.fire(EventType.CREATURE_KILLED, enemy)

    def _fire_death(self, creature : Creature):
        for status_id, inst in list(creature.status.items()):
            handler = STATUS_HANDLERS.get((status_id, EventType.DEATH))
            if handler is not None:
                handler(self, creature, inst.amount)

    def summon(self, enemy : Enemy, front : bool = False):
        """Add an enemy mid-fight. What it does first is up to its own moves."""
        if front:
            self.combat_state.enemies.insert(0, enemy)
        else:
            self.combat_state.enemies.append(enemy)

    def _check_is_over(self):
        # if player is alive and there is an alive non-minion enemy
        if self.combat_state.player.current_hp <= 0:
            self.is_over = True
            return
        
        for enemy in self.combat_state.enemies:
            if not enemy.is_minion:
                self.is_over = False
                return

        self.is_over = True

    ###
    ### Calculators
    ###

    def get_available_actions(self) -> list[dict]:
        output = []
        pending = self.combat_state.pending_choice
        if pending is not None:
            cards = self._pile(pending.pile)
            return [{"action" : "choose_card", "card_index" : i, "pile" : pending.pile,
                     "card_id" : cards[i].card_id.name, "is_upgraded" : cards[i].is_upgraded}
                    for i in pending.indices]

        for c_i, c in enumerate(self.combat_state.player.hand):
            if c.target_type in (TargetType.Self, TargetType.AllEnemies, TargetType.RandomEnemy, TargetType.NONE):
                if c.can_play_card(self, 0):
                    output.append({"action" : "play_card", "card_index" : c_i, "target" : 0})
            elif c.target_type == TargetType.AnyEnemy:
                for e_i, e in enumerate(self.combat_state.enemies):
                    if c.can_play_card(self, e_i):
                        output.append({"action" : "play_card", "card_index" : c_i, "target" : e_i, "target_name" : e.enemy_id})

        output.append({"action" : "end_turn"})
        return output

    def calculate_damage(self, initial_damage : int, owner: Creature, target : Creature) -> int:
        return modify_damage(initial_damage, owner, target, self.card_in_play)

    def calculate_block(self, initial_block : int, owner : Creature, multiplier : int = 1) -> int:
        # Dexterity, then Frail and any other multiplier (Unmovable)
        block = initial_block + owner.status_amount(StatusId.DEXTERITY)
        if StatusId.FRAIL in owner.status:
            block *= 0.75
        return max(0, int(block * multiplier))
