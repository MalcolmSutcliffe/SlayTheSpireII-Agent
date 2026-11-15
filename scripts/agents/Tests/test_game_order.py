import json
from pathlib import Path

import pytest

from agents.verify import compare, game_order_matches
from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    capture = json.loads((FIXTURES / f"{name}.json").read_text())
    return capture, CombatState.from_dict(capture["before"]), CombatState.from_dict(capture["after"])


def test_the_game_draw_order_explains_a_step_that_plays_the_top_of_the_draw_pile():
    """Distilled Chaos plays the top 3 cards: the game's were Primal Force+, Guilty (unplayable: it goes to the discard pile) and a Defend."""
    capture, before, after = load("distilled_chaos_guilty")
    assert game_order_matches(before, capture["actions"], capture["before"], after)


def test_a_wrong_outcome_is_not_excused_by_the_draw_order():
    capture, before, after = load("distilled_chaos_guilty")
    after.enemies[0].current_hp -= 5
    assert not game_order_matches(before, capture["actions"], capture["before"], after)


@pytest.mark.parametrize("seed", range(5))
def test_enemy_plating_block_is_there_when_inferno_hits(seed):
    """Frog Knight: Plating pays its block at the end of the enemy turn, so the player's turn-start Inferno damage is taken by the block."""
    rng.seed(seed)
    capture, before, after = load("frog_knight_plating_inferno")
    predicted = CombatState.deepcopy(before)
    simulator = CombatSimulator(predicted)
    for action in capture["actions"]:
        simulator.perform_action(action)
    assert not compare(predicted, after, random_step=True)
    assert (predicted.enemies[0].current_hp, predicted.enemies[0].block) == (after.enemies[0].current_hp, after.enemies[0].block) == (173, 6)
