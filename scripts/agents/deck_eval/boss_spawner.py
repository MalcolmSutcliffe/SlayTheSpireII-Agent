"""The act bosses: which encounter belongs to which act (and which version of act 1), and fresh round-1 fights for the bosses that no run has captured.

A captured boss is used as it was captured. Bosses without a capture are built here from the game's source (sts2_decompiled Models/Monsters,
Models/Encounters): hit points by ascension, first move, starting powers. Damage, hits and the rest of the moves come from the sim's own
move tables, so a spawned boss plays like a captured one."""
from __future__ import annotations
import copy

from sts2_lite.enemy_moves.registry import MOVE_TABLES
from sts2_lite.enemy_moves.core import TOUGH_ASCENSION

from agents.deck_eval.fight_pool import FightTemplate

# encounter id -> (act, act model); act 1 is Overgrowth or Underdocks, and the boss tells which
BOSS_ACTS = {
    "VANTOM_BOSS": (1, "OVERGROWTH"), "CEREMONIAL_BEAST_BOSS": (1, "OVERGROWTH"), "THE_KIN_BOSS": (1, "OVERGROWTH"),
    "WATERFALL_GIANT_BOSS": (1, "UNDERDOCKS"), "SOUL_FYSH_BOSS": (1, "UNDERDOCKS"), "LAGAVULIN_MATRIARCH_BOSS": (1, "UNDERDOCKS"),
    "THE_INSATIABLE_BOSS": (2, "HIVE"), "KNOWLEDGE_DEMON_BOSS": (2, "HIVE"), "KAISER_CRAB_BOSS": (2, "HIVE"),
    "QUEEN_BOSS": (3, "GLORY"), "TEST_SUBJECT_BOSS": (3, "GLORY"), "AEONGLASS_BOSS": (3, "GLORY"),
}

# a monster of the encounter -> the encounter (to tell which boss a capture is)
BOSS_MONSTERS = {
    "VANTOM": "VANTOM_BOSS", "CEREMONIAL_BEAST": "CEREMONIAL_BEAST_BOSS", "KIN_FOLLOWER": "THE_KIN_BOSS", "KIN_PRIEST": "THE_KIN_BOSS",
    "WATERFALL_GIANT": "WATERFALL_GIANT_BOSS", "SOUL_FYSH": "SOUL_FYSH_BOSS", "LAGAVULIN_MATRIARCH": "LAGAVULIN_MATRIARCH_BOSS",
    "THE_INSATIABLE": "THE_INSATIABLE_BOSS", "KNOWLEDGE_DEMON": "KNOWLEDGE_DEMON_BOSS", "CRUSHER": "KAISER_CRAB_BOSS", "ROCKET": "KAISER_CRAB_BOSS",
    "QUEEN": "QUEEN_BOSS", "TORCH_HEAD_AMALGAM": "QUEEN_BOSS", "TEST_SUBJECT": "TEST_SUBJECT_BOSS", "AEONGLASS": "AEONGLASS_BOSS",
}

# encounter -> (monster, name, hp, hp from the Tough Enemies ascension, first move): MinInitialHp = MaxInitialHp, GenerateMoveStateMachine's first state
SPAWNED = {
    "WATERFALL_GIANT_BOSS": ("WATERFALL_GIANT", "Waterfall Giant", 240, 250, "PRESSURIZE"),
    "SOUL_FYSH_BOSS": ("SOUL_FYSH", "Soul Fysh", 211, 221, "BECKON"),
    "KNOWLEDGE_DEMON_BOSS": ("KNOWLEDGE_DEMON", "Knowledge Demon", 379, 399, "CURSE_OF_KNOWLEDGE"),
}


def normalize_boss_id(encounter : str | None) -> str | None:
    if not encounter:
        return None
    enc = str(encounter).strip().upper().replace(" ", "_")
    return enc if enc.endswith("_BOSS") else enc + "_BOSS"


def boss_of(enemy_ids : list[str]) -> str | None:
    """The boss encounter a list of entity ids (VANTOM_0, ...) belongs to."""
    for entity in enemy_ids:
        monster = entity.rpartition("_")[0]
        if monster in BOSS_MONSTERS:
            return BOSS_MONSTERS[monster]
    return None


def _intents(move) -> list[dict]:
    out = []
    for kind in sorted(move.intents):
        if kind == "attack":
            out.append({"type": "Attack", "base_damage": move.damage, "hits": move.hits, "damage": move.damage,
                        "total_damage": move.damage * move.hits, "label": f"{move.damage}x{move.hits}" if move.hits > 1 else str(move.damage)})
        else:
            out.append({"type": kind.title() if kind != "statuscard" else "StatusCard", "label": ""})
    return out


def enemy_dict(monster : str, name : str, hp : int, first_move : str, ascension : int) -> dict:
    """A bridge-style enemy at the start of a fight on its first move."""
    move = MOVE_TABLES[monster](ascension)[first_move]
    return {"entity_id": f"{monster}_0", "combat_id": 1, "name": name, "hp": hp, "max_hp": hp, "block": 0, "status": [],
            "move_id": f"{first_move}_MOVE", "follow_up_id": f"{move.next_move}_MOVE", "move_log": [f"{first_move}_MOVE"], "intents": _intents(move)}


def spawn_boss(encounter : str, base : FightTemplate, ascension : int) -> FightTemplate | None:
    """Round 1 of a boss with no capture, on the layout of `base` (any captured fight of that act: its player is replaced anyway)."""
    spec = SPAWNED.get(normalize_boss_id(encounter))
    if spec is None:
        return None
    monster, name, hp, tough_hp, first = spec
    state = copy.deepcopy(base.state)
    state["room_type"] = "boss"
    state["enemies"] = [enemy_dict(monster, name, tough_hp if ascension >= TOUGH_ASCENSION else hp, first, ascension)]
    for key in ("context", "run"):
        if key in state:
            state[key] = {**state[key], "ascension": ascension, "act": BOSS_ACTS[normalize_boss_id(encounter)][0]}
    state.pop("battle", None)
    return FightTemplate(name.replace(" ", "_"), BOSS_ACTS[normalize_boss_id(encounter)][0], "boss", state, boss=normalize_boss_id(encounter),
                         variant=BOSS_ACTS[normalize_boss_id(encounter)][1] if BOSS_ACTS[normalize_boss_id(encounter)][0] == 1 else None)


def bosses_of_act(pool : list[FightTemplate], act : int, ascension : int, encounter : str | None = None, variant : str | None = None) -> list[FightTemplate]:
    """Every boss of the act the sim can play (captured ones, and spawned ones for the bosses with no capture); only `encounter` when given."""
    encounter = normalize_boss_id(encounter)
    wanted = [e for e, (a, v) in BOSS_ACTS.items() if a == act and (encounter is None or e == encounter) and (variant is None or v == variant)]
    out, bases = [], [t for t in pool if t.act == act]
    for e in wanted:
        captured = [t for t in pool if t.kind == "boss" and t.boss == e]
        if captured:
            out.extend(captured)
        elif bases and e in SPAWNED:
            out.append(spawn_boss(e, bases[0], ascension))
    return out
