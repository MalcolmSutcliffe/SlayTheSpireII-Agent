"""Inklet tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
from collections import Counter

import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId


def inklets(name="whirlwind_jab_piercing_gaze"):
    return captures.load("inklets", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def index_of(cs, card_id):
    return next(i for i, c in enumerate(cs.player.hand) if c.card_id.name == card_id)

# ---------------------------------------------------------------- table
def test_inklet_has_a_table():
    assert "INKLET" in MOVE_TABLES

def test_inklet_values():
    t = MOVE_TABLES["INKLET"](0)
    assert (t["JAB"].damage, t["JAB"].hits) == (3, 1)
    assert (t["WHIRLWIND"].damage, t["WHIRLWIND"].hits) == (2, 3)
    assert (t["PIERCING_GAZE"].damage, t["PIERCING_GAZE"].hits) == (10, 1)

def test_inklet_hits_harder_on_high_ascension():
    t = MOVE_TABLES["INKLET"]
    assert (t(9)["JAB"].damage, t(9)["WHIRLWIND"].damage, t(9)["PIERCING_GAZE"].damage) == (4, 3, 11)
    assert (t(8)["JAB"].damage, t(8)["WHIRLWIND"].damage, t(8)["PIERCING_GAZE"].damage) == (3, 2, 10)

def test_whirlwind_and_gaze_are_followed_by_a_jab():
    t = MOVE_TABLES["INKLET"](0)
    assert (t["WHIRLWIND"].next_move, t["PIERCING_GAZE"].next_move) == ("JAB", "JAB")

# ---------------------------------------------------------------- reading the bridge
def test_each_inklet_shows_its_own_move():
    cs = inklets()
    assert [(e.move_id, e.attack_damage, e.num_attacks) for e in cs.enemies] == [
        ("WHIRLWIND", 2, 3), ("JAB", 3, 1), ("PIERCING_GAZE", 10, 1)]

def test_inklets_start_slippery():
    assert all(e.status_amount(StatusId.SLIPPERY) == 1 for e in inklets().enemies)

# ---------------------------------------------------------------- the moves
def test_all_three_inklets_attack():
    cs = inklets()
    enemy_turn(cs)
    assert cs.player.current_hp == 43 - 6 - 3 - 10

def test_whirlwind_alone_hits_three_times():
    cs = inklets()
    cs.enemies = cs.enemies[:1]
    enemy_turn(cs)
    assert cs.player.current_hp == 43 - 6

def test_block_is_used_up_across_the_hits():
    cs = inklets()
    cs.enemies = cs.enemies[:1]
    cs.player.block = 4
    enemy_turn(cs)
    assert (cs.player.block, cs.player.current_hp) == (0, 43 - 2)

# ---------------------------------------------------------------- choosing the next move
def test_after_a_whirlwind_or_gaze_comes_a_jab_without_randomness():
    cs = inklets()
    cs.enemies = [cs.enemies[0], cs.enemies[2]]
    before = rng.calls
    enemy_turn(cs)
    assert [e.move_id for e in cs.enemies] == ["JAB", "JAB"]
    assert rng.calls == before

def test_after_a_jab_it_is_gaze_or_whirlwind_equally():
    rng.seed(0)
    counts = Counter()
    for _ in range(2000):
        cs = inklets()
        cs.enemies = [cs.enemies[1]]
        enemy_turn(cs)
        counts[cs.enemies[0].move_id] += 1
    assert set(counts) == {"PIERCING_GAZE", "WHIRLWIND"}
    assert counts["WHIRLWIND"] / 2000 == pytest.approx(0.5, abs=0.04)

def test_the_cycle_always_returns_to_a_jab():
    rng.seed(3)
    cs = inklets()
    cs.enemies = [cs.enemies[1]]
    moves = [cs.enemies[0].move_id]
    for _ in range(12):
        enemy_turn(cs)
        moves.append(cs.enemies[0].move_id)
    assert all(m == "JAB" for m in moves[::2])
    assert all(m != "JAB" for m in moves[1::2])

# ---------------------------------------------------------------- Slippery
def test_a_strike_on_a_slippery_inklet_does_one_damage():
    cs = inklets()
    CombatSimulator(cs).play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    assert cs.enemies[0].current_hp == 15
    assert StatusId.SLIPPERY not in cs.enemies[0].status

def test_the_result_matches_the_captured_state():
    cs = inklets()
    CombatSimulator(cs).play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    ref = inklets("after_attacked")
    assert [(e.current_hp, {k: v.amount for k, v in e.status.items()}) for e in cs.enemies] == \
           [(e.current_hp, {k: v.amount for k, v in e.status.items()}) for e in ref.enemies]
    assert cs.energy == ref.energy and len(cs.player.hand) == len(ref.player.hand)

def test_the_next_strike_on_the_same_inklet_hurts():
    cs = inklets()
    for card in cs.player.hand:
        card.is_upgraded = False
    sim = CombatSimulator(cs)
    sim.play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    sim.play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    assert cs.enemies[0].current_hp == 15 - 6

def test_killing_one_inklet_leaves_the_others():
    cs = inklets()
    cs.enemies[0].status.clear()
    cs.enemies[0].current_hp = 1
    sim = CombatSimulator(cs)
    sim.play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    assert [e.enemy_id for e in cs.enemies] == ["INKLET_1", "INKLET_2"]
    assert not sim.is_over
