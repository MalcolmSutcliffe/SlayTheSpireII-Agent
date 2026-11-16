"""The paired and order checks replay their scenarios in batches (SearchConfig.paired_batch) and stop replaying a line once it is settled
(stats.settled). Run from scripts/: python -m pytest agents/Tests/test_batched_checks.py"""
import pytest

from agents.sts2_MCTS.paired_check import PairedCheck
from agents.sts2_MCTS.params import SearchConfig, RolloutPolicy
from agents.sts2_MCTS.stats import expected_excess, settled, SETTLE_MIN_SCENARIOS
from test_mcts import defend
from test_order import tree_with_line, dexterity_turn
from test_paired import block_choice, root_with_visits, child_for
from sts2_lite import rng
from sts2_lite.card import CardId


@pytest.fixture(autouse=True)
def seeded():
    rng.seed(3)          # the scenarios are drawn from the shared source: a fixed one keeps the counts below from changing from run to run


# ---------------------------------------------------------------- the helpers
def test_expected_excess_of_a_known_gap_is_the_gap_when_positive():
    assert expected_excess(0.3, 0.0) == 0.3 and expected_excess(-0.3, 0.0) == 0.0

def test_expected_excess_of_an_even_move_is_the_standard_error_over_root_two_pi():
    assert expected_excess(0.0, 0.1) == pytest.approx(0.1 * 0.3989422804)

def test_expected_excess_falls_as_the_move_looks_worse():
    assert expected_excess(-0.4, 0.1) < expected_excess(-0.1, 0.1) < expected_excess(0.0, 0.1) < expected_excess(0.1, 0.1)

def noise(n, scale=0.5):
    """Zero-mean differences with a spread (alternating, so the mean is exactly 0)."""
    return [scale if i % 2 else -scale for i in range(n)]

def test_nothing_is_settled_before_the_minimum_number_of_scenarios():
    assert not settled([-1.0] * (SETTLE_MIN_SCENARIOS - 1))
    assert settled([-1.0] * SETTLE_MIN_SCENARIOS)

def test_a_line_that_is_clearly_behind_is_settled():
    assert settled([-0.2 + d * 0.1 for d in noise(150)])

def test_a_line_that_is_clearly_ahead_is_settled():
    assert settled([0.2 + d * 0.1 for d in noise(150)])

def test_a_line_that_is_the_same_everywhere_is_settled():
    assert settled([0.0] * 150)

def test_a_noisy_even_line_is_not_settled():
    """A spread of 0.5 over 150 scenarios leaves a standard error of 0.04: it could still be ahead by 0.015."""
    assert not settled(noise(150))

def test_a_noisy_even_line_is_settled_once_the_error_is_small_enough():
    assert settled(noise(2000))


# ---------------------------------------------------------------- the paired check
CONFIG = SearchConfig(paired_scenarios=300, check_workers=1)

def test_a_decided_comparison_stops_after_the_minimum():
    """Defend+ beats Defend by 3 HP in every scenario: 100 are enough, not 300."""
    mcts, root = root_with_visits(block_choice(), CONFIG)
    plain, plus = child_for(root, "play_card", 0), child_for(root, "play_card", 1)
    result = mcts._paired_check(plain)
    assert result["replaced"] and result["child"] is plus
    assert result["scenarios_run"] == SETTLE_MIN_SCENARIOS and result["scenarios"] == 300
    assert all(c["n"] == SETTLE_MIN_SCENARIOS for c in result["compared"])

def test_a_batch_of_zero_replays_every_scenario_as_before():
    mcts, root = root_with_visits(block_choice(), SearchConfig(paired_scenarios=300, paired_batch=0, check_workers=1))
    result = mcts._paired_check(child_for(root, "play_card", 0))
    assert result["replaced"] and result["scenarios_run"] == 300 and result["compared"][0]["n"] == 300

def test_the_decision_is_the_same_with_and_without_batches():
    for picked in (0, 1):
        decisions = []
        for batch in (0, 50, 7):
            mcts, root = root_with_visits(block_choice(), SearchConfig(paired_scenarios=300, paired_batch=batch, check_workers=1))
            result = mcts._paired_check(child_for(root, "play_card", picked))
            decisions.append(result["replaced"])
        assert len(set(decisions)) == 1

def test_an_undecided_rival_is_replayed_under_every_scenario(monkeypatch):
    """Differences that are noise around 0 never settle in 300 scenarios, and the picked line is replayed under all of them."""
    mcts, root = root_with_visits(block_choice(), CONFIG)
    plain, plus = child_for(root, "play_card", 0), child_for(root, "play_card", 1)
    monkeypatch.setattr(PairedCheck, "_contender_line", lambda self, node: ["rival"] if node is plus else ["picked"])
    calls = [0]
    def rollout(state, line, seed):          # the seeds are random, so alternate by call: the rival's differences are exactly +-0.5 in turn
        if line != ["rival"]:
            return 0.0
        calls[0] += 1
        return 0.5 if calls[0] % 2 else -0.5
    mcts._paired_line_rollout = rollout
    result = mcts._paired_check(plain)
    assert result["scenarios_run"] == 300 and result["compared"][0]["n"] == 300
    assert not result["replaced"]

def test_the_rollouts_used_are_fewer_when_the_comparison_is_decided(monkeypatch):
    calls = []
    for batch in (0, 50):
        mcts, root = root_with_visits(block_choice(), SearchConfig(paired_scenarios=300, paired_batch=batch, check_workers=1))
        count = [0]
        original = mcts._paired_line_rollout
        def counting(*args, original=original, count=count):
            count[0] += 1
            return original(*args)
        mcts._paired_line_rollout = counting
        mcts._paired_check(child_for(root, "play_card", 0))
        calls.append(count[0])
    assert calls[1] < calls[0] / 2


# ---------------------------------------------------------------- the order check
ORDER = dict(paired_scenarios=300, check_workers=1, rollout=RolloutPolicy.ClaudeHeuristicGreedy)

def test_a_decided_order_stops_early_and_is_the_same_order():
    results = []
    for batch in (0, 50):
        mcts, first = tree_with_line(dexterity_turn(), [CardId.DEFEND_IRONCLAD, "potion", "end_turn"], SearchConfig(paired_batch=batch, **ORDER))
        results.append(mcts._order_check(first))
    whole, batched = results
    assert whole["replaced"] and batched["replaced"] and whole["action"] == batched["action"]
    assert whole["scenarios"] == 300 and batched["scenarios"] == SETTLE_MIN_SCENARIOS

def test_the_best_order_is_kept_with_fewer_scenarios():
    mcts, first = tree_with_line(dexterity_turn(), ["potion", CardId.DEFEND_IRONCLAD, "end_turn"], SearchConfig(**ORDER))
    result = mcts._order_check(first)
    assert not result["replaced"] and result["scenarios"] < 300
