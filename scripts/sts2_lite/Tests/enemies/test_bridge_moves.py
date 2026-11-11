"""Reading enemy moves from the bridge's move_id / move_log / base_damage. Run from scripts/: python -m pytest sts2_lite/Tests"""
import os
import re
from pathlib import Path

import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite.combat import CombatState
from sts2_lite.enemy import BridgeMismatch
from sts2_lite.enemy_moves import GAME_MOVE_ALIASES, MOVE_TABLES, table_move_id
from sts2_lite.status import StatusId

DECOMPILED = Path(os.environ.get("STS2_DECOMPILED") or Path(__file__).resolve().parents[4] / "sts2_decompiled")


def attack(base, hits=1, damage=None, extra=()):
    damage = base if damage is None else damage
    return [{"type": "Attack", "label": f"{damage}x{hits}" if hits > 1 else str(damage), "base_damage": base,
             "hits": hits, "damage": damage, "total_damage": damage * hits}, *extra]


def raw_enemy(monster, move_id, log, intents, status=(), slot=0):
    return {"entity_id": f"{monster}_{slot}", "max_hp": 40, "hp": 40, "block": 0, "status": list(status),
            "move_id": move_id, "move_log": list(log), "intents": intents}


def load(*enemies, player_status=()):
    return CombatState.from_dict({
        "round": 1, "energy": 3, "max_energy": 3,
        "player": {"max_hp": 80, "hp": 80, "block": 0, "status": list(player_status),
                   "hand": [], "draw_pile": [], "discard_pile": [], "deck": []},
        "enemies": list(enemies)})


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)


# ---------------------------------------------------------------- damage
def test_base_damage_and_hits_are_read_directly():
    cs = load(raw_enemy("BYRDONIS", "PECK_MOVE", ["PECK_MOVE"], attack(3, 3)))
    assert (cs.enemies[0].attack_damage, cs.enemies[0].num_attacks) == (3, 3)

def test_base_damage_is_not_inverted_through_strength():
    strength = {"id": "STRENGTH_POWER", "amount": 2}
    cs = load(raw_enemy("BYRDONIS", "PECK_MOVE", ["PECK_MOVE"], attack(3, 3, damage=5), status=[strength]))
    assert cs.enemies[0].attack_damage == 3 and cs.enemies[0].damage_candidates is None

def test_damage_the_simulator_cannot_reproduce_is_reported():
    strength = {"id": "STRENGTH_POWER", "amount": 2}
    with pytest.raises(BridgeMismatch, match="damage 5 but the game shows 9"):
        load(raw_enemy("BYRDONIS", "PECK_MOVE", ["PECK_MOVE"], attack(3, 3, damage=9), status=[strength]))

def test_a_mismatch_only_warns_when_not_strict(monkeypatch, caplog):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", False)
    load(raw_enemy("BYRDONIS", "PECK_MOVE", ["PECK_MOVE"], attack(3, 3, damage=9)))
    assert "game shows 9" in caplog.text

def test_player_vulnerable_is_part_of_the_displayed_damage():
    vulnerable = {"id": "VULNERABLE_POWER", "amount": 1}
    load(raw_enemy("BYRDONIS", "PECK_MOVE", ["PECK_MOVE"], attack(4, 3, damage=6)), player_status=[vulnerable])

def test_older_bridge_without_base_damage_still_loads():
    cs = load({"entity_id": "BYRDONIS_0", "max_hp": 40, "hp": 40, "block": 0, "status": [],
               "intents": [{"type": "Attack", "label": "3x3"}]})
    assert (cs.enemies[0].attack_damage, cs.enemies[0].num_attacks) == (3, 3)


# ---------------------------------------------------------------- move identity
def test_move_id_selects_the_move():
    cs = load(raw_enemy("NIBBIT", "SLICE_MOVE", ["BUTT_MOVE", "SLICE_MOVE"],
                        attack(6, extra=[{"type": "Defend", "label": ""}])))
    assert cs.enemies[0].move_id == "SLICE"

def test_aliased_ids_map_to_table_keys():
    cs = load(raw_enemy("BYGONE_EFFIGY", "SLASHES_MOVE", ["SLEEP_MOVE", "WAKE_MOVE", "SLASHES_MOVE"], attack(13)))
    assert cs.enemies[0].move_id == "SLASH"

def test_moves_that_look_alike_are_told_apart_by_id_not_round():
    swing = attack(5, extra=[{"type": "Defend", "label": ""}])
    for move_id in ("SWING_1", "SWING_2"):
        cs = load(raw_enemy("AXE_RUBY_RAIDER", move_id, [move_id], swing))     # round 1 would mean SWING_1
        assert cs.enemies[0].move_id == move_id

def test_a_move_the_table_only_reaches_by_random_choice_is_readable():
    swipe = attack(8, extra=[{"type": "Buff", "label": ""}])
    cs = load(raw_enemy("FOGMOG", "SWIPE_RANDOM_MOVE", ["SWIPE_MOVE", "SWIPE_RANDOM_MOVE"], swipe))
    assert cs.enemies[0].move_id == "SWIPE_RANDOM"

def test_an_unknown_id_is_reported():
    with pytest.raises(BridgeMismatch):
        load(raw_enemy("NIBBIT", "NEW_MOVE", ["NEW_MOVE"], attack(12)))

def test_enemies_without_a_table_keep_the_intent_damage():
    cs = load(raw_enemy("TOADPOLE", "SPIKE_SPIT_MOVE", ["SPIKEN_MOVE", "SPIKE_SPIT_MOVE"], attack(3, 3)))
    e = cs.enemies[0]
    assert e.moves is None and (e.attack_damage, e.num_attacks) == (3, 3)


# ---------------------------------------------------------------- history
def test_streak_counts_the_run_ending_at_the_current_move():
    cs = load(raw_enemy("LEAF_SLIME_M", "CLUMP_SHOT", ["STICKY_SHOT", "CLUMP_SHOT", "CLUMP_SHOT"], attack(8)))
    assert cs.enemies[0].move_streak == 2

def test_used_moves_are_the_earlier_log_entries():
    swipe = attack(8, extra=[{"type": "Buff", "label": ""}])
    cs = load(raw_enemy("FOGMOG", "SWIPE_MOVE", ["ILLUSION_MOVE", "SWIPE_MOVE"], swipe))
    assert cs.enemies[0].used_moves == {"ILLUSION"} and cs.enemies[0].move_streak == 1

def test_the_current_move_is_not_yet_used():
    cs = load(raw_enemy("NIBBIT", "BUTT_MOVE", ["BUTT_MOVE"], attack(12)))
    assert cs.enemies[0].used_moves == set()


# ---------------------------------------------------------------- the id mapping
@pytest.mark.parametrize("monster", sorted(MOVE_TABLES))
def test_every_alias_names_a_table_move(monster):
    table = MOVE_TABLES[monster](0)
    assert all(key in table for key in GAME_MOVE_ALIASES.get(monster, {}).values())

def test_table_move_id_defaults():
    table = MOVE_TABLES["NIBBIT"](0)
    assert table_move_id("NIBBIT", "HISS_MOVE", table) == "HISS"
    assert table_move_id("NIBBIT", "HISS", table) == "HISS"
    assert table_move_id("NIBBIT", "INIT_MOVE", table) is None


def _game_ids(monster):
    if monster.startswith("DECIMILLIPEDE_SEGMENT_"):
        monster = "DECIMILLIPEDE_SEGMENT"       # the three segments share their moves in the abstract base class
    name = "".join(w.capitalize() for w in monster.split("_"))
    files = [f for f in (DECOMPILED / "MegaCrit.Sts2.Core.Models.Monsters").glob("*.cs") if f.stem.lower() == name.lower()]
    return set(re.findall(r'new MoveState\("([A-Z0-9_]+)"', files[0].read_text())) if files else None

@pytest.mark.skipif(not DECOMPILED.exists(), reason="decompiled game source not present")
@pytest.mark.parametrize("monster", sorted(MOVE_TABLES))
def test_every_table_move_corresponds_to_a_game_move(monster):
    """Table keys are the simulator's names; each must be reachable from a real move state id."""
    ids = _game_ids(monster)
    assert ids, f"no decompiled source for {monster}"
    table = MOVE_TABLES[monster](0)
    reachable = {table_move_id(monster, g, table) for g in ids}
    synthetic = {"STUN", "STUNNED"}      # simulator-only moves
    assert set(table) - reachable - synthetic == set()
