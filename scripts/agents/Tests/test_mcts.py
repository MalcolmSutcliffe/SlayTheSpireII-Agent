"""MCTS tests. Run from scripts/: python -m pytest agents/Tests sts2_lite/Tests"""
import math
import random
import sys
import time
from collections import Counter
from unittest import mock

import pytest

from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatState, CombatSimulator
from sts2_lite.enemy import Enemy
from sts2_lite.enemy_moves import nibbit
from sts2_lite.player import Player
import agents.sts2_MCTS.MCTS as mcts_module
from agents.sts2_MCTS.MCTS import (
    MIN_SIMS, SearchConfig,
    sts2_MCTS, sts2_DeterministicNode, sts2_ChanceNode, expand_node, backpropagate,
    outcome_key, OUTCOME_ALPHA, MAX_ROLLOUT_TURNS,
    RolloutPolicy, ROLLOUT_POLICY_DICT,
)


def new_mcts(config=None):
    """A searcher with a config set, as monte_carlo_tree_search would leave it; for tests that call its internals directly."""
    mcts = sts2_MCTS()
    mcts._search_config = config or SearchConfig()
    return mcts


def primed(state, mcts=None, starting_hp=None):
    """A searcher as monte_carlo_tree_search leaves it at the root: the fight's total enemy HP and the player's starting HP are known."""
    mcts = mcts or new_mcts()
    mcts._expected_total_hp = mcts._calculate_expected_total_hp(state)
    mcts._starting_hp = starting_hp or state.player.current_hp
    mcts._starting_max_hp = state.player.max_hp
    return mcts

@pytest.fixture(autouse=True)
def seeded():
    rng.seed(0)


# ---------------------------------------------------------------- helpers
def make_card(card_id, name, card_type, cost, target):
    c = Card()
    c.card_id, c.name, c.type = card_id, name, card_type
    c.energy_cost, c.target_type = cost, target
    c.is_upgraded = False
    c.is_unplayable = False
    return c

def strike():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def defend():
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.Self)

def pommel():
    return make_card(CardId.POMMEL_STRIKE, "Pommel Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def make_state(hand, draw=(), discard=()):
    p = Player()
    p.max_hp = p.current_hp = 50
    p.hand = list(hand)
    p.draw_pile = list(draw)
    p.discard_pile = list(discard)
    e = Enemy()
    e.max_hp = e.current_hp = 60
    e.enemy_id = "E0"
    e.attack_damage, e.num_attacks = 8, 1
    cs = CombatState()
    cs.player, cs.enemies = p, [e]
    cs.energy = cs.max_energy = 3
    cs.turn_number = 1
    return cs

def expanded(cs):
    root = sts2_DeterministicNode(None, cs, None)
    expand_node(root)
    return root

def child_for(root, name, card_index=None):
    return next(c for c in root.children
                if c.action["action"] == name and c.action.get("card_index") == card_index)


# ---------------------------------------------------------------- expansion types
def test_draw_effect_becomes_a_chance_node():
    root = expanded(make_state([pommel()], draw=[strike(), strike(), defend()]))
    assert isinstance(child_for(root, "play_card", 0), sts2_ChanceNode)

def test_action_without_randomness_stays_deterministic():
    root = expanded(make_state([defend(), strike()], draw=[strike(), strike()]))
    assert isinstance(child_for(root, "play_card", 0), sts2_DeterministicNode)
    assert isinstance(child_for(root, "play_card", 1), sts2_DeterministicNode)

def test_end_turn_with_cards_to_draw_is_a_chance_node():
    root = expanded(make_state([defend()], draw=[strike() for _ in range(6)]))
    assert isinstance(child_for(root, "end_turn"), sts2_ChanceNode)

def test_end_turn_with_nothing_to_draw_is_deterministic():
    root = expanded(make_state([]))
    assert isinstance(child_for(root, "end_turn"), sts2_DeterministicNode)

def test_reshuffle_makes_an_action_a_chance_node():
    root = expanded(make_state([pommel()], draw=[], discard=[strike(), defend()]))
    assert isinstance(child_for(root, "play_card", 0), sts2_ChanceNode)

def test_draw_with_nothing_to_draw_is_deterministic():
    root = expanded(make_state([pommel()], draw=[], discard=[]))
    assert isinstance(child_for(root, "play_card", 0), sts2_DeterministicNode)

def test_every_available_action_gets_a_child():
    cs = make_state([pommel(), defend(), strike()], draw=[strike(), defend()])
    root = expanded(cs)
    assert len(root.children) == 4                  # three cards and end_turn
    assert root.is_expanded

def test_mixed_hand_gives_both_node_types():
    root = expanded(make_state([pommel(), defend()], draw=[strike(), strike(), defend()]))
    kinds = {type(c) for c in root.children}
    assert kinds == {sts2_ChanceNode, sts2_DeterministicNode}


# ---------------------------------------------------------------- what the children hold
def test_chance_node_keeps_the_parents_state_and_action():
    cs = make_state([pommel()], draw=[strike(), strike()])
    root = expanded(cs)
    chance = child_for(root, "play_card", 0)
    assert chance.parent is root
    assert chance.pre_state is root.state
    assert chance.action == {"action": "play_card", "card_index": 0, "target": 0, "target_name": "E0"}
    assert chance.is_chance_node

def test_deterministic_child_has_the_action_applied():
    cs = make_state([defend()], draw=[strike()])
    root = expanded(cs)
    child = child_for(root, "play_card", 0)
    assert child.state.player.block == 5
    assert child.state.energy == 2
    assert not child.is_chance_node

def test_expansion_does_not_modify_the_parent_state():
    cs = make_state([pommel(), defend()], draw=[strike(), strike(), defend()])
    hand, pile, energy, hp = list(cs.player.hand), list(cs.player.draw_pile), cs.energy, cs.player.current_hp
    expand_node(sts2_DeterministicNode(None, cs, None))
    assert cs.player.hand == hand and cs.player.draw_pile == pile
    assert cs.energy == energy and cs.player.current_hp == hp


def test_rng_use_without_a_draw_makes_a_chance_node(monkeypatch):
    from sts2_lite import card as card_module

    def random_defend(card, combat, target_index, is_upgraded=False):
        rng.randrange(2)

    monkeypatch.setitem(card_module.GET_CARD_FUNCTION, CardId.DEFEND_IRONCLAD, random_defend)
    root = expanded(make_state([defend()], draw=[strike()]))
    assert isinstance(child_for(root, "play_card", 0), sts2_ChanceNode)


# ---------------------------------------------------------------- outcome sampling
def bash():
    return make_card(CardId.BASH, "Bash", CardType.Attack, 2, TargetType.AnyEnemy)

def pile():
    return [strike(), strike(), strike(), defend(), bash(), bash()]

def pommel_chance():
    cs = make_state([pommel()], draw=pile())
    root = sts2_DeterministicNode(None, cs, None)
    expand_node(root)
    return root, child_for(root, "play_card", 0)

def walk(node):
    yield node
    kids = node.outcomes.values() if node.is_chance_node else node.children
    for k in kids:
        yield from walk(k)

def walk_unique(root):
    """Every node once: transposed states are one node with several parents."""
    seen, stack = set(), [root]
    while stack:
        n = stack.pop()
        if id(n) in seen:
            continue
        seen.add(id(n))
        yield n
        stack.extend(n.outcomes.values() if n.is_chance_node else n.children)


def test_outcome_key_ignores_card_order():
    a = make_state([strike(), defend()], draw=[bash(), strike()])
    b = make_state([defend(), strike()], draw=[strike(), bash()])
    assert outcome_key(a) == outcome_key(b)

def test_outcome_key_distinguishes_hand_from_pile():
    a = make_state([strike()], draw=[defend()])
    b = make_state([defend()], draw=[strike()])
    assert outcome_key(a) != outcome_key(b)

def with_move(cs, move_id):
    cs.enemies[0].move_id = move_id
    return cs

def test_outcome_key_distinguishes_enemy_moves():
    a = with_move(make_state([strike()]), "BUTT")
    b = with_move(make_state([strike()]), "HISS")
    assert outcome_key(a) != outcome_key(b)

def test_outcome_key_matches_for_equal_enemy_moves():
    a = with_move(make_state([strike()]), "BUTT")
    b = with_move(make_state([strike()]), "BUTT")
    assert outcome_key(a) == outcome_key(b)

def test_random_enemy_moves_become_separate_outcomes(monkeypatch):
    # the cards drawn are identical either way, so only the enemy's next move differs
    def random_move(self, *_):
        self.move_id = rng.choice(["BUTT", "HISS"])
    monkeypatch.setattr(Enemy, "_finish_move", random_move)
    cs = make_state([strike()], draw=[strike()] * 6)
    cs.enemies[0].moves = nibbit(0)
    cs.enemies[0].move_id = "BUTT"
    root = sts2_DeterministicNode(None, cs, None)
    chance = sts2_ChanceNode(root, cs, {"action": "end_turn"})
    chance.visits = 100
    for _ in range(40):
        new_mcts()._sample_outcome(chance)
    assert len(chance.outcomes) == 2

def test_outcome_key_distinguishes_upgrades():
    a = make_state([strike()])
    b = make_state([strike()])
    b.player.hand[0].is_upgraded = True
    assert outcome_key(a) != outcome_key(b)

def test_first_sample_creates_a_deterministic_outcome():
    root, chance = pommel_chance()
    child, is_new = new_mcts()._sample_outcome(chance)
    assert is_new
    assert isinstance(child, sts2_DeterministicNode)
    assert child.parent is chance
    assert child.action == chance.action
    assert len(chance.outcomes) == 1 and chance.outcome_counts[outcome_key(child.state)] == 1

def test_outcome_state_has_the_action_and_draw_applied():
    root, chance = pommel_chance()
    child, _ = new_mcts()._sample_outcome(chance)
    assert len(child.state.player.draw_pile) == len(pile()) - 1
    assert len(child.state.player.hand) == 1
    assert child.state.energy == 2

def test_sampling_does_not_modify_the_pre_state():
    root, chance = pommel_chance()
    before = outcome_key(root.state), root.state.energy
    for i in range(30):
        chance.visits = i
        new_mcts()._sample_outcome(chance)
    assert (outcome_key(root.state), root.state.energy) == before

def test_outcome_distribution_matches_the_pile():
    root, chance = pommel_chance()
    mcts, counts, n = new_mcts(), Counter(), 3000
    for i in range(n):
        chance.visits = i
        child, _ = mcts._sample_outcome(chance)
        counts[child.state.player.hand[0].name] += 1
    assert counts["Strike"] / n == pytest.approx(3 / 6, abs=0.05)
    assert counts["Bash"] / n == pytest.approx(2 / 6, abs=0.05)
    assert counts["Defend"] / n == pytest.approx(1 / 6, abs=0.05)

def test_is_new_only_when_an_outcome_is_created():
    root, chance = pommel_chance()
    mcts, new = new_mcts(), 0
    for i in range(200):
        chance.visits = i
        new += mcts._sample_outcome(chance)[1]
    assert new == len(chance.outcomes)

def test_repeated_outcome_returns_the_same_node():
    root, chance = pommel_chance()
    mcts = new_mcts()
    seen = {}
    for i in range(300):
        chance.visits = 100
        child, _ = mcts._sample_outcome(chance)
        key = outcome_key(child.state)
        assert seen.setdefault(key, child) is child

def test_outcome_count_is_capped():
    root, chance = pommel_chance()
    mcts = new_mcts()
    for _ in range(500):
        chance.visits = 1
        mcts._sample_outcome(chance)
    assert len(chance.outcomes) <= math.ceil(mcts._search_config.outcome_c * 1 ** OUTCOME_ALPHA)

def test_cap_grows_with_visits():
    root, chance = pommel_chance()
    mcts = new_mcts()
    for _ in range(300):
        chance.visits = 100
        mcts._sample_outcome(chance)
    assert len(chance.outcomes) == 3

def test_outcome_counts_add_up_to_the_samples():
    root, chance = pommel_chance()
    mcts = new_mcts()
    for _ in range(200):
        chance.visits = 1
        mcts._sample_outcome(chance)
    assert sum(chance.outcome_counts.values()) == 200
    assert set(chance.outcome_counts) == set(chance.outcomes)

def test_capped_sampling_weights_outcomes_by_their_counts(monkeypatch):
    root, chance = pommel_chance()
    mcts = new_mcts()
    chance.visits = 1                                   # cap of 2
    for _ in range(500):
        if len(chance.outcomes) == 2:
            break
        mcts._sample_outcome(chance)
    assert len(chance.outcomes) == 2
    first = next(iter(chance.outcomes))
    chance.outcome_counts[first] = 7

    seen = []
    real = rng.choices
    def spy(population, weights):
        seen.append((list(population), list(weights)))
        return real(population, weights=weights)
    monkeypatch.setattr(rng, "choices", spy)
    for _ in range(200):
        mcts._sample_outcome(chance)
        if seen:
            break
    keys, weights = seen[0]
    assert dict(zip(keys, weights))[first] >= 7
    assert len(set(weights)) == 2

def test_capped_sampling_follows_observed_frequencies():
    root, chance = pommel_chance()
    mcts = new_mcts()
    for _ in range(3000):
        chance.visits = 1
        mcts._sample_outcome(chance)
    total = sum(chance.outcome_counts.values())
    assert total == 3000
    assert max(chance.outcome_counts.values()) / total > 0.4     # dominant outcome stays dominant


# ---------------------------------------------------------------- traversal and search
def test_traverse_resolves_an_unvisited_chance_child():
    cs = make_state([pommel()], draw=pile())
    root = sts2_DeterministicNode(None, cs, None)
    expand_node(root)
    for c in root.children:                             # leave only the chance child unvisited
        if not c.is_chance_node:
            c.visits = 1
    leaf = new_mcts().traverse_node(root)[-1]
    assert not leaf.is_chance_node
    assert leaf.parent.is_chance_node and leaf.parent.parent is root

def search(cs, sims, seed=0, time_budget=None, early_exit=True):
    """Search capped at `sims` simulations; sim-count mode (no time budget) unless one is given."""
    import contextlib, io
    rng.seed(seed)
    mcts = new_mcts()
    config = SearchConfig(max_sims=sims, time_budget=time_budget, early_exit=early_exit)
    with contextlib.redirect_stdout(io.StringIO()):
        action, _stats = mcts.monte_carlo_tree_search(cs, config)
    return action, mcts

def draw_fight():
    return make_state([pommel(), strike(), defend()], draw=pile() + pile())

def test_search_with_draws_returns_a_legal_action():
    cs = draw_fight()
    action, _ = search(cs, 300)
    assert action in CombatSimulator(cs).get_available_actions()

def test_search_takes_the_kill_with_draws_in_play():
    cs = make_state([defend(), strike()], draw=pile())
    cs.enemies[0].current_hp = 6
    cs.enemies[0].attack_damage = 60
    action, _ = search(cs, 300)
    assert action["action"] == "play_card" and action["card_index"] == 1

def test_search_is_reproducible_from_a_seed():
    a1, _ = search(draw_fight(), 200, seed=5)
    a2, _ = search(draw_fight(), 200, seed=5)
    assert a1 == a2

def test_search_does_not_modify_the_input_state():
    cs = draw_fight()
    before = outcome_key(cs), cs.energy, cs.player.current_hp
    search(cs, 200)
    assert (outcome_key(cs), cs.energy, cs.player.current_hp) == before

def test_tree_contains_both_node_types():
    _, mcts = search(draw_fight(), 300)
    kinds = {n.is_chance_node for n in walk(mcts._root_node)}
    assert kinds == {True, False}

def test_every_simulation_reaches_the_root():
    _, mcts = search(draw_fight(), 250)
    assert mcts._root_node.visits == 250

def test_chance_node_visits_equal_the_sum_of_its_outcomes():
    _, mcts = search(draw_fight(), 400)
    chance_nodes = [n for n in walk(mcts._root_node) if n.is_chance_node]
    assert chance_nodes
    for n in chance_nodes:
        assert n.visits == sum(o.visits for o in n.outcomes.values())

def test_deterministic_node_visits_cover_their_children():
    _, mcts = search(draw_fight(), 400)
    parents = Counter(id(c) for n in walk_unique(mcts._root_node) if not n.is_chance_node for c in n.children)
    for n in walk_unique(mcts._root_node):
        # children that other nodes share carry visits that came through those nodes as well
        if not n.is_chance_node and all(parents[id(c)] == 1 for c in n.children):
            assert n.visits >= sum(c.visits for c in n.children)

def test_outcome_count_stays_under_the_cap_throughout_the_tree():
    _, mcts = search(draw_fight(), 400)
    for n in walk(mcts._root_node):
        if n.is_chance_node:
            assert len(n.outcomes) <= max(1, math.ceil(mcts._search_config.outcome_c * n.visits ** OUTCOME_ALPHA))


# ---------------------------------------------------------------- terminal nodes
def lethal_fight():
    """Low HP: ending the turn without blocking is lethal."""
    cs = make_state([defend(), strike()], draw=pile() + pile())
    cs.player.current_hp = 5
    return cs

def winning_fight():
    cs = make_state([strike(), defend()], draw=pile())
    cs.enemies[0].current_hp = 6
    return cs

def finished(node):
    return CombatSimulator(node.state).is_over

def test_winning_action_is_flagged_terminal():
    root = expanded(winning_fight())
    kill = child_for(root, "play_card", 0)
    assert isinstance(kill, sts2_DeterministicNode)
    assert kill.is_terminal

def test_ordinary_action_is_not_flagged_terminal():
    root = expanded(winning_fight())
    assert not child_for(root, "play_card", 1).is_terminal

def test_chance_nodes_carry_no_terminal_flag():
    root = expanded(lethal_fight())
    chance = child_for(root, "end_turn")
    assert chance.is_chance_node
    assert not hasattr(chance, "is_terminal")

def test_lethal_end_turn_outcome_is_flagged_terminal():
    root = expanded(lethal_fight())
    outcome, _ = new_mcts()._sample_outcome(child_for(root, "end_turn"))
    assert outcome.state.player.current_hp <= 0
    assert outcome.is_terminal

def test_survivable_end_turn_outcome_is_not_flagged_terminal():
    cs = lethal_fight()
    cs.player.current_hp = 50
    root = expanded(cs)
    outcome, _ = new_mcts()._sample_outcome(child_for(root, "end_turn"))
    assert not outcome.is_terminal

def test_every_finished_node_is_flagged_and_none_are_expanded():
    for cs in (lethal_fight(), winning_fight()):
        _, mcts = search(cs, 500)
        nodes = [n for n in walk(mcts._root_node) if not n.is_chance_node]
        done = [n for n in nodes if finished(n)]
        assert done
        assert all(n.is_terminal for n in done)
        assert not any(n.is_expanded for n in done)

def test_flagged_nodes_are_always_finished_combats():
    _, mcts = search(lethal_fight(), 500)
    for n in walk(mcts._root_node):
        if not n.is_chance_node and n.is_terminal:
            assert finished(n)

def test_traversal_returns_a_terminal_node_without_expanding_it():
    root = expanded(winning_fight())
    kill = child_for(root, "play_card", 0)
    kill.visits = 1
    for c in root.children:
        c.visits = max(c.visits, 1)
    mcts = new_mcts()
    mcts._num_sims = 10
    root.visits = 10
    kill.total_reward = 10.0                            # make UCT prefer the kill
    leaf = mcts.traverse_node(root)[-1]
    assert leaf is kill
    assert not kill.is_expanded and kill.children == []

def test_rollout_from_a_terminal_node_returns_its_rating_immediately():
    root = expanded(winning_fight())
    kill = child_for(root, "play_card", 0)
    mcts = primed(kill.state)
    assert mcts._simulate_combat_rollout(kill) == mcts._rate_outcome(kill.state)


# ---------------------------------------------------------------- backpropagation
def chain(length):
    node = sts2_DeterministicNode(None, make_state([]), None)
    nodes = [node]
    for _ in range(length):
        node = sts2_DeterministicNode(node, make_state([]), None)
        nodes.append(node)
    return nodes

def test_backpropagate_updates_every_ancestor():
    nodes = chain(5)
    backpropagate(nodes, 0.5)
    assert all(n.visits == 1 and n.total_reward == 0.5 for n in nodes)

def test_backpropagate_accumulates():
    nodes = chain(3)
    backpropagate(nodes, 1.0)
    backpropagate(nodes[:-1], 2.0)
    assert [n.visits for n in nodes] == [2, 2, 2, 1]
    assert [n.total_reward for n in nodes] == [3.0, 3.0, 3.0, 1.0]

def test_backpropagate_only_touches_the_path():
    nodes = chain(3)
    sibling = sts2_DeterministicNode(nodes[1], make_state([]), None)
    backpropagate(nodes, 1.0)
    assert sibling.visits == 0

def test_backpropagate_of_an_empty_path_does_nothing():
    backpropagate([], 1.0)

def test_backpropagate_has_no_depth_limit():
    nodes = chain(5000)
    assert len(nodes) > sys.getrecursionlimit()
    backpropagate(nodes, 1.0)
    assert nodes[0].visits == 1

def test_search_leaves_the_recursion_limit_alone():
    original = sys.getrecursionlimit()
    sys.setrecursionlimit(777)
    try:
        search(draw_fight(), 150)
        assert sys.getrecursionlimit() == 777
    finally:
        sys.setrecursionlimit(original)


# ---------------------------------------------------------------- search settings
def test_sim_cap_ends_the_search():
    _, mcts = search(draw_fight(), 130, early_exit=False)
    assert mcts._root_node.visits == 130

@pytest.mark.parametrize("budget", [0, 1e-9])
def test_an_exhausted_time_budget_still_runs_the_minimum_sims(budget):
    _, mcts = search(draw_fight(), 5000, time_budget=budget)
    assert mcts._root_node.visits == MIN_SIMS

def test_time_budget_ends_the_search_before_the_sim_cap():
    start = time.perf_counter()
    _, mcts = search(draw_fight(), 10**9, time_budget=0.3)
    elapsed = time.perf_counter() - start
    assert MIN_SIMS <= mcts._root_node.visits < 10**9
    assert 0.3 <= elapsed < 3.0

def test_a_longer_budget_allows_more_sims():
    _, short = search(draw_fight(), 10**9, time_budget=0.1)
    _, long_ = search(draw_fight(), 10**9, time_budget=0.6)
    assert long_._root_node.visits > short._root_node.visits

def test_config_defaults_to_sim_count_mode():
    import inspect
    default = inspect.signature(sts2_MCTS.monte_carlo_tree_search).parameters["config"].default
    assert default == SearchConfig()
    assert default.time_budget is None

def test_search_returns_root_stats_and_exit_reason():
    rng.seed(0)
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        action, stats = sts2_MCTS().monte_carlo_tree_search(draw_fight(), SearchConfig(max_sims=200))
    assert action in [c["action"] for c in stats["children"]]
    assert sum(c["visits"] for c in stats["children"]) == stats["num_sims"] >= MIN_SIMS
    assert stats["exit_reason"] in ("MAX_SIMS", "TIME_BUDGET", "STATISTICAL_CONFIDENCE")
    assert stats["time_taken"] > 0


# ---------------------------------------------------------------- rollouts
def random_fight():
    r = random.Random(1)
    cs = make_state([], draw=[r.choice([strike, defend, bash])() for _ in range(30)])
    sim = CombatSimulator(cs)
    sim.end_turn()
    return sim.combat_state

def test_rollouts_from_one_node_vary():
    node = sts2_DeterministicNode(None, random_fight(), None)
    mcts = primed(node.state)
    results = {round(mcts._simulate_combat_rollout(node), 6) for _ in range(40)}
    assert len(results) > 1

def test_rollout_does_not_modify_the_node_state():
    node = sts2_DeterministicNode(None, random_fight(), None)
    before = (outcome_key(node.state), node.state.player.current_hp,
              node.state.turn_number, [id(c) for c in node.state.player.draw_pile])
    primed(node.state)._simulate_combat_rollout(node)
    assert before == (outcome_key(node.state), node.state.player.current_hp,
                      node.state.turn_number, [id(c) for c in node.state.player.draw_pile])

def test_rollouts_are_reproducible_from_a_seed():
    node = sts2_DeterministicNode(None, random_fight(), None)
    mcts = primed(node.state)
    rng.seed(9)
    a = [mcts._simulate_combat_rollout(node) for _ in range(10)]
    rng.seed(9)
    b = [mcts._simulate_combat_rollout(node) for _ in range(10)]
    assert a == b


# ---------------------------------------------------------------- reward
from agents.sts2_MCTS.MCTS import WIN_BASE, TURN_COST

def win_score(hp, max_hp=80, turns=3, start=None):
    """Score of a win ending at `hp`, for a fight that began at `start` HP (default: full HP)."""
    cs = make_state([])
    cs.player.max_hp, cs.player.current_hp, cs.turn_number = max_hp, hp, turns
    cs.enemies[0].current_hp = 0
    return primed(cs, starting_hp=start or max_hp)._rate_outcome(cs)

def loss_score(enemy_hps, enemy_maxes=None):
    """Score of a loss that ends on turn 0, so the bonus for lasting longer is zero (test_outcome.py covers that bonus)."""
    cs = make_state([])
    cs.player.current_hp = 0
    cs.turn_number = 0
    cs.enemies = []
    for i, hp in enumerate(enemy_hps):
        e = Enemy()
        e.max_hp = (enemy_maxes or [60] * len(enemy_hps))[i]
        e.current_hp = hp
        e.enemy_id = f"E{i}"
        e.attack_damage, e.num_attacks = 0, 0
        cs.enemies.append(e)
    return primed(cs)._rate_outcome(cs)

def test_every_win_scores_above_every_loss():
    wins = [win_score(hp, 100, turns) for hp in (1, 10, 50, 100) for turns in (1, 5, 30, 100, 10_000)]
    losses = [loss_score([hp]) for hp in (1, 5, 30, 60)]
    assert min(wins) > 0 >= max(losses)
    assert min(wins) > max(losses)

def test_a_narrow_slow_win_beats_a_near_win_loss():
    assert win_score(hp=2, max_hp=80, turns=12) > loss_score([1], [90])

def test_wins_are_always_positive():
    assert win_score(1, 1000, 100_000) > 0

def test_a_slow_one_hp_win_still_beats_a_near_win_loss():
    """MAX_ROLLOUT_TURNS-long wins at the edge of death must not rank below losing."""
    assert win_score(1, 80, 50, start=80) > loss_score([1], [90])

def test_losses_are_never_positive():
    assert loss_score([1], [1000]) < 0

def test_more_hp_left_scores_higher():
    assert win_score(60) > win_score(40) > win_score(1)

def test_fewer_turns_scores_higher():
    assert win_score(40, turns=3) > win_score(40, turns=8)

def test_each_turn_costs_a_win_turn_cost_hp():
    assert win_score(40, turns=4) - win_score(40, turns=5) == pytest.approx(TURN_COST / 80)

def test_turn_discount_is_small_next_to_hp():
    one_turn = win_score(40, turns=4) - win_score(40, turns=5)
    assert 0 < one_turn < 0.25 * (win_score(60) - win_score(40))      # 20 HP of 80 outweighs a turn

def test_discounting_keeps_wins_positive_and_above_losses_at_the_rollout_limit():
    from agents.sts2_MCTS.MCTS import MAX_ROLLOUT_TURNS
    assert win_score(1, 80, MAX_ROLLOUT_TURNS) > 0 > loss_score([1], [90])

def test_a_win_without_losing_hp_scores_best():
    assert win_score(80, max_hp=80, turns=0) > win_score(79, max_hp=80, turns=0)

def test_healing_during_the_fight_is_rewarded():
    assert win_score(60, max_hp=80, start=40) > win_score(40, max_hp=80, start=40) > win_score(30, max_hp=80, start=40)

def test_ending_above_the_starting_hp_does_not_fail():
    assert win_score(70, max_hp=80, start=10) > WIN_BASE

def test_hp_is_worth_the_same_wherever_it_is_lost():
    """Linear in remaining HP: 10 HP costs the same near death as at full health."""
    near_death = win_score(20, start=80) - win_score(10, start=80)
    healthy = win_score(80, start=80) - win_score(70, start=80)
    assert near_death == pytest.approx(healthy)

def test_the_same_hp_lost_costs_more_from_a_lower_start():
    assert win_score(20, start=30) < win_score(70, start=80)

def test_less_enemy_health_left_scores_higher_in_a_loss():
    assert loss_score([10]) > loss_score([30]) > loss_score([60])

def test_loss_counts_all_enemies_together():
    assert loss_score([30, 10], [60, 20]) == pytest.approx(-40 / 80)

def test_loss_is_between_minus_one_and_zero():
    assert -1.0 <= loss_score([60]) < 0
    assert loss_score([1]) < 0


# ---------------------------------------------------------------- full fight
def hard_fight(seed):
    """Starter deck vs one 90 HP enemy hitting for 16: a narrow race."""
    rng.seed(seed)
    deck = [strike() for _ in range(5)] + [defend() for _ in range(4)] + [bash()]
    cs = make_state([], draw=deck)
    cs.player.max_hp = cs.player.current_hp = 70
    cs.enemies[0].max_hp = cs.enemies[0].current_hp = 90
    cs.enemies[0].attack_damage = 16
    rng.shuffle(cs.player.draw_pile)
    sim = CombatSimulator(cs)
    sim._start_player_turn()
    n = 0
    while not sim.is_over and sim.combat_state.turn_number <= 30:
        actions = sim.get_available_actions()
        if len(actions) == 1:
            action = actions[0]
        else:
            game_rng = rng.getstate()
            view = CombatState.deepcopy(sim.combat_state)
            random.Random(seed * 100 + n).shuffle(view.player.draw_pile)    # hide the real order
            action, _ = search(view, 300, seed=seed * 100 + n)
            rng.setstate(game_rng)
        sim.perform_action(action)
        n += 1
    return sim

@pytest.mark.parametrize("seed", [0, 1, 2])
def test_agent_wins_the_narrow_race(seed):
    sim = hard_fight(seed)
    assert sim.is_over and sim.combat_state.player.current_hp > 0


# ---------------------------------------------------------------- rollout turn cap
def stalled_fight():
    """Neither side can hurt the other, so the fight never ends on its own."""
    cs = make_state([defend()], draw=[defend()] * 5)
    cs.enemies[0].attack_damage = cs.enemies[0].num_attacks = 0
    return cs

def test_rollout_stops_at_the_turn_cap():
    node = sts2_DeterministicNode(None, stalled_fight(), None)
    primed(node.state)._simulate_combat_rollout(node)  # would hang without the cap

def test_rollout_cap_counts_from_the_starting_turn():
    cs = stalled_fight()
    cs.turn_number = 30
    primed(cs)._simulate_combat_rollout(sts2_DeterministicNode(None, cs, None))

def test_unfinished_rollout_is_not_rated_as_a_win():
    cs = stalled_fight()
    cs.turn_number += MAX_ROLLOUT_TURNS
    assert primed(cs)._rate_outcome(cs) < win_score(1, 80, MAX_ROLLOUT_TURNS)

def test_unfinished_rollout_rates_below_any_win():
    mcts = primed(stalled_fight())
    unfinished = mcts._rate_outcome(stalled_fight())
    won = make_state([])
    won.enemies[0].current_hp = 0
    won.player.current_hp = 1
    won.turn_number = 10_000
    assert unfinished < mcts._rate_outcome(won)

def test_damaged_enemy_rates_better_when_unfinished():
    mcts = primed(stalled_fight())
    hurt = stalled_fight()
    hurt.enemies[0].current_hp = 30
    assert mcts._rate_outcome(hurt) > mcts._rate_outcome(stalled_fight())

def test_search_terminates_on_a_stalled_fight():
    action, _ = sts2_MCTS().monte_carlo_tree_search(stalled_fight(), SearchConfig(max_sims=10**9, time_budget=0.2))
    assert action["action"] in ("play_card", "end_turn")


# ---------------------------------------------------------------- random slime moves
def _twig_m_after_clump():
    from sts2_lite.combat import CombatState
    cs = CombatState.from_dict({
        "round": 2, "energy": 3, "max_energy": 3, "context": {"ascension": 0},
        "player": {"max_hp": 80, "hp": 80, "block": 0, "status": [], "hand": [],
                   "draw_pile": [], "discard_pile": [], "deck": []},
        "enemies": [{"entity_id": "TWIG_SLIME_M_0", "max_hp": 27, "hp": 27, "block": 0, "status": [],
                     "intents": [{"type": "Attack", "label": "11"}]}],
    })
    return cs

def test_end_turn_is_a_chance_node_when_a_slime_picks_randomly():
    from agents.sts2_MCTS.MCTS import expand_node, sts2_DeterministicNode, sts2_ChanceNode
    node = sts2_DeterministicNode(None, _twig_m_after_clump(), None)
    expand_node(node)
    end = next(c for c in node.children if c.action["action"] == "end_turn")
    assert isinstance(end, sts2_ChanceNode)

def test_end_turn_stays_deterministic_when_the_slime_is_forced():
    from agents.sts2_MCTS.MCTS import expand_node, sts2_DeterministicNode, sts2_ChanceNode
    cs = _twig_m_after_clump()
    cs.enemies[0].move_streak = 2
    node = sts2_DeterministicNode(None, cs, None)
    expand_node(node)
    end = next(c for c in node.children if c.action["action"] == "end_turn")
    assert not isinstance(end, sts2_ChanceNode)


# ---------------------------------------------------------------- summoned enemies
def _phrog_state(hp):
    from sts2_lite.Tests import captures
    cs = captures.load("phrog_parasite", "lash")
    cs.enemies[0].current_hp = hp
    return cs

def _strike_at_phrog(node):
    return next(c for c in node.children
                if c.action["action"] == "play_card" and c.action["target"] == 0
                and node.state.player.hand[c.action["card_index"]].card_id.name == "STRIKE_IRONCLAD")

def test_killing_the_phrog_is_a_chance_node_because_wriggler_hp_is_random():
    node = sts2_DeterministicNode(None, _phrog_state(1), None)
    expand_node(node)
    assert isinstance(_strike_at_phrog(node), sts2_ChanceNode)

def test_hitting_the_phrog_without_killing_it_is_deterministic():
    node = sts2_DeterministicNode(None, _phrog_state(50), None)
    expand_node(node)
    assert isinstance(_strike_at_phrog(node), sts2_DeterministicNode)

def test_outcome_key_distinguishes_summoned_enemies():
    a, b = _phrog_state(50), _phrog_state(50)
    from sts2_lite.combat import CombatSimulator
    CombatSimulator(b).summon(Enemy.spawn("WRIGGLER", 0, 0))
    assert outcome_key(a) != outcome_key(b)

def test_outcome_key_distinguishes_different_enemies_with_the_same_move():
    a, b = make_state([strike()]), make_state([strike()])
    a.enemies[0].enemy_id, b.enemies[0].enemy_id = "A_0", "B_0"
    assert outcome_key(a) != outcome_key(b)


# ---------------------------------------------------------------- known cards on top of the draw pile
def known_state(known, draw):
    cs = make_state([draw_card_in_hand()], draw=draw)
    cs.player.known_top = known
    return cs

def draw_card_in_hand():
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 0, TargetType.Self)

def test_ending_the_turn_is_still_a_chance_node_with_no_known_cards():
    cs = known_state(0, [strike() for _ in range(8)])
    assert isinstance(child_for(expanded(cs), "end_turn"), sts2_ChanceNode)

def test_ending_the_turn_with_five_known_cards_is_deterministic():
    cs = known_state(5, [strike() for _ in range(8)])
    assert isinstance(child_for(expanded(cs), "end_turn"), sts2_DeterministicNode)

def test_ending_the_turn_with_four_known_cards_is_still_a_chance_node():
    cs = known_state(4, [strike() for _ in range(8)])
    assert isinstance(child_for(expanded(cs), "end_turn"), sts2_ChanceNode)

def test_sampling_keeps_the_known_top_cards():
    cs = known_state(1, [strike(), strike(), strike(), bash()])
    cs.player.hand = []
    for seed in range(10):
        rng.seed(seed)
        state = CombatState.deepcopy(cs)
        state.player.shuffle_draw_pile()
        assert state.player.draw_pile[-1].card_id == CardId.BASH

def test_outcome_key_tells_known_orders_apart():
    a = known_state(2, [defend(), strike(), bash()])
    b = known_state(2, [defend(), bash(), strike()])
    assert outcome_key(a) != outcome_key(b)

def test_outcome_key_ignores_the_order_of_unknown_cards():
    a = known_state(1, [defend(), strike(), bash()])
    b = known_state(1, [strike(), defend(), bash()])
    assert outcome_key(a) == outcome_key(b)

def test_outcome_key_tells_apart_known_and_unknown():
    a = known_state(1, [defend(), strike(), bash()])
    b = known_state(0, [defend(), strike(), bash()])
    assert outcome_key(a) != outcome_key(b)

def test_sampled_outcomes_never_reshuffle_the_known_top_card():
    for seed in range(10):
        rng.seed(seed)
        cs = known_state(1, [strike() for _ in range(12)] + [bash()])
        cs.player.hand = [draw_card_in_hand()]
        chance = sts2_ChanceNode(None, cs, {"action": "end_turn"})
        child, _ = new_mcts()._sample_outcome(chance)
        assert any(c.card_id == CardId.BASH for c in child.state.player.hand)


# ---------------------------------------------------------------- effective HP (enemies that spawn others)
from agents.sts2_MCTS.MCTS import _effective_hp

def phrog_fight(count=1):
    cs = make_state([])
    cs.enemies = []
    for i in range(count):
        e = Enemy()
        e.max_hp = e.current_hp = 61
        e.enemy_id = f"PHROG_PARASITE_{i}"
        e.attack_damage, e.num_attacks = 0, 0
        cs.enemies.append(e)
    return cs

def wrigglers(hps):
    out = []
    for i, hp in enumerate(hps):
        e = Enemy()
        e.max_hp = e.current_hp = hp
        e.enemy_id = f"WRIGGLER_{i}"
        e.attack_damage, e.num_attacks = 0, 0
        out.append(e)
    return out

def test_phrog_parasite_counts_its_wrigglers_in_the_total():
    assert primed(phrog_fight())._expected_total_hp == 61 + 4 * 19

def test_killing_the_phrog_never_rates_worse():
    """The 4 Wrigglers it leaves behind replace the HP it was carrying: the score is continuous across the kill."""
    root = phrog_fight()
    mcts = primed(root)
    alive, hurt = phrog_fight(), phrog_fight()
    hurt.enemies[0].current_hp = 1
    after_kill = phrog_fight()
    after_kill.enemies = wrigglers([19, 19, 20, 18])
    for cs in (alive, hurt, after_kill):
        cs.player.current_hp = 0
    assert mcts._rate_outcome(alive) < mcts._rate_outcome(hurt) < mcts._rate_outcome(after_kill)

def test_every_phrog_adds_its_own_wrigglers_to_both_sides():
    root = phrog_fight(2)
    mcts = primed(root)
    root.player.current_hp = 0
    root.turn_number = 0        # no bonus for lasting longer
    assert mcts._expected_total_hp == 2 * (61 + 76) and mcts._rate_outcome(root) == -1.0

def test_minions_do_not_count():
    cs = phrog_fight()
    minion = wrigglers([10])[0]
    minion.is_minion = True
    cs.enemies.append(minion)
    assert primed(cs)._expected_total_hp == 61 + 76
    assert _effective_hp(minion) == 0

def test_a_root_without_enemies_does_not_divide_by_zero():
    cs = phrog_fight()
    cs.enemies = []
    cs.player.current_hp = 0
    assert primed(cs)._rate_outcome(cs) <= 0


# ---------------------------------------------------------------- search config
def test_outcome_c_sets_the_outcome_cap():
    for c, expected in ((1.0, 1), (4.0, 3)):                    # pommel draws one of 3 card kinds
        root, chance = pommel_chance()
        mcts = new_mcts(SearchConfig(outcome_c=c))
        for _ in range(300):
            chance.visits = 1
            mcts._sample_outcome(chance)
        assert len(chance.outcomes) == expected

def test_exploration_scales_the_uct_bonus():
    root = sts2_DeterministicNode(None, draw_fight(), None)
    child = sts2_DeterministicNode(root, draw_fight(), None)
    child.visits, child.total_reward = 4, 2.0
    scores = {}
    for c in (0.0, 1.0, 2.0):
        mcts = new_mcts(SearchConfig(exploration=c))
        mcts._num_sims = 100
        scores[c] = mcts.get_uct_score(child)
    assert scores[0.0] == pytest.approx(0.5)
    assert scores[2.0] - scores[0.0] == pytest.approx(2 * (scores[1.0] - scores[0.0]))

@pytest.mark.parametrize("policy", list(RolloutPolicy))
def test_rollouts_use_the_configured_policy(policy):
    calls = Counter()
    spies = {p: (lambda c, actions, p=p, f=f: (calls.update([p]), f(c, actions))[1]) for p, f in ROLLOUT_POLICY_DICT.items()}
    with mock.patch.dict(ROLLOUT_POLICY_DICT, spies):
        mcts = primed(draw_fight(), new_mcts(SearchConfig(rollout=policy)))
        mcts._simulate_combat_rollout(sts2_DeterministicNode(None, draw_fight(), None))
    assert set(calls) == {policy}

def _search_with_exit_forced(early_exit):
    import contextlib, io
    with mock.patch.object(sts2_MCTS, "_check_statistical_exit", lambda self: "BEST"), contextlib.redirect_stdout(io.StringIO()):
        mcts = sts2_MCTS()
        _, stats = mcts.monte_carlo_tree_search(draw_fight(), SearchConfig(max_sims=300, early_exit=early_exit))
    return mcts, stats["exit_reason"]

def test_statistical_exit_stops_the_search_when_enabled():
    mcts, reason = _search_with_exit_forced(early_exit=True)
    assert reason == "STATISTICAL_CONFIDENCE: BEST"
    assert mcts._root_node.visits == MIN_SIMS

def test_disabling_early_exit_runs_to_the_sim_cap():
    mcts, reason = _search_with_exit_forced(early_exit=False)
    assert reason == "MAX_SIMS"
    assert mcts._root_node.visits == 300

def test_an_expired_time_budget_is_reported():
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        _, stats = sts2_MCTS().monte_carlo_tree_search(draw_fight(), SearchConfig(max_sims=10**9, time_budget=0.05, early_exit=False))
    assert stats["exit_reason"] == "TIME_BUDGET"
