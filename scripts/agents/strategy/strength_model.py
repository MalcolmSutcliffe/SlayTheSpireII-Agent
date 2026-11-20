"""A deck-strength model: one number per card adds up to the deck's strength, and a nonlinear link with the fight turns strength into what the fight costs.

  python -m agents.strategy.strength_model --runs fights_m400 --variants var_m100 --synergy syn_m100 --out s1 [--train-synergy]

Why this shape (synergy.py, card_model.py): a card's value hardly depends on which other cards are in the deck (pair synergies < ~1 HP), but every card is
worth more in a weaker deck, nearer to losing. So:
    strength s = (sum of the deck's card values) / (N / 15)^alpha + w * log(N / 15)      (N: deck size; alpha: how much a big deck dilutes each card)
    P(lose)    = sigmoid(a(fight) + s)
    HP lost if won = b(fight) + gamma * s
    cost       = P(lose) * HP going in + (1 - P(lose)) * HP lost if won
a(.) and b(.) are linear in the fight's context (fight_model.featurize without the deck: position, kind, encounter, relics, potions), plus, for a fight played
several times (the variants of one source fight), an effect of its own (shrunk to 0), so the variants teach the card values within their fight. The sigmoid
is the link: the same card moves P(lose) most where it is near 1/2, so the model can show the "weaker deck, every card worth more" effect without pair terms.
A higher s is a weaker deck; a card's value is in the same units (negative: it helps).

Fit: full-batch Adam on cross-entropy (P(lose)) plus the scaled squared error of HP lost (won fights), with L2 penalties; early stopping on the runs whose
seed is 1 mod 5; the seed-0-mod-5 runs are held out. The report: P(lose) and cost on held-out self-play fights (with the model's strength switched off, too:
what the deck adds), the within-fight test on held-out variants (fight_model.within_fight; card_model's best was R^2 0.019), and, held out unless
--train-synergy, the synergy experiment: each anchor's shared interaction (any card's extra value in a deck with the anchor) and each pair's, model vs measured."""
from __future__ import annotations
import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agents.selfplay.value_model import MIN_SD, _sigmoid
from agents.strategy.fight_model import NPOS, Vocab, auc, cost, featurize, fight_rows, groups_of, logloss, within_fight

REF_SIZE = 15.0
DECK_SIZE_COL = 8          # featurize's deck size column: the deck, not the context


def context_columns(vocab : Vocab) -> np.ndarray:
    """featurize's columns that are not the deck: position (without deck size), kind, encounter, relics, potions."""
    from agents.selfplay.value_model import PROFILE_KEYS
    c0 = NPOS + len(vocab.encounters)
    deck =set(range(c0, c0 + 2 * len(vocab.cards) + len(PROFILE_KEYS))) | {DECK_SIZE_COL}
    return np.array([j for j in range(vocab.size) if j not in deck])


class Data:
    """The arrays a fit needs from fight rows: context, card and upgrade counts, deck size, group, HP going in, lost, HP lost when won."""
    def __init__(self, fights : list[dict], vocab : Vocab, ctx_cols : np.ndarray, group_at : dict[str, int] | None = None):
        X = featurize(fights, vocab)
        c0, nc = NPOS + len(vocab.encounters), len(vocab.cards)
        self.ctx = X[:, ctx_cols].astype(np.float64)
        self.C = (X[:, c0:c0 + nc] * 4.0).astype(np.float64)
        self.U = (X[:, c0 + nc:c0 + 2 * nc] * 4.0).astype(np.float64)
        self.logn = np.log(np.maximum([len(f["before"]["deck"]) for f in fights], 1) / REF_SIZE)
        self.hp0 = np.array([f["before"]["hp"] for f in fights], dtype=np.float64)
        self.lost = np.array([not f["won"] for f in fights], dtype=np.float64) if fights and "won" in fights[0] else np.zeros(len(fights))
        self.hpl = np.array([f["before"]["hp"] - f["hp_after"] if f.get("won") else 0.0 for f in fights], dtype=np.float64)
        group_at = group_at or {}
        self.g = np.array([group_at.get(f.get("source"), -1) for f in fights], dtype=np.int64)
        self.n = len(fights)


class StrengthModel:
    def __init__(self, vocab : Vocab, ctx_cols : np.ndarray, group_at : dict[str, int] | None = None):
        self.vocab, self.ctx_cols, self.group_at = vocab, np.asarray(ctx_cols), dict(group_at or {})
        self.randomized : dict[str, int] = {}          # card id -> times a variant added it (describe(): only these values are causal)
        self.elites : dict[str, list[str]] = {}       # boss (or "act:N") -> the elite encounters seen in that act

    # ---------------------------------------------------------------- parameters
    def _init(self, d : Data):
        nc, nk, ng = len(self.vocab.cards), len(self.ctx_cols), len(self.group_at)
        self.mu, self.sd = d.ctx.mean(0), np.maximum(d.ctx.std(0), MIN_SD)
        rate = min(max(d.lost.mean(), 1e-3), 1 - 1e-3)
        won = d.lost < 0.5
        self.hp_scale = float(d.hpl[won].std()) if won.any() else 1.0
        self.p = {"v": np.zeros(nc), "vu": np.zeros(nc), "alpha": np.array(0.5), "w": np.array(0.0),
                  "ta": np.zeros(nk), "ba": np.array(math.log(rate / (1 - rate))), "ua": np.zeros(ng),
                  "tb": np.zeros(nk), "bb": np.array(float(d.hpl[won].mean()) if won.any() else 0.0), "ub": np.zeros(ng), "gamma": np.array(5.0)}

    def _z(self, d : Data):
        return (d.ctx - self.mu) / self.sd

    def strength_parts(self, d : Data):
        raw = d.C @ self.p["v"] + d.U @ self.p["vu"]
        scale = np.exp(-self.p["alpha"] * d.logn)
        return raw, scale, raw * scale + self.p["w"] * d.logn

    def _forward(self, d : Data, deck : bool = True):
        Z = self._z(d)
        raw, scale, s = self.strength_parts(d)
        if not deck:
            s = np.zeros(d.n)
        has = d.g >= 0
        ua = np.where(has, self.p["ua"][np.maximum(d.g, 0)], 0.0) if len(self.p["ua"]) else np.zeros(d.n)
        ub = np.where(has, self.p["ub"][np.maximum(d.g, 0)], 0.0) if len(self.p["ub"]) else np.zeros(d.n)
        za = Z @ self.p["ta"] + self.p["ba"] + ua + s
        m = Z @ self.p["tb"] + self.p["bb"] + ub + self.p["gamma"] * s
        return Z, raw, scale, s, za, m

    def outputs(self, d : Data, deck : bool = True) -> dict[str, np.ndarray]:
        *_, za, m = self._forward(d, deck)
        p = _sigmoid(za)
        hl = np.minimum(m, d.hp0)
        return {"p_lose": p, "hp_lost": hl, "cost": p * d.hp0 + (1 - p) * hl, "z": za}

    def loss(self, d : Data) -> float:
        out = self.outputs(d)
        won = d.lost < 0.5
        return logloss(d.lost, out["p_lose"]) + self.hp_weight * float(np.mean(((out["hp_lost"] - d.hpl) / self.hp_scale) ** 2 * won))

    # ---------------------------------------------------------------- fit
    def fit(self, d : Data, val : Data | None = None, steps : int = 3000, lr : float = 0.02, hp_weight : float = 0.5,
            l2 : dict | None = None, patience : int = 100, freeze_deck : bool = False, verbose : bool = False):
        self.hp_weight = hp_weight
        l2 = {"v": 1.0, "vu": 1.0, "ta": 1.0, "tb": 1.0, "ua": 0.5, "ub": 0.5, **(l2 or {})}
        self._init(d)
        frozen = {"v", "vu", "alpha", "w", "gamma"} if freeze_deck else set()
        m1 = {k: np.zeros_like(v, dtype=np.float64) for k, v in self.p.items()}
        m2 = {k: np.zeros_like(v, dtype=np.float64) for k, v in self.p.items()}
        won = (d.lost < 0.5).astype(np.float64)
        n = d.n
        best, best_p, bad = math.inf, None, 0
        for step in range(1, steps + 1):
            Z, raw, scale, s, za, m = self._forward(d, deck=not freeze_deck)
            p = _sigmoid(za)
            capped = m < d.hp0
            dz = (p - d.lost) / n
            dm = 2 * hp_weight * (m - d.hpl) / self.hp_scale ** 2 * won * capped / n
            ds = dz + self.p["gamma"] * dm
            has = d.g >= 0
            gi = np.maximum(d.g, 0)
            ng = len(self.p["ua"])
            grad = {"ta": Z.T @ dz, "ba": dz.sum(), "tb": Z.T @ dm, "bb": dm.sum(),
                    "ua": np.bincount(gi[has], dz[has], minlength=ng) if ng else np.zeros(0),
                    "ub": np.bincount(gi[has], dm[has], minlength=ng) if ng else np.zeros(0),
                    "v": d.C.T @ (ds * scale), "vu": d.U.T @ (ds * scale), "alpha": np.sum(ds * -raw * scale * d.logn), "w": np.sum(ds * d.logn),
                    "gamma": np.sum(dm * s)}
            for k, lam in l2.items():
                grad[k] = grad[k] + 2 * lam * self.p[k] / n
            for k, gk in grad.items():
                if k in frozen:
                    continue
                m1[k] = 0.9 * m1[k] + 0.1 * gk
                m2[k] = 0.999 * m2[k] + 0.001 * gk * gk
                self.p[k] = self.p[k] - lr * (m1[k] / (1 - 0.9 ** step)) / (np.sqrt(m2[k] / (1 - 0.999 ** step)) + 1e-8)
            self.p["alpha"] = np.clip(self.p["alpha"], 0.0, 1.5)
            if val is not None and step % 10 == 0:
                vl = self.loss(val)
                if verbose and step % 200 == 0:
                    print(f"  step {step}: val loss {vl:.4f}", flush=True)
                if vl < best - 1e-5:
                    best, best_p, bad = vl, {k: np.array(v, copy=True) for k, v in self.p.items()}, 0
                else:
                    bad += 10
                    if bad >= patience:
                        break
        if best_p is not None:
            self.p = best_p
        return self

    # ---------------------------------------------------------------- use
    def data(self, fights : list[dict]) -> Data:
        return Data(fights, self.vocab, self.ctx_cols, self.group_at)

    def predict(self, fights : list[dict]) -> dict[str, np.ndarray]:
        return self.outputs(self.data(fights))

    def delta(self, fights : list[dict], card : str) -> np.ndarray:
        """The change in each fight's expected cost (HP; negative: the card helps) from adding `card`."""
        plus = [dict(f, before=dict(f["before"], deck=f["before"]["deck"] + [card])) for f in fights]
        return self.predict(plus)["cost"] - self.predict(fights)["cost"]

    def card_values(self) -> dict[str, float]:
        return {c: float(self.p["v"][j]) for j, c in enumerate(self.vocab.cards)}

    def save(self, folder : Path):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "vocab.json").write_text(json.dumps(dict(self.vocab.to_json(), hp_scale=self.hp_scale, hp_weight=self.hp_weight,
                                                           randomized=self.randomized, elites=self.elites)))
        np.savez(folder / "model.npz", ctx_cols=self.ctx_cols, mu=self.mu, sd=self.sd, **{f"p_{k}": v for k, v in self.p.items() if k not in ("ua", "ub")})

    @classmethod
    def load(cls, folder : Path) -> "StrengthModel":
        meta = json.loads((folder / "vocab.json").read_text())
        st = np.load(folder / "model.npz")
        m = cls(Vocab.from_json(meta), st["ctx_cols"])
        m.mu, m.sd, m.hp_scale, m.hp_weight = st["mu"], st["sd"], meta["hp_scale"], meta["hp_weight"]
        m.randomized, m.elites = meta.get("randomized", {}), meta.get("elites", {})
        m.p = {k[2:]: st[k] for k in st.files if k.startswith("p_")}
        m.p["ua"], m.p["ub"] = np.zeros(0), np.zeros(0)
        return m


def group_index(fights : list[dict]) -> dict[str, int]:
    """A group per source fight played more than once."""
    out = {}
    for src, idx in groups_of([f for f in fights if f.get("source")]).items():
        if len(idx) >= 2:
            out[src] = len(out)
    return out


def describe(model : StrengthModel, fights : list[dict]):
    """Record on the model what a chooser needs besides the values: how often each card was added at random (variant `add` changes: a card that only
    appears in self-play decks has a value confounded with how the decks were built) and which elites each act holds, by its boss and by act number."""
    from agents.selfplay.choosers import base_id
    rnd, el = defaultdict(int), defaultdict(set)
    for f in fights:
        for c in f.get("changes") or []:
            if c["op"] == "add":
                rnd[base_id(c["card"])] += 1
        if f["kind"] == "Elite":
            el[f["before"].get("boss")].add(f["encounter"]); el[f"act:{f['before'].get('act')}"].add(f["encounter"])
    model.randomized = dict(rnd)
    model.elites = {str(k): sorted(v) for k, v in el.items()}


def synergy_check(model : StrengthModel, rows : list[dict]):
    """Each anchor's shared interaction (mean over its partners) and each pair's, by the model (its expected costs of the four cells of each unit) and
    measured (the cells' actual costs)."""
    units = defaultdict(dict)
    for r in rows:
        if not r.get("error") and "won" in r:
            units[(r["anchor"], r["unit"])][(r["a"], r["b"])] = r
    pred = {}
    flat = [(k, cell, r) for k, cells in units.items() for cell, r in cells.items()]
    pc = model.predict([r for *_, r in flat])["cost"]
    for (k, cell, _), c in zip(flat, pc):
        pred[(k, cell)] = c
    by_pair = defaultdict(lambda: ([], []))
    for (anchor, unit), cells in units.items():
        if (None, None) not in cells or (anchor, None) not in cells:
            continue
        for (a, b) in cells:
            if a is None or b is None or (None, b) not in cells:
                continue
            keys = [(None, None), (anchor, None), (None, b), (anchor, b)]
            ms = [cost(cells[x]) for x in keys]
            ps = [pred[((anchor, unit), x)] for x in keys]
            by_pair[(anchor, b)][0].append((ms[3] - ms[1]) - (ms[2] - ms[0]))
            by_pair[(anchor, b)][1].append((ps[3] - ps[1]) - (ps[2] - ps[0]))
    print("\nsynergy experiment: interaction (HP; negative: B is worth more with A in the deck), measured ± SE against the model")
    anchors = defaultdict(lambda: ([], []))
    for (a, b), (ms, ps) in sorted(by_pair.items()):
        ms, ps = np.array(ms), np.array(ps)
        anchors[a][0].extend(ms); anchors[a][1].extend(ps)
        print(f"  {a:14s} {b:16s} measured {ms.mean():+6.2f} ± {ms.std(ddof=1) / np.sqrt(len(ms)):4.2f}   model {ps.mean():+6.2f}")
    print("  shared, by anchor (mean over its partners):")
    xs, ys = [], []
    for a, (ms, ps) in sorted(anchors.items()):
        ms, ps = np.array(ms), np.array(ps)
        xs.append(ms.mean()); ys.append(ps.mean())
        print(f"  {a:14s} {'(any card)':16s} measured {ms.mean():+6.2f}          model {ps.mean():+6.2f}")
    if len(xs) > 2:
        print(f"  correlation of the anchors' shared interactions, model with measured: {np.corrcoef(xs, ys)[0, 1]:+.2f}")


def main(argv=None):
    from agents.selfplay.fit import load_runs
    from agents.selfplay.suite import OUT_ROOT
    from agents.strategy.experiments import read
    from agents.strategy.fight_model import variant_rows
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", default="", help="self-play folders with fight logs")
    p.add_argument("--variants", default="", help="variant files (data/selfplay/variants)")
    p.add_argument("--synergy", default="", help="synergy files (data/selfplay/synergy): held out for the check unless --train-synergy")
    p.add_argument("--train-synergy", action="store_true")
    p.add_argument("--out", help="save in data/selfplay/models/strength/NAME")
    p.add_argument("--min-count", type=int, default=15)
    p.add_argument("--steps", type=int, default=3000)
    p.add_argument("--hp-weight", type=float, default=0.5)
    args = p.parse_args(argv)

    played = fight_rows(load_runs(args.runs.split(","))) if args.runs else []
    variants = variant_rows(args.variants.split(",")) if args.variants else []
    syn = [r for name in filter(None, args.synergy.split(",")) for r in read(OUT_ROOT / "synergy" / f"{name}.jsonl.gz") if not r.get("error") and "won" in r]
    fights = played + variants + (syn if args.train_synergy else [])
    train = [f for f in fights if f["seed"] % 5 not in (0, 1)]
    tune = [f for f in fights if f["seed"] % 5 == 1]
    test = [f for f in fights if f["seed"] % 5 == 0]
    vocab = Vocab.build(train + tune, args.min_count)
    ctx = context_columns(vocab)
    groups = group_index(train + tune + test)
    print(f"{len(train)} train, {len(tune)} tune, {len(test)} test fights ({len(played)} self-play, {len(variants)} variants, "
          f"{len(syn)} synergy {'in training' if args.train_synergy else 'held out'}) | {len(vocab.cards)} cards, {len(ctx)} context columns, {len(groups)} fight groups")

    results = {}
    for name, freeze in (("context only (no deck)", True), ("strength + link", False)):
        start = time.perf_counter()
        model = StrengthModel(vocab, ctx, groups)
        dtr, dtu = model.data(train), model.data(tune)
        model.fit(dtr, dtu, steps=args.steps, hp_weight=args.hp_weight, freeze_deck=freeze)
        results[name] = model
        sp = [f for f in test if "changes" not in f and "anchor" not in f]
        msg = f"  {name:26s}"
        if sp:
            o = model.outputs(model.data(sp), deck=not freeze)
            y = np.array([not f["won"] for f in sp], dtype=float)
            c = np.array([cost(f) for f in sp])
            msg += f"  self-play: logloss {logloss(y, o['p_lose']):.4f}  AUC {auc(y, o['p_lose']):.3f}  cost R^2 {1 - np.mean((c - o['cost']) ** 2) / np.var(c):.3f}"
        vt = [f for f in test if "changes" in f and "anchor" not in f]
        if vt and not freeze:
            wf = within_fight(vt, model.outputs(model.data(vt))["cost"])
            msg += f"  | within-fight corr {wf['corr']:+.3f}  R^2 {wf['r2']:+.3f}"
        print(msg + f"   ({time.perf_counter() - start:.0f}s)")
    model = results["strength + link"]
    describe(model, played + variants)
    print(f"\nalpha (dilution by deck size) {float(model.p['alpha']):.2f}, w (log deck size) {float(model.p['w']):+.3f}, gamma (HP lost per unit of strength) {float(model.p['gamma']):+.2f}")
    vals = sorted(model.card_values().items(), key=lambda kv: kv[1])
    print("card values (strength units; negative helps): best " + ", ".join(f"{c} {v:+.2f}" for c, v in vals[:10]))
    print("                                          worst " + ", ".join(f"{c} {v:+.2f}" for c, v in vals[-8:]))
    srcs = [dict(f, before=dict(f["before"], deck=f["base_deck"])) for f in {f["source"]: f for f in test if "base_deck" in f}.values()]
    if srcs:
        print(f"\nmean change in an elite/boss fight's cost from adding a card, over {len(srcs)} held-out source decks (HP; negative helps):")
        for card in ("CRIMSON_MANTLE", "DEMON_FORM", "OFFERING", "INFLAME", "SHRUG_IT_OFF", "FEEL_NO_PAIN", "RUPTURE", "BARRICADE", "STRIKE_IRONCLAD", "DEFEND_IRONCLAD"):
            d = model.delta(srcs, card)
            print(f"  {card:18s} {d.mean():+6.2f}   (spread over decks {d.std():.2f})")
    if syn:
        synergy_check(model, syn)
    if args.out:
        model.save(OUT_ROOT / "models" / "strength" / args.out)
        print(f"\nsaved to {OUT_ROOT / 'models' / 'strength' / args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
