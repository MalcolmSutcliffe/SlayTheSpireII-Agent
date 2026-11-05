"""Upgrading cards in the middle of a fight. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.card import Card, CardId, CardType, TargetType, UPGRADE_COST_CHANGE
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.player import Player
from sts2_lite.Tests.test_cards import make_card, make_state, play, hps


def strike(upgraded=False):
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy, upgraded)

def power(card_id, cost):
    return make_card(card_id, card_id.name.title(), CardType.Power, cost, TargetType.Self)


def test_upgraded_copy_is_marked_and_renamed():
    up = strike().upgraded_copy()
    assert up.is_upgraded and up.name == "Strike+"

def test_upgraded_copy_leaves_the_original_alone():
    c = strike()
    c.upgraded_copy()
    assert not c.is_upgraded and c.name == "Strike"

def test_upgraded_copy_keeps_the_rest_of_the_card():
    c = strike()
    up = c.upgraded_copy()
    assert (up.card_id, up.type, up.target_type, up.energy_cost, up.is_unplayable) == \
        (c.card_id, c.type, c.target_type, 1, False)

def test_name_does_not_gain_a_second_plus():
    c = strike()
    c.name = "Strike+"
    assert c.upgraded_copy().name == "Strike+"

def test_upgraded_card_hits_harder_when_played():
    cs = make_state([strike()], enemy_count=1, enemy_hp=100)
    cs.player.upgrade_card(cs.player.hand[0])
    play(cs)
    assert hps(cs) == [91]

@pytest.mark.parametrize("card_id", sorted(UPGRADE_COST_CHANGE, key=lambda c: c.name))
def test_cards_that_get_cheaper_when_upgraded(card_id):
    base = {CardId.BARRICADE: 3, CardId.CORRUPTION: 3, CardId.DARK_EMBRACE: 2, CardId.STAMPEDE: 2, CardId.UNMOVABLE: 2, CardId.HAVOC: 1,
            CardId.EXPECT_A_FIGHT: 2, CardId.INFERNAL_BLADE: 1, CardId.BODY_SLAM: 1, CardId.HELLRAISER: 2}[card_id]
    assert power(card_id, base).upgraded_copy().energy_cost == base - 1

def test_cost_never_goes_below_zero():
    assert power(CardId.UNMOVABLE, 0).upgraded_copy().energy_cost == 0

def test_x_cost_stays_x():
    c = make_card(CardId.WHIRLWIND, "Whirlwind", CardType.Attack, "X", TargetType.AllEnemies)
    assert c.upgraded_copy().energy_cost == "X"

def test_upgraded_cheaper_card_is_playable_with_less_energy():
    cs = make_state([power(CardId.BARRICADE, 3)], enemy_count=1)
    cs.energy = 2
    sim = CombatSimulator(cs)
    assert sim.get_available_actions() == [{"action": "end_turn"}]
    cs.player.upgrade_card(cs.player.hand[0])
    assert sim.get_available_actions()[0]["action"] == "play_card"

def test_cards_that_cannot_be_upgraded():
    assert not strike(upgraded=True).is_upgradable
    assert not Card.create_dazed().is_upgradable
    assert not Card.create_slimed().is_upgradable
    with pytest.raises(ValueError):
        strike(upgraded=True).upgraded_copy()
    with pytest.raises(ValueError):
        Card.create_wound().upgraded_copy()

def test_player_upgrade_replaces_the_card_where_it_sits():
    cs = make_state([strike(), strike()], enemy_count=1)
    p = cs.player
    p.draw_pile = [strike()]
    p.discard_pile = [strike()]
    p.exhaust_pile = [strike()]
    targets = [p.hand[1], p.draw_pile[0], p.discard_pile[0], p.exhaust_pile[0]]
    for t in targets:
        new = p.upgrade_card(t)
        assert new.is_upgraded and new is not t
    assert [c.is_upgraded for c in p.hand] == [False, True]
    assert p.draw_pile[0].is_upgraded and p.discard_pile[0].is_upgraded and p.exhaust_pile[0].is_upgraded

def test_upgrade_returns_none_for_unupgradable_or_missing_cards():
    cs = make_state([strike(upgraded=True)], enemy_count=1)
    assert cs.player.upgrade_card(cs.player.hand[0]) is None
    assert cs.player.upgrade_card(strike()) is None

def test_upgrade_does_not_leak_into_a_copied_state():
    cs = make_state([strike()], enemy_count=1)
    other = CombatState.deepcopy(cs)
    cs.player.upgrade_card(cs.player.hand[0])
    assert cs.player.hand[0].is_upgraded and not other.player.hand[0].is_upgraded
