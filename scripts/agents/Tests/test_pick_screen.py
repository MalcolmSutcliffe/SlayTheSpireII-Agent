from __future__ import annotations
"""Picking cards on the game's own screens: the in-combat hand screen renumbers after each pick, a pile screen does not."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import agent_tester


def pick(monkeypatch, state, action, picking_more=True):
    calls = []
    monkeypatch.setattr(agent_tester.subprocess, "run", lambda command, *a, **k: calls.append(command))
    monkeypatch.setattr(agent_tester, "confirm_if_ready", lambda: None)
    agent_tester.act(action, state, picking_more)
    return calls


def cards(*ids):
    return [{"index": i, "id": c, "is_upgraded": False} for i, c in enumerate(ids)]


def hand_action(card_id):
    return {"action": "choose_card", "card_id": card_id, "is_upgraded": False, "pile": "hand"}


def test_hand_screen_renumbers_so_an_earlier_pick_does_not_hide_the_card_now_at_its_index(monkeypatch):
    agent_tester.picked_on_screen.clear()
    first = pick(monkeypatch, {"cards": cards("BASH", "CLUMSY", "STRIKE_IRONCLAD", "DEFEND_IRONCLAD")}, hand_action("BASH"))
    assert first[-1][-1] == "0"
    # Bash left the list: Clumsy is index 0 now, and the pick must find it (the old code skipped index 0 and reported it missing)
    second = pick(monkeypatch, {"cards": cards("CLUMSY", "STRIKE_IRONCLAD", "DEFEND_IRONCLAD")}, hand_action("CLUMSY"))
    assert second and second[-1][-1] == "0"
    third = pick(monkeypatch, {"cards": cards("STRIKE_IRONCLAD", "DEFEND_IRONCLAD")}, hand_action("DEFEND_IRONCLAD"))
    assert third[-1][-1] == "1"
    agent_tester.picked_on_screen.clear()


def test_pile_screen_keeps_its_list_so_two_identical_cards_are_picked_one_after_the_other(monkeypatch):
    agent_tester.picked_on_screen.clear()
    action = {"action": "choose_card", "card_id": "STRIKE_IRONCLAD", "is_upgraded": False, "pile": "draw"}
    state = {"cards": cards("STRIKE_IRONCLAD", "STRIKE_IRONCLAD", "DEFEND_IRONCLAD")}
    assert pick(monkeypatch, state, action)[-1][-1] == "0"
    assert pick(monkeypatch, state, action)[-1][-1] == "1"
    agent_tester.picked_on_screen.clear()
