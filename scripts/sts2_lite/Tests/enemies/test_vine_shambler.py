"""Vine Shambler and Tangled tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.card import CardType
from sts2_lite.combat import CombatSimulator, CombatState, IllegalActionError
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId


def shambler(name):
    return captures.load("vine_shambler", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def index_of(cs, card_id):
    return next(i for i, c in enumerate(cs.player.hand) if c.card_id.name == card_id)

def tangle(cs, amount=1):
    cs.player.apply_status(StatusId.TANGLED, amount)

# ---------------------------------------------------------------- table
def test_vine_shambler_has_a_table():
    assert "VINE_SHAMBLER" in MOVE_TABLES

def test_vine_shambler_values():
    t = MOVE_TABLES["VINE_SHAMBLER"](0)
    assert (t["SWIPE"].damage, t["SWIPE"].hits) == (6, 2)
    assert (t["GRASPING_VINES"].damage, t["GRASPING_VINES"].hits) == (8, 1)
    assert (t["CHOMP"].damage, t["CHOMP"].hits) == (16, 1)
    assert t["GRASPING_VINES"].player_status == ((StatusId.TANGLED, 1),)

def test_vine_shambler_hits_harder_on_high_ascension():
    t = MOVE_TABLES["VINE_SHAMBLER"]
    assert (t(9)["SWIPE"].damage, t(9)["GRASPING_VINES"].damage, t(9)["CHOMP"].damage) == (7, 9, 18)
    assert (t(8)["SWIPE"].damage, t(8)["GRASPING_VINES"].damage, t(8)["CHOMP"].damage) == (6, 8, 16)

def test_vine_shambler_cycle():
    t = MOVE_TABLES["VINE_SHAMBLER"](0)
    assert (t["SWIPE"].next_move, t["GRASPING_VINES"].next_move, t["CHOMP"].next_move) == \
           ("GRASPING_VINES", "CHOMP", "SWIPE")

# ---------------------------------------------------------------- reading the bridge
@pytest.mark.parametrize("name, move, damage, hits", [
    ("swipe", "SWIPE", 6, 2),
    ("grasping_vines", "GRASPING_VINES", 8, 1),
    ("chomp_and_debuff", "CHOMP", 16, 1),
])
def test_moves_are_identified_from_captures(name, move, damage, hits):
    e = shambler(name).enemies[0]
    assert (e.move_id, e.attack_damage, e.num_attacks) == (move, damage, hits)

def test_capture_costs_are_stored_without_tangled():
    cs = shambler("chomp_and_debuff")
    assert cs.player.status_amount(StatusId.TANGLED) == 1
    attacks = [c for c in cs.player.hand + cs.player.draw_pile if c.type == CardType.Attack]
    assert [c.energy_cost for c in attacks] == [1, 2, 1, 1, 1, 1, 1, 2]

def test_capture_costs_match_the_bridge_while_tangled():
    cs = shambler("chomp_and_debuff")
    assert [c.current_cost(cs.player) for c in cs.player.hand] == [2, 3, 2, 2, 1]

# ---------------------------------------------------------------- the cycle
def test_swipe_hits_twice_then_vines_hit_and_tangle():
    cs = shambler("swipe")
    enemy_turn(cs)
    assert cs.player.current_hp == 44 - 12
    assert cs.enemies[0].move_id == "GRASPING_VINES"
    enemy_turn(cs)
    assert cs.player.current_hp == 44 - 12 - 8
    assert cs.player.status_amount(StatusId.TANGLED) == 1
    assert cs.enemies[0].move_id == "CHOMP"

def test_chomp_then_swipe_again():
    cs = shambler("chomp_and_debuff")
    enemy_turn(cs)
    assert cs.player.current_hp == 44 - 16
    assert cs.enemies[0].move_id == "SWIPE"

def test_vines_make_the_next_turn_costlier_then_wear_off():
    cs = shambler("grasping_vines")
    sim = CombatSimulator(cs)
    rng.seed(1)
    sim.end_turn()
    assert cs.player.status_amount(StatusId.TANGLED) == 1
    for card in cs.player.hand:
        extra = 1 if card.type == CardType.Attack else 0
        assert card.current_cost(cs.player) == card.energy_cost + extra
    sim.end_turn()
    assert StatusId.TANGLED not in cs.player.status

# ---------------------------------------------------------------- Tangled
def test_tangled_raises_attack_cost_only():
    cs = shambler("swipe")
    tangle(cs)
    strike, defend = cs.player.hand[index_of(cs, "STRIKE_IRONCLAD")], cs.player.hand[index_of(cs, "DEFEND_IRONCLAD")]
    assert (strike.current_cost(cs.player), defend.current_cost(cs.player)) == (2, 1)

def test_tangled_charges_the_higher_cost():
    cs = shambler("swipe")
    tangle(cs)
    CombatSimulator(cs).play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    assert cs.energy == 1

def test_tangled_stops_an_attack_the_player_cannot_afford():
    cs = shambler("swipe")
    tangle(cs)
    cs.energy = 1
    with pytest.raises(IllegalActionError):
        CombatSimulator(cs).play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    assert cs.energy == 1

def test_tangled_does_not_change_a_skill():
    cs = shambler("swipe")
    tangle(cs)
    CombatSimulator(cs).play_card(index_of(cs, "DEFEND_IRONCLAD"), 0)
    assert cs.energy == 2

def test_tangled_cost_is_in_the_legal_actions():
    cs = shambler("swipe")
    tangle(cs)
    cs.energy = 1
    sim = CombatSimulator(cs)
    plays = [a for a in sim.get_available_actions() if a["action"] == "play_card"]
    assert all(cs.player.hand[a["card_index"]].type != CardType.Attack for a in plays)

def test_tangled_is_removed_when_the_turn_ends():
    cs = shambler("chomp_and_debuff")
    CombatSimulator(cs).end_turn()
    assert StatusId.TANGLED not in cs.player.status

def test_tangled_survives_a_copy():
    cs = shambler("chomp_and_debuff")
    copy = CombatState.deepcopy(cs)
    assert copy.player.status_amount(StatusId.TANGLED) == 1
