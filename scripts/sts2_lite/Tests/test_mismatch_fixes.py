"""Mismatches from a full run. Run from scripts/: python -m pytest sts2_lite/Tests"""
import json
from pathlib import Path

from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.verify import compare, is_random_step

DATA = Path(__file__).parent / "data" / "mismatches"

def load(name):
    d = json.loads((DATA / f"{name}.json").read_text())
    return CombatState.from_dict(d["before"]), CombatState.from_dict(d["after"]), d["actions"]

def test_red_skull_strength_applies_to_breakthrough_hit():
    before, after, actions = load("breakthrough_red_skull")
    CombatSimulator(before).play_card(actions[0]["card_index"], actions[0].get("target", 0))
    assert compare(before, after) == []

def test_toasty_mittens_drum_of_battle_random_exhaust_is_not_an_energy_mismatch():
    before, after, actions = load("toasty_drum_of_battle")
    pre = CombatState.deepcopy(before)
    CombatSimulator(before).end_turn()
    assert compare(before, after, random_step=is_random_step(pre, before, actions)) == []

def test_jack_of_all_trades_random_card_is_tolerated():
    before, after, actions = load("jack_of_all_trades")
    pre = CombatState.deepcopy(before)
    sim = CombatSimulator(before)
    sim.play_card(actions[0]["card_index"], actions[0].get("target", 0))
    assert compare(before, after, random_step=is_random_step(pre, before, actions)) == []


def replay(name):
    before, after, actions = load(name)
    pre = CombatState.deepcopy(before)
    sim = CombatSimulator(before)
    for a in actions:
        sim.perform_action(a)
    return pre, before, after, actions

def test_tender_shows_the_cards_played_not_the_stack():
    pre, predicted, after, actions = replay("tender_applied")
    assert compare(predicted, after, random_step=is_random_step(pre, predicted, actions)) == []

def test_tender_counts_the_card_that_was_just_played():
    pre, predicted, after, actions = replay("tender_card_played")
    assert compare(predicted, after) == []

def test_the_beetle_keeps_the_plating_block_it_gained_before_it_woke():
    from sts2_lite.status import StatusId
    pre, predicted, after, actions = replay("beetle_wakes_with_plating_block")
    beetle = predicted.enemies[2]
    assert beetle.block == 17 and StatusId.PLATING not in beetle.status
    assert compare(predicted, after, random_step=is_random_step(pre, predicted, actions)) == []

def test_stampede_picking_between_attacks_is_not_compared():
    from sts2_lite.verify import is_unpredictable_step
    before, after, actions = load("stampede_random_attack")
    assert is_unpredictable_step(before, actions)
    before.player.hand = [c for c in before.player.hand if c.card_id.name == "BODY_SLAM"]
    assert not is_unpredictable_step(before, actions)        # one kind of Attack left: only that one can be played
