"""Relics that react to what happens: Centennial Puzzle, Gremlin Horn, Pendulum, The Abacus, Unceasing Top, Demon Tongue,
Red Skull and Self-Forming Clay. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.combat import CombatSimulator
from sts2_lite.relic import RelicId, RelicInstance
from sts2_lite.status import StatusId
from sts2_lite.Tests.test_relics_always_on import bloodletting, defend, enemy_attack, relic, state, strike
from sts2_lite.Tests.test_relics_counters import draw_pile, status, with_counter


def hurt_by_card(*relic_ids, hp=50, hand=None):
    cs = draw_pile(state(hand if hand is not None else [bloodletting(), defend(), defend()], *relic_ids))
    cs.player.current_hp, cs.player.max_hp = hp, 80
    return cs

def run(cs, *plays):
    sim = CombatSimulator(cs)
    for index, target in plays:
        sim.play_card(index, target)
    return sim

def to_enemy_turn(cs, damage=5):
    enemy_attack(cs, damage)
    CombatSimulator(cs).end_turn()
    return cs


def test_new_relics_load():
    for name in ["CENTENNIAL_PUZZLE", "GREMLIN_HORN", "PENDULUM", "THE_ABACUS", "UNCEASING_TOP", "DEMON_TONGUE", "RED_SKULL",
                 "SELF_FORMING_CLAY"]:
        assert RelicInstance.from_dict({"id": name, "counter": None, "status": "Normal"}) is not None

def test_red_skull_status_active_means_the_strength_is_on():
    assert RelicInstance.from_dict({"id": "RED_SKULL", "status": "Active"}).used
    assert not RelicInstance.from_dict({"id": "RED_SKULL", "status": "Normal"}).used

def test_demon_tongue_and_centennial_puzzle_read_spent():
    assert RelicInstance.from_dict({"id": "CENTENNIAL_PUZZLE", "status": "Normal", "spent": True}).used
    assert RelicInstance.from_dict({"id": "DEMON_TONGUE", "status": "Normal", "spent": True}).used


# ---------------------------------------------------------------- Centennial Puzzle
def test_centennial_puzzle_draws_three_the_first_time_hit_points_are_lost():
    cs = hurt_by_card(RelicId.CENTENNIAL_PUZZLE)
    run(cs, (0, 0))
    assert len(cs.player.hand) == 2 + 3 and relic(cs, RelicId.CENTENNIAL_PUZZLE).used

def test_centennial_puzzle_only_works_once_a_fight():
    cs = hurt_by_card(RelicId.CENTENNIAL_PUZZLE, hand=[bloodletting(), bloodletting()])
    run(cs, (0, 0))
    hand = len(cs.player.hand)
    run(cs, (0, 0))
    assert len(cs.player.hand) == hand - 1

def test_centennial_puzzle_does_not_fire_without_hp_loss():
    cs = hurt_by_card(RelicId.CENTENNIAL_PUZZLE)
    run(cs, (1, 0))
    assert len(cs.player.hand) == 2 and not relic(cs, RelicId.CENTENNIAL_PUZZLE).used

def test_centennial_puzzle_ignores_blocked_damage():
    cs = hurt_by_card(RelicId.CENTENNIAL_PUZZLE)
    cs.player.block = 20
    to_enemy_turn(cs, 5)
    assert not relic(cs, RelicId.CENTENNIAL_PUZZLE).used

def test_centennial_puzzle_draws_when_an_enemy_hits_the_player():
    cs = hurt_by_card(RelicId.CENTENNIAL_PUZZLE, hand=[defend()])
    to_enemy_turn(cs, 5)
    assert relic(cs, RelicId.CENTENNIAL_PUZZLE).used
    assert len(cs.player.hand) == 5 + 3          # 3 on the hit, 5 for the new turn


# ---------------------------------------------------------------- Gremlin Horn
def test_gremlin_horn_gives_energy_and_a_card_for_each_kill():
    cs = draw_pile(state([strike()], RelicId.GREMLIN_HORN, enemy_hp=1))
    run(cs, (0, 0))
    assert cs.energy == 3 - 1 + 1 and len(cs.player.hand) == 1

def test_gremlin_horn_counts_every_enemy_that_dies():
    cs = draw_pile(state([strike()], RelicId.GREMLIN_HORN, enemies=2, enemy_hp=1))
    cs.enemies[1].current_hp = 50
    run(cs, (0, 0))
    assert cs.energy == 3 and len(cs.player.hand) == 1

def test_gremlin_horn_does_nothing_without_a_kill():
    cs = draw_pile(state([strike()], RelicId.GREMLIN_HORN))
    run(cs, (0, 0))
    assert cs.energy == 2 and len(cs.player.hand) == 0


# ---------------------------------------------------------------- Pendulum
@pytest.mark.parametrize("counter, drawn, expected", [(2, 6, 0), (0, 5, 1), (1, 5, 2), (3, 5, 1)])   # 3: read while it flashed
def test_pendulum_draws_every_third_turn(counter, drawn, expected):
    cs = with_counter(draw_pile(state([defend()], RelicId.PENDULUM)), RelicId.PENDULUM, counter)
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == drawn and relic(cs, RelicId.PENDULUM).counter == expected


# ---------------------------------------------------------------- The Abacus
def test_the_abacus_gives_block_when_the_deck_is_shuffled():
    cs = state([defend()], RelicId.THE_ABACUS)
    cs.player.draw_pile = [strike() for _ in range(2)]
    cs.player.discard_pile = [strike() for _ in range(8)]
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 6

def test_the_abacus_gives_nothing_without_a_shuffle():
    cs = draw_pile(state([defend()], RelicId.THE_ABACUS))
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 0


# ---------------------------------------------------------------- Unceasing Top
def test_unceasing_top_draws_when_the_last_card_is_played():
    cs = draw_pile(state([defend()], RelicId.UNCEASING_TOP))
    run(cs, (0, 0))
    assert len(cs.player.hand) == 1

def test_unceasing_top_waits_for_the_hand_to_empty():
    cs = draw_pile(state([defend(), defend()], RelicId.UNCEASING_TOP))
    run(cs, (0, 0))
    assert len(cs.player.hand) == 1 and cs.player.hand[0].card_id.name == "DEFEND_IRONCLAD"

def test_unceasing_top_does_not_draw_for_a_refused_play():
    cs = draw_pile(state([strike()], RelicId.UNCEASING_TOP))
    with pytest.raises(ValueError):
        CombatSimulator(cs).play_card(0, 5)
    assert len(cs.player.hand) == 1


# ---------------------------------------------------------------- Demon Tongue
def test_demon_tongue_heals_the_first_hp_loss_in_the_turn():
    cs = hurt_by_card(RelicId.DEMON_TONGUE, hand=[bloodletting(), bloodletting()])
    run(cs, (0, 0))
    assert cs.player.current_hp == 50 and relic(cs, RelicId.DEMON_TONGUE).used
    run(cs, (0, 0))
    assert cs.player.current_hp == 47

def test_demon_tongue_cannot_heal_past_max_hp():
    cs = hurt_by_card(RelicId.DEMON_TONGUE, hp=80)
    run(cs, (0, 0))
    assert cs.player.current_hp == 80

def test_demon_tongue_ignores_the_enemy_turn():
    cs = hurt_by_card(RelicId.DEMON_TONGUE, hand=[defend()])
    to_enemy_turn(cs, 5)
    assert cs.player.current_hp == 45

def test_demon_tongue_is_ready_again_next_turn():
    cs = hurt_by_card(RelicId.DEMON_TONGUE, hand=[bloodletting()])
    run(cs, (0, 0))
    cs.player.draw_pile = [bloodletting() for _ in range(20)]
    CombatSimulator(cs).end_turn()
    assert not relic(cs, RelicId.DEMON_TONGUE).used


# ---------------------------------------------------------------- Red Skull
def test_red_skull_gives_strength_at_half_hit_points_or_less():
    cs = hurt_by_card(RelicId.RED_SKULL, hp=43)
    run(cs, (0, 0))          # 43 - 3 = 40 of 80
    assert status(cs, StatusId.STRENGTH) == 3 and relic(cs, RelicId.RED_SKULL).used

def test_red_skull_needs_half_or_less_not_more():
    cs = hurt_by_card(RelicId.RED_SKULL, hp=44)
    run(cs, (0, 0))          # 41 of 80
    assert status(cs, StatusId.STRENGTH) == 0

def test_red_skull_takes_the_strength_back_when_hit_points_recover():
    cs = hurt_by_card(RelicId.RED_SKULL, hp=40)
    cs.player.relics[RelicId.RED_SKULL].used = True
    cs.player.apply_status(StatusId.STRENGTH, 3)
    cs.player.current_hp = 60
    CombatSimulator(cs)._sync_hp()
    assert status(cs, StatusId.STRENGTH) == 0 and not relic(cs, RelicId.RED_SKULL).used

def test_red_skull_does_not_stack():
    cs = hurt_by_card(RelicId.RED_SKULL, hp=30, hand=[bloodletting(), bloodletting()])
    cs.player.relics[RelicId.RED_SKULL].used = True
    cs.player.apply_status(StatusId.STRENGTH, 3)
    run(cs, (0, 0), (0, 0))
    assert status(cs, StatusId.STRENGTH) == 3

def test_red_skull_is_taken_from_the_state_not_remembered():
    old = hurt_by_card(RelicId.RED_SKULL)
    old.player.relics[RelicId.RED_SKULL].used = True
    new = hurt_by_card(RelicId.RED_SKULL)
    new.carry_combat_counters(old)
    assert not relic(new, RelicId.RED_SKULL).used


# ---------------------------------------------------------------- Self-Forming Clay
def test_self_forming_clay_gives_block_next_turn_for_each_hit():
    cs = hurt_by_card(RelicId.SELF_FORMING_CLAY, hand=[defend()])
    enemy_attack(cs, 5, hits=2)
    CombatSimulator(cs).end_turn()
    assert cs.player.block == 6 and status(cs, StatusId.SELF_FORMING_CLAY) == 0

def test_self_forming_clay_works_for_hp_lost_to_a_card():
    cs = hurt_by_card(RelicId.SELF_FORMING_CLAY)
    run(cs, (0, 0))
    assert status(cs, StatusId.SELF_FORMING_CLAY) == 3

def test_self_forming_clay_ignores_blocked_hits():
    cs = hurt_by_card(RelicId.SELF_FORMING_CLAY, hand=[defend()])
    cs.player.block = 20
    to_enemy_turn(cs, 5)
    assert cs.player.block == 0 or cs.player.block == 15 - 15
