"""Fogmog, Eye With Teeth, Illusion and Dazed tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
from collections import Counter

import pytest

from sts2_lite import rng
from sts2_lite.card import CardId
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy import Enemy
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId


def fog(name):
    return captures.load("fogmog", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def ids(cs):
    return [e.enemy_id for e in cs.enemies]

def discard_ids(cs):
    return [c.card_id for c in cs.player.discard_pile]

def index_of(cs, card_id):
    return next(i for i, c in enumerate(cs.player.hand) if c.card_id.name == card_id)

def kill_eye(cs):
    eye = cs.enemies[0]
    eye.current_hp = 1
    sim = CombatSimulator(cs)
    sim.play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    return sim

# ---------------------------------------------------------------- tables
def test_tables_exist():
    assert "FOGMOG" in MOVE_TABLES and "EYE_WITH_TEETH" in MOVE_TABLES

def test_fogmog_values():
    t = MOVE_TABLES["FOGMOG"](0)
    assert (t["SWIPE"].damage, t["SWIPE"].hits) == (8, 1)
    assert t["SWIPE"].self_status == ((StatusId.STRENGTH, 1),)
    assert t["SWIPE_RANDOM"].damage == 8
    assert (t["HEADBUTT"].damage, t["HEADBUTT"].hits) == (14, 1)
    assert t["ILLUSION"].summon == ("EYE_WITH_TEETH", 0)

def test_fogmog_hits_harder_on_high_ascension():
    t = MOVE_TABLES["FOGMOG"]
    assert (t(9)["SWIPE"].damage, t(9)["HEADBUTT"].damage) == (9, 16)
    assert (t(8)["SWIPE"].damage, t(8)["HEADBUTT"].damage) == (8, 14)

def test_eye_adds_three_dazed():
    assert MOVE_TABLES["EYE_WITH_TEETH"](0)["DISTRACT"].cards == ((CardId.DAZED, 3),)

# ---------------------------------------------------------------- reading the bridge
@pytest.mark.parametrize("name, index, move, damage", [
    ("illusion", 0, "ILLUSION", 0),
    ("swipe", 1, "SWIPE", 8),
    ("headbutt", 1, "HEADBUTT", 14),
    ("eye_with_teeth_dead", 0, "SWIPE", 8),
])
def test_fogmog_moves_are_identified_from_captures(name, index, move, damage):
    e = fog(name).enemies[index]
    assert (e.move_id, e.attack_damage) == (move, damage)

def test_the_eye_is_a_minion_with_illusion():
    eye = fog("swipe").enemies[0]
    assert eye.is_minion and eye.move_id == "DISTRACT"
    assert eye.status_amount(StatusId.ILLUSION) == 1

# ---------------------------------------------------------------- Illusion move
def test_illusion_summons_the_eye_in_front_without_it_acting():
    cs = fog("illusion")
    enemy_turn(cs)
    assert ids(cs) == ["EYE_WITH_TEETH_0", "FOGMOG_0"]
    eye = cs.enemies[0]
    assert (eye.current_hp, eye.max_hp, eye.move_id) == (6, 6, "DISTRACT")
    assert eye.is_minion and eye.status_amount(StatusId.ILLUSION) == 1
    assert cs.player.current_hp == 38 and discard_ids(cs) == []
    assert cs.enemies[1].move_id == "SWIPE"

def test_summoning_the_eye_is_not_random():
    before = rng.calls
    enemy_turn(fog("illusion"))
    assert rng.calls == before

# ---------------------------------------------------------------- the moves
def test_swipe_hits_and_the_eye_adds_dazed():
    cs = fog("swipe")
    enemy_turn(cs)
    assert cs.player.current_hp == 38 - 8
    assert discard_ids(cs).count(CardId.DAZED) == 3
    assert cs.enemies[1].status_amount(StatusId.STRENGTH) == 1

def test_headbutt_hits_with_strength():
    cs = fog("headbutt")
    enemy_turn(cs)
    assert cs.player.current_hp == 30 - 16

def test_a_headbutt_is_followed_by_a_swipe_without_randomness():
    cs = fog("headbutt")
    before = rng.calls
    enemy_turn(cs)
    assert cs.enemies[1].move_id == "SWIPE" and rng.calls == before

def test_after_a_swipe_the_headbutt_is_more_likely():
    rng.seed(0)
    counts = Counter()
    for _ in range(3000):
        cs = CombatState.deepcopy(fog("swipe"))
        enemy_turn(cs)
        counts[cs.enemies[1].move_id] += 1
    assert set(counts) == {"SWIPE_RANDOM", "HEADBUTT"}
    assert counts["HEADBUTT"] / 3000 == pytest.approx(0.6, abs=0.04)

def test_the_random_swipe_always_leads_to_a_headbutt():
    cs = fog("swipe")
    cs.enemies[1].move_id = "SWIPE_RANDOM"
    before = rng.calls
    enemy_turn(cs)
    assert cs.enemies[1].move_id == "HEADBUTT" and rng.calls == before

def test_fogmog_never_swipes_three_times_running():
    for seed in range(60):
        rng.seed(seed)
        cs = fog("swipe")
        moves = [cs.enemies[1].move_id]
        for _ in range(8):
            enemy_turn(cs)
            moves.append(cs.enemies[-1].move_id)
        assert "HEADBUTT" in moves[:3]

# ---------------------------------------------------------------- Dazed
def test_dazed_cannot_be_played():
    cs = fog("headbutt")
    plays = [a for a in CombatSimulator(cs).get_available_actions() if a["action"] == "play_card"]
    assert index_of(cs, "DAZED") not in [a["card_index"] for a in plays]

def test_dazed_in_hand_is_exhausted_at_the_end_of_the_turn():
    cs = fog("headbutt")
    exhausted = len(cs.player.exhaust_pile)
    CombatSimulator(cs)._discard_hand()
    assert len(cs.player.exhaust_pile) == exhausted + 1
    assert cs.player.exhaust_pile[-1].card_id == CardId.DAZED
    assert CardId.DAZED not in discard_ids(cs)

def test_other_cards_are_still_discarded():
    cs = fog("headbutt")
    others = [c.card_id for c in cs.player.hand if c.card_id != CardId.DAZED]
    CombatSimulator(cs)._discard_hand()
    assert Counter(discard_ids(cs)) == Counter([c.card_id for c in fog("headbutt").player.discard_pile] + others)
    assert cs.player.hand == []

def test_exhausting_dazed_fires_the_exhaust_event():
    from sts2_lite.hooks import HookType
    cs = fog("headbutt")
    sim = CombatSimulator(cs)
    seen = []
    import sts2_lite.status as status
    status.STATUS_HANDLERS[(StatusId.STRENGTH, HookType.CARD_EXHAUSTED)] = lambda c, o, a, card: seen.append(card.card_id)
    try:
        cs.enemies[1].apply_status(StatusId.STRENGTH, 1)
        sim._discard_hand()
    finally:
        del status.STATUS_HANDLERS[(StatusId.STRENGTH, HookType.CARD_EXHAUSTED)]
    assert seen == [CardId.DAZED]

# ---------------------------------------------------------------- Illusion power
def test_killing_the_eye_removes_it_from_the_state():
    cs = fog("swipe")
    kill_eye(cs)
    assert ids(cs) == ["FOGMOG_0"]
    assert cs.revivals == [("EYE_WITH_TEETH", 0)]

def test_the_eye_returns_after_the_enemy_turn_at_full_hit_points():
    cs = fog("swipe")
    kill_eye(cs)
    enemy_turn(cs)
    assert ids(cs) == ["EYE_WITH_TEETH_0", "FOGMOG_0"]
    eye = cs.enemies[0]
    assert (eye.current_hp, eye.move_id) == (6, "DISTRACT")
    assert eye.status_amount(StatusId.ILLUSION) == 1 and eye.is_minion
    assert cs.revivals == []

def test_the_eye_does_not_act_the_turn_it_was_killed_or_returns():
    cs = fog("swipe")
    kill_eye(cs)
    enemy_turn(cs)
    assert discard_ids(cs).count(CardId.DAZED) == 0

def test_it_can_be_killed_and_return_again():
    cs = fog("swipe")
    kill_eye(cs)
    enemy_turn(cs)
    cs.player.hand[:] = [c for c in fog("swipe").player.hand]
    kill_eye(cs)
    enemy_turn(cs)
    assert ids(cs) == ["EYE_WITH_TEETH_0", "FOGMOG_0"]

def test_a_missing_eye_in_a_capture_returns_next_turn():
    cs = fog("eye_with_teeth_dead")
    assert cs.revivals == [("EYE_WITH_TEETH", 0)]
    enemy_turn(cs)
    assert ids(cs) == ["EYE_WITH_TEETH_0", "FOGMOG_0"]

def test_no_eye_is_expected_before_the_illusion_move():
    assert fog("illusion").revivals == []

def test_the_eye_does_not_return_if_fogmog_is_dead():
    cs = fog("swipe")
    kill_eye(cs)
    cs.enemies[0].current_hp = 1
    sim = CombatSimulator(cs)
    sim.play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    assert sim.is_over
    sim._play_enemy_turn()
    assert ids(cs) == []

def test_killing_fogmog_ends_the_fight_with_the_eye_alive():
    cs = fog("swipe")
    cs.enemies[1].current_hp = 1
    sim = CombatSimulator(cs)
    sim.play_card(index_of(cs, "STRIKE_IRONCLAD"), 1)
    assert sim.is_over

def test_pending_revivals_survive_a_copy():
    cs = fog("eye_with_teeth_dead")
    assert CombatState.deepcopy(cs).revivals == [("EYE_WITH_TEETH", 0)]

def test_spawning_the_eye_uses_no_randomness():
    before = rng.calls
    Enemy.spawn("EYE_WITH_TEETH", 0, 0)
    assert rng.calls == before
