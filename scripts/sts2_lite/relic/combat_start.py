"""Relics that act when a fight starts (room entry) or on its first turn, for a fight built from a deck (agents.deck_eval.fight_builder).

A live bridge state already contains these effects, so none of this is registered as a RelicId (it would count twice).
Order follows CombatManager: room entry -> BeforeSideTurnStart -> energy reset -> BeforeHandDraw -> innate cards to the top ->
hand draw -> AfterPlayerTurnStart -> AfterSideTurnStart. Choice relics (Toolbox, Choices Paradox, Gambling Chip), map relics (Fur Coat,
Delicate Frond), Venerable Tea Set and the Poison/Soul relics (Twisted Funnel, Funerary Mask) are not modelled.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.card import Card
from sts2_lite.card.ids import CardKeyword, CardType
from sts2_lite.helpers import living_enemies
from sts2_lite.relic.card_hooks import _hurt_all
from sts2_lite.relic.ids import RelicId
from sts2_lite.relic.turn_hooks import BRIMSTONE_ENEMY, MERCURY_HOURGLASS_DAMAGE, _red_skull
from sts2_lite.status import StatusId

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator, CombatState

MAX_HAND = 10
ENERGY_RELICS = frozenset({"ECTOPLASM", "SOZU", "PHILOSOPHERS_STONE", "BLESSED_ANTLER", "PRISMATIC_GEM", "WHISPERING_EARRING", "BLOOD_SOAKED_ROSE", "VELVET_CHOKER", "SPIKED_GAUNTLETS"})
COUNTER_RELICS = frozenset({"EMBER_TEA", "BONE_TEA", "TEA_OF_DISCOURTESY", "PUMPKIN_CANDLE"})     # act only while their counter is above 0

PLAYER_STATUS = {"VAJRA": (StatusId.STRENGTH, 1), "SWORD_OF_JADE": (StatusId.STRENGTH, 3), "ODDLY_SMOOTH_STONE": (StatusId.DEXTERITY, 1),
                 "AKABEKO": (StatusId.VIGOR, 8), "GORGET": (StatusId.PLATING, 4), "BRONZE_SCALES": (StatusId.THORNS, 3)}
ENEMY_STATUS_TURN_1 = {"BAG_OF_MARBLES": (StatusId.VULNERABLE, 1), "RED_MASK": (StatusId.WEAK, 1)}
BLOCK = {"ANCHOR": 10, "FAKE_ANCHOR": 4}
HEAL = {"BLOOD_VIAL": 2, "FAKE_BLOOD_VIAL": 1}
DRAW_BONUS = {"BAG_OF_PREPARATION": 2, "RING_OF_THE_SNAKE": 2, "BIG_MUSHROOM": -2}
SLING_STRENGTH, EMBER_TEA_STRENGTH = 2, 2
CONCH_DRAW, CONCH_ENERGY, COCOA_ENERGY, LANTERN_ENERGY, BREAD_ENERGY_LOSS = 2, 1, 4, 1, 2
PANTOGRAPH_HEAL, POPPER_DAMAGE, ROYAL_POISON_DAMAGE = 25, 9, 4
ANTLER_DAZED, TEA_DAZED = 3, 2
STONE_CRACKER_CARDS, POWER_CELL_CARDS, ORANGE_DOUGH_CARDS, BIG_HAT_CARDS = 2, 2, 2, 2


class Opening:
    """The relics that matter at the start of one fight: `relics` is the raw relic list of the state (id, counter, status)."""
    def __init__(self, relics : list[dict], room_type : str, is_boss : bool = False):
        self.active : dict[str, dict] = {}
        for r in relics:
            if r.get("status") == "Disabled" or (r["id"] in COUNTER_RELICS and r.get("counter") is not None and r["counter"] <= 0):
                continue
            self.active[r["id"]] = r
        self.elite = room_type == "elite"
        self.boss = is_boss or room_type == "boss"

    def has(self, relic : str) -> bool:
        return relic in self.active

    def energy_bonus(self) -> int:
        return sum(1 for r in ENERGY_RELICS if r in self.active)

    def draw_delta(self) -> int:
        delta = sum(v for r, v in DRAW_BONUS.items() if r in self.active)
        return delta + (CONCH_DRAW if self.elite and "BOOMING_CONCH" in self.active else 0)

    # --- room entry (BeforeCombatStart / AfterRoomEntered)
    def before_combat(self, cs : CombatState):
        player = cs.player
        if self.has("STONE_CRACKER"):
            candidates = [i for i, c in enumerate(player.draw_pile) if c.is_upgradable]
            for i in rng.sample(candidates, min(STONE_CRACKER_CARDS, len(candidates))):
                player.draw_pile[i] = player.draw_pile[i].upgraded_copy()
        if self.boss and self.has("PANTOGRAPH"):
            player.current_hp = min(player.max_hp, player.current_hp + PANTOGRAPH_HEAL)
        for relic, (status, amount) in PLAYER_STATUS.items():
            if self.has(relic):
                player.apply_status(status, amount)
        if self.has("SLING_OF_COURAGE") and self.elite:
            player.apply_status(StatusId.STRENGTH, SLING_STRENGTH)
        if self.has("EMBER_TEA"):
            player.apply_status(StatusId.STRENGTH, EMBER_TEA_STRENGTH)
        if self.has("GIRYA") and (self.active["GIRYA"].get("counter") or 0) > 0:
            player.apply_status(StatusId.STRENGTH, self.active["GIRYA"]["counter"])
        if self.has("PHILOSOPHERS_STONE"):
            for enemy in cs.enemies:
                enemy.apply_status(StatusId.STRENGTH, 1)

    # --- BeforeSideTurnStart (turn 1) and BeforeHandDraw: called by Player.turn_start with the number of cards it is about to draw
    def before_draw(self, player, count : int) -> int:
        if self.has("POWER_CELL"):
            free = [c for c in player.draw_pile if c.energy_cost == 0 and not c.unplayable]
            for card in rng.sample(free, min(POWER_CELL_CARDS, len(free))):
                player.remove_from_draw_pile(card)
                player.add_to_hand(card)
        antler = ANTLER_DAZED if self.has("BLESSED_ANTLER") else 0
        tea = TEA_DAZED if self.has("TEA_OF_DISCOURTESY") else 0
        for _ in range(antler + tea):
            player.insert_into_draw_pile(Card.create_dazed())
        if self.has("JEWELED_MASK"):
            powers = [c for c in player.draw_pile if c.type == CardType.Power]
            if powers:
                card = rng.choice(powers)
                player.remove_from_draw_pile(card)
                player.add_to_hand(card.free_this_turn())
        innate = [c for c in player.draw_pile if CardKeyword.INNATE in c.keywords]
        if innate:
            rest = [c for c in player.draw_pile if CardKeyword.INNATE not in c.keywords]
            player.draw_pile[:] = rest + innate        # the top of the pile is the end of the list
            player.known_top = 0
        return min(max(count + self.draw_delta(), len(innate)), MAX_HAND)

    # --- before the turn: enemies
    def before_turn(self, cs : CombatState):
        for relic, (status, amount) in ENEMY_STATUS_TURN_1.items():
            if self.has(relic):
                for enemy in cs.enemies:
                    enemy.apply_status(status, amount)

    # --- after the hand draw (AfterPlayerTurnStart, AfterSideTurnStart)
    def after_draw(self, sim : CombatSimulator):
        cs = sim.combat_state
        player = cs.player
        for relic, amount in BLOCK.items():
            if self.has(relic):
                player.apply_block(amount)
        for relic, amount in HEAL.items():
            if self.has(relic):
                player.current_hp = min(player.max_hp, player.current_hp + amount)
        if self.has("FESTIVE_POPPER"):
            _hurt_all(sim, POPPER_DAMAGE)
        if self.has("ROYAL_POISON"):
            mark = player.hp_loss_events
            player.lose_hp(ROYAL_POISON_DAMAGE)
            sim._after_hp_loss(mark)
        upgrades = self.has("BELLOWS") or self.has("BONE_TEA")
        if upgrades:
            player.hand[:] = [c.upgraded_copy() if c.is_upgradable else c for c in player.hand]
        if self.has("VEXING_PUZZLEBOX"):
            player.add_to_hand(_class_card().free_this_turn())
        if self.has("ORANGE_DOUGH"):
            for _ in range(ORANGE_DOUGH_CARDS):
                player.add_to_hand(_colorless_card())
        if self.has("BIG_HAT"):
            for _ in range(BIG_HAT_CARDS):
                card = _ethereal_class_card()
                if card is None:
                    break
                player.add_to_hand(card)
        energy = 0
        if self.has("LANTERN"):
            energy += LANTERN_ENERGY
        if self.has("VERY_HOT_COCOA"):
            energy += COCOA_ENERGY
        if self.elite and self.has("BOOMING_CONCH"):
            energy += CONCH_ENERGY
        if energy:
            sim.gain_energy(energy)
        if self.has("BREAD"):
            cs.energy = max(0, cs.energy - BREAD_ENERGY_LOSS)
        red_skull = player.relics.get(RelicId.RED_SKULL)
        if red_skull is not None:
            red_skull.used = False       # it reacts to hp changes, and the fight may open at half hp or less (or a heal just lifted it above)
            _red_skull(sim, red_skull)


def _class_card() -> Card:
    from sts2_lite.event.run import CLASS_POOL
    return Card.create_generated(rng.choice(CLASS_POOL))

def _colorless_card() -> Card:
    from sts2_lite.event.run import COLORLESS_POOL
    return Card.create_generated(rng.choice(COLORLESS_POOL))

def _ethereal_class_card() -> Card | None:
    from sts2_lite.event.run import CLASS_POOL
    pool = [cid for cid in CLASS_POOL if CardKeyword.ETHEREAL in Card.create_generated(cid).keywords]
    return Card.create_generated(rng.choice(pool)) if pool else None


ENEMY_STATUS_IDS = {StatusId.VULNERABLE: "VULNERABLE_POWER", StatusId.WEAK: "WEAK_POWER", StatusId.STRENGTH: "STRENGTH_POWER"}

def undo_enemy_effects(enemies : list[dict], relics : list[dict]):
    """Takes what a captured player's relics did to the enemies of a bridge state (Bag of Marbles, Red Mask, Philosopher's Stone, Festive Popper) back
    out of the enemy dicts, so the fight can be opened again with another player's relics. Edits `enemies` in place."""
    opening = Opening(relics, "monster")
    removals = [(status, amount) for relic, (status, amount) in ENEMY_STATUS_TURN_1.items() if opening.has(relic)]
    if opening.has("PHILOSOPHERS_STONE"):
        removals.append((StatusId.STRENGTH, 1))
    if opening.has("BRIMSTONE"):        # these two act in the sim's own turn start, which a fight opened again will run
        removals.append((StatusId.STRENGTH, BRIMSTONE_ENEMY))
    for enemy in enemies:
        for status, amount in removals:
            for entry in list(enemy.get("status") or []):
                if entry.get("id") == ENEMY_STATUS_IDS[status]:
                    entry["amount"] -= amount
                    if entry["amount"] <= 0:
                        enemy["status"].remove(entry)
        healed = (POPPER_DAMAGE if opening.has("FESTIVE_POPPER") else 0) + (MERCURY_HOURGLASS_DAMAGE if opening.has("MERCURY_HOURGLASS") else 0)
        if healed:
            enemy["hp"] = min(enemy.get("max_hp", enemy["hp"]), enemy["hp"] + healed)
