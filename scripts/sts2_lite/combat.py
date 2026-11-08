from __future__ import annotations
import re
import itertools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatState

from sts2_lite.creature import Creature
from sts2_lite.player import Player
from sts2_lite.enemy import Enemy
from sts2_lite.card import TargetType, CardType, Card, CardId, STRIKE_CARDS, NORMALITY_CARD_LIMIT, CHANGED_ON_PLAY, MAX_HAND_SIZE, RETURNING_CARDS, transform_options
from sts2_lite.damage import modify_damage, base_from_displayed, bases_from_displayed, EPSILON
from sts2_lite import rng
from sts2_lite.events import EventType
from sts2_lite.relic import RelicId, PER_TURN_FLAG, ALWAYS_REPORTED, take_extra_turn, after_card_played, release_card, fire_relics, blocks_play, PHILOSOPHERS_STONE_STRENGTH, upgraded_after_play, \
    max_energy_gain, victory_heal

from sts2_lite.status import StatusId, StatusBehaviour, STATUS_HANDLERS, AUTOMATION_CARDS, face_target, SLOTH_LIMIT
from sts2_lite.enemy_moves import SUMMONS, SEGMENTS

# what the bridge calls each kind of hand selection
HAND_SELECT_MODES = {"upgrade_select" : "upgrade"}

OPTIONAL_PICKS = frozenset({"to_hand", "exhaust_any", "discover"})       # Neow's Fury, Purity, Discovery (skippable)

KNOWLEDGE_CURSES = {CardId.DISINTEGRATION : StatusId.DISINTEGRATION, CardId.MIND_ROT : StatusId.MIND_ROT,
                    CardId.SLOTH : StatusId.SLOTH, CardId.WASTE_AWAY : StatusId.WASTE_AWAY}
KNOWLEDGE_CURSE_AMOUNTS = {CardId.MIND_ROT : 1, CardId.SLOTH : SLOTH_LIMIT, CardId.WASTE_AWAY : 1}      # Disintegration's depends on the cast


class PendingChoice:
    """A card the player must pick before anything else can happen."""
    def __init__(self, kind : str, indices : list[int], pile : str = "hand", amount : int = 0, source : Card | None = None, hidden : bool = False,
                 offers : list[Card] | None = None, picked : list[int] | None = None):
        self.offers = offers or []  # pile "offer": cards made up for the choice (Discovery), not in any pile
        self.picked = picked or []  # transform: hand positions already chosen, changed once the last pick is made
        self.hidden = hidden        # the options were drawn at random and the game shows its own (Seeker Strike): see adopt_offer
        self.kind = kind            # what the pick does, see CombatSimulator._apply_choice
        self.indices = indices      # positions in the pile that may be picked
        self.pile = pile            # "hand" or "discard"
        self.optional = kind in OPTIONAL_PICKS      # "up to N": the player may stop picking (confirm_choice)
        self.source = source        # to_hand: the card being played, which reaches the discard pile before the second pick
        self.amount = amount        # Burning Pact: cards to draw after the pick; to_hand: picks still to make, this one included

    def deepcopy(self) -> PendingChoice:
        return PendingChoice(self.kind, list(self.indices), self.pile, self.amount, self.source, self.hidden, list(self.offers), list(self.picked))

class CombatState:
    player : Player
    energy : int
    max_energy : int
    enemies : list[Enemy]
    turn_number : int       # CombatState.RoundNumber: enemies' move patterns
    extra_turns : int = 0   # extra player turns taken (Pael's Eye); the round does not advance for them
    ascension : int = 0

    @property
    def player_turn(self) -> int:
        """PlayerCombatState.TurnNumber: RoundNumber plus the extra turns. Relics count these."""
        return self.turn_number + self.extra_turns

    def __init__(self):
        self.enemies = []
        self.cards_played = 0   # this player turn
        self.revivals = []      # (monster, slot) killed enemies that return after the enemy turn
        self.dormant = []       # Decimillipede segments that were killed and will reattach: out of the fight, not dead
        self.pending_choice = None
        self.won = False         # victory heals applied

    @classmethod
    def from_dict(cls, combat_state : dict):
        if "enemies" not in combat_state and "battle" in combat_state:
            # a card-selection screen nests the fight under "battle" and has no top-level energy
            battle = combat_state["battle"]
            combat_state = {**combat_state, "enemies": battle["enemies"], "round": battle["round"],
                            "energy": battle["player"]["energy"], "max_energy": battle["player"]["max_energy"],
                            "reviving": battle.get("reviving", [])}
        cs = cls()
        cs.player = Player.from_dict(combat_state["player"])
        cs.player.remove_displayed_tangled()
        cs.enemies = []
        ascension = combat_state.get("context", {}).get("ascension", 0)
        cs.ascension = ascension
        for enemy in combat_state["enemies"]:
            cs.enemies.append(Enemy.from_dict(enemy, ascension))
        cs.turn_number = combat_state["round"]
        eye = cs.player.relics.get(RelicId.PAELS_EYE)
        if eye is not None:
            cs._read_paels_eye(eye, combat_state["player"].get("relics", []))
        for raw_status in combat_state["player"].get("status", ()):
            if raw_status["id"] == "SLOTH_POWER":
                cs.cards_played = max(cs.cards_played, raw_status["amount"])        # Sloth shows the cards played this turn
        cs._infer_surround_facing(combat_state["enemies"])
        for enemy, raw in zip(cs.enemies, combat_state["enemies"]):
            if enemy.num_attacks > 0 and not Enemy.reads_base_damage(raw["intents"]):
                enemy.damage_candidates = bases_from_displayed(enemy.attack_damage, enemy, cs.player)
                enemy.attack_damage = base_from_displayed(enemy.attack_damage, enemy, cs.player)
            if enemy.move_id is None:       # not given by the bridge's move_id: infer it from the intents
                enemy.identify_move(raw["intents"], cs.turn_number)
            enemy.check_against_bridge(raw, cs.player)
        cs._infer_revivals()
        cs._infer_dormant_segments(combat_state.get("reviving"))
        cs._infer_ringing_play()
        cs.energy = combat_state["energy"]
        cs.max_energy = combat_state["max_energy"]
        cs._infer_normality_plays()
        if combat_state.get("decision") == "hand_select":
            cs._load_hand_select(combat_state)
        return cs

    def _load_hand_select(self, state : dict):
        """The game is waiting for a hand card to be picked; the picks it lists become the choice."""
        kind, amount = HAND_SELECT_MODES.get(state["mode"]), 0
        if kind is None and state["mode"] == "simple_select":     # the prompt is all that says what the pick is for
            prompt = state.get("prompt") or ""
            match = re.search(r"up to (\d+) cards? to Exhaust", prompt)        # Purity
            if match:
                kind, amount = "exhaust_any", int(match.group(1)) - len(state.get("selected_cards") or [])
            elif "on top of your Draw Pile" in prompt:      # Thinking Ahead
                kind = "to_draw_pile"
            elif "to Transform" in prompt:      # Entropy: as many cards as it has stacks
                kind, amount = "transform", max(1, self.player.status_amount(StatusId.ENTROPY) - len(state.get("selected_cards") or []))
        if kind is None:
            raise ValueError(f"unknown card selection mode {state['mode']}")
        hand = self.player.hand
        indices, seen, used = [], set(), set()
        for ticked in state.get("selected_cards") or []:      # cards already ticked: still in the hand, no longer listed as picks
            i = next((i for i, card in enumerate(hand) if i not in used and card.name == ticked["name"]), None)
            if i is not None:
                used.add(i)
        for c in state["cards"]:
            # "index" counts the selectable cards only, not the hand: find the hand card it is
            i = next((i for i, card in enumerate(hand) if i not in used and card.card_id.name == c["id"]
                      and card.is_upgraded == c["is_upgraded"]), None)
            if i is None:
                raise ValueError(f"selectable card {c['id']} is not in the hand")
            used.add(i)
            key = (hand[i].card_id, hand[i].is_upgraded, hand[i].energy_cost)
            if key not in seen:
                seen.add(key)
                indices.append(i)
        self.pending_choice = PendingChoice(kind, indices, amount=amount)

    def adopt_offer(self, offered : list[dict]):
        """A pick whose options the sim drew at random (Seeker Strike, Discovery) has been put on screen by the game: offer
        the game's cards instead. `offered`: the select screen's card list."""
        pending = self.pending_choice
        if pending is None or not pending.hidden:
            return
        if pending.pile == "offer":         # cards that exist only on the screen
            pending.offers = [Card.create_generated(CardId[c["id"]], c["is_upgraded"]) if c["id"] in CardId.__members__ else Card.create_not_implemented(c.get("name") or c["id"]) for c in offered]
            pending.indices = list(range(len(pending.offers)))
            pending.hidden = False
            return
        pile = self.player.draw_pile if pending.pile == "draw" else self.player.hand
        used, keep, seen = set(), [], set()
        for c in offered:
            i = next((i for i, card in enumerate(pile) if i not in used and card.card_id.name == c["id"] and card.is_upgraded == c["is_upgraded"]), None)
            if i is None:
                continue
            used.add(i)
            key = (pile[i].card_id, pile[i].is_upgraded, pile[i].energy_cost)
            if key not in seen:         # identical cards are one option
                seen.add(key)
                keep.append(i)
        if keep:
            pending.indices = keep
        pending.hidden = False

    def _read_paels_eye(self, eye, raw_relics : list[dict]):
        """Spent: extra turn taken (TurnNumber = round + 1). Unspent and Normal: a card was played (PaelsEye.BeforeCardPlayed)."""
        if eye.used:
            self.extra_turns = 1
            return
        raw = next((r for r in raw_relics if r.get("id") == "PAELS_EYE"), {})
        if raw.get("status") == "Normal":
            self.cards_played = max(self.cards_played, 1)

    def carry_turn_counters(self, previous : CombatState | None):
        """The bridge reports no history, so a state loaded mid-turn restarts the per-turn counters
        (attacks played, block gains, exhausts, HP lost). Pass the simulated state from after the last
        action to keep them; nothing is carried into a different turn."""
        if previous is None or previous.player_turn != self.player_turn:
            return
        old, new = previous.player, self.player
        new.attacks_played_this_turn = old.attacks_played_this_turn
        new.plays_started_this_turn = old.plays_started_this_turn
        new.returning = list(old.returning)
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
        HP (Tear Asunder) and the times Inferno and Crimson Mantle were played. Unlike the turn counters they carry across turns."""
        if previous is None:
            return
        old, new = previous.player, self.player
        new.hp_loss_events = max(new.hp_loss_events, old.hp_loss_events)
        new.cards_played_total = max(new.cards_played_total, old.cards_played_total)
        for relic_id, relic in new.relics.items():
            kept = old.relics.get(relic_id)
            if kept is not None and kept.used and relic_id not in PER_TURN_FLAG and relic_id not in ALWAYS_REPORTED:
                relic.used = True       # the bridge does not say that a once-only relic has been spent
        if StatusId.INFERNO in new.status and old.inferno_plays > 0:
            new.inferno_plays = old.inferno_plays
        if StatusId.CRIMSON_MANTLE in new.status and old.crimson_mantle_plays > 0:
            new.crimson_mantle_plays = old.crimson_mantle_plays

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
        candidates = [c for c in hand if c.type != CardType.Status and c.type != CardType.Curse]
        if candidates:
            self.cards_played = 1
            for c in candidates:
                c.is_unplayable = False

    def _infer_normality_plays(self):
        """Normality in hand with an affordable, non-keyword-unplayable card the bridge shows as unplayable:
        the 3-card limit is already used up (the bridge reports no play count)."""
        hand, energy = self.player.hand, self.energy
        if not any(c.card_id == CardId.NORMALITY for c in hand):
            return
        blocked = [c for c in hand if c.is_unplayable and not c.unplayable and c.type not in (CardType.Status, CardType.Curse)
                   and (c.energy_cost == "X" or c.energy_cost <= energy)]
        if blocked:
            self.cards_played = max(self.cards_played, NORMALITY_CARD_LIMIT)
            for c in blocked:
                c.is_unplayable = False

    def _infer_surround_facing(self, raws : list[dict]):
        """The bridge reports Surrounded without the way it faces. An arm behind the player shows 1.5x its base damage, so the facing is
        whichever one explains every arm's shown damage (Right when nothing says: it is where a fight starts)."""
        player = self.player
        inst = player.status.get(StatusId.SURROUNDED)
        if inst is None:
            return
        possible = {0, 1}
        for enemy, raw in zip(self.enemies, raws):
            if StatusId.BACK_ATTACK_LEFT not in enemy.status and StatusId.BACK_ATTACK_RIGHT not in enemy.status:
                continue
            for intent in raw.get("intents", ()):
                if "base_damage" not in intent or "damage" not in intent:
                    continue
                enemy.attack_damage = intent["base_damage"]
                for facing in list(possible):
                    inst.records = [[facing]]
                    if modify_damage(intent["base_damage"], enemy, player) != intent["damage"]:
                        possible.discard(facing)
        inst.records = [[min(possible) if possible else 0]]

    def _infer_dormant_segments(self, reviving : list[dict] | None):
        """Killed Decimillipede segments waiting to reattach. The bridge lists them as `reviving`, with the move they are on. Without that
        field (an older bridge) any segment missing from the living is taken to have died on an earlier turn (its REATTACH is next)."""
        if reviving is not None:
            for raw in reviving:
                dormant = Enemy.dormant_segment(raw["entity_id"].rpartition("_")[0], self.ascension, raw["max_hp"])
                dormant.move_id = "DEAD" if raw.get("move_id") == "DEAD_MOVE" else "REATTACH"
                self.dormant.append(dormant)
            return
        present = {e.enemy_id.rpartition("_")[0] for e in self.enemies}
        if not present & set(SEGMENTS):
            return
        template = next(e for e in self.enemies if e.enemy_id.rpartition("_")[0] in SEGMENTS)
        for segment in SEGMENTS:
            if segment not in present:
                self.dormant.append(Enemy.dormant_segment(segment, self.ascension, template.max_hp))

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
        new_cs.extra_turns = combat_state.extra_turns
        new_cs.ascension = combat_state.ascension
        new_cs.revivals = list(combat_state.revivals)
        new_cs.dormant = [Enemy.deepcopy(e) for e in combat_state.dormant]
        new_cs.cards_played = combat_state.cards_played
        new_cs.pending_choice = combat_state.pending_choice.deepcopy() if combat_state.pending_choice else None
        new_cs.won = combat_state.won
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

_PLAY_IDS = itertools.count(1)      # unique across simulators

class _CardInPlay:
    """Context manager behind CombatSimulator._playing; a plain class because it runs on every card played."""
    __slots__ = ("simulator", "card", "previous", "previous_id")

    def __init__(self, simulator : CombatSimulator, card : Card):
        self.simulator = simulator
        self.card = card

    def __enter__(self):
        self.previous, self.previous_id = self.simulator.card_in_play, self.simulator.play_id
        self.simulator.card_in_play = self.card
        self.simulator.play_id = next(_PLAY_IDS)

    def __exit__(self, *exc):
        self.simulator.card_in_play, self.simulator.play_id = self.previous, self.previous_id


class CombatSimulator:
    combat_state : CombatState
    is_over : bool = False
    ethereal_exhaust : bool = False     # set while the hand is discarded at end of turn
    in_enemy_turn : bool = False        # set while the enemies act
    _announced_block : int | None = None    # block given through gain_block while the player's turn starts

    def __init__(self, combat_state : CombatState):
        self.combat_state = combat_state
        self.card_in_play = None        # the card whose effect is being resolved, for relics that care which card dealt damage
        self.play_id = None             # id of the current play; card objects can repeat
        self.vigor_pending = None       # Vigor the current attack command adds (VigorPower.BeforeAttack)
        self.auto_playing = False       # CardPlay.IsAutoPlay of the play being resolved
        self.card_x = 0                 # the X of the X-cost card last played
        combat_state.player.draw_hook = self._card_drawn
        combat_state.player.shuffle_hook = self._shuffled
        combat_state.player.block_cleared_hook = self._block_cleared
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
        if event is EventType.CARD_EXHAUSTED and args and args[0].card_id is CardId.DRUM_OF_BATTLE:
            self.gain_energy(3 if args[0].is_upgraded else 2)
        handlers = STATUS_HANDLERS.by_event.get(event)
        if handlers is not None:
            for creature in [cs.player, *cs.enemies]:
                for status_id, inst in list(creature.status.items()):  # copy: handlers add statuses
                    handler = handlers.get(status_id)
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
        if action["action"] == "confirm_choice":
            self.confirm_choice()
            return

    def _pile(self, name : str) -> list[Card]:
        player = self.combat_state.player
        if name == "draw":
            return player.draw_pile
        if name == "offer":
            return self.combat_state.pending_choice.offers
        return player.discard_pile if name == "discard" else player.hand

    def request_discovery(self, offers : list[Card]):
        """Discovery: pick one of the cards made up for the choice (or none); it joins the hand for free this turn."""
        self.combat_state.pending_choice = PendingChoice("discover", list(range(len(offers))), "offer", hidden=True, offers=offers)

    def request_curse(self, offers : list[Card], disintegration : int):
        """Knowledge Demon: choose a curse. It is a pick from the choose-a-card screen, no card is played; `amount` is what Disintegration deals."""
        self.combat_state.pending_choice = PendingChoice("curse", list(range(len(offers))), "offer", amount=disintegration, offers=offers)

    def request_transform(self, amount : int):
        """Entropy: choose `amount` cards in the hand to be turned into random cards."""
        hand = self.combat_state.player.hand
        eligible = [i for i, c in enumerate(hand) if transform_options(c)]
        if not eligible:
            return
        if len(eligible) <= amount:         # nothing to choose
            self._transform(eligible)
            return
        self.request_choice("transform", eligible, "hand", amount)

    def _transform(self, indices : list[int]):
        hand = self.combat_state.player.hand
        for i in indices:
            hand[i] = Card.create_generated(rng.choice(transform_options(hand[i])))

    def request_choice(self, kind : str, indices : list[int], pile : str = "hand", amount : int = 0, source : Card | None = None, hidden : bool = False,
                       picked : list[int] | None = None):
        """Ask the player to pick one of the cards at `indices` of a pile. Cards that are the same count
        once, and a lone option is taken without asking. With no option the pick is skipped."""
        cards = self._pile(pile)
        seen, options = set(), []
        for i in indices:
            key = (cards[i].card_id, cards[i].is_upgraded, cards[i].energy_cost)
            if key not in seen:
                seen.add(key)
                options.append(i)
        if len(options) == 1 and kind not in OPTIONAL_PICKS:     # "up to N" picks are optional, so a lone card is still offered
            self._apply_choice(PendingChoice(kind, options, pile, amount, source, hidden, picked=picked), options[0])
        elif options:
            self.combat_state.pending_choice = PendingChoice(kind, options, pile, amount, source, hidden, picked=picked)
        elif amount and kind == "exhaust":
            self.combat_state.player.draw_cards(amount)

    def confirm_choice(self):
        """Stop picking on an \"up to N\" choice (Neow's Fury)."""
        pending = self.combat_state.pending_choice
        if pending is None or not pending.optional:
            raise IllegalActionError("there is no optional card choice to confirm")
        self.combat_state.pending_choice = None
        self._check_hand_emptied()

    def choose_card(self, card_index : int):
        pending = self.combat_state.pending_choice
        if pending is None:
            raise IllegalActionError("no card choice is waiting")
        if card_index not in pending.indices:
            raise IllegalActionError(f"card_index {card_index} is not one of {pending.indices}")
        self.combat_state.pending_choice = None
        self._apply_choice(pending, card_index)
        self._check_hand_emptied()

    def _apply_choice(self, choice : PendingChoice, index : int):
        player = self.combat_state.player
        card = (choice.offers if choice.pile == "offer" else self._pile(choice.pile))[index]
        if choice.kind == "discover":
            player.add_to_hand(card.free_this_turn())
        elif choice.kind == "curse":
            player.apply_status(KNOWLEDGE_CURSES[card.card_id], choice.amount if card.card_id == CardId.DISINTEGRATION else KNOWLEDGE_CURSE_AMOUNTS[card.card_id])
            if card.card_id == CardId.WASTE_AWAY:       # the bridge reports max energy with it taken off, so the sim does the same
                self.combat_state.max_energy = max(0, self.combat_state.max_energy - KNOWLEDGE_CURSE_AMOUNTS[CardId.WASTE_AWAY])
            if not self.is_over:
                self._start_player_turn()           # the pick came in the enemy turn, which had finished
        elif choice.kind == "transform":
            picked = choice.picked + [index]
            eligible = [i for i, c in enumerate(player.hand) if i not in picked and transform_options(c)]
            if choice.amount > 1 and eligible:
                self.request_choice("transform", eligible, "hand", choice.amount - 1, picked=picked)
            else:
                self._transform(picked)
        elif choice.kind == "upgrade":
            player.upgrade_card(card)
        elif choice.kind == "exhaust":
            player.exhaust_card(card)
            self.fire(EventType.CARD_EXHAUSTED, card)
            player.draw_cards(choice.amount)
        elif choice.kind == "exhaust_any":
            player.exhaust_card(card)
            self.fire(EventType.CARD_EXHAUSTED, card)
            if choice.amount > 1 and player.hand:
                self.request_choice("exhaust_any", list(range(len(player.hand))), "hand", choice.amount - 1)
        elif choice.kind == "to_draw_pile":
            self._pile(choice.pile).remove(card)
            player.put_on_top(card)                 # the end of the list is the top
        elif choice.kind == "draw_to_hand":
            player.remove_from_draw_pile(card)
            (player.hand if len(player.hand) < MAX_HAND_SIZE else player.discard_pile).append(card)     # a full hand sends it to the discard pile
        elif choice.kind == "to_hand":
            if len(player.hand) >= 10:              # a full hand leaves the cards in the discard pile
                return
            player.discard_pile.remove(card)
            player.hand.append(card)
            if choice.amount > 1 and len(player.hand) < 10:
                discard = player.discard_pile
                options = list(range(len(discard)))
                for i in reversed(options):             # the card being played is not a candidate for its own effect
                    if discard[i] is choice.source:
                        del options[i]
                        break
                self.request_choice("to_hand", options, "discard", choice.amount - 1, choice.source)

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
        original, card = card, self.private_copy(card)
        to_top = self._nostalgia_mark(card)
        self._face_target(card, target_index)
        try:
            with self._playing(card):
                card.play_card(self, target_index)
        except ValueError:
            hand.insert(card_index, original)
            release_card(self.combat_state.player)
            raise
        self.combat_state.cards_played += 1
        self._finish_card_play(card, hp_loss_mark, to_top=to_top)
        self._check_hand_emptied()

    def _face_target(self, card : Card, target_index : int):
        """SurroundedPower.BeforeCardPlayed: a card aimed at an enemy turns the player towards it."""
        cs = self.combat_state
        if StatusId.SURROUNDED in cs.player.status and card.target_type == TargetType.AnyEnemy and 0 <= target_index < len(cs.enemies):
            face_target(cs.player, cs.enemies[target_index])

    def _check_hand_emptied(self):
        """CombatManager.CheckForEmptyHand: after a manual play fully resolves, never during auto-plays."""
        if not self.is_over and self.combat_state.pending_choice is None and not self.combat_state.player.hand:
            self.fire(EventType.HAND_EMPTIED)

    def _playing(self, card : Card) -> _CardInPlay:
        """Marks `card` as the one being played (cards can play other cards, so the previous one is put back)."""
        return _CardInPlay(self, card)

    @staticmethod
    def private_copy(card : Card) -> Card:
        """Cards that change when played (Rampage, Thrash, Swift/Sown/Vigorous/Momentum/Glam) are played as a copy: card objects are shared between
        simulated states, so the played one must not be changed in place. The copy goes to the discard pile."""
        if card.card_id in (CardId.RAMPAGE, CardId.THRASH) or card.enchantment in CHANGED_ON_PLAY:
            return Card.create_copy(card)
        return card

    def vigor_bonus(self) -> int:
        """VigorPower: the first attack command takes the whole amount for all its hits."""
        if self.vigor_pending is None:
            amount = self.combat_state.player.status_amount(StatusId.VIGOR)
            if amount <= 0:
                return 0
            self.vigor_pending = amount
        return self.vigor_pending

    def finish_vigor(self):
        """VigorPower.AfterAttack: spend the amount the command started with."""
        if self.vigor_pending is None:
            return
        player = self.combat_state.player
        vigor = player.status.get(StatusId.VIGOR)
        if vigor is not None:
            vigor.amount -= self.vigor_pending
            if vigor.amount <= 0:
                del player.status[StatusId.VIGOR]
        self.vigor_pending = None

    def _shuffled(self):
        self.fire(EventType.SHUFFLED)

    def _block_cleared(self):
        self.fire(EventType.BLOCK_CLEARED)

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
        """Automation counts every card drawn; Hellraiser plays a Strike the moment it is drawn."""
        player = self.combat_state.player
        automation = player.status.get(StatusId.AUTOMATION)
        if automation is not None:
            for record in automation.records:
                record[0] -= 1
                if record[0] <= 0:
                    self.gain_energy(1)
                    record[0] = AUTOMATION_CARDS
            automation.sync()
        if StatusId.HELLRAISER in player.status and card.card_id in STRIKE_CARDS and not self.is_over \
                and any(c is card for c in player.hand):
            self.auto_play(card)

    def card_played_hooks(self, card : Card):
        """Everything that follows one play of a card (a card played twice runs it twice)."""
        player = self.combat_state.player
        player.cards_played_total += 1
        if card.type == CardType.Attack:
            player.attacks_played_this_turn += 1
            player.reduce_stomp_costs()
        if player.relics:
            after_card_played(player, card)
        self.fire(EventType.CARD_PLAYED, card)

    def _nostalgia_mark(self, card : Card) -> bool:
        """NostalgiaPower.ModifyCardPlayResultPileTypeAndPosition, asked before the card's plays begin: while fewer than
        Amount Attacks and Skills have been played this turn, this one ends on top of the draw pile instead of the discard pile."""
        player = self.combat_state.player
        nostalgia = player.status.get(StatusId.NOSTALGIA)
        return nostalgia is not None and card.type in (CardType.Attack, CardType.Skill) and player.plays_started_this_turn < nostalgia.amount

    def _finish_card_play(self, card : Card, hp_loss_mark : int, force_exhaust : bool = False, dupe : bool = False, to_top : bool = False):
        player = self.combat_state.player
        self.card_played_hooks(card)
        if player.relics:
            card = upgraded_after_play(player, card)        # Razor Tooth
        if not dupe:
            self._move_played_card(card, force_exhaust, to_top)     # GetResultPileTypeForCardPlay: a dupe goes nowhere
        self._after_hp_loss(hp_loss_mark)

        self.resolve_deaths()
        self._check_is_over()

    def auto_play(self, card : Card, force_exhaust : bool = False, dupe : bool = False, x_value : int | None = None):
        """Play a card from any pile for free, at a random target if it needs one. A dupe (CardModel.CreateDupe) is
        in no pile afterwards."""
        cs = self.combat_state
        player = cs.player
        living = [i for i, e in enumerate(cs.enemies) if e.current_hp > 0]
        if card.target_type == TargetType.AnyEnemy:
            if not living:
                return
            target = living[0] if len(living) == 1 else rng.choice(living)
        else:
            target = 0
        self._face_target(card, target)
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
        to_top = self._nostalgia_mark(card)
        self.finish_vigor()             # an attack that led here (Pommel Strike's draw) has finished
        if player.relics and blocks_play(player):
            self._move_played_card(card, force_exhaust, played=False)     # Velvet Choker: ShouldPlay false -> result pile unplayed
            return
        auto_playing, self.auto_playing = self.auto_playing, True
        try:
            with self._playing(card):
                card.play_card(self, target, free=True, x_value=x_value)
            self._finish_card_play(card, hp_loss_mark, force_exhaust, dupe, to_top)
        finally:
            self.auto_playing = auto_playing

    def auto_play_from_top(self, count : int):
        """CardPileCmd.AutoPlayFromDrawPile (Cascade, Mayhem): the cards are all taken off the top first, then played in that
        order. An Unplayable card goes to the discard pile unplayed."""
        player = self.combat_state.player
        taken = []
        for _ in range(count):
            top = player.take_top()
            if top is None:
                break
            taken.append(top)
        for top in taken:
            if self.is_over:
                break
            if top.unplayable:
                player.discard_pile.append(top)
            else:
                self.auto_play(top)

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
                enemy.apply_damage(player.status_amount(StatusId.INFERNO), player)
        self.resolve_deaths()

    def gain_block(self, creature : Creature, amount : int):
        """Block that has already been through Dexterity and Frail (or never is)."""
        creature.apply_block(amount)
        if amount > 0:
            if self._announced_block is not None and creature is self.combat_state.player:
                self._announced_block += amount
            self.fire(EventType.BLOCK_GAINED, creature, amount)

    def _move_played_card(self, card : Card, force_exhaust : bool = False, to_top : bool = False, played : bool = True):
        player = self.combat_state.player
        if card.card_id in RETURNING_CARDS:
            player.returning.append((card.card_id, card.is_upgraded))        # comes back to the hand next turn (BeforeHandDraw)
        if card.type == CardType.Power:
            return
        if card in player.exhaust_pile:             # exhausted during its own play
            if played and card.until_played:
                pile = player.exhaust_pile
                pile[next(i for i, c in enumerate(pile) if c is card)] = card.cost_after_play()
            return
        if played:
            card = card.cost_after_play()           # AfterCardPlayedCleanup (the game runs it after the move; same result)
        corrupted = card.type == CardType.Skill and StatusId.CORRUPTION in player.status
        if card.exhausts or force_exhaust or corrupted:
            player.exhaust_card(card)
            self.fire(EventType.CARD_EXHAUSTED, card)
        elif to_top:
            player.put_on_top(card)         # Nostalgia
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
        if self.combat_state.player.relics:         # only relics hook it (Pael's Eye)
            self.fire(EventType.TURN_END_EARLY)
            self.resolve_deaths()
        self.fire(EventType.END_TURN)
        self.resolve_deaths()
        for card in list(self.combat_state.player.hand):
            card.on_turn_end_in_hand(self)
        self._after_hp_loss(hp_loss_mark)
        self._check_is_over()
        if self.is_over:
            return

        self._discard_hand()
        retain = self.combat_state.player.status.get(StatusId.RETAIN_HAND)
        if retain is not None:          # RetainHandPower.AfterSideTurnEnd
            retain.amount -= 1
            if retain.amount <= 0:
                del self.combat_state.player.status[StatusId.RETAIN_HAND]
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
        if player.relics and take_extra_turn(self):
            self._take_extra_turn()
            return
        before = set(self.combat_state.player.status)
        self._play_enemy_turn()
        for enemy in self.combat_state.enemies:
            self._return_temporary_strength(enemy)
        self._decrease_statuses(self.combat_state.player, skip=set(self.combat_state.player.status) - before)
        for e in self.combat_state.enemies:
            self._decrease_statuses(e)
        self.combat_state.turn_number += 1
        self._check_is_over()
        if self.combat_state.pending_choice is not None and not self.is_over:
            return          # Knowledge Demon's curse: the next turn starts once one is picked
        self._start_player_turn()

    ###
    ### Helper functions
    ###

    @staticmethod
    def _return_temporary_strength(creature : Creature):
        """Setup Strike, Mangle and Dark Shackles: the Strength they gave or took is returned when the creature's turn ends."""
        for marker, sign in ((StatusId.SETUP_STRIKE, 1), (StatusId.MANGLE, -1), (StatusId.DARK_SHACKLES, -1)):
            amount = creature.status.pop(marker, None)
            if amount is not None:
                creature.apply_status(StatusId.STRENGTH, -sign * amount.amount, bypass_artifact=True)

    def _take_extra_turn(self):
        """CombatManager.SwitchSides (extra turn): no enemy turn, RoundNumber kept, TurnNumber + 1."""
        player = self.combat_state.player
        # debuffs tick at the enemy side's turn end (WeakPower.AfterSideTurnEnd); Plating at its owner's turn start
        plating = player.status.get(StatusId.PLATING)
        if plating is not None:
            plating.amount -= 1
            if plating.amount <= 0:
                del player.status[StatusId.PLATING]
        self.combat_state.extra_turns += 1
        self._start_player_turn(enemies_start=False)

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
        keeps_hand = RelicId.RUNIC_PYRAMID in player.relics or StatusId.RETAIN_HAND in player.status or (
            RelicId.RINGING_TRIANGLE in player.relics and self.combat_state.player_turn <= 1)    # Hook.ShouldFlush
        if not keeps_hand:
            player.discard_pile.extend(c for c in player.hand if not c.retains)    # Ringing Triangle keeps the hand after the first turn
            player.hand[:] = [c for c in player.hand if c.retains]
        if exhausted:
            self.fire(EventType.ETHEREAL_EXHAUSTED, exhausted)

    def _start_player_turn(self, enemies_start : bool = True):
        player = self.combat_state.player
        if player.relics:
            self.combat_state.max_energy += max_energy_gain(player, self.combat_state.player_turn)
        if RelicId.ICE_CREAM in player.relics and self.combat_state.player_turn > 1:
            self.combat_state.energy += self.combat_state.max_energy        # Ice Cream: unspent energy is kept
        else:
            self.combat_state.energy = self.combat_state.max_energy
        self.combat_state.cards_played = 0
        self.fire(EventType.BEFORE_PLAYER_TURN)
        retained_block = player.block_kept_at_turn_start()
        hp_loss_mark = player.hp_loss_events
        self._announced_block = 0
        player.turn_start()
        # announce Crimson Mantle's block (already applied); gain_block block was announced already
        unannounced = player.block - retained_block - self._announced_block
        self._announced_block = None
        if unannounced > 0:
            self.fire(EventType.BLOCK_GAINED, player, unannounced)
        self._after_hp_loss(hp_loss_mark)
        self.fire(EventType.PLAYER_TURN_START)
        self._check_is_over()           # Mercury Hourglass can end the fight
        if not self.is_over:
            self.fire(EventType.AUTO_PRE_PLAY)
        if enemies_start:
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
            was_alive = self.combat_state.player.current_hp > 0
            waiting = list(self.combat_state.dormant)       # segments killed during this turn do their dead turn at the next one
            self.fire(EventType.ENEMY_TURN_START)
            self.resolve_deaths()
            eaten = was_alive and self.combat_state.player.current_hp <= 0      # Sandpit: the enemies do not get to act
            for enemy in ([] if eaten else list(self.combat_state.enemies)):     # enemies summoned now act next turn
                enemy.perform_turn(self)
                self.resolve_deaths()        # an attacker can die to Flame Barrier
                self._sync_hp()
            self.fire(EventType.ENEMY_TURN_END)
            self._reattach_segments(waiting)
        finally:
            self.in_enemy_turn = False
        self._revive()

    def _reattach_segments(self, waiting : list[Enemy]):
        """A dormant segment spends one enemy turn dead (DEAD_MOVE), and the next reattaching (REATTACH_MOVE: it heals by its Reattach amount
        and is back, with an attack chosen at random)."""
        cs = self.combat_state
        for segment in waiting:
            if segment not in cs.dormant:
                continue
            if segment.move_id == "DEAD":
                segment.move_id = "REATTACH"
                continue
            cs.dormant.remove(segment)
            segment.current_hp = min(segment.max_hp, segment.status[StatusId.REATTACH].amount)
            segment._finish_move(self)
            rank = SEGMENTS.index(segment.enemy_id.rpartition("_")[0])
            at = sum(1 for e in cs.enemies if e.enemy_id.rpartition("_")[0] in SEGMENTS and SEGMENTS.index(e.enemy_id.rpartition("_")[0]) < rank)
            cs.enemies.insert(at, segment)

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
            if self.combat_state.enemies:       # ReattachPower: while another segment lives a killed one only lies dead
                for enemy in dead:
                    if StatusId.REATTACH in enemy.status:
                        self.combat_state.dormant.append(Enemy.lie_dead(enemy))
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
        if RelicId.PHILOSOPHERS_STONE in self.combat_state.player.relics:
            enemy.apply_status(StatusId.STRENGTH, PHILOSOPHERS_STONE_STRENGTH)      # AfterCreatureAddedToCombat
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
        if not self.combat_state.won:
            self.combat_state.won = True
            if self.combat_state.player.relics:
                victory_heal(self.combat_state.player)      # final HP includes it

    ###
    ### Calculators
    ###

    def get_available_actions(self) -> list[dict]:
        output = []
        pending = self.combat_state.pending_choice
        if pending is not None:
            cards = self._pile(pending.pile)
            output = [{"action" : "choose_card", "card_index" : i, "pile" : pending.pile,
                       "card_id" : cards[i].card_id.name, "is_upgraded" : cards[i].is_upgraded}
                      for i in pending.indices]
            if pending.optional:
                output.append({"action" : "confirm_choice"})        # take what has been picked so far
            return output

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
        return max(0, int(block * multiplier + EPSILON))
