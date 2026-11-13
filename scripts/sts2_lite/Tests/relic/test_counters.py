import pytest
from sts2_lite.card import CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.relic import RelicId, RelicInstance, SEEN_ATTACK, SEEN_SKILL
from sts2_lite.status import StatusId
from sts2_lite.Tests.relic.test_always_on import card, strike, twin_strike, defend, bash, inflame, whirlwind, held, relic, state, enemy_attack, plays
from sts2_lite.Tests.card.test_card import hps


def impervious():
    return card(CardId.IMPERVIOUS, 2, CardType.Skill, TargetType.Self)

def dazed():
    return card(CardId.DAZED, "Unplayable", CardType.Status, TargetType.Self)

def with_counter(cs, relic_id, counter):
    relic(cs, relic_id).counter = counter
    return cs

def status(cs, status_id):
    return cs.player.status_amount(status_id)

def draw_pile(cs, n=20):
    cs.player.draw_pile = [strike() for _ in range(n)]
    return cs


# ---------------------------------------------------------------- loading
GROUP_2 = ["PEN_NIB", "NUNCHAKU", "KUNAI", "SHURIKEN", "KUSARIGAMA", "LETTER_OPENER", "ORNAMENTAL_FAN", "TUNING_FORK", "RAINBOW_RING",
           "POCKETWATCH", "ART_OF_WAR", "RIPPLE_BASIN", "PERMAFROST", "GAME_PIECE", "MUMMIFIED_HAND", "RAZOR_TOOTH",
           "DAUGHTER_OF_THE_WIND", "INTIMIDATING_HELMET", "JOSS_PAPER", "BURNING_STICKS", "CHARONS_ASHES"]

@pytest.mark.parametrize("name", GROUP_2)
def test_every_relic_loads_from_its_bridge_id(name):
    assert RelicInstance.from_dict({"id": name, "counter": None}).relic_id == RelicId[name]

@pytest.mark.parametrize("name", GROUP_2)
def test_the_bridge_counter_is_kept(name):
    assert RelicInstance.from_dict({"id": name, "counter": 2}).counter == 2

@pytest.mark.parametrize("name, status, used", [
    ("BURNING_STICKS", "Active", False), ("BURNING_STICKS", "Normal", True),
    ("ART_OF_WAR", "Active", False), ("ART_OF_WAR", "Normal", True),
    ("RIPPLE_BASIN", "Active", False), ("RIPPLE_BASIN", "Normal", True),
    ("RAINBOW_RING", "Normal", False), ("RAINBOW_RING", "Active", True),
    ("PEN_NIB", "Active", False), ("PERMAFROST", "Normal", False)])
def test_a_spent_relic_is_read_from_the_bridge_status(name, status, used):
    assert RelicInstance.from_dict({"id": name, "counter": None, "status": status}).used is used

def test_counters_and_flags_are_kept_in_a_copy():
    cs = state([], RelicId.PEN_NIB, RelicId.RAINBOW_RING)
    relic(cs, RelicId.PEN_NIB).counter = 7
    relic(cs, RelicId.RAINBOW_RING).value = 3
    relic(cs, RelicId.RAINBOW_RING).used = True
    copy = CombatState.deepcopy(cs)
    assert relic(copy, RelicId.PEN_NIB).counter == 7
    assert relic(copy, RelicId.RAINBOW_RING).value == 3 and relic(copy, RelicId.RAINBOW_RING).used
    relic(copy, RelicId.PEN_NIB).counter = 0
    assert relic(cs, RelicId.PEN_NIB).counter == 7


# ---------------------------------------------------------------- Pen Nib
def test_pen_nib_doubles_the_tenth_attack():
    cs = with_counter(state([strike()], RelicId.PEN_NIB), RelicId.PEN_NIB, 9)
    plays(cs, (0, 0))
    assert hps(cs) == [100 - 12] and relic(cs, RelicId.PEN_NIB).counter == 0

def test_pen_nib_counts_up_without_doubling_before_that():
    cs = with_counter(state([strike()], RelicId.PEN_NIB), RelicId.PEN_NIB, 8)
    plays(cs, (0, 0))
    assert hps(cs) == [94] and relic(cs, RelicId.PEN_NIB).counter == 9

def test_pen_nib_starts_from_nothing_when_the_bridge_gives_no_counter():
    cs = state([strike()], RelicId.PEN_NIB)
    plays(cs, (0, 0))
    assert relic(cs, RelicId.PEN_NIB).counter == 1

def test_pen_nib_only_doubles_that_one_attack():
    cs = with_counter(state([strike(), strike()], RelicId.PEN_NIB), RelicId.PEN_NIB, 9)
    plays(cs, (0, 0), (0, 0))
    assert hps(cs) == [100 - 12 - 6]

def test_pen_nib_doubles_every_hit_of_a_multi_hit_attack():
    cs = with_counter(state([twin_strike()], RelicId.PEN_NIB), RelicId.PEN_NIB, 9)
    plays(cs, (0, 0))
    assert hps(cs) == [100 - 20]

def test_pen_nib_ignores_skills_and_powers():
    cs = with_counter(state([defend(), inflame()], RelicId.PEN_NIB), RelicId.PEN_NIB, 9)
    plays(cs, (0, 0), (0, 0))
    assert relic(cs, RelicId.PEN_NIB).counter == 9

def test_pen_nib_multiplies_with_vulnerable():
    cs = with_counter(state([strike()], RelicId.PEN_NIB), RelicId.PEN_NIB, 9)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    plays(cs, (0, 0))
    assert hps(cs) == [100 - 18]

def test_a_card_that_fails_does_not_count_for_pen_nib_or_give_the_helmet_block(monkeypatch):
    from sts2_lite import card as card_module
    real = card_module.GET_CARD_FUNCTION[CardId.BASH]

    def fail(*args, **kwargs):
        raise ValueError("cannot be played")
    monkeypatch.setitem(card_module.GET_CARD_FUNCTION, CardId.BASH, fail)
    cs = with_counter(state([bash()], RelicId.PEN_NIB, RelicId.INTIMIDATING_HELMET), RelicId.PEN_NIB, 9)
    with pytest.raises(ValueError):
        CombatSimulator(cs).play_card(0, 0)
    assert relic(cs, RelicId.PEN_NIB).counter == 9 and relic(cs, RelicId.PEN_NIB).triggering is None
    assert cs.player.block == 0 and cs.energy == 3


# ---------------------------------------------------------------- Nunchaku
def test_nunchaku_gives_energy_on_the_tenth_attack():
    cs = with_counter(state([strike()], RelicId.NUNCHAKU), RelicId.NUNCHAKU, 9)
    plays(cs, (0, 0))
    assert cs.energy == 3 and relic(cs, RelicId.NUNCHAKU).counter == 0

def test_nunchaku_counts_up_on_the_way():
    cs = with_counter(state([strike()], RelicId.NUNCHAKU), RelicId.NUNCHAKU, 4)
    plays(cs, (0, 0))
    assert cs.energy == 2 and relic(cs, RelicId.NUNCHAKU).counter == 5

def test_nunchaku_ignores_other_card_types():
    cs = with_counter(state([defend()], RelicId.NUNCHAKU), RelicId.NUNCHAKU, 9)
    plays(cs, (0, 0))
    assert cs.energy == 2 and relic(cs, RelicId.NUNCHAKU).counter == 9


# ---------------------------------------------------------------- Kunai, Shuriken, Kusarigama, Ornamental Fan
def test_kunai_gives_dexterity_on_the_third_attack_of_a_turn():
    cs = with_counter(state([strike()], RelicId.KUNAI), RelicId.KUNAI, 2)
    plays(cs, (0, 0))
    assert status(cs, StatusId.DEXTERITY) == 1 and relic(cs, RelicId.KUNAI).counter == 0

def test_kunai_counts_three_attacks_from_nothing():
    cs = state([strike(), strike(), strike()], RelicId.KUNAI)
    cs.energy = 3
    sim = CombatSimulator(cs)
    sim.play_card(0, 0); sim.play_card(0, 0)
    assert status(cs, StatusId.DEXTERITY) == 0
    sim.play_card(0, 0)
    assert status(cs, StatusId.DEXTERITY) == 1

def test_shuriken_gives_strength_on_the_third_attack():
    cs = with_counter(state([strike()], RelicId.SHURIKEN), RelicId.SHURIKEN, 2)
    plays(cs, (0, 0))
    assert status(cs, StatusId.STRENGTH) == 1 and hps(cs) == [94]       # the Strength comes after the hit

def test_the_attack_count_of_kunai_and_shuriken_starts_again_each_turn():
    cs = draw_pile(state([], RelicId.KUNAI, RelicId.SHURIKEN, RelicId.ORNAMENTAL_FAN, RelicId.LETTER_OPENER))
    for relic_id in (RelicId.KUNAI, RelicId.SHURIKEN, RelicId.ORNAMENTAL_FAN, RelicId.LETTER_OPENER):
        relic(cs, relic_id).counter = 2
    CombatSimulator(cs).end_turn()
    assert all(relic(cs, relic_id).counter == 0 for relic_id in (RelicId.KUNAI, RelicId.SHURIKEN, RelicId.ORNAMENTAL_FAN, RelicId.LETTER_OPENER))

def test_kusarigama_hits_an_enemy_on_the_third_attack():
    cs = with_counter(state([strike()], RelicId.KUSARIGAMA), RelicId.KUSARIGAMA, 2)
    plays(cs, (0, 0))
    assert hps(cs) == [100 - 6 - 6] and relic(cs, RelicId.KUSARIGAMA).counter == 0

def test_kusarigama_picks_one_of_several_enemies():
    cs = with_counter(state([strike()], RelicId.KUSARIGAMA, enemies=3), RelicId.KUSARIGAMA, 2)
    plays(cs, (0, 0))
    assert sum(100 - hp for hp in hps(cs)) == 12

def test_kusarigama_damage_ignores_strength_and_vulnerable():
    cs = with_counter(state([strike()], RelicId.KUSARIGAMA), RelicId.KUSARIGAMA, 2)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    cs.player.apply_status(StatusId.STRENGTH, 2)
    plays(cs, (0, 0))
    assert hps(cs) == [100 - 12 - 6]

def test_kusarigama_counts_start_again_when_the_turn_ends():
    cs = with_counter(draw_pile(state([], RelicId.KUSARIGAMA)), RelicId.KUSARIGAMA, 2)
    CombatSimulator(cs).end_turn()
    assert relic(cs, RelicId.KUSARIGAMA).counter == 0

def test_ornamental_fan_gives_block_on_the_third_attack():
    cs = with_counter(state([strike()], RelicId.ORNAMENTAL_FAN), RelicId.ORNAMENTAL_FAN, 2)
    plays(cs, (0, 0))
    assert cs.player.block == 4

def test_ornamental_fan_block_is_not_changed_by_dexterity():
    cs = with_counter(state([strike()], RelicId.ORNAMENTAL_FAN), RelicId.ORNAMENTAL_FAN, 2)
    cs.player.apply_status(StatusId.DEXTERITY, 3)
    plays(cs, (0, 0))
    assert cs.player.block == 4


# ---------------------------------------------------------------- Letter Opener, Tuning Fork
def test_letter_opener_hurts_every_enemy_on_the_third_skill():
    cs = with_counter(state([defend()], RelicId.LETTER_OPENER, enemies=3), RelicId.LETTER_OPENER, 2)
    plays(cs, (0, 0))
    assert hps(cs) == [95, 95, 95] and relic(cs, RelicId.LETTER_OPENER).counter == 0

def test_letter_opener_ignores_attacks():
    cs = with_counter(state([strike()], RelicId.LETTER_OPENER), RelicId.LETTER_OPENER, 2)
    plays(cs, (0, 0))
    assert hps(cs) == [94] and relic(cs, RelicId.LETTER_OPENER).counter == 2

def test_letter_opener_can_win_the_fight():
    cs = with_counter(state([defend()], RelicId.LETTER_OPENER, enemy_hp=5), RelicId.LETTER_OPENER, 2)
    sim = plays(cs, (0, 0))
    assert sim.is_over

def test_tuning_fork_gives_block_on_the_tenth_skill():
    cs = with_counter(state([defend()], RelicId.TUNING_FORK), RelicId.TUNING_FORK, 9)
    plays(cs, (0, 0))
    assert cs.player.block == 5 + 7 and relic(cs, RelicId.TUNING_FORK).counter == 0

def test_tuning_fork_counts_up_before_that():
    cs = with_counter(state([defend()], RelicId.TUNING_FORK), RelicId.TUNING_FORK, 8)
    plays(cs, (0, 0))
    assert cs.player.block == 5 and relic(cs, RelicId.TUNING_FORK).counter == 9


# ---------------------------------------------------------------- Rainbow Ring
def test_rainbow_ring_needs_an_attack_a_skill_and_a_power_in_one_turn():
    cs = state([strike(), defend(), inflame()], RelicId.RAINBOW_RING)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0); sim.play_card(0, 0)
    assert status(cs, StatusId.STRENGTH) == 0 and status(cs, StatusId.DEXTERITY) == 0
    sim.play_card(0, 0)
    assert status(cs, StatusId.STRENGTH) == 2 + 1 and status(cs, StatusId.DEXTERITY) == 1       # Inflame gives 2 too
    assert relic(cs, RelicId.RAINBOW_RING).used

@pytest.mark.parametrize("hand", [
    ["strike", "defend"], ["strike", "inflame"], ["defend", "inflame"], ["strike", "strike", "defend", "defend"]])
def test_rainbow_ring_needs_all_three_types(hand):
    makers = {"strike": strike, "defend": defend, "inflame": inflame}
    cs = state([makers[name]() for name in hand], RelicId.RAINBOW_RING)
    cs.energy = 4
    sim = CombatSimulator(cs)
    for _ in hand:
        sim.play_card(0, 0)
    assert status(cs, StatusId.DEXTERITY) == 0 and not relic(cs, RelicId.RAINBOW_RING).used

def test_rainbow_ring_gives_its_bonus_once_a_turn():
    cs = state([strike(), defend(), inflame(), strike(), defend(), inflame()], RelicId.RAINBOW_RING)
    cs.energy = 6
    sim = CombatSimulator(cs)
    for _ in range(6):
        sim.play_card(0, 0)
    assert status(cs, StatusId.DEXTERITY) == 1

def test_rainbow_ring_starts_again_next_turn():
    cs = draw_pile(state([], RelicId.RAINBOW_RING))
    relic(cs, RelicId.RAINBOW_RING).used = True
    relic(cs, RelicId.RAINBOW_RING).value = 7
    CombatSimulator(cs).end_turn()
    assert not relic(cs, RelicId.RAINBOW_RING).used and relic(cs, RelicId.RAINBOW_RING).value == 0

def test_a_rainbow_ring_that_has_paid_out_is_remembered_within_the_turn_only():
    old = state([], RelicId.RAINBOW_RING)
    relic(old, RelicId.RAINBOW_RING).used = True
    relic(old, RelicId.RAINBOW_RING).value = 7
    same = state([], RelicId.RAINBOW_RING)
    same.carry_turn_counters(old)
    same.carry_combat_counters(old)
    later = state([], RelicId.RAINBOW_RING)
    later.turn_number = 2
    later.carry_turn_counters(old)
    later.carry_combat_counters(old)
    assert relic(same, RelicId.RAINBOW_RING).used and relic(same, RelicId.RAINBOW_RING).value == 7
    assert not relic(later, RelicId.RAINBOW_RING).used and relic(later, RelicId.RAINBOW_RING).value == 0


# ---------------------------------------------------------------- Pocketwatch
def test_pocketwatch_counts_every_card_played():
    cs = state([strike(), defend(), inflame()], RelicId.POCKETWATCH)
    cs.energy = 3
    sim = CombatSimulator(cs)
    for _ in range(3):
        sim.play_card(0, 0)
    assert relic(cs, RelicId.POCKETWATCH).counter == 3

def test_pocketwatch_draws_three_more_after_a_turn_of_three_cards_or_fewer():
    cs = with_counter(draw_pile(state([], RelicId.POCKETWATCH)), RelicId.POCKETWATCH, 3)
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == 5 + 3 and relic(cs, RelicId.POCKETWATCH).counter == 0

def test_pocketwatch_draws_nothing_extra_after_a_longer_turn():
    cs = with_counter(draw_pile(state([], RelicId.POCKETWATCH)), RelicId.POCKETWATCH, 4)
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == 5

def test_pocketwatch_does_not_carry_the_bonus_to_the_turn_after():
    cs = with_counter(draw_pile(state([], RelicId.POCKETWATCH)), RelicId.POCKETWATCH, 3)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert len(cs.player.hand) == 5 + 3
    relic(cs, RelicId.POCKETWATCH).counter = 4      # a longer turn this time
    sim.end_turn()
    assert len(cs.player.hand) == 5


# ---------------------------------------------------------------- Art of War, Ripple Basin
def test_art_of_war_gives_energy_after_a_turn_without_attacks():
    cs = draw_pile(state([], RelicId.ART_OF_WAR))
    CombatSimulator(cs).end_turn()
    assert cs.energy == 4

def test_art_of_war_gives_nothing_after_a_turn_with_an_attack():
    cs = draw_pile(state([strike()], RelicId.ART_OF_WAR))
    sim = plays(cs, (0, 0))
    sim.end_turn()
    assert cs.energy == 3

def test_art_of_war_looks_only_at_the_turn_before():
    cs = draw_pile(state([strike()], RelicId.ART_OF_WAR))
    sim = plays(cs, (0, 0))
    sim.end_turn()                  # turn 2 follows an attack: no energy
    sim.end_turn()                  # turn 3 follows a turn without one: energy
    assert cs.energy == 4

def test_art_of_war_ignores_other_card_types():
    cs = draw_pile(state([defend()], RelicId.ART_OF_WAR))
    sim = plays(cs, (0, 0))
    sim.end_turn()
    assert cs.energy == 4

def test_ripple_basin_gives_block_when_no_attack_was_played():
    cs = draw_pile(state([], RelicId.RIPPLE_BASIN))
    enemy_attack(cs, 6)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 50 - 2

def test_ripple_basin_gives_nothing_after_an_attack():
    cs = draw_pile(state([strike()], RelicId.RIPPLE_BASIN))
    enemy_attack(cs, 6)
    plays(cs, (0, 0)).end_turn()
    assert cs.player.current_hp == 50 - 6

def test_ripple_basin_checks_each_turn_again():
    cs = draw_pile(state([strike()], RelicId.RIPPLE_BASIN))
    enemy_attack(cs, 6)
    sim = plays(cs, (0, 0))
    sim.end_turn()                  # attack: no block, 6 damage
    sim.end_turn()                  # no attack in turn 2: 4 block, 2 damage
    assert cs.player.current_hp == 50 - 6 - 2

def test_art_of_war_and_ripple_basin_flags_carry_within_a_turn_only():
    old = state([], RelicId.ART_OF_WAR, RelicId.RIPPLE_BASIN)
    relic(old, RelicId.ART_OF_WAR).used = True
    relic(old, RelicId.RIPPLE_BASIN).used = True
    same = state([], RelicId.ART_OF_WAR, RelicId.RIPPLE_BASIN)
    same.carry_turn_counters(old)
    later = state([], RelicId.ART_OF_WAR, RelicId.RIPPLE_BASIN)
    later.turn_number = 2
    later.carry_turn_counters(old)
    later.carry_combat_counters(old)
    assert relic(same, RelicId.ART_OF_WAR).used and relic(same, RelicId.RIPPLE_BASIN).used
    assert not relic(later, RelicId.ART_OF_WAR).used and not relic(later, RelicId.RIPPLE_BASIN).used


# ---------------------------------------------------------------- Powers: Permafrost, Game Piece, Mummified Hand
def test_permafrost_gives_block_for_the_first_power_only():
    cs = state([inflame(), inflame()], RelicId.PERMAFROST)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.player.block == 7
    sim.play_card(0, 0)
    assert cs.player.block == 7

def test_permafrost_ignores_other_cards():
    cs = state([strike(), defend()], RelicId.PERMAFROST)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0); sim.play_card(0, 0)
    assert cs.player.block == 5 and not relic(cs, RelicId.PERMAFROST).used

def test_a_spent_permafrost_carries_to_the_next_state_of_the_fight():
    old = state([], RelicId.PERMAFROST)
    relic(old, RelicId.PERMAFROST).used = True
    new = state([], RelicId.PERMAFROST)
    new.turn_number = 3
    new.carry_combat_counters(old)
    assert relic(new, RelicId.PERMAFROST).used

def test_game_piece_draws_a_card_for_each_power():
    cs = draw_pile(state([inflame(), inflame(), strike()], RelicId.GAME_PIECE))
    cs.energy = 2
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert len(cs.player.hand) == 2 + 1
    sim.play_card(0, 0)
    assert len(cs.player.hand) == 1 + 2

def test_game_piece_ignores_attacks():
    cs = draw_pile(state([strike()], RelicId.GAME_PIECE))
    plays(cs, (0, 0))
    assert len(cs.player.hand) == 0

def test_mummified_hand_makes_a_card_in_hand_free_this_turn():
    cs = state([inflame(), defend()], RelicId.MUMMIFIED_HAND)
    plays(cs, (0, 0))
    free = cs.player.hand[0]
    assert free.energy_cost == 0 and free.restore_cost == 1

def test_mummified_hand_picks_a_card_that_costs_energy():
    cs = state([inflame(), card(CardId.BLOODLETTING, 0, CardType.Skill, TargetType.Self), bash()], RelicId.MUMMIFIED_HAND)
    plays(cs, (0, 0))
    costs = sorted(c.energy_cost for c in cs.player.hand)
    assert costs == [0, 0] and any(c.restore_cost == 2 for c in cs.player.hand)

def test_mummified_hand_does_nothing_with_nothing_to_discount():
    cs = state([inflame(), card(CardId.BLOODLETTING, 0, CardType.Skill, TargetType.Self)], RelicId.MUMMIFIED_HAND)
    plays(cs, (0, 0))
    assert cs.player.hand[0].restore_cost is None

def test_the_free_card_costs_nothing_and_gets_its_cost_back_at_the_end_of_the_turn():
    cs = draw_pile(state([inflame(), bash()], RelicId.MUMMIFIED_HAND))
    sim = plays(cs, (0, 0))
    sim.play_card(0, 0)
    assert cs.energy == 2 and hps(cs) == [100 - 8 - 2]       # Inflame's Strength
    sim.end_turn()
    assert all(c.restore_cost is None for c in cs.player.discard_pile + cs.player.draw_pile + cs.player.hand)


# ---------------------------------------------------------------- Razor Tooth, Daughter of the Wind
def test_razor_tooth_upgrades_an_attack_after_it_is_played():
    cs = state([strike()], RelicId.RAZOR_TOOTH)
    original = cs.player.hand[0]
    plays(cs, (0, 0))
    assert hps(cs) == [94]                                  # this play was not upgraded
    assert cs.player.discard_pile[0].is_upgraded and not original.is_upgraded

def test_razor_tooth_upgrades_a_skill():
    cs = state([defend()], RelicId.RAZOR_TOOTH)
    plays(cs, (0, 0))
    assert cs.player.discard_pile[0].is_upgraded

def test_razor_tooth_leaves_powers_alone():
    cs = state([inflame()], RelicId.RAZOR_TOOTH)
    plays(cs, (0, 0))
    assert not cs.player.hand and not cs.player.discard_pile

def test_razor_tooth_upgrades_an_exhausted_card_too():
    cs = state([impervious()], RelicId.RAZOR_TOOTH)
    cs.energy = 3
    plays(cs, (0, 0))
    assert cs.player.exhaust_pile[0].is_upgraded and not cs.player.discard_pile

def test_razor_tooth_keeps_an_upgraded_card_as_it_is():
    cs = state([strike(up=True)], RelicId.RAZOR_TOOTH)
    played = cs.player.hand[0]
    plays(cs, (0, 0))
    assert cs.player.discard_pile[0] is played

def test_the_upgraded_card_hits_harder_next_time():
    cs = draw_pile(state([strike()], RelicId.RAZOR_TOOTH), 0)
    sim = plays(cs, (0, 0))
    cs.player.hand.append(cs.player.discard_pile.pop())
    sim.play_card(0, 0)
    assert hps(cs) == [100 - 6 - 9]

def test_daughter_of_the_wind_gives_one_block_for_each_attack():
    cs = state([strike(), strike(), defend()], RelicId.DAUGHTER_OF_THE_WIND)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0); sim.play_card(0, 0)
    assert cs.player.block == 2
    sim.play_card(0, 0)
    assert cs.player.block == 2 + 5


# ---------------------------------------------------------------- Intimidating Helmet
def test_intimidating_helmet_gives_block_for_a_card_that_costs_two_or_more():
    cs = state([bash()], RelicId.INTIMIDATING_HELMET)
    plays(cs, (0, 0))
    assert cs.player.block == 4

def test_intimidating_helmet_ignores_cheaper_cards():
    cs = state([strike(), defend()], RelicId.INTIMIDATING_HELMET)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0); sim.play_card(0, 0)
    assert cs.player.block == 5

def test_intimidating_helmet_counts_the_energy_put_into_an_x_card():
    big = state([whirlwind()], RelicId.INTIMIDATING_HELMET)
    small = state([whirlwind()], RelicId.INTIMIDATING_HELMET)
    small.energy = 1
    plays(big, (0, 0)); plays(small, (0, 0))
    assert big.player.block == 4 and small.player.block == 0

def test_intimidating_helmet_ignores_a_card_that_was_played_for_free():
    cs = state([bash()], RelicId.INTIMIDATING_HELMET)
    sim = CombatSimulator(cs)
    sim.auto_play(cs.player.hand[0])
    assert cs.player.block == 0


# ---------------------------------------------------------------- Joss Paper
def test_joss_paper_draws_a_card_on_the_fifth_exhaust():
    cs = with_counter(draw_pile(state([impervious()], RelicId.JOSS_PAPER)), RelicId.JOSS_PAPER, 4)
    cs.energy = 3
    plays(cs, (0, 0))
    assert len(cs.player.hand) == 1 and relic(cs, RelicId.JOSS_PAPER).counter == 0

def test_joss_paper_counts_the_exhausts_on_the_way():
    cs = with_counter(draw_pile(state([impervious()], RelicId.JOSS_PAPER)), RelicId.JOSS_PAPER, 1)
    cs.energy = 3
    plays(cs, (0, 0))
    assert len(cs.player.hand) == 0 and relic(cs, RelicId.JOSS_PAPER).counter == 2

def test_joss_paper_counts_ethereal_cards_once_the_hand_is_discarded():
    cs = with_counter(draw_pile(state([dazed()], RelicId.JOSS_PAPER)), RelicId.JOSS_PAPER, 4)
    CombatSimulator(cs).end_turn()
    assert relic(cs, RelicId.JOSS_PAPER).counter == 0
    assert len(cs.player.hand) == 5 + 1                     # the card it drew stays in hand next turn

def test_joss_paper_counts_each_ethereal_card_once():
    cs = with_counter(draw_pile(state([dazed(), dazed()], RelicId.JOSS_PAPER)), RelicId.JOSS_PAPER, 0)
    CombatSimulator(cs).end_turn()
    assert relic(cs, RelicId.JOSS_PAPER).counter == 2


# ---------------------------------------------------------------- Burning Sticks, Charon's Ashes
def test_burning_sticks_copies_the_first_skill_exhausted_in_a_fight():
    cs = state([impervious()], RelicId.BURNING_STICKS)
    cs.energy = 3
    plays(cs, (0, 0))
    assert len(cs.player.hand) == 1 and cs.player.hand[0].card_id == CardId.IMPERVIOUS
    assert relic(cs, RelicId.BURNING_STICKS).used

def test_burning_sticks_works_once():
    cs = state([impervious()], RelicId.BURNING_STICKS)
    cs.energy = 6
    sim = plays(cs, (0, 0))
    sim.play_card(0, 0)                 # the copy is played and exhausted: no second copy
    assert len(cs.player.hand) == 0 and len(cs.player.exhaust_pile) == 2

def test_burning_sticks_ignores_exhausted_cards_that_are_not_skills():
    cs = state([dazed()], RelicId.BURNING_STICKS)
    CombatSimulator(cs).end_turn()
    assert not relic(cs, RelicId.BURNING_STICKS).used

def test_charons_ashes_hurts_every_enemy_for_each_exhausted_card():
    cs = state([impervious()], RelicId.CHARONS_ASHES, enemies=2)
    cs.energy = 3
    plays(cs, (0, 0))
    assert hps(cs) == [97, 97]

def test_charons_ashes_counts_ethereal_cards():
    cs = draw_pile(state([dazed(), dazed()], RelicId.CHARONS_ASHES))
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [100 - 6]

def test_charons_ashes_kills_an_enemy_on_one_hit_point():
    cs = state([impervious()], RelicId.CHARONS_ASHES, enemies=2, enemy_hp=1)
    cs.energy = 3
    sim = plays(cs, (0, 0))
    assert not cs.enemies and sim.is_over

def test_charons_ashes_damage_ignores_vulnerable():
    cs = state([impervious()], RelicId.CHARONS_ASHES)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    cs.energy = 3
    plays(cs, (0, 0))
    assert hps(cs) == [97]


# ---------------------------------------------------------------- together
def test_a_fight_with_several_of_these_relics_keeps_each_count():
    cs = state([strike(), strike(), strike(), defend()], RelicId.PEN_NIB, RelicId.NUNCHAKU, RelicId.KUNAI, RelicId.ORNAMENTAL_FAN,
               RelicId.DAUGHTER_OF_THE_WIND, RelicId.POCKETWATCH)
    cs.energy = 4
    sim = CombatSimulator(cs)
    for _ in range(4):
        sim.play_card(0, 0)
    assert relic(cs, RelicId.PEN_NIB).counter == 3 and relic(cs, RelicId.NUNCHAKU).counter == 3
    assert relic(cs, RelicId.KUNAI).counter == 0 and status(cs, StatusId.DEXTERITY) == 1
    assert relic(cs, RelicId.POCKETWATCH).counter == 4
    assert cs.player.block == 3 + 4 + 5 + 1         # three Daughter, Fan, Defend with Dexterity


# ---------------------------------------------------------------- states saved from the game
def _capture(name, energy=None):
    """A saved state; `energy` is for captures taken with nothing left to spend."""
    import json
    from pathlib import Path
    cs = CombatState.from_dict(json.loads((Path(__file__).parents[1] / "data" / "relics" / f"{name}.json").read_text()))
    if energy is not None:
        cs.energy = energy
        for c in cs.player.hand:
            c.is_unplayable = False
    return cs

def _play(cs, card_name):
    index = next(i for i, c in enumerate(cs.player.hand) if c.card_id.name == card_name)
    CombatSimulator(cs).play_card(index, 0)

def _hand(cs):
    return sorted(c.card_id.name for c in cs.player.hand)

def _enemy_vulnerable(cs):
    return cs.enemies[0].status_amount(StatusId.VULNERABLE)

def _counters(cs, *relic_ids):
    return [relic(cs, r).counter for r in relic_ids]

PEN_NUNCHAKU_FORK = (RelicId.PEN_NIB, RelicId.NUNCHAKU, RelicId.TUNING_FORK)

def test_saved_counters_are_read_and_an_active_status_is_not_a_spent_relic():
    assert _counters(_capture("pen_nib_nuncaku_tuning_fork"), *PEN_NUNCHAKU_FORK) == [9, 9, 9]
    cs = _capture("kunai")
    assert relic(cs, RelicId.KUNAI).counter == 2 and not relic(cs, RelicId.KUNAI).used
    assert not relic(_capture("joss_paper"), RelicId.JOSS_PAPER).used

def test_saved_state_the_tenth_attack_is_doubled_and_gives_energy():
    cs = _capture("pen_nib_nuncaku_tuning_fork")
    hp = cs.enemies[0].current_hp
    _play(cs, "STRIKE_IRONCLAD")
    assert hp - cs.enemies[0].current_hp == 12
    assert cs.energy == 44                                  # a Strike costs 1, Nunchaku gives it back
    assert _counters(cs, *PEN_NUNCHAKU_FORK) == [0, 0, 9]

def test_saved_state_the_attack_after_the_tenth_is_not_doubled():
    cs = _capture("pen_nib_nuncaku_tuning_fork")
    _play(cs, "STRIKE_IRONCLAD")
    hp = cs.enemies[0].current_hp
    _play(cs, "STRIKE_IRONCLAD")
    assert hp - cs.enemies[0].current_hp == 6
    assert cs.energy == 43
    assert _counters(cs, *PEN_NUNCHAKU_FORK) == [1, 1, 9]

def test_saved_state_the_tenth_skill_gives_block():
    cs = _capture("pen_nib_nuncaku_tuning_fork")
    cs.player.hand.append(_capture("art_of_war_before").player.hand[0])   # a Defend
    block = cs.player.block
    _play(cs, "DEFEND_IRONCLAD")
    assert cs.player.block - block == 5 + 7
    assert relic(cs, RelicId.TUNING_FORK).counter == 0

def test_saved_state_the_third_attack_of_the_turn_gives_dexterity():
    cs = _capture("kunai", energy=3)
    _play(cs, "STRIKE_IRONCLAD")
    assert status(cs, StatusId.DEXTERITY) == 1
    assert relic(cs, RelicId.KUNAI).counter == 0

def test_saved_state_kunai_needs_another_attack_when_a_skill_is_played():
    cs = _capture("kunai", energy=3)
    _play(cs, "DEFEND_IRONCLAD")
    assert status(cs, StatusId.DEXTERITY) == 0
    assert relic(cs, RelicId.KUNAI).counter == 2

def test_saved_state_the_fifth_exhaust_draws_a_card():
    cs = _capture("joss_paper", energy=3)
    cs.player.hand.append(_capture("burning_sticks_before").player.hand[-1])        # a Tremble, which exhausts
    drawn_from = len(cs.player.draw_pile)
    _play(cs, "TREMBLE")
    assert relic(cs, RelicId.JOSS_PAPER).counter == 0
    assert len(cs.player.draw_pile) == drawn_from - 1
    assert len(cs.player.hand) == 4                          # 3 + Tremble - Tremble + the drawn card

def test_saved_state_pocketwatch_counted_five_cards_so_next_turn_draws_normally():
    cs = _capture("joss_paper")
    assert relic(cs, RelicId.POCKETWATCH).counter == 5
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == 5 and cs.turn_number == 2

def test_saved_state_pocketwatch_counted_two_cards_so_next_turn_draws_three_more():
    cs = _capture("pocketwatch")
    assert relic(cs, RelicId.POCKETWATCH).counter == 2
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == 8 and cs.turn_number == 3  # the draw pile was empty: the discard pile is shuffled back in

def test_saved_state_burning_sticks_copies_the_first_exhausted_skill():
    cs = _capture("burning_sticks_before")
    _play(cs, "TREMBLE")
    after = _capture("burning_sticks_after")
    assert _hand(cs) == _hand(after)
    assert [c.card_id.name for c in cs.player.exhaust_pile] == [c.card_id.name for c in after.player.exhaust_pile]
    assert cs.energy == after.energy == 2
    assert _enemy_vulnerable(cs) == _enemy_vulnerable(after) > 0

def test_saved_state_burning_sticks_has_only_one_copy_a_combat():
    cs = _capture("burning_sticks_after")                    # the game reports the relic as spent
    assert relic(cs, RelicId.BURNING_STICKS).used
    _play(cs, "TREMBLE")
    names = _hand(_capture("burning_sticks_before"))
    names.remove("TREMBLE")
    assert _hand(cs) == names                                # the Tremble is gone and no copy took its place

def test_saved_art_of_war_status_reads_as_waiting_then_spent():
    assert not relic(_capture("art_of_war_before"), RelicId.ART_OF_WAR).used
    assert relic(_capture("art_of_war_after"), RelicId.ART_OF_WAR).used

def test_saved_ripple_basin_status_reads_as_waiting_then_spent():
    assert not relic(_capture("ripple_basin_before"), RelicId.RIPPLE_BASIN).used
    assert relic(_capture("ripple_basin_after"), RelicId.RIPPLE_BASIN).used

def test_saved_burning_sticks_status_reads_as_waiting_then_spent():
    assert not relic(_capture("burning_sticks_before"), RelicId.BURNING_STICKS).used
    assert relic(_capture("burning_sticks_after"), RelicId.BURNING_STICKS).used

@pytest.mark.parametrize("name", ["art_of_war", "ripple_basin"])
def test_saved_state_an_attack_played_matches_what_the_game_did(name):
    cs = _capture(f"{name}_before")
    _play(cs, "STRIKE_IRONCLAD")
    after = _capture(f"{name}_after")
    assert cs.enemies[0].current_hp == after.enemies[0].current_hp
    assert cs.energy == after.energy
    assert _hand(cs) == _hand(after)
    assert len(cs.player.discard_pile) == len(after.player.discard_pile)
    assert relic(cs, RelicId.ART_OF_WAR if name == "art_of_war" else RelicId.RIPPLE_BASIN).used

def test_saved_state_art_of_war_gives_energy_after_a_turn_without_attacks():
    cs = _capture("art_of_war_before")
    CombatSimulator(cs).end_turn()
    assert cs.energy == cs.max_energy + 1

def test_saved_state_art_of_war_gives_nothing_after_an_attack():
    cs = _capture("art_of_war_before")
    _play(cs, "STRIKE_IRONCLAD")
    CombatSimulator(cs).end_turn()
    assert cs.energy == cs.max_energy

def test_a_state_read_after_an_attack_still_remembers_it():
    cs = _capture("art_of_war_after")                       # a Strike was played this turn
    CombatSimulator(cs).end_turn()
    assert cs.energy == cs.max_energy

def test_saved_state_ripple_basin_gives_block_only_without_attacks():
    from sts2_lite.events import EventType
    quiet, busy = _capture("ripple_basin_before"), _capture("ripple_basin_before")
    _play(busy, "STRIKE_IRONCLAD")
    for cs in (quiet, busy):
        cs.player.block = 0
        CombatSimulator(cs).fire(EventType.END_TURN)
    assert quiet.player.block == 4 and busy.player.block == 0

def test_a_ripple_basin_read_after_an_attack_gives_no_block():
    from sts2_lite.events import EventType
    cs = _capture("ripple_basin_after")
    cs.player.block = 0
    CombatSimulator(cs).fire(EventType.END_TURN)
    assert cs.player.block == 0


# ---------------------------------------------------------------- Rainbow Ring: what the bridge says it has seen
def _rainbow(types_played=None, status="Normal"):
    raw = {"id": "RAINBOW_RING", "counter": None, "status": status}
    if types_played is not None:
        raw["types_played"] = types_played
    return RelicInstance.from_dict(raw)

def test_rainbow_ring_reads_the_types_played_this_turn():
    assert _rainbow(3).value == SEEN_ATTACK | SEEN_SKILL
    assert _rainbow().value == 0

def test_rainbow_ring_pays_out_when_the_last_type_arrives_after_a_reload():
    cs = state([defend()], RelicId.RAINBOW_RING)
    cs.player.relics[RelicId.RAINBOW_RING] = _rainbow(SEEN_ATTACK | SEEN_SKILL)
    cs.player.hand = [inflame()]
    CombatSimulator(cs).play_card(0, 0)
    assert status(cs, StatusId.DEXTERITY) == 1 and relic(cs, RelicId.RAINBOW_RING).used

def test_rainbow_ring_that_has_paid_out_reads_as_used_and_pays_nothing_more():
    cs = state([inflame()], RelicId.RAINBOW_RING)
    cs.player.relics[RelicId.RAINBOW_RING] = _rainbow(7, "Active")
    assert relic(cs, RelicId.RAINBOW_RING).used
    CombatSimulator(cs).play_card(0, 0)
    assert status(cs, StatusId.DEXTERITY) == 0

def test_types_played_survive_a_copy():
    assert RelicInstance.deepcopy(_rainbow(5)).value == 5


# ---------------------------------------------------------------- Rainbow Ring, saved from the game
def test_saved_rainbow_ring_has_seen_a_skill_and_an_attack():
    ring = relic(_capture("rainbow_ring_skill_attack"), RelicId.RAINBOW_RING)
    assert ring.value == SEEN_ATTACK | SEEN_SKILL and not ring.used

def test_saved_rainbow_ring_that_has_paid_out_is_used_with_all_three_seen():
    ring = relic(_capture("rainbow_ring_skill_attack_power"), RelicId.RAINBOW_RING)
    assert ring.value == 7 and ring.used

def test_saved_state_the_power_completes_rainbow_ring_as_the_game_did():
    cs = _capture("rainbow_ring_skill_attack")
    _play(cs, "INFLAME")
    after = _capture("rainbow_ring_skill_attack_power")
    assert status(cs, StatusId.STRENGTH) == status(after, StatusId.STRENGTH) == 3     # Inflame's 2 and the ring's 1
    assert status(cs, StatusId.DEXTERITY) == status(after, StatusId.DEXTERITY) == 1
    assert cs.energy == after.energy
    assert _hand(cs) == _hand(after)
    assert relic(cs, RelicId.RAINBOW_RING).used

def test_saved_state_rainbow_ring_pays_nothing_more_once_it_has_paid_out():
    cs = _capture("rainbow_ring_skill_attack_power", energy=3)
    _play(cs, "BASH")
    assert status(cs, StatusId.STRENGTH) == 3 and status(cs, StatusId.DEXTERITY) == 1

def test_saved_state_rainbow_ring_starts_again_next_turn():
    cs = _capture("rainbow_ring_skill_attack_power")
    CombatSimulator(cs).end_turn()
    ring = relic(cs, RelicId.RAINBOW_RING)
    assert not ring.used and ring.value == 0
