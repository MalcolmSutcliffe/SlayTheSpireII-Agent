"""The act bosses: which encounter belongs to which act (and which version of act 1), read from the engine's act tables.

The bosses used to be spawned here for the ones no run had captured; the engine builds every encounter (sts2_lite.encounters.build_combat), so a
boss is only chosen from the pool now."""
from __future__ import annotations

from sts2_lite.encounters import ACTS

from agents.deck_eval.fight_pool import ACT_NUMBER, FightTemplate

# encounter id -> (act, act model); act 1 is Overgrowth or Underdocks, and the boss tells which
BOSS_ACTS = {boss.id: (ACT_NUMBER[act.id], act.id) for act in ACTS.values() for boss in act.bosses}


def normalize_boss_id(encounter : str | None) -> str | None:
    if not encounter:
        return None
    enc = str(encounter).strip().upper().replace(" ", "_")
    return enc if enc.endswith("_BOSS") else enc + "_BOSS"


def bosses_of_act(pool : list[FightTemplate], act : int, encounter : str | None = None, variant : str | None = None) -> list[FightTemplate]:
    """Every boss of the act in the pool; only `encounter` when given, only the act 1 `variant` ("OVERGROWTH" / "UNDERDOCKS") when given."""
    encounter = normalize_boss_id(encounter)
    return [t for t in pool if t.kind == "boss" and t.act == act and (encounter is None or t.boss == encounter) and (variant is None or t.variant == variant)]
