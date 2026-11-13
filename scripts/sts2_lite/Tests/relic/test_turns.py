import pytest
from sts2_lite.combat import CombatSimulator
from sts2_lite.events import EventType
from sts2_lite.relic import RelicId, RelicInstance
from sts2_lite.status import StatusId
from sts2_lite.Tests.relic.test_always_on import defend, strike, inflame, relic, state
from sts2_lite.Tests.relic.test_counters import draw_pile, status, with_counter


def on_turn(turn, *relic_ids, hand=None, enemies=1, enemy_hp=100):
    """A state in the middle of turn `turn`, with enough cards to draw for the next ones."""
    cs = draw_pile(state(hand if hand is not None else [defend()], *relic_ids, enemies=enemies, enemy_hp=enemy_hp))
    cs.turn_number = turn
    return cs

def next_turn(cs):
    CombatSimulator(cs).end_turn()
    return cs

def hps(cs):
    return [e.current_hp for e in cs.enemies]


# ---------------------------------------------------------------- turns that are not modelled
@pytest.mark.parametrize("name", ["LANTERN", "AKABEKO", "ANCHOR", "VERY_HOT_COCOA", "BOOMING_CONCH", "FESTIVE_POPPER",
                                  "BELLOWS", "BONE_TEA", "GAMBLING_CHIP", "BLOOD_VIAL", "BAG_OF_PREPARATION", "VENERABLE_TEA_SET"])
def test_a_relic_that_only_acts_on_turn_one_is_left_out(name):
    assert RelicInstance.from_dict({"id": name, "counter": None, "status": "Normal"}) is None


# ---------------------------------------------------------------- energy
def test_candelabra_gives_energy_on_turn_two_only():
    cs = next_turn(on_turn(1, RelicId.CANDELABRA))
    assert cs.turn_number == 2 and cs.energy == cs.max_energy + 2
    cs = next_turn(on_turn(2, RelicId.CANDELABRA))
    assert cs.energy == cs.max_energy

def test_chandelier_gives_energy_on_turn_three_only():
    assert next_turn(on_turn(2, RelicId.CHANDELIER)).energy == 3 + 3
    assert next_turn(on_turn(1, RelicId.CHANDELIER)).energy == 3
    assert next_turn(on_turn(3, RelicId.CHANDELIER)).energy == 3

def test_happy_flower_gives_energy_on_the_third_turn():
    cs = with_counter(on_turn(2, RelicId.HAPPY_FLOWER), RelicId.HAPPY_FLOWER, 2)
    next_turn(cs)
    assert cs.energy == cs.max_energy + 1 and relic(cs, RelicId.HAPPY_FLOWER).counter == 0

@pytest.mark.parametrize("counter, expected", [(0, 1), (1, 2), (3, 1)])      # 3: read while the relic was flashing, which is 0
def test_happy_flower_counts_the_turns_in_between(counter, expected):
    cs = with_counter(on_turn(2, RelicId.HAPPY_FLOWER), RelicId.HAPPY_FLOWER, counter)
    next_turn(cs)
    assert cs.energy == cs.max_energy and relic(cs, RelicId.HAPPY_FLOWER).counter == expected

def test_happy_flower_pays_every_three_turns():
    cs = with_counter(on_turn(1, RelicId.HAPPY_FLOWER), RelicId.HAPPY_FLOWER, 1)
    paid = []
    for _ in range(6):
        next_turn(cs)
        paid.append(cs.energy - cs.max_energy)
    assert paid == [0, 1, 0, 0, 1, 0]


# ---------------------------------------------------------------- block and strength on one turn
def test_horn_cleat_gives_block_on_turn_two_only():
    assert next_turn(on_turn(1, RelicId.HORN_CLEAT)).player.block == 14
    assert next_turn(on_turn(2, RelicId.HORN_CLEAT)).player.block == 0

def test_captains_wheel_gives_block_on_turn_three_only():
    assert next_turn(on_turn(2, RelicId.CAPTAINS_WHEEL)).player.block == 18
    assert next_turn(on_turn(3, RelicId.CAPTAINS_WHEEL)).player.block == 0

def test_the_block_of_horn_cleat_and_captains_wheel_is_not_changed_by_dexterity_or_frail():
    cs = on_turn(1, RelicId.HORN_CLEAT)
    cs.player.apply_status(StatusId.DEXTERITY, 5)
    cs.player.apply_status(StatusId.FRAIL, 2)
    assert next_turn(cs).player.block == 14

def test_sparkling_rouge_gives_strength_and_dexterity_on_turn_three_only():
    cs = next_turn(on_turn(2, RelicId.SPARKLING_ROUGE))
    assert status(cs, StatusId.STRENGTH) == 1 and status(cs, StatusId.DEXTERITY) == 1
    cs = next_turn(on_turn(1, RelicId.SPARKLING_ROUGE))
    assert status(cs, StatusId.STRENGTH) == 0 and status(cs, StatusId.DEXTERITY) == 0

def test_turn_relics_stack_on_the_same_turn():
    cs = next_turn(on_turn(1, RelicId.CANDELABRA, RelicId.HORN_CLEAT))
    assert cs.energy == cs.max_energy + 2 and cs.player.block == 14


# ---------------------------------------------------------------- every turn
def test_mercury_hourglass_hurts_every_enemy_each_turn():
    cs = on_turn(1, RelicId.MERCURY_HOURGLASS, enemies=2)
    next_turn(cs)
    assert hps(cs) == [97, 97]
    next_turn(cs)
    assert hps(cs) == [94, 94]

def test_mercury_hourglass_ignores_vulnerable():
    cs = on_turn(1, RelicId.MERCURY_HOURGLASS)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 3)
    assert hps(next_turn(cs)) == [97]

def test_mercury_hourglass_can_win_the_fight():
    cs = on_turn(1, RelicId.MERCURY_HOURGLASS, enemy_hp=3)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert sim.is_over and not cs.enemies

def test_brimstone_gives_everyone_strength_each_turn():
    cs = on_turn(1, RelicId.BRIMSTONE, enemies=2)
    next_turn(cs)
    assert status(cs, StatusId.STRENGTH) == 2
    assert [e.status_amount(StatusId.STRENGTH) for e in cs.enemies] == [1, 1]
    next_turn(cs)
    assert status(cs, StatusId.STRENGTH) == 4
    assert [e.status_amount(StatusId.STRENGTH) for e in cs.enemies] == [2, 2]

def test_brimstone_skips_dead_enemies():
    cs = on_turn(1, RelicId.BRIMSTONE, enemies=2)
    cs.enemies[1].current_hp = 0
    next_turn(cs)
    assert [e.status_amount(StatusId.STRENGTH) for e in cs.enemies if e.current_hp > 0] == [1]


# ---------------------------------------------------------------- the end of the turn
def end_phase(cs):
    sim = CombatSimulator(cs)
    sim.fire(EventType.PLAY_PHASE_END)
    sim.fire(EventType.END_TURN)
    return cs

def test_stone_calendar_hurts_everyone_at_the_end_of_turn_seven():
    cs = end_phase(on_turn(7, RelicId.STONE_CALENDAR, enemies=2, enemy_hp=100))
    assert hps(cs) == [48, 48]

@pytest.mark.parametrize("turn", [1, 6, 8])
def test_stone_calendar_does_nothing_on_other_turns(turn):
    assert hps(end_phase(on_turn(turn, RelicId.STONE_CALENDAR))) == [100]

def test_stone_calendar_ignores_vulnerable_and_can_win_the_fight():
    cs = on_turn(7, RelicId.STONE_CALENDAR, enemy_hp=52)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 3)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert sim.is_over

def test_stone_calendar_in_a_full_run_of_turns():
    cs = on_turn(1, RelicId.STONE_CALENDAR, enemy_hp=100)
    sim = CombatSimulator(cs)
    for _ in range(6):
        sim.end_turn()
    assert cs.turn_number == 7 and hps(cs) == [100]
    sim.end_turn()
    assert hps(cs) == [48]

def test_orichalcum_gives_block_when_there_is_none():
    assert end_phase(on_turn(1, RelicId.ORICHALCUM)).player.block == 6

def test_orichalcum_does_nothing_when_there_is_block():
    cs = on_turn(1, RelicId.ORICHALCUM)
    cs.player.block = 1
    assert end_phase(cs).player.block == 1

def test_orichalcum_looks_before_plating_gives_block():
    cs = on_turn(1, RelicId.ORICHALCUM)
    cs.player.apply_status(StatusId.PLATING, 3)
    assert end_phase(cs).player.block == 3 + 6

def test_orichalcum_asks_again_every_turn():
    cs = on_turn(1, RelicId.ORICHALCUM)
    cs.player.block = 4
    end_phase(cs)
    cs.player.block = 0
    end_phase(cs)
    assert cs.player.block == 6

def test_cloak_clasp_gives_a_block_for_each_card_in_hand():
    cs = on_turn(1, RelicId.CLOAK_CLASP, hand=[defend(), defend(), strike()])
    assert end_phase(cs).player.block == 3

def test_cloak_clasp_with_an_empty_hand_gives_nothing():
    assert end_phase(on_turn(1, RelicId.CLOAK_CLASP, hand=[])).player.block == 0

def test_cloak_clasp_block_is_not_changed_by_dexterity():
    cs = on_turn(1, RelicId.CLOAK_CLASP, hand=[defend(), defend()])
    cs.player.apply_status(StatusId.DEXTERITY, 4)
    assert end_phase(cs).player.block == 2

def test_screaming_flagon_hurts_everyone_when_the_hand_is_empty():
    cs = end_phase(on_turn(1, RelicId.SCREAMING_FLAGON, hand=[], enemies=2))
    assert hps(cs) == [80, 80]

def test_screaming_flagon_does_nothing_with_a_card_left():
    assert hps(end_phase(on_turn(1, RelicId.SCREAMING_FLAGON, hand=[defend()]))) == [100]

def test_screaming_flagon_after_playing_the_last_card():
    cs = on_turn(1, RelicId.SCREAMING_FLAGON, hand=[defend()])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.end_turn()
    assert hps(cs) == [80]

def test_parrying_shield_hurts_an_enemy_with_ten_block():
    cs = on_turn(1, RelicId.PARRYING_SHIELD)
    cs.player.block = 10
    next_turn(cs)
    assert hps(cs) == [94]

def test_parrying_shield_needs_ten_block():
    cs = on_turn(1, RelicId.PARRYING_SHIELD)
    cs.player.block = 9
    assert hps(next_turn(cs)) == [100]

def test_parrying_shield_hurts_one_of_several_enemies():
    cs = on_turn(1, RelicId.PARRYING_SHIELD, enemies=3)
    cs.player.block = 20
    next_turn(cs)
    assert sorted(hps(cs)) == [94, 100, 100]

def test_parrying_shield_counts_the_block_from_end_of_turn_relics():
    cs = on_turn(1, RelicId.PARRYING_SHIELD, RelicId.ORICHALCUM, RelicId.CLOAK_CLASP, hand=[defend()] * 4)
    cs.player.block = 0
    next_turn(cs)
    assert hps(cs) == [94]                                  # Orichalcum 6, then Cloak Clasp 4

def test_parrying_shield_can_win_the_fight():
    cs = on_turn(1, RelicId.PARRYING_SHIELD, enemy_hp=6)
    cs.player.block = 10
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert sim.is_over


# ---------------------------------------------------------------- a relic the bridge says is spent
def test_a_spent_flag_from_the_bridge_marks_the_relic_used():
    assert RelicInstance.from_dict({"id": "PERMAFROST", "counter": None, "status": "Normal", "spent": True}).used
    assert not RelicInstance.from_dict({"id": "PERMAFROST", "counter": None, "status": "Normal", "spent": False}).used
    assert not RelicInstance.from_dict({"id": "PERMAFROST", "counter": None, "status": "Normal"}).used

def test_permafrost_that_has_paid_out_gives_no_more_block():
    cs = state([inflame()])
    cs.player.relics[RelicId.PERMAFROST] = RelicInstance.from_dict({"id": "PERMAFROST", "status": "Normal", "spent": True})
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.block == 0

def test_permafrost_that_is_waiting_gives_block_on_the_first_power():
    cs = state([inflame()])
    cs.player.relics[RelicId.PERMAFROST] = RelicInstance.from_dict({"id": "PERMAFROST", "status": "Normal", "spent": False})
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.block == 7

def test_ruined_helmet_that_has_doubled_strength_is_not_doubled_again():
    cs = state([inflame()])
    cs.player.relics[RelicId.RUINED_HELMET] = RelicInstance.from_dict({"id": "RUINED_HELMET", "status": "Normal", "spent": True})
    CombatSimulator(cs).play_card(0, 0)
    assert status(cs, StatusId.STRENGTH) == 2


# ---------------------------------------------------------------- states saved from the game
def _capture(name):
    from sts2_lite.Tests.relic.test_counters import _capture as load
    return load(name)

def test_saved_permafrost_reads_as_waiting_then_spent():
    assert not relic(_capture("permafrost_before"), RelicId.PERMAFROST).used
    assert relic(_capture("permafrost_after"), RelicId.PERMAFROST).used

def test_saved_state_the_first_power_gives_permafrost_block_as_the_game_did():
    cs = _capture("permafrost_before")
    index = next(i for i, c in enumerate(cs.player.hand) if c.card_id.name == "INFLAME")
    CombatSimulator(cs).play_card(index, 0)
    after = _capture("permafrost_after")
    assert cs.player.block == after.player.block == 7
    assert cs.energy == after.energy
    assert sorted(c.card_id.name for c in cs.player.hand) == sorted(c.card_id.name for c in after.player.hand)
    assert relic(cs, RelicId.PERMAFROST).used

def test_saved_happy_flower_pays_on_the_next_turn():
    cs = _capture("happy_flower_2")
    assert relic(cs, RelicId.HAPPY_FLOWER).counter == 2
    next_turn(cs)
    assert cs.energy == cs.max_energy + 1 and relic(cs, RelicId.HAPPY_FLOWER).counter == 0
