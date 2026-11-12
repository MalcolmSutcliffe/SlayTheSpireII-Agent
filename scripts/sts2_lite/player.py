from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import Player

from sts2_lite import rng
from sts2_lite.creature import Creature
from sts2_lite.card import Card, CardId, CardType, CardKeyword, CONFUSED_MAX_COST, EnchantmentId, SLITHER_MAX_COST, PLAIN_DAMAGE, GENERATABLE_CARDS

BASIC_ATTACK_COSTS = {CardId.STRIKE_IRONCLAD: 1, CardId.BASH: 2}      # the starter Attacks are not in the generated-card table
from sts2_lite.status import StatusInstance, StatusId, INSTANCED
from sts2_lite.relic import RelicId, RelicInstance, strength_received, lizard_tail_revive, hand_draw_bonus, blocks_draw
from sts2_lite.potion import Potion, PotionId, DEFAULT_POTION_SLOTS, FAIRY_HEAL

GHOST_SEED_CARDS = frozenset({CardId.STRIKE_IRONCLAD, CardId.DEFEND_IRONCLAD})     # Basic rarity, Strike or Defend tag

class Player(Creature):
    plating_at_turn_start = False
    hand : list[Card]
    draw_pile : list[Card]
    discard_pile : list[Card]
    exhaust_pile : list[Card]
    relics : dict[RelicId, RelicInstance]      # relics with an effect in combat
    cards_drawn : int       # running total of cards drawn
    unknown_draws : int     # running total of draws and top-card plays the agent could not foresee; compare before and after an action
    inferno_plays : int      # times Inferno has been played this combat: its HP loss each turn
    shuffle_hook = None      # called when the discard pile is shuffled into the draw pile (set by the simulator)
    draw_hook = None         # called with each card drawn into the hand (set by the simulator for Hellraiser)
    block_cleared_hook = None    # called after block is cleared, before the hand draw (AfterBlockCleared)
    known_top : int         # how many cards at the end of draw_pile (the top) the agent knows the identity and order of
    cards_exhausted_this_turn : int
    gold : int              # Player.Gold; spent in combat by Seal of Gold
    potions : list[Potion]  # the potions held, each with the slot the game keeps it in
    potion_slots : int      # how many the player can carry (Entropic Brew fills the free ones)
    extra_turn_pending : bool       # Ambergris: an extra turn is taken when this one ends

    def __init__(self):
        super().__init__()
        self.hand = []
        self.draw_pile = []
        self.discard_pile = []
        self.exhaust_pile = []
        self.relics = {}
        self.cards_drawn = 0
        self.unknown_draws = 0
        self.known_top = 0
        self.inferno_plays = 0
        self.cards_played_total = 0     # finished plays this combat (Gold Axe)
        self.crimson_mantle_plays = 0   # Crimson Mantle self-damage per turn
        self.attacks_played_this_turn = 0
        self.plays_started_this_turn = 0  # Attack and Skill plays begun this turn, replays and auto-plays included (Nostalgia)
        self.returning = []               # (card id, upgraded) of the Bolas and Thrumming Hatchets played this turn: back in the hand next turn
        self.card_blocks_this_turn = 0    # block gains from cards, for Unmovable
        self.block_play = None            # play_id of the latest card block gain
        self.block_play_gains = 0         # gains made by that play
        self.cards_exhausted_this_turn = 0
        self.gold = 0
        self.potions = []
        self.potion_slots = DEFAULT_POTION_SLOTS
        self.extra_turn_pending = False
        self.binding = False            # Chains of Binding is binding the cards drawn (the player's turn)
        self.bound_cards = 0            # cards bound so far this turn
        self.bound_played = False       # a Bound card has been played this turn: no other can be
        self.smogged = False            # Smoggy: a Skill was played this turn, so every Skill card is afflicted with Smog until it ends

    @classmethod
    def from_dict(cls, player : dict):
        pl = cls()
        pl.max_hp = player["max_hp"]
        pl.current_hp = player["hp"]
        pl.block = player["block"]
        pl.gold = player.get("gold", 0)
        pl.potions = [Potion(potion_id, p.get("slot", i)) for i, p in enumerate(player.get("potions") or [])
                      if (potion_id := PotionId.from_game_id(p.get("id"))) is not None]
        pl.potion_slots = max(player.get("potion_slots", DEFAULT_POTION_SLOTS), 1 + max((p.slot for p in pl.potions), default=-1))
        pl.is_minion = False
        pl.status = {}
        for s in player["status"]:
            inst = StatusInstance.from_dict(s)
            kept = pl.status.get(inst.status_id)
            if kept is not None and inst.status_id in INSTANCED:        # one entry per copy
                kept.merge(inst)
            else:
                pl.status[inst.status_id] = inst
        pl.hand = []
        for card in player["hand"]:
            pl.hand.append(Card.from_dict(card))
        pl.draw_pile = []
        for card in player["draw_pile"]:
            pl.draw_pile.append(Card.from_dict(card))
        pl.discard_pile = []
        for card in player["discard_pile"]:
            pl.discard_pile.append(Card.from_dict(card))
        pl.exhaust_pile = [Card.from_dict(card) for card in player.get("exhaust_pile", [])]
        for relic in map(RelicInstance.from_dict, player.get("relics", [])):
            if relic is not None:
                pl.relics[relic.relic_id] = relic
        if RelicId.GHOST_SEED in pl.relics:
            pl._apply_ghost_seed()
        if StatusId.CONFUSED in pl.status:
            pl._read_confused_stomps()
        pl.inferno_plays = max(1, round(pl.status_amount(StatusId.INFERNO) / 7.5)) if StatusId.INFERNO in pl.status else 0
        # copies inferred from block amount (8 or 10 each)
        pl.crimson_mantle_plays = max(1, round(pl.status_amount(StatusId.CRIMSON_MANTLE) / 9)) if StatusId.CRIMSON_MANTLE in pl.status else 0
        pl._read_growing_cards()
        if StatusId.CHAINS_OF_BINDING in pl.status:         # mid-turn: the cards bound so far are the ones in hand, and the one already played
            pl.binding = True
            pl.bound_played = any(c.bound and c.card_id is not None and raw.get("unplayable_reason") == "BlockedByHook" for c, raw in zip(pl.hand, player["hand"]))
            pl.bound_cards = sum(c.bound for c in pl.hand) + (1 if pl.bound_played else 0)
        if StatusId.SMOGGY in pl.status:         # a Skill in hand that the hook blocks: one was played this turn
            smogged = [c for c, raw in zip(pl.hand, player["hand"])
                       if c.type == CardType.Skill and not c.bound and raw.get("unplayable_reason") == "BlockedByHook"]
            pl.smogged = bool(smogged)
            for c in smogged:
                c.is_unplayable = False         # only the Smog: the simulator knows that itself
        if StatusId.FREE_ATTACK in pl.status:
            pl._read_free_attack_costs()
        return pl

    def _read_confused_stomps(self):
        """A shown Stomp cost under Confused is the roll (minus Attacks played since the draw), not 3 minus Attacks."""
        for card in self.hand + self.draw_pile + self.discard_pile + self.exhaust_pile:
            if card.card_id == CardId.STOMP:
                card.restore_cost = None

    def _apply_ghost_seed(self):
        """GhostSeed.CanAffect: basic Strikes and Defends are Ethereal (idempotent if the bridge already sent it)."""
        for pile in (self.hand, self.draw_pile, self.discard_pile, self.exhaust_pile):
            for i, c in enumerate(pile):
                if c.card_id in GHOST_SEED_CARDS:
                    pile[i] = c.with_keyword(CardKeyword.ETHEREAL)

    def _read_free_attack_costs(self):
        """Free Attack makes the game show every Attack in the hand at 0 (TryModifyEnergyCostInCombatLate), so the shown
        cost is not the card's own: take that from the card tables. current_cost applies the 0 while the power lasts."""
        for i, card in enumerate(self.hand):
            if card.type != CardType.Attack or card.energy_cost != 0:
                continue
            base = BASIC_ATTACK_COSTS.get(card.card_id)
            if base is None and card.card_id in GENERATABLE_CARDS:
                base = Card.create_generated(card.card_id, card.is_upgraded).energy_cost
            if base is not None and base != 0:
                own = Card.create_copy(card)
                own.energy_cost = base
                self.hand[i] = own

    def _read_growing_cards(self):
        """Rampage and Thrash remember the damage they gained, which the bridge only shows in the card text.
        Cards in the hand print their damage with Strength and Weak included, so that is taken back out."""
        from sts2_lite.damage import base_from_displayed
        for pile in (self.hand, self.draw_pile, self.discard_pile, self.exhaust_pile):
            for card in pile:
                if card.card_id == CardId.GOLD_AXE and card.shown_damage is not None:     # prints one damage per play so far
                    shown = card.shown_damage
                    self.cards_played_total = max(self.cards_played_total, base_from_displayed(shown, self, Creature()) if pile is self.hand else shown)
                    continue
                momentum = card.enchantment == EnchantmentId.MOMENTUM and card.card_id in PLAIN_DAMAGE
                if card.shown_damage is None or not (momentum or card.card_id in (CardId.RAMPAGE, CardId.THRASH, CardId.MAUL)):
                    continue
                shown = card.shown_damage
                if pile is self.hand:
                    shown = base_from_displayed(shown, self, Creature())
                if momentum:     # the text carries the accumulated bonus; the enchantment's X is only the per-play step
                    card.enchant_bonus = max(0, shown - PLAIN_DAMAGE[card.card_id][card.is_upgraded])
                elif card.card_id == CardId.RAMPAGE:
                    step = 9 if card.is_upgraded else 5
                    card.bonus_damage = max(0, round((shown - 9) / step)) * step
                elif card.card_id == CardId.MAUL:
                    card.bonus_damage = max(0, shown - (6 if card.is_upgraded else 5))
                else:
                    card.bonus_damage = max(0, shown - (6 if card.is_upgraded else 4))

    def remove_displayed_tangled(self):
        """The bridge shows attack costs with Tangled included; keep base costs."""
        tangled = self.status_amount(StatusId.TANGLED)
        if tangled == 0:
            return
        for card in self.hand + self.draw_pile + self.discard_pile + self.exhaust_pile:
            if card.type == CardType.Attack and card.energy_cost != "X":
                card.energy_cost = max(0, card.energy_cost - tangled)

    @classmethod
    def deepcopy(cls, player : Player) -> Player:
        new_pl = cls()
        new_pl.max_hp = player.max_hp
        new_pl.current_hp = player.current_hp
        new_pl.block = player.block
        new_pl.is_minion = False
        new_pl.status = {}
        for s in player.status.values():
            new_pl.status[s.status_id] = StatusInstance.deepcopy(s)
        new_pl.hand = []
        for card in player.hand:
            new_pl.hand.append(card)
        new_pl.draw_pile = []
        for card in player.draw_pile:
            new_pl.draw_pile.append(card)
        new_pl.discard_pile = []
        for card in player.discard_pile:
            new_pl.discard_pile.append(card)
        new_pl.exhaust_pile = list(player.exhaust_pile)
        new_pl.potions = list(player.potions)           # a Potion never changes
        new_pl.potion_slots = player.potion_slots
        new_pl.extra_turn_pending = player.extra_turn_pending
        new_pl.relics = {relic_id: RelicInstance.deepcopy(relic) for relic_id, relic in player.relics.items()}
        new_pl.cards_drawn = player.cards_drawn
        new_pl.unknown_draws = player.unknown_draws
        new_pl.known_top = player.known_top
        new_pl.inferno_plays = player.inferno_plays
        new_pl.cards_played_total = player.cards_played_total
        new_pl.crimson_mantle_plays = player.crimson_mantle_plays
        new_pl.block_play = player.block_play
        new_pl.block_play_gains = player.block_play_gains
        new_pl.cards_exhausted_this_turn = player.cards_exhausted_this_turn
        new_pl.lost_hp_this_turn = player.lost_hp_this_turn
        new_pl.has_been_attacked_this_turn = player.has_been_attacked_this_turn
        new_pl.hp_loss_events = player.hp_loss_events
        new_pl.hp_lost_log = list(player.hp_lost_log)
        new_pl.attacks_played_this_turn = player.attacks_played_this_turn
        new_pl.plays_started_this_turn = player.plays_started_this_turn
        new_pl.returning = list(player.returning)
        new_pl.card_blocks_this_turn = player.card_blocks_this_turn
        new_pl.gold = player.gold
        new_pl.binding, new_pl.bound_cards, new_pl.bound_played = player.binding, player.bound_cards, player.bound_played
        new_pl.smogged = player.smogged
        return new_pl
    
    def clear_bound(self):
        """ChainsOfBindingPower.BeforeSideTurnEnd: the affliction goes wherever the cards are."""
        self.binding, self.bound_cards, self.bound_played = False, 0, False
        for pile in (self.hand, self.draw_pile, self.discard_pile):
            for i, c in enumerate(pile):
                if c.bound:
                    pile[i] = c.bound_copy(False)

    def turn_start(self):
        self.bound_cards, self.bound_played = 0, False
        self.binding = StatusId.CHAINS_OF_BINDING in self.status
        remnant = self.relics.get(RelicId.BEATING_REMNANT)
        if remnant is not None:
            remnant.value = 0       # its damage limit counts from here
        super().turn_start()
        self.cards_exhausted_this_turn = 0
        self.attacks_played_this_turn = 0
        self.plays_started_this_turn = 0
        self.card_blocks_this_turn = 0
        self.block_play, self.block_play_gains = None, 0
        if self.block_cleared_hook is not None:
            self.block_cleared_hook()
        if self.returning:
            self.return_played_cards()
        extra_draw = self.status.pop(StatusId.DRAW_CARDS_NEXT_TURN, None)       # Relax: part of the hand draw
        clarity = self.status.get(StatusId.CLARITY_EXTRACT)     # Clarity Extract: 1 more card for a few turns
        if clarity is not None:
            clarity.amount -= 1
            if clarity.amount <= 0:
                del self.status[StatusId.CLARITY_EXTRACT]
        self.draw_cards(max(0, (5 + hand_draw_bonus(self) if self.relics else 5) + (extra_draw.amount if extra_draw else 0) + (1 if clarity else 0) - self.status_amount(StatusId.MIND_ROT)), from_hand_draw=True)

        if StatusId.CRIMSON_MANTLE in self.status:
            self.lose_hp(max(1, self.crimson_mantle_plays))
            self.apply_block(self.status[StatusId.CRIMSON_MANTLE].amount)
    
    def return_played_cards(self):
        """Bolas and Thrumming Hatchet (BeforeHandDraw): the ones played last turn go to the hand from wherever they are."""
        returning, self.returning = self.returning, []
        for card_id, upgraded in returning:
            for pile in (self.discard_pile, self.exhaust_pile, self.draw_pile):
                card = next((c for c in pile if c.card_id == card_id and c.is_upgraded == upgraded), None)
                if card is not None:
                    break
            else:
                continue            # already in the hand
            if len(self.hand) >= 10:
                continue
            if pile is self.draw_pile:
                self.remove_from_draw_pile(card)
            else:
                pile.remove(card)
            self.hand.append(card)

    def add_instance(self, status : StatusId, record : list[int]):
        """Apply an instanced power: every play is a separate copy with its own state."""
        inst = self.status.get(status)
        if inst is None:
            self.status[status] = StatusInstance(status, record[0], [record])
        else:
            inst.records.append(record)
            inst.sync()

    def apply_status(self, status : StatusId, amount : int, bypass_artifact : bool = False):
        if status is StatusId.STRENGTH and amount > 0 and self.relics:
            amount = strength_received(self, amount)
        super().apply_status(status, amount, bypass_artifact)

    def die(self):
        if self.potions and self._fairy_revive():
            return
        if self.relics and lizard_tail_revive(self):
            return
        super().die()

    def _fairy_revive(self) -> bool:
        """Fairy in a Bottle: instead of dying the potion is used up and the player is healed to 30% of Max HP (assumed to come before Lizard Tail)."""
        fairy = next((p for p in self.potions if p.potion_id == PotionId.FAIRY_IN_A_BOTTLE), None)
        if fairy is None:
            return False
        self.potions.remove(fairy)
        self.current_hp = max(1, int(self.max_hp * FAIRY_HEAL))
        return True

    def draw_cards(self, num_cards : int, from_hand_draw : bool = False):
        for i in range(num_cards):
            self.draw_card(from_hand_draw)

    def draw_card(self, from_hand_draw : bool = False) -> Card | None:
        """Draw one card and return it (None if nothing was drawn). Battle Trance and Fiddle stop every draw except the start-of-turn hand."""
        if not from_hand_draw and (StatusId.NO_DRAW in self.status or (self.relics and blocks_draw(self))):
            return None
        if len(self.hand) >= 10:
            return None
        if len(self.draw_pile) == 0:
            self.shuffle_discard_into_draw()
        if len(self.draw_pile) == 0:
            return None
        card = self.draw_pile.pop()
        if card.enchantment == EnchantmentId.SLITHER and card.energy_cost != "X" and not card.unplayable:
            card = card.confused_copy(rng.randrange(SLITHER_MAX_COST + 1))     # a new random cost each time it is drawn
        if StatusId.CONFUSED in self.status and card.energy_cost != "X" and not card.unplayable:
            card = card.confused_copy(rng.randrange(CONFUSED_MAX_COST + 1))    # Canonical < 0 (Unplayable) and X keep theirs
        chains = self.status.get(StatusId.CHAINS_OF_BINDING) if self.binding else None
        if chains is not None and self.bound_cards < chains.amount and not card.bound:
            card = card.bound_copy()        # ChainsOfBindingPower.AfterCardDrawn: the first few cards drawn each turn
            self.bound_cards += 1
        self.hand.append(card)
        self.cards_drawn += 1
        if self.known_top > 0:
            self.known_top -= 1
        else:
            self.unknown_draws += 1
        if self.draw_hook is not None:
            self.draw_hook(card)
        return card

    def shuffle_draw_pile(self):
        """Shuffle the draw pile, leaving the known cards on top where they are."""
        if self.known_top <= 0:
            rng.shuffle(self.draw_pile)
            return
        split = max(0, len(self.draw_pile) - self.known_top)
        rest = self.draw_pile[:split]
        rng.shuffle(rest)
        self.draw_pile[:split] = rest

    def take_top(self) -> Card | None:
        """Remove and return the top card of the draw pile (reshuffling an empty pile first) without
        putting it in the hand. Counts as an unforeseen draw unless the agent knew the card."""
        if not self.draw_pile:
            self.shuffle_discard_into_draw()
        if not self.draw_pile:
            return None
        card = self.draw_pile.pop()
        if self.known_top > 0:
            self.known_top -= 1
        else:
            self.unknown_draws += 1
        return card

    def add_to_hand(self, card : Card):
        """A card created mid-fight goes to the hand, or to the discard pile if the hand is full."""
        if card.card_id == CardId.STOMP and self.attacks_played_this_turn:
            card = card.cheaper_this_turn(self.attacks_played_this_turn)
        if len(self.hand) < 10:
            self.hand.append(card)
        else:
            self.discard_pile.append(card)

    def reduce_stomp_costs(self):
        """Every Stomp, wherever it is, costs 1 less this turn each time an Attack is played."""
        for pile in (self.hand, self.draw_pile, self.discard_pile, self.exhaust_pile):
            for i, c in enumerate(pile):
                if c.card_id == CardId.STOMP and c.energy_cost != 0:
                    pile[i] = c.cheaper_this_turn(1)

    def restore_free_cards(self):
        """At the end of the turn cards made free for this turn (Infernal Blade) get their cost back."""
        for pile in (self.hand, self.draw_pile, self.discard_pile, self.exhaust_pile):
            for i, c in enumerate(pile):
                if c.restore_cost is not None:
                    restored = Card.create_copy(c)
                    restored.energy_cost, restored.restore_cost, restored.until_played = c.restore_cost, None, False
                    pile[i] = restored

    def put_on_top(self, card : Card):
        """Place a card on top of the draw pile; the agent knows what it is."""
        self.draw_pile.append(card)
        self.known_top += 1

    def insert_into_draw_pile(self, card : Card):
        """CardPilePosition.Random: any of the len+1 places. Known top cards below the new card are no longer known
        (their distance from the top is uncertain); those above it still are."""
        index = rng.randrange(len(self.draw_pile) + 1)
        if index >= len(self.draw_pile) - self.known_top:
            self.known_top = len(self.draw_pile) - index
        self.draw_pile.insert(index, card)

    def remove_from_draw_pile(self, card : Card):
        """Remove a card from the draw pile, forgetting a known top card if it was one."""
        index = next((i for i, c in enumerate(self.draw_pile) if c is card), None)
        if index is None:
            index = self.draw_pile.index(card)
        if index >= len(self.draw_pile) - self.known_top:
            self.known_top -= 1
        del self.draw_pile[index]

    def shuffle_discard_into_draw(self):
        if not self.discard_pile:
            return
        self.draw_pile.extend(self.discard_pile)
        self.discard_pile = []
        self.known_top = 0
        self.shuffle_draw_pile()
        fitted = [c for c in self.draw_pile if c.enchantment == EnchantmentId.PERFECT_FIT]
        if fitted:      # Perfect Fit: placed on top instead of being shuffled, and the agent knows them
            self.draw_pile = [c for c in self.draw_pile if c.enchantment != EnchantmentId.PERFECT_FIT] + fitted
            self.known_top = len(fitted)
        if self.shuffle_hook is not None:
            self.shuffle_hook()

    def upgrade_card(self, card : Card) -> Card | None:
        """Replace a card in the hand or a pile with its upgraded version. Returns it, or None if the card
        cannot be upgraded or is in none of the piles."""
        if not card.is_upgradable:
            return None
        for pile in (self.hand, self.draw_pile, self.discard_pile, self.exhaust_pile):
            for i, c in enumerate(pile):
                if c is card:
                    pile[i] = card.upgraded_copy()
                    return pile[i]
        return None

    def exhaust_card(self, card :Card):
        # the card being played is in none of the piles
        if card in self.hand:
            self.hand.remove(card)
        elif card in self.draw_pile:
            self.remove_from_draw_pile(card)
        elif card in self.discard_pile:
            self.discard_pile.remove(card)
        self.exhaust_pile.append(card)
        self.cards_exhausted_this_turn += 1

    def readable(self) -> str:
        output = ""
        output += super().readable()
        output += "\nHand : \n"
        for card in self.hand:
            output += str(card.card_id) + "\n"
        # output += "Draw : \n"
        # for card in self.draw_pile:
        #     output += str(card.card_id) + "\n"
        # output += "Discard : \n"
        # for card in self.discard_pile:
        #     output += str(card.card_id) + "\n"
        return output