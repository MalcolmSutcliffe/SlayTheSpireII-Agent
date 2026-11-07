"""Relics that change the numbers: Miniature Cannon, Paper Phrog, Paper Krane, Vambrace, Tungsten Rod, Beating Remnant,
Ruined Helmet, Unsettling Lamp, Chemical X, Ice Cream, Ringing Triangle, Sturdy Clamp and Lizard Tail.
Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.card import CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.damage import modify_damage
from sts2_lite.player import Player
from sts2_lite.relic import RelicId, RelicInstance
from sts2_lite.status import StatusId
from sts2_lite.Tests.test_cards import make_card, make_state, play, hps


def card(card_id, cost, kind, target=TargetType.AnyEnemy, upgraded=False):
    return make_card(card_id, card_id.name.title(), kind, cost, target, upgraded)

def strike(up=False):
    return card(CardId.STRIKE_IRONCLAD, 1, CardType.Attack, upgraded=up)

def twin_strike(up=False):
    return card(CardId.TWIN_STRIKE, 1, CardType.Attack, upgraded=up)

def bash(up=False):
    return card(CardId.BASH, 2, CardType.Attack, upgraded=up)

def defend(up=False):
    return card(CardId.DEFEND_IRONCLAD, 1, CardType.Skill, TargetType.Self, up)

def iron_wave():
    return card(CardId.IRON_WAVE, 1, CardType.Attack)

def inflame():
    return card(CardId.INFLAME, 1, CardType.Power, TargetType.Self)

def uppercut():
    return card(CardId.UPPERCUT, 2, CardType.Attack)

def mangle():
    return card(CardId.MANGLE, 3, CardType.Attack)

def whirlwind():
    return card(CardId.WHIRLWIND, "X", CardType.Attack, TargetType.AllEnemies)

def bloodletting():
    return card(CardId.BLOODLETTING, 0, CardType.Skill, TargetType.Self)

def offering():
    return card(CardId.OFFERING, 0, CardType.Skill, TargetType.Self)

def held(cs, *relic_ids):
    for relic_id in relic_ids:
        cs.player.relics[relic_id] = RelicInstance(relic_id)
    return cs

def relic(cs, relic_id):
    return cs.player.relics[relic_id]

def state(hand, *relic_ids, enemies=1, enemy_hp=100):
    return held(make_state(hand, enemy_count=enemies, enemy_hp=enemy_hp), *relic_ids)

def enemy_attack(cs, damage, hits=1):
    cs.enemies[0].attack_damage = damage
    cs.enemies[0].num_attacks = hits

def plays(cs, *indices_and_targets):
    sim = CombatSimulator(cs)
    for index, target in indices_and_targets:
        sim.play_card(index, target)
    return sim


# ---------------------------------------------------------------- loading
BRIDGE_IDS = ["MINIATURE_CANNON", "PAPER_PHROG", "PAPER_KRANE", "VAMBRACE", "TUNGSTEN_ROD", "BEATING_REMNANT", "RUINED_HELMET",
              "UNSETTLING_LAMP", "CHEMICAL_X", "ICE_CREAM", "RINGING_TRIANGLE", "STURDY_CLAMP", "LIZARD_TAIL"]

@pytest.mark.parametrize("name", BRIDGE_IDS)
def test_every_relic_loads_from_its_bridge_id(name):
    assert RelicInstance.from_dict({"id": name, "counter": None}).relic_id == RelicId[name]

@pytest.mark.parametrize("name, status, used", [
    ("VAMBRACE", "Active", False), ("VAMBRACE", "Normal", True), ("VAMBRACE", None, False),
    ("UNSETTLING_LAMP", "Active", False), ("UNSETTLING_LAMP", "Normal", True),
    ("LIZARD_TAIL", "Normal", False), ("LIZARD_TAIL", "Disabled", True), ("RUINED_HELMET", "Normal", False)])
def test_a_spent_relic_is_read_from_the_bridge_status(name, status, used):
    raw = {"id": name, "counter": None}
    if status is not None:
        raw["status"] = status
    assert RelicInstance.from_dict(raw).used is used

def test_a_copy_keeps_what_a_relic_has_spent_and_counted():
    cs = state([], RelicId.RUINED_HELMET, RelicId.BEATING_REMNANT)
    relic(cs, RelicId.RUINED_HELMET).used = True
    relic(cs, RelicId.BEATING_REMNANT).value = 7
    copy = CombatState.deepcopy(cs)
    assert relic(copy, RelicId.RUINED_HELMET).used and relic(copy, RelicId.BEATING_REMNANT).value == 7
    relic(copy, RelicId.RUINED_HELMET).used = False
    assert relic(cs, RelicId.RUINED_HELMET).used

def test_the_counters_of_a_spent_relic_carry_to_the_next_loaded_state():
    old = state([], RelicId.RUINED_HELMET, RelicId.LIZARD_TAIL)
    relic(old, RelicId.RUINED_HELMET).used = True
    new = state([], RelicId.RUINED_HELMET, RelicId.LIZARD_TAIL)
    new.carry_combat_counters(old)
    assert relic(new, RelicId.RUINED_HELMET).used and not relic(new, RelicId.LIZARD_TAIL).used

def test_beating_remnants_damage_carries_within_a_turn_only():
    old = state([], RelicId.BEATING_REMNANT)
    relic(old, RelicId.BEATING_REMNANT).value = 12
    same = state([], RelicId.BEATING_REMNANT)
    same.carry_turn_counters(old)
    later = state([], RelicId.BEATING_REMNANT)
    later.turn_number = 2
    later.carry_turn_counters(old)
    assert relic(same, RelicId.BEATING_REMNANT).value == 12 and relic(later, RelicId.BEATING_REMNANT).value == 0


# ---------------------------------------------------------------- Miniature Cannon
def test_miniature_cannon_adds_three_to_an_upgraded_attack():
    cs = state([strike(up=True)], RelicId.MINIATURE_CANNON)
    play(cs)
    assert hps(cs) == [100 - 9 - 3]

def test_miniature_cannon_ignores_an_attack_that_is_not_upgraded():
    cs = state([strike()], RelicId.MINIATURE_CANNON)
    play(cs)
    assert hps(cs) == [100 - 6]

def test_miniature_cannon_applies_to_every_hit():
    cs = state([twin_strike(up=True)], RelicId.MINIATURE_CANNON)
    play(cs)
    assert hps(cs) == [100 - 2 * (7 + 3)]

def test_miniature_cannon_adds_to_strike_dummy():
    cs = state([strike(up=True)], RelicId.MINIATURE_CANNON, RelicId.STRIKE_DUMMY)
    play(cs)
    assert hps(cs) == [100 - (9 + 3 + 3)]

def test_miniature_cannon_is_added_before_vulnerable():
    cs = state([bash(up=True)], RelicId.MINIATURE_CANNON)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    play(cs)
    assert hps(cs) == [100 - int((10 + 3) * 1.5)]

def test_miniature_cannon_does_not_change_enemy_attacks():
    cs = state([], RelicId.MINIATURE_CANNON)
    assert CombatSimulator(cs).calculate_damage(10, cs.enemies[0], cs.player) == 10


# ---------------------------------------------------------------- Paper Phrog
def test_paper_phrog_makes_vulnerable_1_75():
    cs = state([strike()], RelicId.PAPER_PHROG)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    play(cs)
    assert hps(cs) == [100 - int(6 * 1.75)]

def test_paper_phrog_does_nothing_without_vulnerable():
    cs = state([strike()], RelicId.PAPER_PHROG)
    play(cs)
    assert hps(cs) == [94]

def test_paper_phrog_does_not_help_enemies_hitting_a_vulnerable_player():
    cs = state([], RelicId.PAPER_PHROG)
    cs.player.apply_status(StatusId.VULNERABLE, 1)
    assert modify_damage(10, cs.enemies[0], cs.player) == 15

def test_paper_phrog_adds_to_cruelty():
    cs = state([strike()], RelicId.PAPER_PHROG)
    cs.player.apply_status(StatusId.CRUELTY, 25)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    play(cs)
    assert hps(cs) == [100 - int(6 * (1.5 + 0.25 + 0.25))]

def test_paper_phrog_applies_to_the_bash_it_just_vulnerabled():
    cs = state([bash(), strike()], RelicId.PAPER_PHROG)
    sim = plays(cs, (0, 0))
    sim.play_card(0, 0)
    assert hps(cs) == [100 - 8 - int(6 * 1.75)]


# ---------------------------------------------------------------- Paper Krane
def test_paper_krane_makes_a_weak_enemy_hit_for_0_6():
    cs = state([], RelicId.PAPER_KRANE)
    cs.enemies[0].apply_status(StatusId.WEAK, 1)
    assert modify_damage(10, cs.enemies[0], cs.player) == 6

def test_a_weak_enemy_hits_for_0_75_without_paper_krane():
    cs = state([])
    cs.enemies[0].apply_status(StatusId.WEAK, 1)
    assert modify_damage(10, cs.enemies[0], cs.player) == 7

def test_paper_krane_does_not_weaken_the_players_own_weak():
    cs = state([], RelicId.PAPER_KRANE)
    cs.player.apply_status(StatusId.WEAK, 1)
    assert modify_damage(10, cs.player, cs.enemies[0]) == 7

def test_paper_krane_does_not_matter_without_weak():
    cs = state([], RelicId.PAPER_KRANE)
    assert modify_damage(10, cs.enemies[0], cs.player) == 10

def test_paper_krane_has_no_rounding_error():
    cs = state([], RelicId.PAPER_KRANE)
    cs.enemies[0].apply_status(StatusId.WEAK, 1)
    for base in range(0, 500):
        assert modify_damage(base, cs.enemies[0], cs.player) == base * 6 // 10, base

def test_paper_krane_and_vulnerable_multiply():
    cs = state([], RelicId.PAPER_KRANE)
    cs.enemies[0].apply_status(StatusId.WEAK, 1)
    cs.player.apply_status(StatusId.VULNERABLE, 1)
    assert modify_damage(10, cs.enemies[0], cs.player) == int(10 * 0.6 * 1.5)


# ---------------------------------------------------------------- Vambrace
def test_vambrace_doubles_the_first_block_from_a_card():
    cs = state([defend(), defend()], RelicId.VAMBRACE)
    plays(cs, (0, 0), (0, 0))
    assert cs.player.block == 10 + 5

def test_vambrace_marks_the_relic_used_once_the_card_is_played():
    cs = state([defend()], RelicId.VAMBRACE)
    play(cs)
    assert relic(cs, RelicId.VAMBRACE).used and relic(cs, RelicId.VAMBRACE).triggering is None

def test_vambrace_does_nothing_once_used():
    cs = state([defend()], RelicId.VAMBRACE)
    relic(cs, RelicId.VAMBRACE).used = True
    play(cs)
    assert cs.player.block == 5

def test_vambrace_doubles_every_block_of_the_same_card():
    cs = state([iron_wave()], RelicId.VAMBRACE)
    play(cs)
    assert cs.player.block == 10

def test_vambrace_is_not_used_by_a_card_that_gives_no_block():
    cs = state([defend(), defend()], RelicId.VAMBRACE)
    cs.player.apply_status(StatusId.DEXTERITY, -5)
    sim = plays(cs, (0, 0))
    assert cs.player.block == 0 and not relic(cs, RelicId.VAMBRACE).used
    del cs.player.status[StatusId.DEXTERITY]
    sim.play_card(0, 0)
    assert cs.player.block == 10

def test_vambrace_is_not_used_by_block_that_is_not_from_a_card():
    cs = state([defend()], RelicId.VAMBRACE)
    sim = CombatSimulator(cs)
    sim.gain_block(cs.player, 4)
    sim.play_card(0, 0)
    assert cs.player.block == 4 + 10

def test_vambrace_multiplies_with_unmovable():
    cs = state([defend()], RelicId.VAMBRACE)
    cs.player.apply_status(StatusId.UNMOVABLE, 1)
    play(cs)
    assert cs.player.block == 20

def test_vambrace_is_applied_after_frail():
    cs = state([defend()], RelicId.VAMBRACE)
    cs.player.apply_status(StatusId.FRAIL, 1)
    play(cs)
    assert cs.player.block == int(5 * 0.75 * 2)

def test_vambrace_is_still_available_after_a_failed_play():
    cs = state([defend(), strike()], RelicId.VAMBRACE)
    sim = CombatSimulator(cs)
    with pytest.raises(ValueError):
        sim.play_card(1, 5)         # no such target
    assert relic(cs, RelicId.VAMBRACE).triggering is None
    sim.play_card(0, 0)
    assert cs.player.block == 10

def test_vambrace_used_in_one_branch_is_not_used_in_another():
    cs = state([defend()], RelicId.VAMBRACE)
    branch = CombatState.deepcopy(cs)
    play(branch)
    assert relic(branch, RelicId.VAMBRACE).used and not relic(cs, RelicId.VAMBRACE).used


# ---------------------------------------------------------------- Tungsten Rod
def test_tungsten_rod_takes_one_off_each_hit_point_loss():
    cs = state([], RelicId.TUNGSTEN_ROD)
    enemy_attack(cs, 10)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 50 - 9

def test_tungsten_rod_applies_to_every_hit():
    cs = state([], RelicId.TUNGSTEN_ROD)
    enemy_attack(cs, 4, hits=3)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 50 - 9

def test_tungsten_rod_turns_one_unblocked_damage_into_none():
    cs = state([], RelicId.TUNGSTEN_ROD)
    cs.player.block = 9
    enemy_attack(cs, 10)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 50 and cs.player.hp_loss_events == 0 and not cs.player.lost_hp_this_turn

def test_tungsten_rod_applies_to_hit_points_a_card_costs():
    cs = state([bloodletting()], RelicId.TUNGSTEN_ROD)
    play(cs)
    assert cs.player.current_hp == 50 - 2

def test_tungsten_rod_never_loses_less_than_nothing():
    cs = state([], RelicId.TUNGSTEN_ROD)
    cs.player.lose_hp(1)
    assert cs.player.current_hp == 50 and cs.player.hp_loss_events == 0

def test_tungsten_rod_does_not_protect_enemies():
    cs = state([], RelicId.TUNGSTEN_ROD)
    cs.enemies[0].apply_damage(10)
    assert cs.enemies[0].current_hp == 90


# ---------------------------------------------------------------- Beating Remnant
def test_beating_remnant_limits_a_hit_to_20():
    cs = state([], RelicId.BEATING_REMNANT)
    cs.player.max_hp = cs.player.current_hp = 80
    enemy_attack(cs, 35)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 60

def test_beating_remnant_limits_a_turns_total():
    cs = state([], RelicId.BEATING_REMNANT)
    cs.player.max_hp = cs.player.current_hp = 80
    enemy_attack(cs, 15, hits=3)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 60

def test_beating_remnant_counts_hit_points_lost_on_the_players_own_turn():
    cs = state([offering()], RelicId.BEATING_REMNANT)
    cs.player.max_hp = cs.player.current_hp = 80
    cs.player.draw_pile = []
    sim = plays(cs, (0, 0))
    enemy_attack(cs, 30)
    sim.end_turn()
    assert cs.player.current_hp == 80 - 20

def test_beating_remnant_starts_over_each_turn():
    cs = state([], RelicId.BEATING_REMNANT)
    cs.player.max_hp = cs.player.current_hp = 80
    enemy_attack(cs, 30)
    sim = CombatSimulator(cs)
    sim.end_turn()
    sim.end_turn()
    assert cs.player.current_hp == 80 - 40

def test_beating_remnant_does_not_count_blocked_damage():
    cs = state([], RelicId.BEATING_REMNANT)
    cs.player.max_hp = cs.player.current_hp = 80
    cs.player.block = 20
    enemy_attack(cs, 30)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 70

def test_tungsten_rod_then_beating_remnant_takes_one_off_first():
    cs = state([], RelicId.TUNGSTEN_ROD, RelicId.BEATING_REMNANT)
    cs.player.max_hp = cs.player.current_hp = 80
    enemy_attack(cs, 30)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 80 - 20

def test_beating_remnant_then_tungsten_rod_limits_first():
    cs = state([], RelicId.BEATING_REMNANT, RelicId.TUNGSTEN_ROD)
    cs.player.max_hp = cs.player.current_hp = 80
    enemy_attack(cs, 30)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 80 - 19


# ---------------------------------------------------------------- Ruined Helmet
def test_ruined_helmet_doubles_the_first_strength_gained():
    cs = state([inflame(), inflame()], RelicId.RUINED_HELMET)
    cs.energy = 9
    plays(cs, (0, 0), (0, 0))
    assert cs.player.status_amount(StatusId.STRENGTH) == 4 + 2

def test_ruined_helmet_is_spent_by_the_first_gain():
    cs = state([inflame()], RelicId.RUINED_HELMET)
    play(cs)
    assert relic(cs, RelicId.RUINED_HELMET).used

def test_ruined_helmet_ignores_strength_lost():
    cs = state([], RelicId.RUINED_HELMET)
    cs.player.apply_status(StatusId.STRENGTH, -2)
    assert cs.player.status_amount(StatusId.STRENGTH) == -2 and not relic(cs, RelicId.RUINED_HELMET).used

def test_ruined_helmet_still_doubles_the_first_gain_after_a_loss():
    cs = state([], RelicId.RUINED_HELMET)
    cs.player.apply_status(StatusId.STRENGTH, -2)
    cs.player.apply_status(StatusId.STRENGTH, 3)
    assert cs.player.status_amount(StatusId.STRENGTH) == 4

def test_ruined_helmet_does_not_double_other_statuses():
    cs = state([], RelicId.RUINED_HELMET)
    cs.player.apply_status(StatusId.DEXTERITY, 2)
    assert cs.player.status_amount(StatusId.DEXTERITY) == 2 and not relic(cs, RelicId.RUINED_HELMET).used

def test_ruined_helmet_does_not_double_enemy_strength():
    cs = state([], RelicId.RUINED_HELMET)
    cs.enemies[0].apply_status(StatusId.STRENGTH, 2)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2

def test_ruined_helmet_does_not_double_a_gain_that_is_spent_already():
    cs = state([inflame()], RelicId.RUINED_HELMET)
    relic(cs, RelicId.RUINED_HELMET).used = True
    play(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == 2


# ---------------------------------------------------------------- Unsettling Lamp
def test_unsettling_lamp_doubles_the_first_debuff_card():
    cs = state([bash(), bash()], RelicId.UNSETTLING_LAMP)
    cs.energy = 9
    plays(cs, (0, 0), (0, 0))
    assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == 4 + 2

def test_unsettling_lamp_doubles_every_debuff_of_that_card():
    cs = state([uppercut()], RelicId.UNSETTLING_LAMP)
    play(cs)
    assert cs.enemies[0].status_amount(StatusId.WEAK) == 2 and cs.enemies[0].status_amount(StatusId.VULNERABLE) == 2

def test_unsettling_lamp_is_spent_after_the_card_is_played():
    cs = state([bash()], RelicId.UNSETTLING_LAMP)
    play(cs)
    assert relic(cs, RelicId.UNSETTLING_LAMP).used and relic(cs, RelicId.UNSETTLING_LAMP).triggering is None

def test_unsettling_lamp_waits_for_a_card_that_debuffs():
    cs = state([strike(), bash()], RelicId.UNSETTLING_LAMP)
    sim = plays(cs, (0, 0))
    assert not relic(cs, RelicId.UNSETTLING_LAMP).used
    sim.play_card(0, 0)
    assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == 4

def test_unsettling_lamp_doubles_the_strength_mangle_takes_and_gives_back():
    cs = state([mangle()], RelicId.UNSETTLING_LAMP)
    sim = plays(cs, (0, 0))
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == -20
    sim.end_turn()
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 0

def test_unsettling_lamp_does_nothing_once_used():
    cs = state([bash()], RelicId.UNSETTLING_LAMP)
    relic(cs, RelicId.UNSETTLING_LAMP).used = True
    play(cs)
    assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == 2

def test_unsettling_lamp_ignores_buffs_the_player_gives_itself():
    cs = state([inflame(), bash()], RelicId.UNSETTLING_LAMP)
    cs.energy = 9
    sim = plays(cs, (0, 0))
    assert not relic(cs, RelicId.UNSETTLING_LAMP).used
    assert cs.player.status_amount(StatusId.STRENGTH) == 2

def test_unsettling_lamp_used_in_one_branch_is_not_used_in_another():
    cs = state([bash()], RelicId.UNSETTLING_LAMP)
    branch = CombatState.deepcopy(cs)
    play(branch)
    assert relic(branch, RelicId.UNSETTLING_LAMP).used and not relic(cs, RelicId.UNSETTLING_LAMP).used


# ---------------------------------------------------------------- Chemical X
def test_chemical_x_adds_two_to_x():
    cs = state([whirlwind()], RelicId.CHEMICAL_X, enemies=1)
    cs.energy = 2
    play(cs)
    assert hps(cs) == [100 - 4 * 5]

def test_chemical_x_works_with_no_energy():
    cs = state([whirlwind()], RelicId.CHEMICAL_X, enemies=1)
    cs.energy = 0
    play(cs)
    assert hps(cs) == [100 - 2 * 5]

def test_x_without_chemical_x():
    cs = state([whirlwind()], enemies=1)
    cs.energy = 2
    play(cs)
    assert hps(cs) == [100 - 2 * 5]

def test_chemical_x_still_spends_only_the_energy_there_is():
    cs = state([whirlwind()], RelicId.CHEMICAL_X)
    cs.energy = 2
    play(cs)
    assert cs.energy == 0

def test_chemical_x_does_not_change_other_cards():
    cs = state([strike()], RelicId.CHEMICAL_X)
    play(cs)
    assert hps(cs) == [94] and cs.energy == 2


# ---------------------------------------------------------------- Ice Cream
def test_ice_cream_keeps_unspent_energy():
    cs = state([], RelicId.ICE_CREAM)
    cs.energy = 2
    CombatSimulator(cs).end_turn()
    assert cs.energy == 2 + 3

def test_ice_cream_adds_up_over_turns():
    cs = state([], RelicId.ICE_CREAM)
    sim = CombatSimulator(cs)
    sim.end_turn()
    sim.end_turn()
    assert cs.energy == 3 + 3 + 3

def test_energy_resets_without_ice_cream():
    cs = state([])
    cs.energy = 2
    CombatSimulator(cs).end_turn()
    assert cs.energy == 3

def test_ice_cream_keeps_nothing_when_no_energy_is_left():
    cs = state([], RelicId.ICE_CREAM)
    cs.energy = 0
    CombatSimulator(cs).end_turn()
    assert cs.energy == 3


# ---------------------------------------------------------------- Ringing Triangle
def test_ringing_triangle_keeps_the_hand_after_the_first_turn():
    cs = state([defend()], RelicId.RINGING_TRIANGLE)
    cs.player.draw_pile = [strike() for _ in range(5)]
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == 6 and cs.player.discard_pile == []

def test_ringing_triangle_discards_the_hand_on_later_turns():
    cs = state([defend()], RelicId.RINGING_TRIANGLE)
    cs.turn_number = 2
    cs.player.draw_pile = [strike() for _ in range(5)]
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == 5 and len(cs.player.discard_pile) == 1

def test_hand_is_discarded_without_ringing_triangle():
    cs = state([defend()])
    cs.player.draw_pile = [strike() for _ in range(5)]
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == 5 and len(cs.player.discard_pile) == 1

def test_ringing_triangle_hand_stops_drawing_at_ten():
    cs = state([defend() for _ in range(8)], RelicId.RINGING_TRIANGLE)
    cs.player.draw_pile = [strike() for _ in range(5)]
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == 10


# ---------------------------------------------------------------- Sturdy Clamp
def test_sturdy_clamp_keeps_up_to_ten_block():
    cs = state([], RelicId.STURDY_CLAMP)
    cs.player.block = 25
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 10

def test_sturdy_clamp_keeps_less_than_ten_block_whole():
    cs = state([], RelicId.STURDY_CLAMP)
    cs.player.block = 6
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 6

def test_block_is_lost_without_sturdy_clamp():
    cs = state([])
    cs.player.block = 25
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 0

def test_sturdy_clamp_block_is_kept_when_the_enemy_hits_first():
    cs = state([], RelicId.STURDY_CLAMP)
    cs.player.block = 25
    enemy_attack(cs, 20)
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 5 and cs.player.current_hp == 50

def test_barricade_keeps_all_block_with_sturdy_clamp():
    cs = state([], RelicId.STURDY_CLAMP)
    cs.player.apply_status(StatusId.BARRICADE, 1)
    cs.player.block = 25
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 25

def test_block_kept_by_sturdy_clamp_is_not_block_gained():
    cs = state([], RelicId.STURDY_CLAMP, enemies=1)
    cs.player.apply_status(StatusId.JUGGERNAUT, 5)
    cs.player.block = 25
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [100]

def test_enemy_block_is_unaffected_by_sturdy_clamp():
    cs = state([], RelicId.STURDY_CLAMP)
    cs.enemies[0].block = 25
    cs.enemies[0].turn_start()
    assert cs.enemies[0].block == 25        # an enemy keeps its block until its own turn, relic or not


# ---------------------------------------------------------------- Lizard Tail
def test_lizard_tail_brings_the_player_back_at_half_hit_points():
    cs = state([], RelicId.LIZARD_TAIL)
    cs.player.max_hp, cs.player.current_hp = 80, 5
    enemy_attack(cs, 20)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.player.current_hp == 40 and not sim.is_over

def test_lizard_tail_works_once():
    cs = state([], RelicId.LIZARD_TAIL)
    cs.player.max_hp, cs.player.current_hp = 80, 5
    enemy_attack(cs, 50)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert relic(cs, RelicId.LIZARD_TAIL).used and not sim.is_over
    sim.end_turn()
    assert cs.player.current_hp == 0 and sim.is_over

def test_lizard_tail_rounds_half_down():
    cs = state([], RelicId.LIZARD_TAIL)
    cs.player.max_hp, cs.player.current_hp = 75, 1
    cs.player.lose_hp(5)
    assert cs.player.current_hp == 37

def test_lizard_tail_heals_at_least_one():
    cs = state([], RelicId.LIZARD_TAIL)
    cs.player.max_hp, cs.player.current_hp = 1, 1
    cs.player.lose_hp(1)
    assert cs.player.current_hp == 1

def test_lizard_tail_saves_a_player_who_kills_themselves():
    cs = state([offering()], RelicId.LIZARD_TAIL)
    cs.player.max_hp, cs.player.current_hp = 80, 6
    cs.player.draw_pile = []
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.player.current_hp == 40 and not sim.is_over

def test_a_spent_lizard_tail_does_not_save_the_player():
    cs = state([], RelicId.LIZARD_TAIL)
    relic(cs, RelicId.LIZARD_TAIL).used = True
    cs.player.lose_hp(500)
    assert cs.player.current_hp == 0

def test_lizard_tail_does_not_save_enemies():
    cs = state([], RelicId.LIZARD_TAIL)
    cs.enemies[0].apply_damage(500)
    assert cs.enemies[0].current_hp == 0

def test_lizard_tail_spent_in_one_branch_is_not_spent_in_another():
    cs = state([], RelicId.LIZARD_TAIL)
    branch = CombatState.deepcopy(cs)
    branch.player.lose_hp(500)
    assert relic(branch, RelicId.LIZARD_TAIL).used and not relic(cs, RelicId.LIZARD_TAIL).used

def test_lizard_tail_and_tungsten_rod_together():
    cs = state([], RelicId.LIZARD_TAIL, RelicId.TUNGSTEN_ROD)
    cs.player.max_hp, cs.player.current_hp = 80, 10
    enemy_attack(cs, 10)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 1 and not relic(cs, RelicId.LIZARD_TAIL).used


# ---------------------------------------------------------------- the pieces on their own
def test_vambrace_stays_with_the_card_that_triggered_it():
    from sts2_lite.relic import block_multiplier, block_gained
    cs = state([], RelicId.VAMBRACE)
    first, second = defend(), defend()
    assert block_multiplier(cs.player, first) == 2
    block_gained(cs.player, first, 5)
    assert block_multiplier(cs.player, first) == 2      # another block from the same card
    assert block_multiplier(cs.player, second) == 1

def test_vambrace_ignores_a_block_of_nothing():
    from sts2_lite.relic import block_multiplier, block_gained
    cs = state([], RelicId.VAMBRACE)
    block_gained(cs.player, defend(), 0)
    assert relic(cs, RelicId.VAMBRACE).triggering is None

def test_unsettling_lamp_is_not_triggered_by_a_debuff_on_the_player():
    from sts2_lite.relic import debuff_multiplier
    cs = state([], RelicId.UNSETTLING_LAMP)
    assert debuff_multiplier(cs.player, bash(), cs.player) == 1
    assert relic(cs, RelicId.UNSETTLING_LAMP).triggering is None

def test_hit_point_loss_is_never_negative():
    from sts2_lite.relic import _tungsten_rod_loss, _beating_remnant_loss
    cs = state([], RelicId.BEATING_REMNANT)
    relic(cs, RelicId.BEATING_REMNANT).value = 25
    assert _tungsten_rod_loss(RelicInstance(RelicId.TUNGSTEN_ROD), 0) == 0
    assert _beating_remnant_loss(relic(cs, RelicId.BEATING_REMNANT), 5) == 0

def test_a_relic_copy_keeps_the_card_it_is_working_on():
    original = RelicInstance(RelicId.VAMBRACE)
    original.triggering = defend()
    assert RelicInstance.deepcopy(original).triggering is original.triggering

def test_a_card_that_fails_after_giving_block_does_not_leave_vambrace_waiting(monkeypatch):
    from sts2_lite import card as card_module
    real = card_module.GET_CARD_FUNCTION[CardId.DEFEND_IRONCLAD]

    def block_then_fail(*args, **kwargs):
        real(*args, **kwargs)
        raise ValueError("fails after the block")
    monkeypatch.setitem(card_module.GET_CARD_FUNCTION, CardId.DEFEND_IRONCLAD, block_then_fail)
    cs = state([defend()], RelicId.VAMBRACE)
    with pytest.raises(ValueError):
        CombatSimulator(cs).play_card(0, 0)
    assert relic(cs, RelicId.VAMBRACE).triggering is None


# ---------------------------------------------------------------- Vambrace, from states saved from the game
def _saved(name):
    import json
    from pathlib import Path
    raw = json.loads((Path(__file__).parent / "data" / "relics" / f"{name}.json").read_text())
    return CombatState.from_dict(raw)

def _play_from_hand(cs, card_name):
    index = next(i for i, c in enumerate(cs.player.hand) if c.card_id.name == card_name)
    before = cs.player.block
    CombatSimulator(cs).play_card(index, 0)
    return cs.player.block - before

def test_saved_state_with_vambrace_waiting_reads_as_unused():
    assert not _saved("vambrace_active").player.relics[RelicId.VAMBRACE].used

def test_saved_state_with_vambrace_spent_reads_as_used():
    assert _saved("vambrace_inactive").player.relics[RelicId.VAMBRACE].used

def test_saved_state_defend_block_is_doubled_while_vambrace_is_waiting():
    assert _play_from_hand(_saved("vambrace_active"), "DEFEND_IRONCLAD") == 10

def test_saved_state_blood_wall_block_is_not_doubled_once_vambrace_is_spent():
    waiting = _play_from_hand(_saved("vambrace_active"), "BLOOD_WALL")
    spent = _play_from_hand(_saved("vambrace_inactive"), "BLOOD_WALL")
    assert waiting == 2 * spent
