"""The expected-regret exit of the search (ConfidenceParams.max_regret_hp, MCTS._expected_regret): stop when the leader is expected to cost no
more than a given number of HP against the other moves, however noisy the rollouts are.
Run from scripts/: python -m pytest agents/Tests/test_regret_exit.py"""
import math

import pytest

from agents.sts2_MCTS.MCTS import sts2_MCTS, sts2_DeterministicNode
from agents.sts2_MCTS.params import SearchConfig
from test_mcts import make_state, strike, defend


def stats(node, visits, mean, std):
    """Give `node` the statistics of `visits` rollouts with this mean and (sample) standard deviation."""
    node.visits, node.total_reward = visits, visits * mean
    node.total_reward_squared = (visits - 1) * std ** 2 + visits * mean ** 2
    return node

def searcher(children, config, starting_hp=50, sims=1000):
    """A searcher whose root has these (visits, mean, std) moves, as if `sims` simulations had been run."""
    cs = make_state([strike(), defend()])
    m = sts2_MCTS()
    m._search_config = config
    m._starting_hp = starting_hp
    m._num_sims = sims
    m._root_node = sts2_DeterministicNode(None, cs, None)
    m._root_node.children = [stats(sts2_DeterministicNode(m._root_node, cs, {"action": "end_turn"}), *c) for c in children]
    return m

def regret_config(hp=1.0, **more):
    return SearchConfig().tuned(max_regret_hp=hp, **more)


def test_regret_default_and_off_switch():
    assert SearchConfig().confidence.max_regret_hp == 1.0
    noisy = searcher([(400, 20.40, 2.3), (380, 20.38, 2.3)], SearchConfig().tuned(max_regret_hp=0.0))
    assert noisy._check_statistical_exit() is None

def test_two_equal_moves_cost_the_standard_error_over_root_two_pi():
    m = searcher([(400, 20.4, 2.0), (400, 20.4, 2.0)], regret_config())
    se = math.sqrt(2 * 2.0 ** 2 / 400)
    assert m._expected_regret(m._root_node.children[0]) == pytest.approx(se / math.sqrt(2 * math.pi))

def test_a_leader_far_ahead_costs_nothing():
    m = searcher([(400, 20.4, 1.0), (400, 15.0, 1.0), (60, 10.0, 1.0)], regret_config())
    assert m._expected_regret(m._root_node.children[0]) < 1e-9

def test_a_rival_that_looks_better_costs_at_least_its_lead():
    m = searcher([(400, 20.0, 1.0), (400, 21.0, 1.0)], regret_config())
    assert m._expected_regret(m._root_node.children[0]) >= 1.0

def test_the_search_stops_when_the_remaining_regret_is_small():
    """Moves 0.02 apart cannot be told apart at this spread without thousands more simulations, but confusing them costs under an HP."""
    m = searcher([(400, 20.40, 0.8), (380, 20.38, 0.8)], regret_config(hp=1.0))
    assert m._check_statistical_exit() == "REGRET"

def test_a_smaller_allowance_keeps_searching():
    m = searcher([(400, 20.40, 0.8), (380, 20.38, 0.8)], regret_config(hp=0.05))
    assert m._check_statistical_exit() is None

def test_it_waits_for_enough_visits():
    """No rollout may have met the rare loss yet: with few visits the spread looks smaller than it is."""
    m = searcher([(100, 20.40, 0.3), (90, 20.38, 0.3)], regret_config(hp=1.0))
    assert m._check_statistical_exit() is None
    m = searcher([(100, 20.40, 0.3), (90, 20.38, 0.3)], regret_config(hp=1.0, regret_min_visits=50))
    assert m._check_statistical_exit() == "REGRET"

def test_it_does_not_stop_a_losing_line():
    m = searcher([(400, -0.40, 0.3), (380, -0.38, 0.3)], regret_config(hp=1.0))
    assert m._check_statistical_exit() is None

def test_the_allowance_is_in_hp_of_the_starting_hp():
    """A point of HP is 1 / starting HP of reward: the same noise is a smaller share of a small fight's HP, so a big one is searched longer."""
    config = regret_config(hp=1.0)
    close = [(400, 20.40, 1.0), (380, 20.36, 1.0)]
    assert searcher(close, config, starting_hp=20)._check_statistical_exit() == "REGRET"
    assert searcher(close, config, starting_hp=200)._check_statistical_exit() is None

def test_a_full_search_reports_the_reason_and_stops_early():
    """Two Strikes' worth of identical moves in a long fight: the search stops on regret well before the cap."""
    from sts2_lite import rng
    cs = make_state([strike(), defend(), strike()], draw=[strike() for _ in range(8)])
    cs.enemies[0].current_hp = cs.enemies[0].max_hp = 200
    cs.enemies[0].attack_damage = 1
    rng.seed(0)
    _, st = sts2_MCTS().monte_carlo_tree_search(cs, SearchConfig(max_sims=3000, paired_scenarios=0).tuned(max_regret_hp=2.0))
    assert st["exit_reason"] is not None and st["num_sims"] <= 3000
