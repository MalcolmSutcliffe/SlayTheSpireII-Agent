"""Mad Science (made by Tinker Time): a 1 energy Attack, Skill or Power with one of nine riders."""
import pytest

from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_card, make_state


def mad(card_type, rider, upgraded=False):
    c = make_card(CardId.MAD_SCIENCE, "Mad Science", card_type, 1, TargetType.AnyEnemy if card_type == CardType.Attack else TargetType.Self, upgraded)
    c.rider = rider
    return c


def play(cs, index=0, target=0):
    CombatSimulator(cs).play_card(index, target)


def test_sapping_hits_for_twelve_and_weakens_and_makes_vulnerable():
    cs = make_state([mad(CardType.Attack, "SAPPING")], enemy_count=1)
    play(cs)
    e = cs.enemies[0]
    assert e.current_hp == 28 and e.status_amount(StatusId.WEAK) == 2 and e.status_amount(StatusId.VULNERABLE) == 2


def test_violence_hits_three_times():
    cs = make_state([mad(CardType.Attack, "VIOLENCE")], enemy_count=1)
    play(cs)
    assert cs.enemies[0].current_hp == 40 - 36


def test_choking_makes_each_card_played_this_turn_cost_the_enemy_six_hp_until_the_turn_ends():
    from sts2_lite.Tests.card.test_card import thunderclap
    cs = make_state([mad(CardType.Attack, "CHOKING"), thunderclap()], enemy_count=1, enemy_hp=100)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    e = cs.enemies[0]
    assert e.status_amount(StatusId.STRANGLE) == 6
    hp = e.current_hp
    sim.play_card(0, 0)
    assert e.current_hp == hp - 4 - 6          # thunderclap's 4 damage, then the strangle
    sim.end_turn()
    assert e.status_amount(StatusId.STRANGLE) == 0


def test_energized_blocks_and_gives_two_energy():
    cs = make_state([mad(CardType.Skill, "ENERGIZED")], enemy_count=1)
    play(cs)
    assert cs.player.block == 8 and cs.energy == 3 - 1 + 2


def test_wisdom_blocks_and_draws_three():
    cs = make_state([mad(CardType.Skill, "WISDOM")], enemy_count=1)
    cs.player.draw_pile = [make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy) for _ in range(5)]
    play(cs)
    assert cs.player.block == 8 and len(cs.player.hand) == 3


def test_chaos_blocks_and_adds_a_free_card():
    cs = make_state([mad(CardType.Skill, "CHAOS")], enemy_count=1)
    play(cs)
    assert cs.player.block == 8 and len(cs.player.hand) == 1 and cs.player.hand[0].energy_cost == 0


def test_expertise_gives_two_strength_and_two_dexterity():
    cs = make_state([mad(CardType.Power, "EXPERTISE")], enemy_count=1)
    play(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == 2 and cs.player.status_amount(StatusId.DEXTERITY) == 2


def test_curious_makes_powers_cost_one_less():
    power = make_card(CardId.DEMON_FORM, "Demon Form", CardType.Power, 3, TargetType.Self)
    cs = make_state([mad(CardType.Power, "CURIOUS"), power], enemy_count=1)
    cs.player.draw_pile = [make_card(CardId.INFLAME, "Inflame", CardType.Power, 1, TargetType.Self)]
    play(cs)
    assert cs.player.hand[0].energy_cost == 2 and cs.player.draw_pile[0].energy_cost == 0


def test_improvement_leaves_a_status_the_run_reads_when_the_fight_ends():
    cs = make_state([mad(CardType.Power, "IMPROVEMENT")], enemy_count=1)
    play(cs)
    assert cs.player.status_amount(StatusId.IMPROVEMENT) == 1


def test_upgrading_gives_innate_and_the_rider_survives_copies_and_reading_from_the_bridge():
    up = mad(CardType.Attack, "VIOLENCE").upgraded_copy()
    assert up.is_upgraded and any(k.name == "INNATE" for k in up.keywords) and up.rider == "VIOLENCE"
    raw = {"id": "MAD_SCIENCE", "name": "Mad Science", "type": "Attack", "cost": 1, "can_play": True, "is_upgraded": False, "target_type": "AnyEnemy",
           "description": "Deal 12 damage 3 times."}
    assert Card.from_dict(raw).rider == "VIOLENCE"
    assert Card.from_dict(dict(raw, description="Gain 8 Block. Draw 3 cards.", type="Skill", target_type="Self")).rider == "WISDOM"
