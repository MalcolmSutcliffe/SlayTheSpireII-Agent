"""Whole-run benchmark: the agent plays complete runs in the engine's sandbox (sts2_lite.campaign.RunSimulator): map, fights, rewards, shops, events, ancients, all of it.

The suite for judging a change to anything the agent does out of combat (and, over many runs, in combat): the same seeds give the same worlds (map, ancients, relic bag, events),
so two versions of the agent are compared run by run.

Usage (from scripts/):
  python -m benchmarks.runs run --seeds 20 --preset fast --label baseline
  python -m benchmarks.runs run --seeds 20 --preset fast --label my_change --set agents.deck_eval.path_search.PATH_SECONDS=4
  python -m benchmarks.runs compare benchmarks/results/A_runs_baseline.jsonl benchmarks/results/B_runs_my_change.jsonl
  python -m benchmarks.runs show benchmarks/results/A_runs_baseline.jsonl

  --agent my | base | package.module:Class     my = MyAgent (MCTS combat + the deck choosers), base = BaseAgent (plays the first action, picks at random out of combat)
  --preset full | fast                          full = the agent's own time caps and 0.5 s per combat decision; fast = 2 s caps and 0.1 s per combat decision, for quick looks
  --set module.NAME=value                       override any module constant in the workers (the time caps, thresholds...); repeatable
  --log                                         keep what the choosers print for every run (results/<file>_logs/seed<N>.txt)

What a run is scored by: `floor` (rooms entered over the whole run; a won run has the most), whether it was `won`, and `act` reached. The summary also gives where runs end (the encounter that killed
them), elites fought, fights, deck and relic counts. `compare` reports the paired difference per seed with a 95% interval; a difference inside the interval is noise (runs are very noisy:
use as many seeds as the time allows: one run takes minutes at the full preset)."""
from __future__ import annotations

import argparse
import ast
import contextlib
import importlib
import io
import json
import math
import os
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmarks.bench import default_workers, fmt, map_jobs

BENCH_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BENCH_DIR / "results"
SEARCH_SEED_OFFSET = 1_000_000          # keeps the agent's own look-ahead apart from the world's seed
FULL_BUDGET, FAST_BUDGET = 0.5, 0.1     # seconds per combat decision

DECK_EVAL = "agents.deck_eval."
PRESETS = {
    "full": {"time_budget": FULL_BUDGET, "set": []},
    "fast": {"time_budget": FAST_BUDGET, "set": [DECK_EVAL + "path_search.PATH_SECONDS=2", DECK_EVAL + "shop_chooser.SHOP_SECONDS=2", DECK_EVAL + "upgrade_chooser.UPGRADE_SECONDS=2",
                                                 DECK_EVAL + "event_chooser.EVENT_SECONDS=2", DECK_EVAL + "ancient_chooser.ANCIENT_SECONDS=2"]},
}


# ---------------------------------------------------------------- one run
def apply_overrides(settings : list[str]):
    """`module.NAME=value` sets that module-level name (the value is a Python literal)."""
    for item in settings:
        target, _, value = item.partition("=")
        module, _, name = target.rpartition(".")
        if not module or not name or not value:
            raise SystemExit(f"--set wants module.NAME=value, not {item!r}")
        setattr(importlib.import_module(module), name, ast.literal_eval(value))

def make_agent(spec : str, seed : int | None = None):
    if spec == "my":
        from agents.my_agent import MyAgent
        return MyAgent(seed)
    if spec == "base":
        from agents.base_agent import BaseAgent
        return BaseAgent()
    module, _, cls = spec.partition(":")
    if not cls:
        raise SystemExit(f"--agent is my, base or package.module:Class, not {spec!r}")
    return getattr(importlib.import_module(module), cls)()

def room_counts(history) -> dict:
    counts = Counter(v.room for v in history)
    return {room: counts.get(room, 0) for room in ("Monster", "Elite", "Boss", "RestSite", "Shop", "Treasure", "Event")}

def play_run(agent_spec : str, seed : int, ascension : int, time_budget : float, settings : list[str], log_path : str | None = None) -> dict:
    """One whole run; the row of results/<file>.jsonl."""
    from sts2_lite.campaign import RunSimulator
    apply_overrides(settings)
    log, start = io.StringIO(), time.perf_counter()
    try:
        with contextlib.redirect_stdout(log):
            result = RunSimulator(make_agent(agent_spec, SEARCH_SEED_OFFSET + seed), seed=seed, ascension=ascension, search_seed=SEARCH_SEED_OFFSET + seed, time_budget=time_budget).run()
        error = None
    except Exception as e:           # a crash is a result too: it is counted and the run's log is kept
        import traceback
        result, error = None, "".join(traceback.format_exception(e))
    seconds = time.perf_counter() - start
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(log_path).write_text(log.getvalue() + (("\n" + error) if error else ""))
    if result is None:
        return {"seed": seed, "error": error.strip().splitlines()[-1], "won": False, "act": 0, "floor": 0, "seconds": seconds}
    return {"seed": seed, "won": result.won, "act": result.act, "floor": result.floor, "hp": result.hp, "max_hp": result.max_hp, "cause": result.cause, "fights": result.fights,
            "deck": result.deck, "relics": result.relics, "rooms": room_counts(result.history), "illegal": result.illegal_choices, "error": None, "seconds": seconds}

def _job(job : tuple) -> dict:
    return play_run(*job)


# ---------------------------------------------------------------- results
def summarize(rows : list[dict]) -> dict:
    ok = [r for r in rows if not r.get("error")]
    n = max(1, len(rows))
    deaths = Counter(r["cause"] for r in ok if not r["won"] and r.get("cause"))
    return {
        "runs": len(rows), "crashed": len(rows) - len(ok),
        "win_rate": sum(r["won"] for r in ok) / n,
        "mean_floor": statistics.fmean(r["floor"] for r in rows) if rows else float("nan"),
        "reached_act2": sum(r["act"] >= 2 for r in ok) / n,
        "reached_act3": sum(r["act"] >= 3 for r in ok) / n,
        "elites_per_run": statistics.fmean(r["rooms"]["Elite"] for r in ok) if ok else float("nan"),
        "fights_per_run": statistics.fmean(r["fights"] for r in ok) if ok else float("nan"),
        "events_per_run": statistics.fmean(r["rooms"]["Event"] for r in ok) if ok else float("nan"),
        "shops_per_run": statistics.fmean(r["rooms"]["Shop"] for r in ok) if ok else float("nan"),
        "final_deck_size": statistics.fmean(len(r["deck"]) for r in ok) if ok else float("nan"),
        "final_relics": statistics.fmean(len(r["relics"]) for r in ok) if ok else float("nan"),
        "illegal_choices": sum(r["illegal"] for r in ok),
        "seconds_per_run": statistics.fmean(r["seconds"] for r in rows) if rows else float("nan"),
        "top_killers": ", ".join(f"{k} x{v}" for k, v in deaths.most_common(5)) or "-",
    }

def paired_diff(a_rows : list[dict], b_rows : list[dict], metric : str) -> dict:
    """Mean of (b - a) over the seeds both files have, with a 95% interval."""
    a = {r["seed"]: float(r[metric]) for r in a_rows}
    diffs = [float(r[metric]) - a[r["seed"]] for r in b_rows if r["seed"] in a]
    n = len(diffs)
    if n == 0:
        return {"n": 0, "mean": float("nan"), "ci95": float("nan"), "significant": False}
    mean = statistics.fmean(diffs)
    ci = 1.96 * statistics.stdev(diffs) / math.sqrt(n) if n > 1 else float("inf")
    return {"n": n, "mean": mean, "ci95": ci, "significant": abs(mean) > ci}

def run_meta(args) -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=SCRIPTS_DIR).stdout.strip() or None
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=SCRIPTS_DIR).stdout.strip())
    except OSError:
        commit, dirty = None, None
    return {"commit": commit, "dirty": dirty, "time": datetime.now().isoformat(timespec="seconds")}

def write_results(label : str, header : dict, rows : list[dict]) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_runs_{label}.jsonl"
    with open(path, "w") as f:
        f.write(json.dumps({"type": "header", "suite": "runs", "label": label, **header}) + "\n")
        for r in sorted(rows, key=lambda r: r["seed"]):
            f.write(json.dumps(r) + "\n")
    return path

def read_results(path : Path) -> tuple[dict, list[dict]]:
    with open(path) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if not rows or rows[0].get("type") != "header" or rows[0].get("suite") != "runs":
        raise SystemExit(f"{path} is not a runs results file")
    return rows[0], rows[1:]

def compare_files(path_a : Path, path_b : Path) -> str:
    (ha, ra), (hb, rb) = read_results(path_a), read_results(path_b)
    lines = [f"A: {ha['label']} ({ha.get('commit')}{'*' if ha.get('dirty') else ''}, agent {ha['agent']}, preset {ha['preset']})",
             f"B: {hb['label']} ({hb.get('commit')}{'*' if hb.get('dirty') else ''}, agent {hb['agent']}, preset {hb['preset']})"]
    if ha.get("ascension") != hb.get("ascension"):
        lines.append(f"  note: ascension differs ({ha.get('ascension')} vs {hb.get('ascension')})")
    sa, sb = summarize(ra), summarize(rb)
    for k in sa:
        lines.append(f"  {k:22s} {fmt(sa[k]):>14s} -> {fmt(sb[k]):>14s}")
    for metric in ("floor", "act", "won"):
        d = paired_diff(ra, rb, metric)
        verdict = "SIGNIFICANT" if d["significant"] else "within noise"
        lines.append(f"  paired Δ{metric:5s} (B-A) = {d['mean']:+.3f} ± {d['ci95']:.3f}  [{verdict}, n={d['n']}]")
    return "\n".join(lines)

def show(path : Path) -> str:
    h, rows = read_results(path)
    out = [f"{h['label']} ({h.get('commit')}): agent {h['agent']}, preset {h['preset']}, ascension {h.get('ascension')}, {len(rows)} runs"]
    out += [f"  {k:22s} {fmt(v)}" for k, v in summarize(rows).items()]
    out.append("  seed  won  act floor   hp  fights elites  secs  killed by")
    for r in sorted(rows, key=lambda r: r["seed"]):
        out.append(f"  {r['seed']:4d}  {'yes' if r['won'] else ' no':>3s}  {r['act']:3d} {r['floor']:5d} {r.get('hp', 0):4d} {r.get('fights', 0):6d} {r.get('rooms', {}).get('Elite', 0):6d} {r['seconds']:5.0f}  {r.get('cause') or r.get('error') or '-'}")
    return "\n".join(out)


# ---------------------------------------------------------------- cli
def main(argv : list[str] | None = None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="play whole runs and write a results file")
    r.add_argument("--agent", default="my")
    r.add_argument("--seeds", type=int, default=10, help="how many runs (seeds first-seed .. first-seed+seeds-1)")
    r.add_argument("--first-seed", type=int, default=0)
    r.add_argument("--ascension", type=int, default=0)
    r.add_argument("--preset", choices=PRESETS, default="full")
    r.add_argument("--time-budget", type=float, default=None, help="seconds per combat decision (default: the preset's)")
    r.add_argument("--set", action="append", default=[], metavar="module.NAME=value", help="override a module constant in the workers (after the preset's)")
    r.add_argument("--workers", type=int, default=default_workers())
    r.add_argument("--label", default=None)
    r.add_argument("--log", action="store_true", help="keep what the choosers print, one file per run")
    c = sub.add_parser("compare", help="paired comparison of two results files")
    c.add_argument("a", type=Path)
    c.add_argument("b", type=Path)
    s = sub.add_parser("show", help="the summary and every run of a results file")
    s.add_argument("file", type=Path)
    args = p.parse_args(argv)

    if args.cmd == "compare":
        print(compare_files(args.a, args.b))
    elif args.cmd == "show":
        print(show(args.file))
    else:
        preset = PRESETS[args.preset]
        settings = preset["set"] + args.set
        budget = args.time_budget if args.time_budget is not None else preset["time_budget"]
        label = args.label or f"{args.agent}_{args.preset}"
        stamp = f"{datetime.now():%Y%m%d_%H%M%S}_runs_{label}"
        jobs = [(args.agent, seed, args.ascension, budget, settings, str(RESULTS_DIR / f"{stamp}_logs" / f"seed{seed}.txt") if args.log else None)
                for seed in range(args.first_seed, args.first_seed + args.seeds)]
        rows = map_jobs(_job, jobs, args.workers, "runs")
        header = {"agent": args.agent, "preset": args.preset, "ascension": args.ascension, "time_budget": budget, "settings": settings, "seeds": [args.first_seed, args.first_seed + args.seeds], **run_meta(args)}
        path = write_results(label, header, rows)
        if args.log:
            (RESULTS_DIR / f"{stamp}_logs").rename(RESULTS_DIR / f"{path.stem}_logs") if (RESULTS_DIR / f"{stamp}_logs").exists() and stamp != path.stem else None
        print(show(path))
        print(f"wrote {path}")

if __name__ == "__main__":
    main()
