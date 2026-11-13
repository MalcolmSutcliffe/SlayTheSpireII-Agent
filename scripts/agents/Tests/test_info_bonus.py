"""Information bonus: resolving a draw early, with plays still to make, earns a small bonus.
Run from scripts/: python -m pytest agents/Tests"""
import math
from unittest import mock

import pytest

from sts2_lite import rng
from agents.sts2_MCTS import MCTS as mcts_module
from agents.sts2_MCTS.MCTS import SearchConfig, sts2_MCTS, sts2_ChanceNode, sts2_DeterministicNode, backpropagate
from test_mcts import make_state, strike, defend, pommel, new_mcts
from agents.sts2_MCTS.params import DEFAULT_CONFIG


# ---------------------------------------------------------------- hand-built nodes
def outcome(parent, mean, visits=40, sd=0.0, actionable=True):
    """A sampled outcome with the given mean value and sample standard deviation."""
    n = sts2_DeterministicNode(parent, make_state([]), None)
    n.visits = visits
    n.total_reward = mean * visits
    n.total_reward_squared = visits * mean * mean + (visits - 1) * sd * sd
    n.actionable = actionable
    return n

def chance_with(outcomes_spec, action=None):
    """outcomes_spec: [(mean, count, kwargs)]"""
    node = sts2_ChanceNode(None, make_state([]), action or {"action": "play_card", "card_index": 0, "target": 0})
    for i, (mean, count, kw) in enumerate(outcomes_spec):
        node.outcomes[i] = outcome(node, mean, **kw)
        node.outcome_counts[i] = count
    return node

def searcher(info_bonus=5.0, cap=0.05):
    m = new_mcts(SearchConfig(info_bonus=info_bonus))
    m._info_cap = cap
    return m


def test_a_chance_node_with_clearly_different_outcomes_earns_nearly_the_cap():
    node = chance_with([(0.2, 10, {}), (0.8, 10, {})])
    assert searcher()._information_value(node) == pytest.approx(0.05 * math.tanh(0.3 / DEFAULT_CONFIG.uct.info_sigma), rel=1e-6)

def test_outcomes_of_equal_value_earn_nothing():
    assert searcher()._information_value(chance_with([(0.5, 10, {}), (0.5, 10, {}), (0.5, 3, {})])) == 0.0

def test_outcomes_that_only_look_different_by_noise_earn_nothing():
    """Means differ by less than their estimates' noise: the spread is taken off the noise."""
    node = chance_with([(0.50, 10, {"visits": 5, "sd": 0.5}), (0.53, 10, {"visits": 5, "sd": 0.5})])
    assert searcher()._information_value(node) == 0.0

def test_one_outcome_earns_nothing():
    assert searcher()._information_value(chance_with([(0.5, 10, {})])) == 0.0

def test_outcomes_visited_too_rarely_are_left_out():
    node = chance_with([(0.2, 10, {"visits": 1}), (0.9, 10, {"visits": 1}), (0.5, 10, {})])
    assert searcher()._information_value(node) == 0.0

def test_the_bonus_scales_with_the_share_of_outcomes_with_something_left_to_play():
    full = searcher()._information_value(chance_with([(0.2, 10, {}), (0.8, 10, {})]))
    half = searcher()._information_value(chance_with([(0.2, 10, {}), (0.8, 10, {"actionable": False})]))
    none = searcher()._information_value(chance_with([(0.2, 10, {"actionable": False}), (0.8, 10, {"actionable": False})]))
    assert half == pytest.approx(full / 2) and none == 0.0

def test_the_bonus_never_exceeds_the_cap():
    node = chance_with([(-5.0, 10, {}), (5.0, 10, {})])
    assert searcher(cap=0.03)._information_value(node) <= 0.03


# ---------------------------------------------------------------- along a path
def test_bonuses_reach_the_chance_node_and_its_ancestors_but_not_what_is_below():
    m = searcher()
    root = sts2_DeterministicNode(None, make_state([]), None)
    chance = chance_with([(0.2, 10, {}), (0.8, 10, {})])
    below = outcome(chance, 0.5)
    bonuses = m._information_bonuses([root, chance, below])
    value = m._information_value(chance)
    assert bonuses == [value, value, 0.0]

def test_several_chance_nodes_on_a_path_are_capped_together():
    m = searcher(cap=0.05)
    root = sts2_DeterministicNode(None, make_state([]), None)
    c1, c2 = chance_with([(0.0, 10, {}), (1.0, 10, {})]), chance_with([(0.0, 10, {}), (1.0, 10, {})])
    bonuses = m._information_bonuses([root, c1, outcome(c1, 0.5), c2, outcome(c2, 0.5)])
    assert max(bonuses) <= 0.05 + 1e-12 and bonuses[0] == pytest.approx(0.05, rel=1e-3)

def test_end_turn_earns_no_bonus():
    m = searcher()
    root = sts2_DeterministicNode(None, make_state([]), None)
    chance = chance_with([(0.0, 10, {}), (1.0, 10, {})], action={"action": "end_turn"})
    assert m._information_bonuses([root, chance, outcome(chance, 0.5)]) is None

def test_no_bonus_when_it_is_off():
    m = searcher(info_bonus=0.0, cap=0.0)
    root = sts2_DeterministicNode(None, make_state([]), None)
    chance = chance_with([(0.0, 10, {}), (1.0, 10, {})])
    assert m._information_bonuses([root, chance, outcome(chance, 0.5)]) is None

def test_backpropagate_adds_each_nodes_own_bonus():
    nodes = [sts2_DeterministicNode(None, make_state([]), None) for _ in range(3)]
    backpropagate(nodes, 0.5, [0.1, 0.1, 0.0])
    assert [n.total_reward for n in nodes] == pytest.approx([0.6, 0.6, 0.5])
    assert nodes[0].total_reward_squared == pytest.approx(0.36)
    backpropagate(nodes, 0.5)
    assert [n.visits for n in nodes] == [2, 2, 2]


# ---------------------------------------------------------------- end to end: the bonus turns a lower-valued draw into the choice
def draw_or_strike():
    """Pommel Strike (draws a card: Strike or Defend) against a plain Strike, one energy each."""
    cs = make_state([pommel(), strike()], draw=[strike(), defend()])
    cs.energy = cs.max_energy = 2
    cs.enemies[0].attack_damage = 0
    return cs

def scripted_rollout(strike_line=0.50, drew_strike=0.62, drew_defend=0.30):
    """Rollout values by the first move and, after Pommel Strike, by the card drawn; no rollout noise.
    The value follows the path the search took (a node shared by a transposition has several)."""
    def rollout(self, node):
        self._num_sims += 1
        path = self._last_path
        first = path[1]
        if first.is_chance_node:
            if first.action["action"] == "end_turn":
                return 0.0
            drawn = path[2]                                          # the sampled outcome of Pommel Strike
            return drew_defend if any(c.card_id.name == "DEFEND_IRONCLAD" for c in drawn.state.player.hand) else drew_strike
        return strike_line if first.action["action"] == "play_card" else 0.0
    return rollout

def remembering_path(traverse):
    def wrapper(self, node):
        self._last_path = traverse(self, node)
        return self._last_path
    return wrapper

import contextlib

@contextlib.contextmanager
def scripted(**values):
    with mock.patch.object(sts2_MCTS, "_simulate_combat_rollout", scripted_rollout(**values)), \
         mock.patch.object(sts2_MCTS, "traverse_node", remembering_path(sts2_MCTS.traverse_node)):
        yield

def decide(info_bonus, sims=1500, seed=0, **values):
    rng.seed(seed)
    cs = draw_or_strike()
    with scripted(**values):
        action, stats = sts2_MCTS().monte_carlo_tree_search(
            cs, SearchConfig(max_sims=sims, early_exit=False, prefer_info=False, reuse_tree=False, info_bonus=info_bonus, paired_scenarios=0))
    chosen = cs.player.hand[action["card_index"]].card_id.name if action["action"] == "play_card" else "end_turn"
    return chosen, stats

def test_without_the_bonus_the_better_valued_strike_is_played():
    """The draw is worth 0.46 on average, the plain Strike 0.50."""
    assert decide(0.0)[0] == "STRIKE_IRONCLAD"

def test_with_the_bonus_the_draw_is_played_first():
    chosen, _ = decide(5.0)                      # a cap of 0.1 (5 HP of 50), above the 0.04 the draw is behind
    assert chosen == "POMMEL_STRIKE"

def test_a_bonus_that_is_too_small_does_not_flip_the_choice():
    """The bonus is bounded: 1 HP gives a cap of 0.02, which cannot cover the 0.04 gap."""
    assert decide(1.0)[0] == "STRIKE_IRONCLAD"

def test_half_an_hp_adds_at_most_half_an_hp_of_reward_to_the_draw():
    """cap = 0.5 / starting hp = 0.01 for a 50 HP player."""
    rng.seed(0)
    cs = draw_or_strike()
    with scripted():
        m = sts2_MCTS()
        m.monte_carlo_tree_search(cs, SearchConfig(max_sims=800, early_exit=False, reuse_tree=False, info_bonus=0.5))
    chance = next(c for c in m._root_node.children if c.is_chance_node and c.action["action"] == "play_card")
    below = sum(o.total_reward for o in chance.outcomes.values()) / sum(o.visits for o in chance.outcomes.values())
    added = chance.total_reward / chance.visits - below
    assert m._info_cap == pytest.approx(0.01)
    assert 0.0 < added <= 0.01 + 1e-9
    assert decide(0.5)[0] == "STRIKE_IRONCLAD"           # and it does not close a 0.04 gap

def test_an_hp_of_bonus_is_an_hp_of_win_reward():
    """A win is rated linearly in HP, so the cap for `info_bonus` HP is the reward of that many HP more at the end of a win."""
    def win(hp):
        cs = make_state([])
        cs.enemies[0].current_hp = 0
        cs.player.current_hp = hp
        return cs
    mcts = sts2_MCTS()
    mcts.monte_carlo_tree_search(draw_or_strike(), SearchConfig(max_sims=100, early_exit=False, reuse_tree=False, info_bonus=1.0))
    one_hp = mcts._rate_outcome(win(41)) - mcts._rate_outcome(win(40))
    assert mcts._info_cap == pytest.approx(one_hp)

@pytest.mark.parametrize("hp", [10, 50, 80])
def test_the_cap_is_the_bonus_over_the_starting_hp(hp):
    cs = draw_or_strike()
    cs.player.max_hp = 80
    cs.player.current_hp = hp
    mcts = sts2_MCTS()
    mcts.monte_carlo_tree_search(cs, SearchConfig(max_sims=100, early_exit=False, reuse_tree=False, info_bonus=0.5))
    assert mcts._info_cap == pytest.approx(0.5 / hp)

def test_the_outcomes_own_values_stay_free_of_the_bonus():
    _, _ = decide(5.0)
    rng.seed(0)
    cs = draw_or_strike()
    with scripted():
        m = sts2_MCTS()
        m.monte_carlo_tree_search(cs, SearchConfig(max_sims=800, early_exit=False, reuse_tree=False, info_bonus=5.0))
    chance = next(c for c in m._root_node.children if c.is_chance_node and c.action["action"] == "play_card")
    means = sorted(round(o.total_reward / o.visits, 6) for o in chance.outcomes.values() if o.visits > 5)
    assert means == [0.30, 0.62]

def test_nothing_is_earned_when_no_energy_is_left_to_use_the_draw():
    cs = draw_or_strike()
    cs.energy = cs.max_energy = 1               # Pommel Strike uses the only energy
    rng.seed(0)
    with scripted():
        m = sts2_MCTS()
        m.monte_carlo_tree_search(cs, SearchConfig(max_sims=800, early_exit=False, reuse_tree=False, info_bonus=5.0))
    chance = next(c for c in m._root_node.children if c.is_chance_node and c.action["action"] == "play_card")
    assert all(not o.actionable for o in chance.outcomes.values())
    assert chance.total_reward / chance.visits == pytest.approx(
        sum(o.total_reward for o in chance.outcomes.values()) / sum(o.visits for o in chance.outcomes.values()), abs=1e-9)

def test_default_search_is_unchanged():
    assert SearchConfig().info_bonus == 0.0
    rng.seed(3)
    cs = draw_or_strike()
    a, _ = sts2_MCTS().monte_carlo_tree_search(cs, SearchConfig(max_sims=300, early_exit=False, reuse_tree=False))
    rng.seed(3)
    b, _ = sts2_MCTS().monte_carlo_tree_search(cs, SearchConfig(max_sims=300, early_exit=False, reuse_tree=False, info_bonus=0.0))
    assert a == b
