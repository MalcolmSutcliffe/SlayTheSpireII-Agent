"""Vigor (VigorPower) and card keywords (CardKeyword, Retain, Ghost Seed). Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.card import Card, CardId, CardKeyword, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.player import Player
from sts2_lite.relic import RelicId
from sts2_lite.status import StatusId, StatusInstance
from sts2_lite.Tests.test_cards import make_card, make_state


def card(card_id, cost=1, kind=CardType.Attack, target=TargetType.AnyEnemy, upgraded=False):
    return make_card(card_id, card_id.name.title(), kind, cost, target, upgraded)

def strike():
    return card(CardId.STRIKE_IRONCLAD)

def defend():
    return card(CardId.DEFEND_IRONCLAD, kind=CardType.Skill, target=TargetType.Self)

def with_vigor(cs, amount=8):
    cs.player.apply_status(StatusId.VIGOR, amount)
    cs.player.draw_pile = [defend() for _ in range(10)]
    return cs

def lost(cs, i=0, hp=100):
    return hp - cs.enemies[i].current_hp

def bridge_card(card_id, kind="Attack", target="AnyEnemy", keywords=None):
    d = {"id": card_id, "type": kind, "name": card_id.title(), "can_play": True, "cost": "1", "is_upgraded": False,
         "target_type": target, "description": "", "keywords": []}
    if keywords is not None:
        d["card_keywords"] = keywords
    return d


# ---------------------------------------------------------------- Vigor (VigorPower)
def test_vigor_loads_from_the_bridge():
    assert StatusInstance.from_dict({"id": "VIGOR_POWER", "amount": 8}).status_id == StatusId.VIGOR

def test_vigor_adds_to_the_first_attack_and_is_spent():
    cs = with_vigor(make_state([strike(), strike()], enemy_count=1, enemy_hp=100))
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert lost(cs) == 14 and StatusId.VIGOR not in cs.player.status
    sim.play_card(0, 0)
    assert lost(cs) == 14 + 6

def test_vigor_applies_to_every_hit_of_the_command():
    cs = with_vigor(make_state([card(CardId.TWIN_STRIKE)], enemy_count=1, enemy_hp=100))
    CombatSimulator(cs).play_card(0, 0)
    assert lost(cs) == 2 * (5 + 8)

def test_vigor_applies_to_every_target_of_the_command():
    cs = with_vigor(make_state([card(CardId.THUNDERCLAP, target=TargetType.AllEnemies)], enemy_count=2, enemy_hp=100))
    CombatSimulator(cs).play_card(0, 0)
    assert lost(cs, 0) == 12 and lost(cs, 1) == 12

def test_vigor_is_added_before_vulnerable():
    cs = with_vigor(make_state([strike()], enemy_count=1, enemy_hp=100))
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    CombatSimulator(cs).play_card(0, 0)
    assert lost(cs) == int((6 + 8) * 1.5)

def test_a_skill_does_not_spend_vigor():
    cs = with_vigor(make_state([defend()], enemy_count=1))
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.status_amount(StatusId.VIGOR) == 8

def test_one_two_punch_replay_is_a_new_command_without_vigor():
    cs = with_vigor(make_state([strike()], enemy_count=1, enemy_hp=100))
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    CombatSimulator(cs).play_card(0, 0)
    assert lost(cs) == 14 + 6

def test_a_strike_hellraiser_plays_after_pommel_strike_gets_no_vigor():
    cs = with_vigor(make_state([card(CardId.POMMEL_STRIKE)], enemy_count=1, enemy_hp=100))
    cs.player.draw_pile = [strike()]
    cs.player.apply_status(StatusId.HELLRAISER, 1)
    CombatSimulator(cs).play_card(0, 0)
    assert lost(cs) == (9 + 8) + 6

def test_a_refused_attack_keeps_vigor():
    cs = with_vigor(make_state([strike()], enemy_count=1, enemy_hp=100))
    sim = CombatSimulator(cs)
    with pytest.raises(ValueError):
        sim.play_card(0, 5)
    assert sim.vigor_pending is None and cs.player.status_amount(StatusId.VIGOR) == 8


# ---------------------------------------------------------------- keywords (CardKeyword)
def test_canonical_keywords():
    assert Card.create_dazed().ethereal and Card.create_dazed().unplayable
    assert Card.create_slimed().exhausts and not Card.create_slimed().unplayable
    assert Card.create_wound().unplayable
    assert strike().keywords == frozenset()

def test_keywords_load_from_the_bridge():
    c = Card.from_dict(bridge_card("STRIKE_IRONCLAD", keywords=["Ethereal", "Retain"]))
    assert c.keywords == {CardKeyword.ETHEREAL, CardKeyword.RETAIN}

def test_the_bridge_list_replaces_the_canonical_one():
    c = Card.from_dict(bridge_card("TREMBLE", kind="Skill", keywords=[]))
    assert not c.exhausts

def test_without_the_bridge_field_keywords_are_canonical():
    assert Card.from_dict(bridge_card("TREMBLE", kind="Skill")).exhausts

def test_with_keyword_copies_and_keeps_through_upgrade():
    base = strike()
    ethereal = base.with_keyword(CardKeyword.ETHEREAL)
    assert ethereal is not base and not base.ethereal and ethereal.ethereal
    assert ethereal.upgraded_copy().ethereal
    assert ethereal.with_keyword(CardKeyword.ETHEREAL) is ethereal

def test_an_ethereal_card_is_exhausted_at_end_of_turn():
    cs = make_state([strike().with_keyword(CardKeyword.ETHEREAL), strike()], enemy_count=1)
    CombatSimulator(cs).end_turn()
    assert [c.card_id for c in cs.player.exhaust_pile] == [CardId.STRIKE_IRONCLAD]

def test_a_retained_card_stays_in_hand():
    kept, other = defend().with_keyword(CardKeyword.RETAIN), strike()
    cs = make_state([kept, other], enemy_count=1)
    cs.player.draw_pile = [defend() for _ in range(10)]
    CombatSimulator(cs).end_turn()
    assert kept in cs.player.hand and other in cs.player.discard_pile and len(cs.player.hand) == 6

def test_an_added_unplayable_keyword_blocks_the_card():
    cs = make_state([strike().with_keyword(CardKeyword.UNPLAYABLE)], enemy_count=1)
    sim = CombatSimulator(cs)
    assert sim.get_available_actions() == [{"action": "end_turn"}]

def test_havoc_skips_a_card_made_unplayable():
    cs = make_state([card(CardId.HAVOC, kind=CardType.Skill, target=TargetType.Self)], enemy_count=1, enemy_hp=100)
    cs.player.draw_pile = [strike().with_keyword(CardKeyword.UNPLAYABLE)]
    CombatSimulator(cs).play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 and len(cs.player.exhaust_pile) == 1


# ---------------------------------------------------------------- Ghost Seed (GhostSeed.CanAffect)
def ghost_seed_player(keywords=None):
    return Player.from_dict({"max_hp": 80, "hp": 80, "block": 0, "status": [],
                             "hand": [bridge_card("STRIKE_IRONCLAD", keywords=keywords), bridge_card("BASH")],
                             "draw_pile": [bridge_card("DEFEND_IRONCLAD", "Skill", "Self")], "discard_pile": [],
                             "relics": [{"id": "GHOST_SEED", "counter": None, "status": "Normal"}]})

def test_ghost_seed_makes_basic_strikes_and_defends_ethereal():
    pl = ghost_seed_player()
    assert pl.hand[0].ethereal and pl.draw_pile[0].ethereal and not pl.hand[1].ethereal

def test_ghost_seed_agrees_with_bridge_keywords():
    assert ghost_seed_player(keywords=["Ethereal"]).hand[0].keywords == {CardKeyword.ETHEREAL}

def test_ghost_seed_strikes_exhaust_at_end_of_turn():
    cs = make_state([], enemy_count=1)
    cs.player = ghost_seed_player()
    cs.player.max_hp = cs.player.current_hp = 80
    CombatSimulator(cs).end_turn()
    assert [c.card_id for c in cs.player.exhaust_pile] == [CardId.STRIKE_IRONCLAD]
