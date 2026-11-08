"""The Insatiable: Liquify Ground, Sandpit and Frantic Escape. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite.card import CardId
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.status import StatusId
from sts2_lite.Tests.enemies.test_hive_simple import at, moves_over, turn


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)


def test_values():
    t = MOVE_TABLES["THE_INSATIABLE"](0)
    assert (t["THRASH"].damage, t["THRASH"].hits, t["LUNGING_BITE"].damage, t["SALIVATE"].self_status) == (8, 2, 28, ((StatusId.STRENGTH, 2),))
    t = MOVE_TABLES["THE_INSATIABLE"](9)
    assert (t["THRASH"].damage, t["LUNGING_BITE"].damage, t["SALIVATE"].self_status) == (9, 31, ((StatusId.STRENGTH, 3),))

def test_cycle_after_liquify():
    assert moves_over(at("THE_INSATIABLE", "LIQUIFY_GROUND"), 3) == ["LIQUIFY_GROUND", "THRASH", "LUNGING_BITE", "SALIVATE"]
    assert moves_over(at("THE_INSATIABLE", "SALIVATE"), 4) == ["SALIVATE", "THRASH_2", "THRASH", "LUNGING_BITE", "SALIVATE"]

def test_the_game_id_of_the_second_thrash_is_read():
    from sts2_lite.Tests.enemies.test_bridge_moves import attack, load, raw_enemy
    cs = load(raw_enemy("THE_INSATIABLE", "THRASH_MOVE_2", ["THRASH_MOVE", "LUNGING_BITE_MOVE", "SALIVATE_MOVE", "THRASH_MOVE_2"], attack(8, 2)))
    assert cs.enemies[0].move_id == "THRASH_2"

def test_liquify_digs_the_pit_and_shuffles_six_frantic_escapes_in():
    cs = at("THE_INSATIABLE", "LIQUIFY_GROUND")
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.SANDPIT) == 4
    assert [c.card_id for c in cs.player.draw_pile] == [CardId.FRANTIC_ESCAPE] * 3
    assert [c.card_id for c in cs.player.discard_pile] == [CardId.FRANTIC_ESCAPE] * 3

def test_the_player_is_eaten_when_the_pit_reaches_zero():
    cs = at("THE_INSATIABLE", "LIQUIFY_GROUND")
    sim = CombatSimulator(cs)
    sim._play_enemy_turn()
    pit = cs.enemies[0].status
    left = []
    for _ in range(3):
        sim._play_enemy_turn()
        left.append(pit[StatusId.SANDPIT].amount)
        assert cs.player.current_hp > 0
    assert left == [3, 2, 1]
    sim._play_enemy_turn()
    assert cs.player.current_hp == 0 and StatusId.SANDPIT not in pit

def test_the_enemies_do_not_act_on_the_turn_the_player_is_eaten():
    cs = at("THE_INSATIABLE", "LIQUIFY_GROUND")
    sim = CombatSimulator(cs)
    sim._play_enemy_turn()
    cs.enemies[0].status[StatusId.SANDPIT].amount = 1
    before = cs.enemies[0].move_id
    sim._play_enemy_turn()
    assert cs.player.current_hp == 0 and cs.enemies[0].move_id == before

def test_end_turn_ends_the_fight_when_the_player_is_eaten():
    cs = at("THE_INSATIABLE", "THRASH", status=[{"id": "SANDPIT_POWER", "amount": 1}])
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert sim.is_over and not cs.won and cs.player.current_hp == 0

def test_playing_frantic_escape_pushes_the_pit_back_and_costs_more_each_time():
    cs = at("THE_INSATIABLE", "THRASH", status=[{"id": "SANDPIT_POWER", "amount": 2}])
    from sts2_lite.card import Card
    card = Card.create(CardId.FRANTIC_ESCAPE)
    cs.player.hand = [card]
    cs.energy = 3
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.enemies[0].status_amount(StatusId.SANDPIT) == 3 and cs.energy == 2
    assert card.energy_cost == 2
