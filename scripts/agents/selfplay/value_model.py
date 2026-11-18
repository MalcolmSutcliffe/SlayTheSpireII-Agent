"""A value model of a run: how many more rooms it will clear from this point, learned from self-play logs.

`featurize` turns a snapshot (choosers.snapshot) into numbers: where the run is (act, floor, ascension, HP, gold), the upcoming boss, the deck (a count of each card, upgraded
ones apart, plus totals of what the cards do, read from card_profile.json, which the engine measured, so a card the model has hardly seen still has a meaning), the relics and
the potions, plus `after_reward` for the state right after a card reward. `Vocab` is the cards, relics and bosses the features have a column for (built from the
training data). A model maps features to the target: the rooms the run still clears from the state, to the end of the run. The rows are every room entered and
every card reward (the deck with the pick added: what a chooser compares), in order (`sequence_of`, `Rows`); `td_targets` turns a run's outcome and a model's
values into TD(lambda) targets, which are far less noisy than the outcome of one run and still reach the end of it (fit.py fits them round after round).

`Ridge` (a linear model) and `MLP` (two hidden layers, numpy only) share `fit(X, y, Xval, yval)` and `predict(X)`. `ValueModel` holds a vocab and a model, and gives what a card chooser
needs: `value(snap)` and `gain(snap, card)` = value(deck + card) - value(deck). `ModelChooser` makes it a `CardChooser`."""
from __future__ import annotations
import functools
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from agents.selfplay.choosers import base_id, card_key

HORIZON = 20        # the old cap on the target (rooms): rows_of / Rows.mc take it as an option, off by default
MAX_COPIES = 4
MIN_SD = 0.1        # a column that hardly varies is not scaled up to unit spread: a rare card would otherwise reach values in the hundreds
CLIP = 8.0
ROOMS = ("Monster", "Elite", "Boss", "RestSite", "Shop", "Treasure", "Unknown")
PROFILE_KEYS = ("damage", "block", "draw", "energy", "strength", "vuln", "weak", "hp", "power", "all")
PROFILE_FILE = Path(__file__).resolve().parents[1] / "deck_eval" / "card_profile.json"
POSITION_NAMES = ["act1", "act2", "act3", "floor", "ascension", "hp_frac", "max_hp", "gold", "deck_size", "potions", "relics"] + [f"room:{r}" for r in ROOMS] + ["after_reward", "pilot_mcts"]
AFTER_REWARD, PILOT_MCTS = POSITION_NAMES.index("after_reward"), POSITION_NAMES.index("pilot_mcts")


def pilot_is_mcts(snap : dict) -> bool:
    """Whether the state's fights are the MCTS's: training rows carry their run's pilot (Rows); a snapshot without one is a question about the agent itself,
    which fights with the MCTS."""
    return snap.get("pilot", "mcts") != "rollout"


@functools.lru_cache(maxsize=1)
def profile() -> dict:
    """card_profile.json, read once (a chooser featurizes at every pick)."""
    return json.loads(PROFILE_FILE.read_text()) if PROFILE_FILE.exists() else {}


class Vocab:
    def __init__(self, cards : list[str], relics : list[str], bosses : list[str]):
        self.cards, self.relics, self.bosses = cards, relics, bosses
        self.card_at = {c: i for i, c in enumerate(cards)}
        self.relic_at = {c: i for i, c in enumerate(relics)}
        self.boss_at = {c: i for i, c in enumerate(bosses)}
        self.size = len(POSITION_NAMES) + len(bosses) + len(relics) + 3 * len(cards) + 2 * len(PROFILE_KEYS)

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
                + [f"upgraded:{c}" for c in self.cards] + [f"does:{k}" for k in PROFILE_KEYS]
                + [f"mcts_card:{c}" for c in self.cards] + [f"mcts_does:{k}" for k in PROFILE_KEYS])


def featurize(snaps : list[dict], vocab : Vocab) -> np.ndarray:
    prof = profile()
    nb, nr, nc = len(vocab.bosses), len(vocab.relics), len(vocab.cards)
    p0 = len(POSITION_NAMES)
    X = np.zeros((len(snaps), vocab.size), dtype=np.float32)
    b0, r0, c0, u0, a0 = p0, p0 + nb, p0 + nb + nr, p0 + nb + nr + nc, p0 + nb + nr + 2 * nc
    m0 = a0 + len(PROFILE_KEYS)             # the deck again, under the MCTS only: what a card is worth to the MCTS on top of what it is worth to either pilot
    md0 = m0 + nc
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
        if s.get("reward"):
            row[AFTER_REWARD] = 1.0
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
        if pilot_is_mcts(s):
            row[PILOT_MCTS] = 1.0
            row[m0:m0 + nc] = row[c0:c0 + nc]
            row[md0:md0 + len(PROFILE_KEYS)] = row[a0:a0 + len(PROFILE_KEYS)]
    return X


def sequence_of(run : dict) -> list[tuple[dict, int]]:
    """The states of a run in the order it met them, each with the rooms already cleared there: entering room i (i cleared), then after each card reward won
    in room i (i + 1 cleared: the snapshot with the pick added, logged as `after`). Logs from before `after` was recorded give the rooms alone."""
    after = {}
    for pick in run.get("picks", []):
        if "after" in pick:
            after.setdefault(pick["room"], []).append(pick["after"])
    seq = []
    for i, room in enumerate(run["rooms"]):
        seq.append((room, i))
        seq += [(snap, i + 1) for snap in after.get(i + 1, [])]
    return seq


class Rows:
    """Every state of `runs` as a training row, run after run in order. `progress`: rooms cleared at the state; `final`: rooms the run cleared in all;
    `episode`: which run (0, 1, ...); `seeds`: the run's seed. `mc` is the plain target: the rooms the run still cleared from the state."""
    def __init__(self, runs):
        self.snaps, progress, final, episode, seeds = [], [], [], [], []
        runs = [r for r in runs if not str(r["outcome"].get("cause")).startswith("engine error")]         # the engine failed, not the deck (run.ENGINE_ERROR)
        for k, run in enumerate(runs):
            cleared = run["outcome"]["rooms_cleared"]
            pilot = run.get("pilot", "rollout")          # logs from before pilots were played by the rollout policy
            for snap, done in sequence_of(run):
                self.snaps.append(dict(snap, pilot=pilot))
                progress.append(done)
                final.append(cleared)
                episode.append(k)
                seeds.append(run["seed"])
        self.progress, self.final = np.array(progress, dtype=np.float32), np.array(final, dtype=np.float32)
        self.episode, self.seeds = np.array(episode), np.array(seeds)

    def __len__(self):
        return len(self.snaps)

    def mc(self, horizon : int | None = None, gamma : float = 1.0) -> np.ndarray:
        """The rooms still cleared from each state (discounted by `gamma` per state when below 1), capped at `horizon` when given."""
        y = td_targets(self, None, lam=1.0, gamma=gamma)
        return y if horizon is None else np.minimum(y, horizon)


def td_targets(rows : Rows, values : np.ndarray | None, lam : float = 0.8, gamma : float = 1.0) -> np.ndarray:
    """TD(lambda) targets, worked backwards through each run. The step from one state to the next earns the rooms cleared between them; the last state of a
    run earns the rooms still to clear (0 after a death on entering, the rest of the act after a reward) and nothing after.
        G[t] = r[t] + gamma * ((1 - lam) * V[t+1] + lam * G[t+1]),   G[last] = r[last]
    lam = 1 is the plain outcome (`values` unused); lam = 0 is one step and then the model's own value. `values`: the model's V at every row."""
    progress, final, episode = rows.progress, rows.final, rows.episode
    n = len(progress)
    G = np.zeros(n, dtype=np.float64)
    for t in range(n - 1, -1, -1):
        last = t == n - 1 or episode[t + 1] != episode[t]
        if last:
            G[t] = max(0.0, final[t] - progress[t])
        else:
            r = max(0.0, progress[t + 1] - progress[t])
            boot = G[t + 1] if lam == 1.0 else (1 - lam) * float(values[t + 1]) + lam * G[t + 1]
            G[t] = r + gamma * boot
    return G.astype(np.float32)


def rows_of(runs, horizon : int | None = None):
    """(snapshots, targets, run seeds) of every state of `runs` (sequence_of): the rooms the run still cleared from there, capped at `horizon` when given."""
    rows = Rows(runs)
    return rows.snaps, rows.mc(horizon), rows.seeds


class Ridge:
    def __init__(self, lam : float = 10.0):
        self.lam = lam

    def fit(self, X, y, Xval=None, yval=None, w=None, wval=None):
        """`w`: a weight per row (weighted least squares; default all 1). Xval, yval, wval are unused (the MLP's early stopping takes them)."""
        self.mu, self.sd = X.mean(0), np.maximum(X.std(0), MIN_SD)
        Z = np.clip((X - self.mu) / self.sd, -CLIP, CLIP)
        Z1 = np.hstack([Z, np.ones((len(Z), 1), dtype=Z.dtype)])
        Zw = Z1 if w is None else Z1 * (np.asarray(w, dtype=Z1.dtype) / np.mean(w))[:, None]
        A = Zw.T @ Z1 + self.lam * np.eye(Z1.shape[1])
        A[-1, -1] -= self.lam
        self.w = np.linalg.solve(A.astype(np.float64), (Zw.T @ y).astype(np.float64)).astype(np.float32)
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

    def fit(self, X, y, Xval=None, yval=None, w=None, wval=None):
        """`w`, `wval`: a weight per row of the training and validation sets (a weighted MSE; default all 1)."""
        self.mu, self.sd = X.mean(0), np.maximum(X.std(0), MIN_SD)
        w = np.ones(len(X), dtype=np.float32) if w is None else (np.asarray(w, dtype=np.float32) / np.mean(w))
        wval = None if yval is None else np.ones(len(yval)) if wval is None else np.asarray(wval) / np.mean(wval)
        self.ymu = float(np.average(y, weights=w))
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
                grad = (2.0 / len(idx)) * (w[idx] * (acts[-1][:, 0] - t[idx]))[:, None]
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
                loss = float(np.mean(wval * (self._forward(Zv)[-1][:, 0] + self.ymu - yval) ** 2))
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
    """A CardChooser from a value model: a card scores its gain over the deck as it is, skipping scores `floor` (a card has to add more than that many rooms).
    The snapshot is scored as the agent's own (pilot: the MCTS), whoever plays the run the chooser is used in."""
    def __init__(self, model : ValueModel, floor : float = 0.0):
        self.model, self.floor = model, floor

    def scores(self, snap, offered):
        keys = [card_key(c) for c in offered]          # an upgraded card on offer is scored as one
        snap = {k: v for k, v in snap.items() if k != "pilot"}
        return self.model.gains(snap, keys) + [self.floor]
