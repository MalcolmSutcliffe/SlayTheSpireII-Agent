"""Cubex Construct and Artifact tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.creature import Creature
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId, is_debuff


def cubex(name):
    return captures.load("cubex_construct", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def index_of(cs, card_id):
    return next(i for i, c in enumerate(cs.player.hand) if c.card_id.name == card_id)

def moves_over(cs, turns):
    seen = [cs.enemies[0].move_id]
    for _ in range(turns):
        enemy_turn(cs)
        seen.append(cs.enemies[0].move_id)
    return seen

# ---------------------------------------------------------------- table
def test_cubex_has_a_table():
    assert "CUBEX_CONSTRUCT" in MOVE_TABLES

def test_cubex_values():
    t = MOVE_TABLES["CUBEX_CONSTRUCT"](0)
    assert (t["REPEATER_BLAST"].damage, t["REPEATER_BLAST"].hits) == (7, 1)
    assert (t["REPEATER_BLAST_2"].damage, t["REPEATER_BLAST_2"].hits) == (7, 1)
    assert (t["EXPEL"].damage, t["EXPEL"].hits) == (5, 2)
    for move in ("CHARGE_UP", "REPEATER_BLAST", "REPEATER_BLAST_2"):
        assert t[move].self_status == ((StatusId.STRENGTH, 2),)
    assert t["EXPEL"].self_status == ()

def test_cubex_hits_harder_on_high_ascension():
    t = MOVE_TABLES["CUBEX_CONSTRUCT"]
    assert (t(9)["REPEATER_BLAST"].damage, t(9)["EXPEL"].damage) == (8, 6)
    assert (t(8)["REPEATER_BLAST"].damage, t(8)["EXPEL"].damage) == (7, 5)

# ---------------------------------------------------------------- reading the bridge
@pytest.mark.parametrize("name, move, damage, hits", [
    ("charge_up", "CHARGE_UP", 0, 0),
    ("repeater_blast", "REPEATER_BLAST", 7, 1),
    ("expel_blast", "EXPEL", 5, 2),
])
def test_moves_are_identified_from_captures(name, move, damage, hits):
    e = cubex(name).enemies[0]
    assert (e.move_id, e.attack_damage, e.num_attacks) == (move, damage, hits)

def test_the_second_blast_is_told_apart_by_the_round():
    cs = cubex("repeater_blast")
    cs.turn_number = 3
    cs.enemies[0].identify_move([{"type": "Attack", "label": "9"}, {"type": "Buff", "label": ""}], 3)
    assert cs.enemies[0].move_id == "REPEATER_BLAST_2"

def test_artifact_is_read_from_the_bridge():
    assert cubex("charge_up").enemies[0].status_amount(StatusId.ARTIFACT) == 1

# ---------------------------------------------------------------- the cycle
def test_the_cycle_is_charge_blast_blast_expel_blast_blast_expel():
    assert moves_over(cubex("charge_up"), 7) == [
        "CHARGE_UP", "REPEATER_BLAST", "REPEATER_BLAST_2", "EXPEL",
        "REPEATER_BLAST", "REPEATER_BLAST_2", "EXPEL", "REPEATER_BLAST"]

def test_the_cycle_involves_no_randomness():
    before = rng.calls
    moves_over(cubex("charge_up"), 10)
    assert rng.calls == before

def test_charge_up_gives_strength_without_attacking():
    cs = cubex("charge_up")
    enemy_turn(cs)
    assert cs.player.current_hp == 43
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2

def test_blast_hits_with_strength_then_gains_more():
    cs = cubex("repeater_blast")
    enemy_turn(cs)
    assert cs.player.current_hp == 43 - 9
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 4

def test_expel_hits_twice_and_gives_no_strength():
    cs = cubex("expel_blast")
    enemy_turn(cs)
    assert cs.player.current_hp == 38 - 22
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 6

def test_strength_grows_to_match_the_captures():
    cs = cubex("charge_up")
    strength = []
    for _ in range(3):
        enemy_turn(cs)
        strength.append(cs.enemies[0].status_amount(StatusId.STRENGTH))
    assert strength == [2, 4, 6]            # the expel capture shows 6

# ---------------------------------------------------------------- Artifact
def test_artifact_negates_the_next_debuff():
    cs = cubex("charge_up")
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    assert StatusId.VULNERABLE not in cs.enemies[0].status
    assert StatusId.ARTIFACT not in cs.enemies[0].status

def test_the_second_debuff_lands():
    cs = cubex("charge_up")
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    cs.enemies[0].apply_status(StatusId.WEAK, 1)
    assert cs.enemies[0].status_amount(StatusId.WEAK) == 1

def test_artifact_stacks_negate_several_debuffs():
    cs = cubex("charge_up")
    cs.enemies[0].apply_status(StatusId.ARTIFACT, 1)
    cs.enemies[0].apply_status(StatusId.WEAK, 1)
    cs.enemies[0].apply_status(StatusId.WEAK, 1)
    assert StatusId.WEAK not in cs.enemies[0].status
    assert StatusId.ARTIFACT not in cs.enemies[0].status

def test_artifact_does_not_stop_a_buff():
    cs = cubex("charge_up")
    cs.enemies[0].apply_status(StatusId.STRENGTH, 2)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2
    assert cs.enemies[0].status_amount(StatusId.ARTIFACT) == 1

def test_artifact_stops_a_strength_loss():
    cs = cubex("charge_up")
    cs.enemies[0].apply_status(StatusId.STRENGTH, -2)
    assert StatusId.STRENGTH not in cs.enemies[0].status

def test_bash_on_the_cubex_wastes_the_artifact():
    cs = cubex("charge_up")
    CombatSimulator(cs).play_card(index_of(cs, "BASH"), 0)
    assert StatusId.VULNERABLE not in cs.enemies[0].status
    assert StatusId.ARTIFACT not in cs.enemies[0].status
    assert cs.enemies[0].current_hp < 65

def test_a_second_bash_applies_vulnerable():
    cs = cubex("charge_up")
    cs.energy = 6
    bash = cs.player.hand[index_of(cs, "BASH")]
    cs.player.hand.append(type(bash).create_copy(bash))
    sim = CombatSimulator(cs)
    sim.play_card(index_of(cs, "BASH"), 0)
    sim.play_card(index_of(cs, "BASH"), 0)
    assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == 2

def test_artifact_survives_a_copy():
    copy = CombatState.deepcopy(cubex("charge_up"))
    assert copy.enemies[0].status_amount(StatusId.ARTIFACT) == 1

@pytest.mark.parametrize("status, amount, expected", [
    (StatusId.VULNERABLE, 2, True), (StatusId.WEAK, 1, True), (StatusId.FRAIL, 1, True),
    (StatusId.SHRINK, -1, True), (StatusId.CONSTRICT, 3, True), (StatusId.TANGLED, 1, True),
    (StatusId.STRENGTH, -2, True), (StatusId.STRENGTH, 2, False), (StatusId.RITUAL, 1, False),
])
def test_which_statuses_are_debuffs(status, amount, expected):
    assert is_debuff(status, amount) is expected
