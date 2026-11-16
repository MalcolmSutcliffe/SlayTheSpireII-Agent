"""Does a longer walk make the card chooser see scaling cards?

Each real early-run deck is walked through a whole act (and `lookahead_rooms` rooms of the next one) with and without one card, on the same walks, for several
`lookahead_rooms`. The gain is in rooms of progress (route_sim). Scaling cards (Powers that grow with the fight) are compared with ordinary cards.
If scaling cards gain more as the lookahead grows, the horizon was hiding them; if they do not, the walk's fights are not what is missing.

Usage (from scripts/):
  python -m benchmarks.lookahead_check --decks 8 --walks 24 --lookaheads 3,8,16 --workers 4 [--cards DEMON_FORM,INFLAME,...] [--act 1]
"""
from __future__ import annotations
import argparse
import json
import math
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

DECKS_FILE = Path(__file__).resolve().parent / "results" / "real_decks.json"
SCALING = ["DEMON_FORM", "INFLAME", "BARRICADE", "DARK_EMBRACE", "FEEL_NO_PAIN", "JUGGERNAUT", "RUPTURE", "CRUELTY"]
CONTROL = ["SHRUG_IT_OFF", "POMMEL_STRIKE", "IRON_WAVE", "TRUE_GRIT", "HEADBUTT", "THUNDERCLAP"]


def pick_decks(n : int, act : int, seed : int, latest : bool = True) -> list[dict]:
    """One deck state per run: its latest in the act by default (a deck strong enough for the walk to clear the act, so the lookahead is played at all)."""
    states = [s for s in json.loads(DECKS_FILE.read_text()) if s["act"] == act]
    by_run = {}
    for s in sorted(states, key=lambda s: s["floor"], reverse=latest):
        by_run.setdefault(s["run"], s)
    runs = sorted(by_run)
    random.Random(seed).shuffle(runs)
    return [by_run[r] for r in runs[:n]]


def job(args):
    state, card, lookahead, walks_n, seed = args
    from agents.deck_eval.config import DeckEvalConfig
    from agents.deck_eval.evaluator import DeckEvaluator
    from agents.deck_eval.fight_pool import load_pool, target_types
    from agents.deck_eval.route_sim import sample_walks
    from agents.deck_eval.advisor import paired_gain
    pool = load_pool()
    cfg = DeckEvalConfig().tuned(lookahead_rooms=lookahead)
    ev = DeckEvaluator(pool, target_types(pool), config=cfg)
    player, act = state["player"], state["act"]
    walks = sample_walks(None, act, state.get("ascension") or 0, walks_n, seed, state["floor"])
    base = ev.score_walks(player["deck"], player, walks)
    start = time.perf_counter()
    from agents.deck_eval.future_cards import CARD_POOL
    entry = next(c for cards in CARD_POOL.values() for c in cards if c["id"] == card)
    score = ev.score_walks(player["deck"] + [dict(entry)], player, walks)
    gain, se = paired_gain(score.rewards, base.rewards)
    return {"run": state["run"], "card": card, "lookahead": lookahead, "gain": gain, "se": se, "base": base.mean, "clear": score.win_rate, "seconds": base.seconds + (time.perf_counter() - start)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--decks", type=int, default=8)
    p.add_argument("--walks", type=int, default=24)
    p.add_argument("--lookaheads", default="3,8,16")
    p.add_argument("--cards", help="comma separated card ids (default: the scaling and control sets)")
    p.add_argument("--act", type=int, default=1)
    p.add_argument("--earliest", action="store_true", help="use each run's earliest deck of the act instead of its latest")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    cards = args.cards.split(",") if args.cards else SCALING + CONTROL
    looks = [int(x) for x in args.lookaheads.split(",")]
    decks = pick_decks(args.decks, args.act, args.seed, not args.earliest)
    jobs = [(d, c, L, args.walks, args.seed * 977 + i) for i, d in enumerate(decks) for c in cards for L in looks]
    print(f"{len(decks)} decks x {len(cards)} cards x lookaheads {looks} = {len(jobs)} jobs of {args.walks} walks")
    start = time.perf_counter()
    with Pool(args.workers) as pool:
        rows = pool.map(job, jobs, chunksize=1)
    print(f"{time.perf_counter() - start:.0f}s")
    print("\ncard gain over the deck as it is, in rooms of progress (mean over decks, ± standard error across decks)")
    print("%-14s %-8s" % ("card", "kind") + "".join("  L=%-12d" % L for L in looks))
    for c in cards:
        out = []
        for L in looks:
            g = [r["gain"] for r in rows if r["card"] == c and r["lookahead"] == L]
            m = sum(g) / len(g)
            se = math.sqrt(sum((x - m) ** 2 for x in g) / max(1, len(g) - 1) / len(g))
            out.append("%+6.2f ± %-5.2f" % (m, se))
        print("%-14s %-8s" % (c, "scaling" if c in SCALING else "control") + "  " + "  ".join(out))
    for L in looks:
        print("lookahead %2d: %.0f%% of the walks clear the act" % (L, 100 * sum(r["clear"] for r in rows if r["lookahead"] == L) / sum(1 for r in rows if r["lookahead"] == L)))
    for L in looks:
        t = [r["seconds"] for r in rows if r["lookahead"] == L]
        print("lookahead %2d: %.1fs per job (2 decks x %d walks)" % (L, sum(t) / len(t), args.walks))


if __name__ == "__main__":
    main()
