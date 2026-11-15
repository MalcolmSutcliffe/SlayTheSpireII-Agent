"""Builds a fight from an encounter id: the monsters with their rolled hit points, starting powers and first moves.

`build_enemies` follows what the game does when it adds an encounter's monsters to a room (hit points, `AfterAddedToRoom` powers, the
state machine's initial state). `build_combat` wraps them in a CombatState around a player that is already set up for the fight."""
from __future__ import annotations

from sts2_lite.combat import CombatState
from sts2_lite.enemy import Enemy
from sts2_lite.enemy_moves import MOVE_TABLES, TOUGH_ASCENSION, table_move_id
from sts2_lite.enemy_moves.core import DEADLY_ASCENSION, Move, MoveTable
from sts2_lite.status import StatusId, StatusInstance
from sts2_lite.encounters.definitions import ENCOUNTERS, Spawn
from sts2_lite.encounters.monsters import MONSTERS

NIBBIT_ALONE, NIBBIT_FRONT, NIBBIT_BACK = "BUTT_MOVE", "SLICE_MOVE", "HISS_MOVE"

# monsters that use another monster's moves (the Mysterious Knight is a Flail Knight), and event dummies that never act
TABLE_ALIASES = {"MYSTERIOUS_KNIGHT": "FLAIL_KNIGHT"}
INERT = {"BATTLE_FRIEND_V1", "BATTLE_FRIEND_V2", "BATTLE_FRIEND_V3", "ARCHITECT"}


def _inert(ascension : int) -> MoveTable:
    return {"NOTHING": Move(frozenset(), "NOTHING")}


def move_table(monster : str):
    if monster in INERT:
        return _inert
    return MOVE_TABLES.get(TABLE_ALIASES.get(monster, monster))


def power_amount(kind : str, base : int, high : int, ascension : int) -> int:
    if kind == "tough":
        return high if ascension >= TOUGH_ASCENSION else base
    if kind == "deadly":
        return high if ascension >= DEADLY_ASCENSION else base
    return base


def opening_move(monster : str, spawn : Spawn, rng) -> str:
    """The game id of the move the monster shows on turn one."""
    return _resolve(MONSTERS[monster].opening, spawn, rng)


def _resolve(opening : tuple, spawn : Spawn, rng) -> str:
    kind = opening[0]
    flags = spawn.flags
    if kind == "fixed":
        return opening[1]
    if kind == "flag":
        return opening[2] if flags.get(opening[1], False) else opening[3]
    if kind == "idx":
        return opening[1][flags.get("starter_idx", 0) % 3]
    if kind == "slot":
        if spawn.slot in opening[1]:
            return opening[1][spawn.slot]
        return _resolve(opening[2], spawn, rng)
    if kind == "random":
        moves, weights = zip(*opening[1])
        return rng.choices(moves, weights=weights)[0]
    if kind == "nibbit":
        if flags.get("is_alone"):
            return NIBBIT_ALONE
        return NIBBIT_FRONT if flags.get("is_front") else NIBBIT_BACK
    if kind == "rat":
        if "starter_idx" in flags:
            return ("SCRATCH_MOVE", "DISEASE_BITE_MOVE", "SCREECH_MOVE")[flags["starter_idx"] % 3]
        return rng.choice(("SCRATCH_MOVE", "DISEASE_BITE_MOVE", "SCREECH_MOVE"))
    if kind == "wriggler":
        if flags.get("start_stunned"):
            return "SPAWNED_MOVE"
        return "WRIGGLE_MOVE" if spawn.slot in ("wriggler2", "wriggler4") else "NASTY_BITE_MOVE"
    raise ValueError(f"unknown opening {opening!r}")


def roll_hp(monster : str, ascension : int, rng) -> int:
    low, high, tough_low, tough_high = MONSTERS[monster].hp
    if ascension >= TOUGH_ASCENSION:
        low, high = tough_low, tough_high
    return rng.randrange(low, high + 1)


def make_enemy(spawn : Spawn, number : int, ascension : int, rng, teammates : list[Enemy] = ()) -> Enemy:
    """One monster as the game adds it to the room. `number` is its place among monsters of its kind (the number in its entity id)."""
    monster = spawn.monster
    setup = MONSTERS[monster]
    e = Enemy()
    e.max_hp = roll_hp(monster, ascension, rng)
    if monster.startswith("DECIMILLIPEDE_SEGMENT"):
        e.max_hp = _unique_segment_hp(e.max_hp, monster, ascension, teammates)
    e.current_hp = e.max_hp
    if "starting_hp_reduction" in spawn.flags:
        e.current_hp = max(1, e.current_hp - spawn.flags["starting_hp_reduction"])
    e.enemy_id = f"{monster}_{number}"
    e.slot = number
    e.status = {}
    for status, who, kind, base, high in setup.powers:
        if who == "self":
            e.status[StatusId[status]] = StatusInstance(StatusId[status], power_amount(kind, base, high, ascension))
    e.is_minion = StatusId.MINION in e.status
    table = move_table(monster)
    if table is None:
        raise KeyError(f"no move table for {monster}")
    e.moves = table(ascension)
    game_move = opening_move(monster, spawn, rng)
    e.move_id = table_move_id(TABLE_ALIASES.get(monster, monster), game_move, e.moves)
    if e.move_id is None:
        raise KeyError(f"{monster}: the opening move {game_move} is not in its move table")
    first = e.moves[e.move_id]
    e.attack_damage = e._move_damage(first)
    e.num_attacks = e._move_hits(first)
    return e


def _unique_segment_hp(hp : int, monster : str, ascension : int, teammates) -> int:
    """DecimillipedeSegment.AfterAddedToRoom: an even maximum that no other segment has."""
    low, high, tough_low, tough_high = MONSTERS[monster].hp
    if ascension >= TOUGH_ASCENSION:
        low, high = tough_low, tough_high
    taken = {t.max_hp for t in teammates}
    if hp % 2 == 1:
        hp += 1
    while hp in taken:
        hp += 2
        if hp > high:
            hp = low
    return hp


def build_enemies(encounter_id : str, ascension : int, rng, variant : int | None = None) -> list[Enemy]:
    spawns = ENCOUNTERS[encounter_id].monsters(rng, variant)
    enemies : list[Enemy] = []
    seen : dict[str, int] = {}
    for spawn in spawns:
        number = seen.get(spawn.monster, 0)
        seen[spawn.monster] = number + 1
        enemies.append(make_enemy(spawn, number, ascension, rng, enemies))
    return enemies


def build_combat(encounter_id : str, ascension : int, player, rng, max_energy : int = 3, final_fight : bool = False, variant : int | None = None) -> CombatState:
    """A CombatState for the encounter. The player must already be set up for the fight (draw pile shuffled, opening hand drawn, relics applied)."""
    cs = CombatState()
    cs.player = player
    cs.enemies = build_enemies(encounter_id, ascension, rng, variant)
    cs.ascension = ascension
    cs.turn_number = 1
    cs.max_energy = cs.energy = max_energy
    cs.final_fight = final_fight
    for enemy, spawn_status in ((e, MONSTERS[e.enemy_id.rpartition("_")[0]]) for e in cs.enemies):
        for status, who, kind, base, high in spawn_status.powers:
            if who == "player":
                player.apply_status(StatusId[status], power_amount(kind, base, high, ascension))
    return cs
