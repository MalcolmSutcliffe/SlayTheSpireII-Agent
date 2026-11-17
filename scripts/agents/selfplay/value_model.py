"""A value model of a run: how many more rooms it will clear from this point, learned from self-play logs.

`featurize` turns a snapshot (choosers.snapshot) into numbers: where the run is (act, floor, ascension, HP, gold), the upcoming boss, the deck (a count of each card, upgraded
ones apart, plus totals of what the cards do, read from card_profile.json, which the engine measured, so a card the model has hardly seen still has a meaning), the relics and
the potions. `Vocab` is the cards, relics and bosses the features have a column for (built from the training data). A model maps features to the target: the rooms the run
still clears, capped at `HORIZON` (so one lucky run through three acts does not dominate a loss).

`Ridge` (a linear model) and `MLP` (two hidden layers, numpy only) share `fit(X, y, Xval, yval)` and `predict(X)`. `ValueModel` holds a vocab and a model, and gives what a card chooser
needs: `value(snap)` and `gain(snap, card)` = value(deck + card) - value(deck). `ModelChooser` makes it a `CardChooser`."""
from __future__ import annotations
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from agents.selfplay.choosers import base_id

HORIZON = 20
MAX_COPIES = 4
MIN_SD = 0.1        # a column that hardly varies is not scaled up to unit spread: a rare card would otherwise reach values in the hundreds
CLIP = 8.0
ROOMS = ("Monster", "Elite", "Boss", "RestSite", "Shop", "Treasure", "Unknown")
PROFILE_KEYS = ("damage", "block", "draw", "energy", "strength", "vuln", "weak", "hp", "power", "all")
PROFILE_FILE = Path(__file__).resolve().parents[1] / "deck_eval" / "card_profile.json"
POSITION_NAMES = ["act1", "act2", "act3", "floor", "ascension", "hp_frac", "max_hp", "gold", "deck_size", "potions", "relics"] + [f"room:{r}" for r in ROOMS]


def profile() -> dict:
    return json.loads(PROFILE_FILE.read_text()) if PROFILE_FILE.exists() else {}


class Vocab:
    def __init__(self, cards : list[str], relics : list[str], bosses : list[str]):
        self.cards, self.relics, self.bosses = cards, relics, bosses
        self.card_at = {c: i for i, c in enumerate(cards)}
        self.relic_at = {c: i for i, c in enumerate(relics)}
        self.boss_at = {c: i for i, c in enumerate(bosses)}
        self.size = len(POSITION_NAMES) + len(bosses) + len(relics) + 2 * len(cards) + len(PROFILE_KEYS)

    @classmethod
    def build(cls, snaps, min_count : int = 40) -> "Vocab":
        cards, relics, bosses = Counter(), Counter(), Counter()
        for s in snaps:
            cards.update(set(base_id(k) for k in s["deck"]))
            relics.update(set(s["relics"]))
            bosses[s["boss"]] += 1
        keep = lambda counter: sorted(k for k, n in counter.items() if n >= min_count and k is not None)
        return cls(keep(cards), keep(relics), keep(bosses))

    def to_json(self) -> dict:
        return {"cards": self.cards, "relics": self.relics, "bosses": self.bosses}

    @classmethod
    def from_json(cls, data : dict) -> "Vocab":
        return cls(data["cards"], data["relics"], data["bosses"])

    def names(self) -> list[str]:
        return (POSITION_NAMES + [f"boss:{b}" for b in self.bosses] + [f"relic:{r}" for r in self.relics] + [f"card:{c}" for c in self.cards]
                + [f"upgraded:{c}" for c in self.cards] + [f"does:{k}" for k in PROFILE_KEYS])


def featurize(snaps : list[dict], vocab : Vocab) -> np.ndarray:
    prof = profile()
    nb, nr, nc = len(vocab.bosses), len(vocab.relics), len(vocab.cards)
    p0 = len(POSITION_NAMES)
    X = np.zeros((len(snaps), vocab.size), dtype=np.float32)
    b0, r0, c0, u0, a0 = p0, p0 + nb, p0 + nb + nr, p0 + nb + nr + nc, p0 + nb + nr + 2 * nc
    for i, s in enumerate(snaps):
        row = X[i]
        act = s["act"]
        if 1 <= act <= 3:
            row[act - 1] = 1.0
        row[3] = s["floor"] / 55.0
        row[4] = (s.get("ascension") or 0) / 10.0
        row[5] = s["hp"] / max(1, s["max_hp"])
        row[6] = s["max_hp"] / 100.0
        row[7] = s["gold"] / 300.0
        row[8] = len(s["deck"]) / 40.0
        row[9] = len(s["potions"]) / 3.0
        row[10] = len(s["relics"]) / 10.0
        if s.get("room") in ROOMS:
            row[11 + ROOMS.index(s["room"])] = 1.0
        j = vocab.boss_at.get(s["boss"])
        if j is not None:
            row[b0 + j] = 1.0
        for r in s["relics"]:
            j = vocab.relic_at.get(r)
            if j is not None:
                row[r0 + j] = 1.0
        for key in s["deck"]:
            cid = base_id(key)
            j = vocab.card_at.get(cid)
            if j is not None:
                row[c0 + j] = min(row[c0 + j] + 1.0 / MAX_COPIES, 1.0)
                if key.endswith("+"):
                    row[u0 + j] = min(row[u0 + j] + 1.0 / MAX_COPIES, 1.0)
            entry = prof.get(key) or prof.get(cid)
            if entry:
                for k, name in enumerate(PROFILE_KEYS):
                    row[a0 + k] += float(entry.get(name) or 0) / 20.0
    return X


def rows_of(runs, horizon : int = HORIZON):
    """(snapshots, targets, run seeds) of every room entered in `runs`: the rooms the run still cleared from there, up to `horizon`."""
    snaps, ys, seeds = [], [], []
    for run in runs:
        cleared = run["outcome"]["rooms_cleared"]
        for i, room in enumerate(run["rooms"]):
            snaps.append(room)
            ys.append(min(max(0, cleared - i), horizon))
            seeds.append(run["seed"])
    return snaps, np.array(ys, dtype=np.float32), np.array(seeds)


class Ridge:
    def __init__(self, lam : float = 10.0):
        self.lam = lam

    def fit(self, X, y, Xval=None, yval=None):
        self.mu, self.sd = X.mean(0), np.maximum(X.std(0), MIN_SD)
        Z = np.clip((X - self.mu) / self.sd, -CLIP, CLIP)
        Z1 = np.hstack([Z, np.ones((len(Z), 1), dtype=Z.dtype)])
        A = Z1.T @ Z1 + self.lam * np.eye(Z1.shape[1])
        A[-1, -1] -= self.lam
        self.w = np.linalg.solve(A.astype(np.float64), (Z1.T @ y).astype(np.float64)).astype(np.float32)
        return self

    def predict(self, X):
        Z = np.clip((X - self.mu) / self.sd, -CLIP, CLIP)
        return np.hstack([Z, np.ones((len(Z), 1), dtype=Z.dtype)]) @ self.w

    def state(self) -> dict:
        return {"kind": "ridge", "mu": self.mu, "sd": self.sd, "w": self.w}

    @classmethod
    def from_state(cls, st) -> "Ridge":
        m = cls()
        m.mu, m.sd, m.w = st["mu"], st["sd"], st["w"]
        return m


class MLP:
    """Two hidden layers of ReLU, MSE, Adam, early stopping on the validation set."""
    def __init__(self, hidden=(128, 64), lr : float = 1e-3, weight_decay : float = 1e-4, epochs : int = 40, batch : int = 512, patience : int = 5, seed : int = 0, verbose : bool = False):
        self.hidden, self.lr, self.wd, self.epochs, self.batch, self.patience, self.seed, self.verbose = hidden, lr, weight_decay, epochs, batch, patience, seed, verbose

    def _init(self, n):
        rng = np.random.default_rng(self.seed)
        sizes = [n, *self.hidden, 1]
        self.W = [(rng.standard_normal((a, b)) * math.sqrt(2.0 / a)).astype(np.float32) for a, b in zip(sizes, sizes[1:])]
        self.b = [np.zeros(b, dtype=np.float32) for b in sizes[1:]]

    def _scale(self, X):
        return np.clip((X - self.mu) / self.sd, -CLIP, CLIP).astype(np.float32)

    def _forward(self, Z):
        acts = [Z]
        for k, (W, b) in enumerate(zip(self.W, self.b)):
            Z = Z @ W + b
            if k < len(self.W) - 1:
                Z = np.maximum(Z, 0)
            acts.append(Z)
        return acts

    def fit(self, X, y, Xval=None, yval=None):
        self.mu, self.sd = X.mean(0), np.maximum(X.std(0), MIN_SD)
        self.ymu = float(y.mean())
        Z, t = self._scale(X), (y - self.ymu).astype(np.float32)
        Zv = None if Xval is None else self._scale(Xval)
        self._init(Z.shape[1])
        mW = [np.zeros_like(w) for w in self.W]; vW = [np.zeros_like(w) for w in self.W]
        mb = [np.zeros_like(b) for b in self.b]; vb = [np.zeros_like(b) for b in self.b]
        rng, step, best, best_state, bad = np.random.default_rng(self.seed + 1), 0, math.inf, None, 0
        for epoch in range(self.epochs):
            order = rng.permutation(len(Z))
            for s in range(0, len(Z), self.batch):
                idx = order[s:s + self.batch]
                acts = self._forward(Z[idx])
                grad = (2.0 / len(idx)) * (acts[-1][:, 0] - t[idx])[:, None]
                step += 1
                for k in range(len(self.W) - 1, -1, -1):
                    gW = acts[k].T @ grad + self.wd * self.W[k]
                    gb = grad.sum(0)
                    if k > 0:
                        grad = (grad @ self.W[k].T) * (acts[k] > 0)
                    for m, v, g, p in ((mW, vW, gW, self.W), (mb, vb, gb, self.b)):
                        m[k] = 0.9 * m[k] + 0.1 * g
                        v[k] = 0.999 * v[k] + 0.001 * g * g
                        p[k] -= self.lr * (m[k] / (1 - 0.9 ** step)) / (np.sqrt(v[k] / (1 - 0.999 ** step)) + 1e-8)
            if Zv is not None:
                loss = float(np.mean((self._forward(Zv)[-1][:, 0] + self.ymu - yval) ** 2))
                if self.verbose:
                    print(f"  epoch {epoch + 1}: val mse {loss:.3f}", flush=True)
                if loss < best - 1e-4:
                    best, best_state, bad = loss, ([w.copy() for w in self.W], [b.copy() for b in self.b]), 0
                else:
                    bad += 1
                    if bad >= self.patience:
                        break
        if best_state is not None:
            self.W, self.b = best_state
        return self

    def predict(self, X):
        return self._forward(self._scale(X))[-1][:, 0] + self.ymu

    def state(self) -> dict:
        st = {"kind": "mlp", "mu": self.mu, "sd": self.sd, "ymu": np.float32(self.ymu), "layers": np.int32(len(self.W))}
        for k, (W, b) in enumerate(zip(self.W, self.b)):
            st[f"W{k}"], st[f"b{k}"] = W, b
        return st

    @classmethod
    def from_state(cls, st) -> "MLP":
        m = cls()
        m.mu, m.sd, m.ymu = st["mu"], st["sd"], float(st["ymu"])
        n = int(st["layers"])
        m.W, m.b = [st[f"W{k}"] for k in range(n)], [st[f"b{k}"] for k in range(n)]
        return m


class ValueModel:
    """A vocab and a fitted model: the interface a card chooser uses."""
    def __init__(self, vocab : Vocab, model):
        self.vocab, self.model = vocab, model

    def values(self, snaps : list[dict]) -> np.ndarray:
        return self.model.predict(featurize(snaps, self.vocab))

    def value(self, snap : dict) -> float:
        return float(self.values([snap])[0])

    def gains(self, snap : dict, cards : list[str]) -> list[float]:
        """value(deck + card) - value(deck) for each card key, in one batch."""
        snaps = [snap] + [dict(snap, deck=snap["deck"] + [c]) for c in cards]
        v = self.values(snaps)
        return [float(x - v[0]) for x in v[1:]]

    def save(self, folder : Path):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "vocab.json").write_text(json.dumps(self.vocab.to_json()))
        np.savez(folder / "model.npz", **self.model.state())

    @classmethod
    def load(cls, folder : Path) -> "ValueModel":
        vocab = Vocab.from_json(json.loads((folder / "vocab.json").read_text()))
        st = dict(np.load(folder / "model.npz", allow_pickle=True))
        kind = str(st["kind"])
        return cls(vocab, (MLP if kind == "mlp" else Ridge).from_state(st))


class ModelChooser:
    """A CardChooser from a value model: a card scores its gain, skipping scores 0 (the deck as it is)."""
    def __init__(self, model : ValueModel):
        self.model = model

    def scores(self, snap, offered):
        keys = [str(c.get("id")) for c in offered]
        return self.model.gains(snap, keys) + [0.0]
