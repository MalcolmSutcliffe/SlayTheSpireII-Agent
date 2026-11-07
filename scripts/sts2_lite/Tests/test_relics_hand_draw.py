"""Pael's Blood, Ring of the Drake, Pollinous Core, Fiddle, Snecko Eye (hand draw). Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.combat import CombatSimulator
from sts2_lite.relic import RelicId, RelicInstance
from sts2_lite.status import StatusId
from sts2_lite.Tests.test_relics_always_on import card, defend, state, relic, plays
from sts2_lite.card import CardId, CardType, TargetType

GROUP_3 = ["PAELS_BLOOD", "RING_OF_THE_DRAKE", "POLLINOUS_CORE", "FIDDLE", "SNECKO_EYE"]

def deck(cs):
    cs.player.draw_pile = [defend() for _ in range(40)]
    return cs

def hand_sizes(cs, turns):
    sim, sizes = CombatSimulator(deck(cs)), []
    for _ in range(turns):
        sim.end_turn()
        sizes.append(len(cs.player.hand))
    return sizes

def pommel_strike():
    return card(CardId.POMMEL_STRIKE, 1, CardType.Attack)


@pytest.mark.parametrize("bridge_id", GROUP_3)
def test_loads_from_the_bridge(bridge_id):
    assert RelicInstance.from_dict({"id": bridge_id, "counter": None}).relic_id == RelicId[bridge_id]

@pytest.mark.parametrize("relic_id, size", [(RelicId.PAELS_BLOOD, 6), (RelicId.SNECKO_EYE, 7), (RelicId.FIDDLE, 7)])
def test_fixed_hand_draw(relic_id, size):
    assert hand_sizes(state([], relic_id), 2) == [size, size]

def test_no_relic_draws_5():
    assert hand_sizes(state([]), 1) == [5]

def test_bonuses_stack():
    assert hand_sizes(state([], RelicId.PAELS_BLOOD, RelicId.FIDDLE), 1) == [8]


# ---------------------------------------------------------------- Ring of the Drake (TurnNumber <= 3)
def test_ring_of_the_drake_through_turn_3():
    assert hand_sizes(state([], RelicId.RING_OF_THE_DRAKE), 3) == [7, 7, 5]


# ---------------------------------------------------------------- Pollinous Core (TurnsSeen, every 4th turn)
def test_pollinous_core_every_4_turns():
    cs = state([], RelicId.POLLINOUS_CORE)
    relic(cs, RelicId.POLLINOUS_CORE).counter = 1          # turn 1 already seen
    assert hand_sizes(cs, 5) == [5, 5, 7, 5, 5]
    assert relic(cs, RelicId.POLLINOUS_CORE).counter == 2

def test_pollinous_core_flash_reading_of_4_is_0():
    cs = state([], RelicId.POLLINOUS_CORE)
    relic(cs, RelicId.POLLINOUS_CORE).counter = 4
    assert hand_sizes(cs, 1) == [5] and relic(cs, RelicId.POLLINOUS_CORE).counter == 1

def test_pollinous_core_bonus_is_one_turn():
    cs = state([], RelicId.POLLINOUS_CORE)
    relic(cs, RelicId.POLLINOUS_CORE).counter = 3
    assert hand_sizes(cs, 2) == [7, 5]


# ---------------------------------------------------------------- Fiddle (ShouldDraw: hand draw only)
def test_fiddle_blocks_card_draw():
    cs = deck(state([pommel_strike()], RelicId.FIDDLE))
    plays(cs, (0, 0))
    assert cs.player.hand == []

def test_fiddle_blocks_relic_draw():
    cs = deck(state([card(CardId.INFLAME, 1, CardType.Power, TargetType.Self)], RelicId.FIDDLE, RelicId.GAME_PIECE))
    plays(cs, (0, 0))
    assert cs.player.hand == []

def test_without_fiddle_cards_draw():
    cs = deck(state([pommel_strike()]))
    plays(cs, (0, 0))
    assert len(cs.player.hand) == 1
