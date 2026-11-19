"""The Silent's Uncommon cards and the powers they apply (values from the decompiled Models.Cards / Models.Powers)."""
import pytest

from sts2_lite.card import Card, CardId, CardKeyword, CardType
from sts2_lite.combat import CombatSimulator
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_state


def gen(card_id, upgraded=False):
    return Card.create_generated(card_id, upgraded)

def ids(cards):
    return [c.card_id for c in cards]

def state(hand, enemies=1, hp=100):
    return make_state(hand, enemy_count=enemies, enemy_hp=hp)

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim

def pick(sim, card_id):
    cs = sim.combat_state
    sim.choose_card(next(i for i in cs.pending_choice.indices if cs.player.hand[i].card_id == card_id))


# ------------------------------------------------------------ attacks
@pytest.mark.parametrize("card_id, upgraded, damage, cost", [(CardId.BACKSTAB, False, 11, 0), (CardId.BACKSTAB, True, 15, 0),
                                                              (CardId.PINPOINT, False, 15, 3), (CardId.POUNCE, True, 20, 2)])
def test_plain_uncommon_attacks(card_id, upgraded, damage, cost):
    card = gen(card_id, upgraded)
    assert card.energy_cost == cost
    cs = state([card]); cs.energy = 3
    play(cs)
    assert cs.enemies[0].current_hp == 100 - damage

def test_backstab_is_innate_and_exhausts():
    assert {CardKeyword.INNATE, CardKeyword.EXHAUST} <= gen(CardId.BACKSTAB).keywords

def test_dash_blocks_and_hits():
    cs = state([gen(CardId.DASH, True)])
    play(cs)
    assert cs.player.block == 13 and cs.enemies[0].current_hp == 87

def test_echoing_slash_hits_again_for_every_kill():
    cs = state([gen(CardId.ECHOING_SLASH)], enemies=3, hp=30)
    cs.enemies[0].current_hp = 5
    play(cs)
    # one kill: everyone left is hit twice
    assert [e.current_hp for e in cs.enemies if e.current_hp > 0] == [10, 10]

def test_finisher_hits_once_per_attack_played_this_turn():
    cs = state([gen(CardId.STRIKE_SILENT), gen(CardId.SHIV), gen(CardId.FINISHER)])
    sim = play(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - 6 - 4 - 2 * 6

def test_finisher_with_no_attacks_deals_nothing():
    cs = state([gen(CardId.FINISHER)])
    play(cs)
    assert cs.enemies[0].current_hp == 100 and cs.energy == 2

def test_flechettes_hits_once_per_skill_in_hand():
    cs = state([gen(CardId.FLECHETTES), gen(CardId.DEFEND_SILENT), gen(CardId.DEFLECT), gen(CardId.STRIKE_SILENT)])
    play(cs)
    assert cs.enemies[0].current_hp == 90

def test_memento_mori_counts_this_turns_discards():
    cs = state([gen(CardId.SURVIVOR), gen(CardId.MEMENTO_MORI), gen(CardId.STRIKE_SILENT)])
    sim = play(cs)
    pick(sim, CardId.STRIKE_SILENT)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - 9 - 4

@pytest.mark.parametrize("others, damage", [(0, 13), (2, 9), (7, 0)])
def test_precise_cut_loses_two_per_other_card_in_hand(others, damage):
    cs = state([gen(CardId.PRECISE_CUT)] + [gen(CardId.DEFEND_SILENT) for _ in range(others)])
    play(cs)
    assert cs.enemies[0].current_hp == 100 - damage

def test_skewer_hits_x_times():
    cs = state([gen(CardId.SKEWER)])
    play(cs)
    assert cs.enemies[0].current_hp == 100 - 3 * 8 and cs.energy == 0

def test_pinpoint_is_cheaper_for_each_skill_played_this_turn_and_back_to_three_next_turn():
    cs = state([gen(CardId.DEFLECT), gen(CardId.DEFLECT), gen(CardId.PINPOINT)])
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.hand[0].energy_cost == 1
    sim.play_card(0, 0)
    assert cs.energy == 2
    pin = gen(CardId.PINPOINT)
    cs2 = state([gen(CardId.DEFLECT), pin])
    sim2 = play(cs2)
    sim2.end_turn()
    assert all(c.energy_cost == 3 for c in cs2.player.hand + cs2.player.draw_pile + cs2.player.discard_pile if c.card_id == CardId.PINPOINT)

def test_pounce_makes_the_next_skill_free():
    cs = state([gen(CardId.POUNCE), gen(CardId.LEG_SWEEP), gen(CardId.UNTOUCHABLE)])
    sim = play(cs)
    assert cs.energy == 1 and cs.player.hand[0].current_cost(cs.player) == 0
    sim.play_card(0, 0)
    assert cs.energy == 1 and cs.player.block == 11
    assert cs.player.hand[0].current_cost(cs.player) == 2

def test_strangle_costs_hp_for_each_later_card_but_not_its_own_play():
    cs = state([gen(CardId.STRANGLE), gen(CardId.DEFLECT), gen(CardId.DEFLECT)])
    cs.enemies[0].block = 50
    sim = play(cs)
    e = cs.enemies[0]
    assert e.current_hp == 100 and e.block == 42 and e.status_amount(StatusId.STRANGLE) == 2
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert e.current_hp == 96 and e.block == 42           # unblockable
    sim.end_turn()
    assert StatusId.STRANGLE not in e.status


# ------------------------------------------------------------ skills
def test_acrobatics_draws_then_discards_one():
    cs = state([gen(CardId.ACROBATICS)])
    cs.player.draw_pile = [gen(CardId.SLICE), gen(CardId.SLICE), gen(CardId.DEFLECT), gen(CardId.STRIKE_SILENT)]
    sim = play(cs)
    assert len(cs.player.hand) == 3 and cs.pending_choice.kind == "discard"
    sim.choose_card(cs.pending_choice.indices[0])
    assert len(cs.player.hand) == 2

def test_blur_keeps_block_for_a_turn():
    cs = state([gen(CardId.BLUR)])
    sim = play(cs)
    sim.end_turn()
    assert cs.player.block == 5 and StatusId.BLUR not in cs.player.status

def test_bouncing_flask_poisons_random_enemies():
    cs = state([gen(CardId.BOUNCING_FLASK, True)], enemies=2)
    play(cs)
    assert sum(e.status_amount(StatusId.POISON) for e in cs.enemies) == 12

@pytest.mark.parametrize("poisoned, poison", [(False, 0), (True, 1 + 9)])
def test_bubble_bubble_needs_poison_already(poisoned, poison):
    cs = state([gen(CardId.BUBBLE_BUBBLE)])
    if poisoned:
        cs.enemies[0].apply_status(StatusId.POISON, 1)
    play(cs)
    assert cs.enemies[0].status_amount(StatusId.POISON) == poison

def test_calculated_gamble_discards_the_hand_draws_as_many_then_plays_sly():
    cs = state([gen(CardId.CALCULATED_GAMBLE), gen(CardId.FLICK_FLACK), gen(CardId.DEFEND_SILENT)])
    cs.player.draw_pile = [gen(CardId.SLICE), gen(CardId.SLICE), gen(CardId.SLICE)]
    play(cs)
    assert ids(cs.player.hand) == [CardId.SLICE, CardId.SLICE]
    assert cs.enemies[0].current_hp == 93 and cs.player.discards_this_turn == 2
    assert ids(cs.player.exhaust_pile) == [CardId.CALCULATED_GAMBLE]

def test_calculated_gamble_upgrade_retains():
    assert gen(CardId.CALCULATED_GAMBLE, True).retains and not gen(CardId.CALCULATED_GAMBLE).retains

@pytest.mark.parametrize("top, block", [(CardId.DEFLECT, 3), (CardId.SLICE, 0)])
def test_escape_plan_blocks_only_when_it_draws_a_skill(top, block):
    cs = state([gen(CardId.ESCAPE_PLAN)])
    cs.player.draw_pile = [gen(top)]
    play(cs)
    assert cs.player.block == block and ids(cs.player.hand) == [top]

def test_expertise_cards_are_retained_this_turn_only():
    cs = state([gen(CardId.EXPERTISE)])
    cs.player.draw_pile = [gen(CardId.SLICE) for _ in range(6)]
    sim = play(cs)
    assert all(c.retains for c in cs.player.hand) and len(cs.player.hand) == 2
    sim.end_turn()
    retained = [c for c in cs.player.hand if c.card_id == CardId.SLICE]
    assert len(cs.player.hand) == 7 and not any(c.retains for c in retained)

def test_expose_strips_block_and_artifact_then_vulnerable():
    cs = state([gen(CardId.EXPOSE)])
    e = cs.enemies[0]
    e.block = 20
    e.apply_status(StatusId.ARTIFACT, 2)
    play(cs)
    assert e.block == 0 and StatusId.ARTIFACT not in e.status and e.status_amount(StatusId.VULNERABLE) == 2

def test_sidestep_energy_next_turn():
    cs = state([gen(CardId.SIDESTEP, True)])
    sim = play(cs)
    sim.end_turn()
    assert cs.energy == 5

def test_hand_trick_gives_a_skill_sly_for_the_turn():
    cs = state([gen(CardId.HAND_TRICK), gen(CardId.DEFEND_SILENT), gen(CardId.SURVIVOR), gen(CardId.SLICE)])
    sim = play(cs)
    assert cs.player.block == 7 and cs.pending_choice.kind == "sly" and len(cs.pending_choice.indices) == 2
    pick(sim, CardId.DEFEND_SILENT)
    assert next(c for c in cs.player.hand if c.card_id == CardId.DEFEND_SILENT).sly
    sim.play_card(next(i for i, c in enumerate(cs.player.hand) if c.card_id == CardId.SURVIVOR), 0)
    pick(sim, CardId.DEFEND_SILENT)
    assert cs.player.block == 7 + 8 + 5           # the Sly Defend played itself

def test_hand_trick_sly_ends_with_the_turn():
    cs = state([gen(CardId.HAND_TRICK), gen(CardId.DEFEND_SILENT)])
    cs.player.draw_pile = [gen(CardId.SLICE) for _ in range(10)]
    sim = play(cs)
    sim.end_turn()
    assert not any(c.sly for c in cs.player.hand + cs.player.discard_pile + cs.player.draw_pile)

def test_haze_poisons_and_weakens_everyone():
    cs = state([gen(CardId.HAZE, True)], enemies=2)
    play(cs)
    assert all(e.status_amount(StatusId.POISON) == 6 and e.status_amount(StatusId.WEAK) == 2 for e in cs.enemies)

def test_hidden_daggers_discards_two_then_makes_shivs():
    cs = state([gen(CardId.HIDDEN_DAGGERS, True), gen(CardId.STRIKE_SILENT), gen(CardId.DEFEND_SILENT), gen(CardId.SLICE)])
    sim = play(cs)
    assert cs.pending_choice.kind == "discard" and CardId.SHIV not in ids(cs.player.hand)
    pick(sim, CardId.STRIKE_SILENT)
    pick(sim, CardId.DEFEND_SILENT)
    assert ids(cs.player.hand) == [CardId.SLICE, CardId.SHIV, CardId.SHIV]
    assert all(c.is_upgraded for c in cs.player.hand if c.card_id == CardId.SHIV)

def test_leg_sweep():
    cs = state([gen(CardId.LEG_SWEEP)])
    play(cs)
    assert cs.player.block == 11 and cs.enemies[0].status_amount(StatusId.WEAK) == 2

def test_mirage_blocks_the_poison_on_enemies():
    cs = state([gen(CardId.MIRAGE)], enemies=2)
    cs.enemies[0].apply_status(StatusId.POISON, 5)
    cs.enemies[1].apply_status(StatusId.POISON, 4)
    play(cs)
    assert cs.player.block == 9 and ids(cs.player.exhaust_pile) == [CardId.MIRAGE]
    assert CardKeyword.EXHAUST not in gen(CardId.MIRAGE, True).keywords

def test_reflex_and_tactician_are_sly():
    cs = state([gen(CardId.SURVIVOR), gen(CardId.TACTICIAN)])
    play(cs)
    assert cs.energy == 3          # 1 for Survivor, 1 back from the discarded Tactician
    assert gen(CardId.REFLEX).sly and gen(CardId.REFLEX).energy_cost == 3

def test_up_my_sleeve_gets_cheaper_for_the_rest_of_the_combat():
    cs = state([gen(CardId.UP_MY_SLEEVE)])
    sim = play(cs)
    assert ids(cs.player.hand) == [CardId.SHIV] * 3
    sleeve = next(c for c in cs.player.discard_pile if c.card_id == CardId.UP_MY_SLEEVE)
    assert sleeve.energy_cost == 1
    sim.end_turn()
    sleeve = next(c for c in cs.player.hand + cs.player.draw_pile + cs.player.discard_pile if c.card_id == CardId.UP_MY_SLEEVE)
    assert sleeve.energy_cost == 1


# ------------------------------------------------------------ powers
def test_accelerant_makes_poison_trigger_more_but_not_beyond_its_amount():
    cs = state([gen(CardId.ACCELERANT)], hp=100)
    cs.enemies[0].apply_status(StatusId.POISON, 5)
    sim = play(cs)
    sim.end_turn()
    assert cs.enemies[0].current_hp == 100 - 5 - 4 and cs.enemies[0].status_amount(StatusId.POISON) == 3
    cs2 = state([gen(CardId.ACCELERANT, True)])
    cs2.enemies[0].apply_status(StatusId.POISON, 2)
    sim2 = play(cs2)
    sim2.end_turn()
    assert cs2.enemies[0].current_hp == 97 and StatusId.POISON not in cs2.enemies[0].status

def test_accuracy_adds_to_shivs_only():
    cs = state([gen(CardId.ACCURACY), gen(CardId.SHIV), gen(CardId.STRIKE_SILENT)])
    sim = play(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - 8 - 6

def test_phantom_blades_first_shiv_each_turn_and_retain():
    cs = state([gen(CardId.PHANTOM_BLADES), gen(CardId.SHIV), gen(CardId.SHIV)])
    sim = play(cs)
    assert all(c.retains for c in cs.player.hand)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - 13 - 4

def test_phantom_blades_shivs_made_later_retain():
    cs = state([gen(CardId.PHANTOM_BLADES), gen(CardId.BLADE_DANCE)])
    sim = play(cs)
    sim.play_card(0, 0)
    sim.end_turn()
    assert ids(cs.player.hand).count(CardId.SHIV) == 3

def test_infinite_blades_adds_a_shiv_each_turn():
    cs = state([gen(CardId.INFINITE_BLADES)])
    sim = play(cs)
    sim.end_turn()
    assert ids(cs.player.hand).count(CardId.SHIV) == 1
    assert CardKeyword.INNATE in gen(CardId.INFINITE_BLADES, True).keywords

def test_noxious_fumes_poisons_every_enemy_at_turn_start():
    cs = state([gen(CardId.NOXIOUS_FUMES)], enemies=2)
    sim = play(cs)
    sim.end_turn()
    assert all(e.status_amount(StatusId.POISON) == 2 for e in cs.enemies)
    sim.end_turn()
    assert all(e.status_amount(StatusId.POISON) == 1 + 2 for e in cs.enemies)

def test_footwork():
    cs = state([gen(CardId.FOOTWORK), gen(CardId.DEFEND_SILENT)])
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.block == 7

def test_speedster_hits_on_draws_outside_the_hand_draw():
    cs = state([gen(CardId.SPEEDSTER), gen(CardId.BACKFLIP)], enemies=2)
    cs.player.draw_pile = [gen(CardId.SLICE) for _ in range(10)]
    cs.energy = 3
    sim = play(cs)
    sim.play_card(0, 0)
    assert [e.current_hp for e in cs.enemies] == [96, 96]
    hp = [e.current_hp for e in cs.enemies]
    sim.end_turn()
    assert [e.current_hp for e in cs.enemies] == hp         # the hand draw does not count

@pytest.mark.parametrize("status", ["ACCELERANT", "ACCURACY", "INFINITE_BLADES", "NOXIOUS_FUMES", "PHANTOM_BLADES", "SPEEDSTER", "FREE_SKILL"])
def test_powers_load_from_bridge_ids(status):
    from sts2_lite.status import status_id_of
    assert status_id_of(status + "_POWER") is StatusId[status]

def test_silent_reward_pool_has_uncommons():
    from sts2_lite.rewards.cards import card_pool
    pool = card_pool("SILENT")
    assert len(pool["Uncommon"]) == 35          # SilentCardPool's 38 minus the multiplayer-only Blade Symphony, Concoct and Fade
