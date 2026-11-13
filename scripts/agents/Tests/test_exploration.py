"""The size of UCT's exploration term: it follows the spread of the rewards the search has seen.
Before any win the rewards are losses within -1..0, so the term is small and the moves can be told apart by enemy HP; once a win
has been found they span ~21 points and the term is what a fixed scale of that size gave.
Run from scripts/: python -m pytest agents/Tests/test_exploration.py"""
import math

import pytest

import agents.sts2_MCTS.MCTS as mcts_module
from agents.sts2_MCTS.MCTS import SearchConfig, sts2_DeterministicNode, sts2_MCTS
from test_mcts import defend, make_state, new_mcts, stalled_fight, strike
from agents.sts2_MCTS.params import DEFAULT_CONFIG

LEGACY_SCALE = ((DEFAULT_CONFIG.reward.win_base + 1.0) / 2.0) ** DEFAULT_CONFIG.uct.exploration_power      # the scale the fixed constant used to be


def seen(lo, hi):
    mcts = new_mcts()
    mcts._reward_lo, mcts._reward_hi = lo, hi
    return mcts

def search(cs, sims=300):
    mcts = sts2_MCTS()
    mcts.monte_carlo_tree_search(cs, SearchConfig(max_sims=sims, early_exit=False, paired_scenarios=0))
    return mcts


# ---------------------------------------------------------------- the scale
def test_before_any_rollout_the_span_is_the_minimum():
    assert new_mcts()._exploration_scale() == pytest.approx((DEFAULT_CONFIG.uct.min_reward_span / 2) ** DEFAULT_CONFIG.uct.exploration_power)

def test_a_span_below_the_minimum_is_raised_to_it():
    assert seen(-0.50, -0.45)._exploration_scale() == pytest.approx(new_mcts()._exploration_scale())

def test_the_scale_is_half_the_span_to_the_power():
    assert seen(-1.0, -0.2)._exploration_scale() == pytest.approx((0.8 / 2) ** DEFAULT_CONFIG.uct.exploration_power)

def test_a_win_seen_gives_the_scale_a_fixed_one_of_that_size_used():
    win = DEFAULT_CONFIG.reward.win_base + 1.0            # a win at full health
    assert seen(-1.0, win - 1.0)._exploration_scale() == pytest.approx(LEGACY_SCALE)

def test_the_scale_grows_with_the_span():
    assert seen(-1, 0)._exploration_scale() < seen(-1, 2)._exploration_scale() < seen(-1, 21)._exploration_scale()

def test_a_losing_search_explores_far_less_than_one_that_has_found_a_win():
    assert seen(-1.0, -0.3)._exploration_scale() < 0.2 * seen(-1.0, 21.0)._exploration_scale()

def test_a_fixed_scale_overrides_the_rewards_seen():
    """The benchmark's reference searches set one."""
    fixed = SearchConfig().tuned(exploration_scale=60.0)
    for lo, hi in ((-1.0, -0.3), (-1.0, 21.0)):
        mcts = seen(lo, hi)
        mcts._search_config = fixed
        assert mcts._exploration_scale() == 60.0


# ---------------------------------------------------------------- the UCT score
def child_of(parent_visits, visits, total):
    parent = sts2_DeterministicNode(None, make_state([strike()]), None)
    parent.visits = parent_visits
    child = sts2_DeterministicNode(parent, make_state([strike()]), {"action": "end_turn"})
    child.visits, child.total_reward = visits, total
    return parent, child

def test_the_uct_bonus_shrinks_with_the_scale():
    parent, child = child_of(100, 10, -5.0)
    narrow, wide = seen(-1.0, -0.3), seen(-1.0, 21.0)
    assert narrow.get_uct_score(child, parent) < wide.get_uct_score(child, parent)
    # the mean (-0.5) is the same in both: only the bonus differs
    assert narrow.get_uct_score(child, parent) > -0.5

def test_the_uct_bonus_is_exploration_times_scale_times_the_usual_root():
    parent, child = child_of(100, 10, -5.0)
    mcts = seen(-1.0, -0.3)
    bonus = mcts.get_uct_score(child, parent) - (-0.5)
    assert bonus == pytest.approx(mcts._search_config.exploration * mcts._exploration_scale() * math.sqrt(math.log(100) / 10))


# ---------------------------------------------------------------- through a search
def test_a_fight_that_cannot_be_won_keeps_a_small_scale():
    mcts = search(stalled_fight())
    assert mcts._reward_hi < 1.0
    assert mcts._exploration_scale() < 1.0

def mixed_fight():
    """10 HP against 8 a turn and 24 HP to get through: some rollouts win, some lose."""
    cs = make_state([strike(), strike(), defend()], draw=[strike(), defend(), strike(), defend(), strike()])
    cs.player.max_hp = cs.player.current_hp = 10
    enemy = cs.enemies[0]
    enemy.max_hp = enemy.current_hp = 24
    enemy.attack_damage, enemy.num_attacks = 8, 1
    return cs

def test_a_fight_with_wins_and_losses_widens_the_scale():
    mcts = search(mixed_fight())
    assert mcts._reward_lo < 0 and mcts._reward_hi > DEFAULT_CONFIG.reward.win_base
    assert mcts._exploration_scale() == pytest.approx(((mcts._reward_hi - mcts._reward_lo) / 2) ** DEFAULT_CONFIG.uct.exploration_power)
    assert mcts._exploration_scale() == pytest.approx(LEGACY_SCALE, rel=0.1)

def test_a_fight_that_is_only_won_keeps_a_small_scale():
    """Every rollout wins and they differ only by the HP left: no need to explore widely."""
    cs = make_state([strike()])
    cs.enemies[0].current_hp = 6
    mcts = search(cs)
    assert mcts._reward_lo > DEFAULT_CONFIG.reward.win_base
    assert mcts._exploration_scale() < 1.0

def test_the_range_is_the_rollout_rewards_not_the_information_bonus():
    """Backpropagation adds a bonus to a path; the span is of the rollouts, so a bonus cannot widen it."""
    mcts = search(stalled_fight())
    assert mcts._reward_lo >= -1.0 and mcts._reward_hi <= 1.0 + 0.02 * 100

def test_a_new_fight_starts_from_a_clean_range():
    mcts = search(make_state([strike()]))
    mcts._reward_lo, mcts._reward_hi = -5.0, 500.0
    other = stalled_fight()
    other.player.current_hp = 33                     # no tree can be reused for this state
    other.enemies[0].max_hp = other.enemies[0].current_hp = 77
    mcts.monte_carlo_tree_search(other, SearchConfig(max_sims=100, early_exit=False, paired_scenarios=0))
    assert mcts._reward_hi < 500.0
