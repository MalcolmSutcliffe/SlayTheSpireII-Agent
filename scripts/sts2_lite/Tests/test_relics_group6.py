"""Seal of Gold, Pael's Eye (and the player turn / round split it needs), Pael's Legion, Snecko Eye (Confused). Run from scripts/: python -m pytest sts2_lite/Tests"""
import json
from pathlib import Path

import pytest

from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardKeyword, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.relic import RelicId, RelicInstance, block_multiplier
from sts2_lite.status import StatusId
from sts2_lite.Tests.test_cards import hps
from sts2_lite.Tests.test_relics_always_on import card, strike, defend, iron_wave, state, relic, enemy_attack, plays
from sts2_lite.Tests.test_relics_group2 import next_turn
from sts2_lite.Tests.test_cards_draw_energy import infernal_blade
from sts2_lite.Tests.test_cards_last import stomp, hellraiser

RELICS = Path(__file__).parent / "data" / "relics"


@pytest.mark.parametrize("bridge_id", ["SEAL_OF_GOLD", "PAELS_EYE", "PAELS_LEGION"])
def test_loads_from_the_bridge(bridge_id):
    assert RelicInstance.from_dict({"id": bridge_id, "counter": None}).relic_id == RelicId[bridge_id]


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
