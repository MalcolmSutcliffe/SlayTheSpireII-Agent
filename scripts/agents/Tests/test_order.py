from __future__ import annotations
"""The order of the turn's plain plays (sts2_MCTS._order_check). Run from scripts/: python -m pytest agents/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.card import CardId, CardType, TargetType
from sts2_lite.potion import Potion, PotionId
import agents.sts2_MCTS.MCTS as mcts_module
from sts2_lite.combat import CombatSimulator
from agents.sts2_MCTS.MCTS import SearchConfig, RolloutPolicy, sts2_MCTS, sts2_DeterministicNode, expand_node
from test_mcts import make_state, make_card, strike, defend, bash, new_mcts, primed

SCENARIOS = 60
CONFIG = SearchConfig(paired_scenarios=SCENARIOS, rollout=RolloutPolicy.ClaudeHeuristicGreedy)


def matches(node, child, want):
    a = child.action
    if want == "potion":
        return a["action"] == "use_potion"
    if want == "end_turn":
        return a["action"] == "end_turn"
    if isinstance(want, tuple):                         # ("choice", CardId): the card a pending choice takes
        return a["action"] == "choose_card" and a["card_id"] == want[1].name
    return a["action"] == "play_card" and node.state.player.hand[a["card_index"]].card_id == want

def tree_with_line(cs, line, config=CONFIG):
    """A searcher whose most visited line is `line` (a CardId, "potion", ("choice", CardId) or "end_turn" per step). Returns it with the root move."""
    mcts = primed(cs, new_mcts(config))
    root = sts2_DeterministicNode(None, cs, None)
    expand_node(root)
    mcts._root_node = root
    for c in root.children:
        c.visits = 1
    node, first = root, None
    for want in line:
        child = next(c for c in node.children if matches(node, c, want))
        child.visits = 100
        first = first or child
        if not child.is_chance_node and not child.is_terminal:
            expand_node(child)
            for k in child.children:
                k.visits = 1
        node = child
    return mcts, first

def dexterity_turn(hand=None, energy=1):
    """Dexterity makes the Defend 7 block instead of 5 against an 8 damage attack: 2 HP, only if it is drunk first."""
    cs = make_state(hand or [defend()], draw=[strike() for _ in range(6)])
    cs.player.potions = [Potion(PotionId.DEXTERITY_POTION, 0)]
    cs.energy = cs.max_energy = energy
    return cs

def true_grit_plus():
    card = make_card(CardId.TRUE_GRIT, "True Grit", CardType.Skill, 1, TargetType.Self)
    card.is_upgraded = True
    return card


# 1. The order the tree chose is replaced when another is ahead
def test_the_potion_is_drunk_before_the_block():
    mcts, first = tree_with_line(dexterity_turn(), [CardId.DEFEND_IRONCLAD, "potion", "end_turn"])
    result = mcts._order_check(first)
    assert result["replaced"] and result["action"]["action"] == "use_potion"
    assert result["compared"][0]["gain"] > 0

def test_vulnerable_is_played_before_the_attack():
    """Strike 6 + Bash 8 leaves 3 of 17; Bash first makes the Strike 9 and kills."""
    cs = make_state([strike(), bash()], draw=[strike() for _ in range(6)])
    cs.enemies[0].current_hp = cs.enemies[0].max_hp = 17
    mcts, first = tree_with_line(cs, [CardId.STRIKE_IRONCLAD, CardId.BASH, "end_turn"])
    result = mcts._order_check(first)
    assert result["replaced"]
    assert cs.player.hand[result["action"]["card_index"]].card_id == CardId.BASH

def test_a_play_and_its_card_choice_move_together():
    cs = dexterity_turn([true_grit_plus(), defend(), strike()], energy=3)
    cs.enemies[0].attack_damage = 30                     # more than the 14 block, so every point of Dexterity counts
    cs.enemies[0].current_hp = cs.enemies[0].max_hp = 12 # two Strikes next turn win it: a loss is scored without the player's HP, so the order shows only in a win
    mcts, first = tree_with_line(cs, [CardId.TRUE_GRIT, ("choice", CardId.STRIKE_IRONCLAD), CardId.DEFEND_IRONCLAD, "potion", "end_turn"])
    result = mcts._order_check(first)
    assert result["distinct"] >= 3                       # the potion can go first, between or last, with the card choice kept with True Grit
    assert result["replaced"] and result["action"]["action"] == "use_potion"


# 2. The order the tree chose is kept when it is the best, or when there is nothing to compare
def test_the_best_order_is_kept():
    mcts, first = tree_with_line(dexterity_turn(), ["potion", CardId.DEFEND_IRONCLAD, "end_turn"])
    result = mcts._order_check(first)
    assert not result["replaced"] and result["action"]["action"] == "use_potion"
    assert all(c["gain"] < 0 for c in result["compared"])

def test_orders_that_end_in_the_same_state_are_not_compared():
    cs = make_state([strike(), defend()], draw=[strike() for _ in range(6)])
    mcts, first = tree_with_line(cs, [CardId.STRIKE_IRONCLAD, CardId.DEFEND_IRONCLAD, "end_turn"])
    assert mcts._order_check(first) is None

def test_one_play_has_no_order():
    mcts, first = tree_with_line(dexterity_turn(), ["potion", "end_turn"])
    assert mcts._order_check(first) is None

def test_a_random_first_play_is_left_alone():
    cs = make_state([make_card(CardId.POMMEL_STRIKE, "Pommel Strike", CardType.Attack, 1, TargetType.AnyEnemy), defend()],
                    draw=[strike() for _ in range(6)])
    mcts, first = tree_with_line(cs, [CardId.POMMEL_STRIKE])
    assert first.is_chance_node
    assert mcts._order_check(first) is None

def test_a_line_with_too_many_plays_keeps_the_trees_order(monkeypatch):
    monkeypatch.setattr(mcts_module, "ORDER_MAX_UNITS", 1)
    mcts, first = tree_with_line(dexterity_turn(), [CardId.DEFEND_IRONCLAD, "potion", "end_turn"])
    assert mcts._order_check(first) is None

def test_a_pending_card_choice_is_not_reordered():
    cs = dexterity_turn([true_grit_plus(), defend(), strike()], energy=3)         # two cards to choose from: with one the sim picks it
    mcts, first = tree_with_line(cs, [CardId.TRUE_GRIT])
    mcts._root_node = first                     # the search is now at the choice True Grit asked for
    assert first.state.pending_choice is not None
    assert mcts._order_check(next(iter(first.children))) is None


# 3. The search around it
def test_the_search_random_stream_is_left_as_if_only_the_scenario_seeds_were_drawn():
    mcts, first = tree_with_line(dexterity_turn(), [CardId.DEFEND_IRONCLAD, "potion", "end_turn"])
    rng.seed(7)
    mcts._order_check(first)
    after = rng.getstate()
    rng.seed(7)
    for _ in range(SCENARIOS):
        rng.randrange(1 << 30)
    assert rng.getstate() == after

def test_a_search_reports_the_order_check_and_the_switch_turns_it_off():
    for on in (True, False):
        rng.seed(3)
        _, stats = sts2_MCTS().monte_carlo_tree_search(
            dexterity_turn(), SearchConfig(max_sims=300, early_exit=False, paired_scenarios=SCENARIOS, order_check=on,
                                           rollout=RolloutPolicy.ClaudeHeuristicGreedy))
        assert ("order" in stats) and (stats["order"] is None or on)
        if not on:
            assert stats["order"] is None

def test_an_error_in_the_order_check_keeps_the_trees_pick(monkeypatch):
    def broken(self, picked):
        raise RuntimeError("boom")
    monkeypatch.setattr(sts2_MCTS, "_order_check", broken)
    rng.seed(3)
    action, stats = sts2_MCTS().monte_carlo_tree_search(
        dexterity_turn(), SearchConfig(max_sims=300, early_exit=False, paired_scenarios=SCENARIOS,
                                       rollout=RolloutPolicy.ClaudeHeuristicGreedy))
    assert action is not None and "boom" in stats["order"]["error"] and not stats["order"]["replaced"]


# 4. The draw goes first when that costs nothing (and the plain plays stay before it when they matter)
def pillage():
    return make_card(CardId.PILLAGE, "Pillage", CardType.Attack, 1, TargetType.AnyEnemy)

def bludgeon():
    return make_card(CardId.BLUDGEON, "Bludgeon", CardType.Attack, 3, TargetType.AnyEnemy)

def inflame():
    return make_card(CardId.INFLAME, "Inflame", CardType.Power, 1, TargetType.Self)

def bash_pillage_bludgeon():
    """4 energy, Bash (2) and Pillage (1) in hand, the draw pile only Bludgeon (3) and the enemy at 38: Pillage draws the Bludgeon and
    6 + 32 kills. Bash first leaves 1 energy, too little for the Bludgeon."""
    cs = make_state([bash(), pillage()], draw=[bludgeon()])
    cs.energy = cs.max_energy = 4
    cs.enemies[0].current_hp = cs.enemies[0].max_hp = 38
    return cs

def play_of(cs, action):
    return cs.player.hand[action["card_index"]].card_id

@pytest.mark.parametrize("seed", range(3))
def test_a_search_plays_pillage_then_bludgeon(seed):
    """The tree finds this one itself: after the draw the Bludgeon wins. (The order check could not: its rollouts play Bash after the draw.)"""
    cs = bash_pillage_bludgeon()
    config = SearchConfig(max_sims=600, early_exit=False, paired_scenarios=SCENARIOS, rollout=RolloutPolicy.ClaudeHeuristicGreedy)
    rng.seed(seed)
    mcts = sts2_MCTS()
    action, _ = mcts.monte_carlo_tree_search(cs, config)
    assert play_of(cs, action) == CardId.PILLAGE
    sim = CombatSimulator(cs)
    sim.perform_action(action)                                 # the Bludgeon is in hand
    assert CardId.BLUDGEON in [c.card_id for c in sim.combat_state.player.hand]
    action, _ = mcts.monte_carlo_tree_search(sim.combat_state, config)
    assert sim.combat_state.player.hand[action["card_index"]].card_id == CardId.BLUDGEON
    sim.perform_action(action)
    assert sim.is_over and sim.combat_state.player.current_hp > 0                  # the Bludgeon killed it

def tied_draw_turn():
    """Defend and Pillage use both energy, so what Pillage draws cannot be played this turn: before or after, the turn is the same."""
    cs = make_state([defend(), pillage()], draw=[defend(), defend(), defend()] + [strike() for _ in range(8)])
    cs.energy = cs.max_energy = 2
    cs.enemies[0].current_hp = cs.enemies[0].max_hp = 12
    return cs

def test_a_draw_that_changes_nothing_is_played_first():
    cs = tied_draw_turn()
    mcts, first = tree_with_line(cs, [CardId.DEFEND_IRONCLAD, CardId.PILLAGE])
    result = mcts._order_check(first)
    assert result["replaced"] and result["draws_first"]
    assert play_of(cs, result["action"]) == CardId.PILLAGE
    assert all(abs(c["gain"]) < mcts_module.TIE_MARGIN for c in result["compared"])           # every order is the same turn

def test_strength_stays_before_the_draw_that_hits():
    """Inflame before Pillage deals 8, which kills the enemy at 8; Pillage first deals 6 and the Inflame is wasted."""
    cs = make_state([inflame(), pillage()], draw=[defend(), defend()])
    cs.energy = cs.max_energy = 2
    cs.enemies[0].current_hp = cs.enemies[0].max_hp = 8
    mcts, first = tree_with_line(cs, [CardId.INFLAME, CardId.PILLAGE])
    result = mcts._order_check(first)
    assert result is None or not result["replaced"]
    drawing = [c for c in (result or {}).get("compared", []) if c["draws_first"]]
    assert all(c["gain"] < 0 for c in drawing)                  # drawing first is worse, so it is not tied with the tree's order

def test_the_better_order_wins_over_a_tied_draw_that_keeps_the_worse_one():
    """Dexterity first is 2 HP better than Defend first; of the orders that draw first, only the one with the potion first keeps that."""
    cs = make_state([defend(), pillage()], draw=[defend(), defend(), defend()] + [strike() for _ in range(8)])
    cs.player.potions = [Potion(PotionId.DEXTERITY_POTION, 0)]
    cs.energy = cs.max_energy = 2
    cs.enemies[0].current_hp = cs.enemies[0].max_hp = 12
    mcts, first = tree_with_line(cs, [CardId.DEFEND_IRONCLAD, "potion", CardId.PILLAGE])
    result = mcts._order_check(first)
    assert result["replaced"] and result["draws_first"]
    assert play_of(cs, result["action"]) == CardId.PILLAGE
    drawing = sorted(c["gain"] for c in result["compared"] if c["draws_first"])
    assert drawing[0] < drawing[-1]                             # the draw with the Defend before the potion is behind the one with it after

def test_a_line_ending_the_turn_has_no_draw_to_move():
    cs = make_state([defend(), strike()], draw=[strike() for _ in range(6)])
    mcts, first = tree_with_line(cs, [CardId.DEFEND_IRONCLAD, CardId.STRIKE_IRONCLAD, "end_turn"])
    assert mcts._order_check(first) is None                     # the same end state either way, and ending the turn first is no option

def test_a_draw_the_hand_cannot_take_first_is_not_tried_when_the_play_is_not_there():
    cs = make_state([pillage()], draw=[defend(), defend()])
    cs.energy = cs.max_energy = 1
    mcts, first = tree_with_line(cs, [CardId.PILLAGE])
    assert first.is_chance_node and mcts._order_check(first) is None


def bash_pillage_bludgeon_or_defend():
    """The same turn, with a Defend under the Bludgeon in the draw pile. Pillage draws until a non-Attack: the Bludgeon comes into the hand
    only when it is on top (half the time), and then it wins on the spot, 6 + 32 against 38. Bash first is worth 3 more damage for sure."""
    cs = bash_pillage_bludgeon()
    cs.player.draw_pile = [bludgeon(), defend()]
    return cs

@pytest.mark.parametrize("seed", range(3))
def test_a_half_chance_of_the_bludgeon_outweighs_three_damage_for_sure(seed):
    """Bash first deals 17 and leaves 21; Pillage first deals 6 and has a half chance of the Bludgeon, which kills."""
    cs = bash_pillage_bludgeon_or_defend()
    config = SearchConfig(max_sims=1000, early_exit=False, paired_scenarios=SCENARIOS, rollout=RolloutPolicy.ClaudeHeuristicGreedy)
    rng.seed(seed)
    mcts = sts2_MCTS()
    action, _ = mcts.monte_carlo_tree_search(cs, config)
    assert play_of(cs, action) == CardId.PILLAGE

def test_the_bludgeon_is_played_when_the_draw_brings_it():
    cs = bash_pillage_bludgeon_or_defend()
    config = SearchConfig(max_sims=600, early_exit=False, paired_scenarios=SCENARIOS, rollout=RolloutPolicy.ClaudeHeuristicGreedy)
    for k in range(40):                                         # a draw that does bring it
        sim = CombatSimulator(cs.deepcopy(cs) if hasattr(cs, "deepcopy") else __import__("copy").deepcopy(cs))
        rng.seed(k)
        sim.combat_state.player.shuffle_draw_pile()
        pillage_at = next(i for i, c in enumerate(sim.combat_state.player.hand) if c.card_id == CardId.PILLAGE)
        sim.perform_action({"action": "play_card", "card_index": pillage_at, "target": 0, "target_name": "E0"})
        if CardId.BLUDGEON in [c.card_id for c in sim.combat_state.player.hand]:
            break
    else:
        pytest.fail("no draw in 40 brought the Bludgeon")
    rng.seed(1)
    action, _ = sts2_MCTS().monte_carlo_tree_search(sim.combat_state, config)
    assert sim.combat_state.player.hand[action["card_index"]].card_id == CardId.BLUDGEON

@pytest.mark.parametrize("seed", range(3))
def test_bash_is_played_first_when_it_is_the_sure_kill(seed):
    """The control for the test above: at 17 HP Bash then Pillage (8 + 6 * 1.5) kills for sure, and Pillage first kills only when the
    Bludgeon is on top. The choice follows the value, not a habit of drawing first."""
    cs = bash_pillage_bludgeon_or_defend()
    cs.enemies[0].current_hp = cs.enemies[0].max_hp = 17
    config = SearchConfig(max_sims=1000, early_exit=False, paired_scenarios=SCENARIOS, rollout=RolloutPolicy.ClaudeHeuristicGreedy)
    rng.seed(seed)
    action, _ = sts2_MCTS().monte_carlo_tree_search(cs, config)
    assert play_of(cs, action) == CardId.BASH
