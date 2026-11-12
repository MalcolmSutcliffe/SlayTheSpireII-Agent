"""Ascension 8 (Tough Enemies: more HP and block) and 9 (Deadly Enemies: more damage and Strength), checked against the decompiled
monsters. Every `X => AscensionHelper.GetValueIfAscension(level, ascended, base)` of a damage / block / hits property is matched to the move
of that name in the sim's table. Run from scripts/: python -m pytest sts2_lite/Tests"""
import os
import re
from pathlib import Path

import pytest

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy import Enemy
from sts2_lite.enemy_moves import HATCHLING_HP, MOVE_TABLES, SPAWN_HP
from sts2_lite.status import StatusId
from sts2_lite.verify import _fresh_spawn_hp_is_random
from sts2_lite.Tests.enemies.test_glory_simple import at, turn

DECOMPILED = Path(os.environ.get("STS2_DECOMPILED") or Path(__file__).resolve().parents[4] / "sts2_decompiled")
MONSTERS = DECOMPILED / "MegaCrit.Sts2.Core.Models.Monsters"
needs_source = pytest.mark.skipif(not MONSTERS.exists(), reason="decompiled monsters not available")

VALUE = re.compile(r"\b(\w+)\s*=>\s*AscensionHelper\.GetValueIfAscension\(AscensionLevel\.(\w+),\s*(-?\d+),\s*(-?\d+)\)")
FIELDS = {"Damage": "damage", "Block": "block", "Repeat": "hits", "Hits": "hits"}

def snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()

def source_values():
    out = []
    for path in sorted(MONSTERS.glob("*.cs")):
        monster = snake(path.stem)
        for name, level, ascended, base in VALUE.findall(path.read_text()):
            out.append((monster, name, level, int(ascended), int(base)))
    return out


@needs_source
def test_damage_block_and_hits_follow_the_source():
    """178 of the properties name their move outright (BiteDamage -> BITE.damage): all of them must match at ascension 0 and at 8 / 9."""
    checked = []
    for monster, name, level, ascended, base in source_values():
        m = re.match(r"(.+?)(Damage|Block|Repeat|Hits)$", name)
        if monster not in MOVE_TABLES or not m or name.startswith(("Min", "Max")):
            continue
        key, field = snake(m.group(1)), FIELDS[m.group(2)]
        plain, ascended_table = MOVE_TABLES[monster](0), MOVE_TABLES[monster](9 if level == "DeadlyEnemies" else 8)
        moves = [k for k in plain if k == key or k.startswith(key) or key.startswith(k)]
        if not moves:
            continue
        assert any(getattr(plain[k], field) == base and getattr(ascended_table[k], field) == ascended for k in moves), \
            f"{monster}.{name}: the game has {base} -> {ascended}, the sim has {[(k, getattr(plain[k], field), getattr(ascended_table[k], field)) for k in moves]}"
        checked.append(name)
    assert len(checked) > 150

@needs_source
def test_spawn_hit_points_follow_the_source():
    for monster, (low, high, tough_low, tough_high) in SPAWN_HP.items():
        text = (MONSTERS / (monster.title().replace("_", "") + ".cs")).read_text()
        def hp(prop):
            m = re.search(prop + r"\s*=>\s*(?:AscensionHelper\.GetValueIfAscension\(AscensionLevel\.ToughEnemies,\s*(\d+),\s*(\d+)\)|(\d+)|MinInitialHp);", text)
            return (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(3)),) * 2 if m.group(3) else None
        mn, mx = hp("MinInitialHp"), hp("MaxInitialHp") or hp("MinInitialHp")
        assert (low, high, tough_low, tough_high) == (mn[1], mx[1], mn[0], mx[0]), monster


# ---------------------------------------------------------------- what the sim does with them
def test_spawned_monsters_roll_the_tougher_hit_points_from_ascension_8():
    for ascension, expected in ((7, (17, 21)), (8, (18, 22)), (10, (18, 22))):
        seen = {Enemy.spawn("WRIGGLER", 0, ascension).max_hp for _ in range(200)}
        assert (min(seen), max(seen)) == expected

def test_a_spawned_gas_bomb_has_one_more_hit_point_from_ascension_8():
    assert Enemy.spawn("GAS_BOMB", 0, 7).max_hp == 7 and Enemy.spawn("GAS_BOMB", 0, 8).max_hp == 8

def test_a_hatched_egg_has_the_tougher_hatchling_hit_points():
    assert HATCHLING_HP == ((19, 22), (20, 23))

def test_the_verifier_range_follows_the_ascension():
    class E:
        def __init__(self, hp): self.enemy_id, self.max_hp, self.current_hp = "WRIGGLER_0", hp, hp
    assert _fresh_spawn_hp_is_random(E(17), E(21), 0) and not _fresh_spawn_hp_is_random(E(17), E(21), 8)
    assert _fresh_spawn_hp_is_random(E(18), E(22), 8) and not _fresh_spawn_hp_is_random(E(18), E(22), 0)

def test_the_deadly_numbers_are_used_from_ascension_9_and_not_before():
    for ascension, damage in ((0, 12), (8, 12), (9, 13)):
        assert MOVE_TABLES["NIBBIT"](ascension)["BUTT"].damage == damage

def test_the_loaded_ascension_builds_the_monsters_tables():
    """The bridge's context carries the ascension; the monsters of the state are built with it (and so are the ones summoned later)."""
    from sts2_lite.combat import CombatState
    from sts2_lite.Tests.enemies.test_bridge_moves import raw_enemy, attack
    for ascension, strength in ((8, 2), (9, 3)):
        raw = {"round": 1, "energy": 3, "max_energy": 3, "context": {"act": 1, "floor": 3, "ascension": ascension},
               "player": {"max_hp": 80, "hp": 80, "block": 0, "status": [], "hand": [], "draw_pile": [], "discard_pile": [], "deck": []},
               "enemies": [raw_enemy("NIBBIT", "HISS_MOVE", ["BUTT_MOVE", "SLICE_MOVE", "HISS_MOVE"], [{"type": "Buff", "label": ""}])]}
        cs = CombatState.from_dict(raw)
        assert cs.ascension == ascension
        turn(cs)
        assert cs.enemies[0].status_amount(StatusId.STRENGTH) == strength

def test_the_forgotten_dread_uses_15_at_ascension_9_plus_its_dexterity():
    assert MOVE_TABLES["THE_FORGOTTEN"](8)["DREAD"].damage == 13 and MOVE_TABLES["THE_FORGOTTEN"](9)["DREAD"].damage == 15
