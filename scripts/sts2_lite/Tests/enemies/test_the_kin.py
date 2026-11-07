"""The Kin tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId


def kin(name):
    return captures.load("the_kin", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def moves(cs):
    return [e.move_id for e in cs.enemies]

def test_table_values():
    f = MOVE_TABLES["KIN_FOLLOWER"](0)
    assert (f["QUICK_SLASH"].damage, f["QUICK_SLASH"].hits) == (5, 1)
    assert (f["BOOMERANG"].damage, f["BOOMERANG"].hits) == (2, 2)
    assert f["POWER_DANCE"].self_status == ((StatusId.STRENGTH, 2),)
    p = MOVE_TABLES["KIN_PRIEST"](0)
    assert (p["ORB_OF_FRAILTY"].damage, p["BEAM"].damage, p["BEAM"].hits) == (8, 3, 3)
    assert p["ORB_OF_FRAILTY"].player_status == ((StatusId.FRAIL, 1),)
    assert p["ORB_OF_WEAKNESS"].player_status == ((StatusId.WEAK, 1),)
    assert p["RITUAL"].self_status == ((StatusId.STRENGTH, 2),)

def test_deadly_ascension():
    f, p = MOVE_TABLES["KIN_FOLLOWER"](9), MOVE_TABLES["KIN_PRIEST"](9)
    assert f["POWER_DANCE"].self_status == ((StatusId.STRENGTH, 3),)
    assert (p["ORB_OF_FRAILTY"].damage, p["ORB_OF_WEAKNESS"].damage) == (9, 9)
    assert p["RITUAL"].self_status == ((StatusId.STRENGTH, 3),)

@pytest.mark.parametrize("name, expected", [
    ("turn_1", ["QUICK_SLASH", "BOOMERANG", "ORB_OF_WEAKNESS"]),
    ("turn_3", ["BOOMERANG", "POWER_DANCE", "BEAM"]),
    ("turn_4", ["POWER_DANCE", "QUICK_SLASH", "RITUAL"]),
    ("turn_5", ["QUICK_SLASH", "BOOMERANG", "ORB_OF_FRAILTY"]),
])
def test_moves_are_identified_from_captures(name, expected):
    assert moves(kin(name)) == expected

def test_displayed_strength_is_removed_from_the_damage():
    cs = kin("turn_5")
    assert cs.enemies[0].attack_damage == 5
    assert cs.enemies[2].attack_damage == 8

def test_the_leading_follower_dances_first():
    cs = kin("turn_3")
    for _ in range(3):
        enemy_turn(cs)
    assert moves(cs)[:2] == ["BOOMERANG", "POWER_DANCE"]
    assert cs.enemies[1].status_amount(StatusId.STRENGTH) == 2

def test_cycles_follow_the_captures():
    cs = kin("turn_3")
    enemy_turn(cs)
    assert moves(cs) == ["POWER_DANCE", "QUICK_SLASH", "RITUAL"]
    enemy_turn(cs)
    assert moves(cs) == ["QUICK_SLASH", "BOOMERANG", "ORB_OF_FRAILTY"]

def test_orb_of_frailty_and_weakness_debuff_the_player():
    cs = kin("turn_5")
    cs.player.current_hp = cs.player.max_hp = 200      # survive both turns; the dead get no debuffs
    enemy_turn(cs)
    assert cs.player.status_amount(StatusId.FRAIL) == 1
    assert moves(cs)[2] == "ORB_OF_WEAKNESS"
    enemy_turn(cs)
    assert cs.player.status_amount(StatusId.WEAK) == 1

def test_beam_hits_three_times():
    cs = kin("turn_3")
    cs.player.block = 0
    hp = cs.player.current_hp
    for e in cs.enemies[:2]:
        e.num_attacks = 0
    enemy_turn(cs)
    assert cs.player.current_hp == hp - 9

def test_priest_ritual_gives_strength():
    cs = kin("turn_4")
    enemy_turn(cs)
    assert cs.enemies[2].status_amount(StatusId.STRENGTH) == 2

def kill(cs, index):
    sim = CombatSimulator(cs)
    cs.enemies[index].current_hp = 0
    sim.resolve_deaths()
    sim._check_is_over()
    return sim

def test_killing_the_priest_ends_the_fight():
    assert kill(kin("turn_3"), 2).is_over

def test_killing_the_followers_does_not_end_the_fight():
    cs = kin("turn_3")
    kill(cs, 1)
    assert not kill(cs, 0).is_over
