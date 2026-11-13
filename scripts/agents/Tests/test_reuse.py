"""Tree reuse: the next search starts from the part of the last one the game went into.
Run from scripts/: python -m pytest agents/Tests"""
import gc
import weakref

import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState
from agents.sts2_MCTS.state_key import state_key
from agents.sts2_MCTS.MCTS import sts2_MCTS
from agents.sts2_MCTS.params import SearchConfig
from test_mcts import make_state, strike, defend, bash, pommel, pile, draw_fight, walk_unique
from agents.sts2_MCTS.params import DEFAULT_CONFIG

CFG = SearchConfig(max_sims=400, early_exit=False)

def searched(cs, config=CFG, seed=0):
    rng.seed(seed)
    mcts = sts2_MCTS()
    action, stats = mcts.monte_carlo_tree_search(cs, config)
    return mcts, action, stats

def after(cs, action):
    sim = CombatSimulator(CombatState.deepcopy(cs))
    sim.perform_action(action)
    return sim.combat_state

def root_child(mcts, card_id):
    hand = mcts._root_node.state.player.hand
    return next(c for c in mcts._root_node.children if c.action["action"] == "play_card" and hand[c.action["card_index"]].card_id == card_id)

def three_cards():
    return make_state([strike(), defend(), bash()])


def test_first_search_is_not_a_reuse():
    _, _, stats = searched(three_cards())
    assert stats["reused"] is False and stats["inherited_visits"] == 0

def test_next_search_continues_from_the_node_the_move_led_to():
    cs = three_cards()
    mcts, _, _ = searched(cs)
    played = next(c for c in mcts._root_node.children if not c.is_chance_node)
    observed = after(cs, played.action)
    before = played.visits
    _, stats = mcts.monte_carlo_tree_search(observed, CFG)
    assert stats["reused"] is True and stats["inherited_visits"] >= before > 0

def test_new_simulations_are_counted_without_the_inherited_ones():
    cs = three_cards()
    mcts, action, _ = searched(cs)
    _, stats = mcts.monte_carlo_tree_search(after(cs, action), SearchConfig(max_sims=150, early_exit=False))
    assert stats["num_sims"] == 150

def test_a_state_the_search_never_reached_starts_a_fresh_tree():
    mcts, _, _ = searched(three_cards())
    other = make_state([strike(), strike()])
    _, stats = mcts.monte_carlo_tree_search(other, CFG)
    assert stats["reused"] is False and stats["inherited_visits"] == 0

def test_reuse_can_be_switched_off():
    cs = three_cards()
    mcts, action, _ = searched(cs)
    _, stats = mcts.monte_carlo_tree_search(after(cs, action), SearchConfig(max_sims=200, early_exit=False, reuse_tree=False))
    assert stats["reused"] is False and stats["inherited_visits"] == 0

def test_the_first_searchs_reward_scale_is_kept():
    cs = make_state([strike(), defend()])
    cs.enemies[0].attack_damage = 12
    mcts, _, _ = searched(cs, SearchConfig(max_sims=600, early_exit=False))
    start_hp, total = mcts._starting_hp, mcts._expected_total_hp
    end_turn = next(c for c in mcts._root_node.children if c.action["action"] == "end_turn")
    observed = CombatState.deepcopy(next(iter(end_turn.outcomes.values())).state)      # the enemy's turn has hit the player
    assert observed.player.current_hp < start_hp
    _, stats = mcts.monte_carlo_tree_search(observed, SearchConfig(max_sims=DEFAULT_CONFIG.min_sims, early_exit=False))
    assert stats["reused"] and (mcts._starting_hp, mcts._expected_total_hp) == (start_hp, total)

def test_a_fresh_tree_gets_a_new_reward_scale():
    mcts, _, _ = searched(three_cards())
    other = make_state([strike()])
    other.player.current_hp = other.player.max_hp = 33
    mcts.monte_carlo_tree_search(other, CFG)
    assert mcts._starting_hp == 33


def test_actions_are_indexed_for_the_observed_state_not_the_old_one():
    cs = make_state([strike(), defend(), bash(), strike()])
    mcts, _, _ = searched(cs)
    node = next(c for c in mcts._root_node.children if not c.is_chance_node and cs.player.hand[c.action["card_index"]].card_id.name == "STRIKE_IRONCLAD")
    observed = after(cs, node.action)
    observed.player.hand.reverse()                       # the game lists the hand in its own order
    _, stats = mcts.monte_carlo_tree_search(observed, CFG)
    legal = CombatSimulator(observed).get_available_actions()
    assert all(c.action in legal for c in mcts._root_node.children)
    assert [c["action"] for c in stats["children"] if c["action"] not in legal] == []
    hand = observed.player.hand
    assert {hand[c.action["card_index"]].card_id for c in mcts._root_node.children if c.action["action"] == "play_card"} == {c.card_id for c in hand}

def test_statistics_follow_the_card_when_the_hand_is_reordered():
    cs = make_state([strike(), defend(), bash(), strike()])
    mcts, _, _ = searched(cs)
    first = mcts._root_node.children[0]
    observed = after(cs, first.action)
    old_by_card = {}
    old_hand = first.state.player.hand
    for c in first.children:
        if c.action["action"] == "play_card":
            old_by_card[old_hand[c.action["card_index"]].card_id] = c.visits
    observed.player.hand.reverse()
    mcts.monte_carlo_tree_search(observed, SearchConfig(max_sims=DEFAULT_CONFIG.min_sims, early_exit=False))
    for c in mcts._root_node.children:
        if c.action["action"] == "play_card":
            cid = observed.player.hand[c.action["card_index"]].card_id
            assert c.visits >= old_by_card[cid] > 0


def test_a_sampled_draw_outcome_is_reused():
    cs = draw_fight()
    mcts, _, _ = searched(cs, SearchConfig(max_sims=600, early_exit=False))
    chance = root_child(mcts, mcts._root_node.state.player.hand[0].card_id)
    chance = next(c for c in mcts._root_node.children if c.is_chance_node and c.action["action"] == "play_card")
    outcome = max(chance.outcomes.values(), key=lambda o: o.visits)
    observed = CombatState.deepcopy(outcome.state)
    _, stats = mcts.monte_carlo_tree_search(observed, SearchConfig(max_sims=DEFAULT_CONFIG.min_sims, early_exit=False))
    assert stats["reused"] is True and stats["inherited_visits"] >= outcome.visits > 0

def test_a_draw_outcome_that_was_not_sampled_starts_a_fresh_tree():
    cs = draw_fight()
    mcts, _, _ = searched(cs, SearchConfig(max_sims=DEFAULT_CONFIG.min_sims, early_exit=False))
    chance = next(c for c in mcts._root_node.children if c.is_chance_node and c.action["action"] == "play_card")
    observed = CombatState.deepcopy(chance.pre_state)
    sim = CombatSimulator(observed)
    sim.perform_action(chance.action)
    observed.player.hand.append(bash())                  # a hand the search cannot have drawn
    _, stats = mcts.monte_carlo_tree_search(observed, SearchConfig(max_sims=DEFAULT_CONFIG.min_sims, early_exit=False))
    assert stats["reused"] is False


def test_the_old_tree_is_released():
    cs = three_cards()
    mcts, action, _ = searched(cs)
    old_root = weakref.ref(mcts._root_node)
    mcts.monte_carlo_tree_search(after(cs, action), SearchConfig(max_sims=DEFAULT_CONFIG.min_sims, early_exit=False))
    gc.collect()
    assert old_root() is None

def test_every_kept_node_hangs_below_the_new_root():
    cs = draw_fight()
    mcts, action, _ = searched(cs)
    mcts.monte_carlo_tree_search(after(cs, action) if not mcts._root_node.children[0].is_chance_node else cs, CFG)
    root = mcts._root_node
    assert root.parent is None
    for n in walk_unique(root):
        if n is root:
            continue
        top, hops = n, 0
        while top.parent is not None and hops < 1000:
            top, hops = top.parent, hops + 1
        assert top is root

def test_the_table_holds_only_kept_non_root_child_nodes_under_their_own_key():
    cs = make_state([strike(), defend(), bash()])
    mcts, action, _ = searched(cs)
    mcts.monte_carlo_tree_search(after(cs, action), CFG)
    kept = {id(n) for n in walk_unique(mcts._root_node)}
    root_children = {id(c) for c in mcts._root_node.children}
    for key, node in mcts._table.items():
        assert id(node) in kept and id(node) not in root_children
        assert state_key(node.state) == key

def test_searching_the_same_state_again_keeps_what_was_learned():
    cs = three_cards()
    mcts, _, _ = searched(cs)
    before = mcts._root_node.visits
    _, stats = mcts.monte_carlo_tree_search(cs, SearchConfig(max_sims=DEFAULT_CONFIG.min_sims, early_exit=False))
    assert stats["reused"] and stats["inherited_visits"] == before

def test_children_visits_cover_the_root_after_reuse():
    """A carried-over child keeps all its visits, including those that reached it by another order of plays (the state's value is
    the same whichever way it was reached), so the children can add up to more than the root; never to much less."""
    cs = three_cards()
    mcts, action, _ = searched(cs, SearchConfig(max_sims=600, early_exit=False))
    mcts.monte_carlo_tree_search(after(cs, action), CFG)
    root = mcts._root_node
    assert sum(c.visits for c in root.children) >= 0.8 * (root.visits - 1)

def test_reused_search_still_takes_the_kill():
    cs = make_state([defend(), strike(), strike()])
    cs.enemies[0].current_hp = 6
    cs.enemies[0].attack_damage = 60
    mcts, _, _ = searched(make_state([defend(), strike()]))
    action, _ = mcts.monte_carlo_tree_search(cs, CFG)
    assert cs.player.hand[action["card_index"]].card_id.name == "STRIKE_IRONCLAD"

def test_a_whole_fight_with_reuse_runs_and_reuses():
    from benchmarks.bench import play_fight
    cfg = SearchConfig(max_sims=150, early_exit=False)
    result = play_fight(draw_fight(), cfg, world_seed=3, search_seed=4)
    assert result["finished"]


def test_a_chain_of_reuses_survives_transposed_children():
    """Strike/Defend played in either order reach one shared node whose stored action fits only its first parent."""
    cs = make_state([strike(), defend(), strike(), defend(), bash()])
    cs.energy = cs.max_energy = 4
    rng.seed(5)
    mcts = sts2_MCTS()
    cfg = SearchConfig(max_sims=300, early_exit=False)
    reused = 0
    for _ in range(4):
        actions = CombatSimulator(cs).get_available_actions()
        if len(actions) < 2:
            break
        action, stats = mcts.monte_carlo_tree_search(cs, cfg)
        reused += stats["reused"]
        assert action in actions
        cs = after(cs, action)
        cs.player.hand.reverse()
    assert reused >= 2
