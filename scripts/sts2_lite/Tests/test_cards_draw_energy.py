"""Battle Trance, Offering, Fiend Fire, Infernal Blade, Forgotten Ritual, Cascade, Expect a Fight, Drum of Battle,
Howl from Beyond, Not Yet, Pact's End and Conflagration. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType, GENERATABLE_CARDS, INFERNAL_BLADE_POOL
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.events import EventType
from sts2_lite.status import StatusId, StatusInstance
from sts2_lite.Tests.test_cards import make_card, make_state, play, hps


def card(card_id, cost, kind, target, upgraded=False):
    return make_card(card_id, card_id.name.title(), kind, cost, target, upgraded)

def strike():
    return card(CardId.STRIKE_IRONCLAD, 1, CardType.Attack, TargetType.AnyEnemy)

def defend():
    return card(CardId.DEFEND_IRONCLAD, 1, CardType.Skill, TargetType.Self)

def bash():
    return card(CardId.BASH, 2, CardType.Attack, TargetType.AnyEnemy)

def battle_trance(up=False):
    return card(CardId.BATTLE_TRANCE, 0, CardType.Skill, TargetType.Self, up)

def offering(up=False):
    return card(CardId.OFFERING, 0, CardType.Skill, TargetType.Self, up)

def fiend_fire(up=False):
    return card(CardId.FIEND_FIRE, 2, CardType.Attack, TargetType.AnyEnemy, up)

def infernal_blade(up=False):
    return card(CardId.INFERNAL_BLADE, 0 if up else 1, CardType.Skill, TargetType.Self, up)

def ritual(up=False):
    return card(CardId.FORGOTTEN_RITUAL, 1, CardType.Skill, TargetType.Self, up)

def cascade(up=False):
    return card(CardId.CASCADE, "X", CardType.Skill, TargetType.Self, up)

def expect(up=False):
    return card(CardId.EXPECT_A_FIGHT, 1 if up else 2, CardType.Skill, TargetType.Self, up)

def drum(up=False):
    return card(CardId.DRUM_OF_BATTLE, 1, CardType.Skill, TargetType.Self, up)

def howl(up=False):
    return card(CardId.HOWL_FROM_BEYOND, 3, CardType.Attack, TargetType.AllEnemies, up)

def not_yet(up=False):
    return card(CardId.NOT_YET, 2, CardType.Skill, TargetType.Self, up)

def pacts_end(up=False):
    return card(CardId.PACTS_END, 0, CardType.Attack, TargetType.AllEnemies, up)

def conflagration(up=False):
    return card(CardId.CONFLAGRATION, 1, CardType.Attack, TargetType.AllEnemies, up)

def state(hand, enemies=1, hp=100):
    return make_state(hand, enemy_count=enemies, enemy_hp=hp)

def ids(cards):
    return [c.card_id for c in cards]

def fresh(n, make=defend):
    return [make() for _ in range(n)]

def st(creature, status_id):
    return creature.status_amount(status_id)


# ---------------------------------------------------------------- Battle Trance
def test_battle_trance_draws_three_and_four_upgraded():
    cs = state([battle_trance()]); cs.player.draw_pile = fresh(6)
    play(cs)
    assert len(cs.player.hand) == 3
    cs = state([battle_trance(True)]); cs.player.draw_pile = fresh(6)
    play(cs)
    assert len(cs.player.hand) == 4

def test_battle_trance_costs_nothing():
    cs = state([battle_trance()]); cs.player.draw_pile = fresh(6)
    play(cs)
    assert cs.energy == 3

def test_battle_trance_blocks_further_draws_this_turn():
    cs = state([battle_trance(), card(CardId.SHRUG_IT_OFF, 1, CardType.Skill, TargetType.Self)])
    cs.player.draw_pile = fresh(8)
    sim = play(cs)
    assert st(cs.player, StatusId.NO_DRAW) == 1
    cs.player.draw_card()
    assert len(cs.player.hand) == 4        # shrug + 3 drawn, nothing more

def test_blocked_draw_is_not_counted_as_a_draw():
    cs = state([]); cs.player.draw_pile = fresh(3)
    cs.player.apply_status(StatusId.NO_DRAW, 1)
    cs.player.draw_card()
    assert cs.player.cards_drawn == 0 and cs.player.unknown_draws == 0 and cs.player.hand == []

def test_a_second_battle_trance_does_not_stack_the_status():
    cs = state([battle_trance(), battle_trance()]); cs.player.draw_pile = fresh(8)
    sim = play(cs)
    sim.play_card(0, 0)
    assert st(cs.player, StatusId.NO_DRAW) == 1

def test_no_draw_ends_with_the_turn_and_the_next_hand_is_drawn():
    cs = state([battle_trance()]); cs.player.draw_pile = fresh(12)
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 1, 1
    sim = play(cs)
    sim.end_turn()
    assert StatusId.NO_DRAW not in cs.player.status and len(cs.player.hand) == 5

def test_battle_trance_draw_blocks_dark_embrace_draws():
    cs = state([battle_trance(), defend()]); cs.player.draw_pile = fresh(8)
    cs.player.apply_status(StatusId.DARK_EMBRACE, 1)
    sim = play(cs)
    before = len(cs.player.hand)
    victim = cs.player.hand[0]
    cs.player.exhaust_card(victim); sim.fire(EventType.CARD_EXHAUSTED, victim)
    assert len(cs.player.hand) == before - 1

def test_artifact_stops_the_no_draw_debuff():
    cs = state([battle_trance()]); cs.player.draw_pile = fresh(6)
    cs.player.apply_status(StatusId.ARTIFACT, 1)
    play(cs)
    assert StatusId.NO_DRAW not in cs.player.status and StatusId.ARTIFACT not in cs.player.status

def test_battle_trance_with_a_full_hand_still_applies_no_draw():
    cs = state([battle_trance()] + fresh(9)); cs.player.draw_pile = fresh(5)
    play(cs)
    assert len(cs.player.hand) == 9 + 1 - 1 + 1 and st(cs.player, StatusId.NO_DRAW) == 1


# ---------------------------------------------------------------- Offering
def test_offering_loses_six_hp_gains_two_energy_draws_three():
    cs = state([offering()]); cs.player.draw_pile = fresh(6)
    play(cs)
    assert cs.player.current_hp == 44 and cs.energy == 5 and len(cs.player.hand) == 3

def test_offering_upgraded_draws_five():
    cs = state([offering(True)]); cs.player.draw_pile = fresh(8)
    play(cs)
    assert len(cs.player.hand) == 5

def test_offering_exhausts():
    cs = state([offering()])
    play(cs)
    assert ids(cs.player.exhaust_pile) == [CardId.OFFERING] and cs.player.discard_pile == []

def test_offering_hp_loss_ignores_block():
    cs = state([offering()]); cs.player.block = 20
    play(cs)
    assert cs.player.current_hp == 44 and cs.player.block == 20

def test_offering_hp_loss_triggers_rupture():
    cs = state([offering()]); cs.player.apply_status(StatusId.RUPTURE, 1)
    play(cs)
    assert st(cs.player, StatusId.STRENGTH) == 1

def test_offering_killing_the_player_ends_the_fight():
    cs = state([offering()]); cs.player.current_hp = 6; cs.player.draw_pile = fresh(5)
    sim = play(cs)
    assert sim.is_over and cs.player.hand == []

def test_offering_energy_is_blocked_by_expect_a_fight():
    cs = state([offering()]); cs.player.apply_status(StatusId.NO_ENERGY_GAIN, 1)
    play(cs)
    assert cs.energy == 3


# ---------------------------------------------------------------- Fiend Fire
def test_fiend_fire_exhausts_the_hand_and_hits_for_each():
    cs = state([fiend_fire(), strike(), defend(), defend()])
    play(cs)
    assert hps(cs) == [100 - 21] and cs.player.hand == []
    assert len(cs.player.exhaust_pile) == 4          # three cards and Fiend Fire itself

def test_fiend_fire_upgraded_hits_for_ten():
    cs = state([fiend_fire(True), strike(), defend()])
    play(cs)
    assert hps(cs) == [100 - 20]

def test_fiend_fire_with_an_empty_hand_deals_nothing():
    cs = state([fiend_fire()])
    play(cs)
    assert hps(cs) == [100] and ids(cs.player.exhaust_pile) == [CardId.FIEND_FIRE]

def test_fiend_fire_uses_strength_and_vulnerable_on_every_hit():
    cs = state([fiend_fire(), defend(), defend()])
    cs.player.apply_status(StatusId.STRENGTH, 2)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    play(cs)
    assert hps(cs) == [100 - 2 * int(9 * 1.5)]

def test_fiend_fire_exhaust_triggers_feel_no_pain():
    cs = state([fiend_fire(), defend(), defend()])
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 3)
    play(cs)
    assert cs.player.block == 3 * 3                  # two cards and itself

def test_fiend_fire_dark_embrace_draws_are_not_exhausted():
    cs = state([fiend_fire(), defend(), defend()]); cs.player.draw_pile = fresh(6)
    cs.player.apply_status(StatusId.DARK_EMBRACE, 1)
    play(cs)
    assert len(cs.player.hand) == 3 and hps(cs) == [100 - 14]

def test_fiend_fire_rejects_a_bad_target_without_exhausting():
    cs = state([fiend_fire(), defend()])
    with pytest.raises(ValueError):
        play(cs, target=5)
    assert len(cs.player.hand) == 2 and cs.player.exhaust_pile == [] and cs.energy == 3

def test_fiend_fire_can_win_the_fight():
    cs = state([fiend_fire(), defend(), defend(), defend()], hp=20)
    sim = play(cs)
    assert sim.is_over


# ---------------------------------------------------------------- Infernal Blade
def test_infernal_blade_adds_a_free_attack_to_the_hand():
    rng.seed(1)
    cs = state([infernal_blade()])
    play(cs)
    added = cs.player.hand[0]
    assert added.type == CardType.Attack and added.energy_cost == 0 and added.restore_cost is not None
    assert cs.energy == 2

def test_infernal_blade_exhausts_and_upgraded_costs_zero():
    cs = state([infernal_blade(True)])
    play(cs)
    assert cs.energy == 3 and ids(cs.player.exhaust_pile) == [CardId.INFERNAL_BLADE]

def test_infernal_blade_gives_a_variety_of_attacks():
    seen = set()
    for seed in range(60):
        rng.seed(seed)
        cs = state([infernal_blade()])
        play(cs)
        seen.add(cs.player.hand[0].card_id)
    assert len(seen) > 8 and seen <= set(INFERNAL_BLADE_POOL)

def test_the_added_attack_can_be_played_for_free():
    for cid in (CardId.CINDER, CardId.BLUDGEON):
        cs = state([infernal_blade()])
        sim = play(cs)
        cs.player.hand[0] = Card.create_generated(cid)
        cs.player.hand[0].restore_cost, cs.player.hand[0].energy_cost = cs.player.hand[0].energy_cost, 0
        before = cs.energy
        sim.play_card(0, 0)
        assert cs.energy == before and hps(cs)[0] < 100

def test_free_card_gets_its_cost_back_at_the_end_of_the_turn():
    cs = state([infernal_blade()]); cs.player.draw_pile = fresh(12)
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 1, 1
    rng.seed(3)
    sim = play(cs)
    added = cs.player.hand[0]
    expected = GENERATABLE_CARDS[added.card_id][2]
    sim.end_turn()
    again = [c for pile in (cs.player.hand, cs.player.draw_pile, cs.player.discard_pile) for c in pile if c.card_id == added.card_id]
    assert again and all(c.restore_cost is None for c in again)
    assert any(c.energy_cost == expected for c in again)

def test_played_free_card_also_gets_its_cost_back_in_the_discard_pile():
    cs = state([infernal_blade()]); cs.player.draw_pile = fresh(12)
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 1, 1
    rng.seed(4)
    sim = play(cs)
    added_id = cs.player.hand[0].card_id
    sim.play_card(0, 0)
    sim.end_turn()
    cards = [c for pile in (cs.player.hand, cs.player.draw_pile, cs.player.discard_pile, cs.player.exhaust_pile)
             for c in pile if c.card_id == added_id]
    assert cards and all(c.energy_cost == GENERATABLE_CARDS[added_id][2] for c in cards)

def test_infernal_blade_with_a_full_hand_puts_the_card_in_the_discard_pile():
    cs = state([infernal_blade()] + fresh(10))
    play(cs)
    assert len(cs.player.hand) == 10 and len(cs.player.discard_pile) == 1      # Infernal Blade itself exhausts

def test_infernal_blade_choice_is_random():
    rng.seed(0)
    cs = state([infernal_blade()])
    before = rng.calls
    play(cs)
    assert rng.calls > before

def test_every_pool_card_is_an_implemented_attack():
    from sts2_lite.card import GET_CARD_FUNCTION
    for cid in INFERNAL_BLADE_POOL:
        name, card_type, cost, target = GENERATABLE_CARDS[cid]
        assert cid in GET_CARD_FUNCTION
        c = Card.create_generated(cid)
        assert c.type == CardType.Attack and c.name == name and c.energy_cost == cost

def test_restoring_does_not_change_the_original_card_object():
    cs = state([]); free = Card.create_generated(CardId.CINDER)
    free.restore_cost, free.energy_cost = 2, 0
    cs.player.hand = [free]
    cs.player.restore_free_cards()
    assert free.energy_cost == 0 and cs.player.hand[0].energy_cost == 2


# ---------------------------------------------------------------- Forgotten Ritual
def test_forgotten_ritual_gives_energy_after_an_exhaust():
    cs = state([ritual()]); cs.player.cards_exhausted_this_turn = 1
    play(cs)
    assert cs.energy == 2 + 3

def test_forgotten_ritual_upgraded_gives_four():
    cs = state([ritual(True)]); cs.player.cards_exhausted_this_turn = 1
    play(cs)
    assert cs.energy == 2 + 4

def test_forgotten_ritual_without_an_exhaust_does_nothing_but_still_exhausts():
    cs = state([ritual()])
    play(cs)
    assert cs.energy == 2 and ids(cs.player.exhaust_pile) == [CardId.FORGOTTEN_RITUAL]

def test_forgotten_ritual_after_an_earlier_card_exhausted():
    cs = state([offering(), ritual()])
    cs.player.draw_pile = fresh(5)
    sim = play(cs)
    sim.play_card(next(i for i, c in enumerate(cs.player.hand) if c.card_id == CardId.FORGOTTEN_RITUAL), 0)
    assert cs.energy == 3 + 2 - 1 + 3

def test_forgotten_ritual_does_not_count_its_own_exhaust():
    cs = state([ritual(), ritual()])
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.energy == 3 - 1 - 1 + 3        # the first one exhausted itself, so the second pays out

def test_forgotten_ritual_energy_is_blocked_by_no_energy_gain():
    cs = state([ritual()]); cs.player.cards_exhausted_this_turn = 1
    cs.player.apply_status(StatusId.NO_ENERGY_GAIN, 1)
    play(cs)
    assert cs.energy == 2


# ---------------------------------------------------------------- Cascade
def test_cascade_plays_the_top_x_cards():
    cs = state([cascade()])
    cs.player.draw_pile = [defend(), defend(), strike(), strike()]
    cs.energy = 2
    play(cs)
    assert hps(cs) == [100 - 12] and cs.energy == 0
    assert len(cs.player.discard_pile) == 3 and len(cs.player.draw_pile) == 2

def test_cascade_upgraded_plays_one_more():
    cs = state([cascade(True)])
    cs.player.draw_pile = [defend(), strike(), strike(), strike()]
    cs.energy = 2
    play(cs)
    assert hps(cs) == [100 - 18]

def test_cascade_with_zero_energy_plays_nothing_unless_upgraded():
    cs = state([cascade()]); cs.energy = 0
    cs.player.draw_pile = [strike()]
    play(cs)
    assert hps(cs) == [100] and len(cs.player.draw_pile) == 1
    cs = state([cascade(True)]); cs.energy = 0
    cs.player.draw_pile = [strike()]
    play(cs)
    assert hps(cs) == [94]

def test_cascade_played_cards_are_free():
    cs = state([cascade()]); cs.energy = 3
    cs.player.draw_pile = [bash(), bash(), bash()]
    play(cs)
    assert hps(cs) == [100 - 8 - 12 - 12] and cs.energy == 0      # Bash makes the target Vulnerable

def test_cascade_reshuffles_the_discard_pile_when_the_draw_pile_runs_out():
    cs = state([cascade()]); cs.energy = 3
    cs.player.draw_pile = [strike()]
    cs.player.discard_pile = [strike(), strike()]
    rng.seed(0)
    play(cs)
    assert hps(cs) == [100 - 18]

def test_cascade_with_nothing_to_draw_does_nothing():
    cs = state([cascade()]); cs.energy = 3
    play(cs)
    assert hps(cs) == [100] and ids(cs.player.discard_pile) == [CardId.CASCADE]

def test_cascade_sends_unplayable_cards_to_the_discard_pile():
    cs = state([cascade()]); cs.energy = 2
    cs.player.draw_pile = [strike(), Card.create_dazed(), Card.create_wound()]
    play(cs)
    assert hps(cs) == [100]
    assert sorted(c.card_id.name for c in cs.player.discard_pile) == ['CASCADE', 'DAZED', 'WOUND']

def test_cascade_cards_are_taken_before_any_is_played():
    cs = state([cascade()]); cs.energy = 2
    cs.player.draw_pile = [defend(), defend(), strike(), card(CardId.POMMEL_STRIKE, 1, CardType.Attack, TargetType.AnyEnemy)]
    play(cs)
    # Pommel Strike (on top) draws a card, but the Strike below it was already taken, so it still gets played
    assert hps(cs) == [100 - 9 - 6] and len(cs.player.hand) == 1 and len(cs.player.draw_pile) == 1

def test_cascade_exhausting_card_goes_to_exhaust_pile():
    cs = state([cascade()]); cs.energy = 1
    cs.player.draw_pile = [offering()]
    play(cs)
    assert ids(cs.player.exhaust_pile) == [CardId.OFFERING]

def test_cascade_x_card_inside_uses_remaining_energy():
    cs = state([cascade()]); cs.energy = 1
    cs.player.draw_pile = [card(CardId.WHIRLWIND, "X", CardType.Attack, TargetType.AllEnemies)]
    play(cs)
    assert hps(cs) == [100]          # Cascade used up the energy, so Whirlwind has X = 0

def test_cascade_counts_as_an_unforeseen_draw_unless_known():
    cs = state([cascade()]); cs.energy = 2
    cs.player.draw_pile = [strike(), strike(), strike()]
    play(cs)
    assert cs.player.unknown_draws == 2
    cs = state([cascade()]); cs.energy = 2
    cs.player.draw_pile = [strike(), strike(), strike()]; cs.player.known_top = 2
    play(cs)
    assert cs.player.unknown_draws == 0 and cs.player.known_top == 0

def test_cascade_can_win_the_fight_and_stop():
    cs = state([cascade()], hp=6); cs.energy = 3
    cs.player.draw_pile = [strike(), strike(), strike()]
    sim = play(cs)
    assert sim.is_over and len(cs.player.discard_pile) == 2      # Cascade and the one Strike that was played


# ---------------------------------------------------------------- Expect a Fight
def test_expect_a_fight_gives_energy_for_each_attack_in_hand():
    cs = state([expect(), strike(), strike(), defend(), bash()])
    play(cs)
    assert cs.energy == 1 + 3

def test_expect_a_fight_with_no_attacks_gives_nothing():
    cs = state([expect(), defend()])
    play(cs)
    assert cs.energy == 1 and st(cs.player, StatusId.NO_ENERGY_GAIN) == 1

def test_expect_a_fight_upgraded_costs_one():
    cs = state([expect(True), strike()])
    play(cs)
    assert cs.energy == 2 + 1

def test_expect_a_fight_stops_later_energy_gain_this_turn():
    cs = state([expect(), strike(), card(CardId.BLOODLETTING, 0, CardType.Skill, TargetType.Self)])
    sim = play(cs)
    before = cs.energy
    sim.play_card(next(i for i, c in enumerate(cs.player.hand) if c.card_id == CardId.BLOODLETTING), 0)
    assert cs.energy == before

def test_no_energy_gain_ends_with_the_turn_and_energy_refills():
    cs = state([expect(), strike()]); cs.player.draw_pile = fresh(10)
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 1, 1
    sim = play(cs)
    sim.end_turn()
    assert StatusId.NO_ENERGY_GAIN not in cs.player.status and cs.energy == cs.max_energy

def test_expect_a_fight_does_not_count_itself_or_other_skills():
    cs = state([expect(), card(CardId.OFFERING, 0, CardType.Skill, TargetType.Self)])
    play(cs)
    assert cs.energy == 1

def test_artifact_stops_the_no_energy_gain_debuff():
    cs = state([expect(), strike()]); cs.player.apply_status(StatusId.ARTIFACT, 1)
    play(cs)
    assert StatusId.NO_ENERGY_GAIN not in cs.player.status


# ---------------------------------------------------------------- Drum of Battle
def test_drum_of_battle_draws_two_and_does_not_exhaust_itself():
    cs = state([drum()]); cs.player.draw_pile = fresh(5)
    play(cs)
    assert len(cs.player.hand) == 2 and cs.player.exhaust_pile == [] and ids(cs.player.discard_pile) == [CardId.DRUM_OF_BATTLE]
    assert cs.energy == 2

def test_drum_of_battle_gives_energy_when_exhausted():
    cs = state([]); sim = CombatSimulator(cs)
    d = drum(); cs.player.hand = [d]
    cs.player.exhaust_card(d); sim.fire(EventType.CARD_EXHAUSTED, d)
    assert cs.energy == 5

def test_drum_of_battle_upgraded_gives_three():
    cs = state([]); sim = CombatSimulator(cs)
    d = drum(True); cs.player.hand = [d]
    cs.player.exhaust_card(d); sim.fire(EventType.CARD_EXHAUSTED, d)
    assert cs.energy == 6

def test_drum_of_battle_exhausted_by_fiend_fire():
    cs = state([fiend_fire(), drum(), strike()])
    play(cs)
    assert cs.energy == 1 + 2

def test_drum_of_battle_exhausted_by_corruption():
    cs = state([drum()]); cs.player.apply_status(StatusId.CORRUPTION, 1)
    cs.player.draw_pile = fresh(3)
    play(cs)
    assert cs.energy == 3 + 2 and len(cs.player.exhaust_pile) == 1

def test_drum_of_battle_energy_is_blocked_by_no_energy_gain():
    cs = state([]); sim = CombatSimulator(cs)
    cs.player.apply_status(StatusId.NO_ENERGY_GAIN, 1)
    d = drum(); cs.player.hand = [d]
    cs.player.exhaust_card(d); sim.fire(EventType.CARD_EXHAUSTED, d)
    assert cs.energy == 3

def test_other_exhausts_give_no_drum_energy():
    cs = state([]); sim = CombatSimulator(cs)
    s = strike(); cs.player.hand = [s]
    cs.player.exhaust_card(s); sim.fire(EventType.CARD_EXHAUSTED, s)
    assert cs.energy == 3


# ---------------------------------------------------------------- Howl from Beyond
def test_howl_hits_all_enemies_for_sixteen_and_twenty_one():
    cs = state([howl()], enemies=2); cs.energy = 3
    play(cs)
    assert hps(cs) == [84, 84] and cs.energy == 0
    cs = state([howl(True)], enemies=2); cs.energy = 3
    play(cs)
    assert hps(cs) == [79, 79]

def test_howl_goes_to_the_discard_pile_when_played():
    cs = state([howl()]); cs.energy = 3
    play(cs)
    assert ids(cs.player.discard_pile) == [CardId.HOWL_FROM_BEYOND]

def test_howl_in_the_exhaust_pile_plays_at_the_end_of_the_turn():
    cs = state([defend()], enemies=2)
    cs.player.exhaust_pile = [howl()]
    for e in cs.enemies:
        e.attack_damage, e.num_attacks = 0, 1
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [84, 84]
    assert cs.player.exhaust_pile == []

def test_howl_leaves_the_exhaust_pile_after_playing():
    cs = state([defend()])
    cs.player.exhaust_pile = [howl()]
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 0, 1
    CombatSimulator(cs).end_turn()
    assert ids(cs.player.exhaust_pile) == []
    total = [c for pile in (cs.player.hand, cs.player.draw_pile, cs.player.discard_pile) for c in pile if c.card_id == CardId.HOWL_FROM_BEYOND]
    assert len(total) == 1

def test_two_howls_in_the_exhaust_pile_both_play():
    cs = state([defend()])
    cs.player.exhaust_pile = [howl(), howl(True)]
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 0, 1
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [100 - 16 - 21]

def test_howl_end_of_turn_play_can_win_the_fight():
    cs = state([defend()], hp=10)
    cs.player.exhaust_pile = [howl()]
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert sim.is_over

def test_howl_is_not_played_while_in_the_hand_or_discard_pile():
    cs = state([howl()]); cs.player.discard_pile = [howl()]
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 0, 1
    CombatSimulator(cs).end_turn()
    assert hps(cs) == [100]

def test_howl_burned_by_fiend_fire_hits_at_end_of_turn():
    cs = state([fiend_fire(), howl()]); cs.energy = 3
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 0, 1
    sim = play(cs)
    assert hps(cs) == [100 - 7]
    sim.end_turn()
    assert hps(cs) == [100 - 7 - 16]


# ---------------------------------------------------------------- Not Yet
def test_not_yet_heals_ten_and_thirteen_upgraded():
    cs = state([not_yet()]); cs.player.current_hp = 20; cs.energy = 2
    play(cs)
    assert cs.player.current_hp == 30
    cs = state([not_yet(True)]); cs.player.current_hp = 20; cs.energy = 2
    play(cs)
    assert cs.player.current_hp == 33

def test_not_yet_does_not_heal_above_max_hp():
    cs = state([not_yet()]); cs.player.current_hp = 45
    play(cs)
    assert cs.player.current_hp == 50

def test_not_yet_exhausts_and_costs_two():
    cs = state([not_yet()])
    play(cs)
    assert cs.energy == 1 and ids(cs.player.exhaust_pile) == [CardId.NOT_YET]

def test_not_yet_is_not_playable_without_energy():
    cs = state([not_yet()]); cs.energy = 1
    with pytest.raises(Exception):
        play(cs)


# ---------------------------------------------------------------- Pact's End
def test_pacts_end_needs_three_exhausted_cards():
    cs = state([pacts_end()], enemies=2)
    cs.player.exhaust_pile = [strike(), strike()]
    play(cs)
    assert hps(cs) == [100, 100]

def test_pacts_end_hits_all_enemies_with_three_exhausted():
    cs = state([pacts_end()], enemies=2)
    cs.player.exhaust_pile = [strike(), strike(), strike()]
    play(cs)
    assert hps(cs) == [83, 83] and cs.energy == 3

def test_pacts_end_upgraded_deals_twenty_three():
    cs = state([pacts_end(True)], enemies=2)
    cs.player.exhaust_pile = fresh(5)
    play(cs)
    assert hps(cs) == [77, 77]

def test_pacts_end_does_not_count_itself_or_the_discard_pile():
    cs = state([pacts_end()])
    cs.player.exhaust_pile = [strike(), strike()]; cs.player.discard_pile = fresh(4)
    play(cs)
    assert hps(cs) == [100]

def test_pacts_end_after_exhausting_with_fiend_fire():
    cs = state([fiend_fire(), strike(), strike(), pacts_end()], enemies=1)
    cs.energy = 5
    sim = play(cs)
    hand_idx = next(i for i, c in enumerate(cs.player.hand) if c.card_id == CardId.PACTS_END) if cs.player.hand else None
    assert hand_idx is None          # fiend fire exhausted the whole hand, pact's end included
    assert len(cs.player.exhaust_pile) == 4

def test_pacts_end_goes_to_the_discard_pile():
    cs = state([pacts_end()]); cs.player.exhaust_pile = fresh(3)
    play(cs)
    assert ids(cs.player.discard_pile) == [CardId.PACTS_END]

def test_pacts_end_uses_strength():
    cs = state([pacts_end()]); cs.player.exhaust_pile = fresh(3)
    cs.player.apply_status(StatusId.STRENGTH, 3)
    play(cs)
    assert hps(cs) == [100 - 20]


# ---------------------------------------------------------------- Conflagration
def test_conflagration_hits_everything_four_times_for_two():
    cs = state([conflagration()], enemies=2)
    play(cs)
    assert hps(cs) == [92, 92]

def test_conflagration_upgraded_hits_five_times():
    cs = state([conflagration(True)], enemies=2)
    play(cs)
    assert hps(cs) == [90, 90]

def test_conflagration_strength_applies_to_each_hit():
    cs = state([conflagration()])
    cs.player.apply_status(StatusId.STRENGTH, 2)
    play(cs)
    assert hps(cs) == [100 - 16]

def test_conflagration_vulnerable():
    cs = state([conflagration()])
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    play(cs)
    assert hps(cs) == [100 - 12]

def test_conflagration_ignores_dead_enemies():
    cs = state([conflagration()], enemies=2)
    cs.enemies[1].current_hp = 0
    play(cs)
    assert hps(cs) == [92]          # the dead enemy has left the fight

def test_conflagration_one_two_punch_doubles_it():
    cs = state([conflagration()]); cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    play(cs)
    assert hps(cs) == [100 - 16]

def test_conflagration_block_absorbs_each_hit():
    cs = state([conflagration()]); cs.enemies[0].block = 3
    play(cs)
    assert hps(cs) == [100 - 5]


# ---------------------------------------------------------------- loading from the bridge
def test_bridge_ids_for_the_new_statuses_load():
    assert StatusInstance.from_dict({"id": "NO_DRAW_POWER", "amount": 1}).status_id == StatusId.NO_DRAW
    assert StatusInstance.from_dict({"id": "NO_ENERGY_GAIN_POWER", "amount": 1}).status_id == StatusId.NO_ENERGY_GAIN

def test_new_cards_load_from_the_bridge():
    for name in ("BATTLE_TRANCE", "CASCADE", "CONFLAGRATION", "DRUM_OF_BATTLE", "EXPECT_A_FIGHT", "FIEND_FIRE",
                 "FORGOTTEN_RITUAL", "HOWL_FROM_BEYOND", "INFERNAL_BLADE", "NOT_YET", "OFFERING", "PACTS_END"):
        c = Card.from_dict({"id": name, "type": "Skill", "name": name, "can_play": True, "cost": "1",
                            "is_upgraded": False, "target_type": "Self"})
        assert c.card_id == CardId[name]

def test_statuses_survive_a_copy_of_the_state():
    cs = state([]); cs.player.apply_status(StatusId.NO_DRAW, 1)
    assert StatusId.NO_DRAW in CombatState.deepcopy(cs).player.status

def test_a_free_card_stays_free_in_a_copy_of_the_state():
    cs = state([])
    free = Card.create_generated(CardId.CINDER)
    free.restore_cost, free.energy_cost = 2, 0
    cs.player.hand = [free]
    assert CombatState.deepcopy(cs).player.hand[0].energy_cost == 0

def test_upgraded_copy_keeps_the_restore_cost_marker():
    free = Card.create_generated(CardId.CINDER)
    free.restore_cost, free.energy_cost = 2, 0
    assert free.upgraded_copy().restore_cost == 2


# ---------------------------------------------------------------- extra checks found by mutation testing
def test_cascade_stops_playing_once_the_fight_is_won():
    cs = state([cascade()], hp=6); cs.energy = 2
    cs.player.draw_pile = [defend(), strike()]
    sim = play(cs)
    assert sim.is_over and cs.player.block == 0

def test_a_second_expect_a_fight_gains_no_energy():
    cs = state([expect(), expect(), strike()])
    cs.energy = 5
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.energy == 5 - 2 + 1 - 2        # the first gained one for the Strike, the second gained nothing

def test_expect_a_fight_and_infernal_blade_cost_one_less_when_upgraded():
    assert expect().upgraded_copy().energy_cost == 1
    assert infernal_blade().upgraded_copy().energy_cost == 0

def test_the_start_of_turn_hand_is_drawn_even_under_no_draw():
    cs = state([]); cs.player.draw_pile = fresh(8)
    cs.player.apply_status(StatusId.NO_DRAW, 1)
    cs.player.turn_start()
    assert len(cs.player.hand) == 5

def test_howl_that_comes_after_the_win_stays_in_the_exhaust_pile():
    cs = state([defend()], hp=10)
    cs.player.exhaust_pile = [howl(), howl()]
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert sim.is_over and len(cs.player.exhaust_pile) == 1


def test_cascade_waits_for_a_card_choice_before_playing_the_next_card():
    """Burning Pact played by Cascade asks which cards to exhaust; the card after it must not change the hand under that choice."""
    pact = card(CardId.BURNING_PACT, 1, CardType.Skill, TargetType.Self)
    cs = state([cascade(), strike(), defend()]); cs.energy = 2
    cs.player.draw_pile = [defend(), pact]              # the end is the top: Burning Pact plays first
    sim = play(cs)
    pending = cs.pending_choice
    assert pending is not None and pending.kind == "exhaust"
    assert [k for k, *_ in cs.continuations] == ["finish", "play", "finish"] and cs.player.block == 0
    assert all(i < len(cs.player.hand) for i in pending.indices)
    assert all(a["card_index"] < len(cs.player.hand) for a in sim.get_available_actions())
    sim.choose_card(pending.indices[0])
    assert cs.continuations == [] and cs.player.block == 5      # the Defend played after the pick

def test_cascade_queue_is_copied_with_the_state():
    pact = card(CardId.BURNING_PACT, 1, CardType.Skill, TargetType.Self)
    cs = state([cascade(), strike(), defend()]); cs.energy = 2
    cs.player.draw_pile = [defend(), pact]
    play(cs)
    copy = CombatState.deepcopy(cs)
    assert len(copy.continuations) == 3 and copy.continuations is not cs.continuations


def test_havoc_playing_headbutt_does_not_reshuffle_the_discard_pile_under_the_pick():
    """Havoc exhausts the card it played, and Dark Embrace then draws: that happens after the pick, not before it."""
    cs = state([card(CardId.HAVOC, 1, CardType.Skill, TargetType.Self), strike()]); cs.energy = 1
    cs.player.draw_pile = [card(CardId.HEADBUTT, 1, CardType.Attack, TargetType.AnyEnemy)]
    cs.player.discard_pile = [defend(), bash(), defend()]
    cs.player.apply_status(StatusId.DARK_EMBRACE, 1)
    sim = play(cs)
    pending = cs.pending_choice
    assert pending is not None and pending.pile == "discard" and pending.indices and all(i < len(cs.player.discard_pile) for i in pending.indices)
    sim.choose_card(pending.indices[0])
    assert cs.pending_choice is None and cs.continuations == []
