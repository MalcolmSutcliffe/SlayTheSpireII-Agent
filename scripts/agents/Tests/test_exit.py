"""Statistical confidence exit of the search. Run from scripts/."""
import math

import pytest

from agents.sts2_MCTS import MCTS as mcts_module
from agents.sts2_MCTS.MCTS import SearchConfig, MIN_SIMS, Z_SCORE, EPSILON, sts2_MCTS, sts2_DeterministicNode, backpropagate
from agents.Tests.test_mcts import make_state, strike

exit_check = getattr(sts2_MCTS, "_check_statistical_exit", None) or sts2_MCTS._check_statistacl_exit


def searcher(*children, sims=500):
    """A searcher whose root has children with the given (visits, mean reward, standard deviation)."""
    mcts = sts2_MCTS()
    mcts._search_config = SearchConfig()
    root = sts2_DeterministicNode(None, make_state([strike()]), None)
    for i, (visits, mean, std) in enumerate(children):
        child = sts2_DeterministicNode(root, make_state([strike()]), {"action": "play_card", "card_index": i, "target": 0})
        child.visits = visits
        child.total_reward = visits * mean
        child.total_reward_squared = (visits - 1) * std ** 2 + visits * mean ** 2     # sample variance == std ** 2
        root.children.append(child)
    mcts._root_node = root
    mcts._num_sims = sims
    return mcts


def test_nodes_start_with_no_squared_reward():
    assert sts2_DeterministicNode(None, make_state([]), None).total_reward_squared == 0.0

def test_backpropagate_adds_the_squared_reward_up_the_tree():
    root = sts2_DeterministicNode(None, make_state([]), None)
    child = sts2_DeterministicNode(root, make_state([]), None)
    backpropagate(child, 0.5)
    backpropagate(child, -1.0)
    for node in (root, child):
        assert node.total_reward == pytest.approx(-0.5)
        assert node.total_reward_squared == pytest.approx(1.25)
        assert node.visits == 2

def test_no_exit_before_the_minimum_sims():
    assert not exit_check(searcher((200, 0.9, 0.1), (100, 0.1, 0.1), sims=MIN_SIMS - 1))

def test_no_exit_while_a_compared_child_has_few_visits():
    assert not exit_check(searcher((200, 0.9, 0.1), (30, 0.1, 0.1)))
    assert not exit_check(searcher((30, 0.9, 0.1), (20, 0.1, 0.1)))

def test_a_single_child_exits_at_once():
    assert exit_check(searcher((50, 0.5, 0.3)))

def test_a_clear_winner_exits():
    assert exit_check(searcher((300, 0.8, 0.3), (150, 0.2, 0.3)))

def test_a_noisy_near_tie_keeps_searching():
    assert not exit_check(searcher((120, 0.50, 0.5), (100, 0.48, 0.5)))

def test_practically_equal_moves_exit_at_the_indifference_limit():
    assert exit_check(searcher((200, 0.500, 0.001), (150, 0.500, 0.001)))

def test_a_forced_line_with_no_spread_exits():
    assert exit_check(searcher((100, 0.4, 0.0), (80, 0.4, 0.0)))

def test_the_standard_error_uses_variances_not_their_squares():
    """n = 100 each, standard deviation 0.3: SE = sqrt(2 * 0.09 / 100) = 0.0424, so Z * SE = 0.099 > 0.07."""
    assert 0.07 < Z_SCORE * math.sqrt(2 * 0.09 / 100)
    assert not exit_check(searcher((101, 0.57, 0.3), (100, 0.50, 0.3)))

def test_a_better_mean_on_a_less_visited_child_blocks_the_exit():
    """The move returned is the most visited one; if a rival looks better the search is not settled."""
    assert not exit_check(searcher((200, 0.4, 0.3), (100, 0.6, 0.3)))

def test_identical_rewards_do_not_break_the_variance():
    r = 1 / 3
    mcts = searcher((100, r, 0.0), (100, r, 0.0))
    for c in mcts._root_node.children:
        c.total_reward_squared = c.visits * r * r      # rounding can make Q - S^2 / n slightly negative
    assert exit_check(mcts) in (True, False)

def test_exit_thresholds_are_sane():
    assert Z_SCORE > 1.5 and 0 < EPSILON < 0.1
