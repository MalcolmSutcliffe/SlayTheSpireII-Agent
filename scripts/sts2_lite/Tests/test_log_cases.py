"""Cases the live tester found: the raw game states before and after, and what the sim must predict from them."""
import json
from pathlib import Path

from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.verify import compare

CASES = Path(__file__).parent / "data" / "log_cases"

def case(name):
    return json.loads((CASES / f"{name}.json").read_text())

def simulate(raw_before, actions):
    cs = CombatState.from_dict(raw_before)
    sim = CombatSimulator(cs)
    for a in actions:
        sim.perform_action(a)
    return cs

def test_armaments_screen_lists_selectable_cards_by_their_own_index():
    screen = case("armaments_select_screen")
    cs = CombatState.from_dict(screen)
    assert cs.pending_choice is not None and cs.pending_choice.kind == "upgrade"
    assert len(cs.pending_choice.indices) == 1                 # two identical Defends are one option
    assert [cs.player.hand[i].card_id for i in cs.pending_choice.indices] == [CardId.DEFEND_IRONCLAD]

def test_selectable_cards_are_matched_to_the_hand_by_identity():
    """The screen skips cards that cannot be upgraded (Dazed), so its indices are not hand positions."""
    screen = case("armaments_select_screen")
    hand = screen["player"]["hand"]
    dazed = {**hand[0], "id": "DAZED", "name": "Dazed", "type": "Status", "cost": "0", "can_play": False}
    screen["player"]["hand"] = [dazed] + hand
    for i, c in enumerate(screen["player"]["hand"]):
        c["index"] = i
    cs = CombatState.from_dict(screen)
    assert cs.pending_choice.indices == [1]                    # the first Defend, behind the Dazed card

def test_armaments_with_two_identical_defends_resolves_like_the_game():
    c = case("armaments_identical_defends")
    predicted = simulate(c["before"], c["actions"])
    final = case("armaments_choose_defend")["after"]
    assert compare(predicted, CombatState.from_dict(final)) == []


def test_armaments_among_other_cards_offers_only_what_can_be_upgraded():
    c = case("armaments_two_cards_apart")
    cs = CombatState.from_dict(c["before"])
    sim = CombatSimulator(cs)
    sim.perform_action(c["actions"][0])
    picks = [a for a in sim.get_available_actions() if a["action"] == "choose_card"]
    assert {a["card_id"] for a in picks} == {"DEFEND_IRONCLAD", "STRIKE_IRONCLAD"}     # not the Dazed
