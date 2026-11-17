"""Fit the value model on self-play logs and say how well it does.

  python -m agents.selfplay.fit --runs v0_random,v0_rarity --out v0 [--model ridge|mlp|both] [--cards-check]

Held out: the runs whose seed is divisible by 5 (a room's rows all go to one side). `--cards-check` prints what the model thinks a card adds to real early decks, the
test the walks were run through (benchmarks/lookahead_check.py), to compare by eye."""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agents.selfplay.suite import OUT_ROOT, read_runs
from agents.selfplay.value_model import HORIZON, MLP, POSITION_NAMES, Ridge, ValueModel, Vocab, featurize, rows_of

SCALING = ["DEMON_FORM", "INFLAME", "BARRICADE", "DARK_EMBRACE", "FEEL_NO_PAIN", "JUGGERNAUT", "RUPTURE", "CRUELTY"]
CONTROL = ["SHRUG_IT_OFF", "POMMEL_STRIKE", "IRON_WAVE", "TRUE_GRIT", "HEADBUTT", "THUNDERCLAP"]
DECKS_FILE = SCRIPTS_DIR / "benchmarks" / "results" / "real_decks.json"


def r2(y, p, base):
    return 1.0 - float(np.mean((y - p) ** 2)) / float(np.mean((y - base) ** 2))


def load_runs(names : list[str]) -> list[dict]:
    runs = []
    for name in names:
        runs += list(read_runs(OUT_ROOT / name / "runs.jsonl.gz"))
    return runs


def snapshot_of_real(state : dict, boss : str | None) -> dict:
    player = state["player"]
    return {"act": state["act"], "floor": state["floor"], "ascension": state.get("ascension") or 0, "boss": boss, "hp": player["hp"], "max_hp": player["max_hp"],
            "gold": player.get("gold", 0), "deck": [c["id"] + ("+" if c.get("is_upgraded") else "") for c in player["deck"]], "relics": [str(r.get("id")) for r in player["relics"]],
            "potions": [str(p.get("id")) for p in player.get("potions", []) if p]}


def cards_check(models : dict[str, ValueModel], n_decks : int = 40):
    """Mean gain of each card over real act-1 decks (each run's latest act-1 state), averaged over the bosses the training data had."""
    states = [s for s in json.loads(DECKS_FILE.read_text()) if s["act"] == 1]
    by_run = {}
    for s in sorted(states, key=lambda s: s["floor"], reverse=True):
        by_run.setdefault(s["run"], s)
    decks = list(by_run.values())[:n_decks]
    print(f"\ngain of a card over {len(decks)} real late-act-1 decks, in rooms (averaged over the bosses; ± standard error across decks)")
    print("%-14s %-8s" % ("card", "kind") + "".join("  %-14s" % n for n in models))
    for card in SCALING + CONTROL:
        out = []
        for model in models.values():
            gains = []
            for s in decks:
                g = [model.gains(snapshot_of_real(s, boss), [card])[0] for boss in model.vocab.bosses]
                gains.append(sum(g) / len(g))
            m = sum(gains) / len(gains)
            se = (sum((x - m) ** 2 for x in gains) / max(1, len(gains) - 1) / len(gains)) ** 0.5
            out.append("%+5.2f ± %-5.2f" % (m, se))
        print("%-14s %-8s" % (card, "scaling" if card in SCALING else "control") + "  " + "  ".join("%-14s" % o for o in out))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", required=True, help="comma separated folders of data/selfplay")
    p.add_argument("--out", help="save the models in data/selfplay/models/NAME")
    p.add_argument("--model", default="both", choices=("ridge", "mlp", "both"))
    p.add_argument("--min-count", type=int, default=40, help="a card, relic or boss needs this many rooms to get its own column")
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--cards-check", action="store_true")
    args = p.parse_args(argv)

    runs = load_runs(args.runs.split(","))
    train_runs, val_runs = [r for r in runs if r["seed"] % 5], [r for r in runs if r["seed"] % 5 == 0]
    snaps, y, _ = rows_of(train_runs)
    vsnaps, vy, _ = rows_of(val_runs)
    vocab = Vocab.build(snaps, args.min_count)
    X, Xv = featurize(snaps, vocab), featurize(vsnaps, vocab)
    print(f"{len(train_runs)} train runs ({len(snaps)} rooms), {len(val_runs)} held-out runs ({len(vsnaps)} rooms) | {vocab.size} features: {len(vocab.cards)} cards, "
          f"{len(vocab.relics)} relics, {len(vocab.bosses)} bosses | target: rooms still cleared, capped at {HORIZON}, mean {y.mean():.2f}")
    base = float(y.mean())
    print(f"\nheld-out R^2 (1 = perfect, 0 = no better than the mean; target spread {float(vy.std()):.2f} rooms)")
    fitted = {}
    npos = len(POSITION_NAMES)
    pos = Ridge(10.0).fit(X[:, :npos], y)
    print(f"  position only (act, floor, ascension, HP, gold, deck size)   {r2(vy, pos.predict(Xv[:, :npos]), base):6.3f}")
    if args.model in ("ridge", "both"):
        start = time.perf_counter()
        fitted["ridge"] = ridge = Ridge(3000.0).fit(X, y)
        print(f"  ridge, everything                                          {r2(vy, ridge.predict(Xv), base):6.3f}   ({time.perf_counter() - start:.1f}s)")
    if args.model in ("mlp", "both"):
        start = time.perf_counter()
        fitted["mlp"] = mlp = MLP(hidden=(32,), weight_decay=1e-3, lr=3e-4, epochs=args.epochs, patience=3).fit(X, y, Xv, vy)
        print(f"  MLP, everything                                            {r2(vy, mlp.predict(Xv), base):6.3f}   ({time.perf_counter() - start:.0f}s)")
    models = {name: ValueModel(vocab, m) for name, m in fitted.items()}
    if "ridge" in fitted:
        w = fitted["ridge"].w[:-1] / 1.0
        names = vocab.names()
        order = np.argsort(-np.abs(w))
        print("\nlargest ridge weights (per standard deviation of the feature; rooms)")
        for j in order[:14]:
            print(f"  {names[j]:34s} {w[j]:+.2f}")
    if args.out:
        for name, model in models.items():
            model.save(OUT_ROOT / "models" / args.out / name)
        print(f"\nsaved to {OUT_ROOT / 'models' / args.out}")
    if args.cards_check and models:
        cards_check(models)
    return 0


if __name__ == "__main__":
    sys.exit(main())
