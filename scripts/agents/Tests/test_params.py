"""SearchConfig and its parameter groups (agents/sts2_MCTS/params.py)."""
import dataclasses
import json

import pytest

from sts2_lite.card import CardRarity
from sts2_lite.potion import PotionId
from agents.sts2_MCTS.params import (DEFAULT_CONFIG, DEFAULT_HEURISTIC, GROUPS, HeuristicParams, RewardParams, RolloutPolicy, SearchConfig)


def test_tuned_changes_a_field_of_the_config_or_of_a_group():
    c = SearchConfig().tuned(max_sims=500, p_random_action=0.0, win_base=10.0, epsilon=0.01, exploration_scale=60.0)
    assert (c.max_sims, c.heuristic.p_random_action, c.reward.win_base, c.confidence.epsilon, c.uct.exploration_scale) == (500, 0.0, 10.0, 0.01, 60.0)

def test_tuned_leaves_the_original_and_the_other_fields_alone():
    base = SearchConfig()
    c = base.tuned(block_mult=1.0)
    assert base.heuristic.block_mult == 24.0 and c.heuristic.block_mult == 1.0
    assert dataclasses.replace(c, heuristic=base.heuristic) == base

def test_tuned_takes_a_whole_group_too():
    group = RewardParams(win_base=5.0)
    assert SearchConfig().tuned(reward=group).reward is group

def test_tuned_rejects_an_unknown_name():
    with pytest.raises(KeyError):
        SearchConfig().tuned(not_a_parameter=1)

def test_a_group_and_one_of_its_fields_cannot_both_be_given():
    with pytest.raises(ValueError):
        SearchConfig().tuned(reward=RewardParams(), win_base=3.0)

def test_no_two_parameters_share_a_name():
    names = [f.name for f in dataclasses.fields(SearchConfig) if f.name not in GROUPS]
    for group in GROUPS.values():
        names += [f.name for f in dataclasses.fields(group)]
    assert len(names) == len(set(names))

def test_the_config_survives_a_json_round_trip():
    c = SearchConfig(rollout=RolloutPolicy.RarityPreference).tuned(
        block_cap=9, win_base=7.5, exploration_scale=None, rarity_weights={**DEFAULT_HEURISTIC.rarity_weights, CardRarity.Rare: 12})
    d = json.loads(json.dumps(c.to_dict()))
    assert d["rollout"] == "RarityPreference" and d["heuristic"]["rarity_weights"]["Rare"] == 12
    assert SearchConfig.from_dict(d) == c

def test_tables_come_back_keyed_by_enum_members():
    back = SearchConfig.from_dict(json.loads(json.dumps(DEFAULT_CONFIG.to_dict())))
    assert back.reward.potion_bonus[PotionId.AMBERGRIS] == 45 and back.heuristic.rarity_weights[CardRarity.Basic] == 1

def test_the_default_config_matches_the_shipped_values():
    c = SearchConfig()
    assert (c.max_sims, c.min_sims, c.exploration, c.outcome_c, c.outcome_alpha, c.max_rollout_turns) == (20000, 100, 1.0, 2.0, 0.5, 50)
    assert (c.paired_scenarios, c.order_check, c.rollout) == (300, True, RolloutPolicy.ClaudeHeuristic)
    assert (c.reward.win_base, c.reward.default_potion_bonus, c.uct.exploration_power, c.confidence.tie_min_visits) == (20.0, 16, 0.75, 30)

def test_each_group_is_frozen():
    for group in (DEFAULT_CONFIG.reward, DEFAULT_CONFIG.uct, DEFAULT_CONFIG.confidence, DEFAULT_HEURISTIC, DEFAULT_CONFIG):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(group, "anything", 1)
