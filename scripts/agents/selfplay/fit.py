"""Fit the value model on self-play logs and say how well it does.

  python -m agents.selfplay.fit --runs v0_random,v0_rarity --out v0 [--model ridge|mlp|both] [--lam 0.8 --iters 3] [--cards-check]

Held out: the runs whose seed is divisible by 5 (a run's rows all go to one side).

Targets: first the plain outcome (the rooms the run still cleared from each state, uncapped unless --horizon), then `--iters` rounds of fitted TD(lambda):
each round the targets are rebuilt from the previous round's model (value_model.td_targets) and the model is refitted. Every round is scored on the held-out
runs against their plain outcome, which is an unbiased (if noisy) sample of the true value, so the rounds compare fairly: a higher R^2 is a better value model. `--cards-check` prints what the model thinks a card adds to real early decks, the
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
from agents.selfplay.value_model import MLP, POSITION_NAMES, Ridge, Rows, ValueModel, Vocab, featurize, pilot_is_mcts, td_targets

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
            "potions": [str(p.get("id")) for p in player.get("potions", []) if p], "reward": True}


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
    p.add_argument("--horizon", type=int, default=None, help="cap the plain targets at this many rooms (default: no cap)")
    p.add_argument("--lam", type=float, default=0.8, help="TD(lambda): 1 is the plain outcome, lower leans on the model's own value of the next states")
    p.add_argument("--gamma", type=float, default=1.0, help="discount per state (1: a room late in the run counts as much as one now)")
    p.add_argument("--iters", type=int, default=3, help="rounds of fitted TD(lambda) after the plain fit (0: the plain fit only)")
    p.add_argument("--cards-check", action="store_true")
    args = p.parse_args(argv)

    runs = load_runs(args.runs.split(","))
    train, val = Rows([r for r in runs if r["seed"] % 5]), Rows([r for r in runs if r["seed"] % 5 == 0])
    y, vy = train.mc(args.horizon, args.gamma), val.mc(None, args.gamma)
    vocab = Vocab.build(train.snaps, args.min_count)
    X, Xv = featurize(train.snaps, vocab), featurize(val.snaps, vocab)
    after = sum(bool(s.get("reward")) for s in train.snaps)
    print(f"{len(set(train.episode))} train runs ({len(train)} states, {after} of them after a card reward), {len(set(val.episode))} held-out runs ({len(val)} states) | "
          f"{vocab.size} features: {len(vocab.cards)} cards, {len(vocab.relics)} relics, {len(vocab.bosses)} bosses | "
          f"target: rooms still cleared{f', capped at {args.horizon}' if args.horizon else ''}, mean {y.mean():.2f}")
    if not after:
        print("  (no after-reward states: these logs were played before they were recorded; play new runs to train on the decks the chooser compares)")
    base = float(vy.mean())
    mcts = np.array([pilot_is_mcts(s) for s in val.snaps])
    pilots = sorted({r.get("pilot", "rollout") for r in runs})
    def score(pred) -> str:
        """R^2 on every held-out state, and on the MCTS-piloted runs' alone (what the agent's card choices are judged on) when there are both."""
        out = f"{r2(vy, pred, base):6.3f}"
        if mcts.any() and not mcts.all():
            out += f"   mcts runs {r2(vy[mcts], pred[mcts], float(vy[mcts].mean())):6.3f}"
        return out
    print(f"\npilots: {', '.join(pilots)} | held-out MCTS-piloted states: {int(mcts.sum())} of {len(mcts)}")
    print(f"held-out R^2 against the runs' outcome (1 = perfect, 0 = no better than the mean; outcome spread {float(vy.std()):.2f} rooms)")
    npos = len(POSITION_NAMES)
    pos = Ridge(10.0).fit(X[:, :npos], y)
    print(f"  position only (act, floor, ascension, HP, gold, deck size)   {score(pos.predict(Xv[:, :npos]))}")
    makers = {"ridge": lambda: Ridge(3000.0), "mlp": lambda: MLP(hidden=(32,), weight_decay=1e-3, lr=3e-4, epochs=args.epochs, patience=3)}
    fitted = {}
    for name in (("ridge", "mlp") if args.model == "both" else (args.model,)):
        start = time.perf_counter()
        model = makers[name]().fit(X, y, Xv, vy)
        print(f"  {name:5s} plain outcome                                    {score(model.predict(Xv))}   ({time.perf_counter() - start:.1f}s)")
        for it in range(args.iters):
            start = time.perf_counter()
            targets = td_targets(train, model.predict(X), args.lam, args.gamma)
            # the held-out runs' TD targets steer the MLP's early stopping; the score stays the plain outcome
            model = makers[name]().fit(X, targets, Xv, td_targets(val, model.predict(Xv), args.lam, args.gamma))
            print(f"  {name:5s} TD(lambda={args.lam:g}) round {it + 1}                           {score(model.predict(Xv))}   ({time.perf_counter() - start:.1f}s)")
        fitted[name] = model
    models = {name: ValueModel(vocab, m) for name, m in fitted.items()}
    if "ridge" in fitted:
        w = fitted["ridge"].w[:-1] / 1.0
        names = vocab.names()
        order = np.argsort(-np.abs(w))
        print("\nlargest ridge weights (per standard deviation of the feature; rooms)")
        for j in order[:14]:
            print(f"  {names[j]:34s} {w[j]:+.2f}")
        delta = [j for j in order if names[j].startswith("mcts_card:")][:12]
        if mcts.any() and delta:
            print("\ncards the MCTS-piloted runs value differently (ridge weight of the card under the MCTS on top of its weight for both pilots; rooms)")
            for j in delta:
                card = names[j].split(":", 1)[1]
                print(f"  {card:26s} {w[j]:+.2f}   (both pilots {w[names.index('card:' + card)]:+.2f})")
    if args.out:
        for name, model in models.items():
            model.save(OUT_ROOT / "models" / args.out / name)
        print(f"\nsaved to {OUT_ROOT / 'models' / args.out}")
    if args.cards_check and models:
        cards_check(models)
    return 0


if __name__ == "__main__":
    sys.exit(main())
