import json
import pytest
import json as _json
from pathlib import Path, Path as _Path
from sts2_lite.card import CardId, CardKeyword, CardType, TargetType, Card
from sts2_lite.combat import CombatSimulator, CombatState, CombatSimulator as _Sim, CombatState as _State
from sts2_lite.relic import RelicId, RelicInstance, RelicId as _RelicId, block_multiplier
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import hps
from sts2_lite.Tests.relic.test_always_on import card, strike, twin_strike, defend, inflame, state, relic, enemy_attack, plays, iron_wave
from agents.verify import compare as _compare
from sts2_lite import rng
from sts2_lite.Tests.card.test_draw_energy import infernal_blade
from sts2_lite.Tests.card.test_ironclad import stomp, hellraiser
from sts2_lite.enemy import Enemy


RELICS = Path(__file__).parents[1] / "data" / "relics"

BRIDGE_IDS = ["SAI", "MR_STRUGGLES", "PAELS_TEARS", "PAELS_FLESH", "LOST_WISP", "FORGOTTEN_SOUL", "IRON_CLUB",
              "HAND_DRILL", "THE_BOOT", "FAKE_ORICHALCUM", "FAKE_STRIKE_DUMMY", "FAKE_HAPPY_FLOWER",
              "SEAL_OF_GOLD", "PAELS_EYE", "PAELS_LEGION",
              "RUNIC_PYRAMID", "TOASTY_MITTENS", "HISTORY_COURSE", "SPIKED_GAUNTLETS", "PHILOSOPHERS_STONE"]

def next_turn(cs):
    cs.player.draw_pile = [defend() for _ in range(20)]
    sim = CombatSimulator(cs)
    sim.end_turn()
    return sim

def true_grit():
    return card(CardId.TRUE_GRIT, 1, CardType.Skill, TargetType.Self)

def thunderclap():
    return card(CardId.THUNDERCLAP, 1, CardType.Attack, TargetType.AllEnemies)


@pytest.mark.parametrize("bridge_id", BRIDGE_IDS)
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

def test_happy_flower_flash_reading_loads_as_zero():
    """From a live run: after the energy was gained the game still showed counter 3 while the relic flashed."""
    from sts2_lite.relic import RelicInstance
    assert RelicInstance.from_dict({"id": "HAPPY_FLOWER", "counter": 3}).counter == 0
    assert RelicInstance.from_dict({"id": "HAPPY_FLOWER", "counter": 2}).counter == 2
    assert RelicInstance.from_dict({"id": "FAKE_HAPPY_FLOWER", "counter": 5}).counter == 0


# ---------------------------------------------------------------- Letter Opener counter (live captures)

_RELICS = _Path(__file__).parents[1] / "data" / "relics"

def _letter_opener(state):
    return state.player.relics[_RelicId.LETTER_OPENER]

def _load(name):
    return _json.loads((_RELICS / name).read_text())

def test_letter_opener_full_count_reads_as_a_reset():
    """The game shows 3 while the relic flashes after the third skill; the sim has already reset to 0."""
    flash = _State.from_dict(_load("letter_opener_third_skill_flash.json"))
    assert _letter_opener(flash).counter == 0
    assert _letter_opener(_State.from_dict(_load("letter_opener_second_skill_before.json"))).counter == 2

def test_the_third_skill_matches_the_game_counter():
    before = _State.from_dict(_load("letter_opener_second_skill_before.json"))
    sim = _Sim(before)
    sim.perform_action({"action": "play_card", "card_index": 7, "target": 0})        # Primal Force
    after = _State.from_dict(_load("letter_opener_third_skill_flash.json"))
    assert _letter_opener(before).counter == _letter_opener(after).counter == 0
    assert _compare(before, after) == []

def test_the_next_card_after_the_flash_keeps_the_counter_at_zero():
    flashing = _State.from_dict(_load("letter_opener_third_skill_flash.json"))
    assert _letter_opener(flashing).counter == 0
    after_attack = _State.from_dict(_load("letter_opener_flash_then_attack.json"))
    assert _letter_opener(after_attack).counter == 0

def test_letter_opener_fires_and_matches_after_battle_trance():
    before = _State.from_dict(_load("letter_opener_battle_trance_before.json"))
    assert _letter_opener(before).counter == 2
    sim = _Sim(before)
    sim.perform_action({"action": "play_card", "card_index": 0, "target": 0})        # Battle Trance+, the third skill
    after = _State.from_dict(_load("letter_opener_battle_trance_after.json"))
    assert _letter_opener(before).counter == _letter_opener(after).counter == 0


RELICS = Path(__file__).parents[1] / "data" / "relics"



# ---------------------------------------------------------------- Seal of Gold (AfterSideTurnStart)
def gold_state(gold, *relic_ids):
    cs = state([], RelicId.SEAL_OF_GOLD, *relic_ids)
    cs.player.gold = gold
    return cs

def test_seal_of_gold_trades_5_gold_for_1_energy_each_turn():
    cs = gold_state(99)
    next_turn(cs)
    assert (cs.energy, cs.player.gold) == (cs.max_energy + 1, 94)

def test_seal_of_gold_needs_at_least_5_gold():
    cs = gold_state(5)
    sim = next_turn(cs)
    assert (cs.energy, cs.player.gold) == (cs.max_energy + 1, 0)
    sim.end_turn()
    assert (cs.energy, cs.player.gold) == (cs.max_energy, 0)

def test_seal_of_gold_does_nothing_below_5_gold():
    cs = gold_state(4)
    next_turn(cs)
    assert (cs.energy, cs.player.gold) == (cs.max_energy, 4)

def test_seal_of_gold_energy_comes_after_the_refill():
    """The energy is added after the turn's refill, so it stacks with Ice Cream's carried energy."""
    cs = gold_state(10, RelicId.ICE_CREAM)
    cs.energy = 2
    next_turn(cs)
    assert cs.energy == 2 + cs.max_energy + 1

def test_seal_of_gold_ignores_expect_a_fight_from_the_previous_turn():
    """Expect a Fight's no-energy-gain lasts only until the end of the turn it was played."""
    cs = gold_state(10)
    cs.player.apply_status(StatusId.NO_ENERGY_GAIN, 1)
    next_turn(cs)
    assert cs.energy == cs.max_energy + 1

def test_gold_without_the_seal_is_never_spent():
    cs = state([])
    cs.player.gold = 50
    next_turn(cs)
    assert (cs.energy, cs.player.gold) == (cs.max_energy, 50)


def test_gold_is_read_from_the_bridge_and_copied():
    d = json.loads((RELICS / "vambrace_active.json").read_text())
    cs = CombatState.from_dict(d)
    assert cs.player.gold == d["player"]["gold"] == 99
    copy = CombatState.deepcopy(cs)
    copy.player.gold -= 5
    assert (copy.player.gold, cs.player.gold) == (94, 99)


# ---------------------------------------------------------------- Pael's Eye (BeforeSideTurnEndEarly, ShouldTakeExtraTurn)
def eye_state(hand=(), *relic_ids, enemies=1):
    cs = state(list(hand), RelicId.PAELS_EYE, *relic_ids, enemies=enemies)
    cs.player.draw_pile = [defend() for _ in range(20)]
    enemy_attack(cs, 10)
    return cs

def test_paels_eye_ending_a_turn_without_playing_exhausts_the_hand_and_takes_an_extra_turn():
    hand = [strike(), defend(), strike()]
    cs = eye_state(hand)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.player.exhaust_pile == hand and cs.player.discard_pile == []
    assert cs.player.current_hp == 50                       # the enemies did not act
    assert (cs.turn_number, cs.player_turn) == (1, 2)       # RoundNumber stays, TurnNumber goes up
    assert len(cs.player.hand) == 5 and cs.energy == cs.max_energy
    assert relic(cs, RelicId.PAELS_EYE).used

def test_paels_eye_works_once_per_combat():
    cs = eye_state([strike()])
    sim = CombatSimulator(cs)
    sim.end_turn()                  # extra turn
    hand = list(cs.player.hand)
    sim.end_turn()                  # nothing played again: a normal turn
    assert cs.player.current_hp == 40 and (cs.turn_number, cs.player_turn) == (2, 3)
    assert all(c in cs.player.discard_pile for c in hand)

def test_paels_eye_does_nothing_after_a_card_is_played():
    cs = eye_state([strike(), defend()])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.end_turn()
    assert cs.player.exhaust_pile == [] and cs.player.current_hp == 40
    assert (cs.turn_number, cs.player_turn) == (2, 2) and not relic(cs, RelicId.PAELS_EYE).used

def test_paels_eye_auto_plays_do_not_count_as_played():
    """AnyCardsPlayedThisTurn skips CardPlay.IsAutoPlay: Howl from Beyond playing itself still allows the extra turn."""
    cs = eye_state([defend()])
    howl = card(CardId.HOWL_FROM_BEYOND, 3, CardType.Attack, TargetType.AllEnemies)
    cs.player.exhaust_pile = [howl]
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [84] and cs.player.current_hp == 50 and relic(cs, RelicId.PAELS_EYE).used

def test_paels_eye_exhausts_retained_cards_and_runs_the_exhaust_hooks():
    kept = defend().with_keyword(CardKeyword.RETAIN)
    cs = eye_state([kept, strike()], RelicId.CHARONS_ASHES)
    CombatSimulator(cs).end_turn()
    assert cs.player.exhaust_pile == [kept, cs.player.exhaust_pile[1]] and hps(cs) == [94]

def test_paels_eye_ticks_no_debuffs_but_the_players_plating():
    """Weak/Vulnerable/Frail tick at the enemy side's turn end; Plating at its owner's turn start."""
    cs = eye_state()
    cs.player.apply_status(StatusId.WEAK, 2)
    cs.player.apply_status(StatusId.PLATING, 3)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.player.status_amount(StatusId.WEAK) == 2 and cs.enemies[0].status_amount(StatusId.VULNERABLE) == 2
    assert cs.player.status_amount(StatusId.PLATING) == 2
    sim.end_turn()
    assert cs.player.status_amount(StatusId.WEAK) == 1 and cs.enemies[0].status_amount(StatusId.VULNERABLE) == 1

def test_paels_eye_extra_turn_clears_the_players_block():
    cs = eye_state()
    cs.player.block = 12
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 0

def test_relics_count_the_extra_turn_as_a_player_turn():
    """Candelabra (TurnNumber == 2) fires on the extra turn; Mr. Struggles deals TurnNumber, not RoundNumber."""
    cs = eye_state((), RelicId.CANDELABRA, RelicId.MR_STRUGGLES)
    CombatSimulator(cs).end_turn()
    assert cs.energy == cs.max_energy + 2 and hps(cs) == [98] and cs.turn_number == 1

def test_bread_energy_starts_on_player_turn_2_even_in_round_1():
    cs = eye_state((), RelicId.BREAD)
    CombatSimulator(cs).end_turn()
    assert cs.max_energy == 4 and cs.turn_number == 1

def test_ice_cream_keeps_energy_into_the_extra_turn():
    """IceCream: refills only on TurnNumber 1; the extra turn after it is turn 2."""
    cs = eye_state((), RelicId.ICE_CREAM)
    cs.energy = 2
    CombatSimulator(cs).end_turn()
    assert cs.energy == 2 + cs.max_energy

def test_ring_of_the_drake_stops_after_player_turn_3_not_round_3():
    cs = eye_state((), RelicId.RING_OF_THE_DRAKE)
    cs.turn_number = 3
    CombatSimulator(cs).end_turn()          # round 3, player turn 4
    assert len(cs.player.hand) == 5

def test_ringing_triangle_keeps_only_the_first_player_turns_hand():
    """RingingTriangle.ShouldFlush: TurnNumber > 1, so the extra turn's hand is discarded although the round is still 1."""
    cs = eye_state((), RelicId.RINGING_TRIANGLE)
    sim = CombatSimulator(cs)
    sim.end_turn()                          # extra turn: round 1, player turn 2
    sim.play_card(0, 0)
    sim.end_turn()
    assert len(cs.player.discard_pile) == 5

def test_extra_turn_survives_a_copy():
    cs = eye_state()
    CombatSimulator(cs).end_turn()
    copy = CombatState.deepcopy(cs)
    assert (copy.turn_number, copy.player_turn) == (1, 2) and relic(copy, RelicId.PAELS_EYE).used


# ---------------------------------------------------------------- Pael's Eye from the bridge
def bridge_state(status, spent, round_number=2):
    d = json.loads((RELICS / "vambrace_active.json").read_text())
    entry = {"id": "PAELS_EYE", "name": "Pael's Eye", "counter": None, "status": status, "keywords": []}
    if spent is not None:
        entry["spent"] = spent
    d["player"]["relics"].append(entry)
    d["round"] = round_number
    return CombatState.from_dict(d)

def test_bridge_spent_eye_means_the_extra_turn_was_taken():
    cs = bridge_state("Normal", True)
    assert relic(cs, RelicId.PAELS_EYE).used and (cs.turn_number, cs.player_turn) == (2, 3)

def test_bridge_active_eye_is_ready():
    cs = bridge_state("Active", False)
    assert not relic(cs, RelicId.PAELS_EYE).used and cs.cards_played == 0 and cs.player_turn == 2

def test_bridge_normal_unspent_eye_means_a_card_was_played_this_turn():
    """BeforeCardPlayed sets Normal; the fight goes on normally at the end of this turn."""
    cs = bridge_state("Normal", False)
    assert cs.cards_played == 1
    CombatSimulator(cs).end_turn()
    assert cs.player_turn == 3 and not relic(cs, RelicId.PAELS_EYE).used

def test_carry_turn_counters_does_not_cross_the_extra_turn():
    """Same round, different player turn: the counters of the turn before the extra turn are not carried."""
    before = bridge_state("Active", False)
    before.player.attacks_played_this_turn = 2
    after = bridge_state("Normal", True)
    after.carry_turn_counters(before)
    assert after.player.attacks_played_this_turn == 0
    after.player.attacks_played_this_turn = 1
    later = bridge_state("Normal", True)        # still the extra turn: carried
    later.carry_turn_counters(after)
    assert later.player.attacks_played_this_turn == 1


# ---------------------------------------------------------------- Pael's Legion (ModifyBlockMultiplicative, Cooldown 2)
def legion_state(hand, *relic_ids, cooldown=None):
    cs = state(hand, RelicId.PAELS_LEGION, *relic_ids)
    relic(cs, RelicId.PAELS_LEGION).counter = cooldown
    return cs

def test_paels_legion_doubles_the_first_block_card_then_cools_down():
    cs = legion_state([defend(), defend()])
    plays(cs, (0, 0), (0, 0))
    assert cs.player.block == 10 + 5 and relic(cs, RelicId.PAELS_LEGION).counter == 2

def test_paels_legion_is_ready_again_two_turns_later():
    """Cooldown 2 is set after the play; AfterSideTurnStart takes 1 off each turn: off next turn, back the turn after."""
    cs = legion_state([defend()])
    sim = plays(cs, (0, 0))
    cs.player.draw_pile = [defend() for _ in range(20)]
    sim.end_turn()
    assert relic(cs, RelicId.PAELS_LEGION).counter == 1
    sim.play_card(0, 0)
    assert cs.player.block == 5
    sim.end_turn()
    assert not relic(cs, RelicId.PAELS_LEGION).counter
    sim.play_card(0, 0)
    assert cs.player.block == 10

def test_paels_legion_ignores_cards_without_block():
    cs = legion_state([strike(), defend()])
    plays(cs, (0, 0), (0, 0))
    assert cs.player.block == 10

def test_paels_legion_doubles_after_dexterity_and_frail():
    cs = legion_state([defend()])
    cs.player.apply_status(StatusId.DEXTERITY, 2)
    cs.player.apply_status(StatusId.FRAIL, 2)
    plays(cs, (0, 0))
    assert cs.player.block == int((5 + 2) * 0.75 * 2)

def test_paels_legion_stacks_with_vambrace():
    cs = legion_state([iron_wave()], RelicId.VAMBRACE)
    plays(cs, (0, 0))
    assert cs.player.block == 5 * 4

def test_paels_legion_throwing_axe_doubles_only_the_first_play():
    """Each play of the series is its own CardPlay with its own AfterCardPlayed (CardModel play loop)."""
    cs = legion_state([defend()], RelicId.THROWING_AXE)
    plays(cs, (0, 0))
    assert cs.player.block == 10 + 5 and relic(cs, RelicId.PAELS_LEGION).counter == 2

def test_paels_legion_refused_play_leaves_it_ready():
    cs = legion_state([iron_wave()])
    with pytest.raises(ValueError):
        CombatSimulator(cs).play_card(0, 5)
    assert not relic(cs, RelicId.PAELS_LEGION).counter and relic(cs, RelicId.PAELS_LEGION).triggering is None

def test_paels_legion_only_doubles_block_from_a_card():
    """ModifyBlockMultiplicative: cardSource == null -> 1."""
    cs = legion_state([])
    assert (block_multiplier(cs.player, None), block_multiplier(cs.player, defend())) == (1, 2)

def test_paels_legion_cooldown_is_read_from_the_bridge():
    assert RelicInstance.from_dict({"id": "PAELS_LEGION", "counter": 1, "status": "Normal"}).counter == 1
    assert not RelicInstance.from_dict({"id": "PAELS_LEGION", "counter": None, "status": "Active"}).counter

def test_paels_legion_capture_defend_gives_the_previewed_10_block():
    """snecko_eye_paels_legion: Legion Active, Defend shows 'Gain 10 Block.'"""
    d = json.loads((RELICS / "snecko_eye_paels_legion.json").read_text())
    cs = CombatState.from_dict(d)
    assert d["player"]["hand"][0]["description"] == "Gain 10 Block." and cs.player.hand[0].energy_cost == 0
    plays(cs, (0, 0))
    assert cs.player.block == 10 and relic(cs, RelicId.PAELS_LEGION).counter == 2
    assert len(cs.enemies) == 1             # the Legion pet is not in the bridge's enemy list


# ---------------------------------------------------------------- Snecko Eye: Confused (ConfusedPower.AfterCardDrawn)
def rolls(monkeypatch, *costs):
    """The next Confused rolls, in order (rng.randrange(4))."""
    queue = list(costs)
    def fake(n):
        assert n == 4
        return queue.pop(0)
    monkeypatch.setattr(rng, "randrange", fake)
    return queue

def confused_state(hand=(), *relic_ids):
    cs = state(list(hand), *relic_ids)
    cs.player.apply_status(StatusId.CONFUSED, 1)
    return cs

def body_slam():
    return card(CardId.BODY_SLAM, 1, CardType.Attack)

def test_confused_capture_loads_with_the_shown_costs():
    d = json.loads((RELICS / "snecko_eye_paels_legion.json").read_text())
    cs = CombatState.from_dict(d)
    assert cs.player.status_amount(StatusId.CONFUSED) == 1
    assert [c.energy_cost for c in cs.player.hand] == [int(c["cost"]) for c in d["player"]["hand"]] == [0, 3, 2, 3, 0, 0, 3]

def test_confused_capture_next_hand_is_seven_rolled_cards():
    """Snecko Eye's +2 hand draw; the 3 unrolled draw-pile cards and the reshuffled ones are all rolled."""
    d = json.loads((RELICS / "snecko_eye_paels_legion.json").read_text())
    cs = CombatState.from_dict(d)
    rng.seed(7)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert len(cs.player.hand) == 7 and all(0 <= c.energy_cost <= 3 for c in cs.player.hand)
    assert len({c.energy_cost for c in cs.player.hand}) > 1

def test_confused_rolls_cover_0_to_3():
    rng.seed(1)
    cs = confused_state()
    cs.player.draw_pile = [strike() for _ in range(9)]
    seen = set()
    for _ in range(200):
        cs.player.draw_pile.append(cs.player.hand.pop() if cs.player.hand else strike())
        seen.add(cs.player.draw_card().energy_cost)
    assert seen == {0, 1, 2, 3}

def test_confused_rolls_mid_turn_draws_and_returns_the_rolled_card(monkeypatch):
    rolls(monkeypatch, 3)
    cs = confused_state()
    cs.player.draw_pile = [strike()]
    drawn = cs.player.draw_card()
    assert drawn.energy_cost == 3 and cs.player.hand == [drawn] and drawn.restore_cost is None

def test_confused_rerolls_a_redrawn_card(monkeypatch):
    rolls(monkeypatch, 0, 2)
    cs = confused_state()
    cs.player.draw_pile = [strike()]
    first = cs.player.draw_card()
    cs.player.hand.remove(first)
    cs.player.draw_pile.append(first)
    assert (first.energy_cost, cs.player.draw_card().energy_cost) == (0, 2)

def test_confused_rolls_the_turn_start_hand(monkeypatch):
    rolls(monkeypatch, 0, 1, 2, 3, 0)
    cs = confused_state()
    cs.player.draw_pile = [defend() for _ in range(5)]
    CombatSimulator(cs).end_turn()
    assert sorted(c.energy_cost for c in cs.player.hand) == [0, 0, 1, 2, 3]

def test_confused_skips_x_and_unplayable_but_rolls_slimed(monkeypatch):
    """Canonical < 0 (Wound, Dazed...) and X costs keep theirs; Slimed costs 1, so it is rolled."""
    rolls(monkeypatch, 3)
    cs = confused_state()
    whirlwind = card(CardId.WHIRLWIND, "X", CardType.Attack, TargetType.AllEnemies)
    cs.player.draw_pile = [Card.create_slimed(), Card.create_wound(), whirlwind]
    costs = [cs.player.draw_card().energy_cost for _ in range(3)]
    assert costs == ["X", 0, 3]

def test_no_roll_without_confused():
    cs = state([])
    cs.player.draw_pile = [strike()]
    calls = rng.calls
    assert cs.player.draw_card().energy_cost == 1 and rng.calls == calls

def test_confused_does_not_touch_cards_that_are_created(monkeypatch):
    """Infernal Blade adds its card to the hand (AddGeneratedCardToCombat): free this turn, not rolled."""
    rolls(monkeypatch)                      # any roll fails the test
    cs = confused_state([infernal_blade()])
    plays(cs, (0, 0))
    made = cs.player.hand[0]
    assert made.energy_cost == 0 and made.restore_cost is not None

def test_stomp_reduction_comes_off_the_rolled_cost(monkeypatch):
    """Stomp rolled to 1, then a Strike: AddThisTurn(-1) on top of the roll -> 0; back to the roll after the turn."""
    rolls(monkeypatch, 1, 3, 3, 3, 3, 3)
    cs = confused_state([strike()])
    cs.player.draw_pile = [stomp()]
    cs.player.draw_card()
    sim = plays(cs, (0, 0))
    stomped = cs.player.hand[0]
    assert stomped.card_id == CardId.STOMP and stomped.energy_cost == 0
    cs.player.draw_pile = [defend() for _ in range(5)]
    sim.end_turn()
    assert [c.energy_cost for c in cs.player.discard_pile if c.card_id == CardId.STOMP] == [1]

def test_stomp_drawn_after_an_attack_takes_the_roll(monkeypatch):
    """The Attack's -1 (this turn) is overridden by the later Absolute roll: modifiers apply in order."""
    rolls(monkeypatch, 3)
    cs = confused_state([strike()])
    cs.player.draw_pile = [stomp()]
    plays(cs, (0, 0))
    assert cs.player.draw_pile[0].energy_cost == 2
    drawn = cs.player.draw_card()
    assert (drawn.energy_cost, drawn.restore_cost) == (3, None)

@pytest.mark.parametrize("rolled, upgraded", [(3, 1), (2, 1), (1, 1), (0, 0)])
def test_upgrade_lowers_a_rolled_cost_only_to_the_new_base(rolled, upgraded):
    """CardEnergyCost.UpgradeBy caps Absolute modifiers above base + change (Hellraiser 2 -> 1)."""
    assert hellraiser().confused_copy(rolled).upgraded_copy().energy_cost == upgraded

def test_upgrade_without_a_cost_change_keeps_the_roll():
    assert strike().confused_copy(3).upgraded_copy().energy_cost == 3

def test_armaments_plus_under_confused(monkeypatch):
    armaments = card(CardId.ARMAMENTS, 1, CardType.Skill, TargetType.Self, upgraded=True)
    cs = confused_state([armaments, hellraiser().confused_copy(3), body_slam().confused_copy(0), strike().confused_copy(3)])
    plays(cs, (0, 0))
    assert [c.energy_cost for c in cs.player.hand] == [1, 0, 3] and all(c.is_upgraded for c in cs.player.hand)

def test_upgrade_keeps_this_turns_reduction_on_top():
    """Rolled 3, Stomp-style -1 this turn (2), upgraded (base 1): 1 - 1 = 0 now, 1 after the turn."""
    c = hellraiser().confused_copy(3).cheaper_this_turn(1).upgraded_copy()
    assert (c.energy_cost, c.restore_cost) == (0, 1)

def test_upgrading_a_free_card_gives_back_the_upgraded_cost():
    """Infernal Blade's free Body Slam, upgraded: free now, 0 (not 1) after the turn."""
    free = body_slam()
    free.restore_cost, free.energy_cost = 1, 0
    up = free.upgraded_copy()
    assert (up.energy_cost, up.restore_cost) == (0, 0)

def test_bridge_stomp_under_confused_is_the_roll():
    d = json.loads((RELICS / "snecko_eye_paels_legion.json").read_text())
    d["player"]["hand"][1].update(id="STOMP", name="Stomp", type="Attack", target_type="AllEnemies", cost="1",
                                  description="Deal 12 damage to ALL enemies.")
    cs = CombatState.from_dict(d)
    assert (cs.player.hand[1].energy_cost, cs.player.hand[1].restore_cost) == (1, None)


RELICS = Path(__file__).parents[1] / "data" / "relics"

def draw_pile(cs, n=30):
    cs.player.draw_pile = [defend() for _ in range(n)]
    return cs

def names(pile):
    return [c.card_id.name for c in pile]



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

def test_feel_no_pain_block_from_toasty_mittens_survives_the_start_of_turn():
    """Captured: the block comes after the turn's block is cleared, so it is still there when the player acts."""
    cs = draw_pile(state([], RelicId.TOASTY_MITTENS))
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 3)
    cs.player.block = 34
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 3

def test_block_is_still_cleared_at_the_start_of_the_turn_without_it():
    cs = draw_pile(state([], RelicId.TOASTY_MITTENS))
    cs.player.block = 34
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 0

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
    path = Path(__file__).parents[1] / "data" / "act1_overgrowth" / "vine_shambler" / "tangled.json"
    cs = CombatState.from_dict(json.loads(path.read_text()))
    strike_card = next(c for c in cs.player.hand if c.card_id is CardId.STRIKE_IRONCLAD)
    defend_card = next(c for c in cs.player.hand if c.card_id is CardId.DEFEND_IRONCLAD)
    assert strike_card.current_cost(cs.player) == 2 and defend_card.current_cost(cs.player) == 1     # as the bridge shows
    sim = CombatSimulator(cs)
    index = cs.player.hand.index(strike_card)
    energy = cs.energy
    sim.play_card(index, 0)
    assert cs.energy == energy - 2
