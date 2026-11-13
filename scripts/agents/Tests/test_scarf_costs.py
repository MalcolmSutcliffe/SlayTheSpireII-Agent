from __future__ import annotations
"""Brilliant Scarf shows the whole hand at 0 when its free card is due: a card that really costs 0 (Juggernaut) keeps that cost from the previous state."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from sts2_lite import rng
from sts2_lite.card import CardId
from sts2_lite.combat import CombatState, CombatSimulator
from sts2_lite.verify import compare

CASE = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "juggernaut_scarf.json")))


def _previous():
    """The state the sim had one play earlier, before the Scarf covered the hand: Juggernaut already at 0, the rest at their table costs."""
    prev = CombatState.deepcopy(CombatState.from_dict(CASE["before"]))
    for i, card in enumerate(prev.player.hand):
        own = type(card).create_copy(card)
        own.guessed_cost = False
        if card.card_id == CardId.JUGGERNAUT:
            own.energy_cost = 0
        prev.player.hand[i] = own
    return prev


def _step(previous):
    rng.seed(0)
    state = CombatState.from_dict(CASE["before"])
    state.carry_card_costs(previous)
    simulator = CombatSimulator(state)
    for action in CASE["actions"]:
        simulator.perform_action(action)
    return compare(state, CombatState.from_dict(CASE["after"]))


def test_a_really_free_card_stays_free_under_the_scarf():
    assert _step(_previous()) == []


def test_without_history_the_table_cost_is_assumed():
    assert any("JUGGERNAUT" in d for d in _step(None))


def test_slimed_costs_one_after_the_scarfs_free_card():
    case = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "slimed_scarf.json")))
    rng.seed(0)
    state = CombatState.from_dict(case["before"])
    simulator = CombatSimulator(state)
    for action in case["actions"]:
        simulator.perform_action(action)
    assert compare(state, CombatState.from_dict(case["after"])) == []
