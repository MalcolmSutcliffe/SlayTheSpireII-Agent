"""Bread and Meat on the Bone. Run from scripts/: python -m pytest sts2_lite/Tests"""
import json
from pathlib import Path

from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.relic import RelicId, RelicInstance
from sts2_lite.Tests.test_cards import make_state
from sts2_lite.Tests.test_relics_always_on import held, strike

RELICS = Path(__file__).parent / "data" / "relics"

def capture(name):
    return json.loads((RELICS / f"{name}.json").read_text())


# ---------------------------------------------------------------- Bread (Bread.ModifyMaxEnergy)
def test_bread_loads():
    assert RelicInstance.from_dict({"id": "BREAD", "counter": None}).relic_id == RelicId.BREAD

def test_bread_turn_1_to_2_matches_capture():
    cs = CombatState.from_dict(capture("bread_turn_1"))
    CombatSimulator(cs).end_turn()
    expected = capture("bread_turn_2")["max_energy"]
    assert cs.turn_number == 2 and cs.max_energy == expected and cs.energy == expected

def test_bread_turn_2_capture_already_includes_it():
    cs = CombatState.from_dict(capture("bread_turn_2"))
    before = cs.max_energy
    CombatSimulator(cs).end_turn()
    assert cs.max_energy == before

def test_no_bread_no_gain():
    cs = make_state([], enemy_count=1, enemy_hp=100)
    cs.player.draw_pile = [strike() for _ in range(10)]
    CombatSimulator(cs).end_turn()
    assert cs.max_energy == 3


# ---------------------------------------------------------------- Meat on the Bone (MeatOnTheBone.AfterCombatVictoryEarly)
def kill_last_enemy(hp, max_hp=80, *relic_ids):
    cs = held(make_state([strike()], enemy_count=1, enemy_hp=5), *relic_ids)
    cs.player.current_hp, cs.player.max_hp = hp, max_hp
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert sim.is_over
    return cs

def test_meat_on_the_bone_heals_at_half_or_less():
    assert kill_last_enemy(40, 80, RelicId.MEAT_ON_THE_BONE).player.current_hp == 52

def test_meat_on_the_bone_does_nothing_above_half():
    assert kill_last_enemy(41, 80, RelicId.MEAT_ON_THE_BONE).player.current_hp == 41

def test_meat_on_the_bone_threshold_rounds_down():
    assert kill_last_enemy(37, 75, RelicId.MEAT_ON_THE_BONE).player.current_hp == 49
    assert kill_last_enemy(38, 75, RelicId.MEAT_ON_THE_BONE).player.current_hp == 38

def test_meat_on_the_bone_heal_is_capped():
    assert kill_last_enemy(5, 10, RelicId.MEAT_ON_THE_BONE).player.current_hp == 10

def test_no_heal_without_the_relic():
    assert kill_last_enemy(10, 80).player.current_hp == 10

def test_no_heal_on_a_loss():
    cs = held(make_state([], enemy_count=1, enemy_hp=100), RelicId.MEAT_ON_THE_BONE)
    cs.player.current_hp = 0
    sim = CombatSimulator(cs)
    assert sim.is_over and cs.player.current_hp == 0

def test_victory_heal_is_applied_once():
    cs = kill_last_enemy(20, 80, RelicId.MEAT_ON_THE_BONE)
    copy = CombatState.deepcopy(cs)
    CombatSimulator(copy)                       # a new simulator on a finished fight
    assert copy.player.current_hp == 32

def test_victory_with_only_minions_left_heals():
    cs = held(make_state([strike()], enemy_count=2, enemy_hp=5), RelicId.MEAT_ON_THE_BONE)
    cs.enemies[1].is_minion = True
    cs.player.current_hp = 20
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert sim.is_over and cs.player.current_hp == 32


# ---------------------------------------------------------------- Burning Blood / Black Blood (AfterCombatVictory)
def test_burning_blood_heals_6_on_victory():
    assert kill_last_enemy(50, 80, RelicId.BURNING_BLOOD).player.current_hp == 56

def test_black_blood_heals_12_on_victory():
    assert kill_last_enemy(50, 80, RelicId.BLACK_BLOOD).player.current_hp == 62

def test_burning_blood_heal_is_capped():
    assert kill_last_enemy(78, 80, RelicId.BURNING_BLOOD).player.current_hp == 80

def test_meat_on_the_bone_checks_hp_before_burning_blood():
    # 40/80 qualifies for Meat; healing Burning Blood first (46) would not
    assert kill_last_enemy(40, 80, RelicId.BURNING_BLOOD, RelicId.MEAT_ON_THE_BONE).player.current_hp == 58

def test_burning_blood_loads_from_capture():
    cs = CombatState.from_dict(capture("bread_turn_1"))
    assert RelicId.BURNING_BLOOD in cs.player.relics

def test_no_victory_heal_on_a_loss():
    cs = held(make_state([], enemy_count=1, enemy_hp=100), RelicId.BURNING_BLOOD)
    cs.player.current_hp = 0
    CombatSimulator(cs)
    assert cs.player.current_hp == 0
