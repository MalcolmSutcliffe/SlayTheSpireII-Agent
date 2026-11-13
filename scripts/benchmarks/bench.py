"""MCTS benchmark harness.

Suites:
  decisions  regret/agreement of a config's root move vs a long-search reference (search efficiency)
  fights     whole fights played in the sim from benchmark states (playing strength)

Usage (from scripts/):
  python -m benchmarks.bench build-ref [--sims 100000] [--seeds 3] [--subset draw]
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

from data_paths import BENCHMARKS
from sts2_lite import rng
from sts2_lite.combat import CombatState, CombatSimulator
from agents.sts2_MCTS.MCTS import sts2_MCTS
from agents.sts2_MCTS.params import GROUPS, SearchConfig, RolloutPolicy

BENCH_DIR = Path(__file__).resolve().parent            # results/ lives here; the suites and reference files are in data/benchmarks/
RESULTS_DIR = BENCH_DIR / "results"
SUITES = ("run4", "act1")        # a suite is a folder of state files + index.jsonl; run4 = real states from data/runs/run4-a9 (current reward)
DEFAULT_SUITE = "run4"

def states_dir(suite: str = DEFAULT_SUITE) -> Path:
    if suite not in SUITES:
        raise SystemExit(f"unknown suite {suite!r}; choose from {SUITES}")
    return BENCHMARKS / suite

def puzzles_path(suite: str = DEFAULT_SUITE) -> Path:
    return BENCHMARKS / f"puzzles_{suite}.json"

TIE_EPS = 0.05              # regret (reward units) at or below this counts as agreeing with the reference: about one HP near full health
REF_EXPLORATION_SCALE = 60.0   # the reference searches explore widely (the live scale lets an early lucky winner starve the other moves); this is set for them only
REF_MIN_VISIT_SHARE = 0.02  # a root move is only a candidate for the reference's best when it kept this share of the reference visits
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
DRAW_CARDS = frozenset({"BATTLE_TRANCE", "BURNING_PACT", "DRUM_OF_BATTLE", "FINESSE", "FLASH_OF_STEEL", "IMPATIENCE", "MASTER_OF_STRATEGY",
                        "OFFERING", "PILLAGE", "POMMEL_STRIKE", "RESTLESSNESS", "SCRAWL", "SHRUG_IT_OFF", "THINKING_AHEAD",       # draw
                        "BLOODLETTING", "EXPECT_A_FIGHT", "FORGOTTEN_RITUAL", "PRODUCTION"})                                     # energy
SUBSETS = ("draw",)

def load_index(smoke: bool = False, subset: str | None = None, suite: str = DEFAULT_SUITE) -> list[dict]:
    """Benchmark entries; smoke keeps round-1 states only (one full fight per encounter).
    subset "draw": states with a draw or energy card in hand (does the search value information?)."""
    with open(states_dir(suite) / "index.jsonl") as f:
        entries = [json.loads(line) for line in f if line.strip()]
    if smoke:
        entries = [e for e in entries if e["round"] == 1]
    if subset == "draw":
        entries = [e for e in entries if any(c.card_id.name in DRAW_CARDS for c in load_state(e["file"], suite).player.hand)]
    elif subset is not None:
        raise SystemExit(f"unknown subset {subset!r}; choose from {SUBSETS}")
    return entries

def reference_path(subset: str | None = None, suite: str = DEFAULT_SUITE) -> Path:
    return BENCHMARKS / (f"reference_{suite}.jsonl" if subset is None else f"reference_{suite}_{subset}.jsonl")

@lru_cache(maxsize=None)
def _raw_state(file: str, suite: str = DEFAULT_SUITE) -> str:
    return (states_dir(suite) / file).read_text()

def load_state(file: str, suite: str = DEFAULT_SUITE) -> CombatState:
    """Fresh CombatState per call; file read is cached per process."""
    with contextlib.redirect_stdout(io.StringIO()):         # sim warnings (unimplemented cards) once per load
        return CombatState.from_dict(json.loads(_raw_state(file, suite)))

def search_fields() -> dict[str, tuple]:
    """Every parameter of a search by name -> (default value, the dataclass field). Fields of the groups (reward, uct, ...) are flat here."""
    defaults = SearchConfig()
    fields = {f.name: (getattr(defaults, f.name), f) for f in dataclasses.fields(SearchConfig) if f.name not in GROUPS}
    for group in GROUPS:
        for f in dataclasses.fields(getattr(defaults, group)):
            fields[f.name] = (getattr(getattr(defaults, group), f.name), f)
    return fields

def parse_overrides(pairs: list[str]) -> dict:
    """['exploration=1.0', 'rollout=FirstAction', 'p_random_action=0'] -> typed values for SearchConfig.tuned (a group's fields are named directly)."""
    fields = search_fields()
    out = {}
    for pair in pairs or []:
        name, _, raw = pair.partition("=")
        if name not in fields:
            raise SystemExit(f"unknown search parameter '{name}' (parameters: {', '.join(fields)})")
        current = fields[name][0]
        if isinstance(current, dict):
            raise SystemExit(f"'{name}' is a table; change it in agents/sts2_MCTS/params.py or policy_sweep.py")
        if isinstance(current, RolloutPolicy) or name == "rollout":
            out[name] = RolloutPolicy[raw]
        elif isinstance(current, bool):
            out[name] = raw.lower() in ("1", "true", "yes")
        elif raw.lower() == "none":
            out[name] = None
        elif isinstance(current, int):
            out[name] = int(float(raw))
        elif isinstance(current, str):
            out[name] = raw
        else:
            out[name] = float(raw)
    return out

def make_config(name: str, overrides: list[str] | None = None) -> SearchConfig:
    return CONFIGS[name].tuned(**parse_overrides(overrides))

def config_dict(config: SearchConfig) -> dict:
    return config.to_dict()

def config_from_dict(d: dict) -> SearchConfig:
    return SearchConfig.from_dict(d)

def action_key(action: dict) -> str:
    """Stable within one state (same state -> same indices); never compare across states."""
    return json.dumps(action, sort_keys=True)


# ---------------------------------------------------------------- search
def run_search(state: CombatState, config: SearchConfig, seed: int) -> tuple[dict, dict]:
    rng.seed(seed)
    return sts2_MCTS().monte_carlo_tree_search(state, config)


# ---------------------------------------------------------------- reference
def _reference_job(job: tuple) -> dict:
    file, seed, config_d, suite = job
    action, stats = run_search(load_state(file, suite), config_from_dict(config_d).tuned(exploration_scale=REF_EXPLORATION_SCALE), seed)
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
    total = sum(n_sum.values())
    contenders = [k for k in q if n_sum[k] >= REF_MIN_VISIT_SHARE * total] or list(q)
    best = max(contenders, key=q.get)         # highest mean among moves the reference really explored (the most visited can be a lucky early winner)
    picks = {run["pick"] for run in runs}
    return {"file": file, "q": q, "visits": dict(n_sum), "best": best,
            "stable": len(picks) == 1, "seeds": len(runs)}

def build_reference(sims: int, seeds: int, workers: int, smoke: bool = False, out: Path | None = None, subset: str | None = None, suite: str = DEFAULT_SUITE) -> list[dict]:
    out = out or reference_path(subset, suite)
    config = dataclasses.replace(CONFIGS["reference"], max_sims=sims)
    entries = load_index(smoke, subset, suite)
    jobs = [(e["file"], s, config_dict(config), suite) for e in entries for s in range(seeds)]
    runs = map_jobs(_reference_job, jobs, workers, "reference")
    by_file = defaultdict(list)
    for r in runs:
        by_file[r["file"]].append(r)
    refs = [merge_reference(e["file"], by_file[e["file"]]) for e in entries]
    with open(out, "w") as f:
        f.write(json.dumps({"type": "header", "suite": "reference", "states": suite, **run_meta(config)}) + "\n")
        for ref in refs:
            f.write(json.dumps(ref) + "\n")
    return refs

def load_reference(path: Path | None = None) -> dict[str, dict]:
    path = path or reference_path()
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
    file, seed, config_d, ref, suite = job
    action, stats = run_search(load_state(file, suite), config_from_dict(config_d), DECISION_SEED_OFFSET + seed)
    return {"file": file, "seed": seed, **score_decision(ref, action),
            "sims": stats["num_sims"], "seconds": stats["time_taken"], "exit_reason": stats["exit_reason"]}

def eval_decisions(config: SearchConfig, seeds: int, workers: int, smoke: bool = False, subset: str | None = None, suite: str = DEFAULT_SUITE) -> list[dict]:
    refs = load_reference(reference_path(subset, suite))
    entries = [e for e in load_index(smoke, subset, suite) if e["file"] in refs]
    jobs = [(e["file"], s, config_dict(config), refs[e["file"]], suite) for e in entries for s in range(seeds)]
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


# ---------------------------------------------------------------- puzzles
# Known-answer positions (puzzles_<suite>.json): "accept" lists the labels that pass (any other fails), "reject" lists the labels that
# fail. A label is the card's name (BRAND, STRIKE...), "potion" or "end_turn". They need no reference search, so they stay valid when
# the reward changes. "opinion": true marks a judgment call rather than a provable error.
def load_puzzles(suite: str = DEFAULT_SUITE) -> list[dict]:
    return json.loads(puzzles_path(suite).read_text())

def action_label(state: CombatState, action: dict) -> str:
    if action["action"] == "use_potion":
        return "potion"
    if action["action"] == "play_card":
        name = state.player.hand[action["card_index"]].card_id.name
        return name[:-len("_IRONCLAD")] if name.endswith("_IRONCLAD") else name
    return action["action"]

def puzzle_passes(puzzle: dict, label: str) -> bool:
    if "accept" in puzzle:
        return label in puzzle["accept"]
    return label not in puzzle["reject"]

def _puzzle_job(job: tuple) -> dict:
    puzzle, seed, config_d, suite = job
    state = load_state(puzzle["file"], suite)
    action, stats = run_search(state, config_from_dict(config_d), DECISION_SEED_OFFSET + seed)
    label = action_label(load_state(puzzle["file"], suite), action)
    return {"file": puzzle["file"], "seed": seed, "label": label, "fail": int(not puzzle_passes(puzzle, label)),
            "opinion": bool(puzzle.get("opinion")), "sims": stats["num_sims"], "seconds": stats["time_taken"]}

def eval_puzzles(config: SearchConfig, seeds: int, workers: int, smoke: bool = False, subset: str | None = None, suite: str = DEFAULT_SUITE) -> list[dict]:
    jobs = [(p, s, config_dict(config), suite) for p in load_puzzles(suite) for s in range(seeds)]
    return map_jobs(_puzzle_job, jobs, workers, "puzzles")

def summarize_puzzles(rows: list[dict]) -> dict:
    proven = [r for r in rows if not r["opinion"]]
    return {"n": len(rows),
            "fail_rate_proven": statistics.fmean(r["fail"] for r in proven) if proven else float("nan"),
            "fail_rate_opinion": statistics.fmean([r["fail"] for r in rows if r["opinion"]] or [float("nan")]),
            "mean_sims": statistics.fmean(r["sims"] for r in rows),
            "mean_seconds": statistics.fmean(r["seconds"] for r in rows)}

def puzzle_table(rows: list[dict]) -> str:
    by = defaultdict(list)
    for r in rows:
        by[r["file"]].append(r)
    out = []
    for file, rs in sorted(by.items()):
        picks = defaultdict(int)
        for r in rs:
            picks[r["label"]] += 1
        out.append(f"  {file}  fail {sum(r['fail'] for r in rs)}/{len(rs)}  picks " + ", ".join(f"{k}:{v}" for k, v in sorted(picks.items())))
    return "\n".join(out)

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
    searcher = sts2_MCTS()                                 # one per fight: with config.reuse_tree it carries the tree from move to move
    while not sim.is_over and sim.combat_state.turn_number < start_turn + turn_cap:
        actions = sim.get_available_actions()
        if not actions:
            break
        if len(actions) == 1:
            action = actions[0]
        else:
            rng.setstate(search)
            action, stats = searcher.monte_carlo_tree_search(sim.combat_state, config)
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
    file, seed, config_d, suite = job
    result = play_fight(load_state(file, suite), config_from_dict(config_d), seed, SEARCH_SEED_OFFSET + seed)
    return {"file": file, "seed": seed, **result}

def eval_fights(config: SearchConfig, seeds: int, workers: int, smoke: bool = False, subset: str | None = None, suite: str = DEFAULT_SUITE) -> list[dict]:
    jobs = [(e["file"], s, config_dict(config), suite) for e in load_index(smoke, subset, suite) for s in range(seeds)]
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
METRICS = {"decisions": "regret", "fights": "score", "puzzles": "fail"}   # lower is better for both

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
    summarize = {"decisions": summarize_decisions, "fights": summarize_fights, "puzzles": summarize_puzzles}[suite]
    sa, sb = summarize(ra), summarize(rb)
    for k in sa:
        lines.append(f"  {k:22s} {fmt(sa[k]):>10s} -> {fmt(sb[k]):>10s}")
    extra = {"fights": ["won"], "decisions": ["agree"], "puzzles": []}[suite]
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

MAX_DEFAULT_WORKERS = 4      # a 100k-sim search keeps its whole tree (~1 GB or more) alive; more workers than RAM allows freezes the machine

def default_workers() -> int:
    return max(1, min((os.cpu_count() or 2) - 2, MAX_DEFAULT_WORKERS))

def _lower_priority():
    with contextlib.suppress(AttributeError, OSError):       # no os.nice on Windows
        os.nice(10)

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
        with multiprocessing.Pool(workers, initializer=_lower_priority, maxtasksperchild=1) as pool:      # a fresh process per job returns the tree's memory
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
        s.add_argument("--suite", choices=SUITES, default=DEFAULT_SUITE, help="which folder of states (and its reference)")
        s.add_argument("--subset", choices=SUBSETS, default=None, help="draw: states with a draw or energy card in hand (own reference file)")
        s.add_argument("--workers", type=int, default=default_workers(), help="parallel searches; each holds its tree in RAM (~1 GB at 100k sims)")

    r = sub.add_parser("build-ref", help="long searches on every state -> reference_act1.jsonl")
    common(r, 3)
    r.add_argument("--sims", type=int, default=CONFIGS["reference"].max_sims)

    for name in ("decisions", "fights", "puzzles"):
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
        refs = build_reference(args.sims, args.seeds, args.workers, args.smoke, subset=args.subset, suite=args.suite)
        print(f"wrote {reference_path(args.subset, args.suite)}: {len(refs)} states, {sum(r['stable'] for r in refs)} stable")
    elif args.cmd in ("decisions", "fights", "puzzles"):
        config = make_config(args.config, args.set)
        label = args.label or "_".join([args.config] + [s.replace("=", "-") for s in args.set])
        run = {"decisions": eval_decisions, "fights": eval_fights, "puzzles": eval_puzzles}[args.cmd]
        rows = run(config, args.seeds, args.workers, args.smoke, args.subset, args.suite)
        summary = {"decisions": summarize_decisions, "fights": summarize_fights, "puzzles": summarize_puzzles}[args.cmd](rows)
        path = write_results(args.cmd, label, config, rows, {"seeds": args.seeds, "smoke": args.smoke, "subset": args.subset, "states": args.suite})
        print(f"{label}: " + "  ".join(f"{k}={fmt(v)}" for k, v in summary.items()))
        if args.cmd == "puzzles":
            print(puzzle_table(rows))
        print(f"wrote {path}")
    elif args.cmd == "compare":
        print(compare_files(args.a, args.b))

if __name__ == "__main__":
    main()
