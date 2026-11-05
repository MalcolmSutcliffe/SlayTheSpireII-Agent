"""Snapping Jaxfruit tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId


def jaxfruit(name):
    return captures.load("snapping_jaxfruit", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

# ---------------------------------------------------------------- table
def test_jaxfruit_has_a_table():
    assert "SNAPPING_JAXFRUIT" in MOVE_TABLES

def test_jaxfruit_values():
    move = MOVE_TABLES["SNAPPING_JAXFRUIT"](0)["ENERGY_ORB"]
    assert (move.damage, move.hits) == (3, 1)
    assert move.self_status == ((StatusId.STRENGTH, 2),)

def test_jaxfruit_hits_harder_on_high_ascension():
    t = MOVE_TABLES["SNAPPING_JAXFRUIT"]
    assert (t(8)["ENERGY_ORB"].damage, t(9)["ENERGY_ORB"].damage) == (3, 4)

def test_jaxfruit_only_repeats_its_move():
    assert MOVE_TABLES["SNAPPING_JAXFRUIT"](0)["ENERGY_ORB"].next_move == "ENERGY_ORB"

# ---------------------------------------------------------------- reading the bridge
def test_first_turn_capture():
    e = jaxfruit("energy_orb_turn_1").enemies[0]
    assert (e.move_id, e.attack_damage, e.num_attacks) == ("ENERGY_ORB", 3, 1)

def test_strength_is_removed_from_the_displayed_damage():
    cs = jaxfruit("energy_orb_turn_2")
    e = cs.enemies[0]
    assert e.status_amount(StatusId.STRENGTH) == 2
    assert (e.move_id, e.attack_damage) == ("ENERGY_ORB", 3)      # the bridge shows 5

# ---------------------------------------------------------------- the move
def test_the_hit_comes_before_the_strength():
    cs = jaxfruit("energy_orb_turn_1")
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 3
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2

def test_second_turn_hits_for_five():
    cs = jaxfruit("energy_orb_turn_2")
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 5
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 4

def test_damage_grows_by_two_each_turn():
    cs = jaxfruit("energy_orb_turn_1")
    taken = []
    for _ in range(4):
        before = cs.player.current_hp
        enemy_turn(cs)
        taken.append(before - cs.player.current_hp)
    assert taken == [3, 5, 7, 9]

def test_high_ascension_starts_at_four():
    cs = jaxfruit("energy_orb_turn_1")
    cs.ascension = 9
    cs.enemies[0].moves = MOVE_TABLES["SNAPPING_JAXFRUIT"](9)
    cs.enemies[0].attack_damage = 4
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 4

def test_strength_survives_the_whole_round():
    cs = jaxfruit("energy_orb_turn_1")
    CombatSimulator(cs).end_turn()
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2
