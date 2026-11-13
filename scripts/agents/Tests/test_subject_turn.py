from __future__ import annotations
"""The Test Subject is not listed while it lies dead between its forms. If the player still holds cards that need a target, the turn is
theirs to end; the loop used to treat the empty enemy list as a fight being set up, waited for ever and never ended the turn."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from agent_runner import combat_session
from sts2_lite.combat import CombatState, CombatSimulator
from sts2_lite.enemy import Enemy
from test_mcts import make_state, strike


def game_state(enemies):
    return {"type": "decision", "decision": "combat_play", "turn": "player", "is_play_phase": True, "enemies": enemies,
            "player": {"hp": 40, "max_hp": 80, "block": 0, "status": {}, "hand": [{}]}}

def test_no_enemies_in_the_player_turn_is_still_set_up_elsewhere():
    assert combat_session.kind_of(game_state([])) == "busy"

def test_no_enemies_in_the_test_subject_fight_is_a_turn_to_play():
    assert combat_session.kind_of(game_state([]), subject_fight=True) == "play"

def test_a_listed_enemy_does_not_need_the_flag():
    assert combat_session.kind_of(game_state([{"name": "x"}])) == "play"

def test_the_enemies_turn_is_never_a_turn_to_play():
    state = game_state([])
    state["turn"] = "enemy"
    assert combat_session.kind_of(state, subject_fight=True) == "busy"

def test_the_fight_is_recognised_from_the_simulated_state():
    cs = make_state([strike()])
    assert not combat_session.in_subject_fight(cs)
    cs.dormant.append(Enemy.dormant_subject(cs.ascension))
    assert combat_session.in_subject_fight(cs)
    assert not combat_session.in_subject_fight(None)

def test_with_the_subject_down_only_ending_the_turn_is_left_for_an_attack_in_hand():
    cs = make_state([strike()])
    cs.enemies = []
    cs.dormant.append(Enemy.dormant_subject(cs.ascension))
    assert [a["action"] for a in CombatSimulator(cs).get_available_actions()] == ["end_turn"]
