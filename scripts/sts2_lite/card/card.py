from __future__ import annotations
from typing import TYPE_CHECKING

import re
from sts2_lite.relic import before_card_played, blocks_play, extra_plays, free_by_relic, restore, snapshot, x_bonus
from sts2_lite.status import StatusId

from sts2_lite.card.constants import BECKON_HP_LOSS, BURN_DAMAGE, CONSUMED_ON_PLAY, CURSE_NAMES, ENCHANT_CORRUPTED_HP_LOSS, ENCHANT_SOWN_ENERGY, INFECTION_DAMAGE, NORMALITY_CARD_LIMIT, TOXIC_DAMAGE, UPGRADE_BASE_COST, UPGRADE_COST_CHANGE, UPGRADE_KEYWORD, UPGRADE_REMOVED_KEYWORD, WITHER_DAMAGE, _AXE, _CHOKER, _ETHEREAL, _EXHAUST, _INNATE, _REPLAY, _RETAIN, _SCARF, _UNPLAYABLE, _unknown_cards, _unknown_enchantments, keyword_mask
from sts2_lite.card.effects import _gain_block
from sts2_lite.card.ids import CardId, CardKeyword, CardType, EnchantmentId, TargetType
from sts2_lite.card.tables import ANCIENT_CARDS, COLORLESS_CARDS, EVENT_CARDS, GENERATABLE_CARDS, HAND_CURSE_EFFECTS, STRIKE_CARDS, TOKEN_CARDS

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator

class Card:
    card_id : CardId
    name : str
    type : CardType
    energy_cost : int | str
    target_type : TargetType
    is_upgraded : bool
    is_unplayable : bool
    guessed_cost : bool = False                # the cost was put back from the card tables while the Scarf showed 0: a previous state may know better
    restore_cost : int | str | None = None     # set while the cost is changed for this turn: the cost it gets back
    until_played : bool = False                # the temporary cost also ends when the card is played (SetThisTurnOrUntilPlayed)
    replay : int = 0                           # extra plays the card has for good (Hidden Gem); Glam's is the REPLAY keyword
    bonus_damage : int = 0                     # damage Rampage and Thrash have gained this combat
    shown_damage : int | None = None           # the damage printed on the card when it was loaded from the game
    enchantment : EnchantmentId | None = None  # at most one per card
    enchant_amount : int = 0                   # the enchantment's X (Sharp 2, Adroit 3, ...)
    enchant_bonus : int = 0                    # damage Momentum has added this combat
    dampened_from : Card | None = None         # Dampen: the upgraded card this one was downgraded from
    wither_level : int = 0                     # Aeonglass's Increasing Intensity: how often this Wither has been fake-upgraded
    bound : bool = False                       # the Queen's Chains of Binding: only one Bound card can be played a turn
    _keywords : int | None = None              # keyword mask; None: the card's canonical keywords
    generated : bool = False                   # made during this fight (the game's DeckVersion is null); the Thieving Hopper cannot take it

    def __init__(self):
        pass

    @property
    def _mask(self) -> int:
        return self._keywords if self._keywords is not None else self.card_id.keyword_mask

    @property
    def keywords(self) -> frozenset[CardKeyword]:
        mask = self._mask
        return frozenset(k for k in CardKeyword if mask & k.value)

    def with_keyword(self, keyword : CardKeyword) -> Card:
        """A copy with `keyword` added (CardCmd.ApplyKeyword); cards are shared between states, so never in place."""
        mask = self._mask
        if mask & keyword.value:
            return self
        new_card = Card.create_copy(self)
        new_card._keywords = mask | keyword.value
        return new_card

    def with_replay(self, extra : int) -> Card:
        """A copy that plays `extra` more times for good (BaseReplayCount)."""
        new_card = Card.create_copy(self)
        new_card.replay = self.replay + extra
        return new_card

    @property
    def has_glam_replay(self) -> bool:
        return bool(self._mask & _REPLAY)

    @property
    def exhausts(self) -> bool:
        return bool(self._mask & _EXHAUST) or self.enchantment == EnchantmentId.GOOPY

    @property
    def ethereal(self) -> bool:
        return bool(self._mask & _ETHEREAL)

    @property
    def unplayable(self) -> bool:
        return bool(self._mask & _UNPLAYABLE)

    @property
    def retains(self) -> bool:
        return bool(self._mask & _RETAIN)

    @classmethod
    def from_dict(cls, card : dict):
        if card["id"] not in CardId.__members__ or card["id"] == "NOT_IMPLEMENTED":
            if card["id"] not in _unknown_cards:
                _unknown_cards.add(card["id"])
                print(f"card {card['id']} is not implemented in the sim: treated as a Wound")
            placeholder = cls.create_not_implemented(card.get("name") or card["id"])
            placeholder.is_upgraded = bool(card.get("is_upgraded"))
            return placeholder
        new_card = cls()
        new_card.card_id = CardId[card["id"]]
        new_card.type = CardType[card["type"]]
        new_card.name = card["name"]
        # "EnergyCostTooHigh" is only the energy left right now: the simulator decides that itself, so the flag must not follow the card
        # into the discard pile (it made every card the player could not afford at the moment unplayable for the rest of a search)
        new_card.is_unplayable = not card["can_play"] and card.get("unplayable_reason") != "EnergyCostTooHigh"
        if card["cost"] == "X":
            new_card.energy_cost = card["cost"]
        else:
            new_card.energy_cost = int(card["cost"])
        new_card.is_upgraded = card["is_upgraded"]
        new_card.generated = bool(card.get("generated"))
        if card.get("card_keywords") is not None:       # CardModel.Keywords; older bridges only send hover tips
            new_card._keywords = keyword_mask(CardKeyword[k.upper()] for k in card["card_keywords"] if k.upper() in CardKeyword.__members__)
        if card.get("enchantment"):
            new_card._read_enchantment(card["enchantment"])
        new_card.bound = any(k.get("name") == "Bound" for k in card.get("keywords") or ())      # Chains of Binding shows as a keyword
        if new_card.bound and card.get("unplayable_reason") == "BlockedByHook":
            new_card.is_unplayable = False              # only because a Bound card was played this turn: the simulator knows that itself
        if new_card.card_id == CardId.STOMP and new_card.energy_cost < 3:
            new_card.restore_cost = 3           # the shown cost already includes this turn's Attacks
        match = re.search(r"Deals?\s+(\d+)", card.get("description") or "")
        new_card.shown_damage = int(match.group(1)) if match else None
        if new_card.card_id == CardId.WITHER:       # "Wither+2": the damage on it is 3 for every step
            damage = re.search(r"(\d+)\s+damage", card.get("description") or "")
            new_card.wither_level = max(0, int(damage.group(1)) // WITHER_DAMAGE - 1) if damage else 0
        replay = re.search(r"Replay (\d+)\.", card.get("description") or "")       # Hidden Gem (Glam prints "Replay 1." too, but it is the keyword)
        new_card.replay = int(replay.group(1)) if replay and new_card.card_id != CardId.HIDDEN_GEM and new_card.enchantment != EnchantmentId.GLAM else 0
        if new_card.enchantment == EnchantmentId.SPIRAL:
            new_card.replay = max(new_card.replay, 1)       # EnchantPlayCount: one more play (the bridge's text may already print "Replay 1.")
        if card["target_type"] == "None":
            new_card.target_type = TargetType.NONE
        else:
            new_card.target_type = TargetType[card["target_type"]]
        return new_card

    def _read_enchantment(self, raw : dict):
        """The enchantment the bridge reports, with the keywords it grants (they are not in the card's keyword list)."""
        enchantment = EnchantmentId.__members__.get(raw["id"])
        if enchantment is None:
            if raw["id"] not in _unknown_enchantments:
                _unknown_enchantments.add(raw["id"])
                print(f"unknown enchantment {raw['id']} on {self.name}: ignored")
            return
        self.enchantment, self.enchant_amount = enchantment, int(raw.get("amount") or 0)
        if enchantment == EnchantmentId.ROYALLY_APPROVED:
            self._keywords = self._mask | _INNATE | _RETAIN
        elif enchantment == EnchantmentId.GLAM:
            self._keywords = self._mask | _REPLAY
        elif enchantment == EnchantmentId.GOOPY:
            self._keywords = self._mask | CardKeyword.EXHAUST.value
        elif enchantment == EnchantmentId.SOULS_POWER:      # "This card loses Exhaust" (the bridge still lists the card's own keywords)
            self._keywords = self._mask & ~CardKeyword.EXHAUST.value

    @classmethod
    def create_slimed(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.SLIMED, "Slimed", CardType.Status
        c.energy_cost, c.target_type = 1, TargetType.NONE
        c.is_upgraded = c.is_unplayable = False
        return c

    @classmethod
    def create_beckon(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.BECKON, "Beckon", CardType.Status
        c.energy_cost, c.target_type = 1, TargetType.NONE
        c.is_upgraded = c.is_unplayable = False
        return c

    @classmethod
    def create_wither(cls, level : int = 0) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.WITHER, "Wither", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        c.wither_level = level
        return c

    def bound_copy(self, bound : bool = True) -> Card:
        c = Card.create_copy(self)
        c.bound = bound
        return c

    @classmethod
    def create_burn(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.BURN, "Burn", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_infection(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.INFECTION, "Infection", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_dazed(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.DAZED, "Dazed", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_wound(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.WOUND, "Wound", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_not_implemented(cls, name : str = "Not implemented") -> Card:
        """A card the sim does not know: a Wound, so that the agent neither plays it nor counts on it."""
        c = cls.create_wound()
        c.card_id, c.name = CardId.NOT_IMPLEMENTED, name
        return c

    @classmethod
    def create_soot(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.SOOT, "Soot", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_toxic(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.TOXIC, "Toxic", CardType.Status
        c.energy_cost, c.target_type = 1, TargetType.NONE
        c.is_upgraded = c.is_unplayable = False
        return c

    @classmethod
    def create_frantic_escape(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.FRANTIC_ESCAPE, "Frantic Escape", CardType.Status
        c.energy_cost, c.target_type = 1, TargetType.Self
        c.is_upgraded = c.is_unplayable = False
        return c

    @classmethod
    def create_knowledge_curse(cls, card_id : CardId) -> Card:
        """What Knowledge Demon offers: a pick, never played (the chosen one applies its power)."""
        c = cls()
        c.card_id, c.type = card_id, CardType.Status
        c.name = card_id.name.replace("_", " ").title()
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_curse(cls, card_id : CardId) -> Card:
        """A curse: cost 0 and unplayable, except Spore Mind (1 energy, Exhaust)."""
        c = cls()
        c.card_id, c.type = card_id, CardType.Curse
        c.name = CURSE_NAMES.get(card_id) or card_id.name.replace("_", " ").title()
        c.energy_cost, c.target_type = (1 if card_id == CardId.SPORE_MIND else 0), TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = card_id != CardId.SPORE_MIND
        return c

    @classmethod
    def create(cls, card_id : CardId) -> Card:
        """A fresh copy of a card that enemies add to the player's piles."""
        from sts2_lite.card.generated import GENERATED_CARDS      # the registries import Card, so they are loaded on use
        c = GENERATED_CARDS[card_id]()
        c.generated = True
        return c

    @classmethod
    def create_generated(cls, card_id : CardId, upgraded : bool = False) -> Card:
        """A fresh copy of a card that a card effect adds to the player's piles (Infernal Blade, Stoke)."""
        name, card_type, cost, target = (GENERATABLE_CARDS.get(card_id) or COLORLESS_CARDS.get(card_id) or EVENT_CARDS.get(card_id) or ANCIENT_CARDS.get(card_id)
                                         or TOKEN_CARDS[card_id])
        c = cls()
        c.card_id, c.name, c.type = card_id, name, card_type
        c.energy_cost, c.target_type = cost, target
        c.is_upgraded = c.is_unplayable = False
        c.generated = True
        return c.upgraded_copy() if upgraded else c

    def confused_copy(self, cost : int) -> Card:
        """ConfusedPower.AfterCardDrawn: SetThisCombat(cost), an Absolute modifier over every earlier one."""
        new_card = Card.create_copy(self)
        new_card.energy_cost, new_card.restore_cost, new_card.until_played = cost, None, False
        return new_card

    def cheaper_this_turn(self, amount : int) -> Card:
        """A copy that costs `amount` less until the end of the turn (Stomp)."""
        new_card = Card.create_copy(self)
        if new_card.restore_cost is None:
            new_card.restore_cost = self.energy_cost
        new_card.energy_cost = max(0, self.energy_cost - amount)
        return new_card

    def free_this_combat(self) -> Card:
        """CardModel.SetToFreeThisCombat: SetThisCombat(0). X costs ignore local modifiers (CardEnergyCost.GetWithModifiers)."""
        if self.energy_cost == "X":
            return self
        new_card = Card.create_copy(self)
        new_card.energy_cost, new_card.restore_cost, new_card.until_played = 0, None, False
        return new_card

    def free_this_turn(self) -> Card:
        """CardModel.SetToFreeThisTurn: SetThisTurnOrUntilPlayed(0)."""
        if self.energy_cost == "X":
            return self
        new_card = Card.create_copy(self)
        if new_card.restore_cost is None:
            new_card.restore_cost = self.energy_cost
        new_card.energy_cost, new_card.until_played = 0, True
        return new_card

    def reduced_to(self, cost : int, this_combat : bool) -> Card:
        """A reduce-only Absolute cost modifier (LocalCostModifier.IsReduceOnly): min(current, cost).
        this_combat: SetThisCombat (also caps the cost a this-turn change gives back); else SetThisTurnOrUntilPlayed."""
        if self.energy_cost == "X":
            return self
        restored = self.restore_cost if self.restore_cost is not None else self.energy_cost
        until = self.until_played
        if this_combat:
            new_restore = None if self.restore_cost is None else min(self.restore_cost, cost)
            new_cost = min(self.energy_cost, cost)
        else:
            new_cost = min(self.energy_cost, cost)
            new_restore = restored if new_cost != self.energy_cost or self.restore_cost is not None else None
            until = until or new_cost != self.energy_cost
        if new_cost == self.energy_cost and new_restore == self.restore_cost and until == self.until_played:
            return self
        new_card = Card.create_copy(self)
        new_card.energy_cost, new_card.restore_cost, new_card.until_played = new_cost, new_restore, until
        return new_card

    def cost_after_play(self) -> Card:
        """CardEnergyCost.AfterCardPlayedCleanup: until-played changes end once the play finishes. The sim keeps one
        temporary cost per card, so a Stomp discount stacked on it ends too (both would be gone by the next turn)."""
        if not self.until_played:
            return self
        new_card = Card.create_copy(self)
        new_card.energy_cost, new_card.restore_cost, new_card.until_played = self.restore_cost, None, False
        return new_card

    @property
    def is_strike(self) -> bool:
        return self.card_id in STRIKE_CARDS

    @property
    def is_upgradable(self) -> bool:
        return not self.is_upgraded and self.type != CardType.Status and self.type != CardType.Curse

    def downgraded_copy(self) -> Card:
        """Dampen: the plain version of an upgraded card (what upgraded_copy undid); shared piles stay untouched."""
        new_card = Card.create_copy(self)
        new_card.is_upgraded = False
        if new_card.name.endswith("+"):
            new_card.name = new_card.name[:-1]
        change = UPGRADE_COST_CHANGE.get(self.card_id, 0)
        if change and new_card.energy_cost != "X":
            new_card.energy_cost = max(0, self.energy_cost - change)
            if self.restore_cost is not None:
                new_card.restore_cost = max(0, self.restore_cost - change)
        keyword = UPGRADE_KEYWORD.get(self.card_id)
        if keyword:
            new_card._keywords = new_card._mask & ~keyword
        removed = UPGRADE_REMOVED_KEYWORD.get(self.card_id)
        if removed:
            new_card._keywords = new_card._mask | removed
        return new_card

    def upgraded_copy(self) -> Card:
        """A new, upgraded copy; the original is left alone because piles are shared between simulated states."""
        if not self.is_upgradable:
            raise ValueError(f"{self.name} cannot be upgraded")
        new_card = Card.create_copy(self)
        new_card.is_upgraded = True
        if not new_card.name.endswith("+"):
            new_card.name += "+"
        change = UPGRADE_COST_CHANGE.get(self.card_id, 0)
        if change and new_card.energy_cost != "X":
            # CardEnergyCost.UpgradeBy: base + change, Absolute modifiers (Confused) capped at it; this-turn offsets stay
            kept = self.restore_cost if self.restore_cost is not None else self.energy_cost
            upgraded = min(kept, UPGRADE_BASE_COST[self.card_id] + change)
            new_card.energy_cost = max(0, self.energy_cost - (kept - upgraded))
            if self.restore_cost is not None:
                new_card.restore_cost = upgraded
        keyword = UPGRADE_KEYWORD.get(self.card_id)
        if keyword:
            new_card._keywords = new_card._mask | keyword
        removed = UPGRADE_REMOVED_KEYWORD.get(self.card_id)
        if removed:
            new_card._keywords = new_card._mask & ~removed
        return new_card

    def on_turn_end_in_hand(self, combat : CombatSimulator):
        """End-of-turn effects of cards held in hand (before the Ethereal exhaust)."""
        card_id = self.card_id
        if card_id == CardId.INFECTION:
            combat.combat_state.player.apply_damage(INFECTION_DAMAGE)
        elif card_id == CardId.BURN:
            combat.combat_state.player.apply_damage(BURN_DAMAGE)
        elif card_id == CardId.BECKON:
            combat.combat_state.player.lose_hp(BECKON_HP_LOSS)        # Unblockable | Unpowered
        elif card_id == CardId.WITHER:
            combat.combat_state.player.apply_damage(WITHER_DAMAGE * (1 + self.wither_level))
        elif card_id == CardId.TOXIC:
            combat.combat_state.player.apply_damage(TOXIC_DAMAGE)
        elif card_id in HAND_CURSE_EFFECTS:
            HAND_CURSE_EFFECTS[card_id](combat.combat_state.player)

    @classmethod
    def create_copy(cls, card : Card) -> Card:
        new_card = cls()
        new_card.card_id = card.card_id
        new_card.type = card.type
        new_card.name = card.name
        new_card.energy_cost = card.energy_cost
        new_card.target_type = card.target_type
        new_card.is_upgraded = card.is_upgraded
        new_card.is_unplayable = card.is_unplayable
        new_card.restore_cost = card.restore_cost
        new_card.guessed_cost = card.guessed_cost
        new_card.until_played = card.until_played
        new_card.bonus_damage = card.bonus_damage
        new_card.replay = card.replay
        new_card.enchantment, new_card.enchant_amount, new_card.enchant_bonus = card.enchantment, card.enchant_amount, card.enchant_bonus
        new_card._keywords = card._keywords
        new_card.generated = card.generated
        new_card.dampened_from = card.dampened_from
        new_card.wither_level = card.wither_level
        new_card.bound = card.bound
        return new_card

    def signature(self) -> tuple:
        """Everything that decides how this card plays: two cards with equal signatures are interchangeable
        (the fields create_copy carries over, minus name/type/target which follow from the id)."""
        return (self.card_id, self.is_upgraded, self.energy_cost, self.is_unplayable, self.restore_cost, self.until_played,
                self.bonus_damage, self.replay, self.enchantment, self.enchant_amount, self.enchant_bonus, self._mask, self.generated, self.dampened_from is not None, self.wither_level, self.bound)

    def current_cost(self, player) -> int | str:
        """Energy cost now: the base cost plus Tangled on attacks."""
        if self.energy_cost == "X":
            return self.energy_cost
        if self.type == CardType.Skill and StatusId.CORRUPTION in player.status:
            return 0
        if self.type == CardType.Attack and StatusId.FREE_ATTACK in player.status and player.status[StatusId.FREE_ATTACK].amount > 0:
            return 0                # FreeAttackPower.TryModifyEnergyCostInCombatLate: the game shows these at 0
        cost = self.energy_cost if self.type != CardType.Attack else self.energy_cost + player.status_amount(StatusId.TANGLED)
        if player.relics and _SCARF in player.relics and free_by_relic(player):
            return 0                # Brilliant Scarf (TryModifyEnergyCostInCombatLate)
        return cost

    def play_card(self, combat : CombatSimulator, target_index : int, free : bool = False, x_value : int | None = None):
        """Play the card. Raises ValueError if it cannot be played; state is restored.
        A free play (auto-play) costs nothing but still consumes Free Attack (FreeAttackPower.BeforeCardPlayed)."""
        player = combat.combat_state.player
        if self.bound:
            player.bound_played = True      # BeforeCardPlayed
        energy = combat.combat_state.energy
        cost = 0 if free else self.current_cost(player)
        free_attack = player.status.get(StatusId.FREE_ATTACK)
        free_attack_amount = free_attack.amount if free_attack else 0
        from sts2_lite.card.plays.registry import GET_CARD_FUNCTION
        play = GET_CARD_FUNCTION[self.card_id]
        saved = snapshot(player) if player.relics else None
        punch = player.status.get(StatusId.ONE_TWO_PUNCH) if self.type == CardType.Attack else None
        x = None
        counted = self.type == CardType.Attack or self.type == CardType.Skill
        if counted:
            player.plays_started_this_turn += 1         # CardPlayStarted: Nostalgia counts these

        try:
            extra = self._extra_plays(player, punch)
            if self.energy_cost == "X":
                x = energy + x_bonus(player) if player.relics else energy        # Chemical X
                if x_value is not None:
                    x = x_value             # a dupe keeps the X of the card it copies
                combat.card_x = x
                spent = 0 if free else energy
                if saved:
                    before_card_played(combat, self, spent)
                if not free:
                    combat.combat_state.energy = 0
                play(self, combat, target_index, self.is_upgraded, x)
                self._enchantment_on_play(combat)
            else:
                spent = cost
                if self.type == CardType.Attack and free_attack_amount > 0:
                    free_attack.amount -= 1
                    combat.combat_state.energy += cost
                    spent = 0
                if saved:
                    before_card_played(combat, self, spent)
                combat.combat_state.energy -= cost
                play(self, combat, target_index, self.is_upgraded)
                self._enchantment_on_play(combat)
        except ValueError:
            combat.combat_state.energy = energy
            if self.bound:
                player.bound_played = False
            if counted:
                player.plays_started_this_turn -= 1
            if free_attack:
                free_attack.amount = free_attack_amount
            if saved:
                restore(player, saved)
            combat.vigor_pending = None
            if punch is not None:
                punch.amount += 1
                player.status[StatusId.ONE_TWO_PUNCH] = punch
            raise
        combat.finish_vigor()

        self.run_extra_plays(combat, target_index, x, extra, saved, spent)

    def run_extra_plays(self, combat : CombatSimulator, target_index : int, x, extra : int, saved, spent):
        """The further plays of one card. A play that asks for a card choice holds the rest back until it is answered (the game plays them in turn)."""
        cs = combat.combat_state
        for done in range(extra):
            if cs.pending_choice is not None:
                cs.continuations = cs.continuations + [("replay", self, target_index, x, extra - done, saved, spent)]
                return
            combat.card_played_hooks(self)          # AfterCardPlayed of the previous play
            if not any(e.current_hp > 0 for e in cs.enemies):
                break
            if saved:
                before_card_played(combat, self, spent)
            self._replay(combat, target_index, x)
            combat.finish_vigor()           # each play is its own attack command

    def _enchantment_on_play(self, combat : CombatSimulator):
        """EnchantmentModel.OnPlay: after the card's own effects, once for every play (replays included)."""
        enchantment = self.enchantment
        if enchantment is None:
            return
        player = combat.combat_state.player
        amount = self.enchant_amount
        if enchantment == EnchantmentId.ADROIT:
            _gain_block(combat, amount)
        elif enchantment == EnchantmentId.CORRUPTED:
            player.lose_hp(ENCHANT_CORRUPTED_HP_LOSS)
        elif enchantment == EnchantmentId.MOMENTUM:
            self.enchant_bonus += amount
        elif enchantment == EnchantmentId.GLAM:
            self._keywords = self._mask & ~_REPLAY          # Replay is spent
        elif enchantment == EnchantmentId.GOOPY:
            self.enchant_amount += 1                        # the amount is the card's permanent block gain + 1
        elif enchantment in CONSUMED_ON_PLAY and amount > 0:    # spent: the game keeps the enchantment with amount 0
            if enchantment == EnchantmentId.SWIFT:
                player.draw_cards(amount)
            elif enchantment == EnchantmentId.SOWN:
                combat.gain_energy(ENCHANT_SOWN_ENERGY)
            self.enchant_amount = 0

    def _extra_plays(self, player, punch) -> int:
        """CardModel.GeneratePlayCount: One-Two Punch (decremented), Throwing Axe. Before the first play."""
        extra = 0
        if punch is not None:
            extra += 1
            punch.amount -= 1
            if punch.amount <= 0:
                del player.status[StatusId.ONE_TWO_PUNCH]
        extra += self.replay
        if StatusId.DUPLICATION in player.status:        # Duplicator Potion: the next card this turn, once
            extra += 1
            del player.status[StatusId.DUPLICATION]
        if self._mask & _REPLAY:        # Replay 1 (Glam); it is spent after this play, but this count is fixed before it
            extra += 1
        if player.relics and _AXE in player.relics:
            extra += extra_plays(player)
        return extra

    def _replay(self, combat : CombatSimulator, target_index : int, x):
        """A further play (each fires Before/AfterCardPlayed); a dead target's effect is skipped."""
        if self.target_type == TargetType.AnyEnemy and combat.combat_state.enemies[target_index].current_hp <= 0:
            return
        if self.type == CardType.Attack or self.type == CardType.Skill:
            combat.combat_state.player.plays_started_this_turn += 1
        from sts2_lite.card.plays.registry import GET_CARD_FUNCTION
        if x is None:
            GET_CARD_FUNCTION[self.card_id](self, combat, target_index, self.is_upgraded)
        else:
            GET_CARD_FUNCTION[self.card_id](self, combat, target_index, self.is_upgraded, x)
        self._enchantment_on_play(combat)

    def can_play_card(self, combat : CombatSimulator, target_index):
        if self.is_unplayable or self.unplayable:
            return False
        if self.type == CardType.Skill and combat.combat_state.player.smogged:
            return False            # Smoggy: afflicted with Smog
        if self.bound and combat.combat_state.player.bound_played:
            return False            # Chains of Binding: one Bound card a turn
        if StatusId.RINGING in combat.combat_state.player.status and combat.combat_state.cards_played >= 1:
            return False
        sloth = combat.combat_state.player.status.get(StatusId.SLOTH)
        if sloth is not None and combat.combat_state.cards_played >= sloth.amount:
            return False            # Sloth: at most this many cards a turn
        if combat.combat_state.cards_played >= NORMALITY_CARD_LIMIT and any(c.card_id == CardId.NORMALITY for c in combat.combat_state.player.hand):
            return False            # Normality: at most 3 cards a turn while it is in hand
        if combat.combat_state.player.relics and _CHOKER in combat.combat_state.player.relics and blocks_play(combat.combat_state.player):
            return False            # Velvet Choker
        if type(self.energy_cost) is str and self.energy_cost == "X":
            return True
        if self.type == CardType.Attack and StatusId.FREE_ATTACK in combat.combat_state.player.status:
            if combat.combat_state.player.status[StatusId.FREE_ATTACK].amount > 0:
                return True
        if self.current_cost(combat.combat_state.player) <= combat.combat_state.energy:
            return True
        return False
