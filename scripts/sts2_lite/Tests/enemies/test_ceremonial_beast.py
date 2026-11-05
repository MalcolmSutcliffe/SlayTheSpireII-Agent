"""Ceremonial Beast, Plow and Ringing tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.combat import CombatSimulator, IllegalActionError
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId, is_debuff


def beast(name):
    return captures.load("ceremonial_beast", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def index_of(cs, card_id):
    return next(i for i, c in enumerate(cs.player.hand) if c.card_id.name == card_id)

def test_table_values():
    t = MOVE_TABLES["CEREMONIAL_BEAST"](0)
    assert t["STAMP"].self_status == ((StatusId.PLOW, 150),)
    assert (t["PLOW"].damage, t["PLOW"].self_status) == (18, ((StatusId.STRENGTH, 2),))
    assert t["STOMP"].damage == 15
    assert (t["CRUSH"].damage, t["CRUSH"].self_status) == (17, ((StatusId.STRENGTH, 3),))
    assert t["BEAST_CRY"].player_status == ((StatusId.RINGING, 1),)

def test_deadly_ascension():
    t = MOVE_TABLES["CEREMONIAL_BEAST"](9)
    assert t["STAMP"].self_status == ((StatusId.PLOW, 160),)
    assert (t["PLOW"].damage, t["STOMP"].damage, t["CRUSH"].damage) == (20, 17, 19)
    assert t["CRUSH"].self_status == ((StatusId.STRENGTH, 4),)

@pytest.mark.parametrize("name, move", [
    ("stamp", "STAMP"), ("plow", "PLOW"), ("stunned", "STUN"),
    ("beast_cry", "BEAST_CRY"), ("stomp", "STOMP"), ("crush", "CRUSH"),
])
def test_moves_are_identified_from_captures(name, move):
    assert beast(name).enemies[0].move_id == move

def test_stamp_applies_plow_then_it_plows_forever():
    cs = beast("stamp")
    enemy_turn(cs)
    e = cs.enemies[0]
    assert e.status_amount(StatusId.PLOW) == 150 and e.move_id == "PLOW"
    enemy_turn(cs)
    assert (e.move_id, e.status_amount(StatusId.STRENGTH)) == ("PLOW", 2)
    enemy_turn(cs)
    assert e.status_amount(StatusId.STRENGTH) == 4

def test_plow_hits_for_its_damage():
    cs = beast("plow")
    cs.player.block = 0
    hp = cs.player.current_hp
    enemy_turn(cs)
    assert cs.player.current_hp == hp - 18

# ---------------------------------------------------------------- Plow breaking
def test_hit_down_to_the_plow_amount_stuns_and_strips_strength():
    cs = beast("plow")
    e = cs.enemies[0]
    e.status[StatusId.STRENGTH] = type(e.status[StatusId.PLOW])(StatusId.STRENGTH, 4)
    e.apply_damage(102)
    assert e.current_hp == 150
    assert StatusId.PLOW not in e.status and StatusId.STRENGTH not in e.status
    assert (e.move_id, e.num_attacks) == ("STUN", 0)

def test_one_more_hp_does_not_break_plow():
    cs = beast("plow")
    e = cs.enemies[0]
    e.apply_damage(101)
    assert StatusId.PLOW in e.status and e.move_id == "PLOW"

def test_blocked_damage_does_not_break_plow():
    e = beast("plow").enemies[0]
    e.current_hp = 151
    e.block = 5
    e.apply_damage(5)
    assert StatusId.PLOW in e.status

def test_plow_breaks_only_once():
    e = beast("plow").enemies[0]
    e.apply_damage(110)
    e.move_id = "BEAST_CRY"
    e.apply_damage(5)
    assert e.move_id == "BEAST_CRY"

def test_stunned_beast_skips_its_turn_then_beast_cries():
    cs = beast("plow")
    cs.enemies[0].apply_damage(110)
    cs.player.block = 0
    hp = cs.player.current_hp
    enemy_turn(cs)
    assert cs.player.current_hp == hp and cs.player.status_amount(StatusId.RINGING) == 0
    assert cs.enemies[0].move_id == "BEAST_CRY"

def test_second_phase_cycle():
    cs = beast("stunned")
    seen = []
    for _ in range(6):
        enemy_turn(cs)
        seen.append(cs.enemies[0].move_id)
    assert seen == ["BEAST_CRY", "STOMP", "CRUSH", "BEAST_CRY", "STOMP", "CRUSH"]

def test_crush_adds_strength_each_time():
    cs = beast("crush")
    enemy_turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 3

# ---------------------------------------------------------------- Ringing
def test_beast_cry_applies_ringing():
    cs = beast("beast_cry")
    enemy_turn(cs)
    assert cs.player.status_amount(StatusId.RINGING) == 1

def test_ringing_is_a_debuff():
    assert is_debuff(StatusId.RINGING, 1)

def test_only_one_card_can_be_played_while_ringing():
    cs = beast("stomp")
    sim = CombatSimulator(cs)
    assert cs.cards_played == 0
    sim.play_card(index_of(cs, "DEFEND_IRONCLAD"), 0)
    with pytest.raises(IllegalActionError):
        sim.play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    assert all(a["action"] == "end_turn" for a in sim.get_available_actions())

def test_cards_are_unrestricted_without_ringing():
    cs = beast("crush")
    sim = CombatSimulator(cs)
    sim.play_card(index_of(cs, "DEFEND_IRONCLAD"), 0)
    sim.play_card(index_of(cs, "DEFEND_IRONCLAD"), 0)

def test_a_failed_play_does_not_use_up_the_card():
    cs = beast("stomp")
    sim = CombatSimulator(cs)
    cs.energy = 0
    with pytest.raises(IllegalActionError):
        sim.play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    assert cs.cards_played == 0

def test_ringing_ends_with_the_player_turn():
    cs = beast("stomp")
    CombatSimulator(cs).end_turn()
    assert StatusId.RINGING not in cs.player.status
    assert cs.cards_played == 0

def test_ringing_applied_by_beast_cry_lasts_the_next_turn_only():
    cs = beast("beast_cry")
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.player.status_amount(StatusId.RINGING) == 1
    sim.play_card(index_of(cs, "DEFEND_IRONCLAD"), 0)
    assert not any(a["action"] == "play_card" for a in sim.get_available_actions())
    sim.end_turn()
    assert StatusId.RINGING not in cs.player.status

def test_captured_mid_turn_after_the_one_card_is_still_locked():
    cs = beast("stomp_card_played")
    sim = CombatSimulator(cs)
    assert cs.cards_played == 1
    assert all(a["action"] == "end_turn" for a in sim.get_available_actions())

def test_capture_before_the_card_is_not_locked():
    cs = beast("stomp")
    assert any(a["action"] == "play_card" for a in CombatSimulator(cs).get_available_actions())

def test_played_card_count_survives_a_copy():
    from sts2_lite.combat import CombatState
    cs = beast("stomp_card_played")
    assert CombatState.deepcopy(cs).cards_played == 1

def test_the_play_count_resets_each_player_turn():
    cs = beast("beast_cry")
    sim = CombatSimulator(cs)
    sim.play_card(index_of(cs, "DEFEND_IRONCLAD"), 0)
    sim.end_turn()
    assert cs.cards_played == 0
    assert any(a["action"] == "play_card" for a in sim.get_available_actions())

def test_cards_locked_by_the_capture_are_playable_again_later():
    cs = beast("stomp_card_played")
    assert not any(c.is_unplayable for c in cs.player.hand)
