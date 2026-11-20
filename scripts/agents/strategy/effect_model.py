"""A card-effect model: how much one card changes what a fight costs the MCTS, learned from the paired fight experiments (experiments.py).

  python -m agents.strategy.effect_model --runs exp_m100 --out m100 [--min-count 10]

Each experiment is a fight played with a deck and with one card more (or less), on the same seeds; its effect is the mean over its reps of
`alt score - base score` (HP; negative: the change helps; `score`: the HP a fight took, a lost one graded by the enemy HP still standing; --score cost: all its HP). The rows are the experiments; the features are the fight's (fight_model.featurize: the run going in,
the encounter and kind, the deck, relics and potions) plus the change the card makes to them (with minus without), so the model learns a card's effect on
this fight for this deck.

The report:
  - how much the fights show of an effect over their own luck: the correlation of one rep's effect with another's, and from it the most of the effects'
    spread any model could explain (the `ceiling` on R^2, for the mean of the reps);
  - held-out R^2 (by the run the fight came from) for: the mean effect of the card alone (`card only`), and the ridge and MLP models of the card in its fight;
  - the observed effect of each card on the elite and boss fights (the experiments are randomized, so these means are the cards' effects under the MCTS,
    without the links between cards and the runs that hold them), next to the model's."""
from __future__ import annotations
import argparse
import json
import sys
import time
import zlib
from collections import defaultdict
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agents.selfplay.choosers import base_id
from agents.selfplay.value_model import MLP, Ridge
from agents.strategy.experiments import apply, read
from agents.strategy.fight_model import Vocab, featurize


def usable(experiments) -> list[dict]:
    """The experiments that played (no engine failure) with at least one rep."""
    return [e for e in experiments if not e.get("error") and e.get("reps")]


SCORE = "graded"            # "cost" or "graded" (see score)


def score(result : dict, hp0 : float, how : str | None = None) -> float:
    """A fight's result in HP. "cost": the HP it took, all of it when lost. "graded" (the default): a lost fight also counts the share of the enemies' HP still
    standing, times the HP it began with (a wipe costs up to twice a near win), so a loss is not one flat number whatever happened."""
    how = how or SCORE
    if how == "cost" or result.get("won", True):
        return result["cost"]
    left = 1.0 - (result.get("progress") or 0.0)
    return result["cost"] + left * hp0


def effects(exp : dict) -> list[float]:
    """The effect of the change in each rep: alt score - base score (HP; see score)."""
    hp0 = exp["before"]["hp"]
    return [score(r["alt"], hp0) - score(r["base"], hp0) for r in exp["reps"]]


def effect(exp : dict) -> float:
    e = effects(exp)
    return sum(e) / len(e)


def held_out(exp : dict) -> bool:
    """The held-out fifth: by the run the fight came from (the source's first field is the run's seed), so a run's fights all go to one side."""
    return zlib.crc32(exp["source"].split("/")[0].encode()) % 5 == 0


def as_fight(exp : dict, deck : list[str]) -> dict:
    return {"encounter": exp["encounter"], "kind": exp["kind"], "before": dict(exp["before"], deck=deck)}


def features(exps : list[dict], vocab : Vocab) -> np.ndarray:
    base = featurize([as_fight(e, e["before"]["deck"]) for e in exps], vocab)
    alt = featurize([as_fight(e, apply(e["before"]["deck"], e["change"])) for e in exps], vocab)
    return np.hstack([base, alt - base])


def card_columns(exps : list[dict], vocab : Vocab) -> np.ndarray:
    """The change alone: +1 / -1 in the changed card's column (and its upgrade's), for the `card only` baseline."""
    X = np.zeros((len(exps), 2 * len(vocab.cards) + 1), dtype=np.float32)
    for i, e in enumerate(exps):
        sign = 1.0 if e["change"]["op"] == "add" else -1.0
        key = e["change"]["card"]
        j = vocab.card_at.get(base_id(key))
        if j is not None:
            X[i, j] = sign
            if key.endswith("+"):
                X[i, len(vocab.cards) + j] = sign
        X[i, -1] = sign
    return X


def reliability(exps : list[dict]) -> tuple[float, float, int]:
    """(correlation of rep 0's effect with rep 1's, the share of the spread of the reps' mean that is not luck, experiments with 2+ reps)."""
    pairs = np.array([effects(e)[:2] for e in exps if len(e["reps"]) >= 2])
    if len(pairs) < 10:
        return float("nan"), float("nan"), len(pairs)
    r = float(np.corrcoef(pairs[:, 0], pairs[:, 1])[0, 1])
    reps = np.mean([len(e["reps"]) for e in exps])
    return r, (reps * r / (1 + (reps - 1) * r)) if r > 0 else 0.0, len(pairs)


def r2(y, p) -> float:
    return 1.0 - float(np.mean((y - p) ** 2)) / float(np.mean((y - y.mean()) ** 2))


class EffectModel:
    def __init__(self, vocab : Vocab, model):
        self.vocab, self.model = vocab, model

    def predict(self, exps : list[dict]) -> np.ndarray:
        """The predicted effect (HP of the fight's cost; negative: the change helps) of each {before, encounter, kind, change}."""
        return self.model.predict(features(exps, self.vocab))

    def save(self, folder : Path):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "vocab.json").write_text(json.dumps(self.vocab.to_json()))
        np.savez(folder / "model.npz", **self.model.state())

    @classmethod
    def load(cls, folder : Path) -> "EffectModel":
        st = dict(np.load(folder / "model.npz", allow_pickle=True))
        return cls(Vocab.from_json(json.loads((folder / "vocab.json").read_text())), (MLP if str(st["kind"]) == "mlp" else Ridge).from_state(st))


def card_table(exps : list[dict], pred : np.ndarray | None, kinds=("Elite", "Boss"), min_n : int = 8, top : int = 15):
    """The observed mean effect of adding each card on fights of `kinds` (± standard error), with the model's mean prediction on the same experiments."""
    rows = defaultdict(list)
    for k, e in enumerate(exps):
        if e["kind"] in kinds and e["change"]["op"] == "add":
            rows[base_id(e["change"]["card"])].append((effect(e), None if pred is None else float(pred[k])))
    table = []
    for card, v in rows.items():
        if len(v) >= min_n:
            obs = np.array([x for x, _ in v])
            table.append((obs.mean(), obs.std(ddof=1) / np.sqrt(len(obs)), None if pred is None else float(np.mean([p for _, p in v])), len(v), card))
    table.sort()
    print(f"\nadding a card to an {'/'.join(kinds)} fight: observed mean effect on its cost (HP; negative helps) ± standard error, and the model's mean, by card "
          f"(at least {min_n} experiments; the {top} that help most, then the {top} that help least)")
    shown = table[:top] + ([None] if len(table) > 2 * top else []) + table[-top:] if len(table) > 2 * top else table
    for row in shown:
        if row is None:
            print("  ...")
            continue
        m, se, p, n, card = row
        print(f"  {card:22s} n={n:4d}  observed {m:+6.2f} ± {se:4.2f}" + ("" if p is None else f"   model {p:+6.2f}"))


def main(argv=None):
    from agents.selfplay.suite import OUT_ROOT
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", required=True, help="comma separated experiment files (data/selfplay/experiments/NAME.jsonl.gz, by NAME)")
    p.add_argument("--out", help="save the MLP in data/selfplay/models/effect/NAME")
    p.add_argument("--min-count", type=int, default=10)
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--score", default="graded", choices=("graded", "cost"), help="how a fight's result is counted (see score)")
    p.add_argument("--kinds", default="Monster,Elite,Boss", help="the kinds of fight to use (comma separated)")
    args = p.parse_args(argv)
    global SCORE
    SCORE = args.score

    exps = [e for e in usable([e for name in args.runs.split(",") for e in read(OUT_ROOT / "experiments" / f"{name}.jsonl.gz")]) if e["kind"] in args.kinds.split(",")]
    train, val = [e for e in exps if not held_out(e)], [e for e in exps if held_out(e)]
    if len(train) < 50 or len(val) < 20:
        print(f"{len(exps)} experiments: not enough to fit and hold out", file=sys.stderr)
        return 1
    y, vy = np.array([effect(e) for e in train], dtype=np.float32), np.array([effect(e) for e in val], dtype=np.float32)
    r, ceiling, npairs = reliability(exps)
    adds = sum(e["change"]["op"] == "add" for e in exps)
    print(f"{len(train)} train experiments, {len(val)} held out ({adds} add a card, {len(exps) - adds} remove one) | effect: mean {y.mean():+.2f}, spread {y.std():.2f} HP")
    print(f"one rep's effect against another's (over {npairs} experiments): r = {r:.3f}, so at most ~{ceiling:.2f} of the effects' spread is the card, the rest the fights' luck")
    for kind in ("Monster", "Elite", "Boss"):
        kr, _, kn = reliability([e for e in exps if e["kind"] == kind])
        if kn >= 10:
            print(f"  {kind:8s} r = {kr:+.3f} over {kn} experiments")

    vocab = Vocab.build([as_fight(e, apply(e["before"]["deck"], e["change"])) for e in train], args.min_count)
    print(f"\nheld-out R^2 of the effect (ceiling ~{ceiling:.2f})")
    cards_only = Ridge(10.0).fit(card_columns(train, vocab), y)
    print(f"  {'card only (its mean effect)':30s} {r2(vy, cards_only.predict(card_columns(val, vocab))):6.3f}")
    X, Xv = features(train, vocab), features(val, vocab)
    fitted = {}
    for name, make in (("ridge", lambda: Ridge(300.0)), ("mlp", lambda: MLP(hidden=(64, 32), weight_decay=1e-3, lr=3e-4, epochs=args.epochs, patience=6))):
        start = time.perf_counter()
        model = make().fit(X, y, Xv, vy)
        fitted[name] = model
        print(f"  {name:30s} {r2(vy, model.predict(Xv)):6.3f}   ({time.perf_counter() - start:.1f}s)")
    best = EffectModel(vocab, fitted["mlp"])
    card_table(exps, best.predict(exps))
    if args.out:
        best.save(OUT_ROOT / "models" / "effect" / args.out)
        print(f"\nsaved the mlp to {OUT_ROOT / 'models' / 'effect' / args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
