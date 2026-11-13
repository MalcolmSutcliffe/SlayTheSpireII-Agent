"""Bygone Effigy, turn 1 of run 6 (Slow: every card played makes its attacks hit harder, so the big hit goes last).
Hand: Bash, Clumsy, Strike, Bludgeon+, Breakthrough+, Spite, Defend with 4 energy. Breakthrough -> Spite -> Bludgeon is ahead of
Bludgeon first by one to two HP (measured with 600 paired scenarios), but not by enough to show with only 300 of them."""
import functools, json, os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from sts2_lite import rng
from sts2_lite.combat import CombatState
from agents.sts2_MCTS.MCTS import sts2_MCTS, SearchConfig

STATE = os.path.join(os.path.dirname(__file__), "fixtures", "effigy_turn1.json")
BREAKTHROUGH, BASH, BLUDGEON = 4, 0, 3        # hand indices


@functools.cache
def search(seed):   # cached: the same seed is searched by more than one test, and a search is deterministic given its seed
    rng.seed(seed)
    state = CombatState.from_dict(json.load(open(STATE)))
    return sts2_MCTS().monte_carlo_tree_search(state, SearchConfig(max_sims=6000, time_budget=None))


@pytest.mark.slow
def test_a_promising_order_is_replayed_under_more_scenarios_and_then_played():
    move, stats = search(3)          # the tree alone picks Bludgeon here
    assert stats["order"]["scenarios"] > 300        # not significant at 300: the check asked for more
    assert move["card_index"] == BREAKTHROUGH


@pytest.mark.slow
def test_bludgeon_is_not_played_first():
    # Bash first is level with Breakthrough, Spite, Bludgeon (measured), so either is fine; Bludgeon first is the 1-2 HP mistake
    for seed in (1, 2, 3):
        move, _ = search(seed)
        assert move["card_index"] in (BASH, BREAKTHROUGH), seed


@pytest.mark.slow
def test_an_order_with_no_edge_does_not_get_extended_forever():
    move, stats = search(0)          # Bash first is level with Breakthrough, Spite, Bludgeon: nothing to replace it with
    assert stats["order"]["scenarios"] <= 300 * 4
    assert move["card_index"] in (BASH, BREAKTHROUGH)
