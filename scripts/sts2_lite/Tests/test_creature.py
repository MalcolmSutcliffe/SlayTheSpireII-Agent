"""Creature tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.creature import Creature
from sts2_lite.enemy import Enemy
from sts2_lite.player import Player
from sts2_lite.status import StatusId


# ---------------------------------------------------------------- helpers
def make_creature(hp=50, block=0):
    return Creature(max_hp=50, current_hp=hp, block=block)

def make_card(card_id, name, card_type, cost, target):
    c = Card()
    c.card_id, c.name, c.type = card_id, name, card_type
    c.energy_cost, c.target_type = cost, target
    c.is_upgraded = False
    c.is_unplayable = False
    return c

def strike():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def twin_strike():
    return make_card(CardId.TWIN_STRIKE, "Twin Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def fight_me():
    return make_card(CardId.FIGHT_ME, "Fight Me!", CardType.Attack, 2, TargetType.AnyEnemy)

def blood_wall():
    return make_card(CardId.BLOOD_WALL, "Blood Wall", CardType.Skill, 2, TargetType.Self)

def make_state(hand=None, enemy_hp=40, energy=3):
    p = Player()
    p.max_hp = p.current_hp = 50
    p.hand = list(hand or [])
    p.draw_pile = [strike() for _ in range(10)]
    e = Enemy()
    e.max_hp = e.current_hp = enemy_hp
    e.enemy_id = "TEST_ENEMY"
    e.attack_damage, e.num_attacks = 0, 1
    cs = CombatState()
    cs.player, cs.enemies = p, [e]
    cs.energy = cs.max_energy = energy
    cs.turn_number = 1
    return cs


# ---------------------------------------------------------------- apply_status
def test_apply_status_creates_status():
    c = make_creature()
    c.apply_status(StatusId.VULNERABLE, 2)
    assert StatusId.VULNERABLE in c.status
    assert c.status_amount(StatusId.VULNERABLE) == 2

def test_apply_status_stacks_same_status():
    c = make_creature()
    c.apply_status(StatusId.WEAK, 1)
    c.apply_status(StatusId.WEAK, 2)
    assert c.status_amount(StatusId.WEAK) == 3

def test_different_statuses_are_tracked_separately():
    c = make_creature()
    c.apply_status(StatusId.WEAK, 1)
    c.apply_status(StatusId.VULNERABLE, 4)
    assert c.status_amount(StatusId.WEAK) == 1
    assert c.status_amount(StatusId.VULNERABLE) == 4
    assert len(c.status) == 2

def test_negative_amounts_reduce_a_status():
    c = make_creature()
    c.apply_status(StatusId.STRENGTH, 3)
    c.apply_status(StatusId.STRENGTH, -1)
    assert c.status_amount(StatusId.STRENGTH) == 2

def test_status_amount_is_zero_when_absent():
    assert make_creature().status_amount(StatusId.THORNS) == 0

def test_status_is_stored_under_its_own_id():
    c = make_creature()
    c.apply_status(StatusId.FRAIL, 2)
    assert c.status[StatusId.FRAIL].status_id == StatusId.FRAIL

@pytest.mark.parametrize("status_id", list(StatusId))
def test_every_status_id_can_be_applied(status_id):
    c = make_creature()
    c.apply_status(status_id, 1)
    assert c.status_amount(status_id) == 1

def test_statuses_are_not_shared_between_creatures():
    a, b = make_creature(), make_creature()
    a.apply_status(StatusId.STRENGTH, 5)
    assert b.status == {}


# ---------------------------------------------------------------- apply_block
def test_apply_block_adds():
    c = make_creature()
    c.apply_block(5)
    assert c.block == 5

def test_apply_block_stacks():
    c = make_creature(block=3)
    c.apply_block(4)
    assert c.block == 7


# ---------------------------------------------------------------- apply_damage and block
# (starting block, damage) -> (expected hp lost, expected block left)
@pytest.mark.parametrize("block, damage, hp_lost, block_left", [
    (0, 10, 10, 0),    # no block: all damage goes to hp
    (5, 10, 5, 0),     # block partly absorbs; remainder hits hp
    (10, 10, 0, 0),    # block exactly equals damage
    (10, 4, 0, 6),     # block more than damage: leftover block remains
    (5, 0, 0, 5),      # zero damage changes nothing
    (0, 0, 0, 0),
])
def test_damage_against_block(block, damage, hp_lost, block_left):
    c = make_creature(hp=50, block=block)
    c.apply_damage(damage)
    assert c.current_hp == 50 - hp_lost
    assert c.block == block_left

def test_lethal_damage_sets_hp_to_zero_not_negative():
    c = make_creature(hp=10)
    c.apply_damage(99)
    assert c.current_hp == 0

def test_exactly_lethal_damage_kills():
    c = make_creature(hp=10)
    c.apply_damage(10)
    assert c.current_hp == 0

def test_block_that_absorbs_everything_prevents_death():
    c = make_creature(hp=1, block=20)
    c.apply_damage(15)
    assert c.current_hp == 1
    assert c.block == 5

def test_damage_overflowing_block_can_kill():
    c = make_creature(hp=4, block=5)
    c.apply_damage(10)       # 5 absorbed, 5 reaches 4 hp
    assert c.current_hp == 0

def test_repeated_hits_deplete_block_then_hp():
    c = make_creature(hp=50, block=6)
    c.apply_damage(4)
    assert (c.current_hp, c.block) == (50, 2)
    c.apply_damage(4)
    assert (c.current_hp, c.block) == (48, 0)


# ---------------------------------------------------------------- lose_hp / die
def test_lose_hp_ignores_block():
    c = make_creature(hp=50, block=20)
    c.lose_hp(3)
    assert c.current_hp == 47
    assert c.block == 20

def test_lose_hp_can_kill():
    c = make_creature(hp=2)
    c.lose_hp(5)
    assert c.current_hp == 0

def test_die_sets_hp_to_zero():
    c = make_creature(hp=30)
    c.die()
    assert c.current_hp == 0


# ---------------------------------------------------------------- Slippery
def test_slippery_reduces_hp_loss_to_one_and_is_consumed():
    c = make_creature(hp=50)
    c.apply_status(StatusId.SLIPPERY, 2)
    c.apply_damage(20)
    assert c.current_hp == 49
    assert c.status_amount(StatusId.SLIPPERY) == 1

def test_slippery_runs_out_then_full_damage_applies():
    c = make_creature(hp=50)
    c.apply_status(StatusId.SLIPPERY, 1)
    c.apply_damage(20)       # absorbed down to 1
    c.apply_damage(20)       # slippery is spent
    assert c.current_hp == 50 - 1 - 20

def test_slippery_applies_to_damage_left_after_block():
    c = make_creature(hp=50, block=5)
    c.apply_status(StatusId.SLIPPERY, 1)
    c.apply_damage(20)       # 15 gets through block, slippery turns it into 1
    assert c.current_hp == 49
    assert c.block == 0


def test_slippery_is_not_used_up_by_a_fully_blocked_hit():
    # block equal to damage: slippery must not trigger
    c = make_creature(hp=50, block=10)
    c.apply_status(StatusId.SLIPPERY, 1)
    c.apply_damage(10)
    assert c.current_hp == 50
    assert c.block == 0
    assert c.status_amount(StatusId.SLIPPERY) == 1

# ---------------------------------------------------------------- Skittish
def test_skittish_gives_block_after_first_attack_of_the_turn():
    c, attacker = make_creature(hp=50), make_creature()
    c.apply_status(StatusId.SKITTISH, 6)
    c.apply_attack_damage(5, attacker)
    assert c.current_hp == 45
    assert c.block == 6

def test_skittish_only_triggers_once_per_turn():
    c, attacker = make_creature(hp=50), make_creature()
    c.apply_status(StatusId.SKITTISH, 6)
    c.apply_attack_damage(5, attacker)
    c.block = 0
    c.apply_attack_damage(5, attacker)
    assert c.block == 0

def test_skittish_triggers_again_after_turn_start():
    c, attacker = make_creature(hp=50), make_creature()
    c.apply_status(StatusId.SKITTISH, 6)
    c.apply_attack_damage(5, attacker)
    c.turn_start()
    c.apply_attack_damage(5, attacker)
    assert c.block == 6

def test_skittish_triggers_on_a_fully_blocked_attack():
    c, attacker = make_creature(hp=50, block=20), make_creature()
    c.apply_status(StatusId.SKITTISH, 6)
    c.apply_attack_damage(5, attacker)
    assert c.current_hp == 50
    assert c.block == 21

def test_skittish_block_comes_after_all_hits_of_a_multi_hit_attack():
    c, attacker = make_creature(hp=50), make_creature()
    c.apply_status(StatusId.SKITTISH, 6)
    c.apply_attack_damage(5, attacker, hits=2)
    assert c.current_hp == 40
    assert c.block == 6

def test_twin_strike_is_not_blunted_by_skittish():
    cs = make_state(hand=[twin_strike()])
    cs.enemies[0].apply_status(StatusId.SKITTISH, 6)
    CombatSimulator(cs).play_card(0, 0)
    assert cs.enemies[0].current_hp == 30
    assert cs.enemies[0].block == 6

def test_fight_me_is_not_blunted_by_skittish():
    cs = make_state(hand=[fight_me()])
    cs.enemies[0].apply_status(StatusId.SKITTISH, 6)
    CombatSimulator(cs).play_card(0, 0)
    assert cs.enemies[0].current_hp == 30
    assert cs.enemies[0].block == 6


# ---------------------------------------------------------------- Thorns
def test_thorns_hurts_the_attacker():
    target, attacker = make_creature(hp=50), make_creature(hp=50)
    target.apply_status(StatusId.THORNS, 3)
    target.apply_attack_damage(10, attacker)
    assert target.current_hp == 40
    assert attacker.current_hp == 47

def test_thorns_triggers_on_every_hit_of_a_multi_hit_attack():
    target, attacker = make_creature(hp=50), make_creature(hp=50)
    target.apply_status(StatusId.THORNS, 3)
    target.apply_attack_damage(5, attacker, hits=2)
    assert attacker.current_hp == 44

def test_thorns_damage_is_absorbed_by_attacker_block():
    target, attacker = make_creature(hp=50), make_creature(hp=50, block=5)
    target.apply_status(StatusId.THORNS, 3)
    target.apply_attack_damage(10, attacker)
    assert attacker.current_hp == 50
    assert attacker.block == 2

def test_thorns_triggers_even_if_the_attack_is_fully_blocked():
    # assumes Thorns trigger on blocked attacks (as in Slay the Spire 1)
    target, attacker = make_creature(hp=50, block=20), make_creature(hp=50)
    target.apply_status(StatusId.THORNS, 3)
    target.apply_attack_damage(10, attacker)
    assert target.current_hp == 50
    assert attacker.current_hp == 47

def test_thorns_does_not_trigger_on_non_attack_damage():
    target, bystander = make_creature(hp=50), make_creature(hp=50)
    target.apply_status(StatusId.THORNS, 3)
    target.apply_damage(10)
    assert bystander.current_hp == 50

def test_attack_without_thorns_leaves_attacker_alone():
    target, attacker = make_creature(hp=50), make_creature(hp=50)
    target.apply_attack_damage(10, attacker)
    assert attacker.current_hp == 50


# ---------------------------------------------------------------- turn_start
def test_turn_start_clears_block():
    c = make_creature(block=12)
    c.turn_start()
    assert c.block == 0

def test_turn_start_resets_attacked_flag():
    c = make_creature()
    c.apply_attack_damage(1, make_creature())
    assert c.has_been_attacked_this_turn
    c.turn_start()
    assert not c.has_been_attacked_this_turn


# ---------------------------------------------------------------- cloning
def _enemy(hp=40, block=3):
    e = Enemy()
    e.max_hp, e.current_hp, e.block = 40, hp, block
    e.enemy_id, e.is_minion = "TEST_ENEMY", False
    e.attack_damage, e.num_attacks = 7, 2
    return e

def test_enemy_clone_copies_values():
    e = _enemy()
    e.apply_status(StatusId.VULNERABLE, 2)
    clone = Enemy.deepcopy(e)
    assert (clone.current_hp, clone.block, clone.max_hp) == (40, 3, 40)
    assert (clone.attack_damage, clone.num_attacks) == (7, 2)
    assert clone.status_amount(StatusId.VULNERABLE) == 2

def test_enemy_clone_is_independent():
    e = _enemy()
    e.apply_status(StatusId.VULNERABLE, 2)
    clone = Enemy.deepcopy(e)
    clone.apply_status(StatusId.VULNERABLE, 5)
    clone.apply_damage(30)
    clone.apply_block(9)
    assert e.status_amount(StatusId.VULNERABLE) == 2
    assert (e.current_hp, e.block) == (40, 3)

def test_player_clone_copies_values_and_is_independent():
    p = Player()
    p.max_hp, p.current_hp, p.block = 80, 61, 4
    p.apply_status(StatusId.DEXTERITY, 2)
    clone = Player.deepcopy(p)
    assert (clone.current_hp, clone.block, clone.max_hp) == (61, 4, 80)
    assert clone.status_amount(StatusId.DEXTERITY) == 2
    clone.apply_status(StatusId.DEXTERITY, 3)
    clone.apply_damage(10)
    assert p.status_amount(StatusId.DEXTERITY) == 2
    assert (p.current_hp, p.block) == (61, 4)


# ---------------------------------------------------------------- readable
def test_readable_mentions_hp_and_block():
    text = make_creature(hp=37, block=8).readable()
    assert "current_hp : 37" in text
    assert "block : 8" in text


# ---------------------------------------------------------------- end to end through the simulator
def test_strike_into_block_and_vulnerable():
    cs = make_state(hand=[strike()])
    cs.enemies[0].block = 4
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    CombatSimulator(cs).play_card(0, 0)
    # 6 * 1.5 = 9, 4 absorbed, 5 reaches hp
    assert cs.enemies[0].block == 0
    assert cs.enemies[0].current_hp == 35

def test_multi_hit_attack_uses_block_across_hits():
    cs = make_state(hand=[twin_strike()])
    cs.enemies[0].block = 6
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    CombatSimulator(cs).play_card(0, 0)
    # 7 per hit: 6 block, then 1 hp, then 7 hp
    assert cs.enemies[0].block == 0
    assert cs.enemies[0].current_hp == 40 - 1 - 7

def test_attacking_a_thorns_enemy_hurts_the_player():
    cs = make_state(hand=[strike()])
    cs.enemies[0].apply_status(StatusId.THORNS, 3)
    CombatSimulator(cs).play_card(0, 0)
    assert cs.enemies[0].current_hp == 34
    assert cs.player.current_hp == 47

def test_enemy_multi_attack_depletes_player_block_then_hp():
    cs = make_state()
    cs.player.block = 5
    cs.enemies[0].attack_damage, cs.enemies[0].num_attacks = 8, 2
    CombatSimulator(cs)._play_enemy_turn()
    # 16 total, 5 absorbed
    assert cs.player.block == 0
    assert cs.player.current_hp == 50 - 11

def test_blood_wall_gains_block_and_loses_hp_ignoring_block():
    cs = make_state(hand=[blood_wall()])
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.block == 16
    assert cs.player.current_hp == 48

def test_player_block_clears_at_start_of_next_turn():
    cs = make_state()
    cs.player.block = 9
    cs.player.turn_start()
    assert cs.player.block == 0
