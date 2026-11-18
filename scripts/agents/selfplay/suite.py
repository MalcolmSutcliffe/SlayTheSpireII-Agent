"""Self-play suite: many full runs in parallel, written to a compressed log that can be stopped and resumed.

  python -m agents.selfplay.suite --out first --runs 2000 --chooser rarity --c 0.5 --epsilon 0.05 --ascensions 0-10 --workers 4
  python -m agents.selfplay.suite --out gen0_mcts --runs 5000 --pilot mcts:100:big --workers 8 --batch 5

`--pilot` is who fights (run.parse_pilot): the rollout policy (default), or the MCTS (`mcts:100` every fight, `mcts:100:big` the elites and bosses). Each run logs its
pilot, and the value model reads it (value_model: the cards' worth under the MCTS is learned apart from under the rollout policy). `--chooser model:NAME[:FLOOR]`
picks with a fitted value model (data/selfplay/models/NAME, see choosers.make_chooser).

`--out NAME` is the folder data/selfplay/NAME: `runs.jsonl.gz` (one run per line: seed, a snapshot of the run on entering each room, every card pick with what was
offered, the scores and whether it was exploratory, and the outcome) and `meta.json` (the settings). Running it again with the same `--out` plays the seeds not done yet, and the
exploration counts (how often each card has been picked, per act) are rebuilt from the log, so a card tried a lot stops being explored whichever run played it.
The runs are played in rounds of `--batch` runs per worker; a round's counts are shared with the next round, not within it. A run depends on the counts it was played with,
so a log that was stopped and resumed is not identical to one played in a single go (each run is still repeatable given its counts)."""
from __future__ import annotations
import argparse
import collections
import gzip
import json
import os
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agents.selfplay.choosers import Counts, base_id
from agents.selfplay.run import RUN_TIMEOUT, parse_pilot, play_run_guarded

try:
    from data_paths import DATA
    OUT_ROOT = Path(DATA) / "selfplay"
except Exception:           # outside the project: next to the scripts
    OUT_ROOT = SCRIPTS_DIR / "selfplay_data"


def read_runs(path : Path):
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def parse_ascensions(text : str) -> list[int]:
    """"0-10" -> 0..10; "0,5,10" -> those; "10" -> [10]. A level listed twice is drawn twice as often: "0-10,10,10" leans on 10."""
    out = []
    for part in text.split(","):
        lo, _, hi = part.partition("-")
        out += list(range(int(lo), int(hi or lo) + 1))
    return out


def ascension_of(seed : int, levels : list[int]) -> int:
    return levels[random.Random(f"{seed}/ascension").randrange(len(levels))]


def job(args) -> list[dict]:
    seeds, chooser, counts, c, epsilon, levels, pilot, timeout = args
    counts = Counts.from_json(counts)
    return [play_run_guarded(s, chooser, counts, c, epsilon, ascension=ascension_of(s, levels), pilot=pilot, timeout=timeout) for s in seeds]


def summary(runs : list[dict]) -> str:
    if not runs:
        return "no runs"
    n = len(runs)
    rooms = [r["outcome"]["rooms_cleared"] for r in runs]
    acts = collections.Counter(r["outcome"]["act"] for r in runs)
    picks = [p for r in runs for p in r["picks"]]
    explore = sum(p["exploratory"] for p in picks)
    taken = collections.Counter(base_id(p["chosen"]) for p in picks if p["chosen"] != "SKIP")
    top = ", ".join(f"{k} {v}" for k, v in taken.most_common(8))
    least = ", ".join(f"{k} {v}" for k, v in sorted(taken.items(), key=lambda kv: kv[1])[:6])
    return (f"{n} runs | rooms cleared: mean {sum(rooms) / n:.1f}, max {max(rooms)} | died in act: " + ", ".join(f"{a}: {acts[a] - sum(r['outcome']['won'] for r in runs if r['outcome']['act'] == a)}" for a in sorted(acts))
            + f" | won {sum(r['outcome']['won'] for r in runs)} | picks {len(picks)}, exploratory {explore / max(1, len(picks)):.0%} | skipped {sum(p['chosen'] == 'SKIP' for p in picks) / max(1, len(picks)):.0%}\n"
            f"  most picked: {top}\n  least picked: {least}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, help="the folder name under data/selfplay")
    p.add_argument("--runs", type=int, default=1000, help="runs in all (with --start-seed, the seeds start-seed .. start-seed + runs - 1)")
    p.add_argument("--start-seed", type=int, default=1)
    p.add_argument("--chooser", default="rarity", help="random | rarity | model:NAME[:FLOOR] (a fitted value model under data/selfplay/models)")
    p.add_argument("--pilot", default="rollout", help="who fights: rollout | mcts:N (every fight) | mcts:N:big (elites and bosses; the rest by the corrected rollout policy)")
    p.add_argument("--c", type=float, default=0.5, help="exploration bonus c / sqrt(n + 1), in the chooser's score units")
    p.add_argument("--epsilon", type=float, default=0.05, help="chance of a uniform random pick")
    p.add_argument("--ascensions", default="0", help="the ascension of each run is drawn from these: 10, 0-10, 0,5,10; a level listed twice is drawn twice as often")
    p.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    p.add_argument("--batch", type=int, default=25, help="runs a worker plays per round (an MCTS pilot plays a run in seconds to a minute: use a small batch, e.g. 5)")
    p.add_argument("--run-timeout", type=int, default=RUN_TIMEOUT, help="seconds before a run is given up as stuck (logged as an engine error; 0: never)")
    args = p.parse_args(argv)
    args.pilot = parse_pilot(args.pilot).name

    out = OUT_ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    log = out / "runs.jsonl.gz"
    meta = {k: getattr(args, k) for k in ("chooser", "c", "epsilon", "ascensions", "pilot")}
    meta_file = out / "meta.json"
    if meta_file.exists() and {"pilot": "rollout", **json.loads(meta_file.read_text())} != meta:          # a log from before pilots: the rollout policy
        print(f"{meta_file} has other settings ({meta_file.read_text().strip()}): use another --out, or the same settings", file=sys.stderr)
        return 1
    meta_file.write_text(json.dumps(meta))

    levels = parse_ascensions(args.ascensions)
    counts, done = Counts(), set()
    for run in read_runs(log):
        done.add(run["seed"])
        counts.add_run(run["picks"])
    todo = [s for s in range(args.start_seed, args.start_seed + args.runs) if s not in done]
    print(f"{out}: {len(done)} runs already played, {len(todo)} to play, {args.workers} workers")
    start, played = time.perf_counter(), 0
    chunk = args.workers * args.batch
    per_job = 1 if args.pilot != "rollout" else args.batch          # MCTS runs take 0.1 s to a minute: one run per job keeps every worker busy to the end of a round
    with Pool(args.workers) as pool:
        for i in range(0, len(todo), chunk):
            seeds = todo[i:i + chunk]
            batches = [seeds[j:j + per_job] for j in range(0, len(seeds), per_job)]
            jobs = [(b, args.chooser, counts.to_json(), args.c, args.epsilon, levels, args.pilot, args.run_timeout) for b in batches]
            results = []
            for batch in pool.imap_unordered(job, jobs):
                with gzip.open(log, "at", encoding="utf-8") as f:          # written as it comes in: a stopped suite keeps every run it finished
                    for run in batch:
                        f.write(json.dumps(run, separators=(",", ":")) + "\n")
                results += batch
            for run in results:
                counts.add_run(run["picks"])            # the next round explores with them
            played += len(results)
            rate = played / (time.perf_counter() - start)
            print(f"{len(done) + played}/{len(done) + len(todo)} runs  {rate:.2f} runs/s  ~{(len(todo) - played) / rate / 60:.1f} min left", flush=True)
    print(summary(list(read_runs(log))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
