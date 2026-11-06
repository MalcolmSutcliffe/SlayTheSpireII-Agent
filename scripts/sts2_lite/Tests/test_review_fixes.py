"""Regression tests checked against sts2_decompiled. Run from scripts/: python -m pytest sts2_lite/Tests"""
import itertools
from decimal import Decimal

import pytest

from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.creature import Creature
from sts2_lite.damage import modify_damage
from sts2_lite.relic import RelicId
from sts2_lite.status import StatusId
from sts2_lite.Tests.test_cards import make_card, make_state
from sts2_lite.Tests.test_relics_always_on import held, relic, strike, defend


def card(card_id, cost=1, kind=CardType.Skill, target=TargetType.Self, upgraded=False):
    return make_card(card_id, card_id.name.title(), kind, cost, target, upgraded)

def thrash():
    return card(CardId.THRASH, 1, CardType.Attack, TargetType.AnyEnemy)

def pommel_strike():
    return card(CardId.POMMEL_STRIKE, 1, CardType.Attack, TargetType.AnyEnemy)

def with_draw_pile(cs, n=10):
    cs.player.draw_pile = [defend() for _ in range(n)]
    return cs


# ---------------------------------------------------------------- damage rounding (Hook.ModifyDamage, decimal)
@pytest.mark.parametrize("weak, vulnerable, shrink", list(itertools.product([False, True], [False, True], [False, True])))
def test_damage_matches_decimal_arithmetic(weak, vulnerable, shrink):
    for base, slow in itertools.product(range(60), range(0, 110, 10)):
        attacker, target = Creature(), Creature()
        expected = Decimal(base)
        if weak:
            attacker.apply_status(StatusId.WEAK, 1); expected *= Decimal("0.75")
        if vulnerable:
            target.apply_status(StatusId.VULNERABLE, 1); expected *= Decimal("1.5")
        if shrink:
            attacker.apply_status(StatusId.SHRINK, 1); expected *= Decimal("0.7")
        if slow:
            target.apply_status(StatusId.SLOW, slow); expected *= 1 + Decimal(slow) / 100
        assert modify_damage(base, attacker, target) == int(expected), (base, slow)

def test_damage_that_floats_used_to_round_down():
    attacker, target = Creature(), Creature()
    target.apply_status(StatusId.VULNERABLE, 1)
    target.apply_status(StatusId.SLOW, 40)
    assert modify_damage(30, attacker, target) == 63        # was 62


# ---------------------------------------------------------------- Unceasing Top (CombatManager.CheckForEmptyHand)
def test_unceasing_top_waits_for_pommel_strike_to_draw():
    cs = held(with_draw_pile(make_state([pommel_strike()], enemy_count=1, enemy_hp=100)), RelicId.UNCEASING_TOP)
    CombatSimulator(cs).play_card(0, 0)
    assert len(cs.player.hand) == 1

def test_unceasing_top_draws_when_second_wind_empties_the_hand():
    cs = held(with_draw_pile(make_state([card(CardId.SECOND_WIND), defend(), defend()], enemy_count=1)), RelicId.UNCEASING_TOP)
    CombatSimulator(cs).play_card(0, 0)
    assert len(cs.player.hand) == 1 and len(cs.player.exhaust_pile) == 2

def test_unceasing_top_draws_when_fiend_fire_empties_the_hand():
    fiend_fire = card(CardId.FIEND_FIRE, 2, CardType.Attack, TargetType.AnyEnemy)
    cs = held(with_draw_pile(make_state([fiend_fire, defend()], enemy_count=1, enemy_hp=100)), RelicId.UNCEASING_TOP)
    CombatSimulator(cs).play_card(0, 0)
    assert len(cs.player.hand) == 1

def test_unceasing_top_waits_for_a_choice_to_finish_the_play():
    headbutt = card(CardId.HEADBUTT, 1, CardType.Attack, TargetType.AnyEnemy)
    cs = held(with_draw_pile(make_state([headbutt], enemy_count=1, enemy_hp=100)), RelicId.UNCEASING_TOP)
    cs.player.discard_pile = [strike(), card(CardId.BASH, 2, CardType.Attack, TargetType.AnyEnemy)]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.player.hand == [] and cs.pending_choice is not None
    sim.choose_card(1)
    assert [c.card_id for c in cs.player.hand] == [CardId.BASH]

def test_unceasing_top_does_not_draw_while_the_hand_has_cards():
    cs = held(with_draw_pile(make_state([defend(), defend()], enemy_count=1)), RelicId.UNCEASING_TOP)
    CombatSimulator(cs).play_card(0, 0)
    assert len(cs.player.hand) == 1


# ---------------------------------------------------------------- Havoc (CardCmd.AutoPlay)
def test_havoc_plays_slimed_instead_of_exhausting_it_unplayed():
    cs = with_draw_pile(make_state([card(CardId.HAVOC)], enemy_count=1))
    cs.player.draw_pile.append(Card.create_slimed())
    CombatSimulator(cs).play_card(0, 0)
    assert len(cs.player.hand) == 1
    assert [c.card_id for c in cs.player.exhaust_pile] == [CardId.SLIMED]

def test_havoc_still_exhausts_an_unplayable_card_unplayed():
    cs = with_draw_pile(make_state([card(CardId.HAVOC)], enemy_count=1))
    cs.player.draw_pile.append(Card.create_wound())
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.hand == [] and [c.card_id for c in cs.player.exhaust_pile] == [CardId.WOUND]


# ---------------------------------------------------------------- Crimson Mantle (CrimsonMantlePower.IncrementSelfDamage)
def test_crimson_mantle_loses_one_hp_per_copy_played():
    mantle = lambda: card(CardId.CRIMSON_MANTLE, 1, CardType.Power)
    cs = with_draw_pile(make_state([mantle(), mantle()], enemy_count=1, enemy_hp=100))
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    sim.end_turn()
    assert cs.player.current_hp == 50 - 2 and cs.player.block == 16

def test_crimson_mantle_plays_survive_a_copy():
    from sts2_lite.combat import CombatState
    cs = make_state([card(CardId.CRIMSON_MANTLE, 1, CardType.Power)], enemy_count=1)
    CombatSimulator(cs).play_card(0, 0)
    assert CombatState.deepcopy(cs).player.crimson_mantle_plays == 1

def test_crimson_mantle_plays_are_carried_to_a_loaded_state():
    from sts2_lite.combat import CombatState
    old = make_state([], enemy_count=1)
    old.player.apply_status(StatusId.CRIMSON_MANTLE, 18)
    old.player.crimson_mantle_plays = 2
    new = CombatState.deepcopy(old)
    new.player.crimson_mantle_plays = 1
    new.carry_combat_counters(old)
    assert new.player.crimson_mantle_plays == 2


# ---------------------------------------------------------------- Unmovable (UnmovablePower)
def test_unmovable_doubles_every_block_second_wind_gives():
    cs = make_state([card(CardId.SECOND_WIND), defend(), defend()], enemy_count=1)
    cs.player.apply_status(StatusId.UNMOVABLE, 1)
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.block == 2 * (5 * 2)

def test_unmovable_tells_two_plays_of_the_same_card_object_apart():
    shared = defend()
    cs = make_state([shared], enemy_count=1)
    cs.player.apply_status(StatusId.UNMOVABLE, 1)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    cs.player.hand.append(cs.player.discard_pile.pop())
    sim.play_card(0, 0)
    assert cs.player.block == 10 + 5


# ---------------------------------------------------------------- Thrash (Thrash.OnPlay)
def thrash_state(*relic_ids):
    cs = make_state([thrash(), strike()], enemy_count=1, enemy_hp=200)
    return held(cs, *relic_ids)

def thrash_bonus(cs):
    return next(c for c in cs.player.discard_pile if c.card_id == CardId.THRASH).bonus_damage

def test_thrash_counts_strike_dummy_on_the_strike_it_exhausts():
    cs = thrash_state(RelicId.STRIKE_DUMMY)
    CombatSimulator(cs).play_card(0, 0)
    assert thrash_bonus(cs) == 6 + 3

def test_thrash_counts_miniature_cannon_by_the_exhausted_card_not_thrash():
    cs = make_state([thrash().upgraded_copy(), strike()], enemy_count=1, enemy_hp=200)
    held(cs, RelicId.MINIATURE_CANNON)
    CombatSimulator(cs).play_card(0, 0)
    assert thrash_bonus(cs) == 6

def test_thrash_doubled_by_pen_nib_does_not_double_its_bonus():
    cs = thrash_state(RelicId.PEN_NIB)
    relic(cs, RelicId.PEN_NIB).counter = 9
    CombatSimulator(cs).play_card(0, 0)
    assert cs.enemies[0].current_hp == 200 - 2 * 8 and thrash_bonus(cs) == 6

def test_thrash_as_the_ninth_attack_reads_the_next_attacks_pen_nib():
    cs = thrash_state(RelicId.PEN_NIB)
    relic(cs, RelicId.PEN_NIB).counter = 8
    CombatSimulator(cs).play_card(0, 0)
    assert thrash_bonus(cs) == 12


def test_crimson_mantle_block_is_given_once():
    cs = with_draw_pile(make_state([card(CardId.CRIMSON_MANTLE, 1, CardType.Power)], enemy_count=1, enemy_hp=100))
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.end_turn()
    assert cs.player.block == 8 and cs.player.current_hp == 49

def test_crimson_mantle_block_still_sets_off_juggernaut():
    cs = with_draw_pile(make_state([card(CardId.CRIMSON_MANTLE, 1, CardType.Power)], enemy_count=1, enemy_hp=100))
    cs.player.apply_status(StatusId.JUGGERNAUT, 5)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.end_turn()
    assert cs.enemies[0].current_hp == 100 - 5


# ---------------------------------------------------------------- turn 2/3 relics (AfterBlockCleared, before the draw)
def test_sparkling_rouge_strength_is_up_before_hellraiser_plays_drawn_strikes():
    cs = make_state([], enemy_count=1, enemy_hp=200)
    held(cs, RelicId.SPARKLING_ROUGE)
    cs.turn_number = 2
    cs.player.draw_pile = [strike() for _ in range(5)]
    cs.player.apply_status(StatusId.HELLRAISER, 1)
    CombatSimulator(cs).end_turn()
    assert cs.enemies[0].current_hp == 200 - 5 * 7

def test_horn_cleat_block_is_there_during_the_draw():
    cs = with_draw_pile(make_state([], enemy_count=1))
    held(cs, RelicId.HORN_CLEAT)
    sim = CombatSimulator(cs)
    seen = []
    cs.player.draw_hook = lambda c: seen.append(cs.player.block)
    sim.end_turn()
    assert seen[0] == 14 and cs.player.block == 14


# ---------------------------------------------------------------- Mummified Hand (MummifiedHand.AfterCardPlayed)
def inflame():
    return card(CardId.INFLAME, 1, CardType.Power)

@pytest.mark.parametrize("seed", range(20))
def test_mummified_hand_skips_skills_corruption_already_made_free(seed):
    from sts2_lite import rng
    rng.seed(seed)
    cs = make_state([inflame(), defend(), defend(), defend(), strike()], enemy_count=1)
    held(cs, RelicId.MUMMIFIED_HAND)
    cs.player.apply_status(StatusId.CORRUPTION, 1)
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.hand[-1].energy_cost == 0
    assert all(c.restore_cost is None for c in cs.player.hand[:-1])

def test_mummified_hand_keeps_the_original_cost_of_a_card_already_cheaper():
    cs = make_state([inflame(), card(CardId.STOMP, 3, CardType.Attack, TargetType.AllEnemies)], enemy_count=1)
    held(cs, RelicId.MUMMIFIED_HAND)
    cs.player.hand[1] = cs.player.hand[1].cheaper_this_turn(1)
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.hand[0].energy_cost == 0 and cs.player.hand[0].restore_cost == 3


# ---------------------------------------------------------------- dead targets (Creature.CanReceivePowers)
def bash():
    return card(CardId.BASH, 2, CardType.Attack, TargetType.AnyEnemy)

def test_lamp_from_capture_is_unspent_after_bash_killed_its_target():
    from sts2_lite.Tests.test_relics_always_on import relic as relic_of
    from sts2_lite.combat import CombatState
    import json
    from pathlib import Path
    raw = json.loads((Path(__file__).parent / "data" / "relics" / "unsettling_lamp_after_kill.json").read_text())
    cs = CombatState.from_dict(raw)
    assert not relic_of(cs, RelicId.UNSETTLING_LAMP).used

def test_bash_killing_its_target_does_not_spend_the_lamp():
    cs = held(make_state([bash(), bash()], enemy_count=2, enemy_hp=5), RelicId.UNSETTLING_LAMP)
    cs.energy = 4
    cs.enemies[1].current_hp = cs.enemies[1].max_hp = 100
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert not relic(cs, RelicId.UNSETTLING_LAMP).used
    sim.play_card(0, 0)
    assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == 4      # second Bash is doubled

def test_vicious_draws_nothing_for_a_dead_target():
    cs = with_draw_pile(make_state([bash()], enemy_count=2, enemy_hp=5))
    cs.player.apply_status(StatusId.VICIOUS, 1)
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.hand == []
