"""Enemy move table tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy import Enemy
from sts2_lite.enemy_moves import MOVE_TABLES, nibbit
from sts2_lite.player import Player
from sts2_lite.status import StatusId


# ---------------------------------------------------------------- helpers
BUTT = [{"type": "Attack", "label": "12"}]
SLICE = [{"type": "Attack", "label": "6"}, {"type": "Defend", "label": ""}]
HISS = [{"type": "Buff", "label": ""}]

def bridge_state(intents=BUTT, entity="NIBBIT_0", ascension=None, enemy_status=(), player_status=()):
    state = {
        "round": 1, "energy": 3, "max_energy": 3,
        "player": {"max_hp": 80, "hp": 80, "block": 0, "status": list(player_status),
                   "hand": [], "draw_pile": [], "discard_pile": [], "deck": []},
        "enemies": [{"entity_id": entity, "max_hp": 44, "hp": 44, "block": 0,
                     "status": list(enemy_status), "intents": list(intents)}],
    }
    if ascension is not None:
        state["context"] = {"act": 1, "floor": 2, "ascension": ascension}
    return state

def nibbit_state(intents=BUTT, **kw):
    return CombatState.from_dict(bridge_state(intents, **kw))

def status(name, amount):
    return {"id": name + "_POWER", "amount": amount}

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()


# ---------------------------------------------------------------- move table
def test_nibbit_cycle_is_butt_slice_hiss():
    t = nibbit(0)
    assert (t["BUTT"].next_move, t["SLICE"].next_move, t["HISS"].next_move) == ("SLICE", "HISS", "BUTT")

def test_nibbit_values():
    t = nibbit(0)
    assert (t["BUTT"].damage, t["BUTT"].hits) == (12, 1)
    assert (t["SLICE"].damage, t["SLICE"].hits, t["SLICE"].block) == (6, 1, 5)
    assert t["HISS"].self_status == ((StatusId.STRENGTH, 2),)

def test_butt_hits_harder_on_high_ascension():
    assert nibbit(8)["BUTT"].damage == 12
    assert nibbit(9)["BUTT"].damage == 13

def test_nibbit_slice_damage_rises_on_the_deadly_ascension():
    assert (nibbit(8)["SLICE"].damage, nibbit(9)["SLICE"].damage) == (6, 7)

def test_nibbit_slice_block_rises_on_the_tough_ascension():
    assert (nibbit(7)["SLICE"].block, nibbit(8)["SLICE"].block, nibbit(9)["SLICE"].block) == (5, 6, 6)

def test_nibbit_hiss_gives_more_strength_on_the_deadly_ascension():
    assert nibbit(8)["HISS"].self_status == ((StatusId.STRENGTH, 2),)
    assert nibbit(9)["HISS"].self_status == ((StatusId.STRENGTH, 3),)

def test_every_follow_up_exists():
    for table in MOVE_TABLES.values():
        moves = table(0)
        for name, m in moves.items():
            if m.choose is not None or name == "STUNNED":       # the follow-up is a function, or the stun's own (Enemy.after_stun)
                continue
            following = [m.next_move] if m.next_move else []
            following += [b.move for b in m.branches] + list(m.next_by_slot)
            assert following and all(f in moves for f in following)


# ---------------------------------------------------------------- reading the current move
@pytest.mark.parametrize("intents, expected", [(BUTT, "BUTT"), (SLICE, "SLICE"), (HISS, "HISS")])
def test_current_move_is_identified_from_the_intent(intents, expected):
    assert nibbit_state(intents).enemies[0].move_id == expected

def test_intent_types_are_case_insensitive():
    cs = nibbit_state([{"type": "ATTACK", "label": "12"}])
    assert cs.enemies[0].move_id == "BUTT"

def test_unknown_intent_falls_back_to_repeating_the_attack():
    cs = nibbit_state([{"type": "Sleep", "label": ""}])
    e = cs.enemies[0]
    assert e.moves is None and e.move_id is None

def test_unknown_enemy_has_no_move_table():
    e = nibbit_state(entity="SEAPUNK_0").enemies[0]
    assert e.moves is None and e.move_id is None

def test_enemy_number_suffix_is_ignored():
    assert nibbit_state(entity="NIBBIT_3").enemies[0].move_id == "BUTT"

def test_identified_move_keeps_the_bridge_damage():
    # displayed 14 = 12 + 2 Strength
    cs = nibbit_state([{"type": "Attack", "label": "14"}], enemy_status=[status("STRENGTH", 2)])
    e = cs.enemies[0]
    assert e.move_id == "BUTT" and e.attack_damage == 12

def test_ascension_is_read_from_the_bridge_context():
    cs = nibbit_state(HISS, ascension=9)
    assert cs.enemies[0].moves["BUTT"].damage == 13

def test_ascension_defaults_to_zero():
    assert nibbit_state(HISS).enemies[0].moves["BUTT"].damage == 12


# ---------------------------------------------------------------- performing moves
def test_butt_attacks_and_advances_to_slice():
    cs = nibbit_state(BUTT)
    enemy_turn(cs)
    e = cs.enemies[0]
    assert cs.player.current_hp == 80 - 12
    assert e.move_id == "SLICE"
    assert (e.attack_damage, e.num_attacks) == (6, 1)

def test_slice_attacks_and_gains_block():
    cs = nibbit_state(SLICE)
    enemy_turn(cs)
    e = cs.enemies[0]
    assert cs.player.current_hp == 80 - 6
    assert e.block == 5
    assert e.move_id == "HISS"

def test_hiss_does_no_damage_and_gives_strength():
    cs = nibbit_state(HISS)
    enemy_turn(cs)
    e = cs.enemies[0]
    assert cs.player.current_hp == 80
    assert e.status_amount(StatusId.STRENGTH) == 2
    assert e.move_id == "BUTT"
    assert (e.attack_damage, e.num_attacks) == (12, 1)

def test_strength_from_hiss_raises_later_attacks():
    cs = nibbit_state(HISS)
    enemy_turn(cs)               # hiss
    enemy_turn(cs)               # butt: 12 + 2
    assert cs.player.current_hp == 80 - 14

def test_full_cycle_damage():
    cs = nibbit_state(BUTT)
    sim = CombatSimulator(cs)
    for _ in range(7):
        sim.end_turn()
    # butt 12, slice 6, hiss, butt 14, slice 8, hiss, butt 16
    assert cs.player.current_hp == 80 - (12 + 6 + 14 + 8 + 16)

def test_cycle_wraps_back_to_butt():
    cs = nibbit_state(BUTT)
    for _ in range(3):
        enemy_turn(cs)
    assert cs.enemies[0].move_id == "BUTT"

def test_high_ascension_butt_damage_is_used():
    cs = nibbit_state(HISS, ascension=9)
    enemy_turn(cs)
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 16      # 13 + 3 Strength

def test_player_block_absorbs_a_move():
    cs = nibbit_state(BUTT)
    cs.player.block = 20
    enemy_turn(cs)
    assert (cs.player.current_hp, cs.player.block) == (80, 8)

def test_enemy_weak_reduces_move_damage():
    cs = nibbit_state(BUTT)
    cs.enemies[0].apply_status(StatusId.WEAK, 1)
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 9


# ---------------------------------------------------------------- enemy block timing
def test_block_from_slice_is_still_up_during_the_players_turn():
    cs = nibbit_state(SLICE)
    CombatSimulator(cs).end_turn()
    assert cs.enemies[0].block == 5

def test_block_absorbs_player_damage_on_the_players_turn():
    cs = nibbit_state(SLICE)
    CombatSimulator(cs).end_turn()
    e = cs.enemies[0]
    e.apply_damage(8)
    assert (e.current_hp, e.block) == (44 - 3, 0)

def test_block_expires_when_the_enemy_next_acts():
    cs = nibbit_state(SLICE)
    sim = CombatSimulator(cs)
    sim.end_turn()               # slice -> block 5
    sim.end_turn()               # hiss
    assert cs.enemies[0].block == 0

def test_enemy_without_moves_also_loses_block_on_its_turn():
    cs = CombatState()
    cs.player, e = Player(), Enemy()
    e.max_hp = e.current_hp = 20
    e.enemy_id, e.attack_damage, e.num_attacks, e.block = "X_0", 0, 0, 7
    cs.enemies, cs.energy, cs.max_energy, cs.turn_number = [e], 3, 3, 1
    enemy_turn(cs)
    assert e.block == 0

def test_new_player_turn_does_not_clear_enemy_block():
    cs = nibbit_state(SLICE)
    sim = CombatSimulator(cs)
    sim._play_enemy_turn()
    sim._start_player_turn()
    assert cs.enemies[0].block == 5

def test_plating_block_is_up_on_the_players_turn_and_gone_after_the_enemy_acts():
    cs = nibbit_state(HISS)
    e = cs.enemies[0]
    e.apply_status(StatusId.PLATING, 4)
    sim = CombatSimulator(cs)
    sim._start_player_turn()
    assert e.block == 4
    sim._play_enemy_turn()
    assert e.block == 0


# ---------------------------------------------------------------- cloning and randomness
def test_clone_keeps_the_move_and_advances_separately():
    cs = nibbit_state(BUTT)
    clone = CombatState.deepcopy(cs)
    assert clone.enemies[0].move_id == "BUTT"
    enemy_turn(clone)
    assert clone.enemies[0].move_id == "SLICE"
    assert cs.enemies[0].move_id == "BUTT"
    assert cs.player.current_hp == 80

def test_clone_keeps_block_and_strength_separate():
    cs = nibbit_state(HISS)
    clone = CombatState.deepcopy(cs)
    enemy_turn(clone)
    assert clone.enemies[0].status_amount(StatusId.STRENGTH) == 2
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 0

def test_nibbit_moves_use_no_randomness():
    cs = nibbit_state(BUTT)
    before = rng.calls
    sim = CombatSimulator(cs)
    for _ in range(6):
        sim._play_enemy_turn()
    assert rng.calls == before

def test_readable_shows_the_move():
    assert "Move: BUTT" in nibbit_state(BUTT).enemies[0].readable()


# ---------------------------------------------------------------- real bridge captures (ascension 0)
from sts2_lite.Tests import captures

def captured(name):
    return captures.load("nibbit", name)

def test_captured_hiss_turn():
    e = captured("hiss").enemies[0]
    assert e.move_id == "HISS" and e.num_attacks == 0
    assert e.block == 5      # Slice's block is still up on the player's turn

def test_captured_butt_turn_reads_base_damage_through_strength():
    # the game shows 14 = 12 + 2 Strength
    e = captured("butt").enemies[0]
    assert e.move_id == "BUTT"
    assert (e.attack_damage, e.num_attacks) == (12, 1)
    assert e.status_amount(StatusId.STRENGTH) == 2
    assert e.block == 0

def test_captured_slice_turn_reads_base_damage_through_strength():
    # the game shows 8 = 6 + 2 Strength, plus a Defend intent
    e = captured("slice").enemies[0]
    assert e.move_id == "SLICE"
    assert (e.attack_damage, e.num_attacks) == (6, 1)

def test_captured_turns_follow_the_cycle():
    for name, following in (("hiss", "BUTT"), ("butt", "SLICE"), ("slice", "HISS")):
        cs = captured(name)
        enemy_turn(cs)
        assert cs.enemies[0].move_id == following

def test_captured_butt_hits_for_the_displayed_damage():
    cs = captured("butt")
    hp = cs.player.current_hp
    enemy_turn(cs)
    assert cs.player.current_hp == hp - 14

def test_captured_slice_hits_for_the_displayed_damage_and_blocks():
    cs = captured("slice")
    hp = cs.player.current_hp
    enemy_turn(cs)
    assert cs.player.current_hp == hp - 8
    assert cs.enemies[0].block == 5

def test_captured_states_offer_actions():
    for name in ("hiss", "butt", "slice"):
        assert CombatSimulator(captured(name)).get_available_actions()


# ---------------------------------------------------------------- shrinker beetle
from sts2_lite.damage import modify_damage
from sts2_lite.enemy_moves import shrinker_beetle

def beetle(name="attack"):
    return captures.load("shrinker_beetle", name)

def beetle_bridge(intents, ascension=None, player_status=()):
    state = bridge_state(intents, entity="SHRINKER_BEETLE_0", ascension=ascension, player_status=player_status)
    state["enemies"][0]["hp"] = state["enemies"][0]["max_hp"] = 38
    return CombatState.from_dict(state)

SHRINK_INTENT = [{"type": "DebuffStrong", "label": ""}]
CHOMP_INTENT = [{"type": "Attack", "label": "7"}]
STOMP_INTENT = [{"type": "Attack", "label": "13"}]
SHRUNK = [{"id": "SHRINK_POWER", "amount": -1}]

def test_beetle_table_values():
    t = shrinker_beetle(0)
    assert (t["CHOMP"].damage, t["STOMP"].damage) == (7, 13)
    assert t["SHRINK"].player_status == ((StatusId.SHRINK, -1),)
    assert (t["SHRINK"].next_move, t["CHOMP"].next_move, t["STOMP"].next_move) == ("CHOMP", "STOMP", "CHOMP")

def test_beetle_hits_harder_on_high_ascension():
    t = shrinker_beetle(9)
    assert (t["CHOMP"].damage, t["STOMP"].damage) == (8, 14)

def test_captured_beetle_turn():
    cs = beetle()
    e = cs.enemies[0]
    assert e.move_id == "CHOMP"
    assert (e.attack_damage, e.num_attacks) == (7, 1)
    assert cs.player.status_amount(StatusId.SHRINK) == -1

@pytest.mark.parametrize("intents, expected", [(SHRINK_INTENT, "SHRINK"), (CHOMP_INTENT, "CHOMP"), (STOMP_INTENT, "STOMP")])
def test_beetle_move_is_identified(intents, expected):
    assert beetle_bridge(intents).enemies[0].move_id == expected

def test_beetle_moves_alternate_chomp_and_stomp():
    cs = beetle_bridge(SHRINK_INTENT)
    seen = []
    for _ in range(5):
        seen.append(cs.enemies[0].move_id)
        enemy_turn(cs)
    assert seen == ["SHRINK", "CHOMP", "STOMP", "CHOMP", "STOMP"]

def test_shrink_move_debuffs_the_player_and_does_no_damage():
    cs = beetle_bridge(SHRINK_INTENT)
    enemy_turn(cs)
    assert cs.player.current_hp == 80
    assert cs.player.status_amount(StatusId.SHRINK) == -1

def test_shrink_is_applied_once_per_use():
    cs = beetle_bridge(SHRINK_INTENT)
    for _ in range(4):
        enemy_turn(cs)
    assert cs.player.status_amount(StatusId.SHRINK) == -1

def test_beetle_chomp_and_stomp_damage():
    cs = beetle_bridge(CHOMP_INTENT)
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 7
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 7 - 13

def test_shrink_does_not_expire_with_turns():
    cs = beetle()
    sim = CombatSimulator(cs)
    for _ in range(5):
        sim.end_turn()
    assert cs.player.status_amount(StatusId.SHRINK) == -1


# ---- the damage cut
def test_shrink_cuts_player_damage_by_thirty_percent():
    cs = beetle()
    assert modify_damage(10, cs.player, cs.enemies[0]) == 7

def test_shrink_truncates_once_like_the_game_display():
    # Bash shows 5 under Shrink (8 * 0.7 = 5.6)
    cs = beetle()
    assert modify_damage(8, cs.player, cs.enemies[0]) == 5

def test_shrink_combines_with_other_modifiers_before_truncating():
    cs = beetle()
    cs.player.apply_status(StatusId.WEAK, 1)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    assert modify_damage(10, cs.player, cs.enemies[0]) == int(10 * 0.75 * 1.5 * 0.7)

def test_shrink_does_not_change_damage_without_the_status():
    cs = beetle_bridge(CHOMP_INTENT)
    assert modify_damage(10, cs.player, cs.enemies[0]) == 10

def test_playing_bash_under_shrink_deals_what_the_card_shows():
    cs = beetle()
    sim = CombatSimulator(cs)
    index = next(i for i, c in enumerate(cs.player.hand) if c.name == "Bash")
    sim.play_card(index, 0)
    assert cs.enemies[0].current_hp == 38 - 5

def test_shrink_does_not_slow_enemy_attacks():
    cs = beetle()
    enemy_turn(cs)
    assert cs.player.current_hp == 73 - 7


# ---- losing the debuff
def test_shrink_ends_when_the_beetle_dies():
    cs = beetle("attack")
    sim = CombatSimulator(cs)
    other = type(cs.enemies[0]).deepcopy(cs.enemies[0])
    other.enemy_id = "NIBBIT_0"
    cs.enemies.append(other)             # keeps the fight going after the kill
    cs.enemies[0].current_hp = 1
    sim.play_card(next(i for i, c in enumerate(cs.player.hand) if c.name == "Bash"), 0)
    assert StatusId.SHRINK not in cs.player.status
    assert len(cs.enemies) == 1

def test_shrink_stays_when_another_enemy_dies():
    cs = beetle()
    other = type(cs.enemies[0]).deepcopy(cs.enemies[0])
    other.enemy_id = "NIBBIT_0"
    other.current_hp = 1
    cs.enemies.append(other)
    sim = CombatSimulator(cs)
    sim.play_card(next(i for i, c in enumerate(cs.player.hand) if c.name == "Bash"), 1)
    assert cs.player.status_amount(StatusId.SHRINK) == -1

def test_killing_a_creature_fires_the_event_once_per_kill():
    from sts2_lite import status as status_module
    from sts2_lite.events import EventType
    cs = beetle()
    seen = []
    status_module.STATUS_HANDLERS[(StatusId.SHRINK, EventType.CREATURE_KILLED)], saved = (
        lambda combat, owner, amount, killed: seen.append(killed.enemy_id),
        status_module.STATUS_HANDLERS[(StatusId.SHRINK, EventType.CREATURE_KILLED)])
    try:
        sim = CombatSimulator(cs)
        cs.enemies[0].current_hp = 1
        sim.play_card(next(i for i, c in enumerate(cs.player.hand) if c.name == "Bash"), 0)
    finally:
        status_module.STATUS_HANDLERS[(StatusId.SHRINK, EventType.CREATURE_KILLED)] = saved
    assert seen == ["SHRINKER_BEETLE_0"]

def test_beetle_moves_use_no_randomness():
    cs = beetle_bridge(SHRINK_INTENT)
    before = rng.calls
    for _ in range(6):
        enemy_turn(cs)
    assert rng.calls == before


# ---- captured beetle turns
def test_captured_shrink_turn():
    cs = beetle("debuff")
    e = cs.enemies[0]
    assert e.move_id == "SHRINK" and e.num_attacks == 0
    assert cs.player.status_amount(StatusId.SHRINK) == 0

def test_captured_stomp_turn():
    cs = beetle("attack_strong")
    e = cs.enemies[0]
    assert e.move_id == "STOMP"
    assert (e.attack_damage, e.num_attacks) == (13, 1)
    assert cs.player.status_amount(StatusId.SHRINK) == -1

def test_captured_beetle_turns_follow_the_cycle():
    for name, following in (("debuff", "CHOMP"), ("attack", "STOMP"),
                            ("attack_strong", "CHOMP")):
        cs = beetle(name)
        enemy_turn(cs)
        assert cs.enemies[0].move_id == following

def test_captured_shrink_turn_debuffs_the_player():
    cs = beetle("debuff")
    enemy_turn(cs)
    assert cs.player.status_amount(StatusId.SHRINK) == -1
    assert cs.player.current_hp == 73

def test_captured_stomp_hits_for_thirteen():
    cs = beetle("attack_strong")
    enemy_turn(cs)
    assert cs.player.current_hp == 66 - 13

def test_strike_under_shrink_deals_what_the_card_shows():
    # the game shows Strike as 4 under Shrink
    cs = beetle("attack_strong")
    index = next(i for i, c in enumerate(cs.player.hand) if c.name == "Strike")
    CombatSimulator(cs).play_card(index, 0)
    assert cs.enemies[0].current_hp == 40 - 4

def test_body_slam_is_cut_by_shrink():
    cs = beetle()
    cs.player.block = 10
    index = next(i for i, c in enumerate(cs.player.hand) if c.name == "Body Slam")
    CombatSimulator(cs).play_card(index, 0)
    assert cs.enemies[0].current_hp == 38 - 7


# ---------------------------------------------------------------- fuzzy wurm crawler
from sts2_lite.enemy_moves import fuzzy_wurm_crawler

GOOP_INTENT = [{"type": "Attack", "label": "4"}]
INHALE_INTENT = [{"type": "Buff", "label": ""}]

def crawler(name):
    return captures.load("fuzzy_wurm_crawler", name)

def crawler_bridge(intents, round_number, ascension=None, strength=0):
    state = bridge_state(intents, entity="FUZZY_WURM_CRAWLER_0", ascension=ascension,
                         enemy_status=[status("STRENGTH", strength)] if strength else ())
    state["round"] = round_number
    return CombatState.from_dict(state)

def test_crawler_table_values():
    t = fuzzy_wurm_crawler(0)
    assert (t["FIRST_GOOP"].damage, t["GOOP"].damage) == (4, 4)
    assert t["INHALE"].self_status == ((StatusId.STRENGTH, 7),)
    assert (t["FIRST_GOOP"].next_move, t["INHALE"].next_move, t["GOOP"].next_move) == ("INHALE", "GOOP", "FIRST_GOOP")

def test_crawler_goop_hits_harder_on_high_ascension():
    t = fuzzy_wurm_crawler(9)
    assert (t["FIRST_GOOP"].damage, t["GOOP"].damage) == (6, 6)

def test_crawler_pattern_is_goop_inhale_goop_goop_inhale():
    cs = crawler_bridge(GOOP_INTENT, 1)
    seen = []
    for _ in range(7):
        seen.append(cs.enemies[0].move_id)
        enemy_turn(cs)
    assert seen == ["FIRST_GOOP", "INHALE", "GOOP", "FIRST_GOOP", "INHALE", "GOOP", "FIRST_GOOP"]

def test_crawler_damage_grows_with_each_inhale():
    cs = crawler_bridge(GOOP_INTENT, 1)
    taken = []
    for _ in range(7):
        hp = cs.player.current_hp
        enemy_turn(cs)
        taken.append(hp - cs.player.current_hp)
    assert taken == [4, 0, 11, 11, 0, 18, 18]

def test_crawler_inhale_does_no_damage():
    cs = crawler_bridge(INHALE_INTENT, 2)
    enemy_turn(cs)
    assert cs.player.current_hp == 80
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 7

def test_crawler_moves_use_no_randomness():
    cs = crawler_bridge(GOOP_INTENT, 1)
    before = rng.calls
    for _ in range(6):
        enemy_turn(cs)
    assert rng.calls == before


# ---- telling the two goops apart (same intent, different next move)
@pytest.mark.parametrize("round_number, expected", [
    (1, "FIRST_GOOP"), (3, "GOOP"), (4, "FIRST_GOOP"), (6, "GOOP"), (7, "FIRST_GOOP")])
def test_goops_are_told_apart_by_the_round(round_number, expected):
    assert crawler_bridge(GOOP_INTENT, round_number).enemies[0].move_id == expected

def test_goop_with_an_unexpected_round_falls_back_to_repeating_the_attack():
    e = crawler_bridge(GOOP_INTENT, 2).enemies[0]
    assert e.moves is None and e.move_id is None

def test_inhale_is_identified_in_any_round():
    assert crawler_bridge(INHALE_INTENT, 2).enemies[0].move_id == "INHALE"
    assert crawler_bridge(INHALE_INTENT, 5).enemies[0].move_id == "INHALE"

def test_goop_damage_is_read_through_strength():
    # displayed 11 = 4 + 7 Strength
    cs = crawler_bridge([{"type": "Attack", "label": "11"}], 3, strength=7)
    e = cs.enemies[0]
    assert e.move_id == "GOOP" and e.attack_damage == 4


# ---- real captures (ascension 0)
def test_captured_crawler_goop_turn():
    e = crawler("goop").enemies[0]
    assert e.move_id == "FIRST_GOOP"
    assert (e.attack_damage, e.num_attacks) == (4, 1)

def test_captured_crawler_inhale_turn():
    e = crawler("inhale").enemies[0]
    assert e.move_id == "INHALE" and e.num_attacks == 0

def test_captured_crawler_goop_after_inhale_turn():
    e = crawler("goop_after_inhale").enemies[0]
    assert e.move_id == "GOOP"
    assert (e.attack_damage, e.num_attacks) == (4, 1)
    assert e.status_amount(StatusId.STRENGTH) == 7

def test_captured_crawler_turns_follow_the_pattern():
    for name, following in (("goop", "INHALE"), ("inhale", "GOOP"), ("goop_after_inhale", "FIRST_GOOP")):
        cs = crawler(name)
        enemy_turn(cs)
        assert cs.enemies[0].move_id == following

def test_captured_goop_after_inhale_hits_for_the_displayed_damage():
    cs = crawler("goop_after_inhale")
    hp = cs.player.current_hp
    enemy_turn(cs)
    assert cs.player.current_hp == hp - 11

def test_captured_inhale_gives_seven_strength():
    cs = crawler("inhale")
    enemy_turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 7
