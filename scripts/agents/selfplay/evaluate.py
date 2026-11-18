"""Does a chooser pick better cards? Every chooser plays the same seeds (the same maps, fights, events and offers until the picks differ) with no exploration,
and the runs are compared seed by seed.

  python -m agents.selfplay.evaluate --out gen0 --choosers rarity,model:gen0/mlp --pilot mcts:100:big --seeds 400 --workers 8

The seeds start at --start-seed (default 1,000,000, far from the seeds the suite trains on). Results go to data/selfplay/eval/NAME.jsonl.gz as each run finishes;
running the same command again plays only what is missing, so a long evaluation can be stopped and resumed, and more seeds or choosers added later.

The report: per chooser, the rooms cleared (mean ± standard error), how many runs reached acts 2 and 3 and won, how often it skipped, and its most taken cards;
then each chooser against the first one, seed by seed: the mean difference in rooms cleared ± its standard error. A difference within about two standard errors of 0
is not yet a difference: play more seeds."""
from __future__ import annotations
import argparse
import collections
import gzip
import json
import math
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agents.selfplay.choosers import Counts, base_id
from agents.selfplay.run import RUN_TIMEOUT, parse_pilot, play_run_guarded
from agents.selfplay.suite import OUT_ROOT, ascension_of, parse_ascensions, read_runs


def job(args) -> dict:
    chooser, seed, pilot, levels, timeout = args
    run = play_run_guarded(seed, chooser, Counts(), c=0.0, epsilon=0.0, ascension=ascension_of(seed, levels), pilot=pilot, timeout=timeout)
    return {"chooser": chooser, "seed": seed, "pilot": run["pilot"], "ascension": run["ascension"], "outcome": run["outcome"],
            "picks": [{"act": p["act"], "offered": p["offered"], "chosen": p["chosen"]} for p in run["picks"]]}


def mean_se(xs : list[float]) -> tuple[float, float]:
    n = len(xs)
    if n == 0:
        return math.nan, math.nan
    m = sum(xs) / n
    return m, (math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n) if n > 1 else math.nan)


def report(results : list[dict], choosers : list[str]) -> str:
    stuck = {r["seed"] for r in results if str(r["outcome"].get("cause")).startswith("engine error: timed out")}
    results = [r for r in results if r["seed"] not in stuck]          # a seed one chooser got stuck on is left out for every chooser, so the comparison stays paired
    by = {c: {r["seed"]: r for r in results if r["chooser"] == c} for c in choosers}
    lines = ["%-28s %6s  %-14s %7s %7s %5s %6s  %s" % ("chooser", "runs", "rooms cleared", "act 2+", "act 3+", "won", "skips", "most taken")]
    for c in choosers:
        runs = list(by[c].values())
        if not runs:
            lines.append(f"{c:28s} no runs yet")
            continue
        rooms = [r["outcome"]["rooms_cleared"] for r in runs]
        m, se = mean_se(rooms)
        picks = [p for r in runs for p in r["picks"]]
        taken = collections.Counter(base_id(p["chosen"]) for p in picks if p["chosen"] != "SKIP")
        n = len(runs)
        lines.append("%-28s %6d  %5.2f ± %-6.2f %6.0f%% %6.0f%% %4.0f%% %5.0f%%  %s" % (
            c, n, m, se, 100 * sum(r["outcome"]["act"] >= 2 for r in runs) / n, 100 * sum(r["outcome"]["act"] >= 3 for r in runs) / n,
            100 * sum(r["outcome"]["won"] for r in runs) / n, 100 * sum(p["chosen"] == "SKIP" for p in picks) / max(1, len(picks)),
            ", ".join(f"{k} {v}" for k, v in taken.most_common(5))))
    if stuck:
        lines.append(f"(left out: {len(stuck)} seed(s) where a run timed out: {', '.join(map(str, sorted(stuck)))})")
    first = choosers[0]
    for c in choosers[1:]:
        seeds = sorted(set(by[first]) & set(by[c]))
        if len(seeds) < 2:
            continue
        diffs = [by[c][s]["outcome"]["rooms_cleared"] - by[first][s]["outcome"]["rooms_cleared"] for s in seeds]
        m, se = mean_se(diffs)
        same = sum(by[c][s]["picks"] == by[first][s]["picks"] for s in seeds)
        verdict = "better" if m > 2 * se else "worse" if m < -2 * se else "no clear difference yet"
        lines.append(f"\n{c} vs {first} on the same {len(seeds)} seeds: {m:+.2f} ± {se:.2f} rooms cleared ({m / se if se else 0:+.1f} standard errors: {verdict}); "
                     f"identical picks on {same} seeds")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, help="results file data/selfplay/eval/NAME.jsonl.gz")
    p.add_argument("--choosers", required=True, help="comma separated: rarity, random, model:NAME[:FLOOR]; the first is the one the others are compared with")
    p.add_argument("--pilot", default="rollout", help="who fights: rollout | mcts:N | mcts:N:big")
    p.add_argument("--seeds", type=int, default=400)
    p.add_argument("--start-seed", type=int, default=1_000_000)
    p.add_argument("--ascensions", default="0")
    p.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    p.add_argument("--run-timeout", type=int, default=RUN_TIMEOUT, help="seconds before a run is given up as stuck (0: never)")
    args = p.parse_args(argv)

    pilot = parse_pilot(args.pilot).name
    choosers = args.choosers.split(",")
    levels = parse_ascensions(args.ascensions)
    path = OUT_ROOT / "eval" / f"{args.out}.jsonl.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    results = [r for r in read_runs(path) if r["pilot"] == pilot]
    done = {(r["chooser"], r["seed"]) for r in results}
    seeds = range(args.start_seed, args.start_seed + args.seeds)
    todo = [(c, s, pilot, levels, args.run_timeout) for s in seeds for c in choosers if (c, s) not in done]
    print(f"{path}: {len(done)} runs already played with pilot {pilot}, {len(todo)} to play, {args.workers} workers", flush=True)
    start, last = time.perf_counter(), time.perf_counter()
    with Pool(args.workers) as pool:
        for i, run in enumerate(pool.imap_unordered(job, todo), 1):
            with gzip.open(path, "at", encoding="utf-8") as f:
                f.write(json.dumps(run, separators=(",", ":")) + "\n")
            results.append(run)
            if time.perf_counter() - last > 30 or i == len(todo):
                last = time.perf_counter()
                rate = i / (last - start)
                print(f"{i}/{len(todo)} runs  {rate:.2f} runs/s  ~{(len(todo) - i) / rate / 60:.1f} min left", flush=True)
    wanted = set(seeds)
    print()
    print(report([r for r in results if r["seed"] in wanted], choosers))
    return 0


if __name__ == "__main__":
    sys.exit(main())
