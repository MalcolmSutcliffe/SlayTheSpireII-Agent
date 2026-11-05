"""Bygone Effigy tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.damage import modify_damage
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId


def effigy(name):
    return captures.load("bygone_effigy", name)

def bridge(intents, ascension=0, slow=0, strength=0, round_number=1):
    status = [{"id": "SLOW_POWER", "amount": slow}]
    if strength:
        status.append({"id": "STRENGTH_POWER", "amount": strength})
    return CombatState.from_dict({
        "round": round_number, "energy": 3, "max_energy": 3, "context": {"ascension": ascension},
        "player": {"max_hp": 80, "hp": 80, "block": 0, "status": [], "hand": [],
                   "draw_pile": [], "discard_pile": [], "deck": []},
        "enemies": [{"entity_id": "BYGONE_EFFIGY_0", "max_hp": 127, "hp": 127, "block": 0,
                     "status": status, "intents": intents}],
    })

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def play(cs, card_id):
    """Play the first card with this id at the effigy."""
    i = next(i for i, c in enumerate(cs.player.hand) if c.card_id.name == card_id)
    CombatSimulator(cs).play_card(i, 0)

def hp_lost_by_effigy(cs, card_id):
    before = cs.enemies[0].current_hp
    play(cs, card_id)
    return before - cs.enemies[0].current_hp


# ---------------------------------------------------------------- table
def test_effigy_has_a_table():
    assert "BYGONE_EFFIGY" in MOVE_TABLES

def test_effigy_sleeps_wakes_then_slashes_forever():
    t = MOVE_TABLES["BYGONE_EFFIGY"](0)
    assert (t["SLEEP"].next_move, t["WAKE"].next_move, t["SLASH"].next_move) == ("WAKE", "SLASH", "SLASH")

def test_effigy_values():
    t = MOVE_TABLES["BYGONE_EFFIGY"]
    assert t(0)["WAKE"].self_status == ((StatusId.STRENGTH, 10),)
    assert (t(0)["SLASH"].damage, t(8)["SLASH"].damage, t(9)["SLASH"].damage) == (13, 13, 15)
    assert t(0)["SLEEP"].hits == 0 and t(0)["WAKE"].hits == 0


# ---------------------------------------------------------------- real captures (ascension 0)
def test_captured_sleep_turn():
    e = effigy("sleep").enemies[0]
    assert (e.move_id, e.num_attacks) == ("SLEEP", 0)
    assert e.current_hp == 127

def test_captured_wake_turn():
    e = effigy("wake").enemies[0]
    assert (e.move_id, e.num_attacks) == ("WAKE", 0)

def test_captured_slash_turn_reads_base_damage_through_strength():
    e = effigy("slash").enemies[0]
    assert e.status[StatusId.STRENGTH].amount == 10
    assert (e.move_id, e.attack_damage, e.num_attacks) == ("SLASH", 13, 1)

def test_captured_turns_follow_the_pattern():
    for name, following in (("sleep", "WAKE"), ("wake", "SLASH"), ("slash", "SLASH")):
        cs = effigy(name)
        enemy_turn(cs)
        assert cs.enemies[0].move_id == following

def test_captured_slash_hits_for_the_displayed_damage():
    cs = effigy("slash")
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 23

def test_captured_states_offer_actions():
    for name in ("sleep", "wake", "slash"):
        assert CombatSimulator(effigy(name)).get_available_actions()

def test_captured_slow_starts_at_zero():
    for name in ("sleep", "wake", "slash"):
        assert effigy(name).enemies[0].status[StatusId.SLOW].amount == 0


# ---------------------------------------------------------------- fight
def test_sleeping_and_waking_do_no_damage():
    cs = effigy("sleep")
    enemy_turn(cs); enemy_turn(cs)
    assert cs.player.current_hp == 80

def test_waking_gives_ten_strength():
    cs = effigy("wake")
    enemy_turn(cs)
    assert cs.enemies[0].status[StatusId.STRENGTH].amount == 10

def test_slash_damage_after_waking():
    cs = effigy("sleep")
    enemy_turn(cs); enemy_turn(cs)
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 23
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 46

def test_high_ascension_slash():
    cs = bridge([{"type": "Buff", "label": ""}], ascension=9)
    enemy_turn(cs); enemy_turn(cs)
    assert cs.player.current_hp == 80 - 25

def test_effigy_uses_no_randomness():
    cs = effigy("sleep")
    before = rng.calls
    for _ in range(5):
        enemy_turn(cs)
    assert rng.calls == before

def test_intents_are_told_apart():
    assert bridge([{"type": "Sleep", "label": ""}]).enemies[0].move_id == "SLEEP"
    assert bridge([{"type": "Buff", "label": ""}]).enemies[0].move_id == "WAKE"
    assert bridge([{"type": "Attack", "label": "13"}]).enemies[0].move_id == "SLASH"


# ---------------------------------------------------------------- Slow
def test_first_card_deals_full_damage():
    assert hp_lost_by_effigy(effigy("sleep"), "STRIKE_IRONCLAD") == 6

def test_each_card_adds_ten_percent_to_the_next_hit():
    cs = effigy("sleep")
    assert [hp_lost_by_effigy(cs, "STRIKE_IRONCLAD") for _ in range(3)] == [6, 6, 7]

def test_any_card_counts_toward_slow():
    cs = effigy("sleep")
    play(cs, "DEFEND_IRONCLAD"); play(cs, "DEFEND_IRONCLAD")
    assert cs.enemies[0].status[StatusId.SLOW].amount == 20
    assert hp_lost_by_effigy(cs, "STRIKE_IRONCLAD") == 7

def test_slow_amount_is_shown_in_percent():
    cs = effigy("sleep")
    play(cs, "STRIKE_IRONCLAD")
    assert cs.enemies[0].status[StatusId.SLOW].amount == 10

def test_slow_resets_for_the_next_turn():
    cs = effigy("sleep")
    play(cs, "STRIKE_IRONCLAD"); play(cs, "STRIKE_IRONCLAD")
    CombatSimulator(cs).end_turn()
    assert cs.enemies[0].status[StatusId.SLOW].amount == 0

def test_slow_is_read_from_a_mid_turn_state():
    cs = bridge([{"type": "Sleep", "label": ""}], slow=30)
    assert cs.enemies[0].status[StatusId.SLOW].amount == 30
    assert modify_damage(10, cs.player, cs.enemies[0]) == 13

def test_slow_stacks_with_vulnerable_before_truncating():
    cs = bridge([{"type": "Sleep", "label": ""}], slow=30)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    assert modify_damage(10, cs.player, cs.enemies[0]) == 19      # 10 x 1.5 x 1.3 = 19.5

def test_slow_does_not_change_damage_without_the_status():
    cs = bridge([{"type": "Sleep", "label": ""}])
    del cs.enemies[0].status[StatusId.SLOW]
    assert modify_damage(10, cs.player, cs.enemies[0]) == 10

def test_slow_does_not_change_the_damage_the_player_takes():
    cs = bridge([{"type": "Attack", "label": "23"}], slow=40, strength=10)
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 23

def test_clone_keeps_slow_separate():
    cs = effigy("sleep")
    play(cs, "STRIKE_IRONCLAD")
    clone = CombatState.deepcopy(cs)
    play(clone, "STRIKE_IRONCLAD")
    assert cs.enemies[0].status[StatusId.SLOW].amount == 10
    assert clone.enemies[0].status[StatusId.SLOW].amount == 20

def test_killing_the_effigy_ends_the_fight():
    cs = effigy("sleep")
    cs.enemies[0].current_hp = 5
    sim = CombatSimulator(cs)
    i = next(i for i, c in enumerate(cs.player.hand) if c.card_id.name == "STRIKE_IRONCLAD")
    sim.play_card(i, 0)
    assert sim.is_over and cs.enemies == []
