"""Slime tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.Tests import captures
from sts2_lite.enemy_moves import MOVE_TABLES

ATTACK = lambda n: [{"type": "Attack", "label": str(n)}]
STATUS = lambda n: [{"type": "StatusCard", "label": str(n)}]


def bridge(entity, intents, ascension=0, round_number=1, hp=30):
    return CombatState.from_dict({
        "round": round_number, "energy": 3, "max_energy": 3, "context": {"ascension": ascension},
        "player": {"max_hp": 80, "hp": 80, "block": 0, "status": [], "hand": [],
                   "draw_pile": [], "discard_pile": [], "deck": []},
        "enemies": [{"entity_id": entity, "max_hp": hp, "hp": hp, "block": 0, "status": [], "intents": intents}],
    })

def captured(name):
    return captures.load("slimes", name)

def turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def moves_over(cs, n):
    seen = []
    for _ in range(n):
        seen.append(cs.enemies[0].move_id)
        turn(cs)
    return seen

def discard_ids(cs):
    return [c.card_id for c in cs.player.discard_pile]


# ---------------------------------------------------------------- tables
@pytest.mark.parametrize("name", ["LEAF_SLIME_S", "TWIG_SLIME_S", "LEAF_SLIME_M", "TWIG_SLIME_M"])
def test_slimes_have_tables(name):
    assert name in MOVE_TABLES

def test_leaf_slime_s_values():
    t = MOVE_TABLES["LEAF_SLIME_S"]
    assert (t(0)["BUTT"].damage, t(9)["BUTT"].damage) == (3, 4)
    assert t(0)["GOOP"].cards == ((CardId.SLIMED, 1),)

def test_twig_slime_s_values():
    t = MOVE_TABLES["TWIG_SLIME_S"]
    assert (t(0)["BUTT"].damage, t(9)["BUTT"].damage) == (4, 5)

def test_leaf_slime_m_values():
    t = MOVE_TABLES["LEAF_SLIME_M"]
    assert t(0)["STICKY_SHOT"].cards == ((CardId.SLIMED, 2),)
    assert (t(0)["CLUMP_SHOT"].damage, t(9)["CLUMP_SHOT"].damage) == (8, 9)

def test_twig_slime_m_values():
    t = MOVE_TABLES["TWIG_SLIME_M"]
    assert t(0)["STICKY_SHOT"].cards == ((CardId.SLIMED, 1),)
    assert (t(0)["CLUMP_SHOT"].damage, t(9)["CLUMP_SHOT"].damage) == (11, 12)


# ---------------------------------------------------------------- reading moves
def test_status_intent_is_identified():
    assert bridge("LEAF_SLIME_M_0", STATUS(2)).enemies[0].move_id == "STICKY_SHOT"
    assert bridge("LEAF_SLIME_S_0", STATUS(1)).enemies[0].move_id == "GOOP"

def test_attack_intent_is_identified():
    assert bridge("LEAF_SLIME_M_0", ATTACK(8)).enemies[0].move_id == "CLUMP_SHOT"
    assert bridge("TWIG_SLIME_S_0", ATTACK(4)).enemies[0].move_id == "BUTT"


# ---------------------------------------------------------------- deterministic slimes
def test_twig_slime_s_attacks_every_turn():
    cs = bridge("TWIG_SLIME_S_0", ATTACK(4), hp=7)
    before = rng.calls
    turn(cs); turn(cs); turn(cs)
    assert cs.player.current_hp == 80 - 12
    assert rng.calls == before

def test_leaf_slime_s_alternates_goop_and_butt():
    cs = bridge("LEAF_SLIME_S_0", STATUS(1), hp=15)
    before = rng.calls
    assert moves_over(cs, 5) == ["GOOP", "BUTT", "GOOP", "BUTT", "GOOP"]
    assert rng.calls == before

def test_leaf_slime_s_butt_follows_goop_damage():
    cs = bridge("LEAF_SLIME_S_0", STATUS(1), hp=15)
    turn(cs)
    assert cs.player.current_hp == 80
    turn(cs)
    assert cs.player.current_hp == 77

def test_leaf_slime_m_alternates_sticky_and_clump():
    cs = bridge("LEAF_SLIME_M_0", STATUS(2), hp=32)
    before = rng.calls
    assert moves_over(cs, 4) == ["STICKY_SHOT", "CLUMP_SHOT", "STICKY_SHOT", "CLUMP_SHOT"]
    assert rng.calls == before

def test_leaf_slime_m_adds_two_slimed_then_hits_for_eight():
    cs = bridge("LEAF_SLIME_M_0", STATUS(2), hp=32)
    turn(cs)
    assert discard_ids(cs) == [CardId.SLIMED, CardId.SLIMED] and cs.player.current_hp == 80
    turn(cs)
    assert len(cs.player.discard_pile) == 2 and cs.player.current_hp == 72

def test_goop_adds_one_slimed_to_the_discard_pile():
    cs = bridge("LEAF_SLIME_S_0", STATUS(1), hp=15)
    turn(cs)
    assert discard_ids(cs) == [CardId.SLIMED]
    assert cs.player.hand == [] and cs.player.draw_pile == []

def test_added_slimed_matches_the_real_card():
    real = Card.from_dict(next(c for c in captures.raw("slimes", "slimed_in_hand")["player"]["hand"]
                               if c["id"] == "SLIMED"))
    made = Card.create_slimed()
    for f in ("card_id", "name", "type", "energy_cost", "target_type", "is_upgraded", "is_unplayable"):
        assert getattr(made, f) == getattr(real, f), f
    assert made.type == CardType.Status and made.target_type == TargetType.NONE

def test_each_slimed_is_a_separate_card():
    cs = bridge("LEAF_SLIME_M_0", STATUS(2), hp=32)
    turn(cs)
    a, b = cs.player.discard_pile
    assert a is not b

def test_dead_slime_adds_nothing():
    cs = captured("weak_fight")
    sim = CombatSimulator(cs)
    for e in cs.enemies:
        e.current_hp = 0 if e.enemy_id != "TWIG_SLIME_S_0" else e.current_hp
    sim.resolve_deaths()
    sim._play_enemy_turn()
    assert discard_ids(cs) == []

def test_slimed_in_the_discard_pile_is_cloned():
    cs = bridge("LEAF_SLIME_S_0", STATUS(1), hp=15)
    turn(cs)
    clone = CombatState.deepcopy(cs)
    clone.player.discard_pile.clear()
    assert len(cs.player.discard_pile) == 1


# ---------------------------------------------------------------- twig slime (M): the random one
def test_twig_slime_m_opens_with_sticky_then_must_clump():
    cs = bridge("TWIG_SLIME_M_0", STATUS(1), hp=27)
    before = rng.calls
    turn(cs)
    assert cs.enemies[0].move_id == "CLUMP_SHOT"
    assert rng.calls == before

def test_twig_slime_m_never_uses_sticky_twice_in_a_row():
    for _ in range(50):
        seq = moves_over(bridge("TWIG_SLIME_M_0", STATUS(1), hp=27), 12)
        assert all(not (a == b == "STICKY_SHOT") for a, b in zip(seq, seq[1:]))

def test_twig_slime_m_never_clumps_three_times_in_a_row():
    for _ in range(50):
        seq = moves_over(bridge("TWIG_SLIME_M_0", STATUS(1), hp=27), 14)
        assert not any(a == b == c == "CLUMP_SHOT" for a, b, c in zip(seq, seq[1:], seq[2:]))

def test_twig_slime_m_after_one_clump_can_do_either():
    seen = set()
    for _ in range(100):
        cs = bridge("TWIG_SLIME_M_0", STATUS(1), hp=27)
        turn(cs)                       # sticky -> clump
        turn(cs)                       # clump -> ?
        seen.add(cs.enemies[0].move_id)
    assert seen == {"CLUMP_SHOT", "STICKY_SHOT"}

def test_twig_slime_m_after_two_clumps_must_sticky():
    for _ in range(30):
        cs = bridge("TWIG_SLIME_M_0", ATTACK(11), hp=27)
        e = cs.enemies[0]
        e.move_streak = 2
        turn(cs)
        assert e.move_id == "STICKY_SHOT"

def test_twig_slime_m_choice_is_random_and_uses_the_shared_rng():
    cs = bridge("TWIG_SLIME_M_0", ATTACK(11), hp=27)
    before = rng.calls
    turn(cs)
    assert rng.calls > before

def test_twig_slime_m_intent_matches_the_chosen_move():
    for _ in range(40):
        cs = bridge("TWIG_SLIME_M_0", ATTACK(11), hp=27)
        turn(cs)
        e = cs.enemies[0]
        assert (e.num_attacks > 0) == (e.move_id == "CLUMP_SHOT")

def test_streak_counts_consecutive_uses():
    cs = bridge("TWIG_SLIME_M_0", ATTACK(11), hp=27)
    e = cs.enemies[0]
    assert e.move_streak == 1
    rng.seed(0)
    for _ in range(30):
        prev = e.move_id
        turn(cs)
        assert e.move_streak <= 2
        if e.move_id != prev:
            assert e.move_streak == 1

def test_clone_keeps_the_streak():
    cs = bridge("TWIG_SLIME_M_0", ATTACK(11), hp=27)
    cs.enemies[0].move_streak = 2
    assert CombatState.deepcopy(cs).enemies[0].move_streak == 2


# ---------------------------------------------------------------- real capture: Twig S, Leaf M, Leaf S
def test_captured_fight_reads_all_three_slimes():
    cs = captured("weak_fight")
    assert [e.move_id for e in cs.enemies] == ["BUTT", "STICKY_SHOT", "GOOP"]
    assert [e.attack_damage for e in cs.enemies] == [4, 0, 0]

def test_captured_fight_first_enemy_turn():
    cs = captured("weak_fight")
    turn(cs)
    assert cs.player.current_hp == 80 - 4
    assert discard_ids(cs) == [CardId.SLIMED] * 3
    assert [e.move_id for e in cs.enemies] == ["BUTT", "CLUMP_SHOT", "BUTT"]

def test_captured_fight_second_enemy_turn():
    cs = captured("weak_fight")
    turn(cs); turn(cs)
    assert cs.player.current_hp == 80 - 4 - 4 - 8 - 3
    assert [e.move_id for e in cs.enemies] == ["BUTT", "STICKY_SHOT", "GOOP"]

def test_captured_fight_has_all_three_as_targets():
    cs = captured("weak_fight")
    attacks = [a for a in CombatSimulator(cs).get_available_actions() if a.get("card_index") == 0]
    assert len(attacks) == 3

def test_slimed_from_the_game_is_playable_and_draws():
    cs = captured("slimed_in_hand")
    hand_before = len(cs.player.hand)
    i = next(i for i, c in enumerate(cs.player.hand) if c.card_id == CardId.SLIMED)
    sim = CombatSimulator(cs)
    sim.play_card(i, 0)
    assert cs.player.exhaust_pile[-1].card_id == CardId.SLIMED
    assert len(cs.player.hand) == hand_before   # one out, one drawn
