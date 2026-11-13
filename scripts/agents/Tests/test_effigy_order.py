from __future__ import annotations
"""Bygone Effigy, turn 1 of run 6 (Slow: every card played makes its attacks hit harder, so the big hit goes last).
Hand: Bash, Clumsy, Strike, Bludgeon+, Breakthrough+, Spite, Defend with 4 energy. Breakthrough -> Spite -> Bludgeon is ahead of
Bludgeon first by one to two HP (measured with 600 paired scenarios), but not by enough to show with only 300 of them."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from sts2_lite import rng
from sts2_lite.combat import CombatState
from agents.sts2_MCTS.MCTS import sts2_MCTS, SearchConfig

STATE = os.path.join(os.path.dirname(__file__), "fixtures", "effigy_turn1.json")
BREAKTHROUGH, BASH, BLUDGEON = 4, 0, 3        # hand indices


def search(seed):
    rng.seed(seed)
    state = CombatState.from_dict(json.load(open(STATE)))
    return sts2_MCTS().monte_carlo_tree_search(state, SearchConfig(max_sims=6000, time_budget=None))


def test_a_promising_order_is_replayed_under_more_scenarios_and_then_played():
    move, stats = search(3)          # the tree alone picks Bludgeon here
    assert stats["order"]["scenarios"] > 300        # not significant at 300: the check asked for more
    assert move["card_index"] == BREAKTHROUGH


def test_the_order_check_moves_breakthrough_before_bludgeon():
    move, stats = search(1)
    assert move["card_index"] == BREAKTHROUGH
    assert stats["order"]["replaced"]


def test_an_order_with_no_edge_does_not_get_extended_forever():
    move, stats = search(0)          # Bash first is level with Breakthrough, Spite, Bludgeon: nothing to replace it with
    assert stats["order"]["scenarios"] <= 300 * 4
    assert move["card_index"] in (BASH, BREAKTHROUGH)
