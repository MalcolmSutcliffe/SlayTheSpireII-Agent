"""Potions in the search: they are left out of it until the fight looks bad (the gate, PotionParams), then allowed at every turn until one is
used. The scenarios below must hold either way; the old priced mode (`gated=False`: a kept potion is worth `potion_bonus` HP) is still
checked at the end.
Run from scripts/: python -m pytest agents/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.potion import Potion, PotionId
from agents.sts2_MCTS.MCTS import sts2_MCTS, sts2_DeterministicNode, expand_node, backpropagate
from agents.sts2_MCTS.params import SearchConfig, PotionParams
from test_mcts import make_state, strike, defend
from agents.sts2_MCTS.params import DEFAULT_CONFIG
from sts2_lite.combat import CombatSimulator


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

def drinks_this_turn(cs, seed, sims=600, **config):
    """Whether the potion is drunk before the turn ends: the search may play a card first (the rollouts credit drinking later in the turn
    just the same) and drink with the next move."""
    sim = CombatSimulator(cs)
    for step in range(8):
        action = first_move(sim.combat_state, seed + step, sims, **config)
        if drinks(action):
            return True
        if action["action"] == "end_turn" or sim.is_over:
            return False
        sim.perform_action(action)
    return False


# 1. The only way to win is the potion: take it over dying
@pytest.mark.parametrize("seed", range(5))
def test_the_potion_is_used_when_it_is_the_only_way_to_win(seed):
    cs = scenario([strike()], hp=1, enemy_hp=15, damage=8)
    assert drinks_this_turn(cs, seed)

@pytest.mark.parametrize("seed", range(3))
def test_the_potion_is_used_when_it_is_the_only_way_to_win_with_a_full_hand(seed):
    """At 1 HP, against 20 damage the hand cannot block (2 Defends = 10) or outrun (one Strike = 6 of 15 HP): only the potion wins."""
    cs = scenario([strike(), defend(), defend()], hp=1, enemy_hp=15, damage=20)
    assert drinks_this_turn(cs, seed)

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
    assert drinks_this_turn(cs, seed)

@pytest.mark.parametrize("seed", range(3))
def test_the_potion_is_kept_when_it_saves_less_than_it_is_worth(seed):
    """The same fight, but the enemy hits for 8: using the potion saves 8 HP and costs 16."""
    cs = scenario([strike()], draw=[strike() for _ in range(6)], hp=50, enemy_hp=12, damage=8)
    assert not drinks(first_move(cs, seed))


# the bonus itself
PRICED = PotionParams(gated=False)

def rated(cs, potions, priced=False):
    cs.player.potions = [Potion(p, i) for i, p in enumerate(potions)]
    cs.enemies[0].current_hp = 0
    m = sts2_MCTS()
    if priced:
        m._search_config = SearchConfig(potions=PRICED)
    m._starting_hp, m._starting_max_hp, m._expected_total_hp = 50, 50, 60
    return m._rate_outcome(cs)

def test_a_win_with_a_potion_left_scores_higher_than_without():
    base = scenario([strike()], hp=30)
    assert rated(base, [PotionId.FIRE_POTION]) > rated(scenario([strike()], hp=30), [])

def test_every_potion_gets_a_bonus_without_an_error():
    for potion in PotionId:
        rated(scenario([strike()], hp=30), [potion])

def test_the_specific_bonus_beats_the_default_for_a_valued_potion():
    """Priced mode (gated=False) only: gated, every potion is worth the same tie-break."""
    assert rated(scenario([strike()], hp=30), [PotionId.AMBERGRIS], priced=True) > rated(scenario([strike()], hp=30), [PotionId.FIRE_POTION], priced=True)
    assert rated(scenario([strike()], hp=30), [PotionId.AMBERGRIS]) == pytest.approx(rated(scenario([strike()], hp=30), [PotionId.FIRE_POTION]))
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


# ---------------------------------------------------------------- the gate
def search(cs, seed=0, sims=600, mcts=None, **config):
    """(move, stats) of one search of `cs` (a searcher is given to keep its tree and gate between searches)."""
    rng.seed(seed)
    mcts = mcts or sts2_MCTS()
    return mcts.monte_carlo_tree_search(cs, SearchConfig(max_sims=sims, early_exit=False, paired_scenarios=0, **config))

def potion_children(mcts):
    return [c for c in mcts._root_node.children if c.action["action"] == "use_potion"]

def hopeless():
    """At 1 HP against 8 damage with one Strike for a 15 HP enemy, nothing but the potion (20 damage) wins."""
    return scenario([strike()], hp=1, enemy_hp=15, damage=8)

def easy():
    return scenario([strike()], hp=50, enemy_hp=6, damage=8)

def costly():
    """Wins without the potion on turn 2, taking 20 (40% of the 50 max HP); the potion wins at once, keeping all 50."""
    return scenario([strike()], draw=[strike() for _ in range(6)], hp=50, enemy_hp=12, damage=20)


def test_an_easy_fight_never_looks_at_the_potion():
    m = sts2_MCTS()
    move, stats = search(easy(), mcts=m)
    assert stats["gate"]["open"] is False and stats["potions_allowed"] is False
    assert potion_children(m) == [] and not drinks(move)
    assert stats["gate"]["p_win"] == 1.0 and stats["gate"]["hp_loss"] <= 0.0

def test_the_gate_opens_when_the_fight_is_lost_without_the_potion():
    m = sts2_MCTS()
    move, stats = search(hopeless(), mcts=m)
    assert stats["gate"]["open"] and stats["gate"]["p_win"] < DEFAULT_CONFIG.potions.win_threshold
    assert stats["potions_allowed"] and potion_children(m) and drinks(move)

def test_the_gate_opens_when_a_sure_win_costs_too_much_hp():
    m = sts2_MCTS()
    move, stats = search(costly(), mcts=m)
    assert stats["gate"]["p_win"] > DEFAULT_CONFIG.potions.win_threshold       # it wins, so it is the HP that opens the gate
    assert stats["gate"]["hp_loss"] > stats["gate"]["hp_loss_limit"] == pytest.approx(DEFAULT_CONFIG.potions.hp_loss_fraction * 50)
    assert stats["gate"]["open"] and drinks(move)

def test_the_gate_stays_closed_when_the_loss_is_below_the_limit():
    """The enemy hits for 8: 8 HP is 16% of the max HP, under the 35% limit, so the potion is not considered."""
    m = sts2_MCTS()
    cs = scenario([strike()], draw=[strike() for _ in range(6)], hp=50, enemy_hp=12, damage=8)
    move, stats = search(cs, mcts=m)
    assert stats["gate"]["open"] is False and potion_children(m) == [] and not drinks(move)

def test_the_thresholds_are_the_configs():
    """The same fight with a lower win threshold and a bigger HP allowance does not open the gate."""
    relaxed = PotionParams(win_threshold=0.0, hp_loss_fraction=10.0)
    m = sts2_MCTS()
    move, stats = search(hopeless(), mcts=m, potions=relaxed)
    assert stats["gate"]["open"] is False and not drinks(move)

def test_the_potions_are_always_allowed_in_the_last_fight():
    cs = easy()
    cs.final_fight = True
    m = sts2_MCTS()
    _, stats = search(cs, mcts=m)
    assert stats["potions_allowed"] and stats["gate"] is None and potion_children(m)

def test_without_the_gate_the_potions_are_always_allowed():
    m = sts2_MCTS()
    _, stats = search(easy(), mcts=m, potions=PRICED)
    assert stats["potions_allowed"] and stats["gate"] is None and potion_children(m)

def test_no_potions_held_means_no_gate():
    cs = easy()
    cs.player.potions = []
    _, stats = search(cs)
    assert stats["gate"] is None


# the gate stays open until a potion is used
def test_once_open_the_gate_stays_open_for_the_next_search():
    m = sts2_MCTS()
    search(hopeless(), mcts=m)
    assert m._latch is not None
    _, stats = search(hopeless(), seed=1, mcts=m)
    assert stats["potions_allowed"] and stats["gate"] is None          # not tested again
    assert stats["reused"]                                              # the tree with potion moves is kept

def test_the_gate_closes_again_when_a_potion_is_used():
    m = sts2_MCTS()
    search(scenario([strike()], hp=1, enemy_hp=15, damage=8, potions=(PotionId.FIRE_POTION, PotionId.BLOCK_POTION)), mcts=m)
    assert m._latch is not None
    # the Fire Potion (slot 0) was drunk: the next state holds only the Block Potion, and the fight is no longer bad
    after = scenario([strike()], hp=50, enemy_hp=6, damage=8, potions=(PotionId.FIRE_POTION, PotionId.BLOCK_POTION))
    after.player.potions = [p for p in after.player.potions if p.slot != 0]
    _, stats = search(after, mcts=m)
    assert m._latch is None
    assert stats["gate"] is not None and stats["gate"]["open"] is False and stats["potions_allowed"] is False

def test_the_gate_can_open_again_for_the_next_potion():
    m = sts2_MCTS()
    both = (PotionId.FIRE_POTION, PotionId.BLOCK_POTION)
    search(scenario([strike()], hp=1, enemy_hp=15, damage=8, potions=both), mcts=m)
    after = scenario([strike()], hp=1, enemy_hp=15, damage=8, potions=both)
    after.player.potions = [p for p in after.player.potions if p.slot != 0]
    _, stats = search(after, mcts=m)
    assert stats["gate"]["open"] and stats["potions_allowed"] and m._latch == frozenset({(1, PotionId.BLOCK_POTION)})

def test_a_new_fight_starts_with_the_gate_closed():
    m = sts2_MCTS()
    search(hopeless(), mcts=m)
    assert m._latch is not None
    other = easy()
    other.enemies[0].enemy_id = "E1"
    _, stats = search(other, mcts=m)
    assert m._latch is None and stats["gate"] is not None and not stats["gate"]["open"]

def test_going_back_to_an_earlier_turn_is_a_new_fight():
    m = sts2_MCTS()
    late = hopeless()
    late.turn_number = 5
    search(late, mcts=m)
    assert m._latch is not None
    _, stats = search(easy(), mcts=m)           # turn 1, the same enemy kind
    assert stats["gate"] is not None and not stats["gate"]["open"]

def test_a_tree_built_for_the_other_setting_is_not_reused():
    """After the gate closes, the old tree (with potion moves in it) is dropped: the next search must not play them."""
    m = sts2_MCTS()
    both = (PotionId.FIRE_POTION, PotionId.BLOCK_POTION)
    search(scenario([strike()], hp=1, enemy_hp=15, damage=8, potions=both), mcts=m)
    after = scenario([strike()], hp=50, enemy_hp=6, damage=8, potions=both)
    after.player.potions = after.player.potions[1:]
    _, stats = search(after, mcts=m)
    assert not stats["reused"] and potion_children(m) == []


# the pieces
def test_expanding_without_potions_leaves_the_potion_moves_out():
    cs = scenario([strike(), defend()], potions=(PotionId.FIRE_POTION, PotionId.BLOCK_POTION))
    with_potions, without = sts2_DeterministicNode(None, cs, None), sts2_DeterministicNode(None, scenario([strike(), defend()], potions=(PotionId.FIRE_POTION, PotionId.BLOCK_POTION)), None)
    expand_node(with_potions)
    expand_node(without, None, False)
    assert sum(c.action["action"] == "use_potion" for c in with_potions.children) == 2
    assert [c.action for c in without.children if c.action["action"] == "use_potion"] == []
    assert len(without.children) == len(with_potions.children) - 2

def test_backpropagation_counts_wins_and_the_hp_they_ended_with():
    a, b = sts2_DeterministicNode(None, easy(), None), sts2_DeterministicNode(None, easy(), None)
    backpropagate([a, b], 1.0, None, True, 42.0)
    backpropagate([a, b], -0.5, None, False, 0.0)
    assert (a.visits, a.wins, a.hp_sum) == (2, 1, 42.0) and (b.visits, b.wins, b.hp_sum) == (2, 1, 42.0)
    backpropagate([a], 1.0)                                              # without the outcome the statistics stay as they are
    assert (a.wins, a.hp_sum) == (1, 42.0)

def test_the_root_knows_how_often_the_fight_was_won():
    m = sts2_MCTS()
    search(easy(), mcts=m)
    root = m._root_node
    assert root.wins == root.visits > 0
    assert 0.95 * 50 * root.visits < root.hp_sum <= 50 * root.visits       # a few rollouts end the turn first and take a hit
    m = sts2_MCTS()
    search(hopeless(), mcts=m, potions=PRICED, sims=300)
    root = m._root_node
    assert 0 < root.wins < root.visits                                  # the potion wins it, the rest lose

def test_a_reused_root_keeps_the_win_statistics():
    m = sts2_MCTS()
    search(easy(), mcts=m)
    first = m._root_node.wins
    search(easy(), seed=1, mcts=m)
    assert m._root_node.wins >= first > 0 and m._root_node.wins == m._root_node.visits


# the old priced mode, for comparison
@pytest.mark.parametrize("seed", range(4))
def test_priced_the_potion_is_kept_when_it_saves_less_than_it_is_worth(seed):
    cs = scenario([strike()], draw=[strike() for _ in range(6)], hp=50, enemy_hp=12, damage=8)
    assert not drinks(first_move(cs, seed, potions=PRICED))

@pytest.mark.parametrize("seed", range(4))
def test_priced_the_potion_is_used_when_it_saves_more_hp_than_it_is_worth(seed):
    assert drinks_this_turn(costly(), seed, potions=PRICED)
