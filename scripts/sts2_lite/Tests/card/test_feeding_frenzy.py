"""Feeding Frenzy (event card, 0 energy Skill): 5 (7 upgraded) Strength this turn."""
from sts2_lite.card import CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_card, make_state


def frenzy(upgraded=False):
    return make_card(CardId.FEEDING_FRENZY, "Feeding Frenzy", CardType.Skill, 0, TargetType.Self, upgraded=upgraded) if "upgraded" in make_card.__code__.co_varnames else make_card(CardId.FEEDING_FRENZY, "Feeding Frenzy", CardType.Skill, 0, TargetType.Self)


def test_gives_five_strength_and_a_marker_that_takes_it_back():
    cs = make_state([frenzy()], enemy_count=1)
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.status_amount(StatusId.STRENGTH) == 5 and cs.player.status_amount(StatusId.FEEDING_FRENZY) == 5
    CombatSimulator._return_temporary_strength(cs.player)
    assert cs.player.status_amount(StatusId.STRENGTH) == 0 and cs.player.status_amount(StatusId.FEEDING_FRENZY) == 0
