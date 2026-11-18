"""The Silent's Rare cards and their powers (values from the decompiled Models.Cards / Models.Powers)."""
import pytest

from sts2_lite.card import Card, CardId, CardKeyword, CardType, EnchantmentId, TargetType
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

def fill_draw(cs, n=10, card_id=CardId.SLICE):
    cs.player.draw_pile = [gen(card_id) for _ in range(n)]


@pytest.mark.parametrize("card_id, cost, upgraded_cost", [(CardId.BULLET_TIME, 3, 2), (CardId.MURDER, 3, 2), (CardId.NIGHTMARE, 3, 2),
                                                          (CardId.SHADOW_STEP, 1, 0), (CardId.WELL_LAID_PLANS, 2, 1), (CardId.TRACKING, 2, 1)])
def test_upgrades_that_lower_the_cost(card_id, cost, upgraded_cost):
    assert (gen(card_id).energy_cost, gen(card_id, True).energy_cost) == (cost, upgraded_cost)

def test_keywords():
    assert gen(CardId.ABRASIVE).sly
    assert {CardKeyword.INNATE, CardKeyword.EXHAUST} <= gen(CardId.ASSASSINATE).keywords
    assert CardKeyword.INNATE in gen(CardId.AFTERIMAGE, True).keywords and CardKeyword.INNATE not in gen(CardId.AFTERIMAGE).keywords
    for cid in (CardId.ADRENALINE, CardId.MALAISE, CardId.NIGHTMARE, CardId.THE_HUNT):
        assert gen(cid).exhausts, cid
    assert gen(CardId.MALAISE).energy_cost == "X"


# ------------------------------------------------------------ attacks
def test_assassinate():
    cs = state([gen(CardId.ASSASSINATE, True)])
    play(cs)
    assert cs.enemies[0].current_hp == 87 and cs.enemies[0].status_amount(StatusId.VULNERABLE) == 2

def test_grand_finale_only_with_an_empty_draw_pile():
    cs = state([gen(CardId.GRAND_FINALE)], enemies=2, hp=100)
    fill_draw(cs, 1)
    sim = CombatSimulator(cs)
    assert not any(a["action"] == "play_card" for a in sim.get_available_actions())
    cs.player.draw_pile = []
    sim.play_card(0, 0)
    assert [e.current_hp for e in cs.enemies] == [40, 40]

def test_murder_counts_every_card_drawn_this_combat():
    cs = state([gen(CardId.MURDER), gen(CardId.BACKFLIP)])
    fill_draw(cs, 5)
    cs.energy = 5
    sim = play(cs, 1)
    assert cs.player.cards_drawn == 2
    sim.play_card(next(i for i, c in enumerate(cs.player.hand) if c.card_id == CardId.MURDER), 0)
    assert cs.enemies[0].current_hp == 100 - 3

def test_the_hunt_marks_a_kill():
    cs = state([gen(CardId.THE_HUNT)], hp=8)
    play(cs)
    assert StatusId.THE_HUNT in cs.player.status
    cs = state([gen(CardId.THE_HUNT)], enemies=2, hp=30)
    play(cs)
    assert StatusId.THE_HUNT not in cs.player.status


# ------------------------------------------------------------ skills
def test_adrenaline():
    cs = state([gen(CardId.ADRENALINE, True)])
    fill_draw(cs)
    play(cs)
    assert cs.energy == 5 and len(cs.player.hand) == 2

def test_blade_of_ink_shivs_weaken():
    cs = state([gen(CardId.BLADE_OF_INK)])
    sim = play(cs)
    assert ids(cs.player.hand) == [CardId.SHIV] * 2 and all(c.enchantment == EnchantmentId.INKY for c in cs.player.hand)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 96 and cs.enemies[0].status_amount(StatusId.WEAK) == 1

def test_bullet_time_makes_the_hand_free_and_stops_draws():
    cs = state([gen(CardId.BULLET_TIME), gen(CardId.PREDATOR), gen(CardId.SKEWER), gen(CardId.BACKFLIP)])
    fill_draw(cs)
    sim = play(cs)
    assert cs.energy == 0 and [c.energy_cost for c in cs.player.hand] == [0, "X", 0]
    sim.play_card(2, 0)
    assert len(cs.player.hand) == 2         # Backflip drew nothing
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 85
    sim.end_turn()
    assert StatusId.NO_DRAW not in cs.player.status

def test_burst_plays_the_next_skill_twice():
    cs = state([gen(CardId.BURST), gen(CardId.DEFLECT), gen(CardId.DEFLECT)])
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.block == 8 and StatusId.BURST not in cs.player.status
    sim.play_card(0, 0)
    assert cs.player.block == 12

def test_burst_wears_off_at_the_end_of_the_turn():
    cs = state([gen(CardId.BURST, True)])
    sim = play(cs)
    sim.end_turn()
    assert StatusId.BURST not in cs.player.status

def test_corrosive_wave_poisons_on_every_draw_this_turn():
    cs = state([gen(CardId.CORROSIVE_WAVE), gen(CardId.BACKFLIP)], enemies=2)
    fill_draw(cs)
    sim = play(cs)
    sim.play_card(0, 0)
    assert all(e.status_amount(StatusId.POISON) == 4 for e in cs.enemies)
    sim.end_turn()
    assert StatusId.CORROSIVE_WAVE not in cs.player.status

def test_knife_trap_plays_the_exhausted_shivs_at_the_target():
    cs = state([gen(CardId.KNIFE_TRAP, True)], enemies=2)
    cs.player.exhaust_pile = [gen(CardId.SHIV), gen(CardId.SHIV), gen(CardId.STRIKE_SILENT)]
    play(cs, 0, 1)
    assert cs.enemies[1].current_hp == 100 - 2 * 6 and cs.enemies[0].current_hp == 100
    assert ids(cs.player.exhaust_pile).count(CardId.SHIV) == 2

@pytest.mark.parametrize("upgraded, energy, amount", [(False, 3, 3), (True, 2, 3), (False, 0, 0)])
def test_malaise(upgraded, energy, amount):
    cs = state([gen(CardId.MALAISE, upgraded)])
    cs.energy = energy
    play(cs)
    e = cs.enemies[0]
    assert e.status_amount(StatusId.STRENGTH) == -amount and e.status_amount(StatusId.WEAK) == amount

def test_nightmare_puts_three_copies_in_the_next_hand():
    cs = state([gen(CardId.NIGHTMARE), gen(CardId.PREDATOR), gen(CardId.DEFLECT)])
    fill_draw(cs, 10, CardId.DEFEND_SILENT)
    sim = play(cs)
    pick(sim, CardId.PREDATOR)
    assert cs.player.status_amount(StatusId.NIGHTMARE) == 3
    sim.end_turn()
    assert ids(cs.player.hand).count(CardId.PREDATOR) == 3 and len(cs.player.hand) == 8
    assert StatusId.NIGHTMARE not in cs.player.status and not cs.player.nightmares

def test_outbreak_poisons_then_triggers_it():
    cs = state([gen(CardId.OUTBREAK)], enemies=2)
    cs.enemies[0].apply_status(StatusId.POISON, 1)
    play(cs)
    assert [e.current_hp for e in cs.enemies] == [90, 91]
    assert [e.status_amount(StatusId.POISON) for e in cs.enemies] == [9, 8]

def test_shadow_step_discards_the_hand_then_doubles_next_turns_damage():
    cs = state([gen(CardId.SHADOW_STEP), gen(CardId.STRIKE_SILENT), gen(CardId.FLICK_FLACK)])
    fill_draw(cs, 10, CardId.STRIKE_SILENT)
    sim = play(cs)
    assert not cs.player.hand and cs.enemies[0].current_hp == 93          # the Sly Flick-Flack played
    sim.end_turn()
    assert cs.player.status_amount(StatusId.DOUBLE_DAMAGE) == 1
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 93 - 12
    sim.end_turn()
    assert StatusId.DOUBLE_DAMAGE not in cs.player.status

def test_shadowmeld_doubles_block_this_turn():
    cs = state([gen(CardId.SHADOWMELD), gen(CardId.DEFEND_SILENT), gen(CardId.DEFEND_SILENT)])
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.block == 10
    sim.end_turn()
    assert StatusId.SHADOWMELD not in cs.player.status

def test_storm_of_steel_turns_the_hand_into_shivs():
    cs = state([gen(CardId.STORM_OF_STEEL, True), gen(CardId.STRIKE_SILENT), gen(CardId.DEFEND_SILENT), gen(CardId.SLICE)])
    play(cs)
    assert ids(cs.player.hand) == [CardId.SHIV] * 3 and all(c.is_upgraded for c in cs.player.hand)
    assert cs.player.discards_this_turn == 3


# ------------------------------------------------------------ powers
def test_abrasive():
    cs = state([gen(CardId.ABRASIVE, True)])
    play(cs)
    assert cs.player.status_amount(StatusId.DEXTERITY) == 1 and cs.player.status_amount(StatusId.THORNS) == 6

def test_afterimage_blocks_after_every_later_card():
    cs = state([gen(CardId.AFTERIMAGE), gen(CardId.SLICE), gen(CardId.SLICE)])
    cs.player.status.clear()
    sim = play(cs)
    assert cs.player.block == 0             # not on its own play
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert cs.player.block == 2

def test_afterimage_block_ignores_dexterity():
    cs = state([gen(CardId.AFTERIMAGE), gen(CardId.SLICE)])
    cs.player.apply_status(StatusId.DEXTERITY, 3)
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.block == 1

def test_second_afterimage_only_adds_from_the_next_card():
    cs = state([gen(CardId.AFTERIMAGE), gen(CardId.AFTERIMAGE), gen(CardId.SLICE)])
    cs.energy = 3
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.block == 1
    sim.play_card(0, 0)
    assert cs.player.block == 3

def test_envenom_poisons_on_unblocked_attack_damage():
    cs = state([gen(CardId.ENVENOM), gen(CardId.STRIKE_SILENT), gen(CardId.STRIKE_SILENT)])
    cs.energy = 4
    sim = play(cs)
    cs.enemies[0].block = 10
    sim.play_card(0, 0)
    assert StatusId.POISON not in cs.enemies[0].status
    sim.play_card(0, 0)
    assert cs.enemies[0].status_amount(StatusId.POISON) == 1

def test_fan_of_knives_shivs_hit_everyone():
    cs = state([gen(CardId.SHIV), gen(CardId.FAN_OF_KNIVES)], enemies=3)
    sim = play(cs, 1)
    assert ids(cs.player.hand) == [CardId.SHIV] * 5
    assert all(c.target_type == TargetType.AllEnemies for c in cs.player.hand)
    sim.play_card(0, 0)
    assert [e.current_hp for e in cs.enemies] == [96, 96, 96]

def test_fan_of_knives_retargets_loaded_shivs():
    """A state loaded from the game under Fan of Knives (Player.from_dict calls fan_shivs)."""
    cs = state([gen(CardId.SHIV)])
    cs.player.draw_pile = [gen(CardId.SHIV)]
    cs.player.fan_shivs()
    assert all(c.target_type == TargetType.AllEnemies for c in cs.player.hand + cs.player.draw_pile)

def test_master_planner_makes_played_skills_sly():
    cs = state([gen(CardId.MASTER_PLANNER), gen(CardId.DEFLECT)])
    sim = play(cs)
    sim.play_card(0, 0)
    deflect = next(c for c in cs.player.discard_pile if c.card_id == CardId.DEFLECT)
    assert deflect.sly

def test_serpent_form_hits_a_random_enemy_after_each_later_card():
    cs = state([gen(CardId.SERPENT_FORM), gen(CardId.DEFLECT)], enemies=2)
    sim = play(cs)
    assert sum(e.current_hp for e in cs.enemies) == 200
    sim.play_card(0, 0)
    assert sum(e.current_hp for e in cs.enemies) == 196

def test_tools_of_the_trade_draws_one_more_then_discards_one():
    cs = state([gen(CardId.TOOLS_OF_THE_TRADE)])
    cs.player.draw_pile = [gen(CardId.SLICE), gen(CardId.DEFLECT)] * 5
    sim = play(cs)
    sim.end_turn()
    assert len(cs.player.hand) == 6 and cs.pending_choice is not None and cs.pending_choice.kind == "discard"
    sim.choose_card(cs.pending_choice.indices[0])
    assert len(cs.player.hand) == 5

def test_tracking_against_weak_enemies():
    cs = state([gen(CardId.TRACKING), gen(CardId.SLICE), gen(CardId.SLICE)], enemies=2)
    sim = play(cs)
    cs.enemies[0].apply_status(StatusId.WEAK, 1)
    sim.play_card(0, 0)
    sim.play_card(0, 1)
    assert [e.current_hp for e in cs.enemies] == [91, 94]

def test_well_laid_plans_keeps_the_hand():
    cs = state([gen(CardId.WELL_LAID_PLANS), gen(CardId.STRIKE_SILENT), gen(CardId.DEFEND_SILENT)])
    fill_draw(cs)
    sim = play(cs)
    sim.end_turn()
    assert ids(cs.player.hand)[:2] == [CardId.STRIKE_SILENT, CardId.DEFEND_SILENT] and len(cs.player.hand) == 7

def test_silent_reward_pool_has_rares():
    from sts2_lite.rewards.cards import card_pool
    assert len(card_pool("SILENT")["Rare"]) == 25           # SilentCardPool's 27 minus the multiplayer-only Flanking and Sneaky

@pytest.mark.parametrize("status", ["AFTERIMAGE", "BURST", "CORROSIVE_WAVE", "ENVENOM", "FAN_OF_KNIVES", "MASTER_PLANNER", "NIGHTMARE",
                                    "SERPENT_FORM", "SHADOW_STEP", "SHADOWMELD", "TOOLS_OF_THE_TRADE", "TRACKING", "WELL_LAID_PLANS",
                                    "THE_HUNT", "DOUBLE_DAMAGE"])
def test_powers_load_from_bridge_ids(status):
    from sts2_lite.status import status_id_of
    assert status_id_of(status + "_POWER") is StatusId[status]
