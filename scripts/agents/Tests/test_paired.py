"""Paired comparison of the root moves. Run from scripts/: python -m pytest agents/Tests"""
import math

import pytest

from sts2_lite import rng
from agents.sts2_MCTS.MCTS import sts2_MCTS, sts2_DeterministicNode, expand_node
from agents.sts2_MCTS.params import SearchConfig
import agents.sts2_MCTS.MCTS as mcts_module
from test_mcts import make_state, strike, defend, new_mcts, primed, child_for


def block_choice():
    """One energy, a Defend and a Defend+ in hand; Strikes to draw next turn against a weak enemy that hits for 8.
    Playing Defend+ is better by 3 HP in every scenario."""
    plus = defend().upgraded_copy()
    cs = make_state([defend(), plus], draw=[strike() for _ in range(6)])
    cs.energy = cs.max_energy = 1
    cs.enemies[0].max_hp = cs.enemies[0].current_hp = 12
    return cs

def root_with_visits(cs, config, visits=200):
    mcts = primed(cs, new_mcts(config))
    root = sts2_DeterministicNode(None, cs, None)
    expand_node(root)
    for c in root.children:
        c.visits = visits
    mcts._root_node = root
    return mcts, root

def test_a_better_rival_replaces_the_picked_move():
    mcts, root = root_with_visits(block_choice(), SearchConfig(paired_scenarios=60))
    plain, plus = child_for(root, "play_card", 0), child_for(root, "play_card", 1)
    result = mcts._paired_check(plain)
    assert result["replaced"] and result["child"] is plus
    gain = next(c for c in result["compared"] if c["action"] is plus.action)
    assert gain["gain"] > 0

def test_the_better_move_is_kept():
    mcts, root = root_with_visits(block_choice(), SearchConfig(paired_scenarios=60))
    plus = child_for(root, "play_card", 1)
    result = mcts._paired_check(plus)
    assert not result["replaced"] and result["child"] is plus

def test_a_rival_with_too_few_visits_is_not_compared():
    mcts, root = root_with_visits(block_choice(), SearchConfig(paired_scenarios=60))
    plain, plus = child_for(root, "play_card", 0), child_for(root, "play_card", 1)
    plus.visits = 1
    for c in root.children:
        if c is not plain and c is not plus:
            c.visits = 1
    assert mcts._paired_check(plain) is None

def test_nothing_to_compare_with_one_move():
    cs = block_choice()
    cs.energy = 0
    mcts, root = root_with_visits(cs, SearchConfig(paired_scenarios=60))
    assert mcts._paired_check(root.children[0]) is None

def test_the_search_random_stream_is_left_as_if_only_the_scenario_seeds_were_drawn():
    n = 40
    rng.seed(7)
    for _ in range(n):
        rng.randrange(1 << 30)
    expected = rng.random_float()
    rng.seed(7)
    mcts, root = root_with_visits(block_choice(), SearchConfig(paired_scenarios=n))
    mcts._paired_check(child_for(root, "play_card", 0))
    assert rng.random_float() == expected

def test_the_input_state_is_not_changed():
    cs = block_choice()
    before = (cs.player.current_hp, cs.energy, len(cs.player.hand), len(cs.player.draw_pile), cs.enemies[0].current_hp)
    mcts, root = root_with_visits(cs, SearchConfig(paired_scenarios=30))
    mcts._paired_check(child_for(root, "play_card", 0))
    assert before == (cs.player.current_hp, cs.energy, len(cs.player.hand), len(cs.player.draw_pile), cs.enemies[0].current_hp)

def test_the_full_search_picks_the_better_block_and_reports_it():
    """Exploration is set to 1.0 so the Defend keeps enough visits to be compared: at the default of 0.5 the search puts ~99% of its
    visits on the Defend+ here and has no rival for the paired check to look at (see the next test)."""
    for seed in range(5):
        rng.seed(seed)
        action, stats = sts2_MCTS().monte_carlo_tree_search(block_choice(), SearchConfig(max_sims=300, reuse_tree=False, exploration=1.0))
        assert action["card_index"] == 1
        assert stats["paired"]["scenarios"] == SearchConfig().paired_scenarios
        assert "child" not in stats["paired"]

def test_a_search_that_is_sure_of_its_move_has_no_rival_to_compare():
    """With nothing but a sliver of visits on the other moves (under PAIRED_VISIT_FRACTION) the paired check has nothing to do.
    (Built on the tree: at an exploration this low a full search locks onto whichever move got ahead first, so which move it ends on,
    and whether another gets a few visits, depends on luck and on the rollout policy.)"""
    mcts, root = root_with_visits(block_choice(), SearchConfig(paired_scenarios=60), visits=1)
    plus = child_for(root, "play_card", 1)
    plus.visits = 300
    assert mcts._paired_check(plus) is None

def test_off_means_no_paired_stats():
    _, stats = sts2_MCTS().monte_carlo_tree_search(block_choice(), SearchConfig(max_sims=200, paired_scenarios=0, reuse_tree=False))
    assert stats["paired"] is None

def test_identical_moves_are_not_replaced():
    cs = make_state([strike(), strike()])
    cs.energy = cs.max_energy = 1
    mcts, root = root_with_visits(cs, SearchConfig(paired_scenarios=60))
    first = child_for(root, "play_card", 0)
    result = mcts._paired_check(first)
    assert result is None or not result["replaced"]


def test_a_refused_potion_falls_back_to_the_trees_favourite_not_the_best_noisy_mean():
    from types import SimpleNamespace as N
    from agents.sts2_MCTS.paired_check import PairedCheck
    potion = N(action={"action": "use_potion"}, visits=3000)
    favourite = N(action={"action": "play_card"}, visits=2500)
    end = N(action={"action": "end_turn"}, visits=240)
    mcts = N(_root_node=N(children=[potion, favourite, end]))
    noise = [(-1) ** i * 0.5 for i in range(40)]
    # end_turn is a hair ahead of the favourite on average, but the paired difference is all noise
    diffs = [[-0.30 + x for x in noise], [-0.29 + x for x in noise][::-1]]
    results = [(favourite, -0.30, 0.1, 40), (end, -0.29, 0.1, 40)]
    check = PairedCheck(mcts)
    best = check._fallback(results, results, diffs, [favourite, end], potion)
    assert best[0] is favourite

def test_a_refused_potion_gives_way_to_a_plain_line_clearly_ahead_of_the_favourite():
    from types import SimpleNamespace as N
    from agents.sts2_MCTS.paired_check import PairedCheck
    potion = N(action={"action": "use_potion"}, visits=3000)
    favourite = N(action={"action": "play_card"}, visits=2500)
    other = N(action={"action": "play_card"}, visits=900)
    mcts = N(_root_node=N(children=[potion, favourite, other]))
    diffs = [[-1.0 + 0.01 * (i % 3) for i in range(40)], [-0.5 + 0.01 * (i % 3) for i in range(40)]]
    results = [(favourite, -1.0, 0.0, 40), (other, -0.5, 0.0, 40)]
    best = PairedCheck(mcts)._fallback(results, results, diffs, [favourite, other], potion)
    assert best[0] is other


def test_a_refused_potion_beats_nothing_when_the_picked_plain_move_is_clearly_ahead_of_the_favourite():
    from types import SimpleNamespace as N
    from agents.sts2_MCTS.paired_check import PairedCheck
    potion = N(action={"action": "use_potion"}, visits=300)
    picked = N(action={"action": "play_card"}, visits=900)
    favourite = N(action={"action": "play_card"}, visits=2500)          # the tree's favourite is not the move the check began with
    mcts = N(_root_node=N(children=[potion, picked, favourite]))
    diffs = [[-1.0 + 0.01 * (i % 3) for i in range(40)], [0.5 for _ in range(40)]]          # rivals: the favourite (below the picked move), the potion
    results = [(favourite, -1.0, 0.0, 40), (potion, 0.5, 0.0, 40)]
    plain = [(picked, 0.0, 0.0, 40), results[0]]
    best = PairedCheck(mcts)._fallback(plain, results, diffs, [favourite, potion], picked)
    assert best[0] is picked


def test_a_card_choice_whose_cards_are_gone_does_not_crash_the_action_list():
    from sts2_lite.combat import CombatSimulator, PendingChoice
    cs = make_state([strike()])
    cs.pending_choice = PendingChoice("upgrade", [3], "hand")
    actions = CombatSimulator(cs).get_available_actions()
    assert cs.pending_choice is None and all(a["action"] != "choose_card" for a in actions) and actions
