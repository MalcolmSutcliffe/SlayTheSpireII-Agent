"""Transposition table: the same state reached by a different order of plays is one node.
Run from scripts/: python -m pytest agents/Tests"""
import math
from collections import Counter

import pytest

from sts2_lite import rng
from agents.sts2_MCTS.state_key import state_key
import agents.sts2_MCTS.MCTS as mcts_module
from agents.sts2_MCTS.MCTS import SearchConfig, sts2_MCTS, sts2_DeterministicNode, expand_node, backpropagate
from test_mcts import make_state, strike, defend, pommel, pile, new_mcts, child_for, walk_unique


def two_plays():
    """Strike and Defend, energy for both: Strike->Defend and Defend->Strike end in the same state."""
    return make_state([strike(), defend()])

def expanded_with(cs, table):
    root = sts2_DeterministicNode(None, cs, None)
    expand_node(root, table)
    return root

def search(cs, sims, seed=0):
    rng.seed(seed)
    mcts = sts2_MCTS()
    mcts.monte_carlo_tree_search(cs, SearchConfig(max_sims=sims, early_exit=False))
    return mcts

def expand_plays(node, table):
    """Expands the children that are plain deterministic nodes (End Turn is a chance node)."""
    for c in node.children:
        if not c.is_chance_node:
            expand_node(c, table)

def parents_of(root):
    count = Counter()
    for n in walk_unique(root):
        kids = n.outcomes.values() if n.is_chance_node else n.children
        for k in kids:
            count[id(k)] += 1
    return count


# ---------------------------------------------------------------- expansion
def test_transposed_plays_share_one_node():
    table = {}
    root = expanded_with(two_plays(), table)
    first, second = child_for(root, "play_card", 0), child_for(root, "play_card", 1)
    expand_node(first, table)
    expand_node(second, table)
    after_strike_then_defend = next(c for c in first.children if c.action["action"] == "play_card")
    after_defend_then_strike = next(c for c in second.children if c.action["action"] == "play_card")
    assert after_strike_then_defend is after_defend_then_strike

def test_without_a_table_every_path_gets_its_own_node():
    root = expanded_with(two_plays(), None)
    first, second = child_for(root, "play_card", 0), child_for(root, "play_card", 1)
    expand_node(first)
    expand_node(second)
    a = next(c for c in first.children if c.action["action"] == "play_card")
    b = next(c for c in second.children if c.action["action"] == "play_card")
    assert a is not b and state_key(a.state) == state_key(b.state)

def test_the_roots_children_are_never_shared():
    table = {}
    root = expanded_with(two_plays(), table)
    assert all(state_key(c.state) not in table for c in root.children if not c.is_chance_node)
    assert len({id(c) for c in root.children}) == len(root.children)

def test_different_states_do_not_share():
    table = {}
    root = expanded_with(two_plays(), table)
    expand_plays(root, table)
    ids_by_key = {}
    for n in walk_unique(root):
        if not n.is_chance_node and n.parent is not None and n is not root:
            ids_by_key.setdefault(state_key(n.state), set()).add(id(n))
    assert all(len(v) == 1 for v in ids_by_key.values())     # one node per state, below the root's children

def test_a_parent_does_not_list_the_same_child_twice():
    table = {}
    root = expanded_with(two_plays(), table)
    expand_plays(root, table)
    for c in root.children:
        if not c.is_chance_node:
            assert len({id(k) for k in c.children}) == len(c.children)


# ---------------------------------------------------------------- statistics
def test_backpropagation_follows_the_path_not_the_first_parent():
    table = {}
    root = expanded_with(two_plays(), table)
    first, second = child_for(root, "play_card", 0), child_for(root, "play_card", 1)
    expand_node(first, table)
    expand_node(second, table)
    shared = next(c for c in first.children if c.action["action"] == "play_card")
    assert shared.parent is first                       # the node remembers only its first parent
    backpropagate([root, second, shared], 1.0)
    assert (root.visits, second.visits, shared.visits, first.visits) == (1, 1, 1, 0)

def test_uct_uses_the_parent_the_search_came_through():
    table = {}
    root = expanded_with(two_plays(), table)
    first, second = child_for(root, "play_card", 0), child_for(root, "play_card", 1)
    expand_node(first, table)
    expand_node(second, table)
    shared = next(c for c in first.children if c.action["action"] == "play_card")
    first.visits, second.visits = 4, 100
    shared.visits, shared.total_reward = 10, 5.0
    mcts = new_mcts()
    low = mcts.get_uct_score(shared, first)
    high = mcts.get_uct_score(shared, second)
    assert high > low
    scale = (mcts_module.MIN_REWARD_SPAN / 2.0) ** mcts_module.EXPLORATION_POWER       # no rollout has run: the span is the minimum
    assert high == pytest.approx(0.5 + mcts._search_config.exploration * scale * math.sqrt(math.log(100) / 10))
    assert mcts.get_uct_score(shared) == low            # default: the first parent

def test_uct_with_a_parent_of_zero_visits_is_finite():
    root = sts2_DeterministicNode(None, two_plays(), None)
    child = sts2_DeterministicNode(root, two_plays(), None)
    child.visits, child.total_reward = 1, 0.5
    assert math.isfinite(new_mcts().get_uct_score(child, root))


# ---------------------------------------------------------------- whole searches
def test_a_search_finds_transpositions_and_keeps_the_root_total():
    mcts = search(two_plays(), 200)
    assert mcts._root_node.visits == 200
    shared = [n for n in walk_unique(mcts._root_node) if parents_of(mcts._root_node)[id(n)] > 1]
    assert shared, "Strike/Defend in either order should have met in one node"
    assert sum(c.visits for c in mcts._root_node.children) == 200

def test_root_children_visits_are_their_own():
    mcts = search(two_plays(), 300)
    assert all(parents_of(mcts._root_node)[id(c)] == 1 for c in mcts._root_node.children)

def test_a_search_with_draws_still_runs_and_is_reproducible():
    cs = lambda: make_state([pommel(), strike(), defend()], draw=pile() + pile())
    a, b = search(cs(), 250, seed=3), search(cs(), 250, seed=3)
    visits = lambda m: [(c.action["action"], c.action.get("card_index"), c.visits) for c in m._root_node.children]
    assert visits(a) == visits(b)

def test_each_search_starts_with_an_empty_table():
    mcts = sts2_MCTS()
    rng.seed(0)
    mcts.monte_carlo_tree_search(two_plays(), SearchConfig(max_sims=60, early_exit=False))
    first = set(mcts._table)
    mcts.monte_carlo_tree_search(make_state([defend()]), SearchConfig(max_sims=60, early_exit=False))
    assert first and not (first & set(mcts._table))
