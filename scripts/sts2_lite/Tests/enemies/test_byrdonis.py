"""Byrdonis tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId


def byrdonis(name):
    return captures.load("byrdonis", name)

def bridge(intents, ascension=0, round_number=1, strength=0, territorial=1):
    status = [{"id": "TERRITORIAL_POWER", "amount": territorial}]
    if strength:
        status.append({"id": "STRENGTH_POWER", "amount": strength})
    return CombatState.from_dict({
        "round": round_number, "energy": 3, "max_energy": 3, "context": {"ascension": ascension},
        "player": {"max_hp": 80, "hp": 80, "block": 0, "status": [], "hand": [],
                   "draw_pile": [], "discard_pile": [], "deck": []},
        "enemies": [{"entity_id": "BYRDONIS_0", "max_hp": 84, "hp": 84, "block": 0,
                     "status": status, "intents": intents}],
    })

# ---------------------------------------------------------------- table
def test_byrdonis_has_a_table():
    assert "BYRDONIS" in MOVE_TABLES

def test_byrdonis_values():
    t = MOVE_TABLES["BYRDONIS"]
    assert (t(0)["SWOOP"].damage, t(0)["SWOOP"].hits) == (17, 1)
    assert (t(0)["PECK"].damage, t(0)["PECK"].hits) == (3, 3)

def test_byrdonis_hits_harder_on_high_ascension():
    t = MOVE_TABLES["BYRDONIS"]
    assert (t(9)["SWOOP"].damage, t(9)["PECK"].damage, t(9)["PECK"].hits) == (19, 4, 3)
    assert (t(8)["SWOOP"].damage, t(8)["PECK"].damage) == (17, 3)

def test_byrdonis_alternates():
    t = MOVE_TABLES["BYRDONIS"](0)
    assert (t["SWOOP"].next_move, t["PECK"].next_move) == ("PECK", "SWOOP")


# ---------------------------------------------------------------- real captures (ascension 0)
def test_captured_swoop_turn():
    e = byrdonis("swoop").enemies[0]
    assert (e.move_id, e.attack_damage, e.num_attacks) == ("SWOOP", 17, 1)

def test_captured_peck_turn_reads_base_damage_through_strength():
    e = byrdonis("peck").enemies[0]
    assert e.status[StatusId.STRENGTH].amount == 1
    assert (e.move_id, e.attack_damage, e.num_attacks) == ("PECK", 3, 3)

def test_captured_enemy_has_territorial():
    assert byrdonis("swoop").enemies[0].status[StatusId.TERRITORIAL].amount == 1

def test_captured_peck_hits_for_the_displayed_damage():
    cs = byrdonis("peck")
    cs.player.block = 0
    hp = cs.player.current_hp
    CombatSimulator(cs).end_turn()
    assert hp - cs.player.current_hp == 4 * 3


# ---------------------------------------------------------------- fight
def test_territorial_strength_grows_every_enemy_turn():
    cs = byrdonis("swoop")
    e = cs.enemies[0]
    for expected in (1, 2, 3, 4):
        CombatSimulator(cs).end_turn()
        assert e.status[StatusId.STRENGTH].amount == expected

def test_attack_damage_follows_the_strength_it_gains():
    cs = byrdonis("swoop")
    cs.player.max_hp = cs.player.current_hp = 500
    taken = []
    for _ in range(4):
        before = cs.player.current_hp
        CombatSimulator(cs).end_turn()
        taken.append(before - cs.player.current_hp)
    assert taken == [17, 4 * 3, 19, 6 * 3]

def test_moves_alternate_swoop_and_peck():
    cs = byrdonis("swoop")
    cs.player.max_hp = cs.player.current_hp = 500
    seen = []
    for _ in range(5):
        seen.append(cs.enemies[0].move_id)
        CombatSimulator(cs).end_turn()
    assert seen == ["SWOOP", "PECK", "SWOOP", "PECK", "SWOOP"]

def test_swoop_is_not_confused_with_peck():
    swoop = bridge([{"type": "Attack", "label": "17"}])
    peck = bridge([{"type": "Attack", "label": "3x3"}])
    assert swoop.enemies[0].move_id == "SWOOP" and peck.enemies[0].move_id == "PECK"

def test_high_ascension_swoop():
    cs = bridge([{"type": "Attack", "label": "19"}], ascension=9)
    cs.player.max_hp = cs.player.current_hp = 80
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 80 - 19

def test_byrdonis_uses_no_randomness():
    cs = byrdonis("swoop")
    cs.player.max_hp = cs.player.current_hp = 500
    before = rng.calls
    sim = CombatSimulator(cs)
    for _ in range(6):
        sim._play_enemy_turn()
    assert rng.calls == before

def test_territorial_gains_its_own_amount():
    cs = bridge([{"type": "Attack", "label": "17"}], territorial=2)
    CombatSimulator(cs).end_turn()
    assert cs.enemies[0].status[StatusId.STRENGTH].amount == 2

def test_clone_keeps_the_byrdonis_move_and_strength():
    cs = byrdonis("peck")
    clone = CombatState.deepcopy(cs)
    CombatSimulator(clone).end_turn()
    assert cs.enemies[0].move_id == "PECK" and clone.enemies[0].move_id == "SWOOP"
    assert cs.enemies[0].status[StatusId.STRENGTH].amount == 1
