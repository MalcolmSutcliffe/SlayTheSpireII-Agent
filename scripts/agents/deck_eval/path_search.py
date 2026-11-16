"""Plans the route through the map by walking it: every path the map still allows, played by the engine's run simulator with the deck the agent has (route_sim).

At each map decision the paths from the options to the end of the map are listed (paths with the same fights, rests and treasure room are one), the most promising ones are
walked, and the option the best path starts with is taken. The path is kept as the agent's planned route (PathPlanner.route): the card, shop, upgrade and event choosers
walk the rest of the act along it. The next map decision plans again from where the agent stands, so the plan follows what the deck, HP and gold have become.

A path is worth the mean reward of its walks (rooms of progress: HP carried over, rests, rewards, relics, the elite's relic; a death costs every room not reached, the next act's first rooms included: route_sim) . Shops and
"?" rooms are walked too (route_sim): a "?" becomes what the game's odds make of it, and an event option is chosen at random. Walks of different paths share the walk seeds, so the dice they meet
are alike until the paths part.

The candidates are cut in two ways. Paths are first ranked by the old node scores (agents/pathing.py), keeping the best of each kind of path (how many elites, how many rest
sites) and up to PER_OPTION for each option; then the walks go in rounds, and every ROUNDS_PER_CUT rounds the worse half is dropped. The search stops at PATH_SECONDS.

Whether such a plan is too careful about elites (a path's risk is counted in full: a death costs the rest of the act, while an elite's reward - its relic, a stronger deck for the
fights after it - is seen only by walking on) is something to watch in the log lines: the chosen path's elites and its chance to come through are printed."""
from __future__ import annotations
import math
import time
from dataclasses import dataclass, field

from agents.decision import Decision, Option
from agents.deck_eval.route_sim import sample_walks

PATH_SECONDS = 10.0
MAX_CANDIDATES = 24
PER_OPTION = 5
ROUND_WALKS = 2             # walks every candidate plays in a round
ROUNDS_PER_CUT = 3
MIN_KEEP = 4
NODE_CAP = 600              # most distinct paths kept below one node
WALK_KINDS = ("combat", "elite", "rest", "treasure", "shop", "unknown", "boss")
LETTER = {"combat": "C", "elite": "E", "rest": "R", "unknown": "?", "treasure": "T", "shop": "$", "boss": "B", "other": "-"}
ELITE_BONUS = 0.4           # rooms of progress added to a path for each elite on it at the end of the act (the walks see an elite's risk in full, its reward only in part)
ELITE_EARLY = 0.25          # an elite at the start of the act gets this share of ELITE_BONUS; the share grows linearly with the row to 1 at the boss: the later the elite, the stronger the deck that meets it
SURROGATE = {"combat": 1.0, "elite": 1.2, "rest": 1.5, "unknown": 1.5, "treasure": 0.5, "shop": 1.0, "boss": 0.0}


def elite_bonus(kinds : tuple, first_row : int, last_row : int) -> float:
    """The bonus of a path: ELITE_BONUS for each elite, scaled from ELITE_EARLY (the act's first row) to 1 (its last row) by where the elite is. `kinds` begins on row `first_row`."""
    total = 0.0
    for i, kind in enumerate(kinds):
        if kind == "elite":
            share = min(1.0, max(0.0, (first_row + i) / max(1, last_row)))
            total += ELITE_BONUS * (ELITE_EARLY + (1.0 - ELITE_EARLY) * share)
    return total


def path_key(kinds : tuple) -> tuple:
    """What a walk can tell two paths apart by: their fights, rests and treasure room in order, how many "?" rooms and whether there is a shop."""
    return (tuple(k for k in kinds if k in WALK_KINDS), sum(k == "unknown" for k in kinds), "shop" in kinds)


def enumerate_paths(nodes : dict, first : tuple, first_type : str | None, kind_of, cap : int = NODE_CAP) -> list[tuple]:
    """The kinds of every different path from `first` to the end of the map (paths that only differ in where their "?" rooms are count once)."""
    memo : dict = {}

    def below(coord : tuple, point_type : str | None = None) -> dict:
        if point_type is None and coord in memo:
            return memo[coord]
        kind = kind_of(point_type or (nodes.get(coord) or {}).get("type"))
        children = (nodes.get(coord) or {}).get("children") or []
        out : dict = {}
        if not children:
            out[path_key((kind,))] = (kind,)
        for c in children:
            for ks in below(tuple(c)).values():
                seq = (kind,) + ks
                out.setdefault(path_key(seq), seq)
        if len(out) > cap:
            out = dict(sorted(out.items(), key=lambda kv: -sum(SURROGATE.get(k, 0) for k in kv[1]))[:cap])
        if point_type is None:
            memo[coord] = out
        return out
    return list(below(first, first_type).values())


@dataclass
class Candidate:
    option : Option
    kinds : tuple
    heuristic : float
    bonus : float = 0.0         # see elite_bonus
    route : object = None
    rewards : list = field(default_factory=list)
    alive : int = 0

    @property
    def mean(self) -> float:
        return sum(self.rewards) / len(self.rewards) if self.rewards else float("-inf")

    @property
    def value(self) -> float:
        return self.mean + self.bonus

    def show(self) -> str:
        return "".join(LETTER.get(k, "-") for k in self.kinds)


class PathSearch:
    def __init__(self, advisor, planner):
        self.advisor, self.planner = advisor, planner

    def candidates(self, decision, nodes, combats_done, treasure_done, hurt, gold, here, act, boss, act_model, elites) -> list[Candidate]:
        from agents.pathing import PlannedRoute, _kind
        planner, found = self.planner, []
        last_row = max((r for _, r in nodes), default=1)
        for opt in decision.options:
            data = opt.data or {}
            first = (data.get("col"), data.get("row"))
            by_group : dict = {}
            for kinds in enumerate_paths(nodes, first, data.get("type"), _kind):
                score = planner.path_score(kinds, first[1], combats_done, treasure_done, hurt, gold, here)
                group = (kinds.count("elite"), kinds.count("rest"))
                if group not in by_group or score > by_group[group][0]:
                    by_group[group] = (score, kinds)
            for score, kinds in sorted(by_group.values(), key=lambda sk: -sk[0])[:PER_OPTION]:
                found.append(Candidate(opt, kinds, score, elite_bonus(kinds, first[1] or 0, last_row)))
        found.sort(key=lambda c: -c.heuristic)
        found = found[:MAX_CANDIDATES]
        for c in found:
            walked = list(c.kinds) if c.kinds[-1] == "boss" else list(c.kinds) + ["boss"]
            c.route = PlannedRoute(["other"] + walked, combats_done, act, boss, act_model, elites)
        return found

    def plan(self, decision : Decision, nodes, combats_done, treasure_done, hurt, gold, here, act, boss, act_model, elites) -> tuple[Option, list[str]] | None:
        """(the option to take, the kinds of the planned path), or None when there is nothing to walk (the planner then goes by its node scores)."""
        player = decision.player
        deck = player.get("deck") or []
        if not deck or not decision.options:
            return None
        cands = self.candidates(decision, nodes, combats_done, treasure_done, hurt, gold, here, act, boss, act_model, elites)
        if not cands:
            return None
        if len({c.kinds for c in cands}) == 1 or len(cands) == 1:
            return cands[0].option, list(cands[0].kinds)
        ctx = decision.state.get("context") or decision.state.get("run") or {}
        ev, start = self.advisor.evaluator, time.perf_counter()
        self.planner.plans += 1
        seed, alive_now, rounds, played = 9000 + self.planner.plans * 1000, list(cands), 0, 0
        while time.perf_counter() - start < PATH_SECONDS:
            for c in alive_now:
                if time.perf_counter() - start >= PATH_SECONDS and played:
                    break
                walks = sample_walks(c.route, act, ctx.get("ascension", 0), ROUND_WALKS, seed + rounds, ctx.get("floor", 1))
                score = ev.score_walks(deck, player, walks)
                c.rewards += score.rewards
                c.alive += round(score.win_rate * len(walks))
                played += len(walks)
            rounds += 1
            if rounds % ROUNDS_PER_CUT == 0 and len(alive_now) > MIN_KEEP:
                alive_now = sorted(alive_now, key=lambda c: -c.value)[:max(MIN_KEEP, math.ceil(len(alive_now) / 2))]
        walked = [c for c in cands if c.rewards]
        best = max(walked, key=lambda c: (c.value, c.heuristic))
        per_option = {}
        for c in walked:
            if id(c.option) not in per_option or c.value > per_option[id(c.option)].value:
                per_option[id(c.option)] = c
        self.advisor.log("path (%d paths of %d kinds of path, %d walks, %.1fs of %.0fs): " % (len(cands), len({path_key(c.kinds) for c in cands}), played, time.perf_counter() - start, PATH_SECONDS) +
                         ", ".join("%s %.2f (%d%% through, %d elites%s)" % (c.show(), c.value, 100 * c.alive / len(c.rewards), c.kinds.count("elite"), ", +%.2f elite bonus" % c.bonus if c.bonus else "") for c in sorted(per_option.values(), key=lambda c: -c.value)) +
                         " -> " + best.show())
        return best.option, list(best.kinds)
