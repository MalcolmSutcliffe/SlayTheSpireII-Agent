"""Slithering Strangler and Constrict tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
from collections import Counter

import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId


def strangler(name):
    return captures.load("slithering_strangler", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def index_of(cs, card_id):
    return next(i for i, c in enumerate(cs.player.hand) if c.card_id.name == card_id)

# ---------------------------------------------------------------- table
def test_strangler_has_a_table():
    assert "SLITHERING_STRANGLER" in MOVE_TABLES

def test_strangler_values():
    t = MOVE_TABLES["SLITHERING_STRANGLER"](0)
    assert (t["THWACK"].damage, t["THWACK"].hits, t["THWACK"].block) == (7, 1, 5)
    assert (t["LASH"].damage, t["LASH"].hits) == (12, 1)
    assert t["CONSTRICT"].player_status == ((StatusId.CONSTRICT, 3),)

def test_strangler_hits_harder_on_high_ascension():
    t = MOVE_TABLES["SLITHERING_STRANGLER"]
    assert (t(9)["THWACK"].damage, t(9)["LASH"].damage) == (8, 13)
    assert (t(8)["THWACK"].damage, t(8)["LASH"].damage) == (7, 12)

# ---------------------------------------------------------------- reading the bridge
@pytest.mark.parametrize("name, move, damage, hits", [
    ("constrict", "CONSTRICT", 0, 0),
    ("lash", "LASH", 12, 1),
    ("thwack", "THWACK", 7, 1),
])
def test_moves_are_identified_from_captures(name, move, damage, hits):
    e = strangler(name).enemies[0]
    assert (e.move_id, e.attack_damage, e.num_attacks) == (move, damage, hits)

def test_constrict_is_read_from_the_player():
    assert strangler("thwack").player.status_amount(StatusId.CONSTRICT) == 6

# ---------------------------------------------------------------- the moves
def test_constrict_move_applies_three():
    cs = strangler("constrict")
    enemy_turn(cs)
    assert cs.player.status_amount(StatusId.CONSTRICT) == 3
    assert cs.player.current_hp == 54

def test_constrict_stacks_each_time():
    cs = strangler("constrict")
    cs.player.apply_status(StatusId.CONSTRICT, 3)
    enemy_turn(cs)
    assert cs.player.status_amount(StatusId.CONSTRICT) == 6

def test_lash_hits_once():
    cs = strangler("lash")
    enemy_turn(cs)
    assert cs.player.current_hp == 54 - 12

def test_thwack_hits_then_blocks():
    cs = strangler("thwack")
    enemy_turn(cs)
    assert cs.player.current_hp == 43 - 7
    assert cs.enemies[0].block == 5

# ---------------------------------------------------------------- choosing the next move
@pytest.mark.parametrize("name", ["lash", "thwack"])
def test_an_attack_is_always_followed_by_constrict(name):
    cs = strangler(name)
    before = rng.calls
    enemy_turn(cs)
    assert cs.enemies[0].move_id == "CONSTRICT"
    assert rng.calls == before

def test_constrict_is_followed_by_either_attack_equally():
    rng.seed(0)
    counts = Counter()
    for _ in range(2000):
        cs = CombatState.deepcopy(strangler("constrict"))
        enemy_turn(cs)
        counts[cs.enemies[0].move_id] += 1
    assert set(counts) == {"THWACK", "LASH"}
    assert counts["THWACK"] / 2000 == pytest.approx(0.5, abs=0.04)

def test_the_same_attack_may_follow_constrict_twice():
    seen = set()
    for seed in range(100):
        rng.seed(seed)
        cs = strangler("lash")
        moves = []
        for _ in range(6):
            enemy_turn(cs)
            moves.append(cs.enemies[0].move_id)
        seen.add(tuple(m for m in moves if m != "CONSTRICT"))
    assert any(len(set(run)) == 1 for run in seen)

# ---------------------------------------------------------------- Constrict
def test_constrict_hurts_at_the_end_of_the_player_turn():
    cs = strangler("lash")
    rng.seed(0)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 54 - 3 - 12     # constrict first, then the lash

def test_constrict_damage_follows_its_amount():
    cs = strangler("thwack")
    rng.seed(0)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 43 - 6 - 7

def test_block_absorbs_constrict():
    cs = strangler("lash")
    cs.player.block = 3
    rng.seed(0)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 54 - 12

def test_constrict_can_end_the_fight():
    cs = strangler("lash")
    cs.player.current_hp = 3
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert sim.is_over and cs.player.current_hp == 0

def test_constrict_ends_when_the_strangler_dies():
    cs = strangler("thwack")
    cs.enemies[0].current_hp = 1
    sim = CombatSimulator(cs)
    sim.play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    assert StatusId.CONSTRICT not in cs.player.status

def test_constrict_survives_a_copy():
    copy = CombatState.deepcopy(strangler("thwack"))
    assert copy.player.status_amount(StatusId.CONSTRICT) == 6
