"""The route the agent has planned through the map, and the kinds of map nodes: shared by the map planner (agents/pathing.py) and the
deck choosers that walk the route ahead (agents/deck_eval)."""
from __future__ import annotations

from dataclasses import dataclass, field


def node_kind(point_type : str | None) -> str:
    """The kind of a map node from the type the bridge reports: "combat" | "elite" | "rest" | "unknown" | "treasure" | "shop" | "boss" | "other"."""
    t = (point_type or "").lower().replace("_", "")
    for kind, names in (("combat", ("monster", "combat")), ("elite", ("elite",)), ("rest", ("restsite", "rest")),
                        ("unknown", ("unknown", "question")), ("treasure", ("treasure",)), ("shop", ("shop", "merchant")), ("boss", ("boss",))):
        if t in names:
            return kind
    return "other"


@dataclass
class PlannedRoute:
    """The route the last map decision chose: kinds[0] is the node just chosen ("combat" | "elite" | "rest" | "unknown" | "treasure" |
    "shop" | "boss" | "other"). `combats_before` is the combats of this act fought before it; the deck evaluator reads the fights ahead from it."""
    kinds : list[str]
    combats_before : int
    act : int
    boss : str | None = None        # the act's boss encounter id, once the map shows it (the bridge's map `boss.encounter`)
    act_model : str | None = None   # "OVERGROWTH" | "UNDERDOCKS" | "HIVE" | "GLORY"
    elites_seen : list = field(default_factory=list)    # the elite encounters fought in this act, in order (None: one that was not recognized); shared with the planner
    elite_counted : bool = False        # the elite fight of kinds[0] is already in elites_seen
