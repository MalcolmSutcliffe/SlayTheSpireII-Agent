"""MCTS benchmark harness.

Suites:
  decisions  regret/agreement of a config's root move vs a long-search reference (search efficiency)
  fights     whole fights played in the sim from benchmark states (playing strength)

Usage (from scripts/):
  python -m benchmarks.bench build-ref [--sims 100000] [--seeds 3]
  python -m benchmarks.bench decisions --config baseline [--seeds 10] [--smoke]
  python -m benchmarks.bench fights    --config baseline [--seeds 10] [--smoke]
  python -m benchmarks.bench compare results/A.jsonl results/B.jsonl
Any config field can be overridden: --set exploration=1.0 --set max_sims=500
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import io
import json
import math
import multiprocessing
import os
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:                       # allow `python benchmarks/bench.py`
    sys.path.insert(0, str(SCRIPTS_DIR))

from sts2_lite import rng
from sts2_lite.combat import CombatState, CombatSimulator
from agents.sts2_MCTS.MCTS import sts2_MCTS, SearchConfig, RolloutPolicy

BENCH_DIR = Path(__file__).resolve().parent
STATES_DIR = BENCH_DIR / "act1"
REFERENCE_PATH = BENCH_DIR / "reference_act1.jsonl"
RESULTS_DIR = BENCH_DIR / "results"

TIE_EPS = 0.01              # regret at or below this counts as agreeing with the reference
DEATH_PENALTY = 20          # fight score of a loss = start_hp + DEATH_PENALTY (always worse than any win)
FIGHT_TURN_CAP = 50
SEARCH_SEED_OFFSET = 1_000_000   # keeps search and world rng streams distinct
DECISION_SEED_OFFSET = 10_000    # decision-suite seeds never reuse reference seeds

CONFIGS = {
    "baseline":  SearchConfig(max_sims=2000),
    "fast":      SearchConfig(max_sims=500),
    "reference": SearchConfig(max_sims=100_000, early_exit=False),
}


# ---------------------------------------------------------------- states and configs
def load_index(smoke: bool = False) -> list[dict]:
    """Benchmark entries; smoke keeps round-1 states only (one full fight per encounter)."""
    with open(STATES_DIR / "index.jsonl") as f:
        entries = [json.loads(line) for line in f if line.strip()]
    return [e for e in entries if e["round"] == 1] if smoke else entries

@lru_cache(maxsize=None)
def _raw_state(file: str) -> str:
    return (STATES_DIR / file).read_text()

def load_state(file: str) -> CombatState:
    """Fresh CombatState per call; file read is cached per process."""
    with contextlib.redirect_stdout(io.StringIO()):         # sim warnings (unimplemented cards) once per load
        return CombatState.from_dict(json.loads(_raw_state(file)))

def parse_overrides(pairs: list[str]) -> dict:
    """['exploration=1.0', 'rollout=FirstAction'] -> typed field values for SearchConfig."""
    fields = {f.name: f for f in dataclasses.fields(SearchConfig)}
    defaults = SearchConfig()
    out = {}
    for pair in pairs or []:
        name, _, raw = pair.partition("=")
        if name not in fields:
            raise SystemExit(f"unknown SearchConfig field '{name}' (fields: {', '.join(fields)})")
        current = getattr(defaults, name)
        if isinstance(current, RolloutPolicy) or name == "rollout":
            out[name] = RolloutPolicy[raw]
        elif isinstance(current, bool):
            out[name] = raw.lower() in ("1", "true", "yes")
        elif raw.lower() == "none":
            out[name] = None
        elif isinstance(current, int):
            out[name] = int(float(raw))
        else:
            out[name] = float(raw)
    return out

def make_config(name: str, overrides: list[str] | None = None) -> SearchConfig:
    return dataclasses.replace(CONFIGS[name], **parse_overrides(overrides))

def config_dict(config: SearchConfig) -> dict:
    d = dataclasses.asdict(config)
    d["rollout"] = config.rollout.name
    return d

def config_from_dict(d: dict) -> SearchConfig:
    d = dict(d)
    d["rollout"] = RolloutPolicy[d["rollout"]]
    return SearchConfig(**d)

def action_key(action: dict) -> str:
    """Stable within one state (same state -> same indices); never compare across states."""
    return json.dumps(action, sort_keys=True)


# ---------------------------------------------------------------- search
def run_search(state: CombatState, config: SearchConfig, seed: int) -> tuple[dict, dict]:
    rng.seed(seed)
    return sts2_MCTS().monte_carlo_tree_search(state, config)


# ---------------------------------------------------------------- reference
def _reference_job(job: tuple) -> dict:
    file, seed, config_d = job
    action, stats = run_search(load_state(file), config_from_dict(config_d), seed)
    return {"file": file, "seed": seed, "pick": action_key(action),
            "children": [{"key": action_key(c["action"]), "visits": c["visits"], "q": c["q"]} for c in stats["children"]]}

def merge_reference(file: str, runs: list[dict]) -> dict:
    """Visit-weighted mean Q per move across seeds; best = most total visits; stable = every seed picked it."""
    q_sum, n_sum = defaultdict(float), defaultdict(int)
    for run in runs:
        for c in run["children"]:
            q_sum[c["key"]] += c["q"] * c["visits"]
            n_sum[c["key"]] += c["visits"]
    q = {k: q_sum[k] / n_sum[k] for k in n_sum if n_sum[k] > 0}
    best = max(n_sum, key=n_sum.get)
    picks = {run["pick"] for run in runs}
    return {"file": file, "q": q, "visits": dict(n_sum), "best": best,
            "stable": len(picks) == 1, "seeds": len(runs)}

def build_reference(sims: int, seeds: int, workers: int, smoke: bool = False, out: Path = REFERENCE_PATH) -> list[dict]:
    config = dataclasses.replace(CONFIGS["reference"], max_sims=sims)
    entries = load_index(smoke)
    jobs = [(e["file"], s, config_dict(config)) for e in entries for s in range(seeds)]
    runs = map_jobs(_reference_job, jobs, workers, "reference")
    by_file = defaultdict(list)
    for r in runs:
        by_file[r["file"]].append(r)
    refs = [merge_reference(e["file"], by_file[e["file"]]) for e in entries]
    with open(out, "w") as f:
        f.write(json.dumps({"type": "header", "suite": "reference", **run_meta(config)}) + "\n")
        for ref in refs:
            f.write(json.dumps(ref) + "\n")
    return refs

def load_reference(path: Path = REFERENCE_PATH) -> dict[str, dict]:
    if not path.exists():
        raise SystemExit(f"no reference at {path}; run `build-ref` first")
    with open(path) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return {r["file"]: r for r in rows if r.get("type") != "header"}


# ---------------------------------------------------------------- decision suite
def score_decision(ref: dict, action: dict) -> dict:
    k = action_key(action)
    best_q = ref["q"][ref["best"]]
    regret = best_q - ref["q"].get(k, min(ref["q"].values()))
    return {"regret": regret, "agree": regret <= TIE_EPS, "exact": k == ref["best"], "stable": ref["stable"]}

def _decision_job(job: tuple) -> dict:
    file, seed, config_d, ref = job
    action, stats = run_search(load_state(file), config_from_dict(config_d), DECISION_SEED_OFFSET + seed)
    return {"file": file, "seed": seed, **score_decision(ref, action),
            "sims": stats["num_sims"], "seconds": stats["time_taken"], "exit_reason": stats["exit_reason"]}

def eval_decisions(config: SearchConfig, seeds: int, workers: int, smoke: bool = False) -> list[dict]:
    refs = load_reference()
    entries = [e for e in load_index(smoke) if e["file"] in refs]
    jobs = [(e["file"], s, config_dict(config), refs[e["file"]]) for e in entries for s in range(seeds)]
    return map_jobs(_decision_job, jobs, workers, "decisions")

def summarize_decisions(rows: list[dict]) -> dict:
    stable = [r for r in rows if r["stable"]]
    return {
        "n": len(rows),
        "mean_regret": statistics.fmean(r["regret"] for r in rows),
        "agree_stable": statistics.fmean(r["agree"] for r in stable) if stable else float("nan"),
        "agree_all": statistics.fmean(r["agree"] for r in rows),
        "mean_sims": statistics.fmean(r["sims"] for r in rows),
        "mean_seconds": statistics.fmean(r["seconds"] for r in rows),
    }


# ---------------------------------------------------------------- fight suite
def is_won(state: CombatState) -> bool:
    return state.player.current_hp > 0 and all(e.is_minion or e.current_hp <= 0 for e in state.enemies)

def play_fight(start: CombatState, config: SearchConfig, world_seed: int, search_seed: int,
               turn_cap: int = FIGHT_TURN_CAP) -> dict:
    """Plays one fight. World (draws, enemy rolls) and search use separate rng streams, swapped around each call,
    so configs facing the same world_seed see the same opening and stay matched until their moves diverge."""
    rng.seed(world_seed);  world = rng.getstate()
    rng.seed(search_seed); search = rng.getstate()

    sim = CombatSimulator(CombatState.deepcopy(start))
    state = sim.combat_state
    rng.setstate(world)
    state.player.shuffle_draw_pile()                       # unknown draw order differs per world seed; known top kept
    world = rng.getstate()

    start_hp, start_turn = state.player.current_hp, state.turn_number
    decisions = sims = 0
    seconds = 0.0
    while not sim.is_over and sim.combat_state.turn_number < start_turn + turn_cap:
        actions = sim.get_available_actions()
        if not actions:
            break
        if len(actions) == 1:
            action = actions[0]
        else:
            rng.setstate(search)
            action, stats = sts2_MCTS().monte_carlo_tree_search(sim.combat_state, config)
            search = rng.getstate()
            decisions += 1
            sims += stats["num_sims"]
            seconds += stats["time_taken"]
        rng.setstate(world)
        sim.perform_action(action)
        world = rng.getstate()

    state = sim.combat_state
    won = is_won(state)
    hp_lost = start_hp - max(state.player.current_hp, 0)
    return {"won": won, "hp_lost": hp_lost, "score": hp_lost if won else start_hp + DEATH_PENALTY,
            "turns": state.turn_number - start_turn, "finished": sim.is_over,
            "decisions": decisions, "sims": sims, "seconds": seconds}

def _fight_job(job: tuple) -> dict:
    file, seed, config_d = job
    result = play_fight(load_state(file), config_from_dict(config_d), seed, SEARCH_SEED_OFFSET + seed)
    return {"file": file, "seed": seed, **result}

def eval_fights(config: SearchConfig, seeds: int, workers: int, smoke: bool = False) -> list[dict]:
    jobs = [(e["file"], s, config_dict(config)) for e in load_index(smoke) for s in range(seeds)]
    return map_jobs(_fight_job, jobs, workers, "fights")

def summarize_fights(rows: list[dict]) -> dict:
    return {
        "n": len(rows),
        "win_rate": statistics.fmean(r["won"] for r in rows),
        "mean_hp_lost_won": statistics.fmean([r["hp_lost"] for r in rows if r["won"]] or [float("nan")]),
        "mean_score": statistics.fmean(r["score"] for r in rows),
        "unfinished": sum(not r["finished"] for r in rows),
        "sims_per_decision": sum(r["sims"] for r in rows) / max(1, sum(r["decisions"] for r in rows)),
        "seconds_per_decision": sum(r["seconds"] for r in rows) / max(1, sum(r["decisions"] for r in rows)),
    }


# ---------------------------------------------------------------- comparison
METRICS = {"decisions": "regret", "fights": "score"}   # lower is better for both

def paired_diff(a_rows: list[dict], b_rows: list[dict], metric: str) -> dict:
    """Mean of (b - a) over (file, seed) pairs present in both, with a 95% interval."""
    a = {(r["file"], r["seed"]): r[metric] for r in a_rows}
    diffs = [float(r[metric]) - float(a[(r["file"], r["seed"])]) for r in b_rows if (r["file"], r["seed"]) in a]
    n = len(diffs)
    if n == 0:
        return {"n": 0, "mean": float("nan"), "ci95": float("nan"), "significant": False}
    mean = statistics.fmean(diffs)
    ci = 1.96 * statistics.stdev(diffs) / math.sqrt(n) if n > 1 else float("inf")
    return {"n": n, "mean": mean, "ci95": ci, "significant": abs(mean) > ci}

def compare_files(path_a: Path, path_b: Path) -> str:
    (ha, ra), (hb, rb) = read_results(path_a), read_results(path_b)
    if ha["suite"] != hb["suite"]:
        raise SystemExit(f"cannot compare a '{ha['suite']}' run with a '{hb['suite']}' run")
    suite = ha["suite"]
    lines = [f"A: {ha['label']} ({ha['commit']})", f"B: {hb['label']} ({hb['commit']})"]
    summarize = summarize_decisions if suite == "decisions" else summarize_fights
    sa, sb = summarize(ra), summarize(rb)
    for k in sa:
        lines.append(f"  {k:22s} {fmt(sa[k]):>10s} -> {fmt(sb[k]):>10s}")
    extra = ["won"] if suite == "fights" else ["agree"]
    for metric in [METRICS[suite]] + extra:
        d = paired_diff(ra, rb, metric)
        verdict = "SIGNIFICANT" if d["significant"] else "within noise"
        lines.append(f"  paired Δ{metric} (B-A) = {d['mean']:+.4f} ± {d['ci95']:.4f}  [{verdict}, n={d['n']}]")
    return "\n".join(lines)


# ---------------------------------------------------------------- io and parallelism
def run_meta(config: SearchConfig) -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                cwd=SCRIPTS_DIR).stdout.strip() or None
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                                    cwd=SCRIPTS_DIR).stdout.strip())
    except OSError:
        commit, dirty = None, None
    return {"config": config_dict(config), "commit": commit, "dirty": dirty,
            "time": datetime.now().isoformat(timespec="seconds")}

def write_results(suite: str, label: str, config: SearchConfig, rows: list[dict], extra: dict) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{suite}_{label}.jsonl"
    with open(path, "w") as f:
        f.write(json.dumps({"type": "header", "suite": suite, "label": label, **extra, **run_meta(config)}) + "\n")
        for r in sorted(rows, key=lambda r: (r["file"], r["seed"])):
            f.write(json.dumps(r) + "\n")
    return path

def read_results(path: Path) -> tuple[dict, list[dict]]:
    with open(path) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if not rows or rows[0].get("type") != "header":
        raise SystemExit(f"{path} has no header line")
    return rows[0], rows[1:]

def map_jobs(fn, jobs: list, workers: int, name: str) -> list:
    """Runs jobs (in a process pool when workers > 1) with a progress line on stderr."""
    t0, out = time.perf_counter(), []
    def progress(i):
        el = time.perf_counter() - t0
        eta = el / i * (len(jobs) - i)
        print(f"\r{name}: {i}/{len(jobs)}  {el:6.0f}s elapsed  ~{eta:5.0f}s left", end="", file=sys.stderr, flush=True)
    if workers <= 1:
        for i, job in enumerate(jobs, 1):
            out.append(fn(job))
            progress(i)
    else:
        with multiprocessing.Pool(workers) as pool:
            for i, r in enumerate(pool.imap_unordered(fn, jobs), 1):
                out.append(r)
                progress(i)
    print(file=sys.stderr)
    return out

def fmt(v) -> str:
    if isinstance(v, float):
        return "nan" if math.isnan(v) else f"{v:.4f}" if abs(v) < 10 else f"{v:.1f}"
    return str(v)


# ---------------------------------------------------------------- cli
def main(argv: list[str] | None = None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(s, seeds):
        s.add_argument("--seeds", type=int, default=seeds)
        s.add_argument("--smoke", action="store_true", help="round-1 states only")
        s.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))

    r = sub.add_parser("build-ref", help="long searches on every state -> reference_act1.jsonl")
    common(r, 3)
    r.add_argument("--sims", type=int, default=CONFIGS["reference"].max_sims)

    for name in ("decisions", "fights"):
        s = sub.add_parser(name)
        common(s, 10)
        s.add_argument("--config", default="baseline", choices=CONFIGS)
        s.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE", help="override a SearchConfig field")
        s.add_argument("--label", default=None, help="results file label (default: config name + overrides)")

    c = sub.add_parser("compare", help="paired comparison of two results files of the same suite")
    c.add_argument("a", type=Path)
    c.add_argument("b", type=Path)

    args = p.parse_args(argv)

    if args.cmd == "build-ref":
        refs = build_reference(args.sims, args.seeds, args.workers, args.smoke)
        print(f"wrote {REFERENCE_PATH}: {len(refs)} states, {sum(r['stable'] for r in refs)} stable")
    elif args.cmd in ("decisions", "fights"):
        config = make_config(args.config, args.set)
        label = args.label or "_".join([args.config] + [s.replace("=", "-") for s in args.set])
        run = eval_decisions if args.cmd == "decisions" else eval_fights
        rows = run(config, args.seeds, args.workers, args.smoke)
        summary = (summarize_decisions if args.cmd == "decisions" else summarize_fights)(rows)
        path = write_results(args.cmd, label, config, rows, {"seeds": args.seeds, "smoke": args.smoke})
        print(f"{label}: " + "  ".join(f"{k}={fmt(v)}" for k, v in summary.items()))
        print(f"wrote {path}")
    elif args.cmd == "compare":
        print(compare_files(args.a, args.b))

if __name__ == "__main__":
    main()
