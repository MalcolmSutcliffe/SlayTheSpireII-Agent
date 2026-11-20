"""A fight model: how the MCTS does in a fight, from the run going into it and the encounter, learned from the fights MCTS-piloted self-play logs.

  python -m agents.strategy.fight_model --runs fights_m400 --variants var_m100 --out m400 [--min-count 20] [--epochs 60]

The rows are the `fight_log` entries of self-play runs (selfplay/run.py: SelfPlayRun.fight_record) that the MCTS played (`mcts`) and the engine did not fail in.
Two models share the features:
  - `lose`: the chance the fight is lost (the player dies, or the fight runs past the turn limit, which self-play counts as a loss): a logistic MLP;
  - `hp_lost`: the HP a won fight costs (HP going in minus HP after it, before the relics that heal after a fight; negative when the fight heals): an MLP.
Together they give the expected `cost` of a fight, in HP: P(lose) * the HP going in + (1 - P(lose)) * the HP lost if won, the measure benchmarks/policy_fit.py
compares policies by (a lost fight costs all the HP it began with).

The features (`featurize`): where the run is (act, ascension, HP, max HP, floor), the fight's kind (Monster / Elite / Boss) and encounter, the deck (a count of each
card and of its upgraded copies, plus totals of what the cards do from deck_eval/card_profile.json, so a card the model has hardly seen still means something), the relics
and the potions held. A card, relic, potion or encounter needs `min_count` training fights to get a column.

The report, on held-out runs (seed divisible by 5): for each target, a model of the encounter and the run's position alone (no deck, relics or potions) against
the full ridge and MLP models. The gap between them is how much the deck tells about the fight: what a card chooser built on this model can see.
With `--variants` (variants.py: random deck variants of logged fights, the cards assigned at random) the model also trains on those, and two more tests
use them: the within-fight test (the variants of one fight differ only in the deck: does the model rank them as their costs came out?) and a table of what each
card does, measured from the variants by regression, against the model's prediction. Then `--cards-check`: the predicted change in a fight's cost when one card
is added to real decks, against each kind of fight."""
from __future__ import annotations
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agents.selfplay.choosers import base_id
from agents.selfplay.value_model import MLP, PROFILE_KEYS, Ridge, profile

KINDS = ("Monster", "Elite", "Boss")
POSITION = ["act1", "act2", "act3", "ascension", "hp", "max_hp", "hp_frac", "floor", "deck_size", "potions", "relics"] + [f"kind:{k}" for k in KINDS]
NPOS = len(POSITION)


def fight_rows(runs, mcts_only : bool = True) -> list[dict]:
    """The fights of `runs` a fight model trains on: each fight_log entry (with its run's `seed`) that the MCTS played (`mcts_only`) and the engine did not fail in."""
    out = []
    for run in runs:
        for f in run.get("fight_log") or []:
            if f.get("error") or (mcts_only and not f.get("mcts")):
                continue
            out.append(dict(f, seed=run["seed"]))
    return out


def lost(f : dict) -> bool:
    return not f["won"]


def hp_lost(f : dict) -> float:
    return float(f["before"]["hp"] - f["hp_after"])


def cost(f : dict) -> float:
    """HP the fight cost: all the HP it began with when it was lost."""
    return float(f["before"]["hp"]) if lost(f) else hp_lost(f)


class Vocab:
    """The cards (base ids), relics, potions and encounters the features have a column for."""
    def __init__(self, cards : list[str], relics : list[str], potions : list[str], encounters : list[str]):
        self.cards, self.relics, self.potions, self.encounters = cards, relics, potions, encounters
        self.card_at = {c: i for i, c in enumerate(cards)}
        self.relic_at = {c: i for i, c in enumerate(relics)}
        self.potion_at = {c: i for i, c in enumerate(potions)}
        self.encounter_at = {c: i for i, c in enumerate(encounters)}
        self.size = NPOS + len(encounters) + 2 * len(cards) + len(PROFILE_KEYS) + len(relics) + len(potions)

    @classmethod
    def build(cls, fights : list[dict], min_count : int = 20) -> "Vocab":
        cards, relics, potions, encounters = Counter(), Counter(), Counter(), Counter()
        for f in fights:
            s = f["before"]
            cards.update(set(base_id(k) for k in s["deck"]))
            relics.update(set(s["relics"]))
            potions.update(set(s["potions"]))
            encounters[f["encounter"]] += 1
        keep = lambda counter: sorted(k for k, n in counter.items() if n >= min_count and k is not None)
        return cls(keep(cards), keep(relics), keep(potions), keep(encounters))

    def to_json(self) -> dict:
        return {"cards": self.cards, "relics": self.relics, "potions": self.potions, "encounters": self.encounters}

    @classmethod
    def from_json(cls, data : dict) -> "Vocab":
        return cls(data["cards"], data["relics"], data["potions"], data["encounters"])

    def names(self) -> list[str]:
        return (POSITION + [f"enc:{e}" for e in self.encounters] + [f"card:{c}" for c in self.cards] + [f"upgraded:{c}" for c in self.cards]
                + [f"does:{k}" for k in PROFILE_KEYS] + [f"relic:{r}" for r in self.relics] + [f"potion:{p}" for p in self.potions])


def featurize(fights : list[dict], vocab : Vocab) -> np.ndarray:
    """One row per fight: {encounter, kind, before (a run snapshot)}."""
    prof = profile()
    ne, nc, nr = len(vocab.encounters), len(vocab.cards), len(vocab.relics)
    e0 = NPOS
    c0 = e0 + ne
    u0 = c0 + nc
    a0 = u0 + nc
    r0 = a0 + len(PROFILE_KEYS)
    p0 = r0 + nr
    X = np.zeros((len(fights), vocab.size), dtype=np.float32)
    for i, f in enumerate(fights):
        s, row = f["before"], X[i]
        act = s.get("act", 1)
        if 1 <= act <= 3:
            row[act - 1] = 1.0
        row[3] = (s.get("ascension") or 0) / 10.0
        row[4] = s["hp"] / 80.0
        row[5] = s["max_hp"] / 80.0
        row[6] = s["hp"] / max(1, s["max_hp"])
        row[7] = s.get("floor", 0) / 50.0
        row[8] = len(s["deck"]) / 30.0
        row[9] = len(s["potions"]) / 3.0
        row[10] = len(s["relics"]) / 10.0
        if f["kind"] in KINDS:
            row[11 + KINDS.index(f["kind"])] = 1.0
        j = vocab.encounter_at.get(f["encounter"])
        if j is not None:
            row[e0 + j] = 1.0
        for key in s["deck"]:
            cid = base_id(key)
            j = vocab.card_at.get(cid)
            if j is not None:
                row[c0 + j] += 0.25
                if key.endswith("+"):
                    row[u0 + j] += 0.25
            entry = prof.get(key) or prof.get(cid)
            if entry:
                for k, name in enumerate(PROFILE_KEYS):
                    row[a0 + k] += float(entry.get(name) or 0) / 20.0
        for r in s["relics"]:
            j = vocab.relic_at.get(r)
            if j is not None:
                row[r0 + j] = 1.0
        for p in s["potions"]:
            j = vocab.potion_at.get(p)
            if j is not None:
                row[p0 + j] += 1.0
    return X


class FightModel:
    """A vocab and the two fitted models: `predict(fights)` gives P(lose), the HP lost if won and the expected cost of each fight."""
    def __init__(self, vocab : Vocab, lose, loss):
        self.vocab, self.lose, self.loss = vocab, lose, loss

    def predict(self, fights : list[dict]) -> dict[str, np.ndarray]:
        X = featurize(fights, self.vocab)
        p = np.clip(self.lose.predict(X), 0.0, 1.0)
        hp = np.array([f["before"]["hp"] for f in fights], dtype=np.float32)
        won_loss = np.minimum(self.loss.predict(X), hp)
        return {"p_lose": p, "hp_lost": won_loss, "cost": p * hp + (1 - p) * won_loss}

    def save(self, folder : Path):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "vocab.json").write_text(json.dumps(self.vocab.to_json()))
        np.savez(folder / "lose.npz", **self.lose.state())
        np.savez(folder / "hp_lost.npz", **self.loss.state())

    @classmethod
    def load(cls, folder : Path) -> "FightModel":
        def model(name):
            st = dict(np.load(folder / name, allow_pickle=True))
            return (MLP if str(st["kind"]) == "mlp" else Ridge).from_state(st)
        return cls(Vocab.from_json(json.loads((folder / "vocab.json").read_text())), model("lose.npz"), model("hp_lost.npz"))


def r2(y, p) -> float:
    return 1.0 - float(np.mean((y - p) ** 2)) / float(np.mean((y - y.mean()) ** 2))


def auc(y, p) -> float:
    """Chance a lost fight is rated more likely to be lost than a won one (0.5: no better than chance)."""
    pos, neg = p[y > 0.5], p[y <= 0.5]
    if not len(pos) or not len(neg):
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order)); ranks[order] = np.arange(1, len(order) + 1)
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def logloss(y, p) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


CHECK_CARDS = ["INFLAME", "DEMON_FORM", "BARRICADE", "FEEL_NO_PAIN", "SHRUG_IT_OFF", "POMMEL_STRIKE", "IRON_WAVE", "THUNDERCLAP", "HEADBUTT", "BLUDGEON", "STRIKE_IRONCLAD"]


def cards_check(model : FightModel, fights : list[dict], n : int = 200):
    """Mean predicted change in a fight's cost (HP; negative: the card helps) when one card is added to the deck, over held-out fights of each kind."""
    print(f"\npredicted change in a fight's cost (HP; negative: the card helps) from adding a card, over up to {n} held-out fights of each kind")
    print("%-16s" % "card" + "".join("%12s" % k for k in KINDS))
    by_kind = {k: [f for f in fights if f["kind"] == k][:n] for k in KINDS}
    base = {k: model.predict(v)["cost"] if v else None for k, v in by_kind.items()}
    for card in CHECK_CARDS:
        cells = []
        for k in KINDS:
            if not by_kind[k]:
                cells.append("%12s" % "-")
                continue
            plus = model.predict([dict(f, before=dict(f["before"], deck=f["before"]["deck"] + [card])) for f in by_kind[k]])["cost"]
            cells.append("%+12.2f" % float(np.mean(plus - base[k])))
        print("%-16s" % card + "".join(cells))


def variant_rows(names : list[str]) -> list[dict]:
    """The fights of variant files (variants.py: data/selfplay/variants/NAME.jsonl.gz) that played: fight rows like fight_rows', with `source`, `base_deck`, `changes`."""
    from agents.selfplay.suite import OUT_ROOT
    from agents.strategy.experiments import read
    return [v for name in names for v in read(OUT_ROOT / "variants" / f"{name}.jsonl.gz") if not v.get("error") and "won" in v]


def groups_of(variants : list[dict]) -> dict[str, list[int]]:
    """Indices of the variants by their source fight."""
    out : dict[str, list[int]] = {}
    for i, v in enumerate(variants):
        out.setdefault(v["source"], []).append(i)
    return out


def within_fight(variants : list[dict], pred : np.ndarray) -> dict:
    """The within-fight test: inside each source fight's variants only the deck differs, so how well the predicted costs' deviations from their fight's mean
    match the actual ones is how well the model knows what the cards do. `ceiling`: the most the fights' own noise leaves room for, from the variants of a fight
    with the very same deck (their spread is the noise). Returns {n, groups, corr, r2, ceiling}."""
    y = np.array([cost(v) for v in variants], dtype=np.float64)
    dev_y, dev_p, shrink = [], [], []
    noise = []
    for idx in groups_of(variants).values():
        if len(idx) < 2:
            continue
        g = np.array(idx)
        dev_y += list(y[g] - y[g].mean())
        dev_p += list(pred[g] - pred[g].mean())
        shrink += [1 - 1 / len(g)] * len(g)
        by_deck : dict[tuple, list[float]] = {}
        for i in idx:
            by_deck.setdefault(tuple(sorted(variants[i]["before"]["deck"])), []).append(y[i])
        for same in by_deck.values():
            if len(same) >= 2:
                noise.append(np.var(same, ddof=1))
    if len(dev_y) < 10:
        return {"n": len(dev_y), "groups": 0, "corr": float("nan"), "r2": float("nan"), "ceiling": float("nan")}
    dev_y, dev_p = np.array(dev_y), np.array(dev_p)
    var = float(np.mean(dev_y ** 2))
    ceiling = 1.0 - float(np.mean(noise)) * float(np.mean(shrink)) / var if noise else float("nan")
    return {"n": len(dev_y), "groups": sum(len(idx) >= 2 for idx in groups_of(variants).values()), "corr": float(np.corrcoef(dev_y, dev_p)[0, 1]),
            "r2": 1.0 - float(np.mean((dev_y - dev_p) ** 2)) / var, "ceiling": ceiling, "noise_sd": float(np.sqrt(np.mean(noise))) if noise else float("nan")}


def change_design(variants : list[dict]) -> tuple[np.ndarray, np.ndarray, list[str], Counter, np.ndarray]:
    """The within-fight regression's data: (X: per variant, how many of each card its changes added (removes -1), less its source fight's mean; Y: its cost less
    the source's mean; the cards (X's columns); how many changes each card had; the variants' indices, in X's row order). Sources with one variant are left out."""
    cards = sorted({base_id(c["card"]) for v in variants for c in v["changes"]})
    at = {c: j for j, c in enumerate(cards)}
    rows, ys, order, seen = [], [], [], Counter()
    y = np.array([cost(v) for v in variants], dtype=np.float64)
    for idx in groups_of(variants).values():
        if len(idx) < 2:
            continue
        D = np.zeros((len(idx), len(cards)))
        for r, i in enumerate(idx):
            for c in variants[i]["changes"]:
                D[r, at[base_id(c["card"])]] += 1.0 if c["op"] == "add" else -1.0
                seen[base_id(c["card"])] += 1
        rows.append(D - D.mean(0))
        ys.append(y[idx] - y[idx].mean())
        order += idx
    if not rows:
        return np.zeros((0, len(cards))), np.zeros(0), cards, seen, np.zeros(0, dtype=int)
    return np.vstack(rows), np.concatenate(ys), cards, seen, np.array(order)


def ridge_se(X : np.ndarray, Y : np.ndarray, lam : float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """(coefficients, standard errors) of a ridge regression without intercept (the rows are already demeaned)."""
    A = X.T @ X + lam * np.eye(X.shape[1])
    beta = np.linalg.solve(A, X.T @ Y)
    resid = Y - X @ beta
    sigma2 = float(resid @ resid) / max(1, len(Y) - X.shape[1])
    return beta, np.sqrt(np.maximum(np.diag(np.linalg.inv(A)) * sigma2, 0))


def card_effects(variants : list[dict], lam : float = 1.0, min_n : int = 30) -> dict[str, tuple[float, float, int]]:
    """{card: (effect on a fight's cost, its standard error, changes seen)} measured from the variants alone: each fight's cost minus its source fight's mean,
    regressed on how many of each card the changes added (removes count -1), so a card's effect is what it did on the fights it was put in at random."""
    X, Y, cards, seen, _ = change_design(variants)
    if not len(Y):
        return {}
    beta, se = ridge_se(X, Y, lam)
    return {c: (float(beta[j]), float(se[j]), seen[c]) for j, c in enumerate(cards) if seen[c] >= min_n}


def model_card_effects(model : FightModel, variants : list[dict], cards : list[str], n : int = 300) -> dict[str, float]:
    """The model's mean change in a fight's cost from adding each card to the source decks of `variants` (up to `n` source fights)."""
    sources = []
    for idx in list(groups_of(variants).values())[:n]:
        v = variants[idx[0]]
        sources.append(dict(v, before=dict(v["before"], deck=v["base_deck"])))
    if not sources:
        return {}
    base = model.predict(sources)["cost"]
    return {c: float(np.mean(model.predict([dict(f, before=dict(f["before"], deck=f["before"]["deck"] + [c])) for f in sources])["cost"] - base)) for c in cards}


def print_card_effects(model : FightModel, variants_all : list[dict], variants_val : list[dict], top : int = 12):
    measured = card_effects(variants_all)
    if not measured:
        return
    predicted = model_card_effects(model, variants_val, list(measured))
    cards = sorted(measured, key=lambda c: measured[c][0])
    m = np.array([measured[c][0] for c in cards]); p = np.array([predicted[c] for c in cards]); se = np.array([measured[c][1] for c in cards])
    w = 1 / np.maximum(se, 1e-3) ** 2
    corr = float(np.corrcoef(m, p)[0, 1]) if len(cards) > 2 else float("nan")
    print(f"\nwhat a card does to an elite or boss fight's cost (HP; negative helps): measured from the random variants (± standard error) against the model's mean "
          f"over held-out decks | {len(cards)} cards with 30+ changes; correlation of the two across cards {corr:+.2f}; mean standard error {np.sqrt(1 / w.mean()):.2f}")
    shown = cards if len(cards) <= 2 * top else cards[:top] + [None] + cards[-top:]
    for c in shown:
        if c is None:
            print("  ...")
            continue
        e, s, n = measured[c]
        print(f"  {c:22s} n={n:5d}  measured {e:+6.2f} ± {s:4.2f}   model {predicted[c]:+6.2f}")


def main(argv=None):
    from agents.selfplay.fit import load_runs
    from agents.selfplay.suite import OUT_ROOT
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", default="", help="comma separated folders of data/selfplay with fight logs (self-play fights)")
    p.add_argument("--variants", default="", help="comma separated variant files (data/selfplay/variants/NAME.jsonl.gz, by NAME): random deck variants")
    p.add_argument("--out", help="save the model in data/selfplay/models/fight/NAME")
    p.add_argument("--min-count", type=int, default=20)
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--cards-check", action="store_true")
    args = p.parse_args(argv)

    played = fight_rows(load_runs(args.runs.split(","))) if args.runs else []
    variants = variant_rows(args.variants.split(",")) if args.variants else []
    fights = played + variants
    train, val = [f for f in fights if f["seed"] % 5], [f for f in fights if f["seed"] % 5 == 0]
    if len(train) < 50 or len(val) < 20:
        print(f"{len(fights)} MCTS fights: not enough to fit and hold out", file=sys.stderr)
        return 1
    vocab = Vocab.build(train, args.min_count)
    X, Xv = featurize(train, vocab), featurize(val, vocab)
    yl, vyl = np.array([lost(f) for f in train], dtype=np.float32), np.array([lost(f) for f in val], dtype=np.float32)
    won, vwon = yl < 0.5, vyl < 0.5
    yh, vyh = np.array([hp_lost(f) for f in train], dtype=np.float32), np.array([hp_lost(f) for f in val], dtype=np.float32)
    kinds = Counter(f["kind"] for f in train)
    print(f"{len(train)} train fights ({len(played)} self-play, {len(variants)} variants in all; {', '.join(f'{k} {kinds[k]}' for k in KINDS)}), {len(val)} held out | "
          f"lost {100 * yl.mean():.1f}% | HP lost when won: mean {yh[won].mean():.1f}, spread {yh[won].std():.1f} | {vocab.size} features: {len(vocab.encounters)} encounters, "
          f"{len(vocab.cards)} cards, {len(vocab.relics)} relics, {len(vocab.potions)} potions")
    context = list(range(NPOS + len(vocab.encounters)))           # the position and the encounter: no deck, relics or potions
    is_var = np.array(["changes" in f for f in val])
    var_val = [f for f in val if "changes" in f]
    print("\nheld out                                   lose: logloss   AUC  |  HP lost when won: R^2  |  cost: R^2  |  within-fight (variants): corr  R^2 (ceiling)")
    vc = np.array([cost(f) for f in val], dtype=np.float32)
    vhp = np.array([f["before"]["hp"] for f in val], dtype=np.float32)
    fitted = {}
    mlp = lambda loss="mse": MLP(hidden=(64, 32), weight_decay=1e-3, lr=3e-4, epochs=args.epochs, patience=5, loss=loss)
    makers = {
        "context mlp (no deck, relics, potions)": (lambda: mlp("bce"), mlp, context),
        "ridge": (lambda: Ridge(300.0), lambda: Ridge(300.0), None),
        "mlp": (lambda: mlp("bce"), mlp, None),
    }
    print(f"  {'mean of the training fights':38s}       {logloss(vyl, np.full(len(vyl), yl.mean())):.4f}  0.500  |  {0.0:6.3f}                |")
    for name, (make_lose, make_loss, cols) in makers.items():
        start = time.perf_counter()
        sel = (lambda A: A[:, cols]) if cols is not None else (lambda A: A)
        lose = make_lose().fit(sel(X), yl, sel(Xv), vyl)
        loss = make_loss().fit(sel(X)[won], yh[won], sel(Xv)[vwon], vyh[vwon])
        pl = np.clip(lose.predict(sel(Xv)), 1e-4, 1 - 1e-4)
        ph = np.minimum(loss.predict(sel(Xv)), vhp)
        pc = pl * vhp + (1 - pl) * ph
        wf = within_fight(var_val, pc[is_var]) if var_val else None
        within = "" if not wf or not wf["groups"] else f"  |  {wf['corr']:+.3f}  {wf['r2']:+.3f} ({wf['ceiling']:.3f})"
        print(f"  {name:38s}       {logloss(vyl, pl):.4f}  {auc(vyl, pl):.3f}  |  {r2(vyh[vwon], ph[vwon]):6.3f}                |  {r2(vc, pc):6.3f}{within}   ({time.perf_counter() - start:.1f}s)")
        if cols is None:
            fitted[name] = FightModel(vocab, lose, loss)
    best = fitted["mlp"]
    if var_val:
        wf = within_fight(var_val, best.predict(var_val)["cost"])
        print(f"  (within-fight test over {wf['n']} held-out variants of {wf['groups']} fights; the same deck replayed on the same dice varies by {wf.get('noise_sd', float('nan')):.1f} HP)")
    if variants:
        print_card_effects(best, variants, var_val)
    if args.out:
        best.save(OUT_ROOT / "models" / "fight" / args.out)
        print(f"\nsaved the mlp to {OUT_ROOT / 'models' / 'fight' / args.out}")
    if args.cards_check:
        cards_check(best, val)
    return 0


if __name__ == "__main__":
    sys.exit(main())
