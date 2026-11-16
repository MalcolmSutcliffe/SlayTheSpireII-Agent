"""Chooses the next map node: the route to the boss with the highest total node score (PathPlanner.choose).

Scores (ROUTE_WEIGHTS):
  combat   1.5 for the first 3 combats of the act (the ones already fought count), 1.0 after
  elite    0.8, 1.8 once the route is past the act's treasure room
  rest     1.5, +1.0 more while the player is under half HP
  unknown  1.5 (a "?" room)
  shop     the first shop of a route: (gold now + 20 per floor in between) / 100, so 300 gold is 3.0; later shops 0
  treasure, boss: 0 (every route has exactly one treasure room)
Ties go to the route with the most rest sites, then to the leftmost first step.

With an `advisor` set (agents/deck_eval), the route is instead the path whose walks through the rest of the act do best (deck_eval/path_search.py); the node scores above only rank the
paths to be walked, and stand in when there is nothing to walk with."""
from __future__ import annotations

from dataclasses import dataclass

from agents.decision import Decision, Option
from agents.deck_eval.path_search import PathSearch
from agents.route import PlannedRoute, node_kind  # noqa: F401  (PlannedRoute: re-exported, the tests build routes from here)

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


class PathPlanner:
    def __init__(self, weights : RouteWeights = ROUTE_WEIGHTS):
        self.w = weights
        self.route : PlannedRoute | None = None
        self._act = None
        self.advisor = None                     # a DeckAdvisor: with it the route is planned by walking the paths
        self.plans = 0
        self.elites : dict[int, list] = {}      # act -> the elite encounters fought in it so far (the game deals them from a bag, so the rest can be known)

    def note_elite(self, elite : str | None):
        """The agent is in an elite fight: `elite` is its encounter id (None: not recognized). Counts once per room."""
        if self.route is not None and self.route.kinds and self.route.kinds[0] == "elite" and not self.route.elite_counted:
            self.route.elite_counted = True
            self.route.elites_seen.append(elite)

    def choose(self, decision : Decision) -> Option:
        state, player = decision.state, decision.player
        nodes = {(n["col"], n["row"]): n for n in state.get("nodes") or ()}
        visited = state.get("visited") or []
        combats_done = sum(node_kind(v.get("type")) == "combat" for v in visited)
        treasure_done = any(node_kind(v.get("type")) == "treasure" for v in visited)
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
        act = ctx.get("act", 1)
        if not visited or act != self._act:         # the first room of an act (or of a run): no elite fought yet
            self.elites[act] = []
        self._act = act
        boss, act_model, elites = (state.get("boss") or {}).get("encounter"), state.get("act_model"), self.elites.setdefault(act, [])
        chosen, kinds = best[1], best[2]
        if self.advisor is not None:
            try:
                planned = PathSearch(self.advisor, self).plan(decision, nodes, combats_done, treasure_done, hurt, gold, here, act, boss, act_model, elites)
            except Exception as e:          # the walks failing must not stop the run: the node scores decide
                self.advisor.log("path planning failed (%r) -> node scores" % (e,))
                planned = None
            if planned is not None:
                chosen, kinds = planned
        self.route = PlannedRoute(kinds, combats_done, act, boss, act_model, elites)
        return chosen

    def path_score(self, kinds : tuple, first_row : int, combats : int, treasure : bool, hurt : bool, gold : float = 0, here : int = 0) -> float:
        """The node score of a path (best_route's, for a path that is already known; the i-th node is on row first_row + i)."""
        w, score, shop_seen = self.w, 0.0, False
        for i, kind in enumerate(kinds):
            if kind == "combat":
                score += w.early_combat if combats < COMBAT_BONUS_COUNT else w.combat
                combats += 1
            elif kind == "elite":
                score += w.elite_after_treasure if treasure else w.elite_before_treasure
            elif kind == "rest":
                score += w.rest + (w.low_hp_rest_bonus if hurt else 0.0)
            elif kind == "unknown":
                score += w.unknown
            elif kind == "treasure":
                treasure = True
            elif kind == "shop":
                if not shop_seen:
                    score += (gold + w.shop_gold_per_floor * max(0, first_row + i - here - 1)) / w.shop_gold_scale
                shop_seen = True
        return score

    def best_route(self, nodes : dict, coord : tuple, point_type : str | None, combats : int, treasure : bool, hurt : bool, gold : float = 0, here : int = 0, shop_seen : bool = False) -> tuple[float, int, list[str]]:
        """(highest total score, rest sites, node kinds) of the best route that starts at `coord` and runs to the end of the map."""
        w = self.w
        kind = node_kind(point_type or (nodes.get(coord) or {}).get("type"))
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
