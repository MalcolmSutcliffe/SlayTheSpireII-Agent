from __future__ import annotations
"""A duplicated card that asks for a card choice (Brand under a Duplicator potion) asks twice, one pick per play, in turn."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from sts2_lite import rng
from sts2_lite.combat import CombatState, CombatSimulator
from agents.verify import compare
from data_paths import SEARCH

CASE = json.load(open(SEARCH / "duplicated_brand.json"))


def test_the_second_play_waits_for_the_first_pick():
    rng.seed(0)
    state = CombatState.from_dict(CASE["before"])
    sim = CombatSimulator(state)
    sim.perform_action(CASE["actions"][0])
    assert state.pending_choice is not None
    sim.perform_action(CASE["actions"][1])
    assert state.pending_choice is not None             # the second Brand asks for its own pick


def test_both_picks_leave_the_state_the_game_reports():
    rng.seed(0)
    state = CombatState.from_dict(CASE["before"])
    sim = CombatSimulator(state)
    for action in CASE["actions"]:
        sim.perform_action(action)
    assert state.pending_choice is None
    assert compare(state, CombatState.from_dict(CASE["after"])) == []
