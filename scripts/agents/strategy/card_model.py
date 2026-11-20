"""A card-effect model: what a change to the deck does to the cost of a fight the MCTS plays, learned only from how the random deck variants of one fight
differ from each other (variants.py), so where the run is cannot stand in for the deck.

  python -m agents.strategy.card_model --variants var_m100 --out v50k [--min-count 15] [--epochs 80]

The fight model (fight_model.py) learns a fight's cost from everything at once; the run's position explains most of it, and what the deck adds is drowned
(its within-fight R^2 is ~0). Here each source fight's variants are a group (the same encounter, run and dice; only the deck differs), and a model g(fight, deck)
is fitted to the costs less their group's mean (fixed effects): what is the same for the whole group cancels, so all that is left to learn is the deck and how
it plays with the fight. A card's value to a deck in a fight is then g(fight, deck + card) - g(fight, deck) (`CardModel.delta`; negative: the card helps).

Three models, compared on the within-fight test over held-out runs (fight_model.within_fight; run seed divisible by 5):
  - `card only`: one number per card, whatever the fight or deck (fight_model.card_effects);
  - `ridge`: each card's count, and its count times the fight's context (boss or elite, act, HP share, deck size) and the deck's makeup (what its cards do
    per card, deck_eval/card_profile.json): a card's value can move with the fight and the deck, linearly;
  - `mlp`: the fight model's features (fight_model.featurize: position, encounter, deck, relics, potions) into an MLP, fitted on the within-group differences:
    any interaction, card with card included, if the data shows it.
The ridge's penalty and the MLP's early stopping use the runs whose seed is 1 mod 5, so the held-out fifth is only tested on.

Then: each check card's value by kind of fight and act (the model's mean delta over held-out source decks), and synergy probes: how much card B's value moves
when the deck has card A, by the model and measured from the variants (a within-fight regression with B's change times whether the deck holds A)."""
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

from agents.selfplay.choosers import base_id
from agents.selfplay.value_model import MLP, PROFILE_KEYS, group_codes, demean
from agents.strategy.fight_model import KINDS, NPOS, Vocab, card_effects, change_design, cost, featurize, groups_of, ridge_se, variant_rows, within_fight

CONTEXT = ["boss", "act2", "act3", "hp_frac", "deck_size"] + [f"per_card:{k}" for k in PROFILE_KEYS]
CHECK = ["CRIMSON_MANTLE", "DEMON_FORM", "OFFERING", "INFLAME", "SHRUG_IT_OFF", "POMMEL_STRIKE", "FEEL_NO_PAIN", "RUPTURE", "BARRICADE", "BODY_SLAM",
         "WHIRLWIND", "STRIKE_IRONCLAD", "DEFEND_IRONCLAD"]
PAIRS = [("BARRICADE", "BODY_SLAM"), ("FEEL_NO_PAIN", "BURNING_PACT"), ("DARK_EMBRACE", "BURNING_PACT"), ("FEEL_NO_PAIN", "TRUE_GRIT"),
         ("RUPTURE", "BLOODLETTING"), ("RUPTURE", "OFFERING"), ("DEMON_FORM", "TWIN_STRIKE"), ("INFLAME", "SWORD_BOOMERANG"), ("JUGGERNAUT", "SHRUG_IT_OFF")]


def columns(vocab : Vocab) -> dict[str, int]:
    """Where featurize puts the card counts, upgraded counts and profile sums."""
    c0 = NPOS + len(vocab.encounters)
    return {"cards": c0, "upgraded": c0 + len(vocab.cards), "profile": c0 + 2 * len(vocab.cards)}


def interactions(X : np.ndarray, vocab : Vocab, sel : list[int]) -> np.ndarray:
    """The ridge's features from featurize's rows: the card and upgrade counts, the profile sums, deck size and its square, and each card of `sel` (vocab
    card indices) times each CONTEXT column."""
    col = columns(vocab)
    nc = len(vocab.cards)
    C = X[:, col["cards"]:col["cards"] + nc] * 4.0
    U = X[:, col["upgraded"]:col["upgraded"] + nc] * 4.0
    P = X[:, col["profile"]:col["profile"] + len(PROFILE_KEYS)]
    size = X[:, 8:9]
    boss = X[:, NPOS - len(KINDS) + KINDS.index("Boss")][:, None]
    K = np.hstack([boss, X[:, 1:3], X[:, 6:7], size, P / np.maximum(size, 1 / 30)])
    inter = (C[:, sel][:, :, None] * K[:, None, :]).reshape(len(X), -1)
    return np.hstack([C, U, P, size, size ** 2, inter]).astype(np.float32)


def demean_rows(F : np.ndarray, codes : np.ndarray) -> np.ndarray:
    order = np.argsort(codes, kind="stable")
    sc = codes[order]
    starts = np.flatnonzero(np.r_[True, sc[1:] != sc[:-1]])
    sums = np.add.reduceat(F[order], starts, axis=0)
    counts = np.diff(np.r_[starts, len(sc)])
    means = np.empty_like(sums)
    means[:] = sums / counts[:, None]
    out = np.empty_like(F)
    out[order] = F[order] - np.repeat(means, counts, axis=0)
    return out


class WithinRidge:
    """Ridge on the features and target less their group's mean (fixed effects), on standardized columns. predict gives g up to a constant per group."""
    def __init__(self, lam : float = 100.0):
        self.lam = lam

    def fit(self, F, y, groups):
        codes = group_codes(groups)
        Fd = demean_rows(F, codes)
        yd = demean(np.asarray(y, dtype=np.float64), codes)
        sd = np.maximum(Fd.std(0), 1e-3).astype(np.float32)
        Z = Fd / sd
        A = (Z.T @ Z).astype(np.float64) + self.lam * np.eye(Z.shape[1])
        self.w = (np.linalg.solve(A, Z.T.astype(np.float64) @ yd) / sd).astype(np.float32)
        return self

    def predict(self, F):
        return F @ self.w

    def state(self) -> dict:
        return {"kind": "within_ridge", "w": self.w, "lam": np.float32(self.lam)}

    @classmethod
    def from_state(cls, st) -> "WithinRidge":
        m = cls(float(st["lam"]))
        m.w = st["w"]
        return m


class CardModel:
    """A vocab and a fitted within-fight model: `score(fights)` is g (only differences between decks of one fight mean anything); `delta(fights, card)` the
    change in each fight's cost from adding `card` (HP; negative: it helps)."""
    def __init__(self, vocab : Vocab, model, sel : list[int] | None = None):
        self.vocab, self.model, self.sel = vocab, model, sel

    def score(self, fights : list[dict]) -> np.ndarray:
        X = featurize(fights, self.vocab)
        return self.model.predict(interactions(X, self.vocab, self.sel) if isinstance(self.model, WithinRidge) else X)

    def delta(self, fights : list[dict], card : str) -> np.ndarray:
        return self.score([with_deck(f, f["before"]["deck"] + [card]) for f in fights]) - self.score(fights)

    def save(self, folder : Path):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "vocab.json").write_text(json.dumps(dict(self.vocab.to_json(), sel=self.sel)))
        np.savez(folder / "model.npz", **self.model.state())

    @classmethod
    def load(cls, folder : Path) -> "CardModel":
        data = json.loads((folder / "vocab.json").read_text())
        st = dict(np.load(folder / "model.npz", allow_pickle=True))
        model = WithinRidge.from_state(st) if str(st["kind"]) == "within_ridge" else MLP.from_state(st)
        return cls(Vocab.from_json(data), model, data.get("sel"))


def with_deck(f : dict, deck : list[str]) -> dict:
    return dict(f, before=dict(f["before"], deck=deck))


class CardOnly:
    """The `card only` baseline: each variant's g is the sum of its changes' measured effects."""
    def __init__(self, variants):
        self.effect = {c: e for c, (e, _, _) in card_effects(variants, min_n=1).items()}

    def predict_variants(self, variants) -> np.ndarray:
        return np.array([sum((1 if c["op"] == "add" else -1) * self.effect.get(base_id(c["card"]), 0.0) for c in v["changes"]) for v in variants])


def sources(variants : list[dict]) -> list[dict]:
    """One fight per source, with its source deck."""
    return [with_deck(variants[idx[0]], variants[idx[0]]["base_deck"]) for idx in groups_of(variants).values()]


def measured_pair(variants : list[dict], a : str, b : str) -> tuple[float, float, int]:
    """(how much card b's measured effect moves when the variant's deck holds card a, its standard error, variants that changed b with a in the deck):
    the within-fight regression of card_effects plus one column, b's change times whether the deck holds a (less the source's mean)."""
    X, Y, cards, _, order = change_design(variants)
    if b not in cards or not len(Y):
        return float("nan"), float("nan"), 0
    jb = cards.index(b)
    has = np.array([any(base_id(k) == a for k in variants[i]["before"]["deck"]) for i in order], dtype=np.float64)
    raw = np.zeros(len(order))
    for r, i in enumerate(order):
        raw[r] = sum((1 if c["op"] == "add" else -1) for c in variants[i]["changes"] if base_id(c["card"]) == b) * has[r]
    x = demean(raw, group_codes([variants[i]["source"] for i in order]))
    beta, se = ridge_se(np.hstack([X, x[:, None]]), Y)
    return float(beta[-1]), float(se[-1]), int(np.count_nonzero(raw))


def print_by_context(model : CardModel, srcs : list[dict], cards : list[str]):
    cells = [(k, a) for k in ("Elite", "Boss") for a in (1, 2, 3)]
    groups = {cell: [f for f in srcs if f["kind"] == cell[0] and f["before"].get("act", 1) == cell[1]] for cell in cells}
    print(f"\nthe model's value of adding a card (HP of the fight's cost; negative helps), mean over held-out source decks, by kind of fight and act")
    print("%-18s" % "card" + "".join("%10s" % f"{k[0]}{a} n={len(groups[(k, a)])}"[:10].rjust(10) for k, a in cells) + "%9s" % "spread")
    for card in cards:
        row, spread = [], []
        for cell in cells:
            fs = groups[cell]
            if len(fs) < 5:
                row.append("%10s" % "-")
                continue
            d = model.delta(fs, card)
            row.append("%+10.2f" % d.mean())
            spread += list(d)
        print("%-18s" % card + "".join(row) + "%9.2f" % (np.std(spread) if spread else float("nan")))
    print("  (spread: the SD of the card's value over those decks: how much it depends on the fight and deck)")


def print_pairs(model : CardModel, srcs : list[dict], variants : list[dict], pairs):
    print("\nsynergy: how much card B's value moves when the deck also holds card A (HP; negative: A makes B better)")
    print(f"  {'A':16s} {'B':16s} {'model':>8s} {'measured':>18s}   (variants that changed B with A in the deck)")
    for a, b in pairs:
        srcs_a = [with_deck(f, f["before"]["deck"] + [a]) for f in srcs]
        m = float(np.mean(model.delta(srcs_a, b) - model.delta(srcs, b)))
        e, se, n = measured_pair(variants, a, b)
        print(f"  {a:16s} {b:16s} {m:+8.2f} {e:+9.2f} ± {se:5.2f}   ({n})")


def main(argv=None):
    from agents.selfplay.suite import OUT_ROOT
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--variants", required=True, help="comma separated variant files (data/selfplay/variants/NAME.jsonl.gz, by NAME)")
    p.add_argument("--out", help="save the model chosen on the tuning runs in data/selfplay/models/card/NAME")
    p.add_argument("--min-count", type=int, default=15, help="fights a card, relic, potion or encounter needs for a column")
    p.add_argument("--interact-min", type=int, default=300, help="changes a card needs for its context interactions in the ridge")
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--kinds", default="Elite,Boss")
    args = p.parse_args(argv)

    variants = [v for v in variant_rows(args.variants.split(",")) if v["kind"] in args.kinds.split(",")]
    fit_set = [v for v in variants if v["seed"] % 5 != 0]
    tune = [v for v in fit_set if v["seed"] % 5 == 1]
    inner = [v for v in fit_set if v["seed"] % 5 != 1]
    test = [v for v in variants if v["seed"] % 5 == 0]
    if len(inner) < 200 or len(tune) < 50 or len(test) < 50:
        print(f"{len(variants)} variants: not enough to fit, tune and hold out", file=sys.stderr)
        return 1
    vocab = Vocab.build(fit_set, args.min_count)
    _, _, cards, seen, _ = change_design(fit_set)
    sel = [vocab.card_at[c] for c in cards if seen[c] >= args.interact_min and c in vocab.card_at]
    print(f"{len(variants)} variants of {len(groups_of(variants))} fights: fit {len(inner)}, tune {len(tune)} (seed 1 mod 5), test {len(test)} (0 mod 5) | "
          f"{len(vocab.cards)} cards, {len(sel)} with context interactions ({len(sel) * len(CONTEXT)} columns)")

    X = {name: featurize(vs, vocab) for name, vs in (("inner", inner), ("tune", tune), ("fit", fit_set), ("test", test))}
    y = {name: np.array([cost(v) for v in vs], dtype=np.float32) for name, vs in (("inner", inner), ("tune", tune), ("fit", fit_set), ("test", test))}
    g = {name: [v["source"] for v in vs] for name, vs in (("inner", inner), ("tune", tune), ("fit", fit_set), ("test", test))}

    print("\nwithin-fight test (held-out runs)        corr     R^2   (ceiling)   | tuning runs R^2")
    def report(name, pred_test, pred_tune, seconds):
        wf, wt = within_fight(test, pred_test), within_fight(tune, pred_tune)
        print(f"  {name:36s} {wf['corr']:+.3f}  {wf['r2']:+.3f}  ({wf['ceiling']:.3f})   |  {wt['r2']:+.3f}   ({seconds:.1f}s)")
        return wt["r2"]

    start = time.perf_counter()
    only_inner = CardOnly(inner)
    report("card only", CardOnly(fit_set).predict_variants(test), only_inner.predict_variants(tune), time.perf_counter() - start)

    F = {name: interactions(X[name], vocab, sel) for name in X}
    best_lam, best_r2 = None, -np.inf
    for lam in (30.0, 100.0, 300.0, 1000.0, 3000.0):
        r = within_fight(tune, WithinRidge(lam).fit(F["inner"], y["inner"], g["inner"]).predict(F["tune"]))["r2"]
        if r > best_r2:
            best_lam, best_r2 = lam, r
    start = time.perf_counter()
    ridge = WithinRidge(best_lam).fit(F["fit"], y["fit"], g["fit"])
    tuned = {}
    tuned["ridge"] = report(f"ridge (lam {best_lam:g})", ridge.predict(F["test"]), WithinRidge(best_lam).fit(F["inner"], y["inner"], g["inner"]).predict(F["tune"]),
                            time.perf_counter() - start)

    start = time.perf_counter()
    mlp = MLP(hidden=(64, 32), weight_decay=1e-3, lr=3e-4, epochs=args.epochs, patience=6, batch=512).fit(X["inner"], y["inner"], X["tune"], y["tune"],
                                                                                                         groups=g["inner"], gval=g["tune"])
    tuned["mlp"] = report("mlp", mlp.predict(X["test"]), mlp.predict(X["tune"]), time.perf_counter() - start)
    noise = within_fight(test, np.zeros(len(test)))
    print(f"  (over {noise['n']} held-out variants of {noise['groups']} fights; the same deck replayed on the same dice varies by {noise['noise_sd']:.1f} HP)")

    models = {"ridge": CardModel(vocab, ridge, sel), "mlp": CardModel(vocab, mlp)}
    name = max(tuned, key=tuned.get)
    best = models[name]
    for kind in args.kinds.split(","):
        part = [i for i, v in enumerate(test) if v["kind"] == kind]
        if part:
            wf = within_fight([test[i] for i in part], best.score([test[i] for i in part]))
            print(f"  {name} on {kind} fights only: corr {wf['corr']:+.3f}, R^2 {wf['r2']:+.3f} (ceiling {wf['ceiling']:.3f}), {wf['groups']} fights")

    srcs = sources(test)
    print(f"\nchosen on the tuning runs: {name}")
    print_by_context(best, srcs, CHECK)
    print_pairs(best, srcs, variants, PAIRS)
    if args.out:
        best.save(OUT_ROOT / "models" / "card" / args.out)
        print(f"\nsaved the {name} to {OUT_ROOT / 'models' / 'card' / args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
