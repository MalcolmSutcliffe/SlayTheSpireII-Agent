"""Potions used strategically: rollouts drink in danger, a potion move must beat every non-potion line, a held potion is worth something in a line not won."""
import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator
from sts2_lite.potion import Potion, PotionId
from agents.sts2_MCTS.MCTS import sts2_MCTS, sts2_DeterministicNode, expand_node
from agents.sts2_MCTS.params import SearchConfig, PotionParams, RolloutPolicy
from agents.sts2_MCTS.rollout_policy import rollout_policy
from test_mcts import make_state, strike, defend, new_mcts, primed, child_for
from test_potion_bonus import scenario


def sim(hp, damage, **kw):
    return CombatSimulator(scenario([], hp=hp, damage=damage, **kw))

def test_a_rollout_drinks_when_the_turn_ends_in_danger():
    c = sim(40, 25)
    assert rollout_policy(c, c.get_available_actions(), RolloutPolicy.FirstAction, None, 0.3)["action"] == "use_potion"

def test_a_rollout_keeps_the_potion_when_the_danger_is_small():
    c = sim(40, 5)
    assert rollout_policy(c, c.get_available_actions(), RolloutPolicy.FirstAction, None, 0.3)["action"] == "end_turn"

def test_block_counts_against_the_danger():
    c = sim(40, 25)
    c.combat_state.player.block = 20
    assert rollout_policy(c, c.get_available_actions(), RolloutPolicy.FirstAction, None, 0.3)["action"] == "end_turn"

def test_a_rollout_never_drinks_without_a_danger_level():
    c = sim(40, 25)
    assert rollout_policy(c, c.get_available_actions(), RolloutPolicy.FirstAction)["action"] == "end_turn"

def test_a_rollout_plays_a_card_before_it_drinks():
    c = CombatSimulator(scenario([strike()], hp=40, damage=25))
    assert rollout_policy(c, c.get_available_actions(), RolloutPolicy.FirstAction, None, 0.3)["action"] == "play_card"

def test_the_rollouts_drink_only_while_the_tree_has_potions():
    m = sts2_MCTS(); m._search_config = SearchConfig()
    m._potions_on = True
    assert m._rollout_danger() == PotionParams().rollout_danger
    m._potions_on = False
    assert m._rollout_danger() is None
    m._potions_on = True; m._search_config = SearchConfig(potions=PotionParams(rollout_use=False))
    assert m._rollout_danger() is None


def rated(potions, alive=True, final=False):
    cs = scenario([], potions=potions)
    cs.final_fight = final
    cs.player.current_hp = 30 if alive else 0
    m = sts2_MCTS(); m._search_config = SearchConfig()
    m._starting_hp, m._starting_max_hp, m._expected_total_hp = 50, 50, 60
    return m._rate_outcome(cs)

def test_a_held_potion_raises_a_line_that_is_not_won():
    assert rated((PotionId.FIRE_POTION, PotionId.BLOCK_POTION)) > rated((PotionId.FIRE_POTION,)) > rated(())

def test_a_dead_player_gains_nothing_for_a_potion():
    assert rated((PotionId.FIRE_POTION,), alive=False) == rated((), alive=False)

def test_the_last_fight_gives_no_hold_value():
    assert rated((PotionId.FIRE_POTION,), final=True) == rated((), final=True)


# the paired check: a potion move has to earn its place
def root_for(cs, config, visits=200):
    mcts = primed(cs, new_mcts(config))
    root = sts2_DeterministicNode(None, cs, None)
    expand_node(root)
    for c in root.children:
        c.visits = visits
    mcts._root_node = root
    return mcts, root

def potion_child(root):
    return next(c for c in root.children if c.action["action"] == "use_potion")

def test_a_potion_that_gains_nothing_is_replaced_by_the_best_other_move():
    # a weak enemy and plenty of HP: every line wins, the potion changes nothing
    cs = scenario([strike(), defend()], draw=[strike() for _ in range(6)], hp=70, enemy_hp=6, damage=2, potions=(PotionId.BLOCK_POTION,))
    mcts, root = root_for(cs, SearchConfig(paired_scenarios=60, check_workers=1))
    result = mcts._paired_check(potion_child(root))
    assert result["replaced"] and result["child"].action["action"] != "use_potion"

def test_a_potion_the_other_lines_cannot_match_is_kept():
    # three Strikes (18) kill the enemy but only one energy, and the rollouts do not drink (rollout_use off): the Energy Potion is the only way to win
    cs = scenario([strike(), strike(), strike()], hp=5, enemy_hp=18, damage=14, potions=(PotionId.ENERGY_POTION,))
    cs.energy = cs.max_energy = 1
    mcts, root = root_for(cs, SearchConfig(paired_scenarios=60, check_workers=1, potions=PotionParams(rollout_use=False)))
    result = mcts._paired_check(potion_child(root))
    assert not result["replaced"]

def test_a_potion_whose_later_use_is_as_good_is_not_played_first():
    # with the rollouts drinking, Strike then (end of turn) the Energy Potion wins just the same: the Strike is played
    cs = scenario([strike(), strike(), strike()], hp=5, enemy_hp=18, damage=14, potions=(PotionId.ENERGY_POTION,))
    cs.energy = cs.max_energy = 1
    mcts, root = root_for(cs, SearchConfig(paired_scenarios=60, check_workers=1))
    result = mcts._paired_check(potion_child(root))
    assert result["replaced"] and result["child"].action["action"] == "play_card"

def test_a_potion_that_can_wait_for_the_end_of_the_turn_is_not_played_first():
    # holding the Block Potion and drinking it after the Strike is as good as drinking it first: the Strike comes first
    cs = scenario([strike()], draw=[strike() for _ in range(6)], hp=9, enemy_hp=12, damage=14, potions=(PotionId.BLOCK_POTION,))
    cs.energy = cs.max_energy = 1
    mcts, root = root_for(cs, SearchConfig(paired_scenarios=60, check_workers=1))
    result = mcts._paired_check(potion_child(root))
    assert result["replaced"] and result["child"].action["action"] == "play_card"


def test_a_potion_pick_is_checked_against_a_search_of_the_plain_moves():
    cs = scenario([strike(), defend()], hp=40, damage=10)
    cs.enemies[0].max_hp = cs.enemies[0].current_hp = 6        # one Strike wins the fight
    config = SearchConfig(time_budget=None, max_sims=200, min_sims=50, early_exit=False)
    mcts = primed(cs, new_mcts(config))
    root = sts2_DeterministicNode(None, CombatState_copy(cs), None)
    expand_node(root)
    mcts._root_node, mcts._table, mcts._tree_potions, mcts._potions_on = root, {}, True, True
    potion = next(c for c in root.children if c.action["action"] == "use_potion")
    potion.visits, potion.total_reward = 1000, 0.1 * 1000                      # a potion line the tree rates far below winning
    found = mcts._plain_check(cs, potion.action)
    assert found["replaced"] and found["action"]["action"] != "use_potion" and found["plain_q"] > found["potion_q"]
    assert mcts._root_node is root and mcts._potions_on is True and mcts._tree_potions is True        # the potion tree is put back
    potion.total_reward = 1000 * 100.0                                         # ... and one it rates far above any plain move
    assert not mcts._plain_check(cs, potion.action)["replaced"]

def CombatState_copy(cs):
    from sts2_lite.combat import CombatState
    return CombatState.deepcopy(cs)
