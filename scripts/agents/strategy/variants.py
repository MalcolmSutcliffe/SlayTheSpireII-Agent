"""Random deck variants: fights the MCTS plays with decks changed at random, for the fight model to learn what cards do.

  python -m agents.strategy.variants --from fights_m400 --out var_m100 --n 50000 --per-source 8 --sims 100 --workers 15

Why not pairs (experiments.py): one card is worth ~1-2 HP of an elite or boss fight, and the MCTS's own play varies by ~10-13 HP between two replays of the
same fight with the same dice (its search draws; more simulations barely help), so a pair of fights cannot show a card's effect. What can is many fights
pooled in one model. Here each fight is a logged fight from self-play (the run going in and the encounter: `--from`) with the deck changed by 0 to
MAX_CHANGES random changes, played once:
  add      a card of the Ironclad's reward pool, every card as likely, upgraded with chance UPGRADE_SHARE;
  remove   a card of the deck (as it stands after the changes before it), each as likely.
The cards are assigned at random, so a model fitted on these fights learns what the cards do, not how decks go with where a run is. Each source fight gets
`--per-source` variants, all on the same game seed (the same monsters and their dice; one of them, often, the deck as it was), so the fight model's report can compare the variants of one fight with each other: there
the deck is the only thing that differs (fight_model: the within-fight test).

A variant is written as a fight row the fight model reads (fight_model.variant_rows): the source fight's `before` with the variant's deck, the encounter and
kind, the result (won, hp_after, turns, progress), plus `source`, `base_deck` and `changes`. Results go to data/selfplay/variants/NAME.jsonl.gz as they finish;
running the same command again plays only the variants not done yet (and plays the failed ones again)."""
from __future__ import annotations
import argparse
import json
import os
import random
import sys
import time
import zlib
import gzip
from multiprocessing import Pool
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agents.strategy.experiments import REWARD_POOL, UPGRADE_SHARE, play, read, source_states

MAX_CHANGES = 4
ADD_SHARE = 0.6             # the rest of the changes remove a card


def changes_for(deck : list[str], r : random.Random, max_changes : int = MAX_CHANGES) -> tuple[list[str], list[dict]]:
    """(the changed deck, the changes): 0 to `max_changes` random adds and removes, each remove taken from the deck as it stands."""
    deck, changes = list(deck), []
    for _ in range(r.randint(0, max_changes)):
        if r.random() < ADD_SHARE or len(deck) <= 1:
            card = r.choice(REWARD_POOL) + ("+" if r.random() < UPGRADE_SHARE else "")
            deck.append(card)
            changes.append({"op": "add", "card": card})
        else:
            card = deck.pop(r.randrange(len(deck)))
            changes.append({"op": "remove", "card": card})
    return deck, changes


def design(states : list[dict], n : int, per_source : int, seed : int, max_changes : int = MAX_CHANGES) -> list[dict]:
    """`n` variants, `per_source` of each source fight drawn (the same seed gives the same list)."""
    r = random.Random(seed)
    out = []
    while len(out) < n:
        s = r.choice(states)
        for _ in range(per_source):
            if len(out) >= n:
                break
            deck, changes = changes_for(s["before"]["deck"], r, max_changes)
            out.append({"i": len(out), "source": s["source"], "encounter": s["encounter"], "kind": s["kind"], "before": s["before"], "deck": deck, "changes": changes})
    return out


def job(args) -> dict:
    v, sims = args
    game_seed = zlib.crc32(f"variant/{v['source']}".encode())          # every variant of a source meets the same monsters and their dice
    row = {"i": v["i"], "source": v["source"], "encounter": v["encounter"], "kind": v["kind"], "before": dict(v["before"], deck=v["deck"]),
           "base_deck": v["before"]["deck"], "changes": v["changes"], "sims": sims, "mcts": True, "game_seed": game_seed,
           "seed": int(v["source"].split("/")[0])}          # `seed`: the self-play run the fight came from (the fight model holds out by it)
    try:
        result = play(v["before"], v["deck"], v["encounter"], v["kind"], game_seed, sims, f"variant/{v['i']}", aligned=False)
    except Exception as error:          # the engine failed: logged as failed, played again on a resume
        return dict(row, error=f"{type(error).__name__}: {error}"[:300])
    return {**row, "won": result["won"], "dead": not result["won"], "hp_after": result["hp_after"], "turns": result["turns"], "progress": result["progress"]}


def play_all(path : Path, tasks : list, fn, workers : int, done : int = 0):
    """Play `tasks` with `fn` on a pool, appending each result row to `path` as it finishes, with progress every minute."""
    start, last, failed = time.perf_counter(), time.perf_counter(), 0
    with Pool(workers) as pool:
        for k, row in enumerate(pool.imap_unordered(fn, tasks, chunksize=1), 1):
            with gzip.open(path, "at", encoding="utf-8") as f:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
            failed += bool(row.get("error"))
            if time.perf_counter() - last > 60 or k == len(tasks):
                last = time.perf_counter()
                rate = k / (last - start)
                print(f"{done + k}/{done + len(tasks)} fights ({failed} failed)  {rate * 3600:.0f}/h  ~{(len(tasks) - k) / rate / 3600:.1f} h left", flush=True)


def main(argv=None):
    from agents.selfplay.suite import OUT_ROOT
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from", dest="sources", required=True, help="comma separated folders of data/selfplay whose fight logs give the fights to start from")
    p.add_argument("--out", required=True, help="results file data/selfplay/variants/NAME.jsonl.gz")
    p.add_argument("--n", type=int, default=20000, help="variants (fights) in all")
    p.add_argument("--per-source", type=int, default=8, help="variants of each source fight")
    p.add_argument("--max-changes", type=int, default=MAX_CHANGES)
    p.add_argument("--sims", type=int, default=100)
    p.add_argument("--kinds", default="Elite,Boss", help="the kinds of fight to start from (comma separated)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = p.parse_args(argv)

    path = OUT_ROOT / "variants" / f"{args.out}.jsonl.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta_file = path.with_suffix("").with_suffix(".meta.json")
    meta = {"from": args.sources, "per_source": args.per_source, "max_changes": args.max_changes, "sims": args.sims, "kinds": args.kinds, "seed": args.seed}
    if meta_file.exists() and json.loads(meta_file.read_text()) != meta:
        print(f"{meta_file} has other settings ({meta_file.read_text().strip()}): use another --out, or the same settings", file=sys.stderr)
        return 1
    states = source_states(args.sources.split(","), tuple(args.kinds.split(",")))
    if not states:
        print("no fights to start from in those logs", file=sys.stderr)
        return 1
    meta_file.write_text(json.dumps(meta))
    done = {v["i"] for v in read(path) if not v.get("error")}
    todo = [v for v in design(states, args.n, args.per_source, args.seed, args.max_changes) if v["i"] not in done]
    print(f"{path}: {len(states)} fights to start from, {len(done)} variants done, {len(todo)} to play at {args.sims} sims, {args.workers} workers", flush=True)
    play_all(path, [(v, args.sims) for v in todo], job, args.workers, len(done))
    return 0


if __name__ == "__main__":
    sys.exit(main())
