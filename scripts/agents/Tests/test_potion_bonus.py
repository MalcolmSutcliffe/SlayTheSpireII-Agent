"""The potion bonus in the combat score: potions are kept when they are not needed and used when they win or save more than they are worth.
Run from scripts/: python -m pytest agents/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.potion import Potion, PotionId
from agents.sts2_MCTS.MCTS import sts2_MCTS
from agents.sts2_MCTS.params import SearchConfig
from test_mcts import make_state, strike, defend
from agents.sts2_MCTS.params import DEFAULT_CONFIG


def scenario(hand, draw=(), hp=50, enemy_hp=60, damage=8, potions=(PotionId.FIRE_POTION,)):
    cs = make_state(hand, draw=draw)
    cs.player.current_hp = hp
    cs.player.potions = [Potion(p, i) for i, p in enumerate(potions)]
    enemy = cs.enemies[0]
    enemy.current_hp = enemy.max_hp = enemy_hp
    enemy.attack_damage, enemy.num_attacks = damage, 1
    return cs

def first_move(cs, seed, sims=600, **config):
    rng.seed(seed)
    action, _ = sts2_MCTS().monte_carlo_tree_search(cs, SearchConfig(max_sims=sims, early_exit=False, **config))
    return action

def drinks(action):
    return action["action"] == "use_potion"


# 1. The only way to win is the potion: take it over dying
@pytest.mark.parametrize("seed", range(5))
def test_the_potion_is_used_when_it_is_the_only_way_to_win(seed):
    cs = scenario([strike()], hp=1, enemy_hp=15, damage=8)
    assert drinks(first_move(cs, seed))

@pytest.mark.parametrize("seed", range(3))
def test_the_potion_is_used_when_it_is_the_only_way_to_win_with_a_full_hand(seed):
    """At 1 HP, against 20 damage the hand cannot block (2 Defends = 10) or outrun (one Strike = 6 of 15 HP): only the potion wins."""
    cs = scenario([strike(), defend(), defend()], hp=1, enemy_hp=15, damage=20)
    assert drinks(first_move(cs, seed))

@pytest.mark.parametrize("seed", range(5))
def test_the_potion_is_kept_when_blocking_wins_without_it(seed):
    """The same hand against 8 damage: Defend, Defend, Strike every turn takes 3 turns and loses no HP, so the potion (worth 16 HP) stays.
    Taking it would be a sure win, but a win with the potion kept is worth more, even at 1 HP."""
    cs = scenario([strike(), defend(), defend()], hp=1, enemy_hp=15, damage=8)
    assert not drinks(first_move(cs, seed))


# 2. A win without the potion: keep it, every time
@pytest.mark.parametrize("seed", range(8))
def test_the_potion_is_kept_when_the_fight_is_won_without_it(seed):
    cs = scenario([strike()], hp=50, enemy_hp=6, damage=8)
    action = first_move(cs, seed)
    assert action["action"] == "play_card"

@pytest.mark.parametrize("seed", range(4))
def test_the_potion_is_kept_over_a_long_but_safe_win(seed):
    """Two turns of Strikes beat a weak enemy, taking 8 once: a 20-damage potion is not worth 16 HP here."""
    cs = scenario([strike(), strike()], draw=[strike(), strike(), strike()], hp=50, enemy_hp=18, damage=2)
    assert not drinks(first_move(cs, seed))


# 3. The potion saves 20 HP (worth more than the 16 it costs) against winning a turn later
@pytest.mark.parametrize("seed", range(5))
def test_the_potion_is_used_when_it_saves_more_hp_than_it_is_worth(seed):
    cs = scenario([strike()], draw=[strike() for _ in range(6)], hp=50, enemy_hp=12, damage=20)
    assert drinks(first_move(cs, seed))

@pytest.mark.parametrize("seed", range(3))
def test_the_potion_is_kept_when_it_saves_less_than_it_is_worth(seed):
    """The same fight, but the enemy hits for 8: using the potion saves 8 HP and costs 16."""
    cs = scenario([strike()], draw=[strike() for _ in range(6)], hp=50, enemy_hp=12, damage=8)
    assert not drinks(first_move(cs, seed))


# the bonus itself
def rated(cs, potions):
    cs.player.potions = [Potion(p, i) for i, p in enumerate(potions)]
    cs.enemies[0].current_hp = 0
    m = sts2_MCTS()
    m._starting_hp, m._starting_max_hp, m._expected_total_hp = 50, 50, 60
    return m._rate_outcome(cs)

def test_a_win_with_a_potion_left_scores_higher_than_without():
    base = scenario([strike()], hp=30)
    assert rated(base, [PotionId.FIRE_POTION]) > rated(scenario([strike()], hp=30), [])

def test_every_potion_gets_a_bonus_without_an_error():
    for potion in PotionId:
        rated(scenario([strike()], hp=30), [potion])

def test_the_specific_bonus_beats_the_default_for_a_valued_potion():
    assert rated(scenario([strike()], hp=30), [PotionId.AMBERGRIS]) > rated(scenario([strike()], hp=30), [PotionId.FIRE_POTION])
    assert DEFAULT_CONFIG.reward.default_potion_bonus == 16


# rollouts never drink potions
from agents.sts2_MCTS.rollout_policy import ROLLOUT_POLICY_DICT, rollout_policy
from agents.sts2_MCTS.params import RolloutPolicy
from sts2_lite.combat import CombatSimulator

@pytest.mark.parametrize("policy", list(RolloutPolicy))
def test_no_rollout_policy_uses_a_potion(policy):
    for seed in range(40):
        rng.seed(seed)
        c = CombatSimulator(scenario([strike(), defend()], potions=(PotionId.FIRE_POTION, PotionId.BLOCK_POTION, PotionId.ENERGY_POTION)))
        assert any(a["action"] == "use_potion" for a in c.get_available_actions())
        assert rollout_policy(c, c.get_available_actions(), policy)["action"] != "use_potion"

def test_a_rollout_with_nothing_but_potions_and_end_turn_ends_the_turn():
    c = CombatSimulator(scenario([], potions=(PotionId.FIRE_POTION,)))
    assert rollout_policy(c, c.get_available_actions(), RolloutPolicy.FirstAction)["action"] == "end_turn"

def test_a_whole_rollout_keeps_the_potions():
    cs = scenario([strike(), defend()], draw=[strike() for _ in range(8)], hp=50, enemy_hp=200, damage=3,
                  potions=(PotionId.FIRE_POTION, PotionId.BLOCK_POTION))
    rng.seed(1)
    m = sts2_MCTS(); m._search_config = SearchConfig(); m._starting_hp, m._starting_max_hp, m._expected_total_hp = 50, 50, 200
    from agents.sts2_MCTS.MCTS import sts2_DeterministicNode
    seen = []
    original = m._rate_outcome
    m._rate_outcome = lambda state: (seen.append(len(state.player.potions)), original(state))[1]
    m._simulate_combat_rollout(sts2_DeterministicNode(None, cs, None))
    assert seen == [2]


# max HP gained in the fight (Feed, Fruit Juice) counts MAX_HP_SCALING HP per point on a win

def rated_with_max_hp(gain, hp=30):
    cs = scenario([strike()], hp=hp)
    cs.player.max_hp = 50 + gain
    cs.enemies[0].current_hp = 0
    m = sts2_MCTS()
    m._starting_hp, m._starting_max_hp, m._expected_total_hp = 40, 50, 60
    return m._rate_outcome(cs)

def test_a_win_that_raised_max_hp_scores_higher():
    assert rated_with_max_hp(0) < rated_with_max_hp(3) < rated_with_max_hp(6)

def test_each_max_hp_point_is_worth_as_much_as_that_many_hp_points():
    """+3 max HP (times MAX_HP_SCALING) matches ending with that much more HP."""
    assert rated_with_max_hp(3, hp=30) == pytest.approx(rated_with_max_hp(0, hp=30 + DEFAULT_CONFIG.reward.max_hp_scaling * 3))

def test_max_hp_does_not_matter_in_a_loss():
    cs = scenario([strike()], hp=0)
    cs.player.max_hp = 56
    m = sts2_MCTS()
    m._starting_hp, m._starting_max_hp, m._expected_total_hp = 40, 50, 60
    plain = scenario([strike()], hp=0)
    assert m._rate_outcome(cs) == m._rate_outcome(plain)
