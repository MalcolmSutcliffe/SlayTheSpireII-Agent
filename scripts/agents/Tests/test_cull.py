"""Identical action culling in MCTS expansion. Run from scripts/."""
import pytest

from sts2_lite import rng
from sts2_lite.card import CardId
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.verify import snapshot
from agents.sts2_MCTS.MCTS import cull_identical_actions, expand_node, sts2_DeterministicNode, _action_key
from agents.Tests.test_mcts import make_state, strike, defend, bash, pile


def kinds(actions):
    return [(a["action"], a.get("card_index"), a.get("target")) for a in actions]

def test_identical_cards_on_the_same_target_are_culled_to_the_first():
    cs = make_state([strike(), strike(), strike(), defend(), defend()])
    c = CombatSimulator(cs)
    kept = cull_identical_actions(c, c.get_available_actions())
    assert kinds(kept) == [("play_card", 0, 0), ("play_card", 3, 0), ("end_turn", None, None)]

def test_different_cards_are_all_kept():
    cs = make_state([strike(), defend(), bash()])
    c = CombatSimulator(cs)
    actions = c.get_available_actions()
    assert cull_identical_actions(c, actions) == actions

def test_upgraded_and_plain_cards_are_not_identical():
    plus = strike()
    plus.is_upgraded = True
    cs = make_state([strike(), plus])
    c = CombatSimulator(cs)
    assert len(cull_identical_actions(c, c.get_available_actions())) == 3

def test_a_card_with_a_different_cost_is_not_identical():
    cheap = strike()
    cheap.energy_cost = 0
    cs = make_state([strike(), cheap])
    c = CombatSimulator(cs)
    assert len(cull_identical_actions(c, c.get_available_actions())) == 3

def test_different_targets_are_kept():
    cs = make_state([strike(), strike()])
    second = cs.enemies[0].__class__()
    second.max_hp = second.current_hp = 60
    second.enemy_id = "E1"
    second.attack_damage, second.num_attacks = 8, 1
    cs.enemies.append(second)
    c = CombatSimulator(cs)
    assert kinds(cull_identical_actions(c, c.get_available_actions())) == [("play_card", 0, 0), ("play_card", 0, 1), ("end_turn", None, None)]

def test_end_turn_is_never_culled():
    c = CombatSimulator(make_state([]))
    assert kinds(cull_identical_actions(c, c.get_available_actions())) == [("end_turn", None, None)]

def test_expansion_makes_one_child_per_distinct_action():
    root = sts2_DeterministicNode(None, make_state([strike()] * 3 + [defend()] * 2), None)
    expand_node(root)
    assert len(root.children) == 3

def test_the_kept_action_is_always_legal():
    cs = make_state([strike(), strike(), defend(), defend(), bash()])
    c = CombatSimulator(cs)
    legal = c.get_available_actions()
    assert all(a in legal for a in cull_identical_actions(c, legal))


# Soundness: every culled action must lead to the same state as the action that was kept in its place.
def result(cs, action):
    rng.seed(7)
    sim = CombatSimulator(CombatState.deepcopy(cs))
    sim.perform_action(action)
    return snapshot(sim.combat_state)

@pytest.mark.parametrize("hand", [
    [strike(), strike(), strike(), defend(), defend()],
    [defend(), strike(), defend(), strike(), bash()],
    [bash(), strike(), bash(), strike(), defend()],
])
def test_culled_actions_lead_to_the_same_state_as_the_kept_one(hand):
    cs = make_state(hand, draw=pile() + pile())
    c = CombatSimulator(cs)
    actions = c.get_available_actions()
    groups = {}
    for a in actions:
        groups.setdefault(_action_key(c, a), []).append(a)
    assert any(len(g) > 1 for g in groups.values())
    for group in groups.values():
        reference = result(cs, group[0])
        for other in group[1:]:
            assert result(cs, other) == reference
