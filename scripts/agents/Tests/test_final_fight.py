from __future__ import annotations
"""In the last fight of the run a potion is worth nothing afterwards: it is not priced in the score, so the agent drinks freely."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from agent_runner import combat_session
from sts2_lite.combat import CombatState
from sts2_lite.potion import PotionId
from test_outcome import won, primed
from test_mcts import make_state


def rated(final, potions=()):
    from sts2_lite.potion import Potion
    cs = make_state([])
    cs.enemies[0].current_hp = 0
    cs.player.current_hp, cs.turn_number = 30, 3
    cs.player.potions = [Potion(p, i) for i, p in enumerate(potions)]
    cs.final_fight = final
    mcts = primed(cs, starting_hp=50)
    mcts._starting_max_hp = cs.player.max_hp
    return mcts._rate_outcome(cs)


def test_a_kept_potion_counts_in_an_ordinary_fight():
    assert rated(False, [PotionId.FIRE_POTION]) > rated(False)

def test_a_kept_potion_counts_for_nothing_in_the_final_fight():
    assert rated(True, [PotionId.FIRE_POTION]) == rated(True)

def test_the_flag_survives_a_copy_of_the_state():
    cs = make_state([])
    cs.final_fight = True
    assert CombatState.deepcopy(cs).final_fight

def state(room="boss", act=3, floor=50, ascension=9):
    return {"room_type": room, "context": {"act": act, "floor": floor, "ascension": ascension}}

def test_the_act_3_boss_is_the_last_fight_below_ascension_10():
    assert combat_session.is_final_fight(state(), set())

def test_other_fights_are_not_the_last():
    seen = set()
    assert not combat_session.is_final_fight(state(room="elite"), seen)
    assert not combat_session.is_final_fight(state(act=2, floor=34), seen)
    assert not combat_session.is_final_fight(state(room="monster", act=3), seen)

def test_from_ascension_10_the_first_act_3_boss_is_not_the_last():
    seen = set()
    assert not combat_session.is_final_fight(state(floor=50, ascension=10), seen)
    assert not combat_session.is_final_fight(state(floor=50, ascension=10), seen)      # the same fight read again
    assert combat_session.is_final_fight(state(floor=51, ascension=10), seen)
