"""Intangible (IntangiblePower.ModifyHpLostAfterOsty): every HP loss is at most 1, not just damage from attacks."""
from sts2_lite.card import CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_card, make_state


def offering():
    return make_card(CardId.OFFERING, "Offering", CardType.Skill, 0, TargetType.Self)


def bloodletting():
    return make_card(CardId.BLOODLETTING, "Bloodletting", CardType.Skill, 0, TargetType.Self)


def test_offering_costs_one_hp_while_intangible():
    cs = make_state([offering()], enemy_count=1)
    cs.player.apply_status(StatusId.INTANGIBLE, 1)
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.current_hp == 49


def test_bloodletting_costs_one_hp_while_intangible_and_three_without():
    for intangible, lost in ((True, 1), (False, 3)):
        cs = make_state([bloodletting()], enemy_count=1)
        if intangible:
            cs.player.apply_status(StatusId.INTANGIBLE, 1)
        CombatSimulator(cs).play_card(0, 0)
        assert cs.player.current_hp == 50 - lost


def test_a_loss_of_zero_stays_zero():
    cs = make_state([], enemy_count=1)
    cs.player.apply_status(StatusId.INTANGIBLE, 1)
    cs.player.lose_hp(0)
    assert cs.player.current_hp == 50
