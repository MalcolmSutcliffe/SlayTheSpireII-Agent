from __future__ import annotations
"""Hellraiser plays every Strike the moment it is drawn, so a different random draw changes the damage dealt: the verifier must not call that a mismatch."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from sts2_lite.combat import CombatState
from sts2_lite.relic import RelicId
from sts2_lite.status import StatusId
from sts2_lite.verify import compare

AFTER = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "hellraiser_after.json")))


def _pair():
    game = CombatState.from_dict(AFTER)
    sim = CombatState.deepcopy(game)
    # the sim drew a Strike that Hellraiser played (7 damage, one more play counted) where the game drew another card
    sim.enemies[0].current_hp -= 7
    sim.player.relics[RelicId.POCKETWATCH].counter += 1
    sim.player.discard_pile.append(sim.player.hand.pop())
    return sim, game


def test_a_different_draw_under_hellraiser_is_not_a_mismatch():
    sim, game = _pair()
    assert StatusId.HELLRAISER in game.player.status
    assert compare(sim, game, random_step=True) == []


def test_without_hellraiser_the_same_differences_are_reported():
    sim, game = _pair()
    del sim.player.status[StatusId.HELLRAISER]
    del game.player.status[StatusId.HELLRAISER]
    assert any("hp" in d for d in compare(sim, game, random_step=True))


def test_a_step_that_is_not_random_is_still_compared_under_hellraiser():
    sim, game = _pair()
    assert compare(sim, game, random_step=False) != []
