"""Decimillipede (three segments with Reattach). Run from scripts/: python -m pytest sts2_lite"""
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy_moves import MOVE_TABLES, SEGMENTS
from sts2_lite.status import StatusId
from sts2_lite.state_key import state_key
from sts2_lite.Tests import captures
from sts2_lite.Tests.enemies.test_bridge_moves import attack, load, raw_enemy


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)

def segment(kind, move="CONSTRICT", hp=45):
    t = MOVE_TABLES[f"DECIMILLIPEDE_SEGMENT_{kind}"](0)
    m = t[move]
    e = raw_enemy(f"DECIMILLIPEDE_SEGMENT_{kind}", move + "_MOVE", [move + "_MOVE"], attack(m.damage, m.hits),
                  status=[{"id": "REATTACH_POWER", "amount": 25}])
    e["max_hp"] = e["hp"] = hp
    return e

def full(moves=("CONSTRICT", "BULK", "WRITHE")):
    cs = load(segment("FRONT", moves[0], 41), segment("MIDDLE", moves[1], 43), segment("BACK", moves[2], 45))
    cs.player.current_hp = 500
    return cs

def ids(cs):
    return [e.enemy_id.split("SEGMENT_")[1].rsplit("_", 1)[0] for e in cs.enemies]

def kill(cs, kind):
    seg = next(e for e in cs.enemies if kind in e.enemy_id)
    seg.current_hp = 0
    CombatSimulator(cs).resolve_deaths()
    return seg


def test_values():
    t = MOVE_TABLES[SEGMENTS[0]](0)
    assert (t["WRITHE"].damage, t["WRITHE"].hits, t["BULK"].damage, t["CONSTRICT"].damage) == (5, 2, 6, 8)
    t = MOVE_TABLES[SEGMENTS[0]](10)
    assert (t["WRITHE"].damage, t["BULK"].damage, t["CONSTRICT"].damage) == (6, 7, 9)

def test_capture_has_a_segment_waiting_to_reattach():
    cs = captures.load("decimillipede", "middle_dead", captures.HIVE)
    assert ids(cs) == ["FRONT", "BACK"]
    assert [(e.enemy_id, e.move_id, e.current_hp) for e in cs.dormant] == [("DECIMILLIPEDE_SEGMENT_MIDDLE_0", "REATTACH", 0)]

def test_a_killed_segment_does_not_die_while_another_lives():
    cs = full()
    kill(cs, "MIDDLE")
    assert ids(cs) == ["FRONT", "BACK"]
    assert [e.move_id for e in cs.dormant] == ["DEAD"]
    assert set(cs.dormant[0].status) == {StatusId.REATTACH}
    CombatSimulator(cs)._check_is_over()

def test_the_fight_is_won_when_the_last_living_segment_falls():
    cs = full()
    sim = CombatSimulator(cs)
    kill(cs, "MIDDLE")
    kill(cs, "FRONT")
    kill(cs, "BACK")
    sim._check_is_over()
    assert sim.is_over and cs.enemies == []

def test_killing_all_three_at_once_is_a_win():
    cs = full()
    for e in cs.enemies:
        e.current_hp = 0
    sim = CombatSimulator(cs)
    sim.resolve_deaths()
    sim._check_is_over()
    assert sim.is_over and cs.dormant == []

def test_dead_turn_then_reattach_then_it_attacks_again():
    cs = full()
    sim = CombatSimulator(cs)
    kill(cs, "MIDDLE")
    sim._play_enemy_turn()          # DEAD_MOVE
    assert ids(cs) == ["FRONT", "BACK"] and cs.dormant[0].move_id == "REATTACH"
    sim._play_enemy_turn()          # REATTACH_MOVE: heals 25
    assert ids(cs) == ["FRONT", "MIDDLE", "BACK"]
    middle = cs.enemies[1]
    assert (middle.current_hp, middle.move_id in {"WRITHE", "BULK", "CONSTRICT"}, cs.dormant) == (25, True, [])
    assert middle.attack_damage == MOVE_TABLES[SEGMENTS[1]](0)[middle.move_id].damage

def test_the_loaded_waiting_segment_is_back_after_the_next_enemy_turn():
    cs = captures.load("decimillipede", "middle_dead", captures.HIVE)
    CombatSimulator(cs)._play_enemy_turn()
    assert ids(cs) == ["FRONT", "MIDDLE", "BACK"] and cs.enemies[1].current_hp == 25

def test_segment_killed_during_the_enemy_turn_still_has_its_dead_turn_next():
    cs = full()
    sim = CombatSimulator(cs)
    waiting = list(cs.dormant)
    cs.dormant.append(__import__("sts2_lite.enemy", fromlist=["Enemy"]).Enemy.lie_dead(cs.enemies[1]))
    sim._reattach_segments(waiting)         # killed after the turn began: not in `waiting`
    assert cs.dormant[0].move_id == "DEAD"

def test_strength_is_lost_with_death_and_the_attacks_follow_their_ring():
    cs = full(("CONSTRICT", "CONSTRICT", "CONSTRICT"))
    sim = CombatSimulator(cs)
    seen = []
    for _ in range(4):
        seen.append(cs.enemies[0].move_id)
        sim._play_enemy_turn()
    assert seen == ["CONSTRICT", "BULK", "WRITHE", "CONSTRICT"]
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2
    kill(cs, "FRONT")
    assert StatusId.STRENGTH not in cs.dormant[0].status

def test_constrict_weakens_and_bulk_gains_strength():
    cs = full(("CONSTRICT", "BULK", "BULK"))
    CombatSimulator(cs)._play_enemy_turn()
    assert cs.player.status_amount(StatusId.WEAK) >= 1
    assert cs.enemies[1].status_amount(StatusId.STRENGTH) == 2

def test_the_waiting_segments_are_part_of_the_state_key():
    a, b = full(), full()
    kill(a, "MIDDLE")
    kill(b, "FRONT")
    assert state_key(a) != state_key(b)
    c = full()
    kill(c, "MIDDLE")
    assert state_key(a) == state_key(c)

def test_copies_keep_the_waiting_segments():
    cs = full()
    kill(cs, "BACK")
    copy = type(cs).deepcopy(cs)
    assert [e.move_id for e in copy.dormant] == ["DEAD"] and copy.dormant[0] is not cs.dormant[0]


def test_the_bridge_lists_waiting_segments_and_the_move_they_are_on():
    cs = captures.load("decimillipede", "middle_dead", captures.HIVE)
    raw = {"round": 3, "energy": 3, "max_energy": 3, "player": {"max_hp": 80, "hp": 80, "block": 0, "status": [], "hand": [], "draw_pile": [], "discard_pile": [], "deck": []},
           "enemies": [segment("FRONT"), segment("BACK")],
           "reviving": [{"entity_id": "DECIMILLIPEDE_SEGMENT_MIDDLE_0", "max_hp": 44, "move_id": "DEAD_MOVE"}]}
    cs = type(cs).from_dict(raw)
    assert [(e.enemy_id, e.move_id, e.max_hp) for e in cs.dormant] == [("DECIMILLIPEDE_SEGMENT_MIDDLE_0", "DEAD", 44)]
    raw["reviving"] = []
    assert type(cs).from_dict(raw).dormant == []        # listed as none: nothing is inferred from what is missing
