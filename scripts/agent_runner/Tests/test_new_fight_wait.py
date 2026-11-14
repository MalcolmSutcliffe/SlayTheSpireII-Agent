from agent_runner import combat_session
from agent_runner.combat_session import CombatSession


def session():
    s = CombatSession.__new__(CombatSession)
    s.fight_floor = s.arrived = None
    return s


def state(floor, hand=("STRIKE",), energy=3):
    return {"context": {"floor": floor}, "hand": list(hand), "energy": energy}


def test_waits_for_the_dealt_hand_on_a_new_floor_and_then_plays():
    s = session()
    assert s.entering_new_fight(state(5, hand=(), energy=3))        # only End Turn is on offer yet
    assert s.entering_new_fight(state(5, hand=("STRIKE",), energy=0))
    assert not s.entering_new_fight(state(5))                       # hand and energy are in
    assert s.fight_floor == 5


def test_later_turns_of_the_same_floor_are_not_awaited():
    s = session()
    s.entering_new_fight(state(5))
    assert not s.entering_new_fight(state(5, hand=(), energy=0))


def test_the_next_floor_is_awaited_again():
    s = session()
    s.entering_new_fight(state(5))
    assert s.entering_new_fight(state(6, hand=()))
    assert not s.entering_new_fight(state(6))


def test_gives_up_after_the_timeout(monkeypatch):
    s = session()
    s.entering_new_fight(state(5, hand=()))
    s.arrived -= combat_session.NEW_FIGHT_TIMEOUT + 1
    assert not s.entering_new_fight(state(5, hand=()))
