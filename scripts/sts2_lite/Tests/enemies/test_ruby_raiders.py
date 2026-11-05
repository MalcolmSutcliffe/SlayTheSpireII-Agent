"""Ruby Raider tests (Assassin, Axe, Brute, Crossbow, Tracker). Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId

BRUTE, AXE, CROSSBOW = 0, 1, 2          # order in the brute_axe_crossbow captures
BAC_1, BAC_2 = "brute_axe_crossbow_1", "brute_axe_crossbow_2"
CAT_1, CAT_2 = "crossbow_assassin_tracker_1", "crossbow_assassin_tracker_2"


def raiders(name):
    return captures.load("raiders", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def moves_over(cs, index, turns):
    seen = [cs.enemies[index].move_id]
    for _ in range(turns):
        enemy_turn(cs)
        seen.append(cs.enemies[index].move_id)
    return seen

def table(name, ascension=0):
    return MOVE_TABLES[name + "_RUBY_RAIDER"](ascension)

# ---------------------------------------------------------------- tables
def test_every_raider_has_a_table():
    for name in ("ASSASSIN", "AXE", "BRUTE", "CROSSBOW", "TRACKER"):
        assert name + "_RUBY_RAIDER" in MOVE_TABLES

def test_raider_values():
    assert table("ASSASSIN")["KILLSHOT"].damage == 10
    axe = table("AXE")
    assert (axe["SWING_1"].damage, axe["SWING_1"].block, axe["BIG_SWING"].damage) == (5, 5, 12)
    assert table("BRUTE")["BEAT"].damage == 7
    assert table("BRUTE")["ROAR"].self_status == ((StatusId.STRENGTH, 3),)
    assert (table("CROSSBOW")["FIRE"].damage, table("CROSSBOW")["RELOAD"].block) == (14, 3)
    hounds = table("TRACKER")["HOUNDS"]
    assert (hounds.damage, hounds.hits) == (1, 8)
    assert table("TRACKER")["TRACK"].player_status == ((StatusId.FRAIL, 2),)

def test_raiders_are_stronger_on_high_ascension():
    assert table("ASSASSIN", 9)["KILLSHOT"].damage == 11
    axe = table("AXE", 9)
    assert (axe["SWING_1"].damage, axe["SWING_1"].block, axe["BIG_SWING"].damage) == (6, 6, 13)
    assert table("BRUTE", 9)["BEAT"].damage == 8
    assert table("CROSSBOW", 9)["FIRE"].damage == 16
    assert table("TRACKER", 9)["HOUNDS"].hits == 9
    for name in ("ASSASSIN", "AXE", "BRUTE", "CROSSBOW", "TRACKER"):
        assert MOVE_TABLES[name + "_RUBY_RAIDER"](8) == MOVE_TABLES[name + "_RUBY_RAIDER"](0)

# ---------------------------------------------------------------- reading the bridge
@pytest.mark.parametrize("name, expected", [
    (BAC_1, [("BEAT", 7, 1), ("SWING_1", 5, 1), ("RELOAD", 0, 0)]),
    (BAC_2, [("ROAR", 0, 0), ("BIG_SWING", 12, 1), ("FIRE", 14, 1)]),
    (CAT_1, [("RELOAD", 0, 0), ("KILLSHOT", 10, 1), ("TRACK", 0, 0)]),
    (CAT_2, [("FIRE", 14, 1), ("KILLSHOT", 10, 1), ("HOUNDS", 1, 8)]),
])
def test_moves_are_identified_from_captures(name, expected):
    cs = raiders(name)
    assert [(e.move_id, e.attack_damage, e.num_attacks) for e in cs.enemies] == expected

def test_the_second_swing_is_told_apart_by_the_round():
    cs = raiders(BAC_1)
    axe = cs.enemies[AXE]
    axe.identify_move([{"type": "Attack", "label": "5"}, {"type": "Defend", "label": ""}], 2)
    assert axe.move_id == "SWING_2"

# ---------------------------------------------------------------- whole fights
def test_first_turn_of_brute_axe_crossbow():
    cs = raiders(BAC_1)
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 7 - 5
    assert [e.block for e in cs.enemies] == [0, 5, 3]
    assert [e.move_id for e in cs.enemies] == ["ROAR", "SWING_2", "FIRE"]

def test_first_turn_of_crossbow_assassin_tracker():
    cs = raiders(CAT_1)
    enemy_turn(cs)
    assert cs.player.current_hp == 30 - 10
    assert cs.player.status_amount(StatusId.FRAIL) == 2
    assert cs.enemies[0].block == 3
    assert [e.move_id for e in cs.enemies] == ["FIRE", "KILLSHOT", "HOUNDS"]

def test_second_turn_of_crossbow_assassin_tracker():
    cs = raiders(CAT_2)
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 14 - 10 - 8

def test_fifth_turn_of_brute_axe_crossbow():
    cs = raiders(BAC_2)
    enemy_turn(cs)
    assert cs.player.current_hp == 43 - 12 - 14
    assert cs.enemies[BRUTE].status_amount(StatusId.STRENGTH) == 9

def test_the_raiders_are_never_random():
    before = rng.calls
    for name in (BAC_1, BAC_2, CAT_1, CAT_2):
        cs = raiders(name)
        enemy_turn(cs); enemy_turn(cs)
    assert rng.calls == before

# ---------------------------------------------------------------- Assassin
def test_assassin_repeats_its_killshot():
    assert moves_over(raiders(CAT_1), 1, 3) == ["KILLSHOT"] * 4

# ---------------------------------------------------------------- Axe
def test_axe_cycle_is_swing_swing_big():
    assert moves_over(raiders(BAC_1), AXE, 6) == [
        "SWING_1", "SWING_2", "BIG_SWING", "SWING_1", "SWING_2", "BIG_SWING", "SWING_1"]

def test_axe_swing_blocks_and_big_swing_does_not():
    cs = raiders(BAC_1)
    enemy_turn(cs)
    assert cs.enemies[AXE].block == 5
    enemy_turn(cs); enemy_turn(cs)               # second swing, then the big swing
    assert cs.enemies[AXE].block == 0

def test_axe_block_lasts_until_its_own_turn():
    cs = raiders(BAC_2)
    assert cs.enemies[AXE].block == 5
    CombatSimulator(cs).end_turn()
    assert cs.enemies[AXE].block == 0

# ---------------------------------------------------------------- Brute
def test_brute_alternates_beat_and_roar():
    assert moves_over(raiders(BAC_1), BRUTE, 5) == ["BEAT", "ROAR", "BEAT", "ROAR", "BEAT", "ROAR"]

def test_brute_gains_three_strength_per_roar():
    cs = raiders(BAC_1)
    strength = []
    for _ in range(4):
        enemy_turn(cs)
        strength.append(cs.enemies[BRUTE].status_amount(StatusId.STRENGTH))
    assert strength == [0, 3, 3, 6]               # the round-6 capture shows 6

def test_brute_beat_gets_stronger():
    cs = raiders(BAC_1)
    cs.enemies = [cs.enemies[BRUTE]]
    taken = []
    for _ in range(3):
        before = cs.player.current_hp
        enemy_turn(cs)
        taken.append(before - cs.player.current_hp)
    assert taken == [7, 0, 10]

# ---------------------------------------------------------------- Crossbow
def test_crossbow_alternates_reload_and_fire():
    assert moves_over(raiders(CAT_1), 0, 4) == ["RELOAD", "FIRE", "RELOAD", "FIRE", "RELOAD"]

def test_crossbow_reload_blocks_and_fire_does_not():
    cs = raiders(CAT_1)
    enemy_turn(cs)
    assert cs.enemies[0].block == 3
    enemy_turn(cs)
    assert cs.enemies[0].block == 0

# ---------------------------------------------------------------- Tracker
def test_tracker_tracks_once_then_sends_hounds_forever():
    assert moves_over(raiders(CAT_1), 2, 3) == ["TRACK", "HOUNDS", "HOUNDS", "HOUNDS"]

def test_hounds_hit_eight_times_and_block_is_used_up():
    cs = raiders(CAT_2)
    cs.enemies = [cs.enemies[2]]
    cs.player.block = 5
    enemy_turn(cs)
    assert (cs.player.block, cs.player.current_hp) == (0, 80 - 3)

def test_frail_from_the_tracker_lasts_two_player_turns():
    cs = raiders(CAT_1)
    sim = CombatSimulator(cs)
    rng.seed(0)
    sim.end_turn()
    assert cs.player.status_amount(StatusId.FRAIL) == 2
    sim.end_turn()
    assert cs.player.status_amount(StatusId.FRAIL) == 1
