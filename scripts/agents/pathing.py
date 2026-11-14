"""Chooses the next map node: the route to the boss with the highest total node score (PathPlanner.choose).

Scores (ROUTE_WEIGHTS):
  combat   1.5 for the first 3 combats of the act (the ones already fought count), 1.0 after
  elite    0.8, 1.8 once the route is past the act's treasure room
  rest     1.5, +1.0 more while the player is under half HP
  unknown  1.5 (a "?" room)
  shop     the first shop of a route: (gold now + 20 per floor in between) / 100, so 300 gold is 3.0; later shops 0
  treasure, boss: 0 (every route has exactly one treasure room)
Ties go to the route with the most rest sites, then to the leftmost first step."""
from __future__ import annotations

from dataclasses import dataclass

from agents.decision import Decision, Option

COMBAT_BONUS_COUNT = 3


@dataclass(frozen=True)
class RouteWeights:
    early_combat : float = 1.5
    combat : float = 1.0
    elite_before_treasure : float = 0.8
    elite_after_treasure : float = 1.8
    rest : float = 1.5
    low_hp_rest_bonus : float = 1.0
    low_hp_below : float = 0.5          # share of max HP
    unknown : float = 1.5
    shop_gold_per_floor : float = 20.0      # gold the agent is expected to pick up on each floor before the shop
    shop_gold_scale : float = 100.0         # gold per point of score

ROUTE_WEIGHTS = RouteWeights()


def _kind(point_type : str | None) -> str:
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


class PathPlanner:
    def __init__(self, weights : RouteWeights = ROUTE_WEIGHTS):
        self.w = weights
        self.route : PlannedRoute | None = None

    def choose(self, decision : Decision) -> Option:
        state, player = decision.state, decision.player
        nodes = {(n["col"], n["row"]): n for n in state.get("nodes") or ()}
        visited = state.get("visited") or []
        combats_done = sum(_kind(v.get("type")) == "combat" for v in visited)
        treasure_done = any(_kind(v.get("type")) == "treasure" for v in visited)
        hurt = player.get("hp", 1) < self.w.low_hp_below * max(1, player.get("max_hp", 1))
        gold = player.get("gold", 0)
        here = (state.get("current_position") or {}).get("row")
        if here is None:        # before the first room: the row above the lowest choice
            here = min((o.data or {}).get("row", 0) for o in decision.options) - 1
        best = None
        for opt in decision.options:
            data = opt.data or {}
            first = (data.get("col"), data.get("row"))
            score, rests, kinds = self.best_route(nodes, first, data.get("type"), combats_done, treasure_done, hurt, gold, here)
            key = (score, rests, -(data.get("col") if data.get("col") is not None else 0))
            if best is None or key > best[0]:
                best = (key, opt, kinds)
        ctx = state.get("context") or state.get("run") or {}
        self.route = PlannedRoute(best[2], combats_done, ctx.get("act", 1))
        return best[1]

    def best_route(self, nodes : dict, coord : tuple, point_type : str | None, combats : int, treasure : bool, hurt : bool, gold : float = 0, here : int = 0, shop_seen : bool = False) -> tuple[float, int, list[str]]:
        """(highest total score, rest sites, node kinds) of the best route that starts at `coord` and runs to the end of the map."""
        w = self.w
        kind = _kind(point_type or (nodes.get(coord) or {}).get("type"))
        score, rests = 0.0, 0
        if kind == "combat":
            score = w.early_combat if combats < COMBAT_BONUS_COUNT else w.combat
            combats += 1
        elif kind == "elite":
            score = w.elite_after_treasure if treasure else w.elite_before_treasure
        elif kind == "rest":
            score, rests = w.rest + (w.low_hp_rest_bonus if hurt else 0.0), 1
        elif kind == "unknown":
            score = w.unknown
        elif kind == "treasure":
            treasure = True
        elif kind == "shop" and not shop_seen:
            floors_between = max(0, coord[1] - here - 1)
            score = (gold + w.shop_gold_per_floor * floors_between) / w.shop_gold_scale
        if kind == "shop":
            shop_seen = True
        children = (nodes.get(coord) or {}).get("children") or []
        best = (0.0, 0, [])
        if children:
            best = max((self.best_route(nodes, tuple(c), None, combats, treasure, hurt, gold, here, shop_seen) for c in children),
                       key=lambda sr: (sr[0], sr[1]))
        return score + best[0], rests + best[1], [kind] + best[2]
