"""Plain attacks and block of the Ironclad pool. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.events import EventType
from sts2_lite.Tests.test_cards import make_card, make_state, play, hps
from sts2_lite.status import StatusId


def card(card_id, cost=1, kind=CardType.Attack, target=TargetType.AnyEnemy, upgraded=False):
    return make_card(card_id, card_id.name.title(), kind, cost, target, upgraded)

def attack(card_id, cost=1, upgraded=False):
    return card(card_id, cost, upgraded=upgraded)

def skill(card_id, cost=1, target=TargetType.Self, upgraded=False):
    return card(card_id, cost, CardType.Skill, target, upgraded)

def vulnerable(enemy, amount):
    enemy.apply_status(StatusId.VULNERABLE, amount)

def one_enemy(hand, hp=100):
    return make_state(hand, enemy_count=1, enemy_hp=hp)

# ---------------------------------------------------------------- Break
def test_break_hits_for_twenty_and_applies_five_vulnerable():
    cs = one_enemy([attack(CardId.BREAK)])
    play(cs)
    assert hps(cs) == [80] and cs.enemies[0].status_amount(StatusId.VULNERABLE) == 5

def test_break_upgraded():
    cs = one_enemy([attack(CardId.BREAK, upgraded=True)])
    play(cs)
    assert hps(cs) == [70] and cs.enemies[0].status_amount(StatusId.VULNERABLE) == 7

def test_break_damage_ignores_the_vulnerable_it_applies():
    cs = one_enemy([attack(CardId.BREAK)])
    cs.player.apply_status(StatusId.STRENGTH, 2)
    play(cs)
    assert hps(cs) == [78]

# ---------------------------------------------------------------- Hemokinesis
def test_hemokinesis_costs_two_hp_and_deals_fifteen():
    cs = one_enemy([attack(CardId.HEMOKINESIS)])
    play(cs)
    assert hps(cs) == [85] and cs.player.current_hp == 48

def test_hemokinesis_upgraded_deals_twenty():
    cs = one_enemy([attack(CardId.HEMOKINESIS, upgraded=True)])
    play(cs)
    assert hps(cs) == [80]

def test_hemokinesis_hp_loss_ignores_block():
    cs = one_enemy([attack(CardId.HEMOKINESIS)])
    cs.player.block = 10
    play(cs)
    assert cs.player.current_hp == 48 and cs.player.block == 10

# ---------------------------------------------------------------- Dismantle
def test_dismantle_hits_once_without_vulnerable():
    cs = one_enemy([attack(CardId.DISMANTLE)])
    play(cs)
    assert hps(cs) == [92]

def test_dismantle_hits_twice_on_a_vulnerable_enemy():
    cs = one_enemy([attack(CardId.DISMANTLE)])
    vulnerable(cs.enemies[0], 1)
    play(cs)
    assert hps(cs) == [100 - 2 * 12]

def test_dismantle_upgraded_damage():
    cs = one_enemy([attack(CardId.DISMANTLE, upgraded=True)])
    play(cs)
    assert hps(cs) == [90]

# ---------------------------------------------------------------- Bully
def test_bully_is_four_without_vulnerable():
    cs = one_enemy([attack(CardId.BULLY, cost=0)])
    play(cs)
    assert hps(cs) == [96]

def test_bully_adds_two_per_vulnerable_stack():
    cs = one_enemy([attack(CardId.BULLY, cost=0)])
    vulnerable(cs.enemies[0], 2)
    play(cs)
    assert hps(cs) == [100 - int((4 + 2 * 2) * 1.5)]

def test_bully_upgraded_adds_three_per_stack():
    cs = one_enemy([attack(CardId.BULLY, cost=0, upgraded=True)])
    vulnerable(cs.enemies[0], 2)
    play(cs)
    assert hps(cs) == [100 - int((4 + 3 * 2) * 1.5)]

# ---------------------------------------------------------------- Ashen Strike
def test_ashen_strike_scales_with_the_exhaust_pile():
    cs = one_enemy([attack(CardId.ASHEN_STRIKE)])
    cs.player.exhaust_pile = [attack(CardId.BREAK), attack(CardId.BREAK)]
    play(cs)
    assert hps(cs) == [100 - (6 + 3 * 2)]

def test_ashen_strike_upgraded_scales_by_four():
    cs = one_enemy([attack(CardId.ASHEN_STRIKE, upgraded=True)])
    cs.player.exhaust_pile = [attack(CardId.BREAK)] * 3
    play(cs)
    assert hps(cs) == [100 - (6 + 4 * 3)]

def test_ashen_strike_base_damage_with_nothing_exhausted():
    cs = one_enemy([attack(CardId.ASHEN_STRIKE)])
    play(cs)
    assert hps(cs) == [94]

# ---------------------------------------------------------------- Molten Fist
def test_molten_fist_doubles_vulnerable_and_exhausts():
    cs = one_enemy([attack(CardId.MOLTEN_FIST)])
    vulnerable(cs.enemies[0], 2)
    play(cs)
    assert hps(cs) == [100 - 15] and cs.enemies[0].status_amount(StatusId.VULNERABLE) == 4
    assert [c.card_id for c in cs.player.exhaust_pile] == [CardId.MOLTEN_FIST]

def test_molten_fist_without_vulnerable_applies_none():
    cs = one_enemy([attack(CardId.MOLTEN_FIST)])
    play(cs)
    assert hps(cs) == [90] and StatusId.VULNERABLE not in cs.enemies[0].status

def test_molten_fist_upgraded_damage():
    cs = one_enemy([attack(CardId.MOLTEN_FIST, upgraded=True)])
    play(cs)
    assert hps(cs) == [86]

# ---------------------------------------------------------------- Uppercut
def test_uppercut_applies_weak_and_vulnerable():
    cs = one_enemy([attack(CardId.UPPERCUT, cost=2)])
    play(cs)
    e = cs.enemies[0]
    assert hps(cs) == [87] and (e.status_amount(StatusId.WEAK), e.status_amount(StatusId.VULNERABLE)) == (1, 1)

def test_uppercut_upgraded_applies_two_of_each():
    cs = one_enemy([attack(CardId.UPPERCUT, cost=2, upgraded=True)])
    play(cs)
    e = cs.enemies[0]
    assert (e.status_amount(StatusId.WEAK), e.status_amount(StatusId.VULNERABLE)) == (2, 2)

# ---------------------------------------------------------------- Sword Boomerang
def boomerang(upgraded=False):
    return card(CardId.SWORD_BOOMERANG, 1, target=TargetType.RandomEnemy, upgraded=upgraded)

def test_sword_boomerang_hits_three_times_for_three():
    cs = one_enemy([boomerang()])
    play(cs)
    assert hps(cs) == [91]

def test_sword_boomerang_upgraded_hits_four_times():
    cs = one_enemy([boomerang(upgraded=True)])
    play(cs)
    assert hps(cs) == [88]

def test_sword_boomerang_spreads_over_enemies_and_all_hits_land():
    cs = make_state([boomerang()], enemy_count=3, enemy_hp=100)
    play(cs)
    assert sum(100 - h for h in hps(cs)) == 9

def test_sword_boomerang_never_wastes_hits_on_the_dead():
    cs = make_state([boomerang(upgraded=True)], enemy_count=2, enemy_hp=100)
    cs.enemies[0].current_hp = 3
    play(cs)
    if len(cs.enemies) == 1:        # the weak one died on its first hit and was never targeted again
        assert cs.enemies[0].current_hp == 100 - 3 * 3
    else:                           # every hit went to the other enemy
        assert hps(cs) == [3, 100 - 3 * 4]

def test_sword_boomerang_is_offered_once_with_no_target():
    cs = make_state([boomerang()], enemy_count=3)
    actions = [a for a in CombatSimulator(cs).get_available_actions() if a["action"] == "play_card"]
    assert len(actions) == 1

def test_sword_boomerang_with_one_enemy_uses_no_randomness():
    from sts2_lite import rng
    cs = one_enemy([boomerang()])
    before = rng.calls
    play(cs)
    assert rng.calls == before

# ---------------------------------------------------------------- Whirlwind
def whirlwind(upgraded=False):
    return card(CardId.WHIRLWIND, "X", target=TargetType.AllEnemies, upgraded=upgraded)

def test_whirlwind_hits_every_enemy_x_times():
    cs = make_state([whirlwind()], enemy_count=2, enemy_hp=100)
    cs.energy = 3
    play(cs)
    assert hps(cs) == [85, 85] and cs.energy == 0

def test_whirlwind_with_no_energy_does_nothing():
    cs = make_state([whirlwind()], enemy_count=2, enemy_hp=100)
    cs.energy = 0
    play(cs)
    assert hps(cs) == [100, 100]

def test_whirlwind_upgraded_damage():
    cs = make_state([whirlwind(upgraded=True)], enemy_count=1, enemy_hp=100)
    cs.energy = 2
    play(cs)
    assert hps(cs) == [84]

def test_whirlwind_stops_hitting_enemies_that_died():
    cs = make_state([whirlwind()], enemy_count=2, enemy_hp=100)
    cs.enemies[0].current_hp = 7
    cs.energy = 3
    play(cs)
    assert hps(cs) == [85]

# ---------------------------------------------------------------- Spite
def test_spite_hits_once_when_no_hp_was_lost():
    cs = one_enemy([attack(CardId.SPITE, cost=0)])
    play(cs)
    assert hps(cs) == [95]

def test_spite_hits_twice_after_losing_hp_this_turn():
    cs = one_enemy([attack(CardId.SPITE, cost=0)])
    cs.player.lose_hp(1)
    play(cs)
    assert hps(cs) == [90]

def test_spite_upgraded_hits_three_times_after_losing_hp():
    cs = one_enemy([attack(CardId.SPITE, cost=0, upgraded=True)])
    cs.player.apply_damage(4)
    play(cs)
    assert hps(cs) == [85]

def test_blocked_damage_does_not_count_as_losing_hp():
    cs = one_enemy([attack(CardId.SPITE, cost=0)])
    cs.player.block = 10
    cs.player.apply_damage(4)
    play(cs)
    assert hps(cs) == [95]

def test_hp_lost_flag_resets_on_the_next_player_turn():
    cs = one_enemy([attack(CardId.SPITE, cost=0)])
    cs.player.lose_hp(1)
    cs.player.turn_start()
    assert not cs.player.lost_hp_this_turn

# ---------------------------------------------------------------- Cinder
def test_cinder_exhausts_a_card_from_hand():
    other = attack(CardId.STRIKE_IRONCLAD)
    cs = one_enemy([attack(CardId.CINDER, cost=2), other])
    play(cs)
    assert hps(cs) == [82]
    assert cs.player.exhaust_pile == [other] and cs.player.hand == []

def test_cinder_with_an_empty_hand_exhausts_nothing():
    cs = one_enemy([attack(CardId.CINDER, cost=2, upgraded=True)])
    play(cs)
    assert hps(cs) == [76] and cs.player.exhaust_pile == []

def test_cinder_fires_the_exhaust_event():
    seen = []
    cs = one_enemy([attack(CardId.CINDER, cost=2), attack(CardId.STRIKE_IRONCLAD)])
    sim = CombatSimulator(cs)
    original = sim.fire
    sim.fire = lambda event, *a: (seen.append(event), original(event, *a))[1]
    sim.play_card(0, 0)
    assert EventType.CARD_EXHAUSTED in seen

# ---------------------------------------------------------------- Feed
def test_feed_kill_raises_max_hp():
    cs = one_enemy([attack(CardId.FEED)], hp=10)
    play(cs)
    assert (cs.player.max_hp, cs.player.current_hp) == (53, 53) and cs.enemies == []

def test_feed_upgraded_kill_raises_max_hp_by_four():
    cs = one_enemy([attack(CardId.FEED, upgraded=True)], hp=12)
    play(cs)
    assert cs.player.max_hp == 54

def test_feed_without_a_kill_does_not():
    cs = one_enemy([attack(CardId.FEED)], hp=11)
    play(cs)
    assert cs.player.max_hp == 50

def test_feed_on_a_minion_does_not():
    cs = one_enemy([attack(CardId.FEED)], hp=10)
    cs.enemies[0].apply_status(StatusId.MINION, 1)
    play(cs)
    assert cs.player.max_hp == 50

def test_feed_exhausts():
    cs = one_enemy([attack(CardId.FEED)])
    play(cs)
    assert [c.card_id for c in cs.player.exhaust_pile] == [CardId.FEED]

# ---------------------------------------------------------------- Dominate
def test_dominate_gives_strength_equal_to_vulnerable():
    cs = one_enemy([skill(CardId.DOMINATE, target=TargetType.AnyEnemy)])
    vulnerable(cs.enemies[0], 2)
    play(cs)
    assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == 3
    assert cs.player.status_amount(StatusId.STRENGTH) == 3

def test_dominate_on_a_fresh_target_gives_one():
    cs = one_enemy([skill(CardId.DOMINATE, target=TargetType.AnyEnemy)])
    play(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == 1

def test_dominate_upgraded_and_exhausts():
    cs = one_enemy([skill(CardId.DOMINATE, target=TargetType.AnyEnemy, upgraded=True)])
    play(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == 2
    assert [c.card_id for c in cs.player.exhaust_pile] == [CardId.DOMINATE]

# ---------------------------------------------------------------- block cards
def test_impervious_blocks_thirty_and_exhausts():
    cs = one_enemy([skill(CardId.IMPERVIOUS, 2)])
    play(cs)
    assert cs.player.block == 30
    assert [c.card_id for c in cs.player.exhaust_pile] == [CardId.IMPERVIOUS]

def test_impervious_upgraded_and_frail():
    cs = one_enemy([skill(CardId.IMPERVIOUS, 2, upgraded=True)])
    cs.player.apply_status(StatusId.FRAIL, 1)
    play(cs)
    assert cs.player.block == 30

def test_evil_eye_blocks_eight_normally():
    cs = one_enemy([skill(CardId.EVIL_EYE)])
    play(cs)
    assert cs.player.block == 8

def test_evil_eye_blocks_twice_after_an_exhaust_this_turn():
    cs = one_enemy([skill(CardId.EVIL_EYE)])
    cs.player.exhaust_card(attack(CardId.STRIKE_IRONCLAD))
    play(cs)
    assert cs.player.block == 16

def test_evil_eye_upgraded_blocks_eleven():
    cs = one_enemy([skill(CardId.EVIL_EYE, upgraded=True)])
    play(cs)
    assert cs.player.block == 11

def test_exhaust_count_resets_each_turn():
    cs = one_enemy([skill(CardId.EVIL_EYE)])
    cs.player.exhaust_card(attack(CardId.STRIKE_IRONCLAD))
    cs.player.turn_start()
    assert cs.player.cards_exhausted_this_turn == 0

def test_evil_eye_counts_an_earlier_exhaust_card_played_this_turn():
    cs = one_enemy([attack(CardId.MOLTEN_FIST), skill(CardId.EVIL_EYE)])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert cs.player.block == 16

def test_taunt_blocks_and_applies_vulnerable():
    cs = one_enemy([skill(CardId.TAUNT, target=TargetType.AnyEnemy)])
    play(cs)
    assert cs.player.block == 7 and cs.enemies[0].status_amount(StatusId.VULNERABLE) == 1

def test_taunt_upgraded():
    cs = one_enemy([skill(CardId.TAUNT, target=TargetType.AnyEnemy, upgraded=True)])
    play(cs)
    assert cs.player.block == 8 and cs.enemies[0].status_amount(StatusId.VULNERABLE) == 2

# ---------------------------------------------------------------- Second Wind
def test_second_wind_exhausts_non_attacks_for_block_each():
    hand = [skill(CardId.SECOND_WIND), skill(CardId.DEFEND_IRONCLAD), skill(CardId.TAUNT),
            attack(CardId.STRIKE_IRONCLAD)]
    cs = one_enemy(hand)
    play(cs)
    assert cs.player.block == 10
    assert [c.card_id for c in cs.player.hand] == [CardId.STRIKE_IRONCLAD]
    assert len(cs.player.exhaust_pile) == 2

def test_second_wind_upgraded_gives_seven_each():
    cs = one_enemy([skill(CardId.SECOND_WIND, upgraded=True), skill(CardId.DEFEND_IRONCLAD)])
    play(cs)
    assert cs.player.block == 7

def test_second_wind_with_no_other_skills_gives_nothing():
    cs = one_enemy([skill(CardId.SECOND_WIND), attack(CardId.STRIKE_IRONCLAD)])
    play(cs)
    assert cs.player.block == 0

def test_second_wind_block_scales_with_dexterity_each_card():
    cs = one_enemy([skill(CardId.SECOND_WIND), skill(CardId.DEFEND_IRONCLAD)])
    cs.player.apply_status(StatusId.DEXTERITY, 2)
    play(cs)
    assert cs.player.block == 7

# ---------------------------------------------------------------- Bloodletting
def test_bloodletting_trades_three_hp_for_two_energy():
    cs = one_enemy([skill(CardId.BLOODLETTING, 0)])
    play(cs)
    assert cs.player.current_hp == 47 and cs.energy == 5

def test_bloodletting_upgraded_gives_three_energy():
    cs = one_enemy([skill(CardId.BLOODLETTING, 0, upgraded=True)])
    play(cs)
    assert cs.energy == 6

def test_bloodletting_sets_the_hp_lost_flag_for_spite():
    cs = one_enemy([skill(CardId.BLOODLETTING, 0), attack(CardId.SPITE, 0)])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert hps(cs) == [90]

# ---------------------------------------------------------------- loading
def test_new_cards_load_from_the_bridge_format():
    for cid in (CardId.BREAK, CardId.SWORD_BOOMERANG, CardId.WHIRLWIND):
        raw = {"id": cid.name, "name": "x", "type": "Attack", "cost": "X" if cid == CardId.WHIRLWIND else "1",
               "target_type": "RandomEnemy" if cid == CardId.SWORD_BOOMERANG else "AnyEnemy",
               "can_play": True, "is_upgraded": False}
        assert Card.from_dict(raw).card_id == cid

def test_every_new_card_has_a_play_function():
    from sts2_lite.card import GET_CARD_FUNCTION
    for cid in (CardId.BREAK, CardId.HEMOKINESIS, CardId.DISMANTLE, CardId.BULLY, CardId.ASHEN_STRIKE,
                CardId.MOLTEN_FIST, CardId.UPPERCUT, CardId.SWORD_BOOMERANG, CardId.WHIRLWIND, CardId.SPITE,
                CardId.CINDER, CardId.FEED, CardId.DOMINATE, CardId.IMPERVIOUS, CardId.EVIL_EYE,
                CardId.TAUNT, CardId.SECOND_WIND, CardId.BLOODLETTING):
        assert cid in GET_CARD_FUNCTION

# ---------------------------------------------------------------- gaps found by mutation checks
def infested_enemy(hp):
    from sts2_lite.enemy import Enemy
    e = Enemy()
    e.max_hp = e.current_hp = hp
    e.enemy_id = "INFESTED_0"
    e.attack_damage = e.num_attacks = 0
    e.apply_status(StatusId.INFESTED, 1)
    return e

def test_molten_fist_leaves_a_dead_targets_vulnerable_alone():
    cs = one_enemy([attack(CardId.MOLTEN_FIST)], hp=5)
    target = cs.enemies[0]
    vulnerable(target, 2)
    play(cs)
    assert target.status_amount(StatusId.VULNERABLE) == 2

def test_sword_boomerang_hits_enemies_summoned_by_an_earlier_hit():
    cs = one_enemy([boomerang()])
    cs.enemies = [infested_enemy(1)]
    play(cs)
    assert len(cs.enemies) == 4 and sum(e.max_hp - e.current_hp for e in cs.enemies) == 6

def test_whirlwind_hits_enemies_summoned_by_an_earlier_hit():
    cs = one_enemy([whirlwind()])
    cs.enemies = [infested_enemy(1)]
    cs.energy = 2
    play(cs)
    assert len(cs.enemies) == 4 and sum(e.max_hp - e.current_hp for e in cs.enemies) == 5 * 4

def test_cinder_with_one_card_in_hand_uses_no_randomness():
    from sts2_lite import rng
    cs = one_enemy([attack(CardId.CINDER, cost=2), attack(CardId.STRIKE_IRONCLAD)])
    before = rng.calls
    play(cs)
    assert rng.calls == before

def spy(sim):
    seen = []
    original = sim.fire
    sim.fire = lambda event, *a: (seen.append(event), original(event, *a))[1]
    return seen

def test_second_wind_fires_an_exhaust_event_per_card():
    cs = one_enemy([skill(CardId.SECOND_WIND), skill(CardId.DEFEND_IRONCLAD), skill(CardId.TAUNT)])
    sim = CombatSimulator(cs)
    seen = spy(sim)
    sim.play_card(0, 0)
    assert seen.count(EventType.CARD_EXHAUSTED) == 2

def test_turn_trackers_survive_a_state_copy():
    from sts2_lite.combat import CombatState
    cs = one_enemy([skill(CardId.EVIL_EYE)])
    cs.player.exhaust_card(attack(CardId.STRIKE_IRONCLAD))
    cs.player.lose_hp(1)
    copy = CombatState.deepcopy(cs)
    assert copy.player.cards_exhausted_this_turn == 1 and copy.player.lost_hp_this_turn

def test_cinder_exhausts_a_random_card():
    from sts2_lite import rng
    exhausted = set()
    for seed in range(30):
        rng.seed(seed)
        cs = one_enemy([attack(CardId.CINDER, cost=2), attack(CardId.STRIKE_IRONCLAD), skill(CardId.DEFEND_IRONCLAD)])
        play(cs)
        exhausted.add(cs.player.exhaust_pile[0].card_id)
    assert exhausted == {CardId.STRIKE_IRONCLAD, CardId.DEFEND_IRONCLAD}
