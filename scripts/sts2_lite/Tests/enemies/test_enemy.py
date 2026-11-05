"""Enemy attack tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy import Enemy
from sts2_lite.player import Player
from sts2_lite.status import StatusId


# ---------------------------------------------------------------- helpers
def make_state(attack_damage=8, num_attacks=2, player_hp=50):
    p = Player()
    p.max_hp = p.current_hp = player_hp
    e = Enemy()
    e.max_hp = e.current_hp = 40
    e.enemy_id = "TEST_ENEMY"
    e.attack_damage, e.num_attacks = attack_damage, num_attacks
    cs = CombatState()
    cs.player, cs.enemies = p, [e]
    cs.energy = cs.max_energy = 3
    cs.turn_number = 1
    return cs

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def bridge_state(label="8x2", intent_type="Attack", enemy_status=(), player_status=()):
    return {
        "round": 1, "energy": 3, "max_energy": 3,
        "player": {"max_hp": 80, "hp": 80, "block": 0, "status": list(player_status),
                   "hand": [], "draw_pile": [], "discard_pile": [], "deck": []},
        "enemies": [{"entity_id": "SEAPUNK_0", "max_hp": 45, "hp": 45, "block": 0,
                     "status": list(enemy_status),
                     "intents": [{"type": intent_type, "label": label}]}],
    }

def status(name, amount):
    return {"id": name + "_POWER", "amount": amount}


# ---------------------------------------------------------------- performing attacks
def test_multi_attack_hits_every_time():
    cs = make_state(attack_damage=8, num_attacks=2)
    enemy_turn(cs)
    assert cs.player.current_hp == 50 - 16

def test_single_attack():
    cs = make_state(attack_damage=7, num_attacks=1)
    enemy_turn(cs)
    assert cs.player.current_hp == 43

def test_enemy_strength_adds_to_every_hit():
    cs = make_state(attack_damage=6, num_attacks=3)
    cs.enemies[0].apply_status(StatusId.STRENGTH, 2)
    enemy_turn(cs)
    assert cs.player.current_hp == 50 - 3 * 8

def test_enemy_weak_reduces_every_hit():
    cs = make_state(attack_damage=10, num_attacks=2)
    cs.enemies[0].apply_status(StatusId.WEAK, 1)
    enemy_turn(cs)
    assert cs.player.current_hp == 50 - 2 * 7

def test_player_vulnerable_increases_every_hit():
    cs = make_state(attack_damage=10, num_attacks=2)
    cs.player.apply_status(StatusId.VULNERABLE, 1)
    enemy_turn(cs)
    assert cs.player.current_hp == 50 - 2 * 15

def test_block_is_used_up_across_hits():
    cs = make_state(attack_damage=5, num_attacks=3)
    cs.player.block = 10
    enemy_turn(cs)
    assert cs.player.block == 0
    assert cs.player.current_hp == 50 - 5

def test_player_thorns_hurt_the_enemy_on_every_hit():
    cs = make_state(attack_damage=5, num_attacks=3)
    cs.player.apply_status(StatusId.THORNS, 2)
    enemy_turn(cs)
    assert cs.enemies[0].current_hp == 40 - 6

def test_enemy_without_an_attack_does_nothing():
    cs = make_state(attack_damage=0, num_attacks=0)
    cs.player.apply_status(StatusId.THORNS, 2)
    enemy_turn(cs)
    assert cs.player.current_hp == 50
    assert cs.enemies[0].current_hp == 40
    assert not cs.player.has_been_attacked_this_turn

def test_ritual_raises_damage_on_the_next_turn():
    cs = make_state(attack_damage=6, num_attacks=1)
    cs.enemies[0].apply_status(StatusId.RITUAL, 2)
    sim = CombatSimulator(cs)
    sim._play_enemy_turn()
    assert cs.player.current_hp == 50 - 6
    sim._play_enemy_turn()
    assert cs.player.current_hp == 50 - 6 - 8

def test_lethal_multi_attack_leaves_player_at_zero():
    cs = make_state(attack_damage=20, num_attacks=3, player_hp=30)
    enemy_turn(cs)
    assert cs.player.current_hp == 0


# ---------------------------------------------------------------- reading intents from the bridge
def test_plain_intent_label():
    cs = CombatState.from_dict(bridge_state(label="8x2"))
    e = cs.enemies[0]
    assert (e.attack_damage, e.num_attacks) == (8, 2)

def test_single_hit_label_without_multiplier():
    e = CombatState.from_dict(bridge_state(label="12")).enemies[0]
    assert (e.attack_damage, e.num_attacks) == (12, 1)

def test_non_attack_intent_has_no_attacks():
    e = CombatState.from_dict(bridge_state(label="", intent_type="Buff")).enemies[0]
    assert (e.attack_damage, e.num_attacks) == (0, 0)

def test_displayed_damage_is_converted_to_base():
    # displayed 15 = (8 + 2) * 1.5 with enemy Strength 2 and player Vulnerable
    cs = CombatState.from_dict(bridge_state(
        label="15x2",
        enemy_status=[status("STRENGTH", 2)],
        player_status=[status("VULNERABLE", 1)]))
    assert cs.enemies[0].attack_damage == 8

def test_weak_enemy_intent_converts_to_the_largest_base():
    cs = CombatState.from_dict(bridge_state(label="3x1", enemy_status=[status("WEAK", 1)]))
    assert cs.enemies[0].attack_damage == 5

def test_simulated_attack_matches_the_displayed_damage():
    cs = CombatState.from_dict(bridge_state(
        label="15x2",
        enemy_status=[status("STRENGTH", 2)],
        player_status=[status("VULNERABLE", 1)]))
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 30

def test_conversion_survives_cloning():
    cs = CombatState.from_dict(bridge_state(label="15x2", enemy_status=[status("STRENGTH", 2)],
                                            player_status=[status("VULNERABLE", 1)]))
    clone = CombatState.deepcopy(cs)
    assert clone.enemies[0].attack_damage == cs.enemies[0].attack_damage == 8
    assert clone.enemies[0].num_attacks == 2
