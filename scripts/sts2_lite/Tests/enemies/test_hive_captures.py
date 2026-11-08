"""Act 2 states captured from the game (Tests/data/act2_hive). Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy import STUNNED
from sts2_lite.status import StatusId
from sts2_lite.Tests import captures


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)       # the table must agree with the game on every move and damage

def hive(enemy, name):
    return captures.load(enemy, name, captures.HIVE)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()


def test_tender_amount_is_the_cards_played_and_the_turn_end_gives_them_back():
    cs = hive("hunter_killer", "tender")
    p = cs.player
    assert p.status[StatusId.TENDER].records == [[2]]
    assert (p.status_amount(StatusId.STRENGTH), p.status_amount(StatusId.DEXTERITY)) == (-2, -2)
    sim = CombatSimulator(cs)
    sim.play_card(1, 0)             # a third card (a Strike) costs one more of each
    assert (p.status_amount(StatusId.STRENGTH), p.status_amount(StatusId.DEXTERITY)) == (-3, -3)
    sim.end_turn()
    assert (p.status_amount(StatusId.STRENGTH), p.status_amount(StatusId.DEXTERITY)) == (0, 0)
    assert p.status[StatusId.TENDER].records == [[0]]

def test_hunter_killer_move_is_read_with_the_tender_state():
    e = hive("hunter_killer", "tender").enemies[0]
    assert (e.move_id, e.used_moves) == ("BITE", {"TENDERIZING_GOOP"})

def test_ovicopter_eggs_hatch_on_their_first_turn():
    cs = hive("ovicopter", "ovicopter")
    assert [e.enemy_id for e in cs.enemies] == ["TOUGH_EGG_0", "TOUGH_EGG_1", "TOUGH_EGG_2", "OVICOPTER_0"]
    enemy_turn(cs)
    eggs = cs.enemies[:3]
    assert all(19 <= e.max_hp <= 22 and e.current_hp == e.max_hp and e.move_id == "NIBBLE" for e in eggs)
    assert all(set(e.status) == {StatusId.MINION} for e in eggs)
    assert cs.enemies[3].move_id == "TENDERIZER" and cs.player.current_hp == cs.player.max_hp - 16

def test_ovicopter_lays_eggs_in_the_same_layout_as_the_game():
    cs = hive("ovicopter", "ovicopter")
    for e in cs.enemies[:3]:
        e.current_hp = 0
    sim = CombatSimulator(cs)
    sim.resolve_deaths()
    ov = cs.enemies[0]
    ov.moves, ov.move_id = ov.moves, "LAY_EGGS"
    enemy_turn(cs)
    assert [e.enemy_id for e in cs.enemies] == ["TOUGH_EGG_0", "TOUGH_EGG_1", "TOUGH_EGG_2", "OVICOPTER_0"]
    assert [e.status_amount(StatusId.HATCH) for e in cs.enemies[:3]] == [1, 1, 1]       # laid with 2, one enemy turn has passed

def test_a_second_laying_puts_the_new_eggs_on_the_left():
    cs = hive("ovicopter", "ovicopter")
    sim = CombatSimulator(cs)
    cs.enemies[1].current_hp = cs.enemies[2].current_hp = 0
    sim.resolve_deaths()
    old = cs.enemies[0]
    old.max_hp = 99
    cs.enemies[-1].move_id = "LAY_EGGS"
    enemy_turn(cs)
    eggs = [e for e in cs.enemies if e.enemy_id.startswith("TOUGH_EGG")]
    assert len(eggs) == 4 and eggs[-1] is old and eggs[-1].enemy_id == "TOUGH_EGG_3"

def test_thieving_hopper_state_and_its_next_turns():
    cs = hive("thieving_hopper", "thieving_hopper")
    h = cs.enemies[0]
    assert (h.move_id, h.status_amount(StatusId.SWIPE), h.status_amount(StatusId.ESCAPE_ARTIST)) == ("FLUTTER", 1, 4)
    enemy_turn(cs)
    assert (h.move_id, h.status_amount(StatusId.FLUTTER), h.status_amount(StatusId.ESCAPE_ARTIST)) == ("HAT_TRICK", 5, 3)

def test_escape_artist_stops_counting_at_one():
    cs = hive("thieving_hopper", "thieving_hopper")
    h = cs.enemies[0]
    h.status[StatusId.ESCAPE_ARTIST].amount = 1
    enemy_turn(cs)
    assert h.status_amount(StatusId.ESCAPE_ARTIST) == 1

def test_slumbering_beetle_encounter_loads_and_the_beetle_wakes_at_the_end_of_an_enemy_turn():
    cs = hive("slumbering_beetle", "slumbering_beetle_on_wake")
    rock, silk, beetle = cs.enemies
    assert (rock.move_id, silk.move_id, beetle.move_id) == ("HEADBUTT", "TOXIC_SPIT", "SNORE")
    assert beetle.status_amount(StatusId.SLUMBER) == 2
    enemy_turn(cs)
    assert beetle.status_amount(StatusId.SLUMBER) == 1 and StatusId.PLATING in beetle.status
    enemy_turn(cs)
    assert StatusId.SLUMBER not in beetle.status and StatusId.PLATING not in beetle.status
    assert beetle.move_id == "SNORE"        # it was chosen before it woke: the roll starts a turn later
    enemy_turn(cs)
    assert beetle.move_id == "ROLL_OUT"
