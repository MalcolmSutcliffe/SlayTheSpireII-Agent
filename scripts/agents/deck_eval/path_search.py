"""Plans the route through the map by walking it: every path the map still allows, played by the engine's run simulator with the deck the agent has (route_sim).

At each map decision the paths from the options to the end of the map are listed (paths with the same fights, rests and treasure room are one), the most promising ones are
walked, and the option the best path starts with is taken. The path is kept as the agent's planned route (PathPlanner.route): the card, shop, upgrade and event choosers
walk the rest of the act along it. The next map decision plans again from where the agent stands, so the plan follows what the deck, HP and gold have become.

A path is worth the mean reward of its walks (rooms of progress: HP carried over, rests, rewards, relics, the elite's relic; a death costs every room not reached, the next act's first rooms included: route_sim) . Shops and
"?" rooms are walked too (route_sim): a "?" becomes what the game's odds make of it, and an event option is chosen at random. Walks of different paths share the walk seeds, so the dice they meet
are alike until the paths part.

The candidates are cut in two ways. Paths are first ranked by the old node scores (agents/pathing.py), keeping the best of each kind of path (how many elites, how many rest
sites) and up to `per_option` for each option; then the walks go in rounds, and every `rounds_per_cut` rounds the worse half is dropped. The search stops at `path_seconds`
(these numbers are DeckEvalConfig's: config.py).

Whether such a plan is too careful about elites (a path's risk is counted in full: a death costs the rest of the act, while an elite's reward - its relic, a stronger deck for the
fights after it - is seen only by walking on) is something to watch in the log lines: the chosen path's elites and its chance to come through are printed."""
from __future__ import annotations
import math
import time
from dataclasses import dataclass, field

from agents.decision import Decision, Option
from agents.deck_eval.config import DEFAULT, DeckEvalConfig
from agents.deck_eval.route_sim import sample_walks
from agents.route import PlannedRoute, node_kind

NODE_CAP = 600              # most distinct paths kept below one node
WALK_KINDS = ("combat", "elite", "rest", "treasure", "shop", "unknown", "boss")
LETTER = {"combat": "C", "elite": "E", "rest": "R", "unknown": "?", "treasure": "T", "shop": "$", "boss": "B", "other": "-"}
SURROGATE = {"combat": 1.0, "elite": 1.2, "rest": 1.5, "unknown": 1.5, "treasure": 0.5, "shop": 1.0, "boss": 0.0}


def elite_bonus(kinds : tuple, first_row : int, last_row : int, config : DeckEvalConfig = DEFAULT, act : int = 1) -> float:
    """The bonus of a path: config.elite_bonus (less config.elite_act_step for each act after the first, never below 0) for each elite, scaled from config.elite_early (the act's first row) to 1 (its last row) by where the elite is.
    `kinds` begins on row `first_row`. The walks see an elite's risk in full and its reward only in part; the later the elite, the stronger the deck that meets it."""
    total, early = 0.0, config.elite_early
    per_elite = max(0.0, config.elite_bonus - config.elite_act_step * max(0, (act or 1) - 1))
    for i, kind in enumerate(kinds):
        if kind == "elite":
            share = min(1.0, max(0.0, (first_row + i) / max(1, last_row)))
            total += per_elite * (early + (1.0 - early) * share)
    return total


def shop_bonus(kinds : tuple, gold : int, config : DeckEvalConfig = DEFAULT) -> float:
    """The bonus of a path for its shops: the gold expected at each (the gold now, plus config.shop_gold_per_floor for each room before it) over config.shop_gold_scale; a shop with less than config.shop_gold_min expected earns nothing."""
    expected = [gold + config.shop_gold_per_floor * i for i, kind in enumerate(kinds) if kind == "shop"]
    return sum(g / config.shop_gold_scale for g in expected if g >= config.shop_gold_min)


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

    def stderr(self) -> float:
        n = len(self.rewards)
        if n < 2:
            return float("inf")
        m = sum(self.rewards) / n
        return math.sqrt(sum((r - m) ** 2 for r in self.rewards) / (n - 1) / n)

    def first_care(self) -> int:
        """Steps until the path first reaches a rest site or a shop (a large number when it never does)."""
        return next((i for i, k in enumerate(self.kinds) if k in ("rest", "shop")), len(self.kinds) + 1)

    def show(self) -> str:
        return "".join(LETTER.get(k, "-") for k in self.kinds)


class PathSearch:
    def __init__(self, advisor, planner):
        self.advisor, self.planner = advisor, planner

    def candidates(self, decision, nodes, combats_done, treasure_done, hurt, gold, here, act, boss, act_model, elites) -> list[Candidate]:
        planner, found, cfg = self.planner, [], self.advisor.config
        last_row = max((r for _, r in nodes), default=1)
        for opt in decision.options:
            data = opt.data or {}
            first = (data.get("col"), data.get("row"))
            by_group : dict = {}
            for kinds in enumerate_paths(nodes, first, data.get("type"), node_kind):
                score = planner.path_score(kinds, first[1], combats_done, treasure_done, hurt, gold, here)
                group = (kinds.count("elite"), kinds.count("rest"))
                if group not in by_group or score > by_group[group][0]:
                    by_group[group] = (score, kinds)
            for score, kinds in sorted(by_group.values(), key=lambda sk: -sk[0])[:cfg.per_option]:
                found.append(Candidate(opt, kinds, score, elite_bonus(kinds, first[1] or 0, last_row, cfg, act) + shop_bonus(kinds, gold or 0, cfg)))
        found.sort(key=lambda c: -c.heuristic)
        found = found[:cfg.max_candidates]
        for c in found:
            walked = list(c.kinds) if c.kinds[-1] == "boss" else list(c.kinds) + ["boss"]
            c.route = PlannedRoute(["other"] + walked, combats_done, act, boss, act_model, elites)
        return found

    @staticmethod
    def tied_when_hurt(best : Candidate, walked : list[Candidate], player : dict, cfg) -> Candidate:
        """Hurt (HP below cfg.path_tie_hp of the max): the walks cannot tell paths apart that are within cfg.path_tie_z standard errors of each other, and the one that
        reaches a rest site or a shop soonest is the careful one to take (the walks see the deck die in the fights before it, but not how soon a rest would have saved it)."""
        hp, max_hp = player.get("hp", player.get("current_hp")), player.get("max_hp")
        if not hp or not max_hp or hp / max_hp >= cfg.path_tie_hp:
            return best
        tied = [c for c in walked if best.value - c.value <= cfg.path_tie_z * math.hypot(best.stderr(), c.stderr())]
        return min(tied, key=lambda c: (c.first_care(), -c.value)) if tied else best

    def plan(self, decision : Decision, nodes, combats_done, treasure_done, hurt, gold, here, act, boss, act_model, elites) -> tuple[Option, list[str]] | None:
        """(the option to take, the kinds of the planned path), or None when there is nothing to walk (the planner then goes by its node scores)."""
        player = decision.player
        deck = player.get("deck") or []
        if not deck or not decision.options:
            return None
        cands = self.candidates(decision, nodes, combats_done, treasure_done, hurt, gold, here, act, boss, act_model, elites)
        if not cands:
            return None
        if len(decision.options) == 1 or len({c.kinds for c in cands}) == 1 or len(cands) == 1:   # a forced step (one option) is not worth walking
            return cands[0].option, list(cands[0].kinds)
        ctx = decision.state.get("context") or decision.state.get("run") or {}
        ev, cfg, start = self.advisor.evaluator, self.advisor.config, time.perf_counter()
        budget = cfg.path_seconds
        self.planner.plans += 1
        seed, alive_now, rounds, played = 9000 + self.planner.plans * 1000, list(cands), 0, 0
        while time.perf_counter() - start < budget:
            for c in alive_now:
                if time.perf_counter() - start >= budget and played:
                    break
                walks = sample_walks(c.route, act, ctx.get("ascension", 0), cfg.round_walks, seed + rounds, ctx.get("floor", 1))
                score = ev.score_walks(deck, player, walks)
                c.rewards += score.rewards
                c.alive += round(score.win_rate * len(walks))
                played += len(walks)
            rounds += 1
            if rounds % cfg.rounds_per_cut == 0 and len(alive_now) > cfg.min_keep:
                alive_now = sorted(alive_now, key=lambda c: -c.value)[:max(cfg.min_keep, math.ceil(len(alive_now) / 2))]
        walked = [c for c in cands if c.rewards]
        best = max(walked, key=lambda c: (c.value, c.heuristic))
        best = self.tied_when_hurt(best, walked, player, cfg)
        per_option = {}
        for c in walked:
            if id(c.option) not in per_option or c.value > per_option[id(c.option)].value:
                per_option[id(c.option)] = c
        self.advisor.log("path (%d paths of %d kinds of path, %d walks, %.1fs of %.0fs): " % (len(cands), len({path_key(c.kinds) for c in cands}), played, time.perf_counter() - start, budget) +
                         ", ".join("%s %.2f (%d%% through, %d elites%s)" % (c.show(), c.value, 100 * c.alive / len(c.rewards), c.kinds.count("elite"), ", +%.2f bonus (elites, shops)" % c.bonus if c.bonus else "") for c in sorted(per_option.values(), key=lambda c: -c.value)) +
                         " -> " + best.show())
        return best.option, list(best.kinds)
