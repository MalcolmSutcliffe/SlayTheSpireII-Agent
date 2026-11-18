"""A card-pick model distilled from the walks: it predicts what the walks would rate a card's gain over skipping (rooms), from the run's snapshot and the card.

  python -m agents.selfplay.pick_model --runs walk0 --out walk0 [--model ridge|mlp|both] [--min-count 20]

The training rows are the offered cards of the walk-labeled runs (label.py): one row per card, its target the walk gain without the kind bonus (`gain`), weighted by
1 / (se^2 + tau^2) (tau: the median se), so a card the walks rated precisely counts more. The features are the snapshot's (value_model.featurize), the change the card
makes to them (the snapshot with the card added, minus without), and which card it is (a column per card of the vocab, and whether it is upgraded).

Held out: the runs whose seed is divisible by 5. The report:
  - R^2 of the predicted gains against the walk gains (weighted), next to the most the walks' own noise leaves room for (`ceiling`);
  - per reward screen, the walk value of the pick (the label gain + kind bonus of the card taken; 0 for a skip), averaged: higher is better. Since the
    labels' noise is independent of a held-out model's picks, this compares choosers fairly. Next to the model: the walks' own pick (`teacher`, its caution
    costs it some), the rarest card, a random card, always skipping, and the best pick by the labels (an upper bound: it is chosen on the noise too);
  - agreement with the teacher's pick.
The chooser takes the best card when its predicted gain plus kind bonus is above `margin` (rooms), else skips; the margin is the one with the best pick value on
the training screens, and is saved with the model. `choosers.make_chooser("pick:NAME[:MARGIN]")` uses it."""
from __future__ import annotations
import argparse
import functools
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agents.deck_eval.cards import RARITY_RANK
from agents.deck_eval.card_reward_chooser import kind_bonus
from agents.deck_eval.config import DEFAULT, DeckEvalConfig
from agents.selfplay.choosers import base_id, card_key
from agents.selfplay.value_model import MLP, Ridge, Vocab, featurize

MARGINS = np.round(np.arange(-1.0, 4.01, 0.1), 2)


def screens_of(runs) -> list[dict]:
    """Every walk-labeled reward screen of `runs`: {seed, snap, labels, teacher, needed, early} (the snapshot is the one the screen was rated on)."""
    out = []
    for run in runs:
        for pick in run.get("picks", []):
            if "labels" in pick and pick["labels"]:
                out.append({"seed": run["seed"], "snap": pick["snap"], "labels": pick["labels"], "teacher": pick["teacher"], "needed": pick["needed"], "early": pick["early"]})
    return out


def features(snaps : list[dict], keys : list[str], vocab : Vocab) -> np.ndarray:
    """One row per (snapshot, card key): the snapshot's features, the change adding the card makes to them, a one-hot of the card and its upgrade."""
    before = featurize(snaps, vocab)
    after = featurize([dict(s, deck=s["deck"] + [k]) for s, k in zip(snaps, keys)], vocab)
    which = np.zeros((len(keys), len(vocab.cards) + 1), dtype=np.float32)
    for i, k in enumerate(keys):
        j = vocab.card_at.get(base_id(k))
        if j is not None:
            which[i, j] = 1.0
        which[i, -1] = float(k.endswith("+"))
    return np.hstack([before, after - before, which])


def card_rows(screens : list[dict]):
    """(snaps, keys, gains, ses, screen index) of every offered card of `screens`."""
    snaps, keys, gains, ses, at = [], [], [], [], []
    for i, s in enumerate(screens):
        for c in s["labels"]:
            snaps.append(s["snap"]); keys.append(c["key"]); gains.append(c["gain"]); ses.append(c["se"]); at.append(i)
    return snaps, keys, np.array(gains, dtype=np.float32), np.array(ses, dtype=np.float32), np.array(at)


@functools.lru_cache(maxsize=4096)
def _entry(key : str) -> dict:
    """A deck entry (type, rarity) for a card key, for the kind bonus; a card the tables do not know is an entry without them (no bonus)."""
    from sts2_lite.event.run import card_entry
    try:
        return card_entry(base_id(key), key.endswith("+"))
    except Exception:
        return {"id": base_id(key)}


def bonuses(snap : dict, offered : list[dict], config : DeckEvalConfig = DEFAULT) -> list[float]:
    deck = [_entry(k) for k in snap["deck"]]
    return [kind_bonus(c, deck, config) for c in offered]


class PickModel:
    def __init__(self, vocab : Vocab, model, margin : float = 0.0):
        self.vocab, self.model, self.margin = vocab, model, margin

    def gains(self, snap : dict, keys : list[str]) -> np.ndarray:
        """The predicted walk gain (rooms, without the kind bonus) of each card key over skipping."""
        return self.model.predict(features([snap] * len(keys), keys, self.vocab))

    def save(self, folder : Path):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "vocab.json").write_text(json.dumps(self.vocab.to_json()))
        (folder / "meta.json").write_text(json.dumps({"kind": "pick", "margin": self.margin}))
        np.savez(folder / "model.npz", **self.model.state())

    @classmethod
    def load(cls, folder : Path) -> "PickModel":
        vocab = Vocab.from_json(json.loads((folder / "vocab.json").read_text()))
        st = dict(np.load(folder / "model.npz", allow_pickle=True))
        meta = json.loads((folder / "meta.json").read_text())
        return cls(vocab, (MLP if str(st["kind"]) == "mlp" else Ridge).from_state(st), meta["margin"])


class PickChooser:
    """A CardChooser from a PickModel: a card scores its predicted gain plus its kind bonus; skipping scores the margin."""
    def __init__(self, model : PickModel, margin : float | None = None, config : DeckEvalConfig = DEFAULT):
        self.model, self.config = model, config
        self.margin = model.margin if margin is None else margin

    def scores(self, snap, offered):
        keys = [card_key(c) for c in offered]
        g = self.model.gains(snap, keys)
        return [float(x + b) for x, b in zip(g, bonuses(snap, offered, self.config))] + [self.margin]


def pick_values(screens : list[dict], pred : np.ndarray, at : np.ndarray, margin : float) -> tuple[np.ndarray, np.ndarray]:
    """(walk value of the pick, the pick's index; len(labels) = skip) on each screen, picking by `pred` (a predicted gain per card row) plus the kind bonus."""
    values, picks = np.zeros(len(screens)), np.zeros(len(screens), dtype=int)
    start = 0
    for i, s in enumerate(screens):
        n = len(s["labels"])
        p = pred[start:start + n] + np.array([c["bonus"] for c in s["labels"]])
        start += n
        j = int(np.argmax(p))
        if p[j] > margin:
            values[i], picks[i] = s["labels"][j]["gain"] + s["labels"][j]["bonus"], j
        else:
            values[i], picks[i] = 0.0, n
    return values, picks


def baselines(screens : list[dict], seed : int = 0) -> dict[str, np.ndarray]:
    """Walk value of the pick on each screen for the reference choosers."""
    r = random.Random(seed)
    total = lambda c: c["gain"] + c["bonus"]
    out = {"teacher (on its labels)": [], "rarest card": [], "random card": [], "always skip": [], "best by labels": []}
    for s in screens:
        labels = s["labels"]
        out["teacher (on its labels)"].append(0.0 if s["teacher"] == len(labels) else total(labels[s["teacher"]]))
        top = max(RARITY_RANK.get(c["rarity"], 0) for c in labels)
        out["rarest card"].append(total(r.choice([c for c in labels if RARITY_RANK.get(c["rarity"], 0) == top])))
        out["random card"].append(total(r.choice(labels)))
        out["always skip"].append(0.0)
        out["best by labels"].append(max(0.0, max(total(c) for c in labels)))
    return {k: np.array(v) for k, v in out.items()}


def wr2(y, p, w) -> float:
    m = np.average(y, weights=w)
    return 1.0 - float(np.average((y - p) ** 2, weights=w)) / float(np.average((y - m) ** 2, weights=w))


def main(argv=None):
    from agents.selfplay.fit import load_runs
    from agents.selfplay.suite import OUT_ROOT
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", required=True, help="comma separated folders of data/selfplay with walk-labeled runs (label.py)")
    p.add_argument("--out", help="save the models in data/selfplay/models/NAME/{ridge,mlp}")
    p.add_argument("--model", default="both", choices=("ridge", "mlp", "both"))
    p.add_argument("--min-count", type=int, default=20, help="a card, relic or boss needs this many screens to get its own column")
    p.add_argument("--epochs", type=int, default=60)
    args = p.parse_args(argv)

    screens = screens_of(load_runs(args.runs.split(",")))
    train = [s for s in screens if s["seed"] % 5]
    val = [s for s in screens if s["seed"] % 5 == 0]
    if not train or not val:
        print(f"{len(screens)} labeled screens: not enough for a train / held-out split", file=sys.stderr)
        return 1
    vocab = Vocab.build([s["snap"] for s in train], args.min_count)
    ts, tk, ty, tse, tat = card_rows(train)
    vs, vk, vy, vse, vat = card_rows(val)
    tau2 = float(np.median(tse)) ** 2
    tw, vw = 1.0 / (tse ** 2 + tau2), 1.0 / (vse ** 2 + tau2)
    X, Xv = features(ts, tk, vocab), features(vs, vk, vocab)
    ceiling = 1.0 - float(np.average(vse ** 2, weights=vw)) / float(np.average((vy - np.average(vy, weights=vw)) ** 2, weights=vw))
    print(f"{len(train)} train screens ({len(ty)} cards), {len(val)} held-out screens ({len(vy)} cards) | {X.shape[1]} features | walk gain mean {ty.mean():+.2f}, "
          f"spread {ty.std():.2f}, median se {np.median(tse):.2f} rooms")
    print(f"\nheld-out R^2 of the predicted walk gains (weighted; the walks' own noise caps it near {ceiling:.2f})")
    makers = {"ridge": lambda: Ridge(300.0), "mlp": lambda: MLP(hidden=(64, 32), weight_decay=1e-3, lr=3e-4, epochs=args.epochs, patience=5)}
    fitted = {}
    for name in (("ridge", "mlp") if args.model == "both" else (args.model,)):
        start = time.perf_counter()
        model = makers[name]().fit(X, ty, Xv, vy, tw, vw)
        pv = model.predict(Xv)
        train_value = [pick_values(train, model.predict(X), tat, m)[0].mean() for m in MARGINS]
        margin = float(MARGINS[int(np.argmax(train_value))])
        fitted[name] = (model, margin, pv)
        print(f"  {name:5s} {wr2(vy, pv, vw):6.3f}   margin {margin:+.1f} rooms (best on the training screens)   ({time.perf_counter() - start:.1f}s)")

    print("\nheld-out walk value of the pick per screen (rooms; label gain + kind bonus, 0 for a skip; ± standard error) | skips | agrees with the teacher")
    teacher = np.array([s["teacher"] for s in val])
    rows = {}
    for name, (model, margin, pv) in fitted.items():
        values, picks = pick_values(val, pv, vat, margin)
        rows[f"pick model ({name})"] = (values, float(np.mean(picks == np.array([len(s["labels"]) for s in val]))), float(np.mean(picks == teacher)))
    for name, values in baselines(val).items():
        skips = {"always skip": 1.0, "teacher (on its labels)": float(np.mean(teacher == np.array([len(s["labels"]) for s in val])))}.get(name, 0.0)
        rows[name] = (values, skips, None)
    for name, (values, skips, agree) in rows.items():
        se = values.std() / np.sqrt(len(values))
        print(f"  {name:24s} {values.mean():+6.3f} ± {se:.3f}   {100 * skips:4.0f}%   {'' if agree is None else f'{100 * agree:.0f}%'}")

    if args.out:
        for name, (model, margin, _) in fitted.items():
            PickModel(vocab, model, margin).save(OUT_ROOT / "models" / args.out / name)
        print(f"\nsaved to {OUT_ROOT / 'models' / args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
