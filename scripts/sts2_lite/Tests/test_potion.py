import json
import pytest
from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType, STRIKE_CARDS, JACK_POOL, TRANSFORM_COLORLESS, CARD_RARITY, CardRarity, COLORLESS_CARDS
from sts2_lite.combat import CombatState, CombatSimulator, IllegalActionError
from sts2_lite.player import Player
from sts2_lite.potion import Potion, PotionId, PotionRarity, POTION_INFO, EFFECTS, usable_potion_actions, use_potion, RANDOM_POTION_POOL
from sts2_lite.state_key import state_key
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_card, make_state, make_enemy
from sts2_lite.Tests.card.test_powers import strike, defend, skill, power, one_enemy
from sts2_lite.relic import RelicId, RelicInstance
from pathlib import Path


def holding(cs, *potions):
    cs.player.potions = [Potion(p, i) for i, p in enumerate(potions)]
    return cs

def drink(cs, potion=None, target=0, slot=0):
    """Use the potion in `slot` (the first one by default) at enemy `target`."""
    sim = CombatSimulator(cs)
    sim.perform_action({"action" : "use_potion", "slot" : slot, "target" : target})
    return sim

def solo(potion, hand=None, hp=100):
    return holding(one_enemy(hand if hand is not None else [strike(), defend()], hp), potion)

def hand_ids(cs):
    return [c.card_id for c in cs.player.hand]

def zero_cost(card):
    return card.energy_cost == 0


# ---------------------------------------------------------------- the list
def test_every_potion_is_described_and_has_an_effect():
    assert set(EFFECTS) == set(PotionId) == set(POTION_INFO)

def test_the_list_is_the_wikis_ironclad_list():
    counts = {r: sum(1 for p in PotionId if p.rarity == r) for r in PotionRarity}
    assert counts == {PotionRarity.COMMON : 16, PotionRarity.UNCOMMON : 16, PotionRarity.RARE : 16, PotionRarity.SPECIAL : 4}
    assert len(PotionId) == 52

@pytest.mark.parametrize("game_id, expected", [
    ("FAIRY_IN_A_BOTTLE", PotionId.FAIRY_IN_A_BOTTLE), ("fairy_in_a_bottle", PotionId.FAIRY_IN_A_BOTTLE), ("REGEN_POTION", PotionId.REGEN_POTION),
    ("GAMBLERS_BREW", PotionId.GAMBLERS_BREW), ("GAMBLER_S_BREW", PotionId.GAMBLERS_BREW), ("SOLDIERS_STEW", PotionId.SOLDIERS_STEW),
    ("POTION_SHAPED_ROCK", PotionId.POTION_SHAPED_ROCK), ("MAZALETHS_GIFT", PotionId.MAZALETHS_GIFT)])
def test_game_ids_are_recognised(game_id, expected):
    assert PotionId.from_game_id(game_id) is expected

def test_another_characters_potion_is_not_known():
    assert PotionId.from_game_id("POISON_POTION") is None and PotionId.from_game_id("") is None

def test_only_fairy_in_a_bottle_works_by_itself():
    assert [p for p in PotionId if not p.info.combat_usable] == [PotionId.FAIRY_IN_A_BOTTLE]

def test_targets_follow_the_wiki():
    assert {p for p in PotionId if p.info.target == TargetType.AnyEnemy} == {
        PotionId.FIRE_POTION, PotionId.VULNERABLE_POTION, PotionId.WEAK_POTION, PotionId.POWDERED_DEMISE, PotionId.BEETLE_JUICE, PotionId.POTION_SHAPED_ROCK}


# ---------------------------------------------------------------- loading and actions
def player_dict(potions):
    cs = make_state([strike()])
    d = {"max_hp" : 50, "hp" : 50, "block" : 0, "status" : [], "hand" : [], "draw_pile" : [], "discard_pile" : [], "potions" : potions}
    return d

def test_potions_load_with_their_slots_and_unknown_ones_are_left_out():
    p = Player.from_dict(player_dict([{"id" : "FIRE_POTION", "slot" : 0}, {"id" : "POISON_POTION", "slot" : 1}, {"id" : "REGEN_POTION", "slot" : 2}]))
    assert [(x.potion_id, x.slot) for x in p.potions] == [(PotionId.FIRE_POTION, 0), (PotionId.REGEN_POTION, 2)]
    assert p.potion_slots >= 3

def test_a_state_without_potions_loads():
    assert Player.from_dict(player_dict([])).potions == []

def test_every_potion_is_an_action_with_a_target_where_one_is_needed():
    cs = make_state([], enemy_count=2)
    holding(cs, PotionId.FIRE_POTION, PotionId.BLOCK_POTION)
    actions = [a for a in CombatSimulator(cs).get_available_actions() if a["action"] == "use_potion"]
    assert [(a["slot"], a["potion_id"], a["target"]) for a in actions] == [(0, "FIRE_POTION", 0), (0, "FIRE_POTION", 1), (1, "BLOCK_POTION", 0)]
    assert actions[0]["target_name"] == "E0"

def test_a_dead_enemy_is_not_a_target():
    cs = holding(make_state([], enemy_count=2), PotionId.FIRE_POTION)
    cs.enemies[0].current_hp = 0
    assert [a["target"] for a in usable_potion_actions(CombatSimulator(cs))] == [1]

def test_fairy_in_a_bottle_cannot_be_used():
    cs = holding(make_state([]), PotionId.FAIRY_IN_A_BOTTLE)
    assert usable_potion_actions(CombatSimulator(cs)) == []
    with pytest.raises(IllegalActionError):
        drink(cs)

def test_no_potion_while_a_card_choice_waits():
    cs = holding(one_enemy([skill(CardId.WISH, 0)]), PotionId.BLOCK_POTION)
    cs.player.hand = [strike(), defend()]
    CombatSimulator(cs).request_choice("exhaust_any", [0, 1], "hand", 2)
    actions = CombatSimulator(cs).get_available_actions()
    assert not any(a["action"] == "use_potion" for a in actions)
    with pytest.raises(IllegalActionError):
        drink(cs)

def test_a_missing_slot_or_target_is_refused():
    cs = solo(PotionId.FIRE_POTION)
    with pytest.raises(IllegalActionError):
        drink(cs, slot=2)
    cs.enemies[0].current_hp = 0
    with pytest.raises(IllegalActionError):
        drink(cs)

def test_using_a_potion_uses_it_up_and_costs_no_energy():
    cs = solo(PotionId.BLOCK_POTION)
    drink(cs)
    assert cs.player.potions == [] and cs.energy == 3

def test_the_slot_stays_when_another_potion_goes():
    cs = holding(one_enemy([]), PotionId.BLOCK_POTION, PotionId.ENERGY_POTION)
    drink(cs, slot=0)
    assert [(p.potion_id, p.slot) for p in cs.player.potions] == [(PotionId.ENERGY_POTION, 1)]
    drink(cs, slot=1)
    assert cs.energy == 5

def test_potions_are_part_of_the_state_key():
    a = solo(PotionId.BLOCK_POTION)
    b = CombatState.deepcopy(a)
    assert state_key(a) == state_key(b)
    b.player.potions = []
    assert state_key(a) != state_key(b)
    c = CombatState.deepcopy(a)
    c.player.potions = [Potion(PotionId.ENERGY_POTION, 0)]
    assert state_key(a) != state_key(c)

def test_deepcopy_keeps_the_potions():
    a = solo(PotionId.BLOCK_POTION)
    b = CombatState.deepcopy(a)
    drink(b)
    assert len(a.player.potions) == 1 and b.player.potions == []


# ---------------------------------------------------------------- simple effects
def test_block_potion():
    cs = solo(PotionId.BLOCK_POTION); drink(cs)
    assert cs.player.block == 12

def test_block_potion_ignores_dexterity_and_frail():
    cs = solo(PotionId.BLOCK_POTION)
    cs.player.apply_status(StatusId.DEXTERITY, 5); cs.player.apply_status(StatusId.FRAIL, 2)
    drink(cs)
    assert cs.player.block == 12

def test_energy_swift_and_cure_all():
    cs = solo(PotionId.ENERGY_POTION); drink(cs)
    assert cs.energy == 5
    cs = solo(PotionId.SWIFT_POTION, hand=[]); cs.player.draw_pile = [strike() for _ in range(5)]; drink(cs)
    assert len(cs.player.hand) == 3
    cs = solo(PotionId.CURE_ALL, hand=[]); cs.player.draw_pile = [strike() for _ in range(5)]; drink(cs)
    assert cs.energy == 4 and len(cs.player.hand) == 2

@pytest.mark.parametrize("potion, status, amount", [
    (PotionId.STRENGTH_POTION, StatusId.STRENGTH, 2), (PotionId.DEXTERITY_POTION, StatusId.DEXTERITY, 2),
    (PotionId.REGEN_POTION, StatusId.REGEN, 5), (PotionId.HEART_OF_IRON, StatusId.PLATING, 7), (PotionId.LIQUID_BRONZE, StatusId.THORNS, 3),
    (PotionId.LUCKY_TONIC, StatusId.BUFFER, 1), (PotionId.MAZALETHS_GIFT, StatusId.RITUAL, 1), (PotionId.DUPLICATOR, StatusId.DUPLICATION, 1),
    (PotionId.GIGANTIFICATION_POTION, StatusId.GIGANTIFICATION, 1), (PotionId.STABLE_SERUM, StatusId.RETAIN_HAND, 2)])
def test_potions_that_give_the_player_a_status(potion, status, amount):
    cs = solo(potion); drink(cs)
    assert cs.player.status_amount(status) == amount

def test_fysh_oil_gives_both():
    cs = solo(PotionId.FYSH_OIL); drink(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == 1 and cs.player.status_amount(StatusId.DEXTERITY) == 1

def test_fire_potion_and_the_rock_do_flat_damage():
    cs = holding(make_state([], enemy_count=2), PotionId.FIRE_POTION); drink(cs, target=1)
    assert [e.current_hp for e in cs.enemies] == [40, 20]
    cs = holding(make_state([]), PotionId.POTION_SHAPED_ROCK); cs.player.apply_status(StatusId.STRENGTH, 5); cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    drink(cs)
    assert cs.enemies[0].current_hp == 25           # neither Strength nor Vulnerable (assumed)

def test_explosive_ampoule_hits_every_enemy():
    cs = holding(make_state([], enemy_count=3), PotionId.EXPLOSIVE_AMPOULE); drink(cs)
    assert [e.current_hp for e in cs.enemies] == [30, 30, 30]

def test_damage_from_a_potion_can_end_the_fight():
    cs = holding(one_enemy([], hp=15), PotionId.FIRE_POTION)
    sim = drink(cs)
    assert sim.is_over and not cs.enemies

def test_foul_potion_hurts_everyone_the_player_too():
    cs = holding(make_state([], enemy_count=2), PotionId.FOUL_POTION); drink(cs)
    assert [e.current_hp for e in cs.enemies] == [28, 28] and cs.player.current_hp == 38

def test_foul_potion_can_kill_the_player():
    cs = holding(one_enemy([]), PotionId.FOUL_POTION); cs.player.current_hp = 10
    sim = drink(cs)
    assert sim.is_over and cs.player.current_hp <= 0

def test_vulnerable_and_weak_potions():
    cs = holding(make_state([], enemy_count=2), PotionId.VULNERABLE_POTION); drink(cs, target=1)
    assert [e.status_amount(StatusId.VULNERABLE) for e in cs.enemies] == [0, 3]
    cs = holding(one_enemy([]), PotionId.WEAK_POTION); drink(cs)
    assert cs.enemies[0].status_amount(StatusId.WEAK) == 3

def test_artifact_stops_a_debuff_potion():
    cs = holding(one_enemy([]), PotionId.WEAK_POTION); cs.enemies[0].apply_status(StatusId.ARTIFACT, 1)
    drink(cs)
    assert cs.enemies[0].status_amount(StatusId.WEAK) == 0

def test_potion_of_binding_hits_all_enemies():
    cs = holding(make_state([], enemy_count=2), PotionId.POTION_OF_BINDING); drink(cs)
    assert all(e.status_amount(StatusId.WEAK) == 1 and e.status_amount(StatusId.VULNERABLE) == 1 for e in cs.enemies)

def test_beetle_juice_cuts_the_enemys_attacks_by_30_percent():
    cs = holding(one_enemy([]), PotionId.BEETLE_JUICE); drink(cs)
    enemy = cs.enemies[0]
    assert enemy.status_amount(StatusId.SHRINK) == 4
    assert cs.player.current_hp == 50
    from sts2_lite.damage import modify_damage
    assert modify_damage(10, enemy, cs.player) == 7

def test_blood_potion_heals_a_fifth_of_max_hp_and_not_past_it():
    cs = solo(PotionId.BLOOD_POTION); cs.player.current_hp = 20; drink(cs)
    assert cs.player.current_hp == 30
    cs = solo(PotionId.BLOOD_POTION); cs.player.current_hp = 45; drink(cs)
    assert cs.player.current_hp == 50

def test_fruit_juice_raises_max_hp_and_hp():
    cs = solo(PotionId.FRUIT_JUICE); cs.player.current_hp = 30; drink(cs)
    assert cs.player.max_hp == 55 and cs.player.current_hp == 35

def test_fortifier_triples_the_block():
    cs = solo(PotionId.FORTIFIER); cs.player.block = 7; drink(cs)
    assert cs.player.block == 21

def test_ship_in_a_bottle_gives_block_now_and_next_turn():
    cs = solo(PotionId.SHIP_IN_A_BOTTLE); drink(cs)
    assert cs.player.block == 10
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 10


# ---------------------------------------------------------------- temporary Strength and Dexterity
def test_flex_potion_strength_is_lost_at_the_end_of_the_turn():
    cs = solo(PotionId.FLEX_POTION); drink(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == 5
    CombatSimulator(cs).end_turn()
    assert cs.player.status_amount(StatusId.STRENGTH) == 0 and StatusId.FLEX_POTION not in cs.player.status

def test_speed_potion_dexterity_is_lost_at_the_end_of_the_turn():
    cs = solo(PotionId.SPEED_POTION); drink(cs)
    assert cs.player.status_amount(StatusId.DEXTERITY) == 5
    CombatSimulator(cs).end_turn()
    assert cs.player.status_amount(StatusId.DEXTERITY) == 0

def test_shackling_potion_takes_enemy_strength_for_the_turn():
    cs = holding(make_state([], enemy_count=2), PotionId.SHACKLING_POTION)
    for e in cs.enemies: e.apply_status(StatusId.STRENGTH, 3)
    drink(cs)
    assert [e.status_amount(StatusId.STRENGTH) for e in cs.enemies] == [-4, -4]
    CombatSimulator(cs).end_turn()
    assert [e.status_amount(StatusId.STRENGTH) for e in cs.enemies] == [3, 3]


# ---------------------------------------------------------------- statuses
def test_regen_heals_at_the_end_of_the_turn_and_wears_off():
    cs = solo(PotionId.REGEN_POTION); cs.player.current_hp = 30; drink(cs)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.player.current_hp == 35 and cs.player.status_amount(StatusId.REGEN) == 4
    for expected in (39, 42, 44, 45):
        sim.end_turn()
        assert cs.player.current_hp == expected
    assert StatusId.REGEN not in cs.player.status

def test_regen_does_not_pass_max_hp():
    cs = solo(PotionId.REGEN_POTION); cs.player.current_hp = 48; drink(cs)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 50

def test_powdered_demise_costs_the_enemy_hp_each_of_its_turns_through_block():
    cs = holding(make_state([], enemy_count=2), PotionId.POWDERED_DEMISE); cs.enemies[1].block = 50
    drink(cs, target=1)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert [e.current_hp for e in cs.enemies] == [40, 31]
    sim.end_turn()
    assert cs.enemies[1].current_hp == 22

def test_powdered_demise_can_kill():
    cs = holding(make_state([], enemy_count=2, enemy_hp=9), PotionId.POWDERED_DEMISE)
    drink(cs, target=0)
    CombatSimulator(cs).end_turn()
    assert len(cs.enemies) == 1

def test_demise_is_a_debuff_so_artifact_stops_it():
    cs = holding(one_enemy([]), PotionId.POWDERED_DEMISE); cs.enemies[0].apply_status(StatusId.ARTIFACT, 1)
    drink(cs)
    assert StatusId.DEMISE not in cs.enemies[0].status

def test_buffer_blocks_the_next_hp_loss_only():
    cs = solo(PotionId.LUCKY_TONIC); drink(cs)
    cs.player.apply_damage(8, cs.enemies[0], True)
    assert cs.player.current_hp == 50 and StatusId.BUFFER not in cs.player.status
    cs.player.apply_damage(8, cs.enemies[0], True)
    assert cs.player.current_hp == 42

def test_buffer_is_not_spent_by_damage_that_block_stops():
    cs = solo(PotionId.LUCKY_TONIC); drink(cs); cs.player.block = 10
    cs.player.apply_damage(8, cs.enemies[0], True)
    assert cs.player.status_amount(StatusId.BUFFER) == 1

def test_mazaleths_gift_gives_strength_at_the_end_of_each_of_the_players_turns():
    cs = solo(PotionId.MAZALETHS_GIFT); drink(cs)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.player.status_amount(StatusId.STRENGTH) == 1
    sim.end_turn()
    assert cs.player.status_amount(StatusId.STRENGTH) == 2

def test_an_enemys_ritual_still_works_as_before():
    cs = one_enemy([]); cs.enemies[0].apply_status(StatusId.RITUAL, 2)
    sim = CombatSimulator(cs)
    sim.end_turn(); sim.end_turn()
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 4 and cs.player.status_amount(StatusId.STRENGTH) == 0

def test_stable_serum_keeps_the_hand_for_two_turns():
    cs = solo(PotionId.STABLE_SERUM, hand=[strike(), defend()]); drink(cs)
    cs.player.draw_pile = []
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert len(cs.player.hand) >= 2
    sim.end_turn()
    assert StatusId.RETAIN_HAND not in cs.player.status

def test_heart_of_iron_plating_gives_block_at_the_end_of_the_turn():
    cs = solo(PotionId.HEART_OF_IRON); drink(cs)
    CombatSimulator(cs).end_turn()
    assert cs.player.status_amount(StatusId.PLATING) in (6, 7)

def test_gigantification_triples_only_the_next_attack():
    cs = solo(PotionId.GIGANTIFICATION_POTION, hand=[strike(), strike()]); drink(cs)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - 18 and StatusId.GIGANTIFICATION not in cs.player.status
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - 18 - 6

def test_gigantification_waits_through_a_skill():
    cs = solo(PotionId.GIGANTIFICATION_POTION, hand=[defend(), strike()]); drink(cs)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.GIGANTIFICATION) == 1
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 82

def test_duplicator_plays_the_next_card_twice_once():
    cs = solo(PotionId.DUPLICATOR, hand=[strike(), strike()]); drink(cs)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 88
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 82

def test_duplicator_goes_when_the_turn_ends():
    cs = solo(PotionId.DUPLICATOR); drink(cs)
    CombatSimulator(cs).end_turn()
    assert StatusId.DUPLICATION not in cs.player.status

def test_clarity_extract_draws_one_now_and_one_more_for_three_turns():
    cs = solo(PotionId.CLARITY_EXTRACT, hand=[]); cs.player.draw_pile = [strike() for _ in range(40)]; drink(cs)
    assert len(cs.player.hand) == 1
    sim = CombatSimulator(cs)
    sizes = []
    for _ in range(4):
        sim.end_turn()
        sizes.append(len(cs.player.hand))
    assert sizes == [6, 6, 6, 5]

def test_radiant_tincture_gives_energy_now_and_for_three_turns():
    cs = solo(PotionId.RADIANT_TINCTURE); drink(cs)
    assert cs.energy == 4
    sim = CombatSimulator(cs)
    energies = []
    for _ in range(4):
        sim.end_turn()
        energies.append(cs.energy)
    assert energies == [4, 4, 4, 3]

def test_ambergris_heals_half_and_takes_an_extra_turn():
    cs = solo(PotionId.AMBERGRIS); cs.player.current_hp = 10; drink(cs)
    assert cs.player.current_hp == 35
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 10, 1
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 35 and cs.extra_turns == 1 and not cs.player.extra_turn_pending
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp < 35


# ---------------------------------------------------------------- Fairy in a Bottle
def test_fairy_revives_to_30_percent_and_is_used_up():
    cs = holding(one_enemy([]), PotionId.FAIRY_IN_A_BOTTLE)
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 80, 1
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 15 and cs.player.potions == []

def test_without_fairy_the_same_hit_kills():
    cs = one_enemy([])
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 80, 1
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert sim.is_over and cs.player.current_hp <= 0

def test_fairy_saves_from_the_players_own_potion():
    cs = holding(one_enemy([]), PotionId.FOUL_POTION, PotionId.FAIRY_IN_A_BOTTLE); cs.player.current_hp = 5
    drink(cs, slot=0)
    assert cs.player.current_hp == 15 and cs.player.potions == []

def test_fairy_works_with_other_potions_held():
    cs = holding(one_enemy([]), PotionId.BLOCK_POTION, PotionId.FAIRY_IN_A_BOTTLE)
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 80, 1
    CombatSimulator(cs).end_turn()
    assert [p.potion_id for p in cs.player.potions] == [PotionId.BLOCK_POTION]


# ---------------------------------------------------------------- cards in and out
def test_attack_skill_and_power_potions_offer_three_of_their_type_free_this_turn():
    for potion, kind in ((PotionId.ATTACK_POTION, CardType.Attack), (PotionId.SKILL_POTION, CardType.Skill), (PotionId.POWER_POTION, CardType.Power)):
        rng.seed(1)
        cs = solo(potion, hand=[]); drink(cs)
        choice = cs.pending_choice
        assert choice is not None and choice.kind == "discover" and len(choice.offers) == 3
        assert len({c.card_id for c in choice.offers}) == 3 and all(c.type == kind for c in choice.offers)
        CombatSimulator(cs).choose_card(0)
        assert len(cs.player.hand) == 1 and zero_cost(cs.player.hand[0])

def test_colorless_potion_offers_colorless_cards():
    from sts2_lite.card import COLORLESS_CARDS
    cs = solo(PotionId.COLORLESS_POTION, hand=[]); drink(cs)
    assert all(c.card_id in COLORLESS_CARDS for c in cs.pending_choice.offers) and len(cs.pending_choice.offers) == 3

def test_orobic_acid_adds_an_attack_a_skill_and_a_power_for_free():
    cs = solo(PotionId.OROBIC_ACID, hand=[]); drink(cs)
    assert sorted(c.type.name for c in cs.player.hand) == ["Attack", "Power", "Skill"] and all(zero_cost(c) for c in cs.player.hand)

def test_a_generated_card_costs_its_price_again_next_turn():
    cs = solo(PotionId.OROBIC_ACID, hand=[]); drink(cs)
    costs = {c.card_id: c.energy_cost for c in cs.player.hand}
    CombatSimulator(cs).end_turn()
    for c in cs.player.discard_pile + cs.player.draw_pile + cs.player.hand:
        if c.card_id in costs:
            assert c.energy_cost == Card.create_generated(c.card_id).energy_cost

def test_blessing_of_the_forge_upgrades_the_hand():
    cs = solo(PotionId.BLESSING_OF_THE_FORGE, hand=[strike(), defend()]); cs.player.draw_pile = [strike()]
    drink(cs)
    assert all(c.is_upgraded for c in cs.player.hand) and not cs.player.draw_pile[0].is_upgraded

def test_ashwater_exhausts_any_number_of_cards():
    cs = solo(PotionId.ASHWATER, hand=[strike(), defend(), skill(CardId.SHRUG_IT_OFF)]); drink(cs)
    sim = CombatSimulator(cs)
    pick = [a for a in sim.get_available_actions() if a["action"] == "choose_card"]
    assert pick and any(a["action"] == "confirm_choice" for a in sim.get_available_actions())
    sim.perform_action(pick[0])
    sim.perform_action({"action" : "confirm_choice"})
    assert len(cs.player.exhaust_pile) == 1 and cs.pending_choice is None

def test_ashwater_can_exhaust_the_whole_hand():
    cs = solo(PotionId.ASHWATER, hand=[strike(), defend()]); drink(cs)
    sim = CombatSimulator(cs)
    while cs.pending_choice is not None:
        sim.perform_action([a for a in sim.get_available_actions() if a["action"] == "choose_card"][0])
    assert cs.player.hand == [] and len(cs.player.exhaust_pile) == 2

def test_glowwater_exhausts_the_hand_and_draws_ten():
    cs = solo(PotionId.GLOWWATER_POTION, hand=[strike(), defend()]); cs.player.draw_pile = [strike() for _ in range(12)]
    drink(cs)
    assert len(cs.player.exhaust_pile) == 2 and len(cs.player.hand) == 10

def test_glowwater_triggers_feel_no_pain():
    cs = solo(PotionId.GLOWWATER_POTION, hand=[strike(), defend()]); cs.player.apply_status(StatusId.FEEL_NO_PAIN, 3)
    drink(cs)
    assert cs.player.block == 6

def test_swift_potion_stops_at_a_full_hand():
    cs = solo(PotionId.SWIFT_POTION, hand=[strike() for _ in range(9)]); cs.player.draw_pile = [strike() for _ in range(5)]
    drink(cs)
    assert len(cs.player.hand) == 10

def test_gamblers_brew_draws_as_many_as_were_discarded():
    cs = solo(PotionId.GAMBLERS_BREW, hand=[strike(), strike(), defend()]); cs.player.draw_pile = [skill(CardId.SHRUG_IT_OFF) for _ in range(5)]
    drink(cs)
    sim = CombatSimulator(cs)
    sim.perform_action([a for a in sim.get_available_actions() if a["action"] == "choose_card"][0])
    sim.perform_action([a for a in sim.get_available_actions() if a["action"] == "choose_card"][0])
    assert cs.pending_choice is not None and len(cs.player.hand) == 1
    sim.perform_action({"action" : "confirm_choice"})
    assert cs.pending_choice is None and len(cs.player.discard_pile) == 2 and len(cs.player.hand) == 3

def test_gamblers_brew_may_discard_nothing():
    cs = solo(PotionId.GAMBLERS_BREW, hand=[strike(), defend()]); drink(cs)
    CombatSimulator(cs).perform_action({"action" : "confirm_choice"})
    assert len(cs.player.hand) == 2 and cs.player.discard_pile == []

def test_gamblers_brew_discarding_the_whole_hand_draws_it_back():
    cs = solo(PotionId.GAMBLERS_BREW, hand=[strike(), defend()]); cs.player.draw_pile = [skill(CardId.SHRUG_IT_OFF) for _ in range(5)]
    drink(cs)
    sim = CombatSimulator(cs)
    while cs.pending_choice is not None:
        sim.perform_action([a for a in sim.get_available_actions() if a["action"] == "choose_card"][0])
    assert len(cs.player.hand) == 2 and all(c.card_id == CardId.SHRUG_IT_OFF for c in cs.player.hand)

def test_touch_of_insanity_makes_the_chosen_card_free_for_the_combat():
    cs = solo(PotionId.TOUCH_OF_INSANITY, hand=[skill(CardId.BARRICADE, 3), strike()]); drink(cs)
    CombatSimulator(cs).choose_card(0)
    assert cs.player.hand[0].energy_cost == 0
    CombatSimulator(cs).end_turn()
    every = cs.player.hand + cs.player.draw_pile + cs.player.discard_pile
    assert [c.energy_cost for c in every if c.card_id == CardId.BARRICADE] == [0]

def test_liquid_memories_returns_a_discarded_card_for_free_this_turn():
    cs = solo(PotionId.LIQUID_MEMORIES, hand=[]); cs.player.discard_pile = [skill(CardId.BARRICADE, 3), strike()]; drink(cs)
    sim = CombatSimulator(cs)
    pick = [a for a in sim.get_available_actions() if a["action"] == "choose_card" and a["card_id"] == "BARRICADE"][0]
    sim.perform_action(pick)
    assert hand_ids(cs) == [CardId.BARRICADE] and cs.player.hand[0].energy_cost == 0 and len(cs.player.discard_pile) == 1

def test_liquid_memories_with_an_empty_discard_does_nothing():
    cs = solo(PotionId.LIQUID_MEMORIES, hand=[]); drink(cs)
    assert cs.pending_choice is None and cs.player.potions == []

def test_droplet_of_precognition_takes_a_card_from_the_draw_pile():
    cs = solo(PotionId.DROPLET_OF_PRECOGNITION, hand=[]); cs.player.draw_pile = [strike(), skill(CardId.BARRICADE, 3), defend()]; drink(cs)
    sim = CombatSimulator(cs)
    sim.perform_action([a for a in sim.get_available_actions() if a["action"] == "choose_card" and a["card_id"] == "BARRICADE"][0])
    assert hand_ids(cs) == [CardId.BARRICADE] and len(cs.player.draw_pile) == 2

def test_bottled_potential_shuffles_everything_in_and_draws_five():
    cs = solo(PotionId.BOTTLED_POTENTIAL, hand=[strike(), defend()]); cs.player.discard_pile = [strike() for _ in range(6)]
    cs.player.draw_pile = [defend() for _ in range(4)]; cs.player.exhaust_pile = [strike()]
    drink(cs)
    p = cs.player
    assert len(p.hand) == 5 and len(p.draw_pile) == 7 and p.discard_pile == [] and len(p.exhaust_pile) == 1

def test_distilled_chaos_plays_the_top_three_cards():
    cs = holding(make_state([], enemy_count=1, enemy_hp=100), PotionId.DISTILLED_CHAOS)
    cs.player.draw_pile = [defend(), strike(), strike(), strike()]
    cs.player.known_top = 0
    drink(cs)
    assert len(cs.player.draw_pile) == 1 and cs.player.block + (100 - cs.enemies[0].current_hp) > 0

def test_snecko_oil_draws_seven_and_randomises_costs_for_this_turn():
    rng.seed(3)
    cs = solo(PotionId.SNECKO_OIL, hand=[skill(CardId.BARRICADE, 3)]); cs.player.draw_pile = [strike() for _ in range(10)]
    drink(cs)
    assert len(cs.player.hand) == 8
    assert all(0 <= c.energy_cost <= 3 for c in cs.player.hand)
    CombatSimulator(cs).end_turn()
    barricade = [c for c in cs.player.hand + cs.player.discard_pile + cs.player.draw_pile if c.card_id == CardId.BARRICADE]
    assert [c.energy_cost for c in barricade] == [3]

def test_soldiers_stew_gives_every_strike_a_replay():
    cs = solo(PotionId.SOLDIERS_STEW, hand=[strike(), defend()])
    cs.player.draw_pile = [strike()]; cs.player.discard_pile = [strike()]
    drink(cs)
    assert all(c.replay == 1 for c in cs.player.hand + cs.player.draw_pile + cs.player.discard_pile if c.card_id in STRIKE_CARDS)
    assert all(c.replay == 0 for c in cs.player.hand if c.card_id == CardId.DEFEND_IRONCLAD)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 88           # twice

def test_soldiers_stew_does_not_change_the_cards_in_other_states():
    cs = solo(PotionId.SOLDIERS_STEW, hand=[strike()])
    other = CombatState.deepcopy(cs)
    drink(cs)
    assert other.player.hand[0].replay == 0

def test_entropic_brew_fills_the_empty_slots():
    rng.seed(5)
    cs = holding(one_enemy([]), PotionId.ENTROPIC_BREW, PotionId.BLOCK_POTION)
    cs.player.potion_slots = 4
    drink(cs, slot=0)
    slots = sorted(p.slot for p in cs.player.potions)
    assert slots == [0, 1, 2, 3] or slots == [0, 1, 2, 3][:len(slots)]
    assert len(cs.player.potions) == 4 and PotionId.ENTROPIC_BREW not in [p.potion_id for p in cs.player.potions]

def test_entropic_brew_only_fills_the_slot_it_frees_when_the_belt_is_full():
    cs = holding(one_enemy([]), PotionId.ENTROPIC_BREW, PotionId.BLOCK_POTION, PotionId.ENERGY_POTION)
    drink(cs, slot=0)
    assert len(cs.player.potions) == 3 and sorted(p.slot for p in cs.player.potions) == [0, 1, 2]


# ---------------------------------------------------------------- search support
def test_the_search_can_use_potions():
    from agents.sts2_MCTS.MCTS import SearchConfig, sts2_MCTS
    cs = holding(one_enemy([], hp=15), PotionId.FIRE_POTION)
    rng.seed(0)
    action, _ = sts2_MCTS().monte_carlo_tree_search(cs, SearchConfig(max_sims=150, early_exit=False, paired_scenarios=0))
    assert action["action"] == "use_potion"


# ---------------------------------------------------------------- potion relics (the wiki's text; the decompiled source has no potion relics)

def with_relic(cs, relic):
    cs.player.relics[relic] = RelicInstance(relic)
    return cs

def test_reptile_trinket_gives_3_strength_for_the_turn_per_potion():
    cs = with_relic(holding(one_enemy([strike()]), PotionId.BLOCK_POTION, PotionId.ENERGY_POTION), RelicId.REPTILE_TRINKET)
    sim = drink(cs, slot=0)
    assert cs.player.status_amount(StatusId.STRENGTH) == 3
    drink(cs, slot=1)
    assert cs.player.status_amount(StatusId.STRENGTH) == 6
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - 6 - 6
    sim.end_turn()
    assert cs.player.status_amount(StatusId.STRENGTH) == 0 and StatusId.REPTILE_TRINKET not in cs.player.status

def test_reptile_trinket_does_nothing_without_a_potion_used():
    cs = with_relic(one_enemy([strike()]), RelicId.REPTILE_TRINKET)
    CombatSimulator(cs).end_turn()
    assert cs.player.status_amount(StatusId.STRENGTH) == 0

def test_reptile_trinket_adds_to_a_flex_potion_and_both_wear_off():
    cs = with_relic(holding(one_enemy([]), PotionId.FLEX_POTION), RelicId.REPTILE_TRINKET)
    sim = drink(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == 8
    sim.end_turn()
    assert cs.player.status_amount(StatusId.STRENGTH) == 0

def test_belt_buckle_adds_2_dexterity_only_while_no_potions_are_held():
    cs = with_relic(holding(one_enemy([defend()]), PotionId.FIRE_POTION), RelicId.BELT_BUCKLE)
    sim = CombatSimulator(cs)
    assert sim.calculate_block(5, cs.player) == 5
    drink(cs, slot=0)
    assert sim.calculate_block(5, cs.player) == 7
    cs.player.potions = [Potion(PotionId.BLOCK_POTION, 0)]
    assert sim.calculate_block(5, cs.player) == 5

def test_belt_buckle_dexterity_stacks_with_real_dexterity_and_frail():
    cs = with_relic(one_enemy([defend()]), RelicId.BELT_BUCKLE)
    cs.player.apply_status(StatusId.DEXTERITY, 1); cs.player.apply_status(StatusId.FRAIL, 1)
    assert CombatSimulator(cs).calculate_block(5, cs.player) == 6     # (5 + 1 + 2) * 0.75

def test_belt_buckle_does_not_change_an_enemys_block():
    cs = with_relic(one_enemy([]), RelicId.BELT_BUCKLE)
    assert CombatSimulator(cs).calculate_block(5, cs.enemies[0]) == 5

def test_the_potion_relics_are_loaded_from_a_state():
    for name in ("REPTILE_TRINKET", "BELT_BUCKLE"):
        assert RelicInstance.from_dict({"id": name}).relic_id.name == name


# ---------------------------------------------------------------- Gambling Chip: a hand-select screen on turn 1
PURITY = Path(__file__).parent / "data" / "cards" / "colorless"

def gambling_chip_screen(ticked=()):
    """The Purity capture with the prompt of a discard screen (the real prompt is not captured yet)."""
    screen = json.loads((PURITY / ("purity_with_selected.json" if ticked else "purity.json")).read_text())
    screen["prompt"] = "Choose any number of cards to discard."
    return screen

def test_a_discard_screen_is_an_optional_discard_any_choice():
    cs = CombatState.from_dict(gambling_chip_screen())
    pending = cs.pending_choice
    assert pending.kind == "discard_any" and pending.amount == 0 and pending.optional
    assert any(a["action"] == "confirm_choice" for a in CombatSimulator(cs).get_available_actions())

def test_gambling_chip_discards_then_draws_as_many():
    cs = CombatState.from_dict(gambling_chip_screen())
    cs.player.draw_pile = [strike() for _ in range(10)]
    size, discard = len(cs.player.hand), len(cs.player.discard_pile)
    sim = CombatSimulator(cs)
    sim.perform_action([a for a in sim.get_available_actions() if a["action"] == "choose_card"][0])
    sim.perform_action([a for a in sim.get_available_actions() if a["action"] == "choose_card"][0])
    sim.perform_action({"action": "confirm_choice"})
    assert cs.pending_choice is None and len(cs.player.hand) == size and len(cs.player.discard_pile) == discard + 2

def test_gambling_chip_may_keep_the_hand():
    cs = CombatState.from_dict(gambling_chip_screen())
    hand = list(cs.player.hand)
    CombatSimulator(cs).perform_action({"action": "confirm_choice"})
    assert cs.player.hand == hand and cs.pending_choice is None

def test_cards_already_ticked_on_the_screen_count_as_discarded():
    screen = gambling_chip_screen(ticked=True)
    cs = CombatState.from_dict(screen)
    ticked = len(screen["selected_cards"])
    size = len(cs.player.hand)
    assert cs.pending_choice.amount == ticked and len(cs.player.discard_pile) >= ticked
    cs.player.draw_pile = [strike() for _ in range(10)]
    CombatSimulator(cs).perform_action({"action": "confirm_choice"})
    assert len(cs.player.hand) == size + ticked


# ---------------------------------------------------------------- Alchemize (Rare colorless Skill, 1 Energy, Exhaust; the upgrade costs 0)

def alchemize_state(potions=(), upgraded=False):
    cs = holding(one_enemy([Card.create_generated(CardId.ALCHEMIZE, upgraded)]), *potions)
    return cs

def test_alchemize_is_a_one_energy_exhausting_rare_skill():
    card = Card.create_generated(CardId.ALCHEMIZE)
    assert (card.type, card.energy_cost, card.exhausts, CARD_RARITY[CardId.ALCHEMIZE]) == (CardType.Skill, 1, True, CardRarity.Rare)

def test_the_upgrade_makes_alchemize_free():
    assert Card.create_generated(CardId.ALCHEMIZE, True).energy_cost == 0

def test_alchemize_procures_a_potion_in_the_first_free_slot():
    rng.seed(1)
    cs = alchemize_state((PotionId.BLOCK_POTION,))
    cs.player.potions.append(Potion(PotionId.ENERGY_POTION, 2))
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert sorted(p.slot for p in cs.player.potions) == [0, 1, 2] and cs.energy == 2
    assert len(cs.player.exhaust_pile) == 1

def test_alchemize_never_makes_fruit_juice():
    made = set()
    for seed in range(400):
        rng.seed(seed)
        cs = alchemize_state()
        CombatSimulator(cs).play_card(0, 0)
        made.add(cs.player.potions[0].potion_id)
    assert PotionId.FRUIT_JUICE not in made and len(made) > 15

def test_alchemize_can_make_the_potions_the_wiki_lists():
    made = set()
    for seed in range(1500):
        rng.seed(seed)
        cs = alchemize_state()
        CombatSimulator(cs).play_card(0, 0)
        made.add(cs.player.potions[0].potion_id)
    assert {PotionId.REGEN_POTION, PotionId.BLOOD_POTION, PotionId.FAIRY_IN_A_BOTTLE, PotionId.ENTROPIC_BREW} <= made

def test_alchemize_with_full_slots_makes_nothing_and_is_still_spent():
    cs = alchemize_state((PotionId.BLOCK_POTION, PotionId.ENERGY_POTION, PotionId.FIRE_POTION))
    CombatSimulator(cs).play_card(0, 0)
    assert len(cs.player.potions) == 3 and len(cs.player.exhaust_pile) == 1

def test_alchemize_respects_extra_potion_slots():
    cs = alchemize_state((PotionId.BLOCK_POTION, PotionId.ENERGY_POTION, PotionId.FIRE_POTION)); cs.player.potion_slots = 5
    CombatSimulator(cs).play_card(0, 0)
    assert len(cs.player.potions) == 4

def test_a_potion_from_alchemize_can_be_drunk_straight_away():
    rng.seed(2)
    cs = alchemize_state()
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert any(a["action"] == "use_potion" for a in sim.get_available_actions() if cs.player.potions[0].info.combat_usable)

def test_alchemize_is_never_generated_or_transformed_into():
    assert CardId.ALCHEMIZE in COLORLESS_CARDS
    assert CardId.ALCHEMIZE not in JACK_POOL and CardId.ALCHEMIZE not in TRANSFORM_COLORLESS

def test_entropic_brew_never_makes_fruit_juice_in_a_fight():
    for seed in range(200):
        rng.seed(seed)
        cs = holding(one_enemy([]), PotionId.ENTROPIC_BREW)
        cs.player.potion_slots = 5
        drink(cs)
        assert PotionId.FRUIT_JUICE not in [p.potion_id for p in cs.player.potions]


# ---------------------------------------------------------------- a card played from the draw pile that asks for a pick holds the rest back (Catastrophe, Beat Down)
def settle(sim):
    """Answers every card choice with the first option."""
    for _ in range(20):
        if sim.combat_state.pending_choice is None:
            return
        acts = [a for a in sim.get_available_actions() if a["action"] == "choose_card"]
        sim.perform_action(acts[0] if acts else {"action": "confirm_choice"})
    raise AssertionError("the choices never ended")

@pytest.mark.parametrize("seed", range(30))
def test_catastrophe_waits_for_the_pick_of_the_first_card_it_plays(seed):
    rng.seed(seed)
    hand = [Card.create_generated(CardId.CATASTROPHE).free_this_turn(), skill(CardId.SHRUG_IT_OFF, 1), skill(CardId.SECOND_WIND, 1)]
    cs = one_enemy(hand)
    cs.player.draw_pile = [skill(CardId.BURNING_PACT, 1), skill(CardId.SECOND_WIND, 1), strike()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    settle(sim)                               # (the old code crashed here: Second Wind emptied the hand under Burning Pact's pick)
    assert cs.pending_choice is None and not cs.continuations
    assert len(cs.player.draw_pile) <= 1      # two cards were played (Burning Pact also draws)

def test_catastrophe_plays_both_cards_after_the_pick():
    rng.seed(3)
    cs = one_enemy([Card.create_generated(CardId.CATASTROPHE).free_this_turn(), defend(), defend()])
    cs.player.draw_pile = [skill(CardId.BURNING_PACT, 1), strike()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    if cs.pending_choice is not None:
        assert len(cs.player.draw_pile) in (0, 1)       # a card waits for its pick, the other still has to be played
    settle(sim)
    assert cs.player.draw_pile == []

@pytest.mark.parametrize("seed", range(10))
def test_beat_down_waits_for_a_pick_too(seed):
    rng.seed(seed)
    cs = one_enemy([Card.create_generated(CardId.BEAT_DOWN).free_this_turn()])
    cs.player.hand += [skill(CardId.SECOND_WIND, 1)]
    cs.player.discard_pile = [strike(), strike(), strike()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    settle(sim)
    assert cs.pending_choice is None


# ---------------------------------------------------------------- Luminesce (Radiant Pearl's token: 0-cost Skill, Retain, Gain 2 Energy (3 upgraded), Exhaust)
LUMINESCE_CAPTURE = Path(__file__).parent / "data" / "relics" / "radiant_pearl_luminesce.json"

def test_luminesce_is_a_free_retaining_exhausting_skill():
    card = Card.create_generated(CardId.LUMINESCE)
    assert (card.type, card.energy_cost, card.exhausts, card.retains) == (CardType.Skill, 0, True, True)

@pytest.mark.parametrize("upgraded, energy", [(False, 2), (True, 3)])
def test_luminesce_gives_energy_and_exhausts(upgraded, energy):
    cs = one_enemy([Card.create_generated(CardId.LUMINESCE, upgraded)])
    CombatSimulator(cs).play_card(0, 0)
    assert cs.energy == 3 + energy and len(cs.player.exhaust_pile) == 1

def test_an_unplayed_luminesce_is_kept_for_the_next_turn():
    cs = one_enemy([Card.create_generated(CardId.LUMINESCE)])
    cs.player.draw_pile = [strike() for _ in range(10)]
    CombatSimulator(cs).end_turn()
    assert CardId.LUMINESCE in hand_ids(cs)

def test_the_radiant_pearl_capture_loads_luminesce_as_a_playable_card():
    cs = CombatState.from_dict(json.loads(LUMINESCE_CAPTURE.read_text()))
    sim = CombatSimulator(cs)
    index = next(i for i, c in enumerate(cs.player.hand) if c.card_id == CardId.LUMINESCE)
    assert any(a["action"] == "play_card" and a["card_index"] == index for a in sim.get_available_actions())
    before = cs.energy
    sim.play_card(index, 0)
    assert cs.energy == before + 2
