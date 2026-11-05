"""MCTS tests. Run from scripts/: python -m pytest agents/Tests sts2_lite/Tests"""
import math
import random
import sys
from collections import Counter

import pytest

from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatState, CombatSimulator
from sts2_lite.enemy import Enemy
from sts2_lite.enemy_moves import nibbit
from sts2_lite.player import Player
from agents.MCTS import (
    sts2_MCTS, sts2_DeterministicNode, sts2_ChanceNode, expand_node, backpropagate,
    outcome_key, OUTCOME_C, OUTCOME_ALPHA, MAX_ROLLOUT_TURNS,
)


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
    cs.deck = []
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
    def random_move(self):
        self.move_id = rng.choice(["BUTT", "HISS"])
    monkeypatch.setattr(Enemy, "_finish_move", random_move)
    cs = make_state([strike()], draw=[strike()] * 6)
    cs.enemies[0].moves = nibbit(0)
    cs.enemies[0].move_id = "BUTT"
    root = sts2_DeterministicNode(None, cs, None)
    chance = sts2_ChanceNode(root, cs, {"action": "end_turn"})
    chance.visits = 100
    for _ in range(40):
        sts2_MCTS()._sample_outcome(chance)
    assert len(chance.outcomes) == 2

def test_outcome_key_distinguishes_upgrades():
    a = make_state([strike()])
    b = make_state([strike()])
    b.player.hand[0].is_upgraded = True
    assert outcome_key(a) != outcome_key(b)

def test_first_sample_creates_a_deterministic_outcome():
    root, chance = pommel_chance()
    child, is_new = sts2_MCTS()._sample_outcome(chance)
    assert is_new
    assert isinstance(child, sts2_DeterministicNode)
    assert child.parent is chance
    assert child.action == chance.action
    assert len(chance.outcomes) == 1 and chance.outcome_counts[outcome_key(child.state)] == 1

def test_outcome_state_has_the_action_and_draw_applied():
    root, chance = pommel_chance()
    child, _ = sts2_MCTS()._sample_outcome(chance)
    assert len(child.state.player.draw_pile) == len(pile()) - 1
    assert len(child.state.player.hand) == 1
    assert child.state.energy == 2

def test_sampling_does_not_modify_the_pre_state():
    root, chance = pommel_chance()
    before = outcome_key(root.state), root.state.energy
    for i in range(30):
        chance.visits = i
        sts2_MCTS()._sample_outcome(chance)
    assert (outcome_key(root.state), root.state.energy) == before

def test_outcome_distribution_matches_the_pile():
    root, chance = pommel_chance()
    mcts, counts, n = sts2_MCTS(), Counter(), 3000
    for i in range(n):
        chance.visits = i
        child, _ = mcts._sample_outcome(chance)
        counts[child.state.player.hand[0].name] += 1
    assert counts["Strike"] / n == pytest.approx(3 / 6, abs=0.05)
    assert counts["Bash"] / n == pytest.approx(2 / 6, abs=0.05)
    assert counts["Defend"] / n == pytest.approx(1 / 6, abs=0.05)

def test_is_new_only_when_an_outcome_is_created():
    root, chance = pommel_chance()
    mcts, new = sts2_MCTS(), 0
    for i in range(200):
        chance.visits = i
        new += mcts._sample_outcome(chance)[1]
    assert new == len(chance.outcomes)

def test_repeated_outcome_returns_the_same_node():
    root, chance = pommel_chance()
    mcts = sts2_MCTS()
    seen = {}
    for i in range(300):
        chance.visits = 100
        child, _ = mcts._sample_outcome(chance)
        key = outcome_key(child.state)
        assert seen.setdefault(key, child) is child

def test_outcome_count_is_capped():
    root, chance = pommel_chance()
    mcts = sts2_MCTS()
    for _ in range(500):
        chance.visits = 1
        mcts._sample_outcome(chance)
    assert len(chance.outcomes) <= math.ceil(OUTCOME_C * 1 ** OUTCOME_ALPHA)

def test_cap_grows_with_visits():
    root, chance = pommel_chance()
    mcts = sts2_MCTS()
    for _ in range(300):
        chance.visits = 100
        mcts._sample_outcome(chance)
    assert len(chance.outcomes) == 3

def test_outcome_counts_add_up_to_the_samples():
    root, chance = pommel_chance()
    mcts = sts2_MCTS()
    for _ in range(200):
        chance.visits = 1
        mcts._sample_outcome(chance)
    assert sum(chance.outcome_counts.values()) == 200
    assert set(chance.outcome_counts) == set(chance.outcomes)

def test_capped_sampling_weights_outcomes_by_their_counts(monkeypatch):
    root, chance = pommel_chance()
    mcts = sts2_MCTS()
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
    mcts = sts2_MCTS()
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
    leaf = sts2_MCTS().traverse_node(root)
    assert not leaf.is_chance_node
    assert leaf.parent.is_chance_node and leaf.parent.parent is root

def search(cs, sims, seed=0):
    import contextlib, io
    rng.seed(seed)
    mcts = sts2_MCTS()
    with contextlib.redirect_stdout(io.StringIO()):
        action = mcts.monte_carlo_tree_search(cs, sims)
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
    for n in walk(mcts._root_node):
        if not n.is_chance_node:
            assert n.visits >= sum(c.visits for c in n.children)

def test_outcome_count_stays_under_the_cap_throughout_the_tree():
    _, mcts = search(draw_fight(), 400)
    for n in walk(mcts._root_node):
        if n.is_chance_node:
            assert len(n.outcomes) <= max(1, math.ceil(OUTCOME_C * n.visits ** OUTCOME_ALPHA))


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
    outcome, _ = sts2_MCTS()._sample_outcome(child_for(root, "end_turn"))
    assert outcome.state.player.current_hp <= 0
    assert outcome.is_terminal

def test_survivable_end_turn_outcome_is_not_flagged_terminal():
    cs = lethal_fight()
    cs.player.current_hp = 50
    root = expanded(cs)
    outcome, _ = sts2_MCTS()._sample_outcome(child_for(root, "end_turn"))
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
    mcts = sts2_MCTS()
    mcts._num_sims = 10
    root.visits = 10
    kill.total_reward = 10.0                            # make UCT prefer the kill
    leaf = mcts.traverse_node(root)
    assert leaf is kill
    assert not kill.is_expanded and kill.children == []

def test_rollout_from_a_terminal_node_returns_its_rating_immediately():
    root = expanded(winning_fight())
    kill = child_for(root, "play_card", 0)
    mcts = sts2_MCTS()
    assert mcts._simulate_random_combat(kill) == mcts._rate_outcome(kill.state)


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
    backpropagate(nodes[-1], 0.5)
    assert all(n.visits == 1 and n.total_reward == 0.5 for n in nodes)

def test_backpropagate_accumulates():
    nodes = chain(3)
    backpropagate(nodes[-1], 1.0)
    backpropagate(nodes[-2], 2.0)
    assert [n.visits for n in nodes] == [2, 2, 2, 1]
    assert [n.total_reward for n in nodes] == [3.0, 3.0, 3.0, 1.0]

def test_backpropagate_only_touches_the_path():
    nodes = chain(3)
    sibling = sts2_DeterministicNode(nodes[1], make_state([]), None)
    backpropagate(nodes[-1], 1.0)
    assert sibling.visits == 0

def test_backpropagate_handles_none():
    backpropagate(None, 1.0)

def test_backpropagate_has_no_depth_limit():
    nodes = chain(5000)
    assert len(nodes) > sys.getrecursionlimit()
    backpropagate(nodes[-1], 1.0)
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
@pytest.mark.parametrize("requested", [0, 1, 3, 99])
def test_small_max_sims_is_raised_to_the_minimum(requested):
    _, mcts = search(draw_fight(), requested)
    assert mcts._root_node.visits == 100

def test_larger_max_sims_is_respected():
    _, mcts = search(draw_fight(), 130)
    assert mcts._root_node.visits == 130


# ---------------------------------------------------------------- rollouts
def random_fight():
    r = random.Random(1)
    cs = make_state([], draw=[r.choice([strike, defend, bash])() for _ in range(30)])
    sim = CombatSimulator(cs)
    sim.end_turn()
    return sim.combat_state

def test_rollouts_from_one_node_vary():
    node = sts2_DeterministicNode(None, random_fight(), None)
    mcts = sts2_MCTS()
    results = {round(mcts._simulate_random_combat(node), 6) for _ in range(40)}
    assert len(results) > 1

def test_rollout_does_not_modify_the_node_state():
    node = sts2_DeterministicNode(None, random_fight(), None)
    before = (outcome_key(node.state), node.state.player.current_hp,
              node.state.turn_number, [id(c) for c in node.state.player.draw_pile])
    sts2_MCTS()._simulate_random_combat(node)
    assert before == (outcome_key(node.state), node.state.player.current_hp,
                      node.state.turn_number, [id(c) for c in node.state.player.draw_pile])

def test_rollouts_are_reproducible_from_a_seed():
    node = sts2_DeterministicNode(None, random_fight(), None)
    mcts = sts2_MCTS()
    rng.seed(9)
    a = [mcts._simulate_random_combat(node) for _ in range(10)]
    rng.seed(9)
    b = [mcts._simulate_random_combat(node) for _ in range(10)]
    assert a == b


# ---------------------------------------------------------------- reward
from agents.MCTS import TURN_DECAY_CONSTANT, WIN_BONUS

def win_score(hp, max_hp=80, turns=3):
    cs = make_state([])
    cs.player.max_hp, cs.player.current_hp, cs.turn_number = max_hp, hp, turns
    cs.enemies[0].current_hp = 0
    return sts2_MCTS()._rate_outcome(cs)

def loss_score(enemy_hps, enemy_maxes=None):
    cs = make_state([])
    cs.player.current_hp = 0
    cs.enemies = []
    for i, hp in enumerate(enemy_hps):
        e = Enemy()
        e.max_hp = (enemy_maxes or [60] * len(enemy_hps))[i]
        e.current_hp = hp
        e.enemy_id = f"E{i}"
        e.attack_damage, e.num_attacks = 0, 0
        cs.enemies.append(e)
    return sts2_MCTS()._rate_outcome(cs)

def test_every_win_scores_above_every_loss():
    wins = [win_score(hp, 100, turns) for hp in (1, 10, 50, 100) for turns in (1, 5, 30, 100, 10_000)]
    losses = [loss_score([hp]) for hp in (1, 5, 30, 60)]
    assert min(wins) > 0 >= max(losses)
    assert min(wins) > max(losses)

def test_a_narrow_slow_win_beats_a_near_win_loss():
    assert win_score(hp=2, max_hp=80, turns=12) > loss_score([1], [90])

def test_wins_are_always_positive():
    assert win_score(1, 1000, 100_000) > 0

def test_losses_are_never_positive():
    assert loss_score([1], [1000]) < 0

def test_more_hp_left_scores_higher():
    assert win_score(60) > win_score(40) > win_score(1)

def test_fewer_turns_scores_higher():
    assert win_score(40, turns=3) > win_score(40, turns=8)

def test_turn_penalty_is_small_next_to_hp():
    one_turn = win_score(40, turns=4) - win_score(40, turns=5)
    assert one_turn == pytest.approx(TURN_DECAY_CONSTANT)
    assert one_turn < 0.25 * (win_score(60) - win_score(40))      # 20 HP of 80 outweighs a turn

def test_win_score_has_the_expected_form():
    assert win_score(40, max_hp=80, turns=5) == pytest.approx(WIN_BONUS + 0.5 - 5 * TURN_DECAY_CONSTANT)

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
    cs.deck = list(deck)
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
    sts2_MCTS()._simulate_random_combat(node)  # would hang without the cap

def test_rollout_cap_counts_from_the_starting_turn():
    cs = stalled_fight()
    cs.turn_number = 30
    sts2_MCTS()._simulate_random_combat(sts2_DeterministicNode(None, cs, None))

def test_unfinished_rollout_is_not_rated_as_a_win():
    cs = stalled_fight()
    cs.turn_number += MAX_ROLLOUT_TURNS
    assert sts2_MCTS()._rate_outcome(cs) <= 0

def test_unfinished_rollout_rates_below_any_win():
    mcts = sts2_MCTS()
    unfinished = mcts._rate_outcome(stalled_fight())
    won = make_state([])
    won.enemies[0].current_hp = 0
    won.player.current_hp = 1
    won.turn_number = 10_000
    assert unfinished < mcts._rate_outcome(won)

def test_damaged_enemy_rates_better_when_unfinished():
    mcts = sts2_MCTS()
    hurt = stalled_fight()
    hurt.enemies[0].current_hp = 30
    assert mcts._rate_outcome(hurt) > mcts._rate_outcome(stalled_fight())

def test_search_terminates_on_a_stalled_fight():
    action = sts2_MCTS().monte_carlo_tree_search(stalled_fight(), 100)
    assert action["action"] in ("play_card", "end_turn")
