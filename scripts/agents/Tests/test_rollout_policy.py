"""Rollout policies. Run from scripts/."""
import contextlib
import io
from collections import Counter
from unittest import mock

import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator
from agents import MCTS as mcts_module
from agents.MCTS import (RolloutPolicies, ROLLOUT_POLICY_DICT, rollout_policy, first_action, random_playable,
                         random_playable_p_end_turn, sts2_MCTS, sts2_DeterministicNode)
from agents.Tests.test_mcts import make_state, strike, defend, bash, draw_fight


def playing(state):
    return CombatSimulator(state).get_available_actions()

def pick_many(policy, actions, n=600, seed=0):
    rng.seed(seed)
    return Counter(id(policy(actions)) for _ in range(n)), {id(a): a for a in actions}

def use_policy(policy):
    return mock.patch.object(mcts_module, "ROLLOUT_POLICY", policy)


def test_every_policy_has_an_implementation():
    assert set(ROLLOUT_POLICY_DICT) == set(RolloutPolicies)

def test_first_action_policy_plays_the_first_action():
    actions = playing(make_state([strike(), defend(), bash()]))
    with use_policy(RolloutPolicies.FirstAction):
        assert rollout_policy(actions) is actions[0]

def test_no_actions_gives_none_and_one_action_is_returned_as_is():
    assert rollout_policy([]) is None
    only = [{"action": "end_turn"}]
    for policy in RolloutPolicies:
        with use_policy(policy):
            assert rollout_policy(only) is only[0]

def test_random_policy_picks_every_action_including_end_turn():
    actions = playing(make_state([strike(), defend()]))
    with use_policy(RolloutPolicies.Random):
        counts, _ = pick_many(rollout_policy, actions)
    assert set(counts) == {id(a) for a in actions}

def test_random_playable_never_ends_the_turn_while_a_card_is_playable():
    actions = playing(make_state([strike(), defend(), bash()]))
    counts, by_id = pick_many(random_playable, actions)
    assert all(by_id[i]["action"] != "end_turn" for i in counts)
    assert len(counts) == len(actions) - 1

def test_p_end_turn_zero_never_ends_and_one_always_ends():
    actions = playing(make_state([strike(), defend()]))
    with mock.patch.object(mcts_module, "P_END_TURN", 0.0):
        counts, by_id = pick_many(random_playable_p_end_turn, actions)
        assert all(by_id[i]["action"] != "end_turn" for i in counts)
    with mock.patch.object(mcts_module, "P_END_TURN", 1.0):
        counts, by_id = pick_many(random_playable_p_end_turn, actions)
        assert all(by_id[i]["action"] == "end_turn" for i in counts)

def test_p_end_turn_ends_about_that_often():
    actions = playing(make_state([strike(), defend()]))
    with mock.patch.object(mcts_module, "P_END_TURN", 0.2):
        counts, by_id = pick_many(random_playable_p_end_turn, actions, n=5000)
    ended = sum(c for i, c in counts.items() if by_id[i]["action"] == "end_turn")
    assert 0.17 < ended / 5000 < 0.23


# a pending choice has no end_turn: every option, the last one too, must stay reachable
def pending_choice_actions(optional):
    cs = make_state([], draw=[strike(), defend(), bash()])
    sim = CombatSimulator(cs)
    sim.request_discovery([strike(), defend(), bash()])
    sim.combat_state.pending_choice.optional = optional
    return sim.get_available_actions()

@pytest.mark.parametrize("policy", [random_playable, random_playable_p_end_turn])
def test_every_option_of_a_pending_choice_can_be_picked(policy):
    actions = pending_choice_actions(optional=False)
    assert all(a["action"] == "choose_card" for a in actions)
    with mock.patch.object(mcts_module, "P_END_TURN", 0.0):
        counts, _ = pick_many(policy, actions)
    assert set(counts) == {id(a) for a in actions}

@pytest.mark.parametrize("policy", list(RolloutPolicies))
def test_a_policy_always_returns_a_legal_action(policy):
    for actions in (playing(make_state([strike(), strike(), defend()])), pending_choice_actions(False), pending_choice_actions(True)):
        with use_policy(policy):
            rng.seed(3)
            assert all(rollout_policy(actions) in actions for _ in range(200))


@pytest.mark.parametrize("policy", list(RolloutPolicies))
def test_rollouts_finish_and_are_reproducible_under_a_seed(policy):
    results = []
    for _ in range(2):
        rng.seed(11)
        mcts = sts2_MCTS()
        root = sts2_DeterministicNode(None, draw_fight(), None)
        mcts._expected_total_hp = mcts._calculate_expected_total_hp(root.state)
        mcts._starting_hp = root.state.player.current_hp
        with use_policy(policy):
            results.append([mcts._simulate_random_combat(root) for _ in range(5)])
    assert results[0] == results[1]
    assert all(-1.0 <= r <= 2.0 for r in results[0])
