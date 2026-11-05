"""Flyconid tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
from collections import Counter

import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId


def flyconid(name):
    return captures.load("flyconid", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def next_moves(name, trials=3000, seed=0):
    """How often each move follows the one in the capture."""
    rng.seed(seed)
    counts = Counter()
    for _ in range(trials):
        cs = CombatState.deepcopy(flyconid(name))
        enemy_turn(cs)
        counts[cs.enemies[0].move_id] += 1
    return counts

# ---------------------------------------------------------------- table
def test_flyconid_has_a_table():
    assert "FLYCONID" in MOVE_TABLES

def test_flyconid_values():
    t = MOVE_TABLES["FLYCONID"](0)
    assert (t["SMASH"].damage, t["SMASH"].hits) == (11, 1)
    assert (t["FRAIL_SPORES"].damage, t["FRAIL_SPORES"].hits) == (8, 1)
    assert t["VULNERABLE_SPORES"].player_status == ((StatusId.VULNERABLE, 2),)
    assert t["FRAIL_SPORES"].player_status == ((StatusId.FRAIL, 2),)

def test_flyconid_hits_harder_on_high_ascension():
    t = MOVE_TABLES["FLYCONID"]
    assert (t(9)["SMASH"].damage, t(9)["FRAIL_SPORES"].damage) == (12, 9)
    assert (t(8)["SMASH"].damage, t(8)["FRAIL_SPORES"].damage) == (11, 8)

# ---------------------------------------------------------------- reading the bridge
@pytest.mark.parametrize("name, move, damage, hits", [
    ("smash", "SMASH", 11, 1),
    ("frail_spores", "FRAIL_SPORES", 8, 1),
    ("vulnerable_spores", "VULNERABLE_SPORES", 0, 0),
])
def test_moves_are_identified_from_captures(name, move, damage, hits):
    e = flyconid(name).enemies[0]
    assert (e.move_id, e.attack_damage, e.num_attacks) == (move, damage, hits)

# ---------------------------------------------------------------- the moves
def test_smash_hits_once():
    cs = flyconid("smash")
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 11

def test_frail_spores_hit_then_apply_frail():
    cs = flyconid("frail_spores")
    enemy_turn(cs)
    assert cs.player.current_hp == 76 - 8
    assert cs.player.status[StatusId.FRAIL].amount == 2

def test_vulnerable_spores_apply_vulnerable():
    cs = flyconid("vulnerable_spores")
    enemy_turn(cs)
    assert cs.player.status[StatusId.VULNERABLE].amount == 2
    assert cs.player.current_hp == 59

def test_frail_makes_block_weaker():
    cs = flyconid("frail_spores")
    enemy_turn(cs)
    assert CombatSimulator(cs).calculate_block(5, cs.player) == 3

def test_frail_from_spores_lasts_two_player_turns():
    cs = flyconid("frail_spores")
    sim = CombatSimulator(cs)
    rng.seed(0)
    sim.end_turn()
    assert cs.player.status[StatusId.FRAIL].amount == 2
    sim.end_turn()
    assert cs.player.status[StatusId.FRAIL].amount == 1

# ---------------------------------------------------------------- choosing the next move
@pytest.mark.parametrize("name", ["smash", "frail_spores", "vulnerable_spores"])
def test_a_move_is_never_repeated(name):
    current = flyconid(name).enemies[0].move_id
    assert current not in next_moves(name, trials=300)

@pytest.mark.parametrize("name, expected", [
    ("smash",             {"VULNERABLE_SPORES": 0.6,  "FRAIL_SPORES": 0.4}),
    ("frail_spores",      {"VULNERABLE_SPORES": 0.75, "SMASH": 0.25}),
    ("vulnerable_spores", {"FRAIL_SPORES": 2 / 3,     "SMASH": 1 / 3}),
])
def test_next_move_follows_the_weights(name, expected):
    counts = next_moves(name)
    assert set(counts) == set(expected)
    for move, share in expected.items():
        assert counts[move] / sum(counts.values()) == pytest.approx(share, abs=0.04)

def test_choice_is_random_so_the_state_is_a_chance_node():
    before = rng.calls
    enemy_turn(flyconid("smash"))
    assert rng.calls > before
