"""Calibrates the walk's fight policy against the real combat search (MCTS).

The walks (agents/deck_eval/route_sim.py) play every fight with the cheap rollout policy. Every out-of-combat decision is only as good as that stand-in, so
this plays each fight a walk meets twice, from the same start (same deck, relics, HP and monsters): once with the rollout policy, as the walk does, and once
with the MCTS agent. The walk goes on with the rollout policy's result, so its decks and HP are the ones the walks see.

Usage (from scripts/):
  python -m benchmarks.calibrate run --walks 6 --acts 3 --time-budget 0.1 --workers 2 --label base
  python -m benchmarks.calibrate show benchmarks/results/<file>.jsonl
Each job is one chain of walks (act 1, then the deck it ends with through act 2 and 3). Output: win rate and HP lost of both players per kind of fight, how often
they disagree, and the rank agreement of the HP lost (does the policy find the same fights hard?).

Reading it: a policy that loses fights MCTS wins makes the walks too pessimistic about the deck (decks that need setup or care are undervalued); one that
wins what MCTS loses is too optimistic; a large gap in HP lost is a bias in how much fights cost. A policy that is merely noisy but unbiased is fine for the walks.
Bias that depends on the deck (it differs between decks of different shape) is what misleads a choice: look at the per-room and per-act rows."""
from __future__ import annotations
import argparse
import contextlib
import io
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmarks.bench import default_workers, map_jobs, play_fight, SEARCH_SEED_OFFSET
from sts2_lite.combat import CombatState

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _won(cs) -> bool:
    return cs.player.current_hp > 0 and all(e.is_minion or e.current_hp <= 0 for e in cs.enemies)


def make_simulator(budget : float):
    from agents.deck_eval.route_sim import RouteSimulator
    from agents.sts2_MCTS.params import SearchConfig

    class CalibratingSimulator(RouteSimulator):
        """A walk whose every fight is also played by the MCTS from the same start."""
        records : list
        search = None

        def fight(self, encounter, room, *args, **kwargs):
            self.room_now = (room, encounter.id)
            return super().fight(encounter, room, *args, **kwargs)

        def play(self, sim):
            cs = sim.combat_state
            start = CombatState.deepcopy(cs)
            hp0, turn0 = cs.player.current_hp, cs.turn_number
            ok = True
            try:
                super().play(sim)
            finally:
                end = sim.combat_state
                rollout = {"won": _won(end), "hp_lost": hp0 - max(0, end.player.current_hp), "turns": end.turn_number - turn0, "finished": sim.is_over}
            if self.turn_limit is not None:          # an event's dummy fight: not a real one
                return
            tag = self.records_tag
            seed = self.walk.seed * 1000 + self.fights
            with contextlib.redirect_stdout(io.StringIO()):
                started = time.perf_counter()
                mcts = play_fight(start, SearchConfig(time_budget=budget), seed, SEARCH_SEED_OFFSET + seed)
            self.records.append({**tag, "room": self.room_now[0], "enemy": self.room_now[1], "act": self.run_state.act, "hp": hp0, "max_hp": cs.player.max_hp,
                                 "deck": len(self.run_state.deck), "rollout": rollout,
                                 "mcts": {k: mcts[k] for k in ("won", "hp_lost", "turns", "finished")}, "mcts_seconds": time.perf_counter() - started})

    return CalibratingSimulator


def run_chain(job : tuple) -> list[dict]:
    """One chain: a walk through act 1 from the starter deck, then the deck it ends with through the next acts."""
    seed, acts, budget, ascension = job
    from agents.deck_eval.evaluator import DeckEvaluator
    from agents.deck_eval.fight_pool import load_pool, target_types
    from agents.deck_eval.route_sim import play_walk, sample_walks
    from sts2_lite.run import new_run
    pool = load_pool()
    targets = target_types(pool)
    config = DeckEvaluator(pool, targets).config
    base = make_simulator(budget)
    records, made = [], []

    class Chain(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.records, self.records_tag = records, {"seed": seed}
            made.append(self)

    run = new_run(ascension)
    player, deck = run.player_dict(), run.deck
    for act in range(1, acts + 1):
        walk = sample_walks(None, act, ascension, 1, seed * 10 + act)[0]
        walk_result = play_walk(walk, deck, player, config, targets, simulator=Chain)
        final = made[-1].run_state
        if final.dead or not walk_result.alive:
            break
        player, deck = {**final.player_dict(), "hp": final.max_hp}, final.deck
    return records


# ---------------------------------------------------------------- results
def mean(xs):
    xs = list(xs)
    return statistics.fmean(xs) if xs else float("nan")


def ranks(xs : list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out, i = [0.0] * len(xs), 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2
        i = j + 1
    return out


def spearman(a : list[float], b : list[float]) -> float:
    if len(a) < 3:
        return float("nan")
    ra, rb = ranks(a), ranks(b)
    ma, mb = mean(ra), mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else float("nan")


def summarize(rows : list[dict]) -> dict:
    both = [r for r in rows if r["rollout"]["won"] and r["mcts"]["won"]]
    cost = lambda r, who: r[who]["hp_lost"] if r[who]["won"] else r["hp"]        # a loss costs all the HP the fight began with
    return {"fights": len(rows),
            "rollout_win": mean(r["rollout"]["won"] for r in rows), "mcts_win": mean(r["mcts"]["won"] for r in rows),
            "rollout_only": sum(r["rollout"]["won"] and not r["mcts"]["won"] for r in rows), "mcts_only": sum(r["mcts"]["won"] and not r["rollout"]["won"] for r in rows),
            "hp_lost_rollout": mean(r["rollout"]["hp_lost"] for r in both), "hp_lost_mcts": mean(r["mcts"]["hp_lost"] for r in both), "both_won": len(both),
            "cost_rollout": mean(cost(r, "rollout") for r in rows), "cost_mcts": mean(cost(r, "mcts") for r in rows),
            "rank_agreement": spearman([cost(r, "rollout") for r in rows], [cost(r, "mcts") for r in rows]),
            "turns_rollout": mean(r["rollout"]["turns"] for r in both), "turns_mcts": mean(r["mcts"]["turns"] for r in both)}


def table(rows : list[dict]) -> str:
    groups = [("all", rows)]
    for key in ("room", "act"):
        for value in sorted({r[key] for r in rows}, key=str):
            groups.append((f"{key} {value}", [r for r in rows if r[key] == value]))
    for lo, hi in ((0, 12), (12, 20), (20, 99)):
        part = [r for r in rows if lo <= r["deck"] < hi]
        if part:
            groups.append((f"deck {lo}-{hi - 1}", part))
    out = ["  %-14s %5s | %-14s | %-9s | %-15s | %-15s | %s" % ("", "n", "win% roll/mcts", "only r/m", "hp lost r/m*", "cost r/m", "rank agr")]
    for name, part in groups:
        s = summarize(part)
        out.append("  %-14s %5d | %5.0f%% /%5.0f%% | %3d / %-3d | %6.1f /%6.1f | %6.1f /%6.1f | %5.2f" % (
            name, s["fights"], 100 * s["rollout_win"], 100 * s["mcts_win"], s["rollout_only"], s["mcts_only"], s["hp_lost_rollout"], s["hp_lost_mcts"],
            s["cost_rollout"], s["cost_mcts"], s["rank_agreement"]))
    out.append("  * HP lost in the fights both won; cost = HP lost, or the HP the fight began with for a loss; rank agr = Spearman of the two costs per fight")
    return "\n".join(out)


def show(path : Path):
    rows = [json.loads(line) for line in open(path) if line.strip()]
    header, rows = rows[0], rows[1:]
    print(f"{path.name}: {header['chains']} chains, acts {header['acts']}, MCTS {header['time_budget']} s per decision")
    print(table(rows))
    worst = sorted((r for r in rows if r["mcts"]["won"] != r["rollout"]["won"]), key=lambda r: -r["max_hp"])[:12]
    if worst:
        print("  fights the two disagree on:")
        for r in worst:
            print("    seed %d act %d %-6s %-28s deck %2d hp %3d/%3d  rollout %s (%d lost)  mcts %s (%d lost)" % (
                r["seed"], r["act"], r["room"], r["enemy"], r["deck"], r["hp"], r["max_hp"], "won" if r["rollout"]["won"] else "LOST", r["rollout"]["hp_lost"],
                "won" if r["mcts"]["won"] else "LOST", r["mcts"]["hp_lost"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--walks", type=int, default=4, help="chains of walks (one seed each)")
    r.add_argument("--first-seed", type=int, default=0)
    r.add_argument("--acts", type=int, default=3)
    r.add_argument("--ascension", type=int, default=0)
    r.add_argument("--time-budget", type=float, default=0.1, help="seconds per MCTS decision")
    r.add_argument("--workers", type=int, default=default_workers())
    r.add_argument("--label", default="calibrate")
    s = sub.add_parser("show")
    s.add_argument("file", type=Path)
    args = ap.parse_args()
    if args.cmd == "show":
        return show(args.file)
    jobs = [(args.first_seed + i, args.acts, args.time_budget, args.ascension) for i in range(args.walks)]
    rows = [row for chain in map_jobs(run_chain, jobs, args.workers, "chains") for row in chain]
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_calibrate_{args.label}.jsonl"
    header = {"type": "header", "suite": "calibrate", "label": args.label, "chains": args.walks, "acts": args.acts, "time_budget": args.time_budget, "ascension": args.ascension}
    with open(path, "w") as f:
        for row in [header] + rows:
            f.write(json.dumps(row) + "\n")
    show(path)
    print("wrote", path)


if __name__ == "__main__":
    main()
