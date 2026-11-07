"""Brand, Giant Rock, Hellraiser, Inferno, Mangle, Pillage, Primal Force, Rampage, Setup Strike, Stoke, Stomp,
Tear Asunder and Thrash. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.card import (Card, CardId, CardType, TargetType, GENERATABLE_CARDS, INFERNAL_BLADE_POOL, STOKE_POOL,
                            GET_CARD_FUNCTION, STRIKE_CARDS)
from sts2_lite.combat import CombatSimulator, CombatState, IllegalActionError
from sts2_lite.events import EventType
from sts2_lite.player import Player
from sts2_lite.status import StatusId, StatusInstance
from sts2_lite.Tests.test_cards import make_card, make_state, play, hps


def card(card_id, cost, kind, target, upgraded=False):
    return make_card(card_id, card_id.name.title(), kind, cost, target, upgraded)

def strike(up=False):
    return card(CardId.STRIKE_IRONCLAD, 1, CardType.Attack, TargetType.AnyEnemy, up)

def defend():
    return card(CardId.DEFEND_IRONCLAD, 1, CardType.Skill, TargetType.Self)

def bash():
    return card(CardId.BASH, 2, CardType.Attack, TargetType.AnyEnemy)

def pommel():
    return card(CardId.POMMEL_STRIKE, 1, CardType.Attack, TargetType.AnyEnemy)

def brand(up=False):
    return card(CardId.BRAND, 0, CardType.Skill, TargetType.Self, up)

def hellraiser(up=False):
    return card(CardId.HELLRAISER, 1 if up else 2, CardType.Power, TargetType.Self, up)

def inferno(up=False):
    return card(CardId.INFERNO, 1, CardType.Power, TargetType.Self, up)

def mangle(up=False):
    return card(CardId.MANGLE, 3, CardType.Attack, TargetType.AnyEnemy, up)

def pillage(up=False):
    return card(CardId.PILLAGE, 1, CardType.Attack, TargetType.AnyEnemy, up)

def primal_force(up=False):
    return card(CardId.PRIMAL_FORCE, 0, CardType.Skill, TargetType.Self, up)

def rampage(up=False):
    return card(CardId.RAMPAGE, 1, CardType.Attack, TargetType.AnyEnemy, up)

def setup_strike(up=False):
    return card(CardId.SETUP_STRIKE, 1, CardType.Attack, TargetType.AnyEnemy, up)

def stoke(up=False):
    return card(CardId.STOKE, 1, CardType.Skill, TargetType.Self, up)

def stomp(cost=3, up=False):
    return card(CardId.STOMP, cost, CardType.Attack, TargetType.AllEnemies, up)

def tear_asunder(up=False):
    return card(CardId.TEAR_ASUNDER, 2, CardType.Attack, TargetType.AnyEnemy, up)

def thrash(up=False):
    return card(CardId.THRASH, 1, CardType.Attack, TargetType.AnyEnemy, up)

def state(hand, enemies=1, hp=100):
    return make_state(hand, enemy_count=enemies, enemy_hp=hp)

def ids(cards):
    return [c.card_id for c in cards]

def fresh(n, make=defend):
    return [make() for _ in range(n)]

def st(creature, status_id):
    return creature.status_amount(status_id)

def hit_back(cs, damage, hits=1):
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = damage, hits


# ---------------------------------------------------------------- Brand
def test_brand_costs_one_hp_and_gives_strength_after_exhausting_a_card():
    cs = state([brand(), strike(), defend()])
    sim = play(cs)
    assert cs.player.current_hp == 49 and st(cs.player, StatusId.STRENGTH) == 1
    assert cs.pending_choice is not None
    sim.choose_card(1)
    assert ids(cs.player.exhaust_pile) == [CardId.DEFEND_IRONCLAD]

def test_brand_upgraded_gives_two_strength():
    cs = state([brand(True), strike()])
    play(cs)
    assert st(cs.player, StatusId.STRENGTH) == 2

def test_brand_does_not_exhaust_itself_and_costs_nothing():
    cs = state([brand(), strike()])
    play(cs)
    assert ids(cs.player.discard_pile) == [CardId.BRAND] and cs.energy == 3

def test_brand_with_one_other_card_exhausts_it_at_once():
    cs = state([brand(), strike()])
    play(cs)
    assert cs.pending_choice is None and ids(cs.player.exhaust_pile) == [CardId.STRIKE_IRONCLAD]

def test_brand_with_an_empty_hand_still_gives_strength():
    cs = state([brand()])
    play(cs)
    assert cs.pending_choice is None and st(cs.player, StatusId.STRENGTH) == 1

def test_brand_exhaust_triggers_feel_no_pain():
    cs = state([brand(), strike()])
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 4)
    play(cs)
    assert cs.player.block == 4

def test_brand_hp_loss_is_unblockable_and_triggers_rupture():
    cs = state([brand(), strike()]); cs.player.block = 10
    cs.player.apply_status(StatusId.RUPTURE, 1)
    play(cs)
    assert cs.player.current_hp == 49 and cs.player.block == 10 and st(cs.player, StatusId.STRENGTH) == 2

def test_brand_at_one_hp_kills_the_player():
    cs = state([brand(), strike()]); cs.player.current_hp = 1
    sim = play(cs)
    assert sim.is_over and st(cs.player, StatusId.STRENGTH) == 0


# ---------------------------------------------------------------- Giant Rock
def test_giant_rock_deals_sixteen_and_twenty_upgraded():
    cs = state([card(CardId.GIANT_ROCK, 1, CardType.Attack, TargetType.AnyEnemy)])
    play(cs)
    assert hps(cs) == [84]
    cs = state([card(CardId.GIANT_ROCK, 1, CardType.Attack, TargetType.AnyEnemy, True)])
    play(cs)
    assert hps(cs) == [80]


# ---------------------------------------------------------------- Primal Force
def test_primal_force_turns_every_attack_into_a_giant_rock():
    cs = state([primal_force(), strike(), defend(), bash(), strike()])
    play(cs)
    assert ids(cs.player.hand) == [CardId.GIANT_ROCK, CardId.DEFEND_IRONCLAD, CardId.GIANT_ROCK, CardId.GIANT_ROCK]
    assert all(not c.is_upgraded for c in cs.player.hand)

def test_upgraded_primal_force_makes_upgraded_rocks():
    cs = state([primal_force(True), strike()])
    play(cs)
    assert cs.player.hand[0].card_id == CardId.GIANT_ROCK and cs.player.hand[0].is_upgraded
    assert cs.player.hand[0].name == "Giant Rock+"

def test_primal_force_leaves_other_cards_and_piles_alone():
    cs = state([primal_force(), defend()])
    cs.player.draw_pile = [strike()]; cs.player.discard_pile = [strike()]
    play(cs)
    assert ids(cs.player.hand) == [CardId.DEFEND_IRONCLAD]
    assert ids(cs.player.draw_pile) == [CardId.STRIKE_IRONCLAD] and ids(cs.player.discard_pile) == [CardId.STRIKE_IRONCLAD, CardId.PRIMAL_FORCE]

def test_a_giant_rock_from_primal_force_is_playable():
    cs = state([primal_force(), strike()])
    sim = play(cs)
    sim.play_card(0, 0)
    assert hps(cs) == [84] and cs.energy == 2

def test_primal_force_costs_nothing_and_does_not_exhaust():
    cs = state([primal_force()])
    play(cs)
    assert cs.energy == 3 and ids(cs.player.discard_pile) == [CardId.PRIMAL_FORCE]


# ---------------------------------------------------------------- Setup Strike
def test_setup_strike_hits_then_gives_temporary_strength():
    cs = state([setup_strike()])
    play(cs)
    assert hps(cs) == [93] and st(cs.player, StatusId.STRENGTH) == 2 and st(cs.player, StatusId.SETUP_STRIKE) == 2

def test_setup_strike_upgraded():
    cs = state([setup_strike(True)])
    play(cs)
    assert hps(cs) == [91] and st(cs.player, StatusId.STRENGTH) == 3

def test_the_strength_is_used_by_the_next_attack_this_turn():
    cs = state([setup_strike(), strike()])
    sim = play(cs)
    sim.play_card(0, 0)
    assert hps(cs) == [100 - 7 - 8]

def test_setup_strike_strength_goes_at_the_end_of_the_turn():
    cs = state([setup_strike()]); cs.player.draw_pile = fresh(10)
    sim = play(cs)
    sim.end_turn()
    assert st(cs.player, StatusId.STRENGTH) == 0 and StatusId.SETUP_STRIKE not in cs.player.status

def test_setup_strike_strength_goes_before_the_enemy_acts():
    cs = state([setup_strike()]); cs.player.draw_pile = fresh(10)
    cs.player.apply_status(StatusId.STRENGTH, 1)
    sim = play(cs)
    sim.end_turn()
    assert st(cs.player, StatusId.STRENGTH) == 1

def test_two_setup_strikes_stack_and_both_are_returned():
    cs = state([setup_strike(), setup_strike()]); cs.player.draw_pile = fresh(10)
    sim = play(cs)
    sim.play_card(0, 0)
    assert st(cs.player, StatusId.STRENGTH) == 4
    sim.end_turn()
    assert st(cs.player, StatusId.STRENGTH) == 0

def perfected_strike(up=False):
    return card(CardId.PERFECTED_STRIKE, 2, CardType.Attack, TargetType.AnyEnemy, up)

def test_perfected_strike_counts_itself():
    cs = state([perfected_strike()])
    play(cs)
    assert hps(cs) == [100 - 8]

def test_perfected_strike_counts_strikes_in_every_pile():
    cs = state([perfected_strike(), card(CardId.STRIKE_IRONCLAD, 1, CardType.Attack, TargetType.AnyEnemy)])
    cs.player.draw_pile = [card(CardId.TWIN_STRIKE, 1, CardType.Attack, TargetType.AnyEnemy)]
    cs.player.discard_pile = [card(CardId.POMMEL_STRIKE, 1, CardType.Attack, TargetType.AnyEnemy)]
    cs.player.exhaust_pile = [card(CardId.ASHEN_STRIKE, 1, CardType.Attack, TargetType.AnyEnemy)]
    play(cs)
    assert hps(cs) == [100 - (6 + 2 * 5)]       # itself, hand, draw, discard and exhaust

def test_perfected_strike_counts_a_generated_strike_and_ignores_other_cards():
    cs = state([perfected_strike(True), card(CardId.DEFEND_IRONCLAD, 1, CardType.Skill, TargetType.Self)])
    cs.player.discard_pile = [Card.create_generated(CardId.SETUP_STRIKE)]
    play(cs)
    assert hps(cs) == [100 - (6 + 3 * 2)]

def test_perfected_strike_counts_a_strike_exhausted_during_the_fight():
    cs = state([perfected_strike()])
    cs.player.exhaust_pile = [card(CardId.STRIKE_IRONCLAD, 1, CardType.Attack, TargetType.AnyEnemy)]
    play(cs)
    assert hps(cs) == [100 - (6 + 2 * 2)]


# ---------------------------------------------------------------- Mangle
def test_mangle_hits_and_takes_ten_strength_from_the_enemy():
    cs = state([mangle()]); cs.energy = 3
    play(cs)
    assert hps(cs) == [85] and st(cs.enemies[0], StatusId.STRENGTH) == -10 and st(cs.enemies[0], StatusId.MANGLE) == 10

def test_mangle_upgraded():
    cs = state([mangle(True)]); cs.energy = 3
    play(cs)
    assert hps(cs) == [80] and st(cs.enemies[0], StatusId.STRENGTH) == -15

def test_mangle_weakens_the_enemy_attack_this_turn_only():
    cs = state([mangle()]); cs.energy = 3; cs.player.draw_pile = fresh(10)
    hit_back(cs, 12)
    sim = play(cs)
    sim.end_turn()
    assert cs.player.current_hp == 50 - 2
    assert st(cs.enemies[0], StatusId.STRENGTH) == 0 and StatusId.MANGLE not in cs.enemies[0].status

def test_artifact_blocks_mangle_but_not_the_damage():
    cs = state([mangle()]); cs.energy = 3
    cs.enemies[0].apply_status(StatusId.ARTIFACT, 1)
    play(cs)
    assert hps(cs) == [85] and st(cs.enemies[0], StatusId.STRENGTH) == 0 and StatusId.MANGLE not in cs.enemies[0].status
    assert StatusId.ARTIFACT not in cs.enemies[0].status

def test_mangle_after_an_enemy_with_strength_gets_restored_exactly():
    cs = state([mangle()]); cs.energy = 3; cs.player.draw_pile = fresh(10)
    cs.enemies[0].apply_status(StatusId.STRENGTH, 3)
    sim = play(cs)
    sim.end_turn()
    assert st(cs.enemies[0], StatusId.STRENGTH) == 3

def test_mangle_costs_three():
    cs = state([mangle()]); cs.energy = 2
    with pytest.raises(Exception):
        play(cs)


# ---------------------------------------------------------------- Pillage
def test_pillage_draws_until_a_non_attack():
    cs = state([pillage()])
    cs.player.draw_pile = [defend(), strike(), strike(), bash()]
    play(cs)
    assert hps(cs) == [94] and ids(cs.player.hand) == [CardId.BASH, CardId.STRIKE_IRONCLAD, CardId.STRIKE_IRONCLAD, CardId.DEFEND_IRONCLAD]
    assert cs.player.draw_pile == []

def test_pillage_stops_after_the_first_non_attack():
    cs = state([pillage()])
    cs.player.draw_pile = [strike(), strike(), defend(), strike()]
    play(cs)
    assert ids(cs.player.hand) == [CardId.STRIKE_IRONCLAD, CardId.DEFEND_IRONCLAD] and len(cs.player.draw_pile) == 2

def test_pillage_with_a_non_attack_on_top_draws_one():
    cs = state([pillage()])
    cs.player.draw_pile = [strike(), defend()]
    play(cs)
    assert len(cs.player.hand) == 1

def test_pillage_upgraded_deals_nine():
    cs = state([pillage(True)])
    cs.player.draw_pile = [defend()]
    play(cs)
    assert hps(cs) == [91]

def test_pillage_stops_when_the_hand_is_full():
    cs = state([pillage()] + fresh(8, strike))
    cs.player.draw_pile = fresh(5, strike)
    play(cs)
    assert len(cs.player.hand) == 10 and len(cs.player.draw_pile) == 3

def test_pillage_with_nothing_to_draw_stops():
    cs = state([pillage()])
    play(cs)
    assert cs.player.hand == []

def test_pillage_does_nothing_more_under_no_draw():
    cs = state([pillage()]); cs.player.draw_pile = fresh(5, strike)
    cs.player.apply_status(StatusId.NO_DRAW, 1)
    play(cs)
    assert cs.player.hand == []

def test_pillage_reshuffles_the_discard_pile():
    cs = state([pillage()]); cs.player.discard_pile = [strike(), defend()]
    rng.seed(1)
    play(cs)
    assert len(cs.player.hand) >= 1

def test_pillage_counts_unforeseen_draws():
    cs = state([pillage()]); cs.player.draw_pile = [defend(), strike()]
    play(cs)
    assert cs.player.unknown_draws == 2

def test_draw_card_returns_the_card():
    cs = state([]); d = defend(); cs.player.draw_pile = [d]
    assert cs.player.draw_card() is d and cs.player.draw_card() is None


# ---------------------------------------------------------------- Stomp
def test_stomp_hits_all_enemies_for_twelve_and_fifteen():
    cs = state([stomp()], enemies=2); cs.energy = 3
    play(cs)
    assert hps(cs) == [88, 88]
    cs = state([stomp(up=True)], enemies=2); cs.energy = 3
    play(cs)
    assert hps(cs) == [85, 85]

def test_stomp_gets_cheaper_with_every_attack_played():
    cs = state([stomp(), strike(), strike()])
    sim = CombatSimulator(cs)
    sim.play_card(1, 0)
    assert cs.player.hand[0].energy_cost == 2
    sim.play_card(1, 0)
    assert cs.player.hand[0].energy_cost == 1

def test_stomp_in_the_draw_and_discard_piles_gets_cheaper_too():
    cs = state([strike()]); cs.player.draw_pile = [stomp()]; cs.player.discard_pile = [stomp()]
    play(cs)
    assert cs.player.draw_pile[0].energy_cost == 2 and cs.player.discard_pile[0].energy_cost == 2

def test_skills_do_not_make_stomp_cheaper():
    cs = state([defend(), stomp()])
    play(cs)
    assert cs.player.hand[0].energy_cost == 3

def test_stomp_never_costs_less_than_zero():
    cs = state([strike(), strike(), strike(), strike(), stomp()]); cs.energy = 9
    sim = CombatSimulator(cs)
    for _ in range(4):
        sim.play_card(0, 0)
    assert cs.player.hand[0].energy_cost == 0

def test_stomp_can_be_played_for_its_reduced_cost():
    cs = state([strike(), stomp()], enemies=2)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert cs.energy == 3 - 1 - 2 and hps(cs)[1] == 88

def test_stomp_played_costs_less_for_the_next_one_too():
    cs = state([stomp(), stomp()]); cs.energy = 6
    sim = play(cs)
    assert cs.player.hand[0].energy_cost == 2

def test_stomp_cost_comes_back_at_the_end_of_the_turn():
    cs = state([strike(), stomp()]); cs.player.draw_pile = fresh(10)
    hit_back(cs, 0)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.end_turn()
    stomps = [c for pile in (cs.player.hand, cs.player.draw_pile, cs.player.discard_pile) for c in pile if c.card_id == CardId.STOMP]
    assert len(stomps) == 1 and stomps[0].energy_cost == 3 and stomps[0].restore_cost is None

def test_a_stomp_made_mid_turn_counts_the_attacks_already_played():
    cs = state([strike(), strike()])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0); sim.play_card(0, 0)
    cs.player.add_to_hand(Card.create_generated(CardId.STOMP))
    assert cs.player.hand[0].energy_cost == 1

def test_a_stomp_made_before_any_attack_costs_three():
    cs = state([])
    cs.player.add_to_hand(Card.create_generated(CardId.STOMP))
    assert cs.player.hand[0].energy_cost == 3

def test_a_loaded_cheap_stomp_remembers_its_full_cost():
    c = Card.from_dict({"id": "STOMP", "type": "Attack", "name": "Stomp", "can_play": True, "cost": "1",
                        "is_upgraded": False, "target_type": "AllEnemies", "description": "Deal 12 damage."})
    assert c.energy_cost == 1 and c.restore_cost == 3
    c = Card.from_dict({"id": "STOMP", "type": "Attack", "name": "Stomp", "can_play": True, "cost": "3",
                        "is_upgraded": False, "target_type": "AllEnemies", "description": "Deal 12 damage."})
    assert c.restore_cost is None

def test_stomp_cost_change_does_not_touch_the_shared_card_object():
    s = stomp(); cs = state([strike()]); cs.player.draw_pile = [s]
    play(cs)
    assert s.energy_cost == 3 and cs.player.draw_pile[0].energy_cost == 2


# ---------------------------------------------------------------- Tear Asunder
def test_tear_asunder_hits_once_at_full_health():
    cs = state([tear_asunder()])
    play(cs)
    assert hps(cs) == [95]

def test_tear_asunder_upgraded_hits_for_seven():
    cs = state([tear_asunder(True)])
    play(cs)
    assert hps(cs) == [93]

def test_tear_asunder_hits_once_more_for_every_time_the_player_lost_hp():
    cs = state([tear_asunder()])
    cs.player.apply_damage(3); cs.player.apply_damage(2); cs.player.lose_hp(1)
    play(cs)
    assert hps(cs) == [100 - 4 * 5]

def test_fully_blocked_hits_do_not_count_for_tear_asunder():
    cs = state([tear_asunder()]); cs.player.block = 50
    cs.player.apply_damage(10)
    play(cs)
    assert hps(cs) == [95]

def test_tear_asunder_counts_hp_lost_to_cards():
    cs = state([card(CardId.BLOODLETTING, 0, CardType.Skill, TargetType.Self), tear_asunder()])
    sim = play(cs)
    sim.play_card(0, 0)
    assert hps(cs) == [90]

def test_tear_asunder_uses_strength_on_every_hit():
    cs = state([tear_asunder()]); cs.player.apply_damage(1)
    cs.player.apply_status(StatusId.STRENGTH, 2)
    play(cs)
    assert hps(cs) == [100 - 14]

def test_tear_asunder_counts_enemy_hits_from_earlier_turns():
    cs = state([tear_asunder()]); cs.player.draw_pile = fresh(10)
    hit_back(cs, 5)
    sim = CombatSimulator(cs)
    sim.end_turn(); sim.end_turn()
    cs.player.hand = [tear_asunder()]
    sim.play_card(0, 0)
    assert hps(cs) == [100 - 3 * 5]

def test_the_hit_count_is_carried_over_a_reload():
    prev = state([]); prev.player.apply_damage(3); prev.player.apply_damage(3)
    new = state([tear_asunder()])
    new.carry_combat_counters(prev)
    play(new)
    assert hps(new) == [100 - 3 * 5]

def test_carrying_counters_never_lowers_them():
    prev = state([]); new = state([]); new.player.hp_loss_events = 4
    new.carry_combat_counters(prev); new.carry_combat_counters(None)
    assert new.player.hp_loss_events == 4


# ---------------------------------------------------------------- Rampage
def test_rampage_grows_by_five_each_play():
    cs = state([rampage()]); cs.energy = 9
    sim = play(cs)
    assert hps(cs) == [91]
    cs.player.hand = list(cs.player.discard_pile); cs.player.discard_pile = []
    sim.play_card(0, 0)
    assert hps(cs) == [91 - 14]
    cs.player.hand = list(cs.player.discard_pile); cs.player.discard_pile = []
    sim.play_card(0, 0)
    assert hps(cs) == [91 - 14 - 19]

def test_upgraded_rampage_grows_by_nine():
    cs = state([rampage(True)]); cs.energy = 9
    sim = play(cs)
    cs.player.hand = list(cs.player.discard_pile); cs.player.discard_pile = []
    sim.play_card(0, 0)
    assert hps(cs) == [100 - 9 - 18]

def test_the_growth_stays_on_the_card_in_the_discard_pile():
    cs = state([rampage()])
    play(cs)
    assert cs.player.discard_pile[0].bonus_damage == 5 and cs.player.discard_pile[0].card_id == CardId.RAMPAGE

def test_playing_rampage_does_not_change_the_card_object_it_started_as():
    original = rampage(); cs = state([original])
    play(cs)
    assert original.bonus_damage == 0 and cs.player.discard_pile[0] is not original

def test_other_branches_do_not_see_the_growth():
    original = rampage(); cs = state([original])
    branch = CombatState.deepcopy(cs)
    play(cs)
    CombatSimulator(branch).play_card(0, 0)
    assert hps(branch) == [91] and original.bonus_damage == 0

def test_a_rampage_that_is_not_played_stays_the_same():
    cs = state([rampage(), defend()]); cs.player.hand[0].bonus_damage = 10
    play(cs, target=0)
    assert hps(cs) == [100 - 19]

def test_rampage_strength_applies_on_top():
    cs = state([rampage()]); cs.player.apply_status(StatusId.STRENGTH, 3)
    play(cs)
    assert hps(cs) == [100 - 12]

def test_one_two_punch_plays_rampage_twice_with_growth():
    cs = state([rampage()]); cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    play(cs)
    assert hps(cs) == [100 - 9 - 14] and cs.player.discard_pile[0].bonus_damage == 10

def test_a_failed_rampage_play_leaves_the_original_in_the_hand():
    original = rampage(); cs = state([original])
    with pytest.raises(ValueError):
        play(cs, target=5)
    assert cs.player.hand == [original]

def test_juggling_copies_keep_the_growth():
    r = rampage(); r.bonus_damage = 5
    assert Card.create_copy(r).bonus_damage == 5

def test_generated_rampage_is_fresh():
    assert Card.create_generated(CardId.RAMPAGE).bonus_damage == 0


# ---------------------------------------------------------------- Thrash
def test_thrash_hits_twice_for_four():
    cs = state([thrash()])
    play(cs)
    assert hps(cs) == [92]

def test_thrash_upgraded_hits_twice_for_six():
    cs = state([thrash(True)])
    play(cs)
    assert hps(cs) == [88]

def test_thrash_exhausts_an_attack_and_adds_its_damage():
    cs = state([thrash(), strike()])
    play(cs)
    assert ids(cs.player.exhaust_pile) == [CardId.STRIKE_IRONCLAD] and cs.player.hand == []
    assert cs.player.discard_pile[0].bonus_damage == 6

def test_thrash_adds_the_damage_with_strength():
    cs = state([thrash(), strike()]); cs.player.apply_status(StatusId.STRENGTH, 2)
    play(cs)
    assert cs.player.discard_pile[0].bonus_damage == 8

def test_thrash_hits_harder_the_next_time():
    cs = state([thrash(), strike()]); cs.energy = 5
    sim = play(cs)
    assert hps(cs) == [92]
    cs.player.hand = [cs.player.discard_pile.pop()]
    sim.play_card(0, 0)
    assert hps(cs) == [92 - 2 * 10]

def test_thrash_ignores_other_cards():
    cs = state([thrash(), defend()])
    play(cs)
    assert ids(cs.player.hand) == [CardId.DEFEND_IRONCLAD] and cs.player.exhaust_pile == []

def test_thrash_with_no_attacks_adds_nothing():
    cs = state([thrash()])
    play(cs)
    assert cs.player.discard_pile[0].bonus_damage == 0

def test_thrash_picks_randomly_between_attacks():
    picked = set()
    for seed in range(30):
        rng.seed(seed)
        cs = state([thrash(), strike(), bash()])
        play(cs)
        picked.add(cs.player.exhaust_pile[0].card_id)
    assert picked == {CardId.STRIKE_IRONCLAD, CardId.BASH}

def test_thrash_with_one_attack_uses_no_rng():
    cs = state([thrash(), strike()])
    before = rng.calls
    play(cs)
    assert rng.calls == before

def test_thrash_uses_the_current_damage_of_special_cards():
    cs = state([thrash(), card(CardId.BODY_SLAM, 1, CardType.Attack, TargetType.AnyEnemy)]); cs.player.block = 11
    play(cs)
    assert cs.player.discard_pile[0].bonus_damage == 11
    cs = state([thrash(), card(CardId.ASHEN_STRIKE, 1, CardType.Attack, TargetType.AnyEnemy)])
    cs.player.exhaust_pile = fresh(2)
    play(cs)
    assert cs.player.discard_pile[0].bonus_damage == 12
    cs = state([thrash(), rampage()]); cs.player.hand[1].bonus_damage = 10
    play(cs)
    assert cs.player.discard_pile[0].bonus_damage == 19

def test_thrash_exhaust_triggers_feel_no_pain_and_does_not_change_the_original():
    original = thrash(); cs = state([original, strike()])
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 3)
    play(cs)
    assert cs.player.block == 3 and original.bonus_damage == 0

def test_thrash_can_take_a_second_thrash():
    other = thrash(); other.bonus_damage = 6
    cs = state([thrash(), other])
    play(cs)
    assert cs.player.discard_pile[0].bonus_damage == 10


# ---------------------------------------------------------------- Stoke
def test_stoke_exhausts_the_hand_and_adds_that_many_cards():
    cs = state([stoke(), strike(), defend(), bash()])
    play(cs)
    assert len(cs.player.exhaust_pile) == 3 and len(cs.player.hand) == 3
    assert all(c.card_id in STOKE_POOL for c in cs.player.hand)

def test_stoke_upgraded_adds_upgraded_cards():
    cs = state([stoke(True), strike(), defend()])
    play(cs)
    assert len(cs.player.hand) == 2 and all(c.is_upgraded for c in cs.player.hand)
    assert all(c.name.endswith("+") for c in cs.player.hand)

def test_stoke_with_an_empty_hand_adds_nothing_and_does_not_exhaust_itself():
    cs = state([stoke()])
    play(cs)
    assert cs.player.hand == [] and ids(cs.player.discard_pile) == [CardId.STOKE]

def test_stoke_does_not_exhaust_itself():
    cs = state([stoke(), strike()])
    play(cs)
    assert CardId.STOKE not in ids(cs.player.exhaust_pile)

def test_stoke_gives_a_variety_of_cards():
    seen = set()
    for seed in range(40):
        rng.seed(seed)
        cs = state([stoke(), strike(), strike(), strike()])
        play(cs)
        seen.update(c.card_id for c in cs.player.hand)
    assert len(seen) > 15

def test_stoke_never_adds_basic_cards_or_cards_that_cannot_be_generated():
    for forbidden in (CardId.STRIKE_IRONCLAD, CardId.DEFEND_IRONCLAD, CardId.BASH, CardId.BREAK, CardId.CORRUPTION,
                      CardId.FEED, CardId.NOT_YET, CardId.GIANT_ROCK):
        assert forbidden not in STOKE_POOL

def test_every_card_stoke_can_add_can_be_played():
    for cid in STOKE_POOL:
        assert cid in GET_CARD_FUNCTION, cid

def test_stoke_triggers_feel_no_pain_for_each_card():
    cs = state([stoke(), strike(), strike()]); cs.player.apply_status(StatusId.FEEL_NO_PAIN, 2)
    play(cs)
    assert cs.player.block == 4

def test_stoke_dark_embrace_draws_stay_in_the_hand_and_are_not_exhausted():
    cs = state([stoke(), strike(), strike()]); cs.player.draw_pile = fresh(6)
    cs.player.apply_status(StatusId.DARK_EMBRACE, 1)
    play(cs)
    assert len(cs.player.exhaust_pile) == 2 and len(cs.player.hand) == 4

def test_stoke_extra_cards_go_to_the_discard_pile_when_the_hand_is_full():
    cs = state([stoke()] + fresh(3)); cs.player.draw_pile = fresh(20)
    cs.player.apply_status(StatusId.DARK_EMBRACE, 3)
    play(cs)
    assert len(cs.player.hand) == 10 and len(cs.player.discard_pile) >= 2

def test_stoke_uses_one_random_choice_per_card():
    cs = state([stoke(), strike(), strike(), strike()])
    before = rng.calls
    play(cs)
    assert rng.calls - before >= 3

def test_a_stomp_added_by_stoke_counts_attacks_already_played():
    cs = state([strike(), stoke(), strike()])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    for seed in range(100):
        rng.seed(seed)
        c = CombatState.deepcopy(cs)
        CombatSimulator(c).play_card(0, 0)
        stomps = [x for x in c.player.hand if x.card_id == CardId.STOMP]
        if stomps:
            assert stomps[0].energy_cost == 2
            return


# ---------------------------------------------------------------- the card pools
def test_infernal_blade_pool_has_only_generable_attacks():
    for forbidden in (CardId.STRIKE_IRONCLAD, CardId.BASH, CardId.BREAK, CardId.FEED, CardId.GIANT_ROCK):
        assert forbidden not in INFERNAL_BLADE_POOL
    for needed in (CardId.MANGLE, CardId.PILLAGE, CardId.RAMPAGE, CardId.SETUP_STRIKE, CardId.STOMP,
                   CardId.TEAR_ASUNDER, CardId.THRASH, CardId.FIEND_FIRE):
        assert needed in INFERNAL_BLADE_POOL
    assert all(GENERATABLE_CARDS[c][1] == CardType.Attack for c in INFERNAL_BLADE_POOL)

def test_the_stoke_pool_has_every_type():
    types = {GENERATABLE_CARDS[c][1] for c in STOKE_POOL}
    assert types == {CardType.Attack, CardType.Skill, CardType.Power}

def test_generated_cards_have_the_right_upgraded_cost():
    assert Card.create_generated(CardId.BARRICADE, True).energy_cost == 2
    assert Card.create_generated(CardId.HELLRAISER, True).energy_cost == 1
    assert Card.create_generated(CardId.BODY_SLAM, True).energy_cost == 0
    assert Card.create_generated(CardId.CASCADE, True).energy_cost == "X"

def test_strike_tag_cards():
    assert STRIKE_CARDS == {CardId.STRIKE_IRONCLAD, CardId.PERFECTED_STRIKE, CardId.POMMEL_STRIKE, CardId.TWIN_STRIKE,
                            CardId.ASHEN_STRIKE, CardId.SETUP_STRIKE}


# ---------------------------------------------------------------- Hellraiser
def test_hellraiser_applies_its_power_once():
    cs = state([hellraiser(), hellraiser()]); cs.energy = 4
    sim = play(cs)
    sim.play_card(0, 0)
    assert st(cs.player, StatusId.HELLRAISER) == 1

def test_hellraiser_costs_two_and_one_upgraded():
    assert card(CardId.HELLRAISER, 2, CardType.Power, TargetType.Self).upgraded_copy().energy_cost == 1

def test_a_drawn_strike_is_played_at_once():
    cs = state([]); cs.player.apply_status(StatusId.HELLRAISER, 1)
    cs.player.draw_pile = [defend(), strike()]
    sim = CombatSimulator(cs)
    cs.player.draw_card()
    assert hps(cs) == [94] and cs.player.hand == [] and ids(cs.player.discard_pile) == [CardId.STRIKE_IRONCLAD]
    assert cs.energy == 3

def test_other_drawn_cards_stay_in_the_hand():
    cs = state([]); cs.player.apply_status(StatusId.HELLRAISER, 1)
    cs.player.draw_pile = [strike(), defend(), bash()]
    sim = CombatSimulator(cs)
    cs.player.draw_cards(2)
    assert ids(cs.player.hand) == [CardId.BASH, CardId.DEFEND_IRONCLAD]

def test_every_strike_card_is_played_when_drawn():
    for cid in STRIKE_CARDS:
        cs = state([]); cs.player.apply_status(StatusId.HELLRAISER, 1)
        cs.player.draw_pile = [Card.create_generated(cid) if cid in GENERATABLE_CARDS else strike()]
        CombatSimulator(cs)
        cs.player.draw_card()
        assert cs.player.hand == [], cid

def test_without_hellraiser_a_drawn_strike_stays():
    cs = state([]); cs.player.draw_pile = [strike()]
    CombatSimulator(cs)
    cs.player.draw_card()
    assert len(cs.player.hand) == 1

def test_hellraiser_plays_strikes_drawn_at_the_start_of_the_turn():
    cs = state([]); cs.player.apply_status(StatusId.HELLRAISER, 1)
    cs.player.draw_pile = [defend(), defend(), defend(), strike(), strike(), defend()]
    sim = CombatSimulator(cs)
    sim._start_player_turn()
    assert hps(cs) == [88] and len(cs.player.hand) == 3 and cs.player.draw_pile[0].card_id == CardId.DEFEND_IRONCLAD

def test_hellraiser_chains_through_pommel_strike():
    cs = state([]); cs.player.apply_status(StatusId.HELLRAISER, 1)
    cs.player.draw_pile = [defend(), strike(), pommel()]
    CombatSimulator(cs)
    cs.player.draw_card()
    assert hps(cs) == [100 - 9 - 6] and cs.player.hand == [] and ids(cs.player.draw_pile) == [CardId.DEFEND_IRONCLAD]

def test_hellraiser_play_triggers_on_play_effects():
    cs = state([]); cs.player.apply_status(StatusId.HELLRAISER, 1)
    cs.player.apply_status(StatusId.RAGE, 3)
    cs.player.draw_pile = [strike()]
    CombatSimulator(cs)
    cs.player.draw_card()
    assert cs.player.block == 3

def test_hellraiser_can_win_the_fight():
    cs = state([], hp=6); cs.player.apply_status(StatusId.HELLRAISER, 1)
    cs.player.draw_pile = [strike()]
    sim = CombatSimulator(cs)
    cs.player.draw_card()
    assert sim.is_over

def test_hellraiser_does_not_play_after_the_fight_is_over():
    cs = state([], hp=6); cs.player.apply_status(StatusId.HELLRAISER, 1)
    cs.player.draw_pile = [strike(), strike()]
    sim = CombatSimulator(cs)
    cs.player.draw_cards(2)
    assert sim.is_over and len(cs.player.hand) == 1

def test_a_state_copy_has_no_draw_hook_until_a_simulator_wraps_it():
    cs = state([]); CombatSimulator(cs)
    assert CombatState.deepcopy(cs).player.draw_hook is None

def test_hellraiser_on_a_copy_works_once_it_is_wrapped():
    cs = state([]); cs.player.apply_status(StatusId.HELLRAISER, 1); cs.player.draw_pile = [strike()]
    copy = CombatState.deepcopy(cs)
    CombatSimulator(copy)
    copy.player.draw_card()
    assert hps(copy) == [94] and hps(cs) == [100]

def test_cascade_taking_a_strike_does_not_trigger_hellraiser():
    cs = state([card(CardId.CASCADE, "X", CardType.Skill, TargetType.Self)]); cs.energy = 1
    cs.player.apply_status(StatusId.HELLRAISER, 1)
    cs.player.draw_pile = [strike()]
    play(cs)
    assert hps(cs) == [94]       # played once by Cascade, not twice


# ---------------------------------------------------------------- Inferno
def test_inferno_gives_six_and_nine_upgraded():
    cs = state([inferno()])
    play(cs)
    assert st(cs.player, StatusId.INFERNO) == 6 and cs.player.inferno_plays == 1
    cs = state([inferno(True)])
    play(cs)
    assert st(cs.player, StatusId.INFERNO) == 9

def test_inferno_stacks_and_costs_more_hp_each_turn():
    cs = state([inferno(), inferno()])
    sim = play(cs)
    sim.play_card(0, 0)
    assert st(cs.player, StatusId.INFERNO) == 12 and cs.player.inferno_plays == 2

def test_inferno_costs_hp_at_the_start_of_each_turn_and_hurts_every_enemy():
    cs = state([], enemies=2); cs.player.apply_status(StatusId.INFERNO, 6); cs.player.inferno_plays = 1
    cs.player.draw_pile = fresh(10)
    CombatSimulator(cs)._start_player_turn()
    assert cs.player.current_hp == 49 and hps(cs) == [94, 94]

def test_two_inferno_plays_cost_two_hp_in_one_loss_that_hurts_once():
    cs = state([]); cs.player.apply_status(StatusId.INFERNO, 12); cs.player.inferno_plays = 2
    cs.player.draw_pile = fresh(10)
    CombatSimulator(cs)._start_player_turn()
    assert cs.player.current_hp == 48 and hps(cs) == [100 - 12]       # one loss of HP, one burst of damage

def test_inferno_hurts_enemies_whenever_a_card_costs_hp():
    cs = state([card(CardId.BLOODLETTING, 0, CardType.Skill, TargetType.Self)], enemies=2)
    cs.player.apply_status(StatusId.INFERNO, 6)
    play(cs)
    assert hps(cs) == [94, 94]

def test_inferno_ignores_damage_from_enemies():
    cs = state([]); cs.player.apply_status(StatusId.INFERNO, 6); cs.player.inferno_plays = 1
    cs.player.draw_pile = fresh(10)
    hit_back(cs, 5)
    CombatSimulator(cs).end_turn()
    # the enemy hit does not count; the loss at the start of the next turn does
    assert hps(cs) == [94]

def test_inferno_ignores_blocked_hits_and_unrelated_turns():
    cs = state([defend()]); cs.player.apply_status(StatusId.INFERNO, 6)
    play(cs)
    assert hps(cs) == [100]

def test_inferno_is_blocked_by_enemy_block_and_ignores_strength():
    cs = state([card(CardId.BLOODLETTING, 0, CardType.Skill, TargetType.Self)])
    cs.player.apply_status(StatusId.INFERNO, 6); cs.player.apply_status(StatusId.STRENGTH, 5)
    cs.enemies[0].block = 4
    play(cs)
    assert hps(cs) == [98]

def test_inferno_can_kill_enemies():
    cs = state([card(CardId.BLOODLETTING, 0, CardType.Skill, TargetType.Self)], hp=5)
    cs.player.apply_status(StatusId.INFERNO, 6)
    sim = play(cs)
    assert sim.is_over

def test_inferno_and_rupture_both_react_to_the_turn_start_loss():
    cs = state([]); cs.player.apply_status(StatusId.INFERNO, 6); cs.player.inferno_plays = 1
    cs.player.apply_status(StatusId.RUPTURE, 1); cs.player.draw_pile = fresh(10)
    CombatSimulator(cs)._start_player_turn()
    assert st(cs.player, StatusId.STRENGTH) == 1

def test_inferno_counts_every_hp_loss_in_one_card():
    cs = state([card(CardId.HEMOKINESIS, 1, CardType.Attack, TargetType.AnyEnemy)])
    cs.player.apply_status(StatusId.INFERNO, 6)
    play(cs)
    assert hps(cs) == [100 - 15 - 6]

def test_inferno_estimate_when_loaded_from_the_game():
    pl = Player.from_dict({"max_hp": 80, "hp": 80, "block": 0, "hand": [], "draw_pile": [], "discard_pile": [],
                           "status": [{"id": "INFERNO_POWER", "amount": 12}]})
    assert pl.inferno_plays == 2
    pl = Player.from_dict({"max_hp": 80, "hp": 80, "block": 0, "hand": [], "draw_pile": [], "discard_pile": [],
                           "status": [{"id": "INFERNO_POWER", "amount": 6}]})
    assert pl.inferno_plays == 1
    pl = Player.from_dict({"max_hp": 80, "hp": 80, "block": 0, "hand": [], "draw_pile": [], "discard_pile": [], "status": []})
    assert pl.inferno_plays == 0

def test_carried_inferno_plays_beat_the_estimate():
    prev = state([]); prev.player.apply_status(StatusId.INFERNO, 15); prev.player.inferno_plays = 3
    new = state([]); new.player.apply_status(StatusId.INFERNO, 15); new.player.inferno_plays = 2
    new.carry_combat_counters(prev)
    assert new.player.inferno_plays == 3

def test_inferno_plays_survive_a_copy_of_the_state():
    cs = state([]); cs.player.inferno_plays = 4
    assert CombatState.deepcopy(cs).player.inferno_plays == 4


# ---------------------------------------------------------------- loading from the bridge
def bridge_player(hand, status=()):
    return {"max_hp": 80, "hp": 80, "block": 0, "hand": hand, "draw_pile": [], "discard_pile": [],
            "status": [{"id": s, "amount": a} for s, a in status]}

def bridge_card(card_id, description, cost="1", typ="Attack", up=False):
    return {"id": card_id, "type": typ, "name": card_id, "can_play": True, "cost": cost, "is_upgraded": up,
            "target_type": "AnyEnemy", "description": description}

def test_new_status_ids_load():
    for name, status in (("SETUP_STRIKE_POWER", StatusId.SETUP_STRIKE), ("MANGLE_POWER", StatusId.MANGLE),
                         ("HELLRAISER_POWER", StatusId.HELLRAISER), ("INFERNO_POWER", StatusId.INFERNO)):
        assert StatusInstance.from_dict({"id": name, "amount": 3}).status_id == status

def test_all_the_new_cards_load():
    for name in ("BRAND", "GIANT_ROCK", "HELLRAISER", "INFERNO", "MANGLE", "PILLAGE", "PRIMAL_FORCE", "RAMPAGE",
                 "SETUP_STRIKE", "STOKE", "STOMP", "TEAR_ASUNDER", "THRASH"):
        assert Card.from_dict(bridge_card(name, "Deal 5 damage.")).card_id == CardId[name]

def test_a_loaded_rampage_reads_its_growth_from_the_text():
    pl = Player.from_dict(bridge_player([bridge_card("RAMPAGE", "Deal 14 damage.")]))
    assert pl.hand[0].bonus_damage == 5
    pl = Player.from_dict(bridge_player([bridge_card("RAMPAGE", "Deal 9 damage.")]))
    assert pl.hand[0].bonus_damage == 0
    pl = Player.from_dict(bridge_player([bridge_card("RAMPAGE", "Deal 24 damage.")]))
    assert pl.hand[0].bonus_damage == 15

def test_an_upgraded_loaded_rampage_grows_by_nine():
    pl = Player.from_dict(bridge_player([bridge_card("RAMPAGE", "Deal 18 damage.", up=True)]))
    assert pl.hand[0].bonus_damage == 9

def test_loaded_rampage_text_includes_strength_which_is_taken_back_out():
    pl = Player.from_dict(bridge_player([bridge_card("RAMPAGE", "Deal 17 damage.")], [("STRENGTH_POWER", 3)]))
    assert pl.hand[0].bonus_damage == 5

def test_loaded_rampage_text_includes_weak_which_is_taken_back_out():
    pl = Player.from_dict(bridge_player([bridge_card("RAMPAGE", "Deal 10 damage.")], [("WEAK_POWER", 1)]))
    assert pl.hand[0].bonus_damage == 5

def test_cards_in_other_piles_are_read_as_printed():
    d = bridge_player([], [("STRENGTH_POWER", 3)])
    d["discard_pile"] = [bridge_card("RAMPAGE", "Deal 14 damage.")]
    d["draw_pile"] = [bridge_card("THRASH", "Deal 10 damage.")]
    pl = Player.from_dict(d)
    assert pl.discard_pile[0].bonus_damage == 5 and pl.draw_pile[0].bonus_damage == 6

def test_a_loaded_thrash_reads_its_growth():
    pl = Player.from_dict(bridge_player([bridge_card("THRASH", "Deal 4 damage.")]))
    assert pl.hand[0].bonus_damage == 0
    pl = Player.from_dict(bridge_player([bridge_card("THRASH", "Deal 11 damage.")]))
    assert pl.hand[0].bonus_damage == 7
    pl = Player.from_dict(bridge_player([bridge_card("THRASH", "Deal 11 damage.", up=True)]))
    assert pl.hand[0].bonus_damage == 5

def test_a_card_without_a_description_loads_with_no_growth():
    c = bridge_card("RAMPAGE", None)
    del c["description"]
    pl = Player.from_dict(bridge_player([c]))
    assert pl.hand[0].bonus_damage == 0

def test_other_cards_get_no_growth_from_their_text():
    pl = Player.from_dict(bridge_player([bridge_card("STRIKE_IRONCLAD", "Deal 16 damage.")]))
    assert pl.hand[0].bonus_damage == 0


# ---------------------------------------------------------------- mutation survivors
def test_setup_strike_strength_goes_even_through_artifact():
    cs = state([setup_strike()]); cs.player.draw_pile = fresh(10)
    cs.player.apply_status(StatusId.ARTIFACT, 1)
    sim = play(cs)
    assert st(cs.player, StatusId.STRENGTH) == 2
    sim.end_turn()
    assert st(cs.player, StatusId.STRENGTH) == 0 and st(cs.player, StatusId.ARTIFACT) == 1

def test_inferno_estimate_rounds_to_the_nearest_play():
    pl = Player.from_dict({"max_hp": 80, "hp": 80, "block": 0, "hand": [], "draw_pile": [], "discard_pile": [],
                           "status": [{"id": "INFERNO_POWER", "amount": 22}]})
    assert pl.inferno_plays == 3

def test_loaded_rampage_growth_rounds_to_the_nearest_step():
    pl = Player.from_dict(bridge_player([bridge_card("RAMPAGE", "Deal 17 damage.")]))
    assert pl.hand[0].bonus_damage == 10

def test_a_loaded_stomp_costing_two_remembers_its_full_cost():
    c = Card.from_dict({"id": "STOMP", "type": "Attack", "name": "Stomp", "can_play": True, "cost": "2",
                        "is_upgraded": False, "target_type": "AllEnemies", "description": "Deal 12 damage."})
    assert c.energy_cost == 2 and c.restore_cost == 3

def test_thrash_adds_the_printed_damage_of_an_upgraded_thrash():
    cs = state([thrash(), thrash(True)])
    play(cs)
    assert cs.player.discard_pile[0].bonus_damage == 6
