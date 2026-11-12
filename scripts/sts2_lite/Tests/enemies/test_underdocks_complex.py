"""Act 1 (Underdocks) monsters, phase 2: Gremlin Merc and its gremlins, Living Fog and Gas Bombs, Two-Tailed Rats, Terror Eel.
Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite import rng
from sts2_lite.card import Card, CardId
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy import STUNNED
from sts2_lite.enemy_moves import MOVE_TABLES, rat_counter, table_move_id
from sts2_lite.status import StatusId
from sts2_lite.Tests.enemies.test_bridge_moves import attack, load, raw_enemy
from sts2_lite.Tests.enemies.test_glory_simple import at, moves_over, status, turn
from sts2_lite.Tests.enemies.test_hive_simple import defend, strike


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)

def ascended(cs, monster, ascension):
    cs.enemies[0].moves = MOVE_TABLES[monster](ascension)
    return cs


@pytest.mark.parametrize("monster, move, base, deadly, hits", [
    ("SNEAKY_GREMLIN", "TACKLE", 9, 10, 1),
    ("LIVING_FOG", "ADVANCED_GAS", 8, 9, 1), ("LIVING_FOG", "BLOAT", 5, 6, 1), ("LIVING_FOG", "SUPER_GAS_BLAST", 8, 9, 1),
    ("GAS_BOMB", "EXPLODE", 8, 9, 1),
    ("TWO_TAILED_RAT", "SCRATCH", 8, 9, 1), ("TWO_TAILED_RAT", "DISEASE_BITE", 6, 7, 1),
    ("TERROR_EEL", "CRASH", 16, 18, 1), ("TERROR_EEL", "THRASH", 3, 4, 3),
])
def test_damage_rises_on_deadly_ascension(monster, move, base, deadly, hits):
    for ascension, damage in ((0, base), (9, deadly)):
        m = MOVE_TABLES[monster](ascension)[move]
        assert (m.damage, m.hits) == (damage, hits)

def test_the_merc_s_damage_follows_tough_enemies_not_deadly_enemies():
    for move, base, tough, hits in (("GIMME", 7, 8, 2), ("DOUBLE_SMASH", 6, 7, 2), ("HEHE", 8, 9, 1)):
        assert [MOVE_TABLES["GREMLIN_MERC"](a)[move].damage for a in (0, 8, 9)] == [base, tough, tough]
        assert MOVE_TABLES["GREMLIN_MERC"](0)[move].hits == hits


# ---------------------------------------------------------------- Gremlin Merc
def merc(move="GIMME", gold=100, **kw):
    cs = at("GREMLIN_MERC", move, status=[status("SURPRISE", 1), status("THIEVERY", 20)], hp=50, max_hp=50, **kw)
    cs.player.gold = gold
    return cs

def test_merc_cycle_and_the_game_s_name_for_its_double_smash():
    assert moves_over(merc(), 3) == ["GIMME", "DOUBLE_SMASH", "HEHE", "GIMME"]
    assert table_move_id("GREMLIN_MERC", "DOUBLE_SMASH_MOVE", MOVE_TABLES["GREMLIN_MERC"](0)) == "DOUBLE_SMASH"

def test_each_attack_takes_gold_and_remembers_how_much():
    cs = merc()
    thievery = cs.enemies[0].status[StatusId.THIEVERY]
    turn(cs)
    assert (cs.player.gold, cs.player.current_hp) == (80, 80 - 14)
    assert thievery.records[0][1] == 20
    turn(cs)
    assert cs.player.gold == 60 and thievery.records[0][1] == 40
    turn(cs)
    assert cs.player.gold == 40 and thievery.records[0][1] == 60

def test_the_merc_takes_only_what_there_is():
    cs = merc(gold=7)
    turn(cs)
    assert cs.player.gold == 0 and cs.enemies[0].status[StatusId.THIEVERY].records[0][1] == 7
    turn(cs)
    assert cs.enemies[0].status[StatusId.THIEVERY].records[0][1] == 7

def test_double_smash_weakens_and_hehe_adds_strength():
    cs = merc("DOUBLE_SMASH")
    turn(cs)
    assert cs.player.status_amount(StatusId.WEAK) == 2 and cs.player.current_hp == 80 - 12 and cs.player.gold == 80
    cs = merc("HEHE")
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2 and cs.player.current_hp == 80 - 8

def kill_merc(cs):
    merc_enemy = cs.enemies[0]
    merc_enemy.current_hp = 0
    sim = CombatSimulator(cs)
    sim.resolve_deaths()
    return sim

def test_when_the_merc_dies_a_sneaky_and_a_fat_gremlin_step_out_and_the_fight_goes_on():
    cs = merc()
    turn(cs)
    turn(cs)
    sim = kill_merc(cs)
    assert [e.enemy_id.rpartition("_")[0] for e in cs.enemies] == ["SNEAKY_GREMLIN", "FAT_GREMLIN"]
    assert not sim.is_over
    sneaky, fat = cs.enemies
    assert fat.status_amount(StatusId.HEIST) == 40 and StatusId.HEIST not in sneaky.status
    assert {sneaky.move_id, fat.move_id} == {"SPAWNED"}

def test_a_merc_that_stole_nothing_gives_the_fat_gremlin_no_heist():
    cs = merc()
    kill_merc(cs)
    assert StatusId.HEIST not in cs.enemies[1].status

def test_the_gremlins_wake_then_the_sneaky_one_tackles_and_the_fat_one_flees():
    cs = merc()
    sim = kill_merc(cs)
    hp = cs.player.current_hp
    turn(cs)
    assert cs.player.current_hp == hp                  # waking up
    assert [e.move_id for e in cs.enemies] == ["TACKLE", "FLEE"]
    turn(cs)
    assert cs.player.current_hp == hp - 9
    assert [e.enemy_id.rpartition("_")[0] for e in cs.enemies] == ["SNEAKY_GREMLIN"]       # the fat one is gone with the gold

def test_killing_both_gremlins_ends_the_fight_and_killing_only_the_merc_does_not():
    cs = merc()
    sim = kill_merc(cs)
    for e in cs.enemies:
        e.current_hp = 0
    sim.resolve_deaths()
    sim._check_is_over()
    assert sim.is_over

def test_the_gremlins_have_the_hit_points_of_the_game():
    for ascension, sneaky, fat in ((0, (10, 14), (13, 17)), (8, (11, 15), (14, 18))):
        for seed in range(40):
            rng.seed(seed)
            cs = merc(ascension=ascension)
            cs.ascension = ascension
            kill_merc(cs)
            assert sneaky[0] <= cs.enemies[0].max_hp <= sneaky[1] and fat[0] <= cs.enemies[1].max_hp <= fat[1]


# ---------------------------------------------------------------- Living Fog
def fog(move="ADVANCED_GAS", ascension=0, **kw):
    return ascended(at("LIVING_FOG", move, ascension, hp=80, max_hp=80, **kw), "LIVING_FOG", ascension)

def test_living_fog_gases_then_alternates_bloat_and_blast():
    cs = fog()
    seen = [cs.enemies[-1].move_id]
    for _ in range(5):
        turn(cs)
        seen.append(cs.enemies[-1].move_id)       # the bombs come in on its left
    assert seen == ["ADVANCED_GAS", "BLOAT", "SUPER_GAS_BLAST", "BLOAT", "SUPER_GAS_BLAST", "BLOAT"]

def test_advanced_gas_hits_and_makes_the_player_smoggy():
    cs = fog()
    turn(cs)
    assert cs.player.current_hp == 80 - 8 and cs.player.status_amount(StatusId.SMOGGY) == 1

def test_smoggy_does_not_stack_and_artifact_stops_it():
    cs = fog()
    cs.player.apply_status(StatusId.SMOGGY, 1)
    cs.player.apply_status(StatusId.SMOGGY, 1)
    assert cs.player.status_amount(StatusId.SMOGGY) == 1
    cs = fog()
    cs.player.apply_status(StatusId.ARTIFACT, 1)
    cs.player.apply_status(StatusId.SMOGGY, 1)
    assert StatusId.SMOGGY not in cs.player.status and StatusId.ARTIFACT not in cs.player.status

def test_bloat_adds_a_gas_bomb_to_the_left_of_the_fog_each_time():
    cs = fog("BLOAT")
    turn(cs)
    assert [e.enemy_id.rpartition("_")[0] for e in cs.enemies] == ["GAS_BOMB", "LIVING_FOG"]
    bomb = cs.enemies[0]
    assert bomb.is_minion and bomb.max_hp == 7 and bomb.move_id == "EXPLODE"
    turn(cs)
    turn(cs)
    assert [e.enemy_id for e in cs.enemies if e.enemy_id.startswith("GAS_BOMB")] != []

def test_never_more_than_five_bombs_and_free_places_are_reused():
    cs = fog("BLOAT")
    for _ in range(12):
        cs.enemies[-1].move_id = "BLOAT"
        cs.enemies[-1].attack_damage, cs.enemies[-1].num_attacks = 5, 1
        for e in cs.enemies[:-1]:
            e.move_id = "EXPLODE"
        cs.enemies[-1].perform_turn(CombatSimulator(cs))
    bombs = [e for e in cs.enemies if e.enemy_id.startswith("GAS_BOMB")]
    assert len(bombs) == 5 and sorted(b.slot for b in bombs) == [0, 1, 2, 3, 4]

def gas_bomb_state(ascension=0):
    damage = 9 if ascension >= 9 else 8
    bomb = raw_enemy("GAS_BOMB", "EXPLODE_MOVE", ["EXPLODE_MOVE"],
                     [{"type": "DeathBlow", "label": str(damage), "base_damage": damage, "hits": 1, "damage": damage, "total_damage": damage}],
                     status=[status("MINION", 1)])
    bomb["hp"] = bomb["max_hp"] = 7
    return load(bomb, raw_enemy("LIVING_FOG", "SUPER_GAS_BLAST_MOVE", ["SUPER_GAS_BLAST_MOVE"], attack(8)))

def test_a_gas_bomb_explodes_for_its_damage_and_is_gone():
    cs = gas_bomb_state()
    CombatSimulator(cs)._play_enemy_turn()
    assert cs.player.current_hp == 80 - 8 - 8              # the bomb, then the fog
    assert [e.enemy_id.rpartition("_")[0] for e in cs.enemies] == ["LIVING_FOG"]

def test_blocking_the_bomb_leaves_the_player_unhurt_by_it_but_it_still_goes():
    cs = gas_bomb_state()
    cs.player.block = 8
    CombatSimulator(cs)._play_enemy_turn()
    assert cs.player.current_hp == 80 - 8
    assert [e.enemy_id.rpartition("_")[0] for e in cs.enemies] == ["LIVING_FOG"]

def smog_hand():
    cs = fog(status=[])
    cs.player.status[StatusId.SMOGGY] = __import__("sts2_lite.status", fromlist=["StatusInstance"]).StatusInstance(StatusId.SMOGGY, 1)
    cs.energy = 3
    cs.player.hand = [defend(), defend(), strike(), defend()]
    return cs

def test_after_a_skill_every_skill_is_unplayable_until_the_turn_ends():
    cs = smog_hand()
    sim = CombatSimulator(cs)
    assert all(c.can_play_card(sim, 0) for c in cs.player.hand)
    sim.play_card(0, 0)
    assert [c.can_play_card(sim, 0) for c in cs.player.hand] == [False, True, False]
    sim.play_card(1, 0)                 # the Strike
    assert cs.player.hand[0].can_play_card(sim, 0) is False

def test_attacks_do_not_trigger_smog_and_the_next_turn_is_clear():
    cs = smog_hand()
    sim = CombatSimulator(cs)
    sim.play_card(2, 0)
    assert cs.player.smogged is False and cs.player.hand[0].can_play_card(sim, 0)
    sim.play_card(0, 0)
    assert cs.player.smogged
    sim.end_turn()
    assert cs.player.smogged is False

def test_without_the_smoggy_power_skills_stay_playable():
    cs = smog_hand()
    del cs.player.status[StatusId.SMOGGY]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.player.hand[0].can_play_card(sim, 0)


# ---------------------------------------------------------------- Two-Tailed Rats
def rat(move="SCRATCH", log=None, ascension=0, **kw):
    m = MOVE_TABLES["TWO_TAILED_RAT"](ascension)[move]
    game_id = move + "_MOVE"
    intents = attack(m.damage, m.hits) if m.hits else [{"type": t.title(), "label": ""} for t in sorted(m.intents)]
    raw = raw_enemy("TWO_TAILED_RAT", game_id, log or [game_id], intents, **kw)
    raw["hp"] = raw["max_hp"] = 20
    return raw

def rat_pack(*moves, ascension=0):
    cs = load(*[{**rat(m, ascension=ascension), "entity_id": f"TWO_TAILED_RAT_{i}"} for i, m in enumerate(moves)])
    cs.ascension = ascension
    return cs

def test_rats_read_their_history_from_the_move_log():
    cs = load(rat("SCRATCH", ["SCRATCH_MOVE", "SCREECH_MOVE", "DISEASE_BITE_MOVE", "SCRATCH_MOVE"]))
    acts, cooldown, backups = cs.enemies[0].counter % 3, cs.enemies[0].counter // 3 % 4, cs.enemies[0].counter // 12
    assert (acts, cooldown, backups) == (2, 2, 0)
    cs = load(rat("SCRATCH", ["SCRATCH_MOVE", "CALL_FOR_BACKUP_MOVE", "SCRATCH_MOVE"]))
    assert cs.enemies[0].counter == rat_counter(1, 0, 1)

def test_a_fresh_rat_does_not_call_for_backup_in_its_first_two_moves():
    for seed in range(120):
        rng.seed(seed)
        cs = rat_pack("SCRATCH", "SCRATCH", "SCRATCH")
        sim = CombatSimulator(cs)
        sim._play_enemy_turn()
        assert all(e.move_id != "CALL_FOR_BACKUP" for e in cs.enemies)

def test_scratch_and_bite_never_repeat_and_screech_waits_three_moves():
    for seed in range(60):
        rng.seed(seed)
        cs = rat_pack("SCRATCH")
        sim = CombatSimulator(cs)
        history = [cs.enemies[0].move_id]
        for _ in range(12):
            if cs.enemies[0].move_id == "CALL_FOR_BACKUP":
                break
            sim._play_enemy_turn()
            history.append(cs.enemies[0].move_id)
        for i in range(1, len(history)):
            if history[i] in ("SCRATCH", "DISEASE_BITE"):
                assert history[i] != history[i - 1]
            if history[i] == "SCREECH":
                assert "SCREECH" not in history[max(0, i - 3):i]

def test_a_rat_that_has_moved_twice_usually_calls_for_backup_and_a_new_rat_comes_in_at_the_front():
    called = 0
    for seed in range(100):
        rng.seed(seed)
        cs = load(rat("SCRATCH", ["SCRATCH_MOVE", "DISEASE_BITE_MOVE", "SCRATCH_MOVE"]))
        cs.enemies[0].move_id = "CALL_FOR_BACKUP"
        cs.enemies[0].attack_damage = cs.enemies[0].num_attacks = 0
        cs.enemies[0].counter = rat_counter(2, 0, 0)
        CombatSimulator(cs)._play_enemy_turn()
        assert len(cs.enemies) == 2 and cs.enemies[1].counter // 12 == 1 and cs.enemies[0].counter // 12 == 1
        assert cs.enemies[0].enemy_id.startswith("TWO_TAILED_RAT") and 17 <= cs.enemies[0].max_hp <= 21
        called += 1
    assert called == 100

def test_the_chance_of_calling_is_three_in_four_once_it_may():
    calls = 0
    for seed in range(400):
        rng.seed(seed)
        cs = load(rat("SCRATCH", ["SCRATCH_MOVE", "DISEASE_BITE_MOVE", "SCRATCH_MOVE"]))
        e = cs.enemies[0]
        e.counter = rat_counter(1, 0, 0)
        e.perform_turn(CombatSimulator(cs))           # its second move: now it may call
        calls += e.move_id == "CALL_FOR_BACKUP"
    assert 0.65 < calls / 400 < 0.85

def test_a_rat_calls_at_most_once_and_the_fight_calls_at_most_three_times_and_five_rats():
    cs = load(rat("SCRATCH"))
    e = cs.enemies[0]
    e.counter = rat_counter(2, 0, 3)
    assert enemy_choice_has_no_call(cs)
    e.counter = rat_counter(2, 0, 0)
    e.used_moves.add("CALL_FOR_BACKUP")
    assert enemy_choice_has_no_call(cs)
    cs = rat_pack("SCRATCH", "SCRATCH", "SCRATCH", "SCRATCH", "SCRATCH")
    for r in cs.enemies:
        r.counter = rat_counter(2, 0, 0)
    assert enemy_choice_has_no_call(cs)

def enemy_choice_has_no_call(cs):
    sim = CombatSimulator(cs)
    e = cs.enemies[0]
    for seed in range(80):
        rng.seed(seed)
        if e.moves[e.move_id].choose(e, sim) == "CALL_FOR_BACKUP":
            return False
    return True

def test_two_rats_never_both_call_in_the_same_round():
    for seed in range(60):
        rng.seed(seed)
        cs = rat_pack("SCRATCH", "SCRATCH")
        for r in cs.enemies:
            r.counter = rat_counter(1, 0, 0)
        CombatSimulator(cs)._play_enemy_turn()
        assert [r.move_id for r in cs.enemies].count("CALL_FOR_BACKUP") <= 1


# ---------------------------------------------------------------- Terror Eel
def eel(move="CRASH", hp=140, status_list=(), **kw):
    return at("TERROR_EEL", move, hp=hp, max_hp=140, status=[status("SHRIEK", 70), *status_list], **kw)

def test_eel_alternates_crash_and_thrash():
    assert moves_over(eel(), 4) == ["CRASH", "THRASH", "CRASH", "THRASH", "CRASH"]

def test_thrash_hits_three_times_and_the_vigor_goes_into_the_next_crash_only():
    cs = eel("THRASH")
    turn(cs)
    assert cs.player.current_hp == 80 - 9 and cs.enemies[0].status_amount(StatusId.VIGOR) == 6
    cs.enemies[0].check_against_bridge(raw_enemy("TERROR_EEL", "CRASH_MOVE", [], attack(16, 1, damage=22)), cs.player)
    turn(cs)
    assert cs.player.current_hp == 80 - 9 - 22 and StatusId.VIGOR not in cs.enemies[0].status

def test_shriek_stuns_the_eel_into_terror_when_a_hit_leaves_it_at_seventy_or_less():
    cs = eel()
    e = cs.enemies[0]
    e.apply_damage(60, cs.player, True)             # 80 left: nothing yet
    assert e.move_id != STUNNED and StatusId.SHRIEK in e.status
    e.apply_damage(10, cs.player, True)             # 70 left
    assert e.move_id == STUNNED and e.after_stun == "TERROR" and StatusId.SHRIEK not in e.status

def test_a_blocked_hit_does_not_set_off_shriek():
    cs = eel(hp=70)
    e = cs.enemies[0]
    e.block = 20
    e.apply_damage(5, cs.player, True)
    assert e.move_id != STUNNED and StatusId.SHRIEK in e.status

def test_after_the_shriek_the_eel_loses_a_turn_then_terrifies_then_crashes():
    cs = eel(hp=120)
    e = cs.enemies[0]
    e.apply_damage(60, cs.player, True)
    hp = cs.player.current_hp
    turn(cs)
    assert cs.player.current_hp == hp and e.move_id == "TERROR"
    turn(cs)
    assert cs.player.status_amount(StatusId.VULNERABLE) == 99 and e.move_id == "CRASH"
    turn(cs)
    assert cs.player.current_hp == hp - int(16 * 1.5)

def test_shriek_goes_off_once_and_a_tough_eel_screams_at_seventy_five():
    cs = eel()
    e = cs.enemies[0]
    e.apply_damage(70, cs.player, True)
    turn(cs)
    turn(cs)
    e.apply_damage(5, cs.player, True)
    assert e.move_id != STUNNED
    cs = at("TERROR_EEL", "CRASH", ascension=8, hp=140, max_hp=150, status=[status("SHRIEK", 75)])
    e = cs.enemies[0]
    e.apply_damage(66, cs.player, True)
    assert e.move_id == STUNNED


# ---------------------------------------------------------------- captured from the game (Tests/data/act1_underdocks)
from sts2_lite import verify
from sts2_lite.Tests import captures

def under(enemy, name):
    return captures.load(enemy, name, captures.UNDERDOCKS)

def enemy_diffs(cs, want):
    return [d for d in verify.compare(cs, want) if d.startswith("enemy") and "hp" not in d]

def test_every_phase_two_capture_loads_with_moves_and_damage_agreeing():
    for enemy, names in (("gremlin_merc", ("turn_2", "after_killed", "after_killed_next_turn")),
                         ("two_tailed_rats", ("turn_1", "summoning", "after_summon")),
                         ("living_fog", ("turn_1", "turn_2", "turn_3")),
                         ("terror_eel", ("before_shriek", "shriek", "after_shriek"))):
        for name in names:
            under(enemy, name)

def test_capture_the_merc_dying_leaves_a_sneaky_and_a_fat_gremlin_carrying_the_gold():
    cs = under("gremlin_merc", "turn_2")
    assert cs.enemies[0].status[StatusId.THIEVERY].records == [[20, 20]]
    cs.player.gold = 79
    cs.enemies[0].current_hp = 0
    sim = CombatSimulator(cs)
    sim.resolve_deaths()
    want = under("gremlin_merc", "after_killed")
    assert enemy_diffs(cs, want) == []
    assert not sim.is_over

def test_capture_the_gremlins_next_turn_one_tackles_and_the_other_flees():
    cs = under("gremlin_merc", "after_killed")
    turn(cs)
    want = under("gremlin_merc", "after_killed_next_turn")
    assert enemy_diffs(cs, want) == []
    turn(cs)
    assert cs.player.current_hp == want.player.current_hp - 9
    assert [e.enemy_id.rpartition("_")[0] for e in cs.enemies] == ["SNEAKY_GREMLIN"]

def test_capture_living_fog_gases_then_bloats_in_a_bomb():
    cs = under("living_fog", "turn_1")
    turn(cs)
    assert enemy_diffs(cs, under("living_fog", "turn_2")) == [] and cs.player.status_amount(StatusId.SMOGGY) == 1
    cs = under("living_fog", "turn_2")
    turn(cs)
    assert enemy_diffs(cs, under("living_fog", "turn_3")) == []

def test_capture_a_skill_blocked_by_smog_is_read_as_smogged_not_unplayable():
    cs = under("living_fog", "turn_2")
    sim = CombatSimulator(cs)
    assert cs.player.smogged
    skills = [c for c in cs.player.hand if c.card_id == CardId.DEFEND_IRONCLAD]
    assert skills and not any(c.can_play_card(sim, 0) for c in skills)
    assert all(c.can_play_card(sim, 0) for c in cs.player.hand if c.card_id == CardId.STRIKE_IRONCLAD)
    sim.end_turn()
    assert cs.player.smogged is False and all(c.can_play_card(sim, 0) for c in skills)

def test_capture_a_fresh_turn_with_smoggy_is_not_smogged():
    cs = under("living_fog", "turn_3")
    assert cs.player.smogged is False

def test_capture_the_gas_bomb_explodes_for_eight():
    cs = under("living_fog", "turn_3")
    turn(cs)
    assert cs.player.current_hp == 80 - 8 - 8
    assert [e.enemy_id.rpartition("_")[0] for e in cs.enemies] == ["LIVING_FOG"]

def test_capture_eel_stunned_after_the_shriek_then_terrifies_then_crashes_for_twenty_four():
    cs = under("terror_eel", "before_shriek")
    assert cs.enemies[0].move_id == STUNNED and cs.enemies[0].after_stun == "TERROR"
    turn(cs)
    assert enemy_diffs(cs, under("terror_eel", "shriek")) == []
    turn(cs)
    assert enemy_diffs(cs, under("terror_eel", "after_shriek")) == []
    assert cs.player.status_amount(StatusId.VULNERABLE) == 99
    turn(cs)
    assert cs.player.current_hp == 80 - 24
# the rat captures live in two_tailed_rats: turn_1 (three rats), summoning (three, one about to call), after_summon (four)
# the rat captures are filed under gremlin_merc: turn_1 (three rats), summoning (three, one about to call), after_summon (four)
def test_capture_three_rats_load_with_their_histories():
    cs = under("two_tailed_rats", "summoning")
    parts = [(r.counter % 3, r.counter // 3 % 4, r.counter // 12) for r in cs.enemies]
    assert parts == [(2, 2, 0), (2, 0, 0), (2, 0, 0)]       # the first screeched two moves ago, so it cannot yet again

def test_capture_a_rat_calls_for_backup_and_the_new_one_stands_in_front():
    for seed in range(30):
        rng.seed(seed)
        cs = under("two_tailed_rats", "summoning")
        turn(cs)
        want = under("two_tailed_rats", "after_summon")
        assert len(cs.enemies) == len(want.enemies) == 4
        assert cs.enemies[0].max_hp in range(17, 22)
        assert cs.enemies[1].move_id != "CALL_FOR_BACKUP"            # the caller used its one call
        assert [r.counter // 12 for r in cs.enemies] == [1, 1, 1, 1]
        assert [r.counter // 12 for r in want.enemies] == [1, 1, 1, 1]

def test_capture_after_the_summon_a_second_rat_may_already_have_chosen_to_call():
    cs = under("two_tailed_rats", "after_summon")
    calling = [r for r in cs.enemies if r.move_id == "CALL_FOR_BACKUP"]
    assert len(calling) == 1 and calling[0] is cs.enemies[2]
