"""Root tie-break: among statistically tied moves, play the one whose outcome is not yet known (a draw) first.
Run from scripts/: python -m pytest agents/Tests"""
import dataclasses
import math

import pytest

from sts2_lite import rng
from agents.sts2_MCTS.MCTS import (
    SearchConfig, sts2_MCTS, sts2_DeterministicNode, sts2_ChanceNode,
    TIE_MARGIN, TIE_MIN_VISITS, TIE_VISIT_FRACTION, Z_SCORE,
)
from test_mcts import make_state, new_mcts, strike, defend, pommel, pile


PLAY = lambda i: {"action": "play_card", "card_index": i, "target": 0}
END = {"action": "end_turn"}


def with_stats(node, visits, q, var=0.01):
    """Sets the node's statistics to `visits` simulations with mean `q` and sample variance `var`."""
    node.visits = visits
    node.total_reward = visits * q
    node.total_reward_squared = (visits - 1) * var + visits * q * q
    return node

def det(root, action, visits, q, var=0.01):
    return with_stats(sts2_DeterministicNode(root, make_state([]), action), visits, q, var)

def chance(root, action, visits, q, var=0.01):
    return with_stats(sts2_ChanceNode(root, make_state([]), action), visits, q, var)

def root_with(*builders, prefer_info=True):
    """A searcher whose root has the given children; each builder is called with the root."""
    mcts = new_mcts(SearchConfig(prefer_info=prefer_info))
    root = sts2_DeterministicNode(None, make_state([]), None)
    root.children = [b(root) for b in builders]
    mcts._root_node = root
    return mcts, root.children


# ---------------------------------------------------------------- config
def test_prefer_info_is_on_by_default():
    assert SearchConfig().prefer_info is True

def test_prefer_info_is_a_config_field_that_can_be_switched_off():
    assert dataclasses.replace(SearchConfig(), prefer_info=False).prefer_info is False


# ---------------------------------------------------------------- picking
def test_a_tied_draw_goes_first():
    mcts, (strike_play, draw) = root_with(lambda r: det(r, PLAY(0), 1000, 0.800),
                                          lambda r: chance(r, PLAY(1), 900, 0.795))
    assert mcts._pick_root_child() is draw

def test_a_draw_that_is_ahead_goes_first_too():
    mcts, (_, draw) = root_with(lambda r: det(r, PLAY(0), 1000, 0.800), lambda r: chance(r, PLAY(1), 900, 0.810))
    assert mcts._pick_root_child() is draw

def test_without_prefer_info_the_most_visited_move_wins():
    mcts, (top, _) = root_with(lambda r: det(r, PLAY(0), 1000, 0.800), lambda r: chance(r, PLAY(1), 900, 0.795), prefer_info=False)
    assert mcts._pick_root_child() is top

def test_a_clearly_worse_draw_is_not_played_first():
    mcts, (top, _) = root_with(lambda r: det(r, PLAY(0), 1000, 0.80), lambda r: chance(r, PLAY(1), 900, 0.80 - 2 * TIE_MARGIN))
    assert mcts._pick_root_child() is top

def test_a_gap_just_inside_the_margin_but_significant_is_not_a_tie():
    """No variance: a gap of half the margin is certain, so the draw really is worse."""
    mcts, (top, _) = root_with(lambda r: det(r, PLAY(0), 1000, 0.80, var=0.0),
                               lambda r: chance(r, PLAY(1), 900, 0.80 - TIE_MARGIN / 2, var=0.0))
    assert mcts._pick_root_child() is top

def test_a_gap_inside_the_margin_and_the_noise_is_a_tie():
    mcts, (_, draw) = root_with(lambda r: det(r, PLAY(0), 1000, 0.80, var=0.5),
                                lambda r: chance(r, PLAY(1), 900, 0.80 - TIE_MARGIN / 2, var=0.5))
    assert mcts._pick_root_child() is draw

def test_end_turn_is_a_chance_node_but_never_the_informative_move():
    mcts, (top, _) = root_with(lambda r: det(r, PLAY(0), 1000, 0.80), lambda r: chance(r, END, 950, 0.80))
    assert mcts._pick_root_child() is top

def test_a_tied_deterministic_move_does_not_beat_the_top():
    mcts, (top, _) = root_with(lambda r: det(r, PLAY(0), 1000, 0.80), lambda r: det(r, PLAY(1), 950, 0.80))
    assert mcts._pick_root_child() is top

def test_a_thinly_visited_draw_is_not_trusted():
    thin = int(TIE_VISIT_FRACTION * 1000) - 50
    assert thin >= TIE_MIN_VISITS
    mcts, (top, _) = root_with(lambda r: det(r, PLAY(0), 1000, 0.80), lambda r: chance(r, PLAY(1), thin, 0.80))
    assert mcts._pick_root_child() is top

def test_a_draw_with_enough_share_of_the_visits_counts():
    share = int(TIE_VISIT_FRACTION * 1000) + 1
    mcts, (_, draw) = root_with(lambda r: det(r, PLAY(0), 1000, 0.80), lambda r: chance(r, PLAY(1), share, 0.80))
    assert mcts._pick_root_child() is draw

def test_too_few_visits_overall_keeps_the_top_move():
    few = TIE_MIN_VISITS - 1
    mcts, (top, _) = root_with(lambda r: det(r, PLAY(0), few, 0.80), lambda r: chance(r, PLAY(1), few - 1, 0.80))
    assert mcts._pick_root_child() is top

def test_the_most_visited_of_several_tied_draws_wins():
    mcts, (_, a, b) = root_with(lambda r: det(r, PLAY(0), 1000, 0.80), lambda r: chance(r, PLAY(1), 700, 0.80),
                                lambda r: chance(r, PLAY(2), 800, 0.80))
    assert mcts._pick_root_child() is b

def test_the_top_move_is_returned_when_it_is_the_draw():
    mcts, (top, _) = root_with(lambda r: chance(r, PLAY(0), 1000, 0.80), lambda r: det(r, PLAY(1), 600, 0.79))
    assert mcts._pick_root_child() is top

def test_a_single_child_is_returned():
    mcts, (only,) = root_with(lambda r: det(r, PLAY(0), 500, 0.5))
    assert mcts._pick_root_child() is only


# ---------------------------------------------------------------- the tie test itself
def test_tied_is_true_for_the_node_itself():
    mcts, (top, _) = root_with(lambda r: det(r, PLAY(0), 1000, 0.8), lambda r: det(r, PLAY(1), 900, 0.1))
    assert mcts._tied(top, top)

def test_tied_follows_the_early_exit_z_score():
    gap, n, var = 0.004, 400, 0.04
    se = math.sqrt(var / n + var / n)
    assert gap <= TIE_MARGIN and gap > Z_SCORE * se * 0.0       # sanity
    mcts, (top, node) = root_with(lambda r: det(r, PLAY(0), n, 0.8, var), lambda r: chance(r, PLAY(1), n, 0.8 - gap, var))
    assert mcts._tied(node, top) == (gap <= Z_SCORE * se)


# ---------------------------------------------------------------- whole searches
def draw_fight():
    return make_state([pommel(), strike(), defend()], draw=pile() + pile())

def run_search(cs, config, seed=0):
    rng.seed(seed)
    mcts = sts2_MCTS()
    action, stats = mcts.monte_carlo_tree_search(cs, config)
    return mcts, action, stats

def test_the_returned_action_is_the_pick_of_the_tie_break():
    mcts, action, _ = run_search(draw_fight(), SearchConfig(max_sims=600, early_exit=False))
    assert action is mcts._pick_root_child().action

def test_switching_it_off_returns_the_most_visited_move():
    mcts, action, _ = run_search(draw_fight(), SearchConfig(max_sims=600, early_exit=False, prefer_info=False))
    assert action is max(mcts._root_node.children, key=lambda c: c.visits).action

def test_the_tie_break_never_changes_the_statistics():
    on = run_search(draw_fight(), SearchConfig(max_sims=500, early_exit=False), seed=2)[2]
    off = run_search(draw_fight(), SearchConfig(max_sims=500, early_exit=False, prefer_info=False), seed=2)[2]
    assert [(c["visits"], c["q"]) for c in on["children"]] == [(c["visits"], c["q"]) for c in off["children"]]

def test_a_tie_break_move_is_always_one_of_the_roots_children():
    for seed in range(5):
        mcts, action, _ = run_search(draw_fight(), SearchConfig(max_sims=300, early_exit=False), seed)
        assert any(c.action is action for c in mcts._root_node.children)
