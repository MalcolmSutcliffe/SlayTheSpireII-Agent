"""Rollout policies. Run from scripts/."""
import contextlib
import io
from collections import Counter
from unittest import mock

import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator
from agents.sts2_MCTS import MCTS as mcts_module
from agents.sts2_MCTS.MCTS import (RolloutPolicy, ROLLOUT_POLICY_DICT, rollout_policy, first_action, random_playable,
                         random_playable_p_end_turn, sts2_DeterministicNode, SearchConfig)
from agents.Tests.test_mcts import new_mcts, make_state, strike, defend, bash, draw_fight


def playing_sim(state):
    sim = CombatSimulator(state)
    return sim, sim.get_available_actions()

def playing(state):
    return playing_sim(state)[1]

def pick_many(policy, actions, n=600, seed=0, sim=None):
    rng.seed(seed)
    return Counter(id(policy(sim, actions)) for _ in range(n)), {id(a): a for a in actions}


def test_every_policy_has_an_implementation():
    assert set(ROLLOUT_POLICY_DICT) == set(RolloutPolicy)

def test_first_action_policy_plays_the_first_action():
    sim, actions = playing_sim(make_state([strike(), defend(), bash()]))
    assert rollout_policy(sim, actions, RolloutPolicy.FirstAction) is actions[0]

def test_no_actions_gives_none_and_one_action_is_returned_as_is():
    only = [{"action": "end_turn"}]
    sim = CombatSimulator(make_state([strike()]))
    for policy in RolloutPolicy:
        assert rollout_policy(sim, [], policy) is None
        assert rollout_policy(sim, only, policy) is only[0]

def test_random_policy_picks_every_action_including_end_turn():
    sim, actions = playing_sim(make_state([strike(), defend()]))
    counts, _ = pick_many(lambda c, a: rollout_policy(c, a, RolloutPolicy.RandomAction), actions, sim=sim)
    assert set(counts) == {id(a) for a in actions}

def test_random_playable_never_ends_the_turn_while_a_card_is_playable():
    sim, actions = playing_sim(make_state([strike(), defend(), bash()]))
    counts, by_id = pick_many(random_playable, actions, sim=sim)
    assert all(by_id[i]["action"] != "end_turn" for i in counts)
    assert len(counts) == len(actions) - 1

def test_p_end_turn_zero_never_ends_and_one_always_ends():
    sim, actions = playing_sim(make_state([strike(), defend()]))
    with mock.patch.object(mcts_module, "P_END_TURN", 0.0):
        counts, by_id = pick_many(random_playable_p_end_turn, actions, sim=sim)
        assert all(by_id[i]["action"] != "end_turn" for i in counts)
    with mock.patch.object(mcts_module, "P_END_TURN", 1.0):
        counts, by_id = pick_many(random_playable_p_end_turn, actions, sim=sim)
        assert all(by_id[i]["action"] == "end_turn" for i in counts)

def test_p_end_turn_ends_about_that_often():
    sim, actions = playing_sim(make_state([strike(), defend()]))
    with mock.patch.object(mcts_module, "P_END_TURN", 0.2):
        counts, by_id = pick_many(random_playable_p_end_turn, actions, n=5000, sim=sim)
    ended = sum(c for i, c in counts.items() if by_id[i]["action"] == "end_turn")
    assert 0.17 < ended / 5000 < 0.23


# a pending choice has no end_turn: every option, the last one too, must stay reachable
def pending_choice_actions(optional):
    cs = make_state([], draw=[strike(), defend(), bash()])
    sim = CombatSimulator(cs)
    sim.request_discovery([strike(), defend(), bash()])
    sim.combat_state.pending_choice.optional = optional
    return sim, sim.get_available_actions()

@pytest.mark.parametrize("policy", [random_playable, random_playable_p_end_turn])
def test_every_option_of_a_pending_choice_can_be_picked(policy):
    sim, actions = pending_choice_actions(optional=False)
    assert all(a["action"] == "choose_card" for a in actions)
    with mock.patch.object(mcts_module, "P_END_TURN", 0.0):
        counts, _ = pick_many(policy, actions, sim=sim)
    assert set(counts) == {id(a) for a in actions}

@pytest.mark.parametrize("policy", list(RolloutPolicy))
def test_a_policy_always_returns_a_legal_action(policy):
    for sim, actions in (playing_sim(make_state([strike(), strike(), defend()])), pending_choice_actions(False), pending_choice_actions(True)):
        rng.seed(3)
        assert all(rollout_policy(sim, actions, policy) in actions for _ in range(200))


@pytest.mark.parametrize("policy", list(RolloutPolicy))
def test_rollouts_finish_and_are_reproducible_under_a_seed(policy):
    results = []
    for _ in range(2):
        rng.seed(11)
        mcts = new_mcts(SearchConfig(rollout=policy))
        root = sts2_DeterministicNode(None, draw_fight(), None)
        mcts._expected_total_hp = mcts._calculate_expected_total_hp(root.state)
        mcts._starting_hp = root.state.player.current_hp
        mcts._starting_max_hp = root.state.player.max_hp
        results.append([mcts._simulate_combat_rollout(root) for _ in range(5)])
    assert results[0] == results[1]
    assert all(-1.0 <= r <= mcts_module.REWARD_SPAN for r in results[0])


# --- weighted policies (RarityPreference, Heuristic) ---
from agents.Tests.test_mcts import pommel, make_card
from sts2_lite.card import CardId, CardType, TargetType
from sts2_lite.status import StatusId

WEIGHTED = [mcts_module.rarity_preference, mcts_module.claude_heuristic]

def frequency(policy, sim, actions, card_id, n=3000, seed=1):
    counts, by_id = pick_many(policy, actions, n=n, seed=seed, sim=sim)
    hand = sim.combat_state.player.hand
    return sum(c for i, c in counts.items() if by_id[i]["action"] == "play_card" and hand[by_id[i]["card_index"]].card_id == card_id) / n

def rare(card_id=CardId.BARRICADE):
    return make_card(card_id, "Rare", CardType.Skill, 1, TargetType.Self)

@pytest.mark.parametrize("policy", WEIGHTED)
def test_weighted_policies_end_the_turn_only_by_the_random_action_roll(policy):
    sim, actions = playing_sim(make_state([strike(), defend()]))
    with mock.patch.object(mcts_module, "P_RANDOM_ACTION", 0.0):
        counts, by_id = pick_many(policy, actions, sim=sim)
    assert all(by_id[i]["action"] != "end_turn" for i in counts)
    with mock.patch.object(mcts_module, "P_RANDOM_ACTION", 1.0):
        counts, by_id = pick_many(policy, actions, sim=sim)
    assert any(by_id[i]["action"] == "end_turn" for i in counts)

@pytest.mark.parametrize("policy", WEIGHTED)
def test_weighted_policies_reach_every_option_of_a_pending_choice(policy):
    sim, actions = pending_choice_actions(optional=False)
    counts, _ = pick_many(policy, actions, sim=sim)
    assert set(counts) == {id(a) for a in actions}

def test_rarity_preference_orders_by_rarity_and_treats_bash_as_a_common():
    with mock.patch.object(mcts_module, "P_RANDOM_ACTION", 0.0), mock.patch.object(mcts_module, "BLOCK_MULT", 0.0):
        sim, actions = playing_sim(make_state([strike(), rare(), bash()]))
        assert frequency(mcts_module.rarity_preference, sim, actions, CardId.BARRICADE) > \
            frequency(mcts_module.rarity_preference, sim, actions, CardId.BASH)
    # weights: rare 8, bash (common) 2, strike 1 -> with Bash unable to be a vulnerable-first pick (all enemies vulnerable)
    sim.combat_state.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    with mock.patch.object(mcts_module, "P_RANDOM_ACTION", 0.0), mock.patch.object(mcts_module, "BLOCK_MULT", 0.0):
        f_bash = frequency(mcts_module.rarity_preference, sim, actions, CardId.BASH)
        f_strike = frequency(mcts_module.rarity_preference, sim, actions, CardId.STRIKE_IRONCLAD)
    assert f_bash == pytest.approx(2/11, abs=0.03) and f_strike == pytest.approx(1/11, abs=0.03)

@pytest.mark.parametrize("policy", WEIGHTED)
def test_vulnerable_is_played_before_attacks(policy):
    sim, actions = playing_sim(make_state([strike(), strike(), bash()]))
    with mock.patch.object(mcts_module, "P_RANDOM_ACTION", 0.0):
        assert frequency(policy, sim, actions, CardId.BASH) > 0.7
    sim.combat_state.enemies[0].apply_status(StatusId.VULNERABLE, 2)           # already vulnerable: attacks are free to go
    with mock.patch.object(mcts_module, "P_RANDOM_ACTION", 0.0):
        assert frequency(policy, sim, actions, CardId.BASH) < 0.5

@pytest.mark.parametrize("policy", WEIGHTED)
def test_block_is_preferred_only_while_damage_is_unblocked(policy):
    cs = make_state([strike(), defend()])
    cs.enemies[0].attack_damage = 20
    sim, actions = playing_sim(cs)
    with mock.patch.object(mcts_module, "P_RANDOM_ACTION", 0.0):
        under_attack = frequency(policy, sim, actions, CardId.DEFEND_IRONCLAD)
        cs.player.block = 20
        covered = frequency(policy, sim, actions, CardId.DEFEND_IRONCLAD)
    assert under_attack > 0.7 > covered

@pytest.mark.parametrize("policy", WEIGHTED)
def test_block_preference_grows_with_incoming_damage(policy):
    out = []
    for dmg in (3, 8, 30):
        cs = make_state([strike(), defend()])
        cs.enemies[0].attack_damage = dmg
        sim, actions = playing_sim(cs)
        with mock.patch.object(mcts_module, "P_RANDOM_ACTION", 0.0):
            out.append(frequency(policy, sim, actions, CardId.DEFEND_IRONCLAD, n=4000))
    assert out[0] < out[1] < out[2]

@pytest.mark.parametrize("policy", WEIGHTED)
def test_draw_cards_are_played_first_only_with_room_in_hand(policy):
    sim, actions = playing_sim(make_state([strike(), strike(), pommel()]))
    with mock.patch.object(mcts_module, "P_RANDOM_ACTION", 0.0), mock.patch.object(mcts_module, "BLOCK_MULT", 0.0):
        roomy = frequency(policy, sim, actions, CardId.POMMEL_STRIKE)
        sim.combat_state.player.hand = [strike() for _ in range(9)] + [pommel()]
        actions = sim.get_available_actions()
        full = frequency(policy, sim, actions, CardId.POMMEL_STRIKE)
    assert roomy > 0.6 and full < 0.1

def test_heuristic_plays_powers_first():
    power = make_card(CardId.INFLAME, "Inflame", CardType.Power, 1, TargetType.Self)
    sim, actions = playing_sim(make_state([strike(), strike(), power]))
    with mock.patch.object(mcts_module, "P_RANDOM_ACTION", 0.0):
        assert frequency(mcts_module.claude_heuristic, sim, actions, CardId.INFLAME) > 0.55


# --- focus fire ---
def two_enemies(hp_a, hp_b, block_a=0, block_b=0, minion_b=False):
    from sts2_lite.enemy import Enemy
    cs = make_state([strike(), strike()])
    b = Enemy()
    b.max_hp = b.current_hp = hp_b
    b.enemy_id, b.attack_damage, b.num_attacks, b.block, b.is_minion = "E1", 5, 1, block_b, minion_b
    cs.enemies[0].current_hp, cs.enemies[0].block = hp_a, block_a
    cs.enemies.append(b)
    return cs

def targets_chosen(policy, cs, n=400):
    sim = CombatSimulator(cs)
    actions = sim.get_available_actions()
    rng.seed(2)
    with mock.patch.object(mcts_module, "P_RANDOM_ACTION", 0.0):
        return {policy(sim, actions)["target"] for _ in range(n)}

@pytest.mark.parametrize("policy", WEIGHTED)
@pytest.mark.parametrize("focus,expected", [("none", {0, 1}), ("first", {0}), ("lowest_hp", {1}), ("lowest_hp_block", {1})])
def test_focus_modes_pick_the_expected_enemy(policy, focus, expected):
    with mock.patch.object(mcts_module, "FOCUS", focus):
        assert targets_chosen(policy, two_enemies(30, 12)) == expected

@pytest.mark.parametrize("policy", WEIGHTED)
def test_focus_counts_block(policy):
    cs = two_enemies(hp_a=20, hp_b=12, block_b=15)           # 20 against 27 effective
    with mock.patch.object(mcts_module, "FOCUS", "lowest_hp_block"):
        assert targets_chosen(policy, cs) == {0}
    with mock.patch.object(mcts_module, "FOCUS", "lowest_hp"):
        assert targets_chosen(policy, two_enemies(hp_a=20, hp_b=12, block_b=15)) == {1}

@pytest.mark.parametrize("policy", WEIGHTED)
def test_focus_skips_a_minion_while_another_enemy_lives(policy):
    cs = two_enemies(hp_a=40, hp_b=3, minion_b=True)
    with mock.patch.object(mcts_module, "FOCUS", "lowest_hp_block"):
        assert targets_chosen(policy, cs) == {0}

@pytest.mark.parametrize("policy", WEIGHTED)
def test_focus_leaves_untargeted_cards_and_the_ending_of_the_turn_alone(policy):
    cs = two_enemies(30, 12)
    cs.player.hand = [defend(), strike()]
    sim = CombatSimulator(cs)
    actions = sim.get_available_actions()
    rng.seed(4)
    with mock.patch.object(mcts_module, "FOCUS", "lowest_hp_block"), mock.patch.object(mcts_module, "P_RANDOM_ACTION", 0.0):
        picks = [policy(sim, actions) for _ in range(300)]
    assert any("target_name" not in a for a in picks)                 # Defend still played
    assert {a["target"] for a in picks if "target_name" in a} == {1}

def test_focus_default_is_one_of_the_modes():
    assert mcts_module.FOCUS in ("none", "first", "lowest_hp", "lowest_hp_block")
