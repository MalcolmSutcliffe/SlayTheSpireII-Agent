import pytest
import json
from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType, EVENT_CARDS, INFERNAL_BLADE_POOL, GET_CARD_FUNCTION
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.status import StatusId, StatusInstance
from sts2_lite.Tests.card.test_card import make_card, make_state, hps
from sts2_lite.Tests.card.test_colorless import strike, defend
from pathlib import Path


def card(card_id, upgraded=False):
    name, kind, cost, target = EVENT_CARDS[card_id]
    return make_card(card_id, name, kind, cost, target, upgraded)

def one_enemy(hand, hp=100):
    return make_state(hand, enemy_count=1, enemy_hp=hp)

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim

def end_turn(cs):
    sim = CombatSimulator(cs)
    sim.end_turn()
    return sim

def costed(cost, card_id=CardId.BLUDGEON, card_type=CardType.Attack):
    return make_card(card_id, card_id.name, card_type, cost, TargetType.AnyEnemy)


# ------------------------------------------------------------ registration
def test_every_event_card_has_a_play_function_and_loads_from_the_bridge():
    for card_id, (name, kind, cost, target) in EVENT_CARDS.items():
        assert card_id in GET_CARD_FUNCTION
        loaded = Card.from_dict({"id": card_id.name, "type": kind.name, "name": name, "can_play": True, "cost": cost,
                                 "is_upgraded": False, "target_type": target.name})
        assert loaded.card_id == card_id

def test_exhaust_keywords():
    assert card(CardId.ENLIGHTENMENT).exhausts and card(CardId.METAMORPHOSIS).exhausts
    assert not any(card(c).exhausts for c in (CardId.BYRD_SWOOP, CardId.PECK, CardId.EXTERMINATE, CardId.SQUASH, CardId.TORIC_TOUGHNESS))


# ------------------------------------------------------------ attacks
def test_swoop_damage_and_cost():
    for upgraded, damage in ((False, 14), (True, 18)):
        cs = one_enemy([card(CardId.BYRD_SWOOP, upgraded)])
        play(cs)
        assert hps(cs) == [100 - damage] and cs.energy == 3

def test_swoop_uses_strength():
    cs = one_enemy([card(CardId.BYRD_SWOOP)])
    cs.player.apply_status(StatusId.STRENGTH, 3)
    play(cs)
    assert hps(cs) == [83]

def test_peck_hits_three_times_four_upgraded():
    for upgraded, total in ((False, 6), (True, 8)):
        cs = one_enemy([card(CardId.PECK, upgraded)])
        play(cs)
        assert hps(cs) == [100 - total] and cs.energy == 2

def test_peck_strength_applies_to_every_hit():
    cs = one_enemy([card(CardId.PECK)])
    cs.player.apply_status(StatusId.STRENGTH, 2)
    play(cs)
    assert hps(cs) == [88]

def test_exterminate_hits_every_enemy_four_times():
    for upgraded, per_enemy in ((False, 12), (True, 16)):
        cs = make_state([card(CardId.EXTERMINATE, upgraded)], enemy_count=2, enemy_hp=100)
        play(cs)
        assert hps(cs) == [100 - per_enemy] * 2 and cs.energy == 2

def test_exterminate_keeps_hitting_the_survivor():
    cs = make_state([card(CardId.EXTERMINATE)], enemy_count=2, enemy_hp=100)
    weak, strong = cs.enemies
    weak.current_hp = 5
    play(cs)                            # the dead one is removed from the list
    assert weak.current_hp <= 0 and strong.current_hp == 88 and cs.enemies == [strong]

def test_squash_damage_then_vulnerable():
    for upgraded, damage, vulnerable in ((False, 10, 2), (True, 12, 3)):
        cs = one_enemy([card(CardId.SQUASH, upgraded)])
        play(cs)
        assert hps(cs) == [100 - damage]
        assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == vulnerable

def test_squash_vulnerable_does_not_boost_its_own_hit():
    cs = one_enemy([card(CardId.SQUASH), card(CardId.BYRD_SWOOP)])
    sim = play(cs)
    assert hps(cs) == [90]
    sim.play_card(0, 0)
    assert hps(cs) == [90 - 21]          # Vulnerable: 14 * 1.5


# ------------------------------------------------------------ Enlightenment
def test_enlightenment_reduces_the_hand_to_one_this_turn():
    cs = one_enemy([card(CardId.ENLIGHTENMENT), costed(2), costed(3), costed(0), costed(1)])
    play(cs)
    assert [c.energy_cost for c in cs.player.hand] == [1, 1, 0, 1]
    assert cs.energy == 3 and cs.player.exhaust_pile[0].card_id == CardId.ENLIGHTENMENT

def test_enlightenment_wears_off_at_the_end_of_the_turn():
    cs = one_enemy([card(CardId.ENLIGHTENMENT), costed(2, CardId.BLUDGEON), costed(3, CardId.PYRE, CardType.Power)])
    play(cs)
    end_turn(cs)
    piles = cs.player.hand + cs.player.discard_pile + cs.player.draw_pile
    costs = {c.card_id: c.energy_cost for c in piles}
    assert costs[CardId.BLUDGEON] == 2 and costs[CardId.PYRE] == 3
    assert all(c.restore_cost is None for c in piles)

def test_upgraded_enlightenment_lasts_the_combat():
    cs = one_enemy([card(CardId.ENLIGHTENMENT, True), costed(2, CardId.BLUDGEON)])
    play(cs)
    end_turn(cs)
    piles = cs.player.hand + cs.player.discard_pile + cs.player.draw_pile
    assert [c.energy_cost for c in piles if c.card_id == CardId.BLUDGEON] == [1]

def test_enlightenment_never_raises_a_cost_and_leaves_x_alone():
    free = costed(3, CardId.BLUDGEON).free_this_turn()
    x = make_card(CardId.WHIRLWIND, "Whirlwind", CardType.Attack, "X", TargetType.AllEnemies)
    cs = one_enemy([card(CardId.ENLIGHTENMENT), free, x])
    play(cs)
    assert cs.player.hand[0].energy_cost == 0 and cs.player.hand[0].restore_cost == 3
    assert cs.player.hand[1].energy_cost == "X"

def test_upgraded_enlightenment_caps_a_temporary_cost_once_it_wears_off():
    """LocalCostModifier example: a 3-cost card at 0 this turn stays 0, then costs 1 (not 3) next turn."""
    free = costed(3, CardId.BLUDGEON).free_this_turn()
    cs = one_enemy([card(CardId.ENLIGHTENMENT, True), free])
    play(cs)
    assert cs.player.hand[0].energy_cost == 0 and cs.player.hand[0].restore_cost == 1
    end_turn(cs)
    piles = cs.player.hand + cs.player.discard_pile + cs.player.draw_pile
    assert [c.energy_cost for c in piles if c.card_id == CardId.BLUDGEON] == [1]

def test_enlightenment_does_not_touch_the_shared_card_objects():
    original = costed(3)
    cs = one_enemy([card(CardId.ENLIGHTENMENT), original])
    play(cs)
    assert original.energy_cost == 3 and cs.player.hand[0] is not original


# ------------------------------------------------------------ Metamorphosis
def test_metamorphosis_shuffles_free_attacks_into_the_draw_pile():
    for upgraded, count in ((False, 3), (True, 5)):
        cs = one_enemy([card(CardId.METAMORPHOSIS, upgraded)])
        cs.player.draw_pile = [defend() for _ in range(4)]
        play(cs)
        made = [c for c in cs.player.draw_pile if c.card_id != CardId.DEFEND_IRONCLAD]
        assert len(made) == count and len(cs.player.draw_pile) == 4 + count
        assert all(c.card_id in INFERNAL_BLADE_POOL and c.type == CardType.Attack for c in made)
        assert all(c.energy_cost in (0, "X") and c.restore_cost is None for c in made)
        assert cs.energy == 1 and cs.player.exhaust_pile[0].card_id == CardId.METAMORPHOSIS

def test_metamorphosis_cards_stay_free_after_the_turn():
    cs = one_enemy([card(CardId.METAMORPHOSIS)])
    cs.player.draw_pile = [defend() for _ in range(10)]
    play(cs)
    end_turn(cs)
    piles = cs.player.hand + cs.player.discard_pile + cs.player.draw_pile
    made = [c for c in piles if c.card_id in INFERNAL_BLADE_POOL]
    assert len(made) == 3 and all(c.energy_cost in (0, "X") for c in made)

def test_metamorphosis_can_repeat_a_card(monkeypatch):
    monkeypatch.setattr(rng, "choice", lambda seq: CardId.BLUDGEON if CardId.BLUDGEON in seq else seq[0])
    cs = one_enemy([card(CardId.METAMORPHOSIS)])
    play(cs)
    assert [c.card_id for c in cs.player.draw_pile] == [CardId.BLUDGEON] * 3

def test_generated_whirlwind_keeps_its_x_cost(monkeypatch):
    monkeypatch.setattr(rng, "choice", lambda seq: CardId.WHIRLWIND if CardId.WHIRLWIND in seq else seq[0])
    cs = one_enemy([card(CardId.METAMORPHOSIS)])
    play(cs)
    assert all(c.energy_cost == "X" for c in cs.player.draw_pile)
    blade = make_card(CardId.INFERNAL_BLADE, "Infernal Blade", CardType.Skill, 1, TargetType.Self)
    cs = one_enemy([blade])
    play(cs)
    assert cs.player.hand[0].card_id == CardId.WHIRLWIND and cs.player.hand[0].energy_cost == "X"

@pytest.mark.parametrize("index, known_after", [(0, 2), (3, 2), (4, 1), (5, 0)])
def test_random_insert_keeps_only_the_known_cards_above_it(monkeypatch, index, known_after):
    """Draw pile of 5 (top = end) with the top 2 known; inserting at `index` of 0..5."""
    cs = one_enemy([])
    cs.player.draw_pile = [defend() for _ in range(5)]
    cs.player.known_top = 2
    monkeypatch.setattr(rng, "randrange", lambda n: index)
    new = strike()
    cs.player.insert_into_draw_pile(new)
    assert cs.player.draw_pile[index] is new and cs.player.known_top == known_after


# ------------------------------------------------------------ Toric Toughness
def test_toric_toughness_blocks_now_and_for_the_next_two_turns():
    for upgraded, block in ((False, 5), (True, 7)):
        cs = one_enemy([card(CardId.TORIC_TOUGHNESS, upgraded)])
        play(cs)
        assert cs.player.block == block and cs.energy == 1
        assert cs.player.status_amount(StatusId.TORIC_TOUGHNESS) == 2
        end_turn(cs)
        assert cs.player.block == block and cs.player.status_amount(StatusId.TORIC_TOUGHNESS) == 1
        end_turn(cs)
        assert cs.player.block == block and StatusId.TORIC_TOUGHNESS not in cs.player.status
        end_turn(cs)
        assert cs.player.block == 0

def test_toric_toughness_repeats_the_modified_block_unpowered():
    cs = one_enemy([card(CardId.TORIC_TOUGHNESS)])
    cs.player.apply_status(StatusId.DEXTERITY, 2)
    play(cs)
    assert cs.player.block == 7
    cs.player.apply_status(StatusId.FRAIL, 3)           # later Frail does not shrink the stored block
    cs.player.status[StatusId.DEXTERITY].amount = 10
    end_turn(cs)
    assert cs.player.block == 7

def test_toric_toughness_adds_to_block_kept_by_barricade():
    cs = one_enemy([card(CardId.TORIC_TOUGHNESS)])
    cs.player.apply_status(StatusId.BARRICADE, 1)
    play(cs)
    end_turn(cs)
    assert cs.player.block == 10

def test_two_toric_toughness_copies_tick_separately():
    cs = one_enemy([card(CardId.TORIC_TOUGHNESS), card(CardId.TORIC_TOUGHNESS, True)])
    cs.energy = 4
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.block == 12 and cs.player.status[StatusId.TORIC_TOUGHNESS].records == [[2, 5], [2, 7]]
    end_turn(cs)
    assert cs.player.block == 12 and cs.player.status_amount(StatusId.TORIC_TOUGHNESS) == 2

def test_toric_toughness_power_loads_from_the_bridge():
    for text in ("At the start of your next 2 turns, gain 7 Block.", "At the start of your next 2 turns, gain [gold]7[/gold] Block."):
        inst = StatusInstance.from_dict({"id": "TORIC_TOUGHNESS_POWER", "amount": 2, "description": text})
        assert inst.status_id == StatusId.TORIC_TOUGHNESS and inst.records == [[2, 7]]
    inst = StatusInstance.from_dict({"id": "TORIC_TOUGHNESS_POWER", "amount": 1})
    assert inst.records == [[1, 5]]


CAPTURES = Path(__file__).parents[1] / "data" / "cards" / "colorless"

def tough_enemy(hand, hp=200):
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
    cs = tough_enemy([bludgeon().free_this_turn()])
    CombatSimulator(cs).play_card(0, 0)
    played, = everywhere(cs, CardId.BLUDGEON)
    assert cs.energy == 3 and (played.energy_cost, played.restore_cost, played.until_played) == (3, None, False)

def test_card_returned_to_hand_the_same_turn_costs_full_price():
    """Infernal Blade's free card, played, then pulled back with Neow's Fury: it costs 3 again."""
    fury = make_card(CardId.NEOWS_FURY, "Neow's Fury", CardType.Attack, 1, TargetType.AnyEnemy)
    cs = tough_enemy([bludgeon().free_this_turn(), fury])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    sim.choose_card(next(i for i, c in enumerate(cs.player.discard_pile) if c.card_id == CardId.BLUDGEON))
    back = next(c for c in cs.player.hand if c.card_id == CardId.BLUDGEON)
    assert back.energy_cost == 3 and not back.until_played

def test_enlightenment_discount_ends_when_the_card_is_played():
    cs = tough_enemy([event_card(CardId.ENLIGHTENMENT), bludgeon()])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.player.hand[0].energy_cost == 1 and cs.player.hand[0].until_played
    sim.play_card(0, 0)
    assert cs.energy == 2
    assert [c.energy_cost for c in everywhere(cs, CardId.BLUDGEON)] == [3]

def test_upgraded_enlightenment_survives_the_play():
    cs = tough_enemy([event_card(CardId.ENLIGHTENMENT, True), bludgeon()])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    played, = everywhere(cs, CardId.BLUDGEON)
    assert played.energy_cost == 1 and not played.until_played

def test_upgraded_enlightenment_on_a_free_card_leaves_it_at_one_after_the_play():
    cs = tough_enemy([event_card(CardId.ENLIGHTENMENT, True), bludgeon().free_this_turn()])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    played, = everywhere(cs, CardId.BLUDGEON)
    assert cs.energy == 3 and played.energy_cost == 1

def test_stomp_discount_is_kept_after_the_play():
    stomp = make_card(CardId.STOMP, "Stomp", CardType.Attack, 3, TargetType.AllEnemies).cheaper_this_turn(2)
    cs = tough_enemy([stomp])
    CombatSimulator(cs).play_card(0, 0)
    played, = everywhere(cs, CardId.STOMP)
    assert (played.energy_cost, played.restore_cost) == (1, 3)

def test_an_auto_played_card_gives_its_cost_back():
    free = bludgeon().free_this_turn()
    cs = tough_enemy([])
    cs.player.draw_pile = [defend(), free]
    CombatSimulator(cs).auto_play(free)
    played, = everywhere(cs, CardId.BLUDGEON)
    assert played.energy_cost == 3 and not played.until_played

def test_an_exhausting_free_card_is_reset_in_the_exhaust_pile():
    offering = make_card(CardId.SHRUG_IT_OFF, "Shrug It Off", CardType.Skill, 1, TargetType.Self).free_this_turn()
    cs = tough_enemy([offering])
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
        cs = tough_enemy([])
        _crossbow(CombatSimulator(cs), None)
        made = cs.player.hand[-1]
        assert made.until_played or made.energy_cost == "X"
    cs = tough_enemy([bludgeon(2)])
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


event_card = card
