"""Fits the walk's fight policy to the MCTS.

A fixed set of fights (a deck of the starter cards plus a few card rewards, a monster group from the engine's pools, some HP) is played once by the MCTS (the
slow part, cached in a file), and then by any number of variants of the rollout policy (fast). A variant is better the closer its cost per fight is to the
MCTS's: a fight's cost is the HP it took, or all the HP the fight began with if it was lost.

Usage (from scripts/):
  python -m benchmarks.policy_fit mcts --cases 120 --time-budget 0.1 --workers 2      # plays the MCTS on the cases (cached by case and budget)
  python -m benchmarks.policy_fit sweep [--reps 6] [--set name=field:value,field:value ...]   # variants of the policy against it
Variants (`--set`) change HeuristicParams fields (and `policy` names a RolloutPolicy); with none given a built-in list of single-field sweeps runs."""
from __future__ import annotations
import argparse
import json
import random
import statistics
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmarks.bench import SEARCH_SEED_OFFSET, default_workers, map_jobs, play_fight
from benchmarks.calibrate import spearman

CACHE_DIR = Path(__file__).resolve().parent / "results"
MAX_HP = 80
EXTRAS = {1: (0, 7), 2: (6, 13), 3: (10, 19)}            # card rewards a deck holds when it meets an act's fights


def make_case(seed : int, i : int):
    """(template, deck, player) of case i: the same for every player."""
    from agents.deck_eval.fight_mix import new_act_mix, pick_fights
    from agents.deck_eval.fight_pool import load_pool, target_types
    from agents.deck_eval.future_cards import extra_cards
    from sts2_lite.run import new_run
    r = random.Random(seed * 100003 + i)
    act = r.choice((1, 1, 2, 3))
    pool = load_pool()
    template = pick_fights(pool, new_act_mix(act), 1, r.randrange(1 << 30))[0]
    run = new_run()
    deck = run.deck + extra_cards(r.randint(*EXTRAS[act]), r)
    hp = r.randint(int(0.55 * MAX_HP), MAX_HP)
    player = {"hp": hp, "max_hp": MAX_HP, "relics": run.relics, "gold": 0}
    return template, deck, player, target_types(pool), act


def build(seed : int, i : int):
    from agents.deck_eval.fight_builder import build_fight
    template, deck, player, targets, act = make_case(seed, i)
    return build_fight(template, deck, player, targets), template, player["hp"], act


def mcts_job(job):
    seed, i, budget = job
    from agents.sts2_MCTS.params import SearchConfig
    sim, template, hp, act = build(seed, i)
    out = play_fight(sim.combat_state, SearchConfig(time_budget=budget), seed * 1000 + i, SEARCH_SEED_OFFSET + seed * 1000 + i)
    return {"i": i, "act": act, "kind": template.kind, "enemy": template.name, "hp": hp, "won": out["won"], "hp_lost": out["hp_lost"], "turns": out["turns"]}


def policy_job(job):
    seed, i, name, spec, rep = job
    from sts2_lite import rng
    from sts2_lite.combat import CombatSimulator
    from agents.sts2_MCTS.params import RolloutPolicy, SearchConfig
    from agents.sts2_MCTS.rollout_policy import rollout_policy
    cfg = SearchConfig().tuned(rollout=RolloutPolicy[spec.get("policy", "ClaudeHeuristic")], **{k: v for k, v in spec.items() if k != "policy"})
    sim, template, hp, act = build(seed, i)
    cs = sim.combat_state
    from agents.sts2_MCTS import outcome_score
    expected = outcome_score.expected_total_hp(cs)
    rng.seed(seed * 7919 + i * 31 + rep)
    start_turn = cs.turn_number
    while not sim.is_over and cs.turn_number < start_turn + 25:
        actions = sim.get_available_actions()
        if not actions:
            break
        sim.perform_action(rollout_policy(sim, actions, cfg.rollout, cfg.heuristic))
    won = cs.player.current_hp > 0 and all(e.is_minion or e.current_hp <= 0 for e in cs.enemies)
    left = outcome_score.enemy_progress_left(cs, expected)
    return {"i": i, "name": name, "won": won, "hp_lost": hp - max(0, cs.player.current_hp), "hp": hp, "left": 0.0 if won else left}


def cost(row) -> float:
    return row["hp_lost"] if row["won"] else row["hp"]


VARIANTS = {
    "shipped": {},
    "greedy": {"policy": "ClaudeHeuristicGreedy"},
    "no random": {"p_random_action": 0.0},
    "block x0": {"p_random_action": 0.0, "block_mult": 0.0},
    "block x3": {"p_random_action": 0.0, "block_mult": 3.0},
    "block x8": {"p_random_action": 0.0, "block_mult": 8.0},
    "cap 25": {"p_random_action": 0.0, "block_cap": 25},
    "attack first": {"p_random_action": 0.0, "block_mult": 0.0, "draw_first": 1.0, "power_first": 1.0},
}


def parse_variant(text : str) -> tuple[str, dict]:
    name, _, fields = text.partition("=")
    spec = {}
    for item in filter(None, fields.split(",")):
        key, _, value = item.partition(":")
        spec[key] = value if key == "policy" else json.loads(value)
    return name, spec


LEFT_EDGES = (0.35, 0.7)            # a lost fight's share of enemy HP left: close / half way / far


def fit(cached : list[dict], args):
    """Per kind of fight: KEEP (the share of the HP a won fight costs that the MCTS also loses) and RESCUE (the chance the MCTS wins a fight the policy lost, by how much
    of the enemy was left, and the HP that win costs as a share of the HP the fight began with)."""
    jobs = [(args.seed, r["i"], "shipped", {}, rep) for r in cached for rep in range(args.reps)]
    runs = map_jobs(policy_job, jobs, args.workers, "policy fights")
    by_case = {r["i"]: r for r in cached}
    groups = {"weak": ("weak", "normal"), "normal": ("weak", "normal"), "elite": ("elite",), "boss": ("boss",)}
    print("# kind: KEEP, RESCUE by (left <= %.2f, <= %.2f, more), RESCUE_COST (n of won pairs / n of lost runs)" % LEFT_EDGES)
    table = {}
    for kind, members in groups.items():
        rows = [(r, by_case[r["i"]]) for r in runs if by_case[r["i"]]["kind"] in members]
        both = [(r, m) for r, m in rows if r["won"] and m["won"]]
        keep = sum(m["hp_lost"] for r, m in both) / max(1, sum(r["hp_lost"] for r, m in both)) if both else 1.0
        lost = [(r, m) for r, m in rows if not r["won"]]
        rescue = []
        for lo, hi in ((0, LEFT_EDGES[0]), (LEFT_EDGES[0], LEFT_EDGES[1]), (LEFT_EDGES[1], 99)):
            part = [(r, m) for r, m in lost if lo < r["left"] <= hi or (lo == 0 and r["left"] <= hi)]
            rescue.append(round(sum(m["won"] for r, m in part) / len(part), 2) if part else 0.0)
        saved = [m["hp_lost"] / m["hp"] for r, m in lost if m["won"]]
        cost = round(statistics.fmean(saved), 2) if saved else 0.5
        table[kind] = (round(keep, 2), tuple(rescue), cost)
        print("%-7s keep %.2f  rescue %s  rescue_cost %.2f   (%d / %d)" % (kind, keep, rescue, cost, len(both), len(lost)))
    print("CORRECTION = " + repr(table))


def corrected(run : dict, case : dict, roll : float) -> dict:
    """What route_sim.correct makes of one run of the policy on a case (roll: the uniform number that decides a rescue)."""
    from agents.deck_eval import route_sim
    keep, rescue, cost_share = route_sim.CORRECTION.get("weak" if case["kind"] == "normal" else case["kind"], route_sim.CORRECTION["normal"])
    if run["won"]:
        return {"won": True, "hp_lost": round(keep * run["hp_lost"]), "hp": run["hp"]}
    left = run["left"]
    chance = rescue[0 if left <= route_sim.LEFT_EDGES[0] else 1 if left <= route_sim.LEFT_EDGES[1] else 2]
    if roll < chance:
        return {"won": True, "hp_lost": min(run["hp"] - 1, round(cost_share * run["hp"])), "hp": run["hp"]}
    return run


def check(cached : list[dict], args):
    jobs = [(args.seed, r["i"], "shipped", {}, rep) for r in cached for rep in range(args.reps)]
    runs = map_jobs(policy_job, jobs, args.workers, "policy fights")
    by_case = {r["i"]: r for r in cached}
    rolls = random.Random(5)
    out = [(r, by_case[r["i"]], corrected(r, by_case[r["i"]], rolls.random())) for r in runs]
    def line(name, sel):
        part = [(r, m, c) for r, m, c in out if sel(m)]
        if not part:
            return
        ids = sorted({m["i"] for r, m, c in part})
        per = lambda who, f: {i: statistics.fmean(f(x) for x in who if x[1]["i"] == i) for i in ids}
        raw, fixed = per(part, lambda x: cost(x[0])), per(part, lambda x: cost(x[2]))
        mc = {i: cost({"won": by_case[i]["won"], "hp_lost": by_case[i]["hp_lost"], "hp": by_case[i]["hp"]}) for i in ids}
        win = lambda f: 100 * statistics.fmean(f(x) for x in part)
        mw = 100 * statistics.fmean(by_case[i]["won"] for i in ids)
        print("%-8s n=%3d | win raw %3.0f%% fixed %3.0f%% mcts %3.0f%% | cost raw %5.1f fixed %5.1f mcts %5.1f | MAE raw %4.1f fixed %4.1f | rank agr raw %.2f fixed %.2f" % (
            name, len(ids), win(lambda x: x[0]["won"]), win(lambda x: x[2]["won"]), mw, statistics.fmean(raw.values()), statistics.fmean(fixed.values()), statistics.fmean(mc.values()),
            statistics.fmean(abs(raw[i] - mc[i]) for i in ids), statistics.fmean(abs(fixed[i] - mc[i]) for i in ids),
            spearman([raw[i] for i in ids], [mc[i] for i in ids]), spearman([fixed[i] for i in ids], [mc[i] for i in ids])))
    line("all", lambda m: True)
    for kind in ("weak", "normal", "elite", "boss"):
        line(kind, lambda m, k=kind: m["kind"] == k)
    for act in (1, 2, 3):
        line("act %d" % act, lambda m, a=act: m["act"] == a)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mcts")
    m.add_argument("--cases", type=int, default=100)
    m.add_argument("--seed", type=int, default=1)
    m.add_argument("--time-budget", type=float, default=0.1)
    m.add_argument("--workers", type=int, default=default_workers())
    s = sub.add_parser("sweep")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--time-budget", type=float, default=0.1)
    s.add_argument("--reps", type=int, default=6)
    s.add_argument("--workers", type=int, default=default_workers())
    c = sub.add_parser("check", help="the shipped policy with route_sim.CORRECTION applied, against the MCTS on these cases (use a seed the fit has not seen)")
    c.add_argument("--seed", type=int, default=2)
    c.add_argument("--time-budget", type=float, default=0.1)
    c.add_argument("--reps", type=int, default=8)
    c.add_argument("--workers", type=int, default=default_workers())
    f = sub.add_parser("fit", help="the numbers of route_sim.CORRECTION: how the shipped policy's fights are turned into the MCTS's")
    f.add_argument("--seed", type=int, default=1)
    f.add_argument("--time-budget", type=float, default=0.1)
    f.add_argument("--reps", type=int, default=8)
    f.add_argument("--workers", type=int, default=default_workers())
    s.add_argument("--set", action="append", default=[], metavar="NAME=field:value,...")
    args = ap.parse_args()
    cache = CACHE_DIR / f"policy_fit_mcts_s{args.seed}_b{args.time_budget}.json"
    CACHE_DIR.mkdir(exist_ok=True)
    cached = json.loads(cache.read_text()) if cache.exists() else []
    if args.cmd == "mcts":
        have = {r["i"] for r in cached}
        todo = [(args.seed, i, args.time_budget) for i in range(args.cases) if i not in have]
        cached += map_jobs(mcts_job, todo, args.workers, "mcts fights")
        cache.write_text(json.dumps(sorted(cached, key=lambda r: r["i"])))
        print(f"{len(cached)} cases in {cache}")
        return
    if not cached:
        raise SystemExit("no MCTS cases: run the `mcts` command first")
    if args.cmd == "fit":
        return fit(cached, args)
    if args.cmd == "check":
        return check(cached, args)
    variants = dict(parse_variant(t) for t in args.set) or VARIANTS
    jobs = [(args.seed, r["i"], name, spec, rep) for name, spec in variants.items() for r in cached for rep in range(args.reps)]
    rows = map_jobs(policy_job, jobs, args.workers, "policy fights")
    by_case = {r["i"]: r for r in cached}
    mc = {i: cost({"won": r["won"], "hp_lost": r["hp_lost"], "hp": r["hp"]}) for i, r in by_case.items()}
    print("MCTS (%d fights, %.2f s/decision): win %.0f%%  mean cost %.1f" % (len(cached), args.time_budget, 100 * statistics.fmean(r["won"] for r in cached), statistics.fmean(mc.values())))
    print("%-14s %6s %9s %8s %6s %9s   %s" % ("variant", "win%", "cost", "bias", "MAE", "rank agr", "win% by act 1/2/3"))
    for name in variants:
        mine = [r for r in rows if r["name"] == name]
        per_case = {i: statistics.fmean(cost(r) for r in mine if r["i"] == i) for i in by_case}
        wins = {i: statistics.fmean(r["won"] for r in mine if r["i"] == i) for i in by_case}
        diffs = [per_case[i] - mc[i] for i in by_case]
        acts = [statistics.fmean(wins[i] for i in by_case if by_case[i]["act"] == a) for a in (1, 2, 3)]
        print("%-14s %5.0f%% %9.1f %+8.1f %6.1f %9.2f   %s" % (name, 100 * statistics.fmean(wins.values()), statistics.fmean(per_case.values()), statistics.fmean(diffs),
              statistics.fmean(abs(d) for d in diffs), spearman([per_case[i] for i in by_case], [mc[i] for i in by_case]), " / ".join("%.0f%%" % (100 * w) for w in acts)))


if __name__ == "__main__":
    main()
