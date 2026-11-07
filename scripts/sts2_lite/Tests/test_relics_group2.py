"""Sai, Mr. Struggles, Pael's Tears, Pael's Flesh, Lost Wisp, Forgotten Soul, Iron Club, Hand Drill, The Boot,
Fake Orichalcum, Fake Strike Dummy, Fake Happy Flower. Run from scripts/: python -m pytest sts2_lite/Tests"""
import json
from pathlib import Path

import pytest

from sts2_lite.card import CardId, CardKeyword, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.relic import RelicId, RelicInstance
from sts2_lite.status import StatusId
from sts2_lite.Tests.test_cards import hps
from sts2_lite.Tests.test_relics_always_on import (card, strike, twin_strike, defend, inflame, state, relic,
                                                   enemy_attack, plays)

RELICS = Path(__file__).parent / "data" / "relics"

GROUP_2 = ["SAI", "MR_STRUGGLES", "PAELS_TEARS", "PAELS_FLESH", "LOST_WISP", "FORGOTTEN_SOUL", "IRON_CLUB",
           "HAND_DRILL", "THE_BOOT", "FAKE_ORICHALCUM", "FAKE_STRIKE_DUMMY", "FAKE_HAPPY_FLOWER"]

def next_turn(cs):
    cs.player.draw_pile = [defend() for _ in range(20)]
    sim = CombatSimulator(cs)
    sim.end_turn()
    return sim

def true_grit():
    return card(CardId.TRUE_GRIT, 1, CardType.Skill, TargetType.Self)

def thunderclap():
    return card(CardId.THUNDERCLAP, 1, CardType.Attack, TargetType.AllEnemies)


@pytest.mark.parametrize("bridge_id", GROUP_2)
def test_loads_from_the_bridge(bridge_id):
    assert RelicInstance.from_dict({"id": bridge_id, "counter": None}).relic_id == RelicId[bridge_id]


# ---------------------------------------------------------------- Sai (AfterSideTurnStart, unpowered)
def test_sai_gives_7_block_each_turn():
    cs = state([], RelicId.SAI)
    next_turn(cs)
    assert cs.player.block == 7

def test_sai_block_ignores_dexterity_and_frail():
    cs = state([], RelicId.SAI)
    cs.player.apply_status(StatusId.DEXTERITY, 3)
    cs.player.apply_status(StatusId.FRAIL, 3)
    next_turn(cs)
    assert cs.player.block == 7


# ---------------------------------------------------------------- Mr. Struggles (AfterPlayerTurnStart)
def test_mr_struggles_deals_the_turn_number_to_all():
    cs = state([], RelicId.MR_STRUGGLES, enemies=2)
    sim = next_turn(cs)
    assert hps(cs) == [98, 98]
    sim.end_turn()
    assert hps(cs) == [95, 95]

def test_mr_struggles_ignores_vulnerable():
    cs = state([], RelicId.MR_STRUGGLES)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 5)
    next_turn(cs)
    assert hps(cs) == [98]


# ---------------------------------------------------------------- Pael's Tears (BeforeSideTurnEnd / AfterSideTurnStart)
def test_paels_tears_gives_2_energy_after_leftover():
    cs = state([], RelicId.PAELS_TEARS)
    next_turn(cs)
    assert cs.energy == 5

def test_paels_tears_nothing_without_leftover():
    cs = state([], RelicId.PAELS_TEARS)
    cs.energy = 0
    next_turn(cs)
    assert cs.energy == 3

def test_paels_tears_checks_each_turn():
    cs = state([], RelicId.PAELS_TEARS)
    sim = next_turn(cs)
    cs.energy = 0
    sim.end_turn()
    assert cs.energy == 3


# ---------------------------------------------------------------- Pael's Flesh (ModifyMaxEnergy, TurnNumber >= 3)
def test_paels_flesh_adds_max_energy_from_turn_3():
    cs = state([], RelicId.PAELS_FLESH)
    sim = next_turn(cs)
    assert cs.turn_number == 2 and cs.max_energy == 3
    sim.end_turn()
    assert cs.turn_number == 3 and cs.max_energy == cs.energy == 4
    sim.end_turn()
    assert cs.max_energy == 4

def test_paels_flesh_and_bread_stack():
    cs = state([], RelicId.PAELS_FLESH, RelicId.BREAD)
    sim = next_turn(cs)
    sim.end_turn()
    assert cs.max_energy == 5


# ---------------------------------------------------------------- Lost Wisp (AfterCardPlayed, Power)
def test_lost_wisp_hits_all_for_8_on_a_power():
    cs = state([inflame()], RelicId.LOST_WISP, enemies=2)
    plays(cs, (0, 0))
    assert hps(cs) == [92, 92]

def test_lost_wisp_ignores_other_cards():
    cs = state([defend()], RelicId.LOST_WISP)
    plays(cs, (0, 0))
    assert hps(cs) == [100]

def test_lost_wisp_is_unpowered():
    cs = state([inflame()], RelicId.LOST_WISP)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    plays(cs, (0, 0))
    assert hps(cs) == [92]


# ---------------------------------------------------------------- Forgotten Soul (AfterCardExhausted)
def test_forgotten_soul_deals_1_per_exhaust():
    cs = state([true_grit(), strike(), strike()], RelicId.FORGOTTEN_SOUL)
    plays(cs, (0, 0))
    assert hps(cs) == [99]

def test_forgotten_soul_on_ethereal_exhaust():
    cs = state([strike().with_keyword(CardKeyword.ETHEREAL)], RelicId.FORGOTTEN_SOUL)
    next_turn(cs)
    assert hps(cs) == [99]

def test_forgotten_soul_hits_one_enemy():
    cs = state([true_grit(), strike(), strike()], RelicId.FORGOTTEN_SOUL, enemies=3)
    plays(cs, (0, 0))
    assert sorted(hps(cs)) == [99, 100, 100]


# ---------------------------------------------------------------- Iron Club (AfterCardPlayed, CardsPlayed % 4)
def test_iron_club_draws_on_every_4th_card():
    cs = state([defend() for _ in range(5)], RelicId.IRON_CLUB)
    cs.energy = 10
    cs.player.draw_pile = [strike() for _ in range(5)]
    plays(cs, (0, 0), (0, 0), (0, 0))
    assert len(cs.player.hand) == 2 and relic(cs, RelicId.IRON_CLUB).counter == 3
    plays(cs, (0, 0))
    assert len(cs.player.hand) == 2 and relic(cs, RelicId.IRON_CLUB).counter == 0

def test_iron_club_counter_carries_across_turns():
    cs = state([defend()], RelicId.IRON_CLUB)
    relic(cs, RelicId.IRON_CLUB).counter = 3
    cs.player.draw_pile = [strike()]
    plays(cs, (0, 0))
    assert [c.card_id for c in cs.player.hand] == [CardId.STRIKE_IRONCLAD]

def test_iron_club_flash_reading_of_4_is_0():
    cs = state([defend()], RelicId.IRON_CLUB)
    relic(cs, RelicId.IRON_CLUB).counter = 4
    plays(cs, (0, 0))
    assert relic(cs, RelicId.IRON_CLUB).counter == 1 and cs.player.hand == []


# ---------------------------------------------------------------- Hand Drill (AfterDamageGiven, WasBlockBroken)
def test_hand_drill_applies_2_vulnerable_on_block_break():
    cs = state([strike()], RelicId.HAND_DRILL)
    cs.enemies[0].block = 4
    plays(cs, (0, 0))
    assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == 2 and hps(cs) == [98]

def test_hand_drill_exact_block_counts_as_broken():
    cs = state([strike()], RelicId.HAND_DRILL)
    cs.enemies[0].block = 6
    plays(cs, (0, 0))
    assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == 2 and hps(cs) == [100]

def test_hand_drill_not_without_block_or_if_block_holds():
    cs = state([strike(), strike()], RelicId.HAND_DRILL, enemies=2)
    cs.enemies[1].block = 10
    plays(cs, (0, 0), (0, 1))
    assert StatusId.VULNERABLE not in cs.enemies[0].status and StatusId.VULNERABLE not in cs.enemies[1].status

def test_hand_drill_later_hits_are_vulnerable():
    cs = state([twin_strike()], RelicId.HAND_DRILL)
    cs.enemies[0].block = 5
    plays(cs, (0, 0))
    assert hps(cs) == [100 - int(5 * 1.5)]

def test_hand_drill_on_relic_damage():
    cs = state([inflame()], RelicId.HAND_DRILL, RelicId.LOST_WISP)
    cs.enemies[0].block = 3
    plays(cs, (0, 0))
    assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == 2

def test_hand_drill_not_doubled_by_lamp():
    cs = state([strike()], RelicId.HAND_DRILL, RelicId.UNSETTLING_LAMP)
    cs.enemies[0].block = 1
    plays(cs, (0, 0))
    assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == 2 and not relic(cs, RelicId.UNSETTLING_LAMP).used

def test_hand_drill_triggers_vicious():
    cs = state([strike()], RelicId.HAND_DRILL)
    cs.enemies[0].block = 1
    cs.player.apply_status(StatusId.VICIOUS, 1)
    cs.player.draw_pile = [defend()]
    plays(cs, (0, 0))
    assert len(cs.player.hand) == 1

def test_hand_drill_ignores_enemy_attacks():
    cs = state([], RelicId.HAND_DRILL)
    cs.player.block = 3
    enemy_attack(cs, 5)
    next_turn(cs)
    assert StatusId.VULNERABLE not in cs.player.status


# ---------------------------------------------------------------- The Boot (ModifyHpLostAfterOstyLate)
def test_the_boot_raises_small_attack_hp_loss_to_5():
    cs = state([strike()], RelicId.THE_BOOT)
    cs.enemies[0].block = 4
    plays(cs, (0, 0))
    assert hps(cs) == [95]

def test_the_boot_ignores_fully_blocked_and_big_hits():
    cs = state([strike(), strike()], RelicId.THE_BOOT, enemies=2)
    cs.enemies[0].block = 6
    plays(cs, (0, 0), (0, 1))
    assert hps(cs) == [100, 94]

def test_the_boot_applies_per_hit():
    cs = state([card(CardId.SWORD_BOOMERANG, 1, CardType.Attack, TargetType.RandomEnemy)], RelicId.THE_BOOT)
    plays(cs, (0, 0))
    assert hps(cs) == [100 - 3 * 5]

def test_the_boot_ignores_unpowered_damage():
    cs = state([inflame()], RelicId.THE_BOOT, RelicId.FORGOTTEN_SOUL, RelicId.LOST_WISP)
    cs.enemies[0].block = 5
    plays(cs, (0, 0))
    assert hps(cs) == [97]

def test_the_boot_does_not_protect_the_player():
    cs = state([], RelicId.THE_BOOT)
    enemy_attack(cs, 2)
    next_turn(cs)
    assert cs.player.current_hp == 48


# ---------------------------------------------------------------- Fake Orichalcum / Fake Strike Dummy / Fake Happy Flower
def test_fake_orichalcum_gives_3_without_block():
    cs = state([], RelicId.FAKE_ORICHALCUM)
    enemy_attack(cs, 10)
    next_turn(cs)
    assert cs.player.current_hp == 50 - 7

def test_fake_orichalcum_not_with_block():
    cs = state([defend()], RelicId.FAKE_ORICHALCUM)
    enemy_attack(cs, 10)
    sim = plays(cs, (0, 0))
    sim.end_turn()
    assert cs.player.current_hp == 50 - 5

def test_fake_and_real_orichalcum_stack():
    cs = state([], RelicId.FAKE_ORICHALCUM, RelicId.ORICHALCUM)
    enemy_attack(cs, 10)
    next_turn(cs)
    assert cs.player.current_hp == 50 - 1

def test_fake_strike_dummy_adds_1_to_strikes():
    cs = state([strike(), card(CardId.BASH, 2, CardType.Attack)], RelicId.FAKE_STRIKE_DUMMY)
    plays(cs, (0, 0), (0, 0))
    assert hps(cs) == [100 - 7 - 8]

def test_fake_strike_dummy_stacks_with_strike_dummy():
    cs = state([strike()], RelicId.FAKE_STRIKE_DUMMY, RelicId.STRIKE_DUMMY)
    plays(cs, (0, 0))
    assert hps(cs) == [100 - 10]

def test_fake_happy_flower_every_5_turns():
    cs = state([], RelicId.FAKE_HAPPY_FLOWER)
    relic(cs, RelicId.FAKE_HAPPY_FLOWER).counter = 1        # turn 1 already seen
    sim = next_turn(cs)
    energies = [cs.energy]
    for _ in range(5):
        sim.end_turn()
        energies.append(cs.energy)
    assert energies == [3, 3, 3, 4, 3, 3]

def test_fake_happy_flower_flash_reading_of_5_is_0():
    cs = state([], RelicId.FAKE_HAPPY_FLOWER)
    relic(cs, RelicId.FAKE_HAPPY_FLOWER).counter = 5
    next_turn(cs)
    assert relic(cs, RelicId.FAKE_HAPPY_FLOWER).counter == 1 and cs.energy == 3

def test_happy_flower_still_every_3_turns():
    cs = state([], RelicId.HAPPY_FLOWER)
    relic(cs, RelicId.HAPPY_FLOWER).counter = 1
    sim = next_turn(cs)
    sim.end_turn()
    assert cs.energy == 4


# ---------------------------------------------------------------- captures (after-states, rewound to the play)
def rewind(name, card_id, enemy, hp, block=0, status=()):
    """Undo the last play: `card_id` back to hand from discard, 1 energy back, the target's state before the hit."""
    d = json.loads((RELICS / f"{name}.json").read_text())
    after = [e["hp"] for e in d["enemies"]], d["enemies"][enemy]["status"]
    discard = d["player"]["discard_pile"]
    index = max(i for i, c in enumerate(discard) if c["id"] == card_id)
    d["player"]["hand"].append(discard.pop(index))
    d["energy"] += 1
    d["enemies"][enemy].update(hp=hp, block=block, status=list(status))
    cs = CombatState.from_dict(d)
    return cs, len(cs.player.hand) - 1, after

def test_twin_strike_capture_exact_break_then_vulnerable_second_hit():
    # Nibbit had 5 block from Slice: hit 1 breaks it exactly (0 HP), hit 2 deals 5 * 1.5
    cs, card, (hp_after, status_after) = rewind("hand_drill_twin_strike", "TWIN_STRIKE", 0, hp=43, block=5)
    CombatSimulator(cs).play_card(card, 0)
    assert hps(cs) == hp_after == [36, 42]
    assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == status_after[0]["amount"] == 2

def test_slippery_then_boot_capture():
    # Slippery makes the Strike's loss 1, then The Boot makes it 5 (11 -> 6)
    slippery = {"id": "SLIPPERY_POWER", "name": "Slippery", "amount": 1, "type": "Buff"}
    cs, card, (hp_after, status_after) = rewind("slippery_boot", "STRIKE_IRONCLAD", 0, hp=11, status=[slippery])
    CombatSimulator(cs).play_card(card, 0)
    assert hps(cs) == hp_after == [6, 16, 14]
    assert StatusId.SLIPPERY not in cs.enemies[0].status and status_after == []
