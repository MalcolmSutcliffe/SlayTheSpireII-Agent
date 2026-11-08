"""Kaiser Crab (Crusher on the left, Rocket on the right) and the Surrounded facing. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite.combat import CombatSimulator
from sts2_lite.damage import modify_damage
from sts2_lite.status import StatusId
from sts2_lite.Tests import captures


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)

def crab(name):
    return captures.load("kaiser_crab", name, captures.HIVE)

def facing(cs):
    return cs.player.status[StatusId.SURROUNDED].records[0][0]

def arms(cs):
    return {e.enemy_id.split("_")[0]: e for e in cs.enemies}


def test_facing_is_read_from_the_shown_damage():
    assert facing(crab("surrounded_from_left")) == 0        # the Crusher's 12 shows as 18
    assert facing(crab("surrounded_from_right")) == 1       # the Rocket's 3 shows as 4

def test_the_arm_behind_the_player_hits_one_and_a_half_times():
    cs = crab("surrounded_from_left")
    a = arms(cs)
    assert modify_damage(12, a["CRUSHER"], cs.player) == 18
    assert modify_damage(3, a["ROCKET"], cs.player) == 3
    cs = crab("surrounded_from_right")
    a = arms(cs)
    assert modify_damage(12, a["CRUSHER"], cs.player) == 12
    assert modify_damage(3, a["ROCKET"], cs.player) == 4

def test_striking_the_arm_that_is_behind_turns_the_player():
    cs = crab("surrounded_from_left")          # facing Right: the Crusher is behind
    CombatSimulator(cs).play_card(0, 0)         # a Strike at the Crusher
    assert facing(cs) == 1
    assert modify_damage(12, arms(cs)["CRUSHER"], cs.player) == 12
    assert modify_damage(3, arms(cs)["ROCKET"], cs.player) == 4

def test_striking_the_arm_in_front_keeps_the_facing_and_defend_does_not_turn():
    cs = crab("surrounded_from_left")
    sim = CombatSimulator(cs)
    sim.play_card(1, 0)                         # Defend
    assert facing(cs) == 0
    rocket = next(i for i, e in enumerate(cs.enemies) if e.enemy_id.startswith("ROCKET"))
    sim.play_card(0, rocket)                    # Strike the Rocket: it is in front already
    assert facing(cs) == 0
    sim.play_card(0, rocket)
    assert facing(cs) == 0

def test_turning_back_from_the_right():
    cs = crab("surrounded_from_right")          # facing Left: the Rocket is behind
    rocket = next(i for i, e in enumerate(cs.enemies) if e.enemy_id.startswith("ROCKET"))
    CombatSimulator(cs).play_card(0, rocket)
    assert facing(cs) == 0

def test_the_enemy_turn_uses_the_facing_for_its_hits():
    cs = crab("surrounded_from_left")
    CombatSimulator(cs)._play_enemy_turn()
    assert cs.player.current_hp == 80 - 18 - 3

def test_a_dying_arm_enrages_the_other():
    cs = crab("surrounded_from_left")
    a = arms(cs)
    a["ROCKET"].current_hp = 1
    rocket = cs.enemies.index(a["ROCKET"])
    CombatSimulator(cs).play_card(0, rocket)
    assert [e.enemy_id for e in cs.enemies] == ["CRUSHER_0"]
    crusher = cs.enemies[0]
    assert crusher.status_amount(StatusId.STRENGTH) == 6
    assert crusher.block == 99
    assert StatusId.CRAB_RAGE not in crusher.status

def test_with_one_side_left_the_player_turns_to_it():
    cs = crab("surrounded_from_left")           # facing Right
    a = arms(cs)
    a["CRUSHER"].current_hp = 1
    CombatSimulator(cs).play_card(0, cs.enemies.index(a["CRUSHER"]))
    # the Crusher was struck, which turned the player Left; the Rocket (right arm) is alone and now behind
    assert [e.enemy_id for e in cs.enemies] == ["ROCKET_0"]
    assert facing(cs) == 0

def test_move_cycles():
    cs = crab("surrounded_from_left")
    a = arms(cs)
    crusher, rocket = a["CRUSHER"], a["ROCKET"]
    seen_c, seen_r = [], []
    sim = CombatSimulator(cs)
    for _ in range(6):
        seen_c.append(crusher.move_id); seen_r.append(rocket.move_id)
        cs.player.current_hp = 500
        sim._play_enemy_turn()
    assert seen_c == ["THRASH", "ENLARGING_STRIKE", "BUG_STING", "ADAPT", "GUARDED_STRIKE", "THRASH"]
    assert seen_r == ["TARGETING_RETICLE", "PRECISION_BEAM", "CHARGE_UP", "LASER", "RECHARGE", "TARGETING_RETICLE"]

def test_bug_sting_weak_and_frail_and_adapt_strength():
    cs = crab("surrounded_from_right")
    crusher = arms(cs)["CRUSHER"]
    sim = CombatSimulator(cs)
    for _ in range(4):
        cs.player.current_hp = 500
        sim._play_enemy_turn()
    assert cs.player.status_amount(StatusId.WEAK) >= 1 and cs.player.status_amount(StatusId.FRAIL) >= 1
    assert crusher.status_amount(StatusId.STRENGTH) == 2
    assert crusher.block == 0
    cs.player.current_hp = 500
    sim._play_enemy_turn()          # GUARDED_STRIKE
    assert crusher.block == 18

def test_ascended_values():
    from sts2_lite.enemy_moves import crusher, rocket
    c, r = crusher(10), rocket(10)
    assert (c["THRASH"].damage, c["BUG_STING"].damage, c["GUARDED_STRIKE"].damage) == (14, 7, 14)
    assert (r["TARGETING_RETICLE"].damage, r["PRECISION_BEAM"].damage, r["LASER"].damage) == (4, 20, 35)
