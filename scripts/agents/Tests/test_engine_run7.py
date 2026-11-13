from __future__ import annotations
"""Steps of run 7 (Ascension 10) where the sim and the game disagreed, replayed from the saved states: each must now match the game."""
import json, os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from sts2_lite import rng
from sts2_lite.combat import CombatState, CombatSimulator
from sts2_lite.relic import RelicInstance, RelicId
from agents.verify import compare

CASES = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "engine_run7.json")))


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_the_step_matches_the_game(case):
    rng.seed(0)
    state = CombatState.from_dict(case["before"])
    simulator = CombatSimulator(state)
    for action in case["actions"]:
        simulator.perform_action(action)
    assert compare(state, CombatState.from_dict(case["after"]), random_step=case["random_step"]) == []


def test_nunchaku_shown_at_10_has_already_paid_out():
    assert RelicInstance.from_dict({"id": "NUNCHAKU", "counter": 10}).counter == 0
    assert RelicInstance.from_dict({"id": "NUNCHAKU", "counter": 9}).counter == 9
