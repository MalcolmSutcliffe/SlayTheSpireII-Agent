"""The Defect: orbs, Focus, the character's cards and powers, relics, potions and run setup."""
import pytest

from sts2_lite import orbs
from sts2_lite.card import Card, CardId, CardType, GET_CARD_FUNCTION
from sts2_lite.card.constants import CARD_ENERGY_COST_AND_TARGET
from sts2_lite.card.tables import ANCIENT_CARDS, CARD_RARITY, DEFECT_CARDS, TOKEN_CARDS, combat_pool
from sts2_lite.character import CHARACTERS
from sts2_lite.combat import CombatSimulator
from sts2_lite.hooks import HookType
from sts2_lite.player import Player
from sts2_lite.potion import EFFECTS, PotionId
from sts2_lite.relic import RelicId, RelicInstance
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_state


def gen(card_id, upgraded=False):
    return Card.create_generated(card_id, upgraded)

def state(hand, hp=100, enemies=1, draw=(), discard=(), slots=3):
    cs = make_state(hand, enemy_count=enemies, enemy_hp=hp)
    cs.player.character = "DEFECT"
    cs.player.orb_slots = slots
    cs.player.draw_pile = list(draw)
    cs.player.discard_pile = list(discard)
    return cs

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim

def sim_of(cs):
    return CombatSimulator(cs)

def hp(cs, i=0):
    return cs.enemies[i].current_hp

def kinds(cs):
    return [o.kind for o in cs.player.orbs]

def focus(cs, amount):
    cs.player.apply_status(StatusId.FOCUS, amount)


# ------------------------------------------------------------ the character
def test_the_character():
    c = CHARACTERS["DEFECT"]
    assert (c.hp, c.gold, c.relic, c.title) == (75, 99, "CRACKED_CORE", "The Defect")
    assert c.deck.count("STRIKE_DEFECT") == 4 and c.deck.count("DEFEND_DEFECT") == 4 and "ZAP" in c.deck and "DUALCAST" in c.deck

def test_a_defect_run_starts_with_the_cracked_core():
    from sts2_lite.run.state import new_run
    run = new_run(0, "DEFECT")
    assert (run.character, run.hp, len(run.deck), run.relics[0]["id"]) == ("DEFECT", 75, 10, "CRACKED_CORE")

def test_every_card_has_a_play_a_cost_and_a_rarity():
    for card_id, (name, ctype, cost, target) in {**DEFECT_CARDS, CardId.QUADCAST: ANCIENT_CARDS[CardId.QUADCAST], CardId.BIASED_COGNITION: ANCIENT_CARDS[CardId.BIASED_COGNITION], CardId.FUEL: TOKEN_CARDS[CardId.FUEL]}.items():
        assert card_id in GET_CARD_FUNCTION, card_id
        assert CARD_ENERGY_COST_AND_TARGET[card_id] == (cost, target), card_id
        assert CARD_RARITY[card_id] is not None

def test_the_pool_has_the_defects_cards_without_the_multiplayer_ones():
    assert len(DEFECT_CARDS) == 84
    pool = set(combat_pool("DEFECT"))
    assert CardId.ZAP not in pool and CardId.DUALCAST not in pool and CardId.QUADCAST not in pool        # Basic and Ancient cards are never generated
    assert CardId.CLAW in pool and CardId.ECHO_FORM in pool and CardId.MULTI_CAST in pool

def test_the_reward_pool_and_the_ancient_cards():
    from sts2_lite.rewards.cards import card_pool
    from sts2_lite.campaign.ancients import ANCIENT_CARDS_OF
    assert CardId.BALL_LIGHTNING in card_pool("DEFECT")["Common"] and CardId.ECHO_FORM in card_pool("DEFECT")["Rare"]
    assert ANCIENT_CARDS_OF["DEFECT"] == ("QUADCAST", "BIASED_COGNITION")


# ------------------------------------------------------------ orbs
def test_zap_channels_a_lightning_orb():
    cs = state([gen(CardId.ZAP)])
    play(cs)
    assert kinds(cs) == [orbs.LIGHTNING] and cs.energy == 2

def test_a_full_queue_evokes_the_first_orb():
    cs = state([gen(CardId.ZAP)], slots=2)
    cs.player.orbs = [orbs.Orb(orbs.FROST), orbs.Orb(orbs.LIGHTNING)]
    play(cs)
    assert kinds(cs) == [orbs.LIGHTNING, orbs.LIGHTNING] and cs.player.block == 5          # Frost's evoke

def test_no_slots_means_the_orb_is_lost():
    cs = state([gen(CardId.ZAP)], slots=0)
    play(cs)
    assert cs.player.orbs == []

def test_lightning_evoke_and_passive():
    cs = state([])
    sim = sim_of(cs)
    orbs.channel(sim, orbs.LIGHTNING)
    orbs.before_turn_end(sim)
    assert hp(cs) == 97
    orbs.evoke_next(sim)
    assert hp(cs) == 89 and cs.player.orbs == []

def test_orb_damage_ignores_strength_and_vulnerable():
    cs = state([])
    cs.player.apply_status(StatusId.STRENGTH, 5)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    sim = sim_of(cs)
    orbs.channel(sim, orbs.LIGHTNING)
    orbs.evoke_next(sim)
    assert hp(cs) == 92

def test_frost_gives_block_that_ignores_dexterity():
    cs = state([])
    cs.player.apply_status(StatusId.DEXTERITY, 5)
    sim = sim_of(cs)
    orbs.channel(sim, orbs.FROST)
    orbs.before_turn_end(sim)
    assert cs.player.block == 2
    orbs.evoke_next(sim)
    assert cs.player.block == 7

def test_dark_stores_up_its_passives_and_hits_the_weakest_enemy():
    cs = state([], enemies=2)
    cs.enemies[1].current_hp = 50
    sim = sim_of(cs)
    orbs.channel(sim, orbs.DARK)
    orbs.before_turn_end(sim)
    orbs.before_turn_end(sim)
    orbs.evoke_next(sim)
    assert hp(cs, 1) == 50 - 18 and hp(cs, 0) == 100

def test_plasma_gives_energy_at_the_start_of_the_turn_and_when_evoked():
    cs = state([])
    sim = sim_of(cs)
    orbs.channel(sim, orbs.PLASMA)
    orbs.before_turn_end(sim)
    assert cs.energy == 3                       # Plasma does not fire at the end of the turn
    orbs.after_turn_start(sim)
    assert cs.energy == 4
    orbs.evoke_next(sim)
    assert cs.energy == 6

def test_glass_hits_everything_and_weakens():
    cs = state([], enemies=2)
    sim = sim_of(cs)
    orbs.channel(sim, orbs.GLASS)
    orbs.before_turn_end(sim)
    orbs.before_turn_end(sim)
    assert (hp(cs, 0), hp(cs, 1)) == (100 - 4 - 3, 100 - 4 - 3)
    orbs.evoke_next(sim)
    assert hp(cs, 0) == 100 - 7 - 4 and cs.player.orbs == []        # 2 x 2

def test_focus_changes_the_values_and_never_goes_below_zero():
    cs = state([])
    sim = sim_of(cs)
    orbs.channel(sim, orbs.LIGHTNING)
    focus(cs, 2)
    orbs.before_turn_end(sim)
    assert hp(cs) == 95
    focus(cs, -20)
    orbs.before_turn_end(sim)
    assert hp(cs) == 95
    assert orbs.evoke_value(cs.player, cs.player.orbs[0]) == 0

def test_focus_does_not_change_plasma_or_a_stored_dark_evoke():
    cs = state([])
    focus(cs, 3)
    assert orbs.passive_value(cs.player, orbs.Orb(orbs.PLASMA)) == 1
    assert orbs.evoke_value(cs.player, orbs.Orb(orbs.PLASMA)) == 2
    assert orbs.evoke_value(cs.player, orbs.Orb(orbs.DARK)) == 6

def test_the_turn_end_fires_the_passives():
    cs = state([], hp=100)
    cs.player.orbs = [orbs.Orb(orbs.LIGHTNING)]
    cs.player.orb_slots = 3
    sim_of(cs).end_turn()
    assert hp(cs) <= 97

def test_dualcast_evokes_the_first_orb_twice():
    cs = state([gen(CardId.DUALCAST)])
    cs.player.orbs = [orbs.Orb(orbs.LIGHTNING), orbs.Orb(orbs.FROST)]
    play(cs)
    assert hp(cs) == 84 and kinds(cs) == [orbs.FROST]

def test_dualcast_does_nothing_without_orbs():
    cs = state([gen(CardId.DUALCAST)])
    play(cs)
    assert hp(cs) == 100

@pytest.mark.parametrize("upgraded, times", [(False, 3), (True, 4)])
def test_multi_cast_spends_all_energy(upgraded, times):
    cs = state([gen(CardId.MULTI_CAST, upgraded)])
    cs.player.orbs = [orbs.Orb(orbs.LIGHTNING)]
    play(cs)
    assert cs.energy == 0 and hp(cs) == 100 - 8 * times and cs.player.orbs == []

def test_quadcast():
    cs = state([gen(CardId.QUADCAST)])
    cs.player.orbs = [orbs.Orb(orbs.LIGHTNING)]
    play(cs)
    assert hp(cs) == 100 - 32

def test_shatter_evokes_the_first_orb_once_per_orb_and_once_more():
    cs = state([gen(CardId.SHATTER)])
    cs.player.orbs = [orbs.Orb(orbs.LIGHTNING), orbs.Orb(orbs.FROST)]
    play(cs)
    assert hp(cs) == 100 - 7 - 8 * 3 and kinds(cs) == [orbs.FROST]

def test_capacitor_adds_slots_up_to_ten():
    cs = state([gen(CardId.CAPACITOR, True)], slots=9)
    play(cs)
    assert cs.player.orb_slots == 10

def test_bulk_up_costs_a_slot_and_its_orb():
    cs = state([gen(CardId.BULK_UP)])
    cs.player.orbs = [orbs.Orb(orbs.FROST), orbs.Orb(orbs.FROST), orbs.Orb(orbs.LIGHTNING)]
    play(cs)
    assert cs.player.orb_slots == 2 and kinds(cs) == [orbs.FROST, orbs.FROST]
    assert cs.player.status_amount(StatusId.STRENGTH) == 2 and cs.player.status_amount(StatusId.DEXTERITY) == 2

def test_tempest_channels_x_orbs():
    cs = state([gen(CardId.TEMPEST)], slots=5)
    cs.energy = 3
    play(cs)
    assert kinds(cs) == [orbs.LIGHTNING] * 3 and cs.energy == 0

def test_voltaic_counts_every_lightning_channeled_this_fight():
    cs = state([gen(CardId.VOLTAIC)], slots=6)
    cs.energy = 3
    sim = sim_of(cs)
    orbs.channel(sim, orbs.LIGHTNING, 2)
    orbs.channel(sim, orbs.FROST)
    sim.play_card(0, 0)
    assert kinds(cs).count(orbs.LIGHTNING) == 4

def test_barrage_and_compile_driver_count_orbs():
    cs = state([gen(CardId.BARRAGE)])
    cs.player.orbs = [orbs.Orb(orbs.LIGHTNING), orbs.Orb(orbs.FROST)]
    play(cs)
    assert hp(cs) == 90
    cs = state([gen(CardId.COMPILE_DRIVER)], draw=[gen(CardId.ZAP)] * 5)
    cs.player.orbs = [orbs.Orb(orbs.LIGHTNING), orbs.Orb(orbs.FROST), orbs.Orb(orbs.LIGHTNING)]
    play(cs)
    assert hp(cs) == 93 and len(cs.player.hand) == 2

def test_barrage_with_no_orbs_still_needs_a_target():
    cs = state([gen(CardId.BARRAGE)])
    with pytest.raises(ValueError):
        play(cs, target=3)

def test_tesla_coil_fires_the_lightning_passives_at_the_target():
    cs = state([gen(CardId.TESLA_COIL)], enemies=2)
    cs.player.orbs = [orbs.Orb(orbs.LIGHTNING), orbs.Orb(orbs.FROST), orbs.Orb(orbs.LIGHTNING)]
    play(cs, target=1)
    assert hp(cs, 1) == 100 - 3 - 6 and hp(cs, 0) == 100

def test_darkness_triggers_the_dark_passives():
    cs = state([gen(CardId.DARKNESS, True)])
    cs.player.orbs = [orbs.Orb(orbs.DARK)]
    play(cs)
    assert [o.kind for o in cs.player.orbs] == [orbs.DARK, orbs.DARK] and cs.player.orbs[0].evoke == 18

def test_synchronize_gives_temporary_focus_and_it_goes_back():
    cs = state([gen(CardId.SYNCHRONIZE)])
    cs.player.orbs = [orbs.Orb(orbs.LIGHTNING), orbs.Orb(orbs.FROST), orbs.Orb(orbs.FROST)]
    play(cs)
    assert cs.player.status_amount(StatusId.FOCUS) == 2
    CombatSimulator._return_temporary_strength(cs.player)
    assert cs.player.status_amount(StatusId.FOCUS) == 0

def test_hyperbeam_takes_focus_until_the_end_of_the_turn():
    cs = state([gen(CardId.HYPERBEAM)], enemies=2)
    focus(cs, 1)
    cs.energy = 3
    play(cs)
    assert (hp(cs, 0), hp(cs, 1)) == (76, 76) and cs.player.status_amount(StatusId.FOCUS) == -2
    CombatSimulator._return_temporary_strength(cs.player)
    assert cs.player.status_amount(StatusId.FOCUS) == 1

def test_focused_strike_and_hotfix():
    cs = state([gen(CardId.FOCUSED_STRIKE), gen(CardId.HOTFIX)])
    sim = sim_of(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert hp(cs) == 91 and cs.player.status_amount(StatusId.FOCUS) == 3
    CombatSimulator._return_temporary_strength(cs.player)
    assert cs.player.status_amount(StatusId.FOCUS) == 0

def test_defragment_is_permanent_focus():
    cs = state([gen(CardId.DEFRAGMENT)])
    play(cs)
    assert cs.player.status_amount(StatusId.FOCUS) == 1

def test_biased_cognition_trades_focus_for_a_loss_each_turn():
    cs = state([gen(CardId.BIASED_COGNITION)])
    sim = play(cs)
    assert cs.player.status_amount(StatusId.FOCUS) == 5
    sim.fire(HookType.BEFORE_PLAYER_TURN)
    assert cs.player.status_amount(StatusId.FOCUS) == 4


# ------------------------------------------------------------ powers
def test_loop_repeats_the_first_orbs_passive_at_the_start_of_the_turn():
    cs = state([gen(CardId.LOOP)])
    cs.player.orbs = [orbs.Orb(orbs.LIGHTNING)]
    sim = play(cs)
    sim.fire(HookType.PLAYER_TURN_START)
    assert hp(cs) == 97

def test_storm_channels_for_every_other_power_not_for_itself():
    cs = state([gen(CardId.STORM), gen(CardId.DEFRAGMENT)])
    sim = sim_of(cs)
    sim.play_card(0, 0)
    assert cs.player.orbs == []
    sim.play_card(0, 0)
    assert kinds(cs) == [orbs.LIGHTNING]

def test_subroutine_gives_energy_for_later_powers():
    cs = state([gen(CardId.SUBROUTINE), gen(CardId.DEFRAGMENT)])
    sim = sim_of(cs)
    sim.play_card(0, 0)
    assert cs.energy == 2
    sim.play_card(0, 0)
    assert cs.energy == 2           # paid 1, got 1

def test_echo_form_plays_the_first_card_of_the_turn_twice():
    cs = state([gen(CardId.STRIKE_DEFECT), gen(CardId.STRIKE_DEFECT)])
    cs.player.apply_status(StatusId.ECHO_FORM, 1)
    sim = sim_of(cs)
    sim.play_card(0, 0)
    assert hp(cs) == 100 - 12
    sim.play_card(0, 0)
    assert hp(cs) == 100 - 18

def test_signal_boost_plays_the_next_power_twice():
    cs = state([gen(CardId.SIGNAL_BOOST), gen(CardId.DEFRAGMENT)])
    sim = sim_of(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.FOCUS) == 2 and StatusId.SIGNAL_BOOST not in cs.player.status

def test_synthesis_makes_the_next_power_free():
    cs = state([gen(CardId.SYNTHESIS), gen(CardId.CREATIVE_AI)])
    sim = sim_of(cs)
    sim.play_card(0, 0)
    assert cs.energy == 1
    sim.play_card(0, 0)
    assert cs.energy == 1 and StatusId.CREATIVE_AI in cs.player.status

def test_feral_returns_the_first_free_attacks_to_the_hand():
    cs = state([gen(CardId.CLAW)])
    cs.player.apply_status(StatusId.FERAL, 1)
    sim = sim_of(cs)
    sim.play_card(0, 0)
    assert [c.card_id for c in cs.player.hand] == [CardId.CLAW]
    sim.play_card(0, 0)
    assert cs.player.hand == [] and [c.card_id for c in cs.player.discard_pile] == [CardId.CLAW]

def test_machine_learning_draws_more_each_turn():
    cs = state([], draw=[gen(CardId.ZAP)] * 8)
    cs.player.apply_status(StatusId.MACHINE_LEARNING, 1)
    cs.player.turn_start()
    assert len(cs.player.hand) == 6

def test_iteration_draws_for_the_first_status_drawn():
    cs = state([], draw=[gen(CardId.ZAP)] * 3 + [Card.create(CardId.WOUND)])
    cs.player.apply_status(StatusId.ITERATION, 2)
    sim_of(cs)
    cs.player.draw_cards(1)
    assert len(cs.player.hand) == 3

def test_thunder_hits_for_every_lightning_evoke():
    cs = state([])
    cs.player.apply_status(StatusId.THUNDER, 4)
    sim = sim_of(cs)
    orbs.channel(sim, orbs.LIGHTNING)
    orbs.evoke_next(sim)
    assert hp(cs) == 100 - 8 - 4

def test_hailstorm_and_coolant_need_orbs():
    cs = state([])
    cs.player.apply_status(StatusId.HAILSTORM, 6)
    cs.player.apply_status(StatusId.COOLANT, 2)
    cs.player.orbs = [orbs.Orb(orbs.FROST), orbs.Orb(orbs.FROST), orbs.Orb(orbs.DARK)]
    sim = sim_of(cs)
    sim.fire(HookType.END_TURN)
    assert hp(cs) == 94
    sim.fire(HookType.PLAYER_TURN_START)
    assert cs.player.block == 4

def test_consuming_shadow_evokes_the_last_orb_after_the_turn():
    cs = state([gen(CardId.CONSUMING_SHADOW)], slots=3)
    sim = play(cs)
    assert kinds(cs) == [orbs.DARK, orbs.DARK]
    sim.fire(HookType.PLAYER_TURN_ENDED)
    assert kinds(cs) == [orbs.DARK] and hp(cs) == 94

def test_lightning_rod_and_spinner_channel_when_the_energy_is_reset():
    cs = state([])
    cs.player.apply_status(StatusId.LIGHTNING_ROD, 2)
    cs.player.apply_status(StatusId.SPINNER, 1)
    sim = sim_of(cs)
    from sts2_lite import defect
    defect.after_energy_reset(sim)
    assert kinds(cs) == [orbs.LIGHTNING, orbs.GLASS] and cs.player.status_amount(StatusId.LIGHTNING_ROD) == 1

def test_spinner_upgraded_channels_a_glass_orb_at_once():
    cs = state([gen(CardId.SPINNER, True)])
    play(cs)
    assert kinds(cs) == [orbs.GLASS]

def test_creative_ai_brings_a_power_to_the_hand():
    cs = state([])
    cs.player.apply_status(StatusId.CREATIVE_AI, 1)
    sim_of(cs).fire(HookType.BLOCK_CLEARED)
    assert len(cs.player.hand) == 1 and cs.player.hand[0].type == CardType.Power

def test_trash_to_treasure_and_smokestack_react_to_statuses_a_card_makes():
    cs = state([gen(CardId.BOOST_AWAY)])
    cs.player.apply_status(StatusId.TRASH_TO_TREASURE, 1)
    cs.player.apply_status(StatusId.SMOKESTACK, 5)
    play(cs)
    assert hp(cs) == 95 and len(cs.player.orbs) == 1 and [c.card_id for c in cs.player.discard_pile] == [CardId.BOOST_AWAY, CardId.DAZED] or len(cs.player.discard_pile) == 2

def test_statuses_made_by_enemies_do_not_trigger_smokestack():
    cs = state([])
    cs.player.apply_status(StatusId.SMOKESTACK, 5)
    sim = sim_of(cs)
    sim.in_enemy_turn = True
    sim._card_generated(Card.create(CardId.DAZED))
    assert hp(cs) == 100


# ------------------------------------------------------------ cards
def test_claw_grows_every_claw():
    cs = state([gen(CardId.CLAW)], discard=[gen(CardId.CLAW)])
    cs.player.hand.append(gen(CardId.CLAW))
    sim = play(cs)
    assert hp(cs) == 97
    assert sorted(c.bonus_damage for c in cs.player.hand + cs.player.discard_pile) == [2, 2, 2]
    sim.play_card(0, 0)
    assert hp(cs) == 97 - 5

def test_helix_drill_hits_once_for_every_energy_spent_this_turn():
    cs = state([gen(CardId.STRIKE_DEFECT), gen(CardId.HELIX_DRILL)])
    sim = sim_of(cs)
    sim.play_card(0, 0)
    assert hp(cs) == 94
    sim.play_card(0, 0)
    assert hp(cs) == 91

def test_scrape_discards_the_cards_that_cost_energy():
    cs = state([gen(CardId.SCRAPE)], draw=[gen(CardId.STRIKE_DEFECT), gen(CardId.CLAW), gen(CardId.ZAP), gen(CardId.BEAM_CELL)])
    play(cs)
    assert sorted(c.card_id.name for c in cs.player.hand) == ["BEAM_CELL", "CLAW"] and len(cs.player.discard_pile) == 3

def test_flak_cannon_exhausts_every_status_and_hits_for_each():
    cs = state([gen(CardId.FLAK_CANNON)], discard=[Card.create(CardId.WOUND)], draw=[Card.create(CardId.DAZED)])
    cs.energy = 3
    play(cs)
    assert hp(cs) == 100 - 16 and len(cs.player.exhaust_pile) == 2

def test_compact_turns_statuses_into_fuel():
    cs = state([gen(CardId.COMPACT), Card.create(CardId.WOUND)])
    sim = play(cs)
    assert [c.card_id for c in cs.player.hand] == [CardId.FUEL] and cs.player.block == 6
    sim.play_card(0, 0)
    assert cs.energy == 3

def test_turbo_gives_energy_and_a_void_that_costs_energy_when_drawn():
    cs = state([gen(CardId.TURBO)], draw=[Card.create(CardId.VOID)])
    play(cs)
    assert cs.energy == 5 and CardId.VOID in [c.card_id for c in cs.player.discard_pile]
    cs.player.draw_cards(1)
    assert cs.player.hand[-1].card_id == CardId.VOID and cs.energy == 4

def test_a_void_is_unplayable_and_ethereal():
    c = Card.create(CardId.VOID)
    assert c.unplayable and c.ethereal and c.type == CardType.Status

def test_go_for_the_eyes_needs_an_attacking_enemy():
    cs = state([gen(CardId.GO_FOR_THE_EYES)])
    cs.enemies[0].attack_damage = 0
    cs.enemies[0].moves = None
    play(cs)
    assert cs.enemies[0].status_amount(StatusId.WEAK) == 0
    cs = state([gen(CardId.GO_FOR_THE_EYES)])
    cs.enemies[0].attack_damage = 7
    play(cs)
    assert cs.enemies[0].status_amount(StatusId.WEAK) == 1

def test_sunder_gives_energy_for_a_kill():
    cs = state([gen(CardId.SUNDER)], hp=26)
    cs.energy = 3
    play(cs)
    assert cs.energy == 3

def test_all_for_one_returns_free_cards_of_the_discard_pile():
    cs = state([gen(CardId.ALL_FOR_ONE)], discard=[gen(CardId.CLAW), gen(CardId.STRIKE_DEFECT), gen(CardId.ZAP).free_this_turn()])
    cs.energy = 2
    play(cs)
    assert sorted(c.card_id.name for c in cs.player.hand) == ["CLAW", "ZAP"]

def test_momentum_strike_is_free_afterwards():
    cs = state([gen(CardId.MOMENTUM_STRIKE)])
    play(cs)
    assert cs.player.discard_pile[0].energy_cost == 0

def test_modded_adds_a_slot_and_costs_more_each_time():
    cs = state([gen(CardId.MODDED)], draw=[gen(CardId.ZAP)])
    play(cs)
    assert cs.player.orb_slots == 4 and cs.player.discard_pile[0].energy_cost == 1

def test_genetic_algorithm_grows_and_the_deck_remembers():
    card = Card.create_copy(gen(CardId.GENETIC_ALGORITHM))
    card.deck_index = 4
    cs = state([card])
    play(cs)
    assert cs.player.block == 1 and cs.player.deck_buffs == {4: 3}
    assert cs.player.exhaust_pile[0].bonus_damage == 3

def test_adaptive_strike_leaves_a_free_copy():
    cs = state([gen(CardId.ADAPTIVE_STRIKE)])
    cs.energy = 2
    play(cs)
    assert [c.energy_cost for c in cs.player.discard_pile] == [0, 2] or sorted(c.energy_cost for c in cs.player.discard_pile) == [0, 2]

def test_reboot_shuffles_everything_into_the_draw_pile():
    cs = state([gen(CardId.REBOOT), gen(CardId.ZAP)], draw=[gen(CardId.CLAW)] * 6, discard=[gen(CardId.LEAP)])
    cs.energy = 0
    play(cs)
    assert len(cs.player.hand) == 4 and len(cs.player.draw_pile) == 4 and cs.player.discard_pile == []

def test_scavenge_exhausts_a_card_for_energy_next_turn():
    cs = state([gen(CardId.SCAVENGE), gen(CardId.ZAP), gen(CardId.CLAW)])
    sim = play(cs)
    assert cs.player.status_amount(StatusId.ENERGY_NEXT_TURN) == 2 and cs.pending_choice is not None
    sim.choose_card(0)
    assert len(cs.player.exhaust_pile) == 1

def test_hologram_returns_a_card_of_the_discard_pile():
    cs = state([gen(CardId.HOLOGRAM)], discard=[gen(CardId.CLAW), gen(CardId.LEAP)])
    sim = play(cs)
    assert cs.player.block == 3 and cs.pending_choice is not None
    sim.choose_card(0)
    assert [c.card_id for c in cs.player.hand] == [CardId.CLAW]

def test_ice_lance_chills_and_meteor_strike_channels_plasma():
    cs = state([gen(CardId.ICE_LANCE)], slots=5)
    cs.energy = 3
    play(cs)
    assert kinds(cs) == [orbs.FROST] * 3 and hp(cs) == 81
    cs = state([gen(CardId.METEOR_STRIKE)], slots=3)
    cs.energy = 5
    play(cs)
    assert kinds(cs) == [orbs.PLASMA] * 3 and hp(cs) == 76

def test_uproar_plays_an_attack_of_the_draw_pile():
    cs = state([gen(CardId.UPROAR)], draw=[gen(CardId.ZAP), gen(CardId.STRIKE_DEFECT)])
    cs.energy = 2
    play(cs)
    assert hp(cs) == 100 - 12 - 6


# ------------------------------------------------------------ the bridge
def test_the_bridge_orbs_are_read_back_without_focus():
    raw = {"max_hp": 75, "hp": 75, "block": 0, "character": "The Defect", "hand": [], "draw_pile": [], "discard_pile": [],
           "status": [{"id": "FOCUS_POWER", "amount": 2}],
           "orbs": [{"id": "LIGHTNING_ORB", "passive_val": 5, "evoke_val": 10}, {"id": "DARK_ORB", "passive_val": 8, "evoke_val": 20}], "orb_slots": 4}
    player = Player.from_dict(raw)
    assert player.orb_slots == 4 and [o.kind for o in player.orbs] == [orbs.LIGHTNING, orbs.DARK]
    assert player.orbs[0].passive == 3 and player.orbs[1].evoke == 20 and player.orbs[1].passive == 6

def test_a_defect_without_reported_slots_has_three():
    raw = {"max_hp": 75, "hp": 75, "block": 0, "character": "The Defect", "hand": [], "draw_pile": [], "discard_pile": [], "status": []}
    assert Player.from_dict(raw).orb_slots == 3


# ------------------------------------------------------------ relics
def add_relic(cs, relic_id):
    cs.player.relics[relic_id] = RelicInstance(relic_id)

def test_infused_core_adds_one_to_lightning():
    cs = state([])
    add_relic(cs, RelicId.INFUSED_CORE)
    sim = sim_of(cs)
    orbs.channel(sim, orbs.LIGHTNING)
    orbs.before_turn_end(sim)
    assert hp(cs) == 96

def test_gold_plated_cables_double_the_first_orbs_passive():
    cs = state([])
    add_relic(cs, RelicId.GOLD_PLATED_CABLES)
    sim = sim_of(cs)
    orbs.channel(sim, orbs.LIGHTNING)
    orbs.channel(sim, orbs.FROST)
    orbs.before_turn_end(sim)
    assert hp(cs) == 94 and cs.player.block == 2

def test_metronome_hits_everything_on_the_seventh_orb():
    cs = state([], enemies=2, slots=10)
    add_relic(cs, RelicId.METRONOME)
    sim = sim_of(cs)
    orbs.channel(sim, orbs.FROST, 6)
    assert hp(cs) == 100
    orbs.channel(sim, orbs.FROST)
    assert (hp(cs, 0), hp(cs, 1)) == (70, 70)

def test_emotion_chip_triggers_the_passives_after_a_turn_that_cost_hp():
    cs = state([])
    add_relic(cs, RelicId.EMOTION_CHIP)
    cs.player.orbs = [orbs.Orb(orbs.LIGHTNING)]
    sim = sim_of(cs)
    sim.fire(HookType.PLAYER_TURN_START)
    assert hp(cs) == 100
    sim.fire(HookType.HP_LOST, 3)
    sim.fire(HookType.PLAYER_TURN_START)
    assert hp(cs) == 97

def test_the_turn_one_relics_in_a_deck_built_fight():
    from sts2_lite.relic.combat_start import Opening
    cs = state([])
    sim = sim_of(cs)
    opening = Opening([{"id": "CRACKED_CORE"}, {"id": "SYMBIOTIC_VIRUS"}, {"id": "RUNIC_CAPACITOR"}], "monster", False)
    opening._orb_relics(sim)
    assert kinds(cs) == [orbs.LIGHTNING, orbs.DARK] and cs.player.orb_slots == 6

def test_relic_pool():
    from sts2_lite.relic.pool_data import POOL
    assert {r[0] for r in POOL if r[4] == "defect"} == {"CRACKED_CORE", "DATA_DISK", "EMOTION_CHIP", "GOLD_PLATED_CABLES", "POWER_CELL", "METRONOME", "RUNIC_CAPACITOR", "SYMBIOTIC_VIRUS"}


# ------------------------------------------------------------ potions
def test_defect_potions():
    cs = state([])
    sim = sim_of(cs)
    EFFECTS[PotionId.FOCUS_POTION](sim, 0)
    assert cs.player.status_amount(StatusId.FOCUS) == 2
    EFFECTS[PotionId.POTION_OF_CAPACITY](sim, 0)
    assert cs.player.orb_slots == 5
    EFFECTS[PotionId.ESSENCE_OF_DARKNESS](sim, 0)
    assert kinds(cs) == [orbs.DARK] * 5

def test_the_potion_pool():
    from sts2_lite.potion_pool import potion_pool
    assert {PotionId.FOCUS_POTION, PotionId.POTION_OF_CAPACITY, PotionId.ESSENCE_OF_DARKNESS} <= set(potion_pool("DEFECT"))
    assert PotionId.FOCUS_POTION not in potion_pool("IRONCLAD")


def test_rocket_punch_discount_lasts_until_it_is_played():
    cs = state([gen(CardId.BOOST_AWAY)], draw=[gen(CardId.ROCKET_PUNCH)])
    cs.player.hand.append(gen(CardId.ROCKET_PUNCH))
    cs.player.apply_status(StatusId.SMOKESTACK, 1)
    sim = sim_of(cs)
    sim.play_card(0, 0)       # Boost Away makes a Dazed
    punch = next(c for c in cs.player.hand if c.card_id == CardId.ROCKET_PUNCH)
    assert punch.energy_cost == 1
    cs.player.restore_free_cards()
    assert next(c for c in cs.player.hand if c.card_id == CardId.ROCKET_PUNCH).energy_cost == 1
