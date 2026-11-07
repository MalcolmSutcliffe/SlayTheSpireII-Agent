"""Runic Pyramid, Toasty Mittens, History Course, Spiked Gauntlets, Philosopher's Stone.
Run from scripts/: python -m pytest sts2_lite/Tests"""
import json
from pathlib import Path

import pytest

from sts2_lite.card import CardId, CardKeyword, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy import Enemy
from sts2_lite.relic import RelicId, RelicInstance
from sts2_lite.status import StatusId
from sts2_lite.Tests.test_cards import hps
from sts2_lite.Tests.test_relics_always_on import card, strike, defend, inflame, state, relic, plays

RELICS = Path(__file__).parent / "data" / "relics"

LAST_FIVE = ["RUNIC_PYRAMID", "TOASTY_MITTENS", "HISTORY_COURSE", "SPIKED_GAUNTLETS", "PHILOSOPHERS_STONE"]

def draw_pile(cs, n=30):
    cs.player.draw_pile = [defend() for _ in range(n)]
    return cs

def names(pile):
    return [c.card_id.name for c in pile]


@pytest.mark.parametrize("bridge_id", LAST_FIVE)
def test_loads_from_the_bridge(bridge_id):
    assert RelicInstance.from_dict({"id": bridge_id, "counter": None}).relic_id == RelicId[bridge_id]


# ---------------------------------------------------------------- Runic Pyramid (ShouldFlush)
def test_runic_pyramid_keeps_the_hand():
    cs = draw_pile(state([strike(), defend()], RelicId.RUNIC_PYRAMID))
    CombatSimulator(cs).end_turn()
    assert cs.player.discard_pile == [] and len(cs.player.hand) == 2 + 5

def test_runic_pyramid_every_turn_not_just_the_first():
    cs = draw_pile(state([strike()], RelicId.RUNIC_PYRAMID))
    sim = CombatSimulator(cs)
    sim.end_turn(); sim.end_turn(); sim.end_turn()
    assert cs.player.discard_pile == [] and len(cs.player.hand) == 10          # the hand limit

def test_runic_pyramid_still_exhausts_ethereal_cards():
    cs = draw_pile(state([strike().with_keyword(CardKeyword.ETHEREAL), defend()], RelicId.RUNIC_PYRAMID))
    CombatSimulator(cs).end_turn()
    assert names(cs.player.exhaust_pile) == ["STRIKE_IRONCLAD"] and cs.player.discard_pile == []

def test_without_runic_pyramid_the_hand_is_discarded():
    cs = draw_pile(state([strike(), defend()]))
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == 5


# ---------------------------------------------------------------- Toasty Mittens (BeforeHandDraw)
def test_toasty_mittens_exhausts_the_top_card_and_gives_strength():
    cs = draw_pile(state([], RelicId.TOASTY_MITTENS), 10)
    cs.player.draw_pile[-1] = strike()                  # the top of the pile
    CombatSimulator(cs).end_turn()
    assert names(cs.player.exhaust_pile) == ["STRIKE_IRONCLAD"] and cs.player.status_amount(StatusId.STRENGTH) == 1
    assert len(cs.player.hand) == 5 and len(cs.player.draw_pile) == 4

def test_toasty_mittens_every_turn():
    cs = draw_pile(state([], RelicId.TOASTY_MITTENS))
    sim = CombatSimulator(cs)
    sim.end_turn(); sim.end_turn()
    assert len(cs.player.exhaust_pile) == 2 and cs.player.status_amount(StatusId.STRENGTH) == 2

def test_toasty_mittens_reshuffles_an_empty_draw_pile_first():
    cs = state([], RelicId.TOASTY_MITTENS)
    cs.player.draw_pile = []
    cs.player.discard_pile = [defend() for _ in range(8)]
    CombatSimulator(cs).end_turn()
    assert len(cs.player.exhaust_pile) == 1 and len(cs.player.hand) == 5

def test_toasty_mittens_fires_exhaust_triggers():
    cs = draw_pile(state([], RelicId.TOASTY_MITTENS, RelicId.FORGOTTEN_SOUL))
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [99]

def test_toasty_mittens_with_nothing_to_exhaust_still_gives_strength():
    cs = state([], RelicId.TOASTY_MITTENS)
    cs.player.draw_pile, cs.player.discard_pile = [], []
    CombatSimulator(cs).end_turn()
    assert cs.player.status_amount(StatusId.STRENGTH) == 1


# ---------------------------------------------------------------- History Course (AfterAutoPrePlayPhaseEntered)
def test_history_course_replays_last_turns_last_attack():
    cs = draw_pile(state([strike(), strike()], RelicId.HISTORY_COURSE))
    sim = plays(cs, (0, 0))
    sim.end_turn()
    assert hps(cs) == [100 - 6 - 6]

def test_history_course_replays_only_the_last_one():
    cs = draw_pile(state([strike(), defend()], RelicId.HISTORY_COURSE))
    sim = plays(cs, (0, 0), (0, 0))
    sim.end_turn()
    assert hps(cs) == [94] and cs.player.block == 5

def test_history_course_ignores_powers():
    cs = draw_pile(state([strike(), inflame()], RelicId.HISTORY_COURSE))
    sim = plays(cs, (0, 0), (0, 0))
    sim.end_turn()
    assert hps(cs) == [100 - 6 - 8]           # Inflame came last, but its Strength applies to the replayed Strike

def test_history_course_does_nothing_without_a_play():
    cs = draw_pile(state([], RelicId.HISTORY_COURSE))
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [100]

def test_history_course_dupe_goes_to_no_pile_and_is_not_replayed_again():
    cs = draw_pile(state([strike()], RelicId.HISTORY_COURSE))
    sim = plays(cs, (0, 0))
    sim.end_turn()
    discarded = names(cs.player.discard_pile)
    assert discarded.count("STRIKE_IRONCLAD") == 1 and relic(cs, RelicId.HISTORY_COURSE).triggering is None
    sim.end_turn()
    assert hps(cs) == [100 - 6 - 6]

def test_history_course_dupe_does_not_exhaust_or_use_energy():
    cs = draw_pile(state([card(CardId.TREMBLE, 1, CardType.Skill, TargetType.AnyEnemy)], RelicId.HISTORY_COURSE))
    sim = plays(cs, (0, 0))
    energy = cs.max_energy
    sim.end_turn()
    assert cs.energy == energy and names(cs.player.exhaust_pile) == ["TREMBLE"]

def test_history_course_dupe_keeps_the_x_of_the_original():
    whirlwind = card(CardId.WHIRLWIND, "X", CardType.Attack, TargetType.AllEnemies)
    cs = draw_pile(state([whirlwind], RelicId.HISTORY_COURSE))
    cs.energy = 2
    sim = plays(cs, (0, 0))
    assert hps(cs) == [100 - 2 * 5]
    sim.end_turn()
    assert hps(cs) == [100 - 2 * 5 - 2 * 5]             # the dupe has X = 2 though 3 energy is available

def test_history_course_kills_end_the_fight():
    cs = draw_pile(state([strike()], RelicId.HISTORY_COURSE, enemy_hp=12))
    sim = plays(cs, (0, 0))
    sim.end_turn()
    assert sim.is_over


# ---------------------------------------------------------------- Spiked Gauntlets (TryModifyEnergyCostInCombat)
def test_spiked_gauntlets_capture_costs_come_from_the_bridge():
    cs = CombatState.from_dict(json.loads((RELICS / "spiked_gauntlets.json").read_text()))
    inflame_card = next(c for c in cs.player.hand if c.card_id is CardId.INFLAME)
    assert RelicId.SPIKED_GAUNTLETS in cs.player.relics
    assert inflame_card.current_cost(cs.player) == 2          # 1 + the Gauntlets, as shown; not added again
    assert cs.max_energy == 4

def test_spiked_gauntlets_capture_inflame_spends_the_shown_cost():
    cs = CombatState.from_dict(json.loads((RELICS / "spiked_gauntlets.json").read_text()))
    sim = CombatSimulator(cs)
    index = next(i for i, c in enumerate(cs.player.hand) if c.card_id is CardId.INFLAME)
    sim.play_card(index, 0)
    assert cs.energy == 1

@pytest.mark.parametrize("relics, extra", [((), 0), ((RelicId.SPIKED_GAUNTLETS,), 1)])
def test_spiked_gauntlets_powers_made_by_stoke_cost_one_more(monkeypatch, relics, extra):
    import sts2_lite.card as card_module
    monkeypatch.setattr(card_module, "STOKE_POOL", [CardId.INFLAME])
    cs = state([card(CardId.STOKE, 1, CardType.Skill, TargetType.Self), defend()], *relics)
    CombatSimulator(cs).play_card(0, 0)
    made = next(c for c in cs.player.hand if c.card_id is CardId.INFLAME)
    assert made.energy_cost == 1 + extra


# ---------------------------------------------------------------- Philosopher's Stone (AfterCreatureAddedToCombat)
def test_philosophers_stone_strengthens_summoned_enemies():
    cs = state([], RelicId.PHILOSOPHERS_STONE)
    sim = CombatSimulator(cs)
    sim.summon(Enemy.spawn("EYE_WITH_TEETH", 0, 0))
    assert cs.enemies[-1].status_amount(StatusId.STRENGTH) == 1

def test_summoned_enemies_have_no_strength_without_the_relic():
    cs = state([])
    sim = CombatSimulator(cs)
    sim.summon(Enemy.spawn("EYE_WITH_TEETH", 0, 0))
    assert StatusId.STRENGTH not in cs.enemies[-1].status


# ---------------------------------------------------------------- Tangled shown by the bridge (capture)
def test_tangled_capture_attack_costs_are_not_counted_twice():
    path = Path(__file__).parent / "data" / "act1_overgrowth" / "vine_shambler" / "tangled.json"
    cs = CombatState.from_dict(json.loads(path.read_text()))
    strike_card = next(c for c in cs.player.hand if c.card_id is CardId.STRIKE_IRONCLAD)
    defend_card = next(c for c in cs.player.hand if c.card_id is CardId.DEFEND_IRONCLAD)
    assert strike_card.current_cost(cs.player) == 2 and defend_card.current_cost(cs.player) == 1     # as the bridge shows
    sim = CombatSimulator(cs)
    index = cs.player.hand.index(strike_card)
    energy = cs.energy
    sim.play_card(index, 0)
    assert cs.energy == energy - 2
