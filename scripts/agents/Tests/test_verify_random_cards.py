from __future__ import annotations
"""The verifier must not flag the random cards a card generates (Stoke) as a mismatch with the game."""
from sts2_lite import rng
from sts2_lite.card import CardId, Card
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.verify import compare, is_random_step
from agents.Tests.test_mcts import make_state, strike, defend, bash


def stoke_hand():
    return make_state([Card.create_generated(CardId.STOKE), strike(), defend(), bash(), strike()])


def play_stoke(seed):
    rng.seed(seed)
    cs = stoke_hand()
    before = CombatState.deepcopy(cs)
    action = next(a for a in CombatSimulator(cs).get_available_actions() if a["action"] == "play_card" and cs.player.hand[a["card_index"]].card_id == CardId.STOKE)
    CombatSimulator(cs).perform_action(action)
    return before, cs, [action]


def test_stoke_is_a_random_step():
    before, after, actions = play_stoke(0)
    assert is_random_step(before, after, actions)


def test_stoke_with_different_random_cards_is_not_a_mismatch():
    _, first, _ = play_stoke(1)
    for seed in range(2, 40):
        _, other, _ = play_stoke(seed)
        if compare(first, other):         # a seed that made other cards (the exact comparison sees it)
            assert compare(first, other, random_step=True) == [], seed
            return
    raise AssertionError("no seed gave different cards")


def test_a_real_difference_in_the_cards_owned_is_still_flagged_on_a_random_step():
    _, first, _ = play_stoke(1)
    _, other, _ = play_stoke(1)
    other.player.hand.pop()                # a card missing, not a different pick
    assert any(d.startswith("cards owned") for d in compare(first, other, random_step=True))
