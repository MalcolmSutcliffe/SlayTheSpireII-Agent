"""Vantom tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.card import CardId
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId


def vantom(name):
    return captures.load("vantom", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def test_table_values():
    t = MOVE_TABLES["VANTOM"](0)
    assert (t["INK_BLOT"].damage, t["INK_BLOT"].hits) == (7, 1)
    assert (t["INKY_LANCE"].damage, t["INKY_LANCE"].hits) == (6, 2)
    assert (t["DISMEMBER"].damage, t["DISMEMBER"].cards) == (26, ((CardId.WOUND, 3),))
    assert t["PREPARE"].self_status == ((StatusId.STRENGTH, 2),)

def test_deadly_ascension_hits_harder():
    t = MOVE_TABLES["VANTOM"](9)
    assert (t["INK_BLOT"].damage, t["INKY_LANCE"].damage, t["DISMEMBER"].damage) == (8, 7, 30)

@pytest.mark.parametrize("name, move", [
    ("ink_blot", "INK_BLOT"), ("inky_lance", "INKY_LANCE"),
    ("dismember", "DISMEMBER"), ("prepare", "PREPARE"),
])
def test_moves_are_identified_from_captures(name, move):
    assert vantom(name).enemies[0].move_id == move

def test_strength_is_removed_from_the_displayed_damage():
    e = vantom("wound_in_hand").enemies[0]
    assert (e.move_id, e.attack_damage) == ("INK_BLOT", 7)

def test_the_cycle_repeats():
    cs = vantom("ink_blot")
    seen = [cs.enemies[0].move_id]
    for _ in range(5):
        enemy_turn(cs)
        seen.append(cs.enemies[0].move_id)
    assert seen == ["INK_BLOT", "INKY_LANCE", "DISMEMBER", "PREPARE", "INK_BLOT", "INKY_LANCE"]

def test_dismember_adds_three_wounds_to_the_discard_pile():
    cs = vantom("dismember")
    before = sum(c.card_id == CardId.WOUND for c in cs.player.discard_pile)
    cs.player.block = 0
    hp = cs.player.current_hp
    enemy_turn(cs)
    assert sum(c.card_id == CardId.WOUND for c in cs.player.discard_pile) == before + 3
    assert cs.player.current_hp == hp - 26

def test_wounds_cannot_be_played():
    cs = vantom("wound_in_hand")
    wound = next(c for c in cs.player.hand if c.card_id == CardId.WOUND)
    assert not wound.can_play_card(CombatSimulator(cs), 0)

def test_prepare_gives_two_strength():
    cs = vantom("prepare")
    enemy_turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2

def test_slippery_caps_each_hit_at_one_hp():
    cs = vantom("ink_blot")
    e = cs.enemies[0]
    hp = e.current_hp
    e.apply_damage(30)
    assert e.current_hp == hp - 1
    assert e.status_amount(StatusId.SLIPPERY) == 7

def test_slippery_is_gone_after_eight_hits():
    cs = vantom("ink_blot")
    e = cs.enemies[0]
    for _ in range(8):
        e.apply_damage(10)
    assert StatusId.SLIPPERY not in e.status
    hp = e.current_hp
    e.apply_damage(10)
    assert e.current_hp == hp - 10

def test_wounds_from_dismember_are_unplayable():
    cs = vantom("dismember")
    enemy_turn(cs)
    wounds = [c for c in cs.player.discard_pile if c.card_id == CardId.WOUND]
    assert wounds and all(c.is_unplayable for c in wounds)
