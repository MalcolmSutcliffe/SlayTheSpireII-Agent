"""A model of how much a deck is worth in a fight, learned from fights the MCTS played (benchmarks/deck_sweep.py).

The interface every model has (the card chooser does not care which one it holds):

    model.predict(deck, relics, fight_kind, hp_frac=1.0) -> float       the model's target for the deck (see `Row.target`): a share of the starting HP
    model.gain(deck, card, relics, fight_kind, hp_frac=1.0) -> float    predict(deck + [card]) - predict(deck)

`PairRegression` is the penalised base-plus-pairs model: a value per card (`base`) and a value per pair of different cards that are both in the deck (`pair`), fitted by ridge
regression, with a separate penalty for each block, so a pair it has seen little of stays at 0. Costs are things to avoid, so a card that helps has a negative base."""
from __future__ import annotations
import json
from itertools import combinations
from pathlib import Path

import numpy as np

KINDS = ("weak", "normal", "elite", "boss")
ALWAYS_PRESENT = 0.9     # a card in more than this share of the decks gets no pairs
MAX_COPIES = 3          # a fourth Strike counts as the third: the counts of a deck are capped


class DeckModel:
    def predict(self, deck : list[dict], relics : list[dict] | None, fight_kind : str, hp_frac : float = 1.0) -> float:
        raise NotImplementedError

    def gain(self, deck : list[dict], card : dict, relics : list[dict] | None, fight_kind : str, hp_frac : float = 1.0) -> float:
        return self.predict(deck + [card], relics, fight_kind, hp_frac) - self.predict(deck, relics, fight_kind, hp_frac)


def card_ids(deck : list[dict]) -> list[str]:
    return [c["id"] for c in deck]


class PairRegression(DeckModel):
    """target ~ intercept[kind] + sum base[card] * count(card) + sum pair[a, b] * (a and b in the deck) + hp_slope * hp_frac."""
    def __init__(self, lam_base : float = 4.0, lam_pair : float = 40.0):
        self.lam_base, self.lam_pair = lam_base, lam_pair
        self.cards : list[str] = []
        self.pairs : list[tuple[str, str]] = []
        self.intercept = {k: 0.0 for k in KINDS}
        self.base : dict[str, float] = {}
        self.pair : dict[tuple[str, str], float] = {}
        self.hp_slope = 0.0
        self._pair_index : dict[tuple[str, str], int] = {}

    ### features

    def _features(self, deck, kind, hp_frac) -> dict[int, float]:
        """{column: value} of one deck, columns: kinds | hp | cards | pairs (a card's column is its place in `cards`, a pair's its place in `pairs`)."""
        ids = card_ids(deck)
        counts : dict[str, int] = {}
        for i in ids:
            counts[i] = counts.get(i, 0) + 1
        row = {KINDS.index(kind): 1.0, len(KINDS): hp_frac}
        offset = len(KINDS) + 1
        for card, n in counts.items():
            if card in self._card_col:
                row[offset + self._card_col[card]] = float(min(n, MAX_COPIES))
        offset += len(self.cards)
        for pair in combinations(sorted(counts), 2):
            col = self._pair_index.get(pair)
            if col is not None:
                row[offset + col] = 1.0
        return row

    def _index(self, rows):
        """The cards and pairs seen. A card that is in nearly every deck (the starter cards) has no pairs: they would only repeat its own value."""
        seen_cards, seen_pairs, present = set(), set(), {}
        for deck, *_ in rows:
            ids = sorted(set(card_ids(deck)))
            seen_cards.update(ids)
            for i in ids:
                present[i] = present.get(i, 0) + 1
        common = {c for c, n in present.items() if n > ALWAYS_PRESENT * len(rows)}
        for deck, *_ in rows:
            seen_pairs.update(combinations([i for i in sorted(set(card_ids(deck))) if i not in common], 2))
        self.cards = sorted(seen_cards)
        self.pairs = sorted(seen_pairs)
        self._card_col = {c: i for i, c in enumerate(self.cards)}
        self._pair_index = {p: i for i, p in enumerate(self.pairs)}

    ### fit

    def fit(self, rows : list[tuple], targets : list[float]) -> "PairRegression":
        """`rows`: (deck, relics, fight_kind, hp_frac) per fight; `targets`: what each is worth. Ridge in the dual form (as many unknowns as there are pairs, but only as many equations as fights)."""
        self._index(rows)
        n_kind, n_card = len(KINDS) + 1, len(self.cards)
        scale = np.concatenate([np.full(n_kind, 100.0), np.full(n_card, 1 / np.sqrt(self.lam_base)), np.full(len(self.pairs), 1 / np.sqrt(self.lam_pair))])
        X = np.zeros((len(rows), len(scale)))
        for r, (deck, relics, kind, hp_frac) in enumerate(rows):
            for col, v in self._features(deck, kind, hp_frac).items():
                X[r, col] = v
        Xs = X * scale                                     # a feature scaled by 1/sqrt(lam) is penalised by lam under a plain ridge of 1
        y = np.asarray(targets, float)
        K = Xs @ Xs.T
        alpha = np.linalg.solve(K + np.eye(len(rows)), y)
        w = scale * (Xs.T @ alpha)
        self.intercept = {k: float(w[i]) for i, k in enumerate(KINDS)}
        self.hp_slope = float(w[len(KINDS)])
        self.base = {c: float(w[n_kind + i]) for i, c in enumerate(self.cards)}
        self.pair = {p: float(w[n_kind + n_card + i]) for i, p in enumerate(self.pairs)}
        return self

    ### use

    def predict(self, deck, relics, fight_kind, hp_frac : float = 1.0) -> float:
        counts : dict[str, int] = {}
        for i in card_ids(deck):
            counts[i] = counts.get(i, 0) + 1
        total = self.intercept.get(fight_kind, 0.0) + self.hp_slope * hp_frac
        total += sum(self.base.get(c, 0.0) * min(n, MAX_COPIES) for c, n in counts.items())
        total += sum(self.pair.get(p, 0.0) for p in combinations(sorted(counts), 2))
        return total

    def card_table(self, top : int = 15) -> str:
        base = sorted(self.base.items(), key=lambda kv: kv[1])
        pairs = sorted(self.pair.items(), key=lambda kv: kv[1])
        lines = ["base (negative = helps): best " + ", ".join("%s %+.3f" % kv for kv in base[:top]), "                         worst " + ", ".join("%s %+.3f" % kv for kv in base[-top:]),
                 "pairs: best " + ", ".join("%s+%s %+.3f" % (a, b, v) for (a, b), v in pairs[:top]), "       worst " + ", ".join("%s+%s %+.3f" % (a, b, v) for (a, b), v in pairs[-top:])]
        return "\n".join(lines)

    def save(self, path : Path):
        data = {"lam_base": self.lam_base, "lam_pair": self.lam_pair, "intercept": self.intercept, "hp_slope": self.hp_slope, "base": self.base,
                "pair": {"%s|%s" % p: v for p, v in self.pair.items() if abs(v) > 1e-9}}
        Path(path).write_text(json.dumps(data, indent=1))

    @classmethod
    def load(cls, path : Path) -> "PairRegression":
        data = json.loads(Path(path).read_text())
        m = cls(data["lam_base"], data["lam_pair"])
        m.intercept, m.hp_slope, m.base = data["intercept"], data["hp_slope"], data["base"]
        m.pair = {tuple(k.split("|")): v for k, v in data["pair"].items()}
        return m
