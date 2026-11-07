"""State comparison used by agent_tester to find drift between the sim and the game."""
import json
from pathlib import Path

from sts2_lite.card import Card, CardId
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.status import StatusId
from sts2_lite.verify import compare, snapshot, is_random_step

DATA = Path(__file__).parent / "data"

def load(name="relics/spiked_gauntlets.json"):
    return CombatState.from_dict(json.loads((DATA / name).read_text()))

def played(cs, action):
    after = CombatState.deepcopy(cs)
    CombatSimulator(after).perform_action(action)
    return after

def first_play(cs):
    return next(a for a in CombatSimulator(cs).get_available_actions() if a["action"] == "play_card")


def test_a_state_matches_its_own_copy():
    cs = load()
    assert compare(cs, CombatState.deepcopy(cs)) == []

def test_player_and_enemy_differences_are_named():
    cs, other = load(), load()
    other.player.current_hp -= 3
    other.energy -= 1
    other.enemies[0].current_hp -= 5
    other.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    diffs = compare(cs, other)
    assert "player hp: sim 80, game 77" in diffs
    assert any("energy" in d for d in diffs)
    assert any("enemy 0" in d and "hp" in d for d in diffs)
    assert any("VULNERABLE" in d for d in diffs)

def test_a_card_missing_from_the_game_is_reported():
    cs, other = load(), load()
    other.player.discard_pile.append(Card.create_soot())
    assert any("cards owned" in d and "SOOT" in d for d in compare(cs, other))

def test_hand_differences_are_exact_unless_the_step_was_random():
    cs, other = load(), load()
    other.player.hand.append(other.player.draw_pile.pop())      # the game drew a card the sim did not
    assert any(d.startswith("hand") for d in compare(cs, other))
    relaxed = compare(cs, other, random_step=True)
    assert all(not d.startswith(("hand", "draw", "discard")) for d in relaxed)

def test_a_played_card_matches_its_own_reload():
    cs = load()
    predicted = played(cs, first_play(cs))
    assert predicted.energy < cs.energy
    assert compare(predicted, CombatState.deepcopy(predicted)) == []
    assert compare(cs, predicted) != []

def test_end_turn_is_a_random_step_and_a_plain_play_is_not():
    cs = load()
    end = {"action": "end_turn"}
    assert is_random_step(cs, played(cs, end), [end])
    play = first_play(cs)
    assert not is_random_step(cs, played(cs, play), [play])

def test_snapshot_is_plain_data():
    json.dumps(snapshot(load()))
