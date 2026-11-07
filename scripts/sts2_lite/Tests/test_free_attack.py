"""Free Attack as the game shows it: Attacks in the hand read cost 0 while it lasts. Run from scripts/: python -m pytest sts2_lite/Tests"""
import json
from pathlib import Path

from sts2_lite.card import CardId
from sts2_lite.combat import CombatState, CombatSimulator
from sts2_lite.status import StatusId
from sts2_lite.verify import compare

DATA = Path(__file__).parent / "data" / "cards"

def load(name):
    return CombatState.from_dict(json.loads((DATA / f"{name}.json").read_text()))

def play(cs, index):
    sim = CombatSimulator(cs)
    target = cs.enemies and 0
    sim.play_card(index, target)
    return cs

def test_a_loaded_hand_gets_its_own_costs_back():
    """The game showed Pommel Strike and Mangle at 0 while Free Attack was up."""
    cs = load("free_attack_mangle_before")
    costs = {c.card_id: c.energy_cost for c in cs.player.hand}
    assert costs[CardId.POMMEL_STRIKE] == 1 and costs[CardId.MANGLE] == 3
    assert all(c.current_cost(cs.player) == 0 for c in cs.player.hand)

def test_unrelenting_makes_the_next_attack_free_and_matches_the_game():
    cs = load("unrelenting_before")
    play(cs, 2)
    assert compare(cs, load("unrelenting_after")) == []

def test_only_one_attack_is_free_and_the_costs_come_back():
    """Mangle uses the Free Attack; the game then shows Pommel Strike at 1 again."""
    cs = load("free_attack_mangle_before")
    play(cs, 1)
    assert compare(cs, load("free_attack_mangle_after")) == []
    pommel = next(c for c in cs.player.hand if c.card_id == CardId.POMMEL_STRIKE)
    assert pommel.current_cost(cs.player) == 1 and cs.player.status_amount(StatusId.FREE_ATTACK) == 0

# ---------------------------------------------------------------- intents shown through Weak and Strength
def beast(name):
    return CombatState.from_dict(json.loads((DATA.parent / "act1_overgrowth" / "ceremonial_beast" / f"{name}.json").read_text()))

def test_weakened_beast_still_identifies_plow():
    """Plow (18 + 2 Strength, Weak) shows 15; truncation also maps base 19 to 15, which matched no move."""
    cs = beast("plow_weak_before")
    assert cs.enemies[0].move_id == "PLOW"

def test_plow_adds_two_strength_and_matches_the_game():
    cs = beast("plow_weak_before")
    CombatSimulator(cs).end_turn()
    assert compare(cs, beast("plow_weak_after"), random_step=True) == []
