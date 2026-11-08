"""Temporary costs that end when the card is played (SetThisTurnOrUntilPlayed), and the Toric Toughness capture.
Run from scripts/: python -m pytest sts2_lite/Tests"""
import json
from pathlib import Path

from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.status import StatusId
from test_cards import make_card, make_state
from test_colorless import defend
from test_event_cards import card as event_card

CAPTURES = Path(__file__).parent / "data" / "cards" / "colorless"

def one_enemy(hand, hp=200):
    return make_state(hand, enemy_count=1, enemy_hp=hp)

def bludgeon(cost=3):
    return make_card(CardId.BLUDGEON, "Bludgeon", CardType.Attack, cost, TargetType.AnyEnemy)

def everywhere(cs, card_id):
    p = cs.player
    return [c for c in p.hand + p.draw_pile + p.discard_pile + p.exhaust_pile if c.card_id == card_id]


def test_free_this_turn_is_marked_until_played():
    free = bludgeon().free_this_turn()
    assert (free.energy_cost, free.restore_cost, free.until_played) == (0, 3, True)
    assert bludgeon().cheaper_this_turn(1).until_played is False          # Stomp: AddThisTurn lasts the turn

def test_playing_a_free_card_gives_its_cost_back():
    cs = one_enemy([bludgeon().free_this_turn()])
    CombatSimulator(cs).play_card(0, 0)
    played, = everywhere(cs, CardId.BLUDGEON)
    assert cs.energy == 3 and (played.energy_cost, played.restore_cost, played.until_played) == (3, None, False)

def test_card_returned_to_hand_the_same_turn_costs_full_price():
    """Infernal Blade's free card, played, then pulled back with Neow's Fury: it costs 3 again."""
    fury = make_card(CardId.NEOWS_FURY, "Neow's Fury", CardType.Attack, 1, TargetType.AnyEnemy)
    cs = one_enemy([bludgeon().free_this_turn(), fury])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    sim.choose_card(next(i for i, c in enumerate(cs.player.discard_pile) if c.card_id == CardId.BLUDGEON))
    back = next(c for c in cs.player.hand if c.card_id == CardId.BLUDGEON)
    assert back.energy_cost == 3 and not back.until_played

def test_enlightenment_discount_ends_when_the_card_is_played():
    cs = one_enemy([event_card(CardId.ENLIGHTENMENT), bludgeon()])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.player.hand[0].energy_cost == 1 and cs.player.hand[0].until_played
    sim.play_card(0, 0)
    assert cs.energy == 2
    assert [c.energy_cost for c in everywhere(cs, CardId.BLUDGEON)] == [3]

def test_upgraded_enlightenment_survives_the_play():
    cs = one_enemy([event_card(CardId.ENLIGHTENMENT, True), bludgeon()])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    played, = everywhere(cs, CardId.BLUDGEON)
    assert played.energy_cost == 1 and not played.until_played

def test_upgraded_enlightenment_on_a_free_card_leaves_it_at_one_after_the_play():
    cs = one_enemy([event_card(CardId.ENLIGHTENMENT, True), bludgeon().free_this_turn()])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    played, = everywhere(cs, CardId.BLUDGEON)
    assert cs.energy == 3 and played.energy_cost == 1

def test_stomp_discount_is_kept_after_the_play():
    stomp = make_card(CardId.STOMP, "Stomp", CardType.Attack, 3, TargetType.AllEnemies).cheaper_this_turn(2)
    cs = one_enemy([stomp])
    CombatSimulator(cs).play_card(0, 0)
    played, = everywhere(cs, CardId.STOMP)
    assert (played.energy_cost, played.restore_cost) == (1, 3)

def test_an_auto_played_card_gives_its_cost_back():
    free = bludgeon().free_this_turn()
    cs = one_enemy([])
    cs.player.draw_pile = [defend(), free]
    CombatSimulator(cs).auto_play(free)
    played, = everywhere(cs, CardId.BLUDGEON)
    assert played.energy_cost == 3 and not played.until_played

def test_an_exhausting_free_card_is_reset_in_the_exhaust_pile():
    offering = make_card(CardId.SHRUG_IT_OFF, "Shrug It Off", CardType.Skill, 1, TargetType.Self).free_this_turn()
    cs = one_enemy([offering])
    cs.player.apply_status(StatusId.CORRUPTION, 1)          # Skills exhaust
    CombatSimulator(cs).play_card(0, 0)
    played, = cs.player.exhaust_pile
    assert played.energy_cost == 1 and not played.until_played

def test_until_played_is_part_of_the_signature():
    a = bludgeon().free_this_turn()
    b = Card.create_copy(a)
    b.until_played = False
    assert a.signature() != b.signature()

def test_crossbow_and_mummified_hand_freebies_are_until_played():
    from sts2_lite.relic import _crossbow, _mummified_hand
    for seed in range(5):                   # Crossbow's random Attack; Whirlwind would stay X
        cs = one_enemy([])
        _crossbow(CombatSimulator(cs), None)
        made = cs.player.hand[-1]
        assert made.until_played or made.energy_cost == "X"
    cs = one_enemy([bludgeon(2)])
    _mummified_hand(CombatSimulator(cs), None)
    assert cs.player.hand[0].energy_cost == 0 and cs.player.hand[0].until_played


# ------------------------------------------------------------ Toric Toughness: real capture (power just applied)
def test_toric_toughness_capture_loads_and_pays_out():
    raw = json.loads((CAPTURES / "toric_toughness.json").read_text())
    cs = CombatState.from_dict(raw)
    inst = cs.player.status[StatusId.TORIC_TOUGHNESS]
    assert inst.amount == 2 and inst.records == [[2, 5]] and cs.player.block == 5
    sim = CombatSimulator(cs)
    sim.end_turn()
    if not sim.is_over:
        assert cs.player.block >= 5 and cs.player.status_amount(StatusId.TORIC_TOUGHNESS) == 1
