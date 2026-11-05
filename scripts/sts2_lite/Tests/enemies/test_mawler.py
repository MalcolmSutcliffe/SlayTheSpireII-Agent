"""Mawler tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy import Enemy
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId


def mawler(name):
    return captures.load("mawler", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def sequence(cs, turns):
    """Moves the Mawler shows over `turns` enemy turns, starting with the current one."""
    moves = [cs.enemies[0].move_id]
    for _ in range(turns):
        enemy_turn(cs)
        moves.append(cs.enemies[0].move_id)
    return moves

# ---------------------------------------------------------------- table
def test_mawler_has_a_table():
    assert "MAWLER" in MOVE_TABLES

def test_mawler_values():
    t = MOVE_TABLES["MAWLER"](0)
    assert (t["RIP_AND_TEAR"].damage, t["RIP_AND_TEAR"].hits) == (14, 1)
    assert (t["CLAW"].damage, t["CLAW"].hits) == (4, 2)
    assert t["ROAR"].player_status == ((StatusId.VULNERABLE, 3),)

def test_mawler_hits_harder_on_high_ascension():
    t = MOVE_TABLES["MAWLER"]
    assert (t(9)["RIP_AND_TEAR"].damage, t(9)["CLAW"].damage) == (16, 5)
    assert (t(8)["RIP_AND_TEAR"].damage, t(8)["CLAW"].damage) == (14, 4)

# ---------------------------------------------------------------- reading the bridge
@pytest.mark.parametrize("name, move, damage, hits", [
    ("claw", "CLAW", 4, 2),
    ("roar", "ROAR", 0, 0),
    ("rip_and_tear", "RIP_AND_TEAR", 14, 1),
])
def test_moves_are_identified_from_captures(name, move, damage, hits):
    e = mawler(name).enemies[0]
    assert (e.move_id, e.attack_damage, e.num_attacks) == (move, damage, hits)

def test_vulnerable_is_removed_from_the_displayed_damage():
    assert mawler("rip_and_tear_after_roar").enemies[0].attack_damage == 14
    assert mawler("claw_after_roar").enemies[0].attack_damage == 4

# ---------------------------------------------------------------- the moves
def test_claw_hits_twice():
    cs = mawler("claw")
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 8

def test_rip_and_tear_hits_once():
    cs = mawler("rip_and_tear")
    enemy_turn(cs)
    assert cs.player.current_hp == 44 - 14

def test_roar_applies_vulnerable_for_three_turns():
    cs = mawler("roar")
    enemy_turn(cs)
    assert cs.player.status[StatusId.VULNERABLE].amount == 3
    assert cs.player.current_hp == 80

def test_vulnerable_raises_the_next_attack():
    cs = mawler("rip_and_tear_after_roar")
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 21

# ---------------------------------------------------------------- choosing the next move
@pytest.mark.parametrize("seed", range(40))
def test_no_move_is_repeated(seed):
    rng.seed(seed)
    moves = sequence(mawler("claw"), 12)
    assert all(a != b for a, b in zip(moves, moves[1:]))

@pytest.mark.parametrize("seed", range(40))
def test_roar_is_used_at_most_once(seed):
    rng.seed(seed)
    assert sequence(mawler("claw"), 30).count("ROAR") <= 1

def test_roar_can_come_after_either_attack():
    after = {"CLAW": set(), "RIP_AND_TEAR": set()}
    for seed in range(200):
        rng.seed(seed)
        moves = sequence(mawler("claw"), 6)
        for a, b in zip(moves, moves[1:]):
            if a in after:
                after[a].add(b)
    assert after["CLAW"] == {"RIP_AND_TEAR", "ROAR"}
    assert after["RIP_AND_TEAR"] == {"CLAW", "ROAR"}

def test_after_roar_the_choice_is_free_between_the_attacks():
    seen = set()
    for seed in range(60):
        rng.seed(seed)
        cs = mawler("roar")
        enemy_turn(cs)
        seen.add(cs.enemies[0].move_id)
    assert seen == {"CLAW", "RIP_AND_TEAR"}

def test_once_only_move_stays_unavailable_after_a_copy():
    cs = mawler("roar")
    enemy_turn(cs)
    copy = CombatState.deepcopy(cs)
    assert "ROAR" in copy.enemies[0].used_moves
    copy.enemies[0].used_moves.clear()
    assert "ROAR" in cs.enemies[0].used_moves

def test_forced_choice_costs_no_randomness():
    # after a Roar, with the other attack just used, only one move is left
    cs = mawler("claw")
    cs.enemies[0].used_moves.add("ROAR")
    before = rng.calls
    enemy_turn(cs)
    assert rng.calls == before
    assert cs.enemies[0].move_id == "RIP_AND_TEAR"

# ---------------------------------------------------------------- debuff timing
def test_vulnerable_from_a_roar_lasts_three_player_turns():
    cs = mawler("roar")
    sim = CombatSimulator(cs)
    rng.seed(0)
    sim.end_turn()
    assert cs.player.status[StatusId.VULNERABLE].amount == 3     # as the bridge shows on the next turn
    sim.end_turn()
    assert cs.player.status[StatusId.VULNERABLE].amount == 2

def test_debuff_already_on_the_player_ticks_every_turn():
    cs = mawler("claw_after_roar")
    rng.seed(0)
    CombatSimulator(cs).end_turn()
    assert cs.player.status[StatusId.VULNERABLE].amount == 1
