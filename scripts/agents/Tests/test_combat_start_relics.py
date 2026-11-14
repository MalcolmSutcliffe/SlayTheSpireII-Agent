import copy
import pytest

from agents.deck_eval.fight_builder import build_fight
from agents.deck_eval.fight_pool import load_pool, target_types
from sts2_lite import rng
from sts2_lite.card.ids import CardId
from sts2_lite.status import StatusId

POOL = load_pool()
pytestmark = pytest.mark.skipif(not POOL, reason="no captures")


def _fight(relics, kind="weak", deck=None, hp=70, seed=1):
    rng.seed(seed)
    template = next(t for t in POOL if t.kind == kind)
    base = next(t for t in POOL if t.kind == "weak").state["player"]
    deck = deck if deck is not None else [dict(c, _upgrade=False) for c in base["deck"]]
    player = {"hp": hp, "max_hp": 80, "relics": [{"id": r} if isinstance(r, str) else r for r in relics], "deck": deck}
    return build_fight(template, deck, player, target_types(POOL))

def _status(creature, status):
    return creature.status_amount(status)


def test_no_relics_is_the_plain_opening():
    sim = _fight([])
    assert len(sim.combat_state.player.hand) == 5 and sim.combat_state.energy == 3 and sim.combat_state.player.block == 0

def test_strength_dexterity_vigor_plating_block_and_heal():
    sim = _fight(["VAJRA", "SWORD_OF_JADE", "ODDLY_SMOOTH_STONE", "AKABEKO", "GORGET", "ANCHOR", "BLOOD_VIAL"], hp=50)
    p = sim.combat_state.player
    assert _status(p, StatusId.STRENGTH) == 4 and _status(p, StatusId.DEXTERITY) == 1
    assert _status(p, StatusId.VIGOR) == 8 and _status(p, StatusId.PLATING) == 4
    assert p.block == 10 and p.current_hp == 52

def test_enemy_debuffs_and_philosophers_stone():
    sim = _fight(["BAG_OF_MARBLES", "RED_MASK", "PHILOSOPHERS_STONE"])
    assert sim.combat_state.max_energy == 4 and sim.combat_state.energy == 4
    for e in sim.combat_state.enemies:
        assert _status(e, StatusId.VULNERABLE) == 1 and _status(e, StatusId.WEAK) == 1 and _status(e, StatusId.STRENGTH) == 1

def test_elite_only_relics():
    plain = _fight(["BOOMING_CONCH", "SLING_OF_COURAGE"], kind="weak")
    elite = _fight(["BOOMING_CONCH", "SLING_OF_COURAGE"], kind="elite")
    assert len(plain.combat_state.player.hand) == 5 and plain.combat_state.energy == 3
    assert len(elite.combat_state.player.hand) == 7 and elite.combat_state.energy == 4
    assert _status(elite.combat_state.player, StatusId.STRENGTH) == 2 and _status(plain.combat_state.player, StatusId.STRENGTH) == 0

def test_energy_and_draw_relics():
    sim = _fight(["LANTERN", "BAG_OF_PREPARATION", "VERY_HOT_COCOA"])
    assert sim.combat_state.energy == 3 + 1 + 4 and len(sim.combat_state.player.hand) == 7
    mushroom = _fight(["BIG_MUSHROOM", "BREAD"])
    assert len(mushroom.combat_state.player.hand) == 3 and mushroom.combat_state.energy == 1

def test_festive_popper_royal_poison_and_pantograph():
    sim = _fight(["FESTIVE_POPPER", "ROYAL_POISON"], hp=50)
    assert sim.combat_state.player.current_hp == 46
    assert any(e.current_hp < e.max_hp for e in sim.combat_state.enemies)
    boss = _fight(["PANTOGRAPH"], kind="boss", hp=40)
    assert boss.combat_state.player.current_hp == 65

def test_blessed_antler_adds_energy_and_three_dazed():
    sim = _fight(["BLESSED_ANTLER"])
    p = sim.combat_state.player
    cards = p.hand + p.draw_pile
    assert sim.combat_state.energy == 4 and sum(c.card_id == CardId.DAZED for c in cards) == 3

def test_bellows_and_bone_tea_upgrade_the_hand():
    sim = _fight(["BELLOWS"])
    assert all(c.is_upgraded or not c.is_upgradable for c in sim.combat_state.player.hand)
    spent = _fight([{"id": "BONE_TEA", "counter": 0}])
    assert any(c.is_upgradable for c in spent.combat_state.player.hand)

def test_innate_cards_are_in_the_opening_hand_even_beyond_five():
    base = [{"id": "STRIKE_IRONCLAD", "type": "Attack", "cost": 1}] * 20
    innate = [{"id": "MIND_BLAST", "type": "Attack", "cost": 2}] * 7
    deck = [dict(c, _upgrade=False) for c in base + innate]
    sim = _fight([], deck=deck)
    hand = sim.combat_state.player.hand
    assert len(hand) == 7 and all(c.card_id == CardId.MIND_BLAST for c in hand)

def test_upgrade_makes_aggression_and_juggling_innate():
    deck = [dict({"id": "STRIKE_IRONCLAD", "type": "Attack", "cost": 1}, _upgrade=False)] * 20
    deck += [{"id": "AGGRESSION", "type": "Power", "cost": 1, "_upgrade": True}, {"id": "JUGGLING", "type": "Power", "cost": 1, "_upgrade": True}]
    sim = _fight([], deck=deck)
    ids = {c.card_id for c in sim.combat_state.player.hand}
    assert CardId.AGGRESSION in ids and CardId.JUGGLING in ids

def test_jeweled_mask_takes_a_free_power():
    deck = [dict({"id": "STRIKE_IRONCLAD", "type": "Attack", "cost": 1}, _upgrade=False)] * 20 + [{"id": "DEMON_FORM", "type": "Power", "cost": 3, "_upgrade": False}]
    sim = _fight(["JEWELED_MASK"], deck=deck)
    demon = [c for c in sim.combat_state.player.hand if c.card_id == CardId.DEMON_FORM]
    assert len(demon) == 1 and demon[0].energy_cost == 0

def test_spent_counter_relics_do_nothing():
    sim = _fight([{"id": "EMBER_TEA", "counter": 0}, {"id": "TEA_OF_DISCOURTESY", "counter": 0}])
    cards = sim.combat_state.player.hand + sim.combat_state.player.draw_pile
    assert _status(sim.combat_state.player, StatusId.STRENGTH) == 0 and not any(c.card_id == CardId.DAZED for c in cards)
