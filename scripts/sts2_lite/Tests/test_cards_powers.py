"""Powers of the Ironclad pool. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.Tests.test_cards import make_card, make_state, play, hps
from sts2_lite.status import StatusId


def card(card_id, cost=1, kind=CardType.Attack, target=TargetType.AnyEnemy, upgraded=False):
    return make_card(card_id, card_id.name.title(), kind, cost, target, upgraded)

def strike():
    return card(CardId.STRIKE_IRONCLAD)

def defend():
    return card(CardId.DEFEND_IRONCLAD, kind=CardType.Skill, target=TargetType.Self)

def skill(card_id, cost=1, upgraded=False):
    return card(card_id, cost, CardType.Skill, TargetType.Self, upgraded)

def power(card_id, cost=1, upgraded=False):
    return card(card_id, cost, CardType.Power, TargetType.Self, upgraded)

def dazed():
    return Card.create_dazed()

def one_enemy(hand, hp=100):
    return make_state(hand, enemy_count=1, enemy_hp=hp)

def status(creature, status_id):
    return creature.status_amount(status_id)

def attacker(cs, damage, hits=1, index=0):
    e = cs.enemies[index]
    e.attack_damage, e.num_attacks = damage, hits
    return e

def play_index(sim, index, target=0):
    sim.play_card(index, target)


# ---------------------------------------------------------------- applying the powers
@pytest.mark.parametrize("card_id,cost,status_id,amount,upgraded_amount", [
    (CardId.CRUELTY, 1, StatusId.CRUELTY, 25, 50),
    (CardId.DEMON_FORM, 3, StatusId.DEMON_FORM, 2, 3),
    (CardId.FEEL_NO_PAIN, 1, StatusId.FEEL_NO_PAIN, 3, 4),
    (CardId.JUGGERNAUT, 2, StatusId.JUGGERNAUT, 6, 8),
    (CardId.RUPTURE, 1, StatusId.RUPTURE, 1, 2),
    (CardId.VICIOUS, 1, StatusId.VICIOUS, 1, 2),
    (CardId.STONE_ARMOR, 1, StatusId.PLATING, 4, 6),
    (CardId.PYRE, 2, StatusId.PYRE, 1, 2),
])
def test_power_card_applies_its_amount(card_id, cost, status_id, amount, upgraded_amount):
    for upgraded, expected in ((False, amount), (True, upgraded_amount)):
        cs = one_enemy([power(card_id, cost, upgraded)])
        sim = play(cs)
        assert status(cs.player, status_id) == expected
        assert cs.energy == 3 - cost
        assert cs.player.discard_pile == [] and cs.player.exhaust_pile == []     # powers leave play

@pytest.mark.parametrize("card_id,status_id", [
    (CardId.BARRICADE, StatusId.BARRICADE), (CardId.CORRUPTION, StatusId.CORRUPTION),
    (CardId.DARK_EMBRACE, StatusId.DARK_EMBRACE), (CardId.JUGGLING, StatusId.JUGGLING),
    (CardId.STAMPEDE, StatusId.STAMPEDE), (CardId.UNMOVABLE, StatusId.UNMOVABLE),
])
def test_one_stack_power_cards_apply_one(card_id, status_id):
    cs = one_enemy([power(card_id, 0), power(card_id, 0)])
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    play_index(sim, 0)
    expected = 2 if card_id in (CardId.DARK_EMBRACE, CardId.JUGGLING, CardId.STAMPEDE, CardId.UNMOVABLE) else 1
    assert status(cs.player, status_id) == expected

def test_one_stack_powers_that_do_not_stack_stay_at_one():
    for card_id, status_id in ((CardId.BARRICADE, StatusId.BARRICADE), (CardId.CORRUPTION, StatusId.CORRUPTION)):
        cs = one_enemy([power(card_id, 0), power(card_id, 0)])
        sim = CombatSimulator(cs)
        play_index(sim, 0)
        play_index(sim, 0)
        assert status(cs.player, status_id) == 1


# ---------------------------------------------------------------- Barricade
def test_barricade_keeps_block_into_the_next_turn():
    cs = one_enemy([])
    cs.player.block = 12
    cs.player.apply_status(StatusId.BARRICADE, 1)
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 12

def test_block_is_lost_without_barricade():
    cs = one_enemy([])
    cs.player.block = 12
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 0

def test_barricade_block_still_absorbs_damage():
    cs = one_enemy([])
    attacker(cs, 5)
    cs.player.block = 12
    cs.player.apply_status(StatusId.BARRICADE, 1)
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 7 and cs.player.current_hp == 50


# ---------------------------------------------------------------- Corruption
def test_corruption_makes_skills_free_and_exhausts_them():
    cs = one_enemy([defend()])
    cs.player.apply_status(StatusId.CORRUPTION, 1)
    play(cs)
    assert cs.energy == 3 and cs.player.block == 5
    assert [c.card_id for c in cs.player.exhaust_pile] == [CardId.DEFEND_IRONCLAD]
    assert cs.player.discard_pile == []

def test_corruption_leaves_attacks_alone():
    cs = one_enemy([strike()])
    cs.player.apply_status(StatusId.CORRUPTION, 1)
    play(cs)
    assert cs.energy == 2
    assert cs.player.exhaust_pile == [] and len(cs.player.discard_pile) == 1

def test_corruption_lets_a_skill_be_played_with_no_energy():
    cs = one_enemy([defend()])
    cs.energy = 0
    cs.player.apply_status(StatusId.CORRUPTION, 1)
    sim = CombatSimulator(cs)
    assert sim.get_available_actions()[0]["action"] == "play_card"

def test_corruption_exhaust_fires_the_exhaust_hooks():
    cs = one_enemy([defend()])
    cs.player.apply_status(StatusId.CORRUPTION, 1)
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 3)
    play(cs)
    assert cs.player.block == 8

def test_corruption_does_not_touch_cost_of_status_cards_or_powers():
    cs = one_enemy([power(CardId.DEMON_FORM, 3)])
    cs.player.apply_status(StatusId.CORRUPTION, 1)
    play(cs)
    assert cs.energy == 0

def test_card_that_already_exhausts_is_exhausted_once_under_corruption():
    cs = one_enemy([card(CardId.IMPERVIOUS, 2, CardType.Skill, TargetType.Self)])
    cs.player.apply_status(StatusId.CORRUPTION, 1)
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 3)
    play(cs)
    assert len(cs.player.exhaust_pile) == 1 and cs.player.block == 33


# ---------------------------------------------------------------- Dark Embrace
def test_dark_embrace_draws_when_a_card_is_exhausted():
    cs = one_enemy([card(CardId.SECOND_WIND, 1, CardType.Skill, TargetType.Self), defend(), skill(CardId.TREMBLE)])
    cs.player.draw_pile = [strike() for _ in range(5)]
    cs.player.apply_status(StatusId.DARK_EMBRACE, 1)
    play(cs)
    assert cs.player.cards_exhausted_this_turn == 2
    assert len(cs.player.hand) == 2

def test_dark_embrace_draws_its_amount_per_exhaust():
    cs = one_enemy([card(CardId.SECOND_WIND, 1, CardType.Skill, TargetType.Self), defend()])
    cs.player.draw_pile = [strike() for _ in range(9)]
    cs.player.apply_status(StatusId.DARK_EMBRACE, 2)
    play(cs)
    assert len(cs.player.hand) == 2         # one card exhausted, two drawn

def test_dark_embrace_draws_after_ethereal_cards_leave_the_hand():
    cs = one_enemy([dazed(), dazed(), strike()])
    cs.player.draw_pile = [defend() for _ in range(5)]
    cs.player.apply_status(StatusId.DARK_EMBRACE, 1)
    sim = CombatSimulator(cs)
    sim._discard_hand()
    assert len(cs.player.hand) == 2 and all(c.card_id == CardId.DEFEND_IRONCLAD for c in cs.player.hand)
    assert [c.card_id for c in cs.player.discard_pile] == [CardId.STRIKE_IRONCLAD]
    assert len(cs.player.exhaust_pile) == 2

def test_dark_embrace_does_not_draw_during_discard_for_ordinary_cards():
    cs = one_enemy([strike(), strike()])
    cs.player.draw_pile = [defend() for _ in range(5)]
    cs.player.apply_status(StatusId.DARK_EMBRACE, 1)
    CombatSimulator(cs)._discard_hand()
    assert cs.player.hand == []

def test_ethereal_flag_is_off_again_after_the_discard():
    cs = one_enemy([dazed()])
    sim = CombatSimulator(cs)
    sim._discard_hand()
    assert sim.ethereal_exhaust is False

def test_ethereal_draw_survives_into_the_next_turn():
    cs = one_enemy([dazed()])
    cs.player.draw_pile = [defend() for _ in range(8)]
    cs.player.apply_status(StatusId.DARK_EMBRACE, 1)
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == 6     # one drawn for the dazed, five for the new turn


# ---------------------------------------------------------------- Demon Form
def test_demon_form_gives_strength_at_the_start_of_each_turn():
    cs = one_enemy([])
    cs.player.apply_status(StatusId.DEMON_FORM, 2)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert status(cs.player, StatusId.STRENGTH) == 2
    sim.end_turn()
    assert status(cs.player, StatusId.STRENGTH) == 4

def test_demon_form_gives_nothing_the_turn_it_is_played():
    cs = one_enemy([power(CardId.DEMON_FORM, 3)])
    play(cs)
    assert status(cs.player, StatusId.STRENGTH) == 0

def test_enemies_do_not_get_the_player_demon_form_strength():
    cs = one_enemy([])
    cs.player.apply_status(StatusId.DEMON_FORM, 2)
    CombatSimulator(cs).end_turn()
    assert status(cs.enemies[0], StatusId.STRENGTH) == 0


# ---------------------------------------------------------------- Feel No Pain
def test_feel_no_pain_blocks_for_each_exhausted_card():
    cs = one_enemy([card(CardId.SECOND_WIND, 1, CardType.Skill, TargetType.Self), defend(), defend()])
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 3)
    play(cs)
    # Second Wind's own 5 per card plus Feel No Pain's 3
    assert cs.player.block == 2 * 5 + 2 * 3

def test_feel_no_pain_ignores_dexterity_and_frail():
    cs = one_enemy([card(CardId.IMPERVIOUS, 2, CardType.Skill, TargetType.Self)])
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 4)
    cs.player.apply_status(StatusId.DEXTERITY, 3)
    cs.player.apply_status(StatusId.FRAIL, 2)
    play(cs)
    assert cs.player.block == int((30 + 3) * 0.75) + 4

def test_feel_no_pain_triggers_for_ethereal_cards_at_end_of_turn():
    cs = one_enemy([dazed(), dazed()])
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 3)
    cs.player.apply_status(StatusId.BARRICADE, 1)      # keeps the block visible after the turn change
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 6

def test_feel_no_pain_blocks_the_enemy_turn_that_follows():
    cs = one_enemy([dazed(), dazed()])
    attacker(cs, 6)
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 3)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 50


# ---------------------------------------------------------------- Juggernaut
def test_juggernaut_hits_an_enemy_when_block_is_gained():
    cs = one_enemy([defend()])
    cs.player.apply_status(StatusId.JUGGERNAUT, 6)
    play(cs)
    assert hps(cs) == [94]

def test_juggernaut_damage_ignores_strength_and_vulnerable():
    cs = one_enemy([defend()])
    cs.player.apply_status(StatusId.JUGGERNAUT, 6)
    cs.player.apply_status(StatusId.STRENGTH, 5)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    play(cs)
    assert hps(cs) == [94]

def test_juggernaut_fires_once_per_block_gain():
    cs = one_enemy([card(CardId.EVIL_EYE, 1, CardType.Skill, TargetType.Self)])
    cs.player.cards_exhausted_this_turn = 1
    cs.player.apply_status(StatusId.JUGGERNAUT, 4)
    play(cs)
    assert hps(cs) == [92]         # Evil Eye gains block twice

def test_juggernaut_needs_block_actually_gained():
    cs = one_enemy([defend()])
    cs.player.apply_status(StatusId.JUGGERNAUT, 6)
    cs.player.apply_status(StatusId.DEXTERITY, -9)
    play(cs)
    assert cs.player.block == 0 and hps(cs) == [100]

def test_juggernaut_triggers_on_feel_no_pain_block():
    cs = one_enemy([card(CardId.IMPERVIOUS, 2, CardType.Skill, TargetType.Self)])
    cs.player.apply_status(StatusId.JUGGERNAUT, 6)
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 2)
    play(cs)
    assert hps(cs) == [88]

def test_juggernaut_picks_among_the_living_enemies():
    seen = set()
    for seed in range(30):
        rng.seed(seed)
        cs = make_state([defend()], enemy_count=3, enemy_hp=50)
        cs.player.apply_status(StatusId.JUGGERNAUT, 6)
        play(cs)
        assert sorted(hps(cs)) == [44, 50, 50]
        seen.add(hps(cs).index(44))
    assert seen == {0, 1, 2}

def test_juggernaut_can_kill_and_ends_the_fight():
    cs = one_enemy([defend()], hp=6)
    cs.player.apply_status(StatusId.JUGGERNAUT, 6)
    sim = play(cs)
    assert sim.is_over and cs.enemies == []

def test_juggernaut_triggers_for_block_at_turn_start():
    cs = one_enemy([])
    cs.player.apply_status(StatusId.JUGGERNAUT, 5)
    cs.player.apply_status(StatusId.CRIMSON_MANTLE, 8)
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [95]

def test_juggernaut_ignores_retained_barricade_block_at_turn_start():
    cs = one_enemy([])
    cs.player.block = 20
    cs.player.apply_status(StatusId.BARRICADE, 1)
    cs.player.apply_status(StatusId.JUGGERNAUT, 5)
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [100]


# ---------------------------------------------------------------- Rage
def test_rage_gives_block_for_each_attack_played():
    cs = one_enemy([strike(), strike()])
    cs.player.apply_status(StatusId.RAGE, 3)
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    play_index(sim, 0)
    assert cs.player.block == 6

def test_rage_ignores_skills():
    cs = one_enemy([defend()])
    cs.player.apply_status(StatusId.RAGE, 3)
    play(cs)
    assert cs.player.block == 5

def test_rage_block_ignores_dexterity():
    cs = one_enemy([strike()])
    cs.player.apply_status(StatusId.RAGE, 3)
    cs.player.apply_status(StatusId.DEXTERITY, 4)
    play(cs)
    assert cs.player.block == 3

def test_rage_ends_with_the_turn():
    cs = one_enemy([])
    cs.player.apply_status(StatusId.RAGE, 3)
    CombatSimulator(cs).end_turn()
    assert StatusId.RAGE not in cs.player.status

def test_rage_card_stacks_when_played_twice():
    cs = one_enemy([skill(CardId.RAGE, 0), skill(CardId.RAGE, 0, upgraded=True)])
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    play_index(sim, 0)
    assert status(cs.player, StatusId.RAGE) == 8


# ---------------------------------------------------------------- Flame Barrier
def test_flame_barrier_gives_block_and_the_thorns_like_status():
    cs = one_enemy([card(CardId.FLAME_BARRIER, 2, CardType.Skill, TargetType.Self)])
    play(cs)
    assert cs.player.block == 12 and status(cs.player, StatusId.FLAME_BARRIER) == 4

def test_flame_barrier_upgraded():
    cs = one_enemy([card(CardId.FLAME_BARRIER, 2, CardType.Skill, TargetType.Self, upgraded=True)])
    play(cs)
    assert cs.player.block == 16 and status(cs.player, StatusId.FLAME_BARRIER) == 6

def test_flame_barrier_hurts_the_attacker_for_each_hit():
    cs = one_enemy([card(CardId.FLAME_BARRIER, 2, CardType.Skill, TargetType.Self)])
    attacker(cs, 2, hits=3)
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    sim.end_turn()
    assert hps(cs) == [100 - 12]

def test_flame_barrier_works_when_the_hit_is_fully_blocked():
    cs = one_enemy([])
    attacker(cs, 3)
    cs.player.block = 50
    cs.player.apply_status(StatusId.FLAME_BARRIER, 4)
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [96] and cs.player.current_hp == 50

def test_flame_barrier_ends_after_the_enemy_turn():
    cs = one_enemy([])
    cs.player.apply_status(StatusId.FLAME_BARRIER, 4)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert StatusId.FLAME_BARRIER not in cs.player.status
    attacker(cs, 3)
    sim.end_turn()
    assert hps(cs) == [100]

def test_flame_barrier_is_still_up_during_the_player_turn_it_was_played():
    cs = one_enemy([card(CardId.FLAME_BARRIER, 2, CardType.Skill, TargetType.Self), strike()])
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    assert StatusId.FLAME_BARRIER in cs.player.status

def test_flame_barrier_kills_the_attacker_mid_turn_and_stops_its_hits():
    cs = one_enemy([])
    e = attacker(cs, 5, hits=4)
    e.current_hp = 4
    cs.player.apply_status(StatusId.FLAME_BARRIER, 4)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.player.current_hp == 45     # the first hit lands, its reflection kills the attacker, no more hits
    assert cs.enemies == [] and sim.is_over

def test_a_killed_attacker_does_not_stop_the_other_enemies():
    cs = make_state([], enemy_count=2, enemy_hp=40)
    attacker(cs, 3, 1, 0).current_hp = 4
    attacker(cs, 7, 1, 1)
    cs.player.apply_status(StatusId.FLAME_BARRIER, 4)
    CombatSimulator(cs).end_turn()
    assert len(cs.enemies) == 1 and cs.player.current_hp == 50 - 3 - 7

def test_enemy_killed_in_its_own_turn_does_not_act_later():
    cs = make_state([], enemy_count=2, enemy_hp=40)
    attacker(cs, 3, 1, 0).current_hp = 4
    attacker(cs, 7, 1, 1)
    cs.player.apply_status(StatusId.FLAME_BARRIER, 4)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.enemies[0].enemy_id == "E1"


# ---------------------------------------------------------------- Pyre
def test_pyre_raises_max_energy_right_away_and_next_turn():
    cs = one_enemy([power(CardId.PYRE, 2)])
    sim = play(cs)
    assert cs.max_energy == 4
    sim.end_turn()
    assert cs.energy == 4

def test_pyre_upgraded_gives_two():
    cs = one_enemy([power(CardId.PYRE, 2, upgraded=True)])
    play(cs)
    assert cs.max_energy == 5


# ---------------------------------------------------------------- Cruelty
def test_cruelty_strengthens_vulnerable():
    cs = one_enemy([strike()])
    cs.player.apply_status(StatusId.CRUELTY, 25)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    play(cs)
    assert hps(cs) == [100 - int(6 * 1.75)]

def test_cruelty_upgraded():
    cs = one_enemy([strike()])
    cs.player.apply_status(StatusId.CRUELTY, 50)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    play(cs)
    assert hps(cs) == [100 - 12]

def test_cruelty_does_nothing_without_vulnerable():
    cs = one_enemy([strike()])
    cs.player.apply_status(StatusId.CRUELTY, 25)
    play(cs)
    assert hps(cs) == [94]

def test_cruelty_does_not_make_the_player_more_vulnerable():
    cs = one_enemy([])
    attacker(cs, 10)
    cs.player.apply_status(StatusId.CRUELTY, 50)
    cs.player.apply_status(StatusId.VULNERABLE, 2)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 50 - 15


# ---------------------------------------------------------------- Vicious
def test_vicious_draws_when_vulnerable_is_applied():
    cs = one_enemy([card(CardId.BASH, 2)])
    cs.player.draw_pile = [strike() for _ in range(4)]
    cs.player.apply_status(StatusId.VICIOUS, 2)
    play(cs)
    assert len(cs.player.hand) == 2

def test_vicious_draws_for_each_enemy_hit_by_thunderclap():
    cs = make_state([card(CardId.THUNDERCLAP, 1, target=TargetType.AllEnemies)], enemy_count=3)
    cs.player.draw_pile = [strike() for _ in range(6)]
    cs.player.apply_status(StatusId.VICIOUS, 1)
    play(cs)
    assert len(cs.player.hand) == 3

def test_vicious_does_not_draw_without_vulnerable():
    cs = one_enemy([strike()])
    cs.player.draw_pile = [strike() for _ in range(4)]
    cs.player.apply_status(StatusId.VICIOUS, 2)
    play(cs)
    assert cs.player.hand == []

def test_vicious_does_not_draw_when_artifact_blocks_the_vulnerable():
    cs = one_enemy([card(CardId.BASH, 2)])
    cs.player.draw_pile = [strike() for _ in range(4)]
    cs.player.apply_status(StatusId.VICIOUS, 2)
    cs.enemies[0].apply_status(StatusId.ARTIFACT, 1)
    play(cs)
    assert cs.player.hand == []

def test_vicious_draws_when_molten_fist_doubles_vulnerable():
    cs = one_enemy([card(CardId.MOLTEN_FIST, 1)])
    cs.player.draw_pile = [strike() for _ in range(4)]
    cs.player.apply_status(StatusId.VICIOUS, 1)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    play(cs)
    assert len(cs.player.hand) == 1 and status(cs.enemies[0], StatusId.VULNERABLE) == 4

def test_vicious_draw_marks_the_action_as_random():
    cs = one_enemy([card(CardId.BASH, 2)])
    cs.player.draw_pile = [strike() for _ in range(4)]
    cs.player.apply_status(StatusId.VICIOUS, 1)
    play(cs)
    assert cs.player.unknown_draws == 1


# ---------------------------------------------------------------- Rupture
def test_rupture_gives_strength_after_a_card_costs_hp():
    cs = one_enemy([card(CardId.BLOODLETTING, 0, CardType.Skill, TargetType.Self)])
    cs.player.apply_status(StatusId.RUPTURE, 1)
    play(cs)
    assert status(cs.player, StatusId.STRENGTH) == 1

def test_rupture_strength_comes_after_the_card_resolves():
    cs = one_enemy([card(CardId.HEMOKINESIS, 1)])
    cs.player.apply_status(StatusId.RUPTURE, 2)
    play(cs)
    assert hps(cs) == [85] and status(cs.player, StatusId.STRENGTH) == 2

def test_rupture_needs_hp_to_be_lost():
    cs = one_enemy([defend()])
    cs.player.apply_status(StatusId.RUPTURE, 1)
    play(cs)
    assert StatusId.STRENGTH not in cs.player.status

def test_rupture_counts_every_loss_within_one_card():
    cs = one_enemy([card(CardId.HEMOKINESIS, 1)])
    cs.enemies[0].apply_status(StatusId.THORNS, 2)
    cs.player.apply_status(StatusId.RUPTURE, 3)
    play(cs)
    assert status(cs.player, StatusId.STRENGTH) == 6        # card cost plus the thorns hit

def test_rupture_ignores_damage_taken_in_the_enemy_turn():
    cs = one_enemy([])
    attacker(cs, 5)
    cs.player.apply_status(StatusId.RUPTURE, 1)
    CombatSimulator(cs).end_turn()
    assert status(cs.player, StatusId.STRENGTH) == 0

def test_rupture_ignores_fully_blocked_attacks():
    cs = one_enemy([])
    attacker(cs, 5)
    cs.player.block = 10
    cs.player.apply_status(StatusId.RUPTURE, 1)
    CombatSimulator(cs).end_turn()
    assert status(cs.player, StatusId.STRENGTH) == 0

def test_rupture_triggers_on_hp_loss_at_turn_start():
    cs = one_enemy([])
    cs.player.apply_status(StatusId.RUPTURE, 1)
    cs.player.apply_status(StatusId.CRIMSON_MANTLE, 8)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert status(cs.player, StatusId.STRENGTH) == 1

def test_rupture_counts_each_loss_separately():
    cs = one_enemy([card(CardId.BLOOD_WALL, 2, CardType.Skill, TargetType.Self)])
    cs.player.apply_status(StatusId.RUPTURE, 1)
    play(cs)
    assert status(cs.player, StatusId.STRENGTH) == 1

def test_rupture_triggers_on_thorns_damage_while_attacking():
    cs = one_enemy([strike()])
    cs.enemies[0].apply_status(StatusId.THORNS, 3)
    cs.player.apply_status(StatusId.RUPTURE, 1)
    play(cs)
    assert status(cs.player, StatusId.STRENGTH) == 1

def test_rupture_triggers_on_infection_at_end_of_turn():
    cs = one_enemy([Card.create_infection()])
    cs.player.apply_status(StatusId.RUPTURE, 1)
    CombatSimulator(cs).end_turn()
    assert status(cs.player, StatusId.STRENGTH) == 1


# ---------------------------------------------------------------- Stampede
def test_stampede_plays_an_attack_from_hand_at_end_of_turn():
    cs = one_enemy([strike(), defend()])
    cs.player.apply_status(StatusId.STAMPEDE, 1)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert hps(cs) == [94]

def test_stampede_does_not_cost_energy_or_turn_plays():
    cs = one_enemy([strike()])
    cs.player.apply_status(StatusId.STAMPEDE, 1)
    cs.energy = 0
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert hps(cs) == [94]

def test_stampede_plays_the_amount_of_attacks():
    cs = one_enemy([strike(), strike(), strike()])
    cs.player.apply_status(StatusId.STAMPEDE, 2)
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [88]

def test_stampede_with_nothing_to_play_does_nothing():
    cs = one_enemy([defend()])
    cs.player.apply_status(StatusId.STAMPEDE, 3)
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [100]

def test_stampede_skips_unplayable_attacks():
    c = strike()
    c.is_unplayable = True
    cs = one_enemy([c])
    cs.player.apply_status(StatusId.STAMPEDE, 1)
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [100]

def test_stampede_choice_is_random_among_attacks():
    seen = set()
    for seed in range(40):
        rng.seed(seed)
        cs = make_state([strike(), card(CardId.BASH, 2)], enemy_count=1, enemy_hp=100)
        cs.player.apply_status(StatusId.STAMPEDE, 1)
        CombatSimulator(cs).end_turn()
        seen.add(hps(cs)[0])
    assert seen == {94, 92}

def test_stampede_attack_goes_to_the_discard_pile():
    from sts2_lite.events import EventType
    cs = one_enemy([strike()])
    cs.player.apply_status(StatusId.STAMPEDE, 1)
    CombatSimulator(cs).fire(EventType.PLAY_PHASE_END)
    assert cs.player.hand == [] and len(cs.player.discard_pile) == 1

def test_stampede_kills_end_the_fight():
    cs = one_enemy([strike()], hp=5)
    cs.player.apply_status(StatusId.STAMPEDE, 1)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert sim.is_over

def test_stampede_triggers_rage_and_other_card_played_effects():
    cs = one_enemy([strike()])
    cs.player.apply_status(StatusId.STAMPEDE, 1)
    cs.player.apply_status(StatusId.RAGE, 3)
    cs.player.apply_status(StatusId.BARRICADE, 1)
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 3


# ---------------------------------------------------------------- Juggling
def test_juggling_copies_the_third_attack():
    cs = one_enemy([strike(), strike(), strike()])
    cs.player.apply_status(StatusId.JUGGLING, 1)
    sim = CombatSimulator(cs)
    for _ in range(3):
        play_index(sim, 0)
    assert len(cs.player.hand) == 1 and cs.player.hand[0].card_id == CardId.STRIKE_IRONCLAD
    assert cs.player.hand[0] is not cs.player.discard_pile[0]

def test_juggling_does_not_copy_other_attacks():
    cs = one_enemy([strike() for _ in range(5)])
    cs.player.apply_status(StatusId.JUGGLING, 1)
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    play_index(sim, 0)
    assert len(cs.player.hand) == 3
    play_index(sim, 0)
    assert len(cs.player.hand) == 3         # two left plus the copy

def test_juggling_ignores_skills_when_counting():
    cs = one_enemy([strike(), defend(), strike(), strike(), defend()])
    cs.energy = 9
    cs.player.apply_status(StatusId.JUGGLING, 1)
    sim = CombatSimulator(cs)
    for _ in range(3):
        play_index(sim, 0)
    assert len(cs.player.hand) == 2         # the third card played was a skill: no copy yet
    play_index(sim, 0)
    assert len(cs.player.hand) == 2         # two left plus the copy of the third attack, one played
    assert [c.card_id for c in cs.player.hand].count(CardId.STRIKE_IRONCLAD) == 1

def test_juggling_copies_per_stack():
    cs = one_enemy([strike(), strike(), strike()])
    cs.player.apply_status(StatusId.JUGGLING, 2)
    sim = CombatSimulator(cs)
    for _ in range(3):
        play_index(sim, 0)
    assert len(cs.player.hand) == 2

def test_juggling_counts_attacks_played_before_it():
    cs = one_enemy([strike(), strike(), strike()])
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    play_index(sim, 0)
    cs.player.apply_status(StatusId.JUGGLING, 1)
    play_index(sim, 0)
    assert len(cs.player.hand) == 1

def test_juggling_attack_counter_resets_each_turn():
    cs = one_enemy([strike() for _ in range(5)])
    cs.player.draw_pile = [strike() for _ in range(6)]
    cs.player.apply_status(StatusId.JUGGLING, 1)
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    play_index(sim, 0)
    sim.end_turn()
    assert cs.player.attacks_played_this_turn == 0
    play_index(sim, 0)
    assert cs.player.attacks_played_this_turn == 1

def test_juggling_copy_goes_to_the_discard_pile_when_the_hand_is_full():
    cs = one_enemy([strike(), strike(), strike()] + [defend() for _ in range(9)])
    cs.energy = 9
    cs.player.apply_status(StatusId.JUGGLING, 2)
    sim = CombatSimulator(cs)
    for _ in range(3):
        play_index(sim, 0)
    assert len(cs.player.hand) == 10 and len(cs.player.discard_pile) == 4

def test_juggling_fires_only_on_the_third():
    cs = one_enemy([strike() for _ in range(6)])
    cs.energy = 9
    cs.player.apply_status(StatusId.JUGGLING, 1)
    sim = CombatSimulator(cs)
    for _ in range(6):
        play_index(sim, 0)
    assert len(cs.player.hand) == 1


# ---------------------------------------------------------------- Unmovable
def test_unmovable_doubles_the_first_block_each_turn():
    cs = one_enemy([defend(), defend()])
    cs.player.apply_status(StatusId.UNMOVABLE, 1)
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    assert cs.player.block == 10
    play_index(sim, 0)
    assert cs.player.block == 15

def test_unmovable_amount_is_the_number_of_doubled_gains():
    cs = one_enemy([defend(), defend(), defend()])
    cs.player.apply_status(StatusId.UNMOVABLE, 2)
    sim = CombatSimulator(cs)
    for _ in range(3):
        play_index(sim, 0)
    assert cs.player.block == 10 + 10 + 5

def test_unmovable_resets_each_turn():
    cs = one_enemy([defend()])
    cs.player.draw_pile = [defend() for _ in range(6)]
    cs.player.apply_status(StatusId.UNMOVABLE, 1)
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    sim.end_turn()
    play_index(sim, 0)
    assert cs.player.block == 10

def test_unmovable_applies_after_dexterity_and_frail():
    cs = one_enemy([defend()])
    cs.player.apply_status(StatusId.UNMOVABLE, 1)
    cs.player.apply_status(StatusId.FRAIL, 1)
    play(cs)
    assert cs.player.block == int(5 * 0.75 * 2)

def test_unmovable_does_not_double_unpowered_block():
    cs = one_enemy([strike(), defend()])
    cs.player.apply_status(StatusId.UNMOVABLE, 1)
    cs.player.apply_status(StatusId.RAGE, 3)
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    assert cs.player.block == 3
    play_index(sim, 0)
    assert cs.player.block == 3 + 10

def test_unmovable_counts_each_block_of_a_card():
    cs = one_enemy([card(CardId.EVIL_EYE, 1, CardType.Skill, TargetType.Self), defend()])
    cs.player.cards_exhausted_this_turn = 1
    cs.player.apply_status(StatusId.UNMOVABLE, 1)
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    assert cs.player.block == 16 + 8
    play_index(sim, 0)
    assert cs.player.block == 16 + 8 + 5


# ---------------------------------------------------------------- Colossus
def test_colossus_gives_block_and_a_one_turn_buff():
    cs = one_enemy([card(CardId.COLOSSUS, 1, CardType.Skill, TargetType.Self)])
    play(cs)
    assert cs.player.block == 5 and status(cs.player, StatusId.COLOSSUS) == 1

def test_colossus_upgraded_block():
    cs = one_enemy([card(CardId.COLOSSUS, 1, CardType.Skill, TargetType.Self, upgraded=True)])
    play(cs)
    assert cs.player.block == 8

def test_colossus_halves_damage_from_vulnerable_attackers():
    cs = one_enemy([])
    attacker(cs, 10)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    cs.player.apply_status(StatusId.COLOSSUS, 1)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 45

def test_colossus_leaves_other_attackers_alone():
    cs = one_enemy([])
    attacker(cs, 10)
    cs.player.apply_status(StatusId.COLOSSUS, 1)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 40

def test_colossus_wears_off_after_the_enemy_turn():
    cs = one_enemy([])
    attacker(cs, 10)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 5)
    cs.player.apply_status(StatusId.COLOSSUS, 1)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert StatusId.COLOSSUS not in cs.player.status
    sim.end_turn()
    assert cs.player.current_hp == 50 - 5 - 10

def test_colossus_does_not_reduce_the_players_own_attacks():
    cs = one_enemy([strike()])
    cs.player.apply_status(StatusId.COLOSSUS, 1)
    cs.player.apply_status(StatusId.VULNERABLE, 1)
    play(cs)
    assert hps(cs) == [94]


# ---------------------------------------------------------------- One-Two Punch
def test_one_two_punch_plays_the_next_attack_twice():
    cs = one_enemy([strike()])
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    play(cs)
    assert hps(cs) == [88] and cs.energy == 2
    assert len(cs.player.discard_pile) == 1

def test_one_two_punch_is_used_up_by_one_attack():
    cs = one_enemy([strike(), strike()])
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    play_index(sim, 0)
    assert hps(cs) == [100 - 12 - 6] and StatusId.ONE_TWO_PUNCH not in cs.player.status

def test_one_two_punch_with_two_stacks():
    cs = one_enemy([strike(), strike(), strike()])
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 2)
    sim = CombatSimulator(cs)
    for _ in range(3):
        play_index(sim, 0)
    assert hps(cs) == [100 - 12 - 12 - 6]

def test_one_two_punch_waits_through_skills():
    cs = one_enemy([defend(), strike()])
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    sim = CombatSimulator(cs)
    play_index(sim, 0)
    assert status(cs.player, StatusId.ONE_TWO_PUNCH) == 1
    play_index(sim, 0)
    assert hps(cs) == [88]

def test_one_two_punch_ends_with_the_turn():
    cs = one_enemy([])
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    CombatSimulator(cs).end_turn()
    assert StatusId.ONE_TWO_PUNCH not in cs.player.status

def test_one_two_punch_second_play_is_skipped_on_a_dead_target():
    cs = one_enemy([strike()], hp=6)
    cs.enemies[0].apply_status(StatusId.THORNS, 4)
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    play(cs)
    assert cs.player.current_hp == 46       # thorns hit once: the second play never happened

def test_one_two_punch_doubles_side_effects():
    cs = one_enemy([card(CardId.ANGER, 0)])
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    play(cs)
    assert len(cs.player.discard_pile) == 3

def test_one_two_punch_doubles_x_cost_attacks():
    cs = one_enemy([card(CardId.WHIRLWIND, "X")])
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    play(cs)
    assert hps(cs) == [100 - 30] and cs.energy == 0

def test_one_two_punch_ignores_a_failed_play():
    cs = one_enemy([strike()])
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    with pytest.raises(ValueError):
        play(cs, target=4)
    assert status(cs.player, StatusId.ONE_TWO_PUNCH) == 1

def test_one_two_punch_does_not_use_free_attack_twice():
    cs = one_enemy([strike(), strike()])
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    cs.player.apply_status(StatusId.FREE_ATTACK, 1)
    play(cs)
    assert cs.energy == 3 and hps(cs) == [88]


# ---------------------------------------------------------------- Stone Armor
def test_stone_armor_blocks_at_the_end_of_the_turn():
    cs = one_enemy([])
    attacker(cs, 3)
    cs.player.apply_status(StatusId.PLATING, 4)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 50

def test_stone_armor_does_not_block_at_turn_start():
    cs = one_enemy([])
    cs.player.apply_status(StatusId.PLATING, 4)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.player.block == 0

def test_stone_armor_wears_down_by_one_a_turn():
    cs = one_enemy([])
    cs.player.apply_status(StatusId.PLATING, 4)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert status(cs.player, StatusId.PLATING) == 3
    attacker(cs, 20)
    sim.end_turn()
    assert cs.player.current_hp == 50 - 17

def test_stone_armor_plating_leaves_when_used_up():
    cs = one_enemy([])
    cs.player.apply_status(StatusId.PLATING, 1)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert StatusId.PLATING not in cs.player.status

def test_end_of_turn_plating_block_is_for_the_player_only():
    cs = one_enemy([])
    cs.enemies[0].apply_status(StatusId.PLATING, 4)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.enemies[0].block == 3
    from sts2_lite.events import EventType
    cs.enemies[0].block = 0
    sim.fire(EventType.END_TURN)
    assert cs.enemies[0].block == 0

def test_enemy_plating_is_unchanged():
    cs = one_enemy([])
    cs.enemies[0].apply_status(StatusId.PLATING, 4)
    CombatSimulator(cs).end_turn()
    assert cs.enemies[0].block == 3


# ---------------------------------------------------------------- engine pieces
def test_auto_play_is_free_and_not_counted_as_a_card_play():
    cs = one_enemy([strike()])
    cs.energy = 0
    sim = CombatSimulator(cs)
    sim.auto_play(cs.player.hand[0])
    assert hps(cs) == [94] and cs.energy == 0 and cs.cards_played == 0
    assert cs.player.hand == [] and len(cs.player.discard_pile) == 1

def test_auto_play_does_not_use_up_free_attack():
    cs = one_enemy([strike()])
    cs.player.apply_status(StatusId.FREE_ATTACK, 1)
    CombatSimulator(cs).auto_play(cs.player.hand[0])
    assert status(cs.player, StatusId.FREE_ATTACK) == 1

def test_auto_play_takes_the_card_from_the_draw_pile():
    cs = one_enemy([])
    c = strike()
    cs.player.draw_pile = [c, strike()]
    CombatSimulator(cs).auto_play(c)
    assert len(cs.player.draw_pile) == 1 and hps(cs) == [94]

def test_auto_play_of_an_x_cost_card_uses_current_energy_without_spending_it():
    cs = one_enemy([card(CardId.WHIRLWIND, "X")])
    CombatSimulator(cs).auto_play(cs.player.hand[0])
    assert hps(cs) == [100 - 15] and cs.energy == 3

def test_playing_an_x_cost_card_normally_spends_all_energy():
    cs = one_enemy([card(CardId.WHIRLWIND, "X")])
    play(cs)
    assert hps(cs) == [100 - 15] and cs.energy == 0

def test_auto_play_can_force_exhaust():
    cs = one_enemy([strike()])
    CombatSimulator(cs).auto_play(cs.player.hand[0], force_exhaust=True)
    assert len(cs.player.exhaust_pile) == 1 and cs.player.discard_pile == []

def test_auto_play_with_no_target_leaves_the_card_alone():
    cs = one_enemy([strike()])
    cs.enemies[0].current_hp = 0
    CombatSimulator(cs).auto_play(cs.player.hand[0])
    assert len(cs.player.hand) == 1

def test_auto_play_picks_a_random_living_target():
    seen = set()
    for seed in range(30):
        rng.seed(seed)
        cs = make_state([strike()], enemy_count=3, enemy_hp=50)
        CombatSimulator(cs).auto_play(cs.player.hand[0])
        seen.add(hps(cs).index(44))
    assert seen == {0, 1, 2}

def test_auto_play_of_a_power_stays_out_of_the_piles():
    cs = one_enemy([power(CardId.DEMON_FORM, 3)])
    CombatSimulator(cs).auto_play(cs.player.hand[0])
    assert status(cs.player, StatusId.DEMON_FORM) == 2 and cs.player.discard_pile == []

def test_gain_block_event_ignores_zero():
    from sts2_lite.events import EventType
    import sts2_lite.status as st
    cs = one_enemy([])
    sim = CombatSimulator(cs)
    seen = []
    st.STATUS_HANDLERS[(StatusId.STRENGTH, EventType.BLOCK_GAINED)] = lambda c, o, a, creature, amount: seen.append(amount)
    try:
        cs.player.apply_status(StatusId.STRENGTH, 1)
        sim.gain_block(cs.player, 0)
        sim.gain_block(cs.player, 4)
    finally:
        del st.STATUS_HANDLERS[(StatusId.STRENGTH, EventType.BLOCK_GAINED)]
    assert seen == [4] and cs.player.block == 4

def test_player_turn_start_event_fires_after_the_draw():
    from sts2_lite.events import EventType
    import sts2_lite.status as st
    cs = one_enemy([])
    cs.player.draw_pile = [strike() for _ in range(6)]
    sim = CombatSimulator(cs)
    seen = []
    st.STATUS_HANDLERS[(StatusId.STRENGTH, EventType.PLAYER_TURN_START)] = lambda c, o, a: seen.append(len(cs.player.hand))
    try:
        cs.player.apply_status(StatusId.STRENGTH, 1)
        sim.end_turn()
    finally:
        del st.STATUS_HANDLERS[(StatusId.STRENGTH, EventType.PLAYER_TURN_START)]
    assert seen == [5]

def test_deepcopy_keeps_the_new_player_counters():
    from sts2_lite.player import Player
    cs = one_enemy([])
    cs.player.attacks_played_this_turn = 2
    cs.player.card_blocks_this_turn = 3
    cs.player.hp_loss_events = 4
    copy = Player.deepcopy(cs.player)
    assert (copy.attacks_played_this_turn, copy.card_blocks_this_turn, copy.hp_loss_events) == (2, 3, 4)

def test_hp_loss_events_count_real_losses_only():
    from sts2_lite.creature import Creature
    c = Creature(max_hp=50, current_hp=50, block=5)
    c.apply_damage(3)       # blocked
    assert c.hp_loss_events == 0
    c.apply_damage(9)
    c.lose_hp(0)
    c.lose_hp(2)
    assert c.hp_loss_events == 2

def test_every_new_card_has_a_play_function():
    from sts2_lite.card import GET_CARD_FUNCTION
    from sts2_lite.Tests.test_cards import NEW_POWER_CARDS
    for cid in NEW_POWER_CARDS:
        assert cid in GET_CARD_FUNCTION

def test_cards_are_sorted_in_the_function_map():
    from sts2_lite.card import GET_CARD_FUNCTION
    names = [c.name for c in GET_CARD_FUNCTION]
    assert names == sorted(names)

def test_bridge_power_ids_load():
    for raw in ("BARRICADE_POWER", "CORRUPTION_POWER", "DARK_EMBRACE_POWER", "DEMON_FORM_POWER", "FEEL_NO_PAIN_POWER",
                "JUGGERNAUT_POWER", "RUPTURE_POWER", "STAMPEDE_POWER", "CRUELTY_POWER", "RAGE_POWER", "FLAME_BARRIER_POWER",
                "JUGGLING_POWER", "VICIOUS_POWER", "PYRE_POWER", "UNMOVABLE_POWER", "COLOSSUS_POWER", "ONE_TWO_PUNCH_POWER"):
        from sts2_lite.status import StatusInstance
        assert StatusInstance.from_dict({"id": raw, "amount": 2}).amount == 2


# ---------------------------------------------------------------- per-turn counters across loads
def test_carry_turn_counters_keeps_this_turns_counts():
    from sts2_lite.combat import CombatState
    old = one_enemy([]).player
    prev = one_enemy([])
    prev.player.attacks_played_this_turn = 2
    prev.player.card_blocks_this_turn = 1
    prev.player.cards_exhausted_this_turn = 3
    prev.player.lost_hp_this_turn = True
    prev.cards_played = 4
    new = one_enemy([])
    new.carry_turn_counters(prev)
    p = new.player
    assert (p.attacks_played_this_turn, p.card_blocks_this_turn, p.cards_exhausted_this_turn, p.lost_hp_this_turn) == (2, 1, 3, True)
    assert new.cards_played == 4

def test_carry_turn_counters_ignores_another_turn_or_no_state():
    prev = one_enemy([])
    prev.player.card_blocks_this_turn = 1
    prev.turn_number = 1
    new = one_enemy([])
    new.turn_number = 2
    new.carry_turn_counters(prev)
    new.carry_turn_counters(None)
    assert new.player.card_blocks_this_turn == 0

def test_carry_turn_counters_keeps_the_larger_card_count():
    prev = one_enemy([])
    prev.cards_played = 0
    new = one_enemy([])
    new.cards_played = 1        # inferred from Ringing
    new.carry_turn_counters(prev)
    assert new.cards_played == 1

def test_unmovable_does_not_double_again_after_a_reload():
    first = one_enemy([defend(), defend()])
    first.player.apply_status(StatusId.UNMOVABLE, 1)
    sim = CombatSimulator(first)
    play_index(sim, 0)
    reloaded = one_enemy([defend()])
    reloaded.player.apply_status(StatusId.UNMOVABLE, 1)
    reloaded.carry_turn_counters(first)
    play(reloaded)
    assert reloaded.player.block == 5
