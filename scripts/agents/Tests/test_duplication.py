from __future__ import annotations
"""The game calls the Duplicator potion's status DUPLICATION (id DUPLICATION_POWER); the sim had named it DUPLICATOR, so reading the state crashed."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from sts2_lite.combat import CombatSimulator
from sts2_lite.status import StatusId, StatusInstance
from test_mcts import make_state, strike


def test_the_games_status_id_is_read():
    status = StatusInstance.from_dict({"id": "DUPLICATION_POWER", "amount": 1})
    assert status.status_id == StatusId.DUPLICATION and status.amount == 1


def play_first_card(cs):
    action = next(a for a in CombatSimulator(cs).get_available_actions() if a["action"] == "play_card")
    CombatSimulator(cs).perform_action(action)


def test_the_next_card_is_played_twice_and_only_once():
    once = make_state([strike(), strike()])
    twice = make_state([strike(), strike()])
    twice.player.apply_status(StatusId.DUPLICATION, 1)
    hp = once.enemies[0].current_hp
    play_first_card(once)
    play_first_card(twice)
    assert hp - twice.enemies[0].current_hp == 2 * (hp - once.enemies[0].current_hp)
    assert StatusId.DUPLICATION not in twice.player.status
    before = twice.enemies[0].current_hp
    play_first_card(twice)                  # the second Strike is an ordinary one
    assert before - twice.enemies[0].current_hp == hp - once.enemies[0].current_hp
