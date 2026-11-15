"""Sloth (SlothPower): a card counts before it does anything, and an auto-play (Cascade) is held back by it like any other play."""
import pytest

from sts2_lite.card import CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, IllegalActionError
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_card, make_state, strike


def cascade():
    return make_card(CardId.CASCADE, "Cascade", CardType.Skill, "X", TargetType.Self)


def with_sloth(cs):
    cs.player.apply_status(StatusId.SLOTH, 3)
    return CombatSimulator(cs)


def test_cascade_and_its_cards_count_toward_sloth():
    cs = make_state([strike(), cascade()], enemy_count=1, enemy_hp=100)
    cs.player.draw_pile = [strike(), strike(), strike()]
    sim = with_sloth(cs)
    sim.play_card(0, 0)                  # 1st card
    sim.play_card(0, 0)                  # Cascade: the 2nd, with X = 2
    assert cs.sloth_played == 3          # ... and the first card it plays is the 3rd; the second is held back
    assert cs.enemies[0].current_hp == 100 - 2 * 6
    assert len(cs.player.draw_pile) == 1


def test_a_fourth_card_is_refused():
    cs = make_state([strike(), strike(), strike(), strike()], enemy_count=1)
    sim = with_sloth(cs)
    for _ in range(3):
        sim.play_card(0, 0)
    cs.energy = 3
    with pytest.raises(IllegalActionError):
        sim.play_card(0, 0)
