"""Who picks the cards of a self-play run, and how it explores.

A `CardChooser` scores the offered cards of a reward screen from a snapshot of the run (`snapshot()`): `scores(snap, offered)` returns one number per offered
card and one more, last, for skipping the reward. Higher is better. The scores are meant to read as expected rooms of progress, so a network that learns to predict
the run's outcome can be plugged in as it is; the first choosers (random, rarity) only give an order.

`Explorer` wraps a chooser: it adds a bonus `c / sqrt(n + 1)` to a card, n being the number of runs that picked the card in this act, so a card that
has hardly been tried is picked more often; and with chance `epsilon` it picks uniformly among the cards and the skip. Every pick records whether it differs from what the
chooser alone would have picked (`exploratory`), because a pick forced on a deck that cannot use the card will lose, and a fit should know that."""
from __future__ import annotations
import functools
import math
import random
from typing import Protocol

from agents.deck_eval.cards import RARITY_RANK


def card_key(card : dict) -> str:
    """A card as the logs name it: its id, plus `+` when upgraded."""
    return str(card.get("id")) + ("+" if card.get("is_upgraded") else "")


def base_id(key : str) -> str:
    return key[:-1] if key.endswith("+") else key


def snapshot(run, act : int | None = None) -> dict:
    """What a chooser and the logs see of the run: plain data, no hidden part."""
    return {"act": run.act if act is None else act, "floor": run.floor, "ascension": run.ascension, "boss": run.boss, "hp": run.hp, "max_hp": run.max_hp, "gold": run.gold,
            "deck": [card_key(c) for c in run.deck], "relics": [str(r.get("id")) for r in run.relics], "potions": [str(p.get("id")) for p in run.potions if p]}


class CardChooser(Protocol):
    def scores(self, snap : dict, offered : list[dict]) -> list[float]:
        """One score per offered card, then one for skipping the reward."""


class RandomChooser:
    """Every card a draw in [0, 1); skipping scores `skip`."""
    def __init__(self, seed : int | str = 0, skip : float = 0.25):
        self.rng, self.skip = random.Random(seed), skip

    def scores(self, snap, offered):
        return [self.rng.random() for _ in offered] + [self.skip]


class RarityChooser:
    """The rarest card first (what the walks' stand-in agent does), ties by a small draw; skipping scores just under a common card."""
    def __init__(self, seed : int | str = 0):
        self.rng = random.Random(seed)

    def scores(self, snap, offered):
        return [RARITY_RANK.get(c.get("rarity"), 0) + 0.1 * self.rng.random() for c in offered] + [0.5]


CHOOSERS = {"random": RandomChooser, "rarity": RarityChooser}


@functools.lru_cache(maxsize=8)
def _value_model(name : str):
    """A fitted value model from data/selfplay/models/NAME (fit.py --out), loaded once per process."""
    from agents.selfplay.suite import OUT_ROOT
    from agents.selfplay.value_model import ValueModel
    folder = OUT_ROOT / "models" / name
    if not (folder / "model.npz").exists():
        raise ValueError(f"no value model at {folder} (fit one with: python -m agents.selfplay.fit --out ...)")
    return ValueModel.load(folder)


@functools.lru_cache(maxsize=8)
def _pick_model(name : str):
    """A pick model from data/selfplay/models/NAME (pick_model.py --out), loaded once per process."""
    from agents.selfplay.suite import OUT_ROOT
    from agents.selfplay.pick_model import PickModel
    folder = OUT_ROOT / "models" / name
    if not (folder / "meta.json").exists():
        raise ValueError(f"no pick model at {folder} (fit one with: python -m agents.selfplay.pick_model --out ...)")
    return PickModel.load(folder)


def make_chooser(name : str, seed : int | str = 0) -> CardChooser:
    """"random", "rarity", or "model:NAME[:FLOOR]": the value model saved as data/selfplay/models/NAME (e.g. model:gen0/mlp), taking a card only when it adds
    more than FLOOR rooms (default 0)."""
    if name.startswith("pick:"):            # a pick model distilled from the walks (pick_model.py): pick:NAME[:MARGIN], e.g. pick:walk0/mlp
        from agents.selfplay.pick_model import PickChooser
        path, _, margin = name[len("pick:"):].partition(":")
        return PickChooser(_pick_model(path), float(margin) if margin else None)
    if name.startswith("model:"):
        from agents.selfplay.value_model import ModelChooser
        path, _, floor = name[len("model:"):].partition(":")
        return ModelChooser(_value_model(path), float(floor) if floor else 0.0)
    if name not in CHOOSERS:
        raise ValueError(f"unknown chooser {name!r}: {sorted(CHOOSERS)}, model:NAME[:FLOOR] or pick:NAME[:MARGIN]")
    return CHOOSERS[name](seed)


class Counts:
    """How many runs picked each card, per act: `{(act, card id): n}`."""
    def __init__(self, table : dict[tuple[int, str], int] | None = None):
        self.table : dict[tuple[int, str], int] = dict(table or {})

    def n(self, act : int, card_id : str) -> int:
        return self.table.get((act, base_id(card_id)), 0)

    def add_run(self, picks : list[dict]):
        """Count each distinct card a run picked, in the act it picked it."""
        seen = {(p["act"], base_id(p["chosen"])) for p in picks if p["chosen"] != "SKIP"}
        for key in seen:
            self.table[key] = self.table.get(key, 0) + 1

    def merge(self, other : "Counts"):
        for key, n in other.table.items():
            self.table[key] = self.table.get(key, 0) + n

    def to_json(self) -> dict[str, int]:
        return {f"{act}|{cid}": n for (act, cid), n in self.table.items()}

    @classmethod
    def from_json(cls, data : dict[str, int]) -> "Counts":
        return cls({(int(k.split("|")[0]), k.split("|", 1)[1]): n for k, n in data.items()})


class Explorer:
    """`chooser` plus the exploration bonus `c / sqrt(n + 1)` and a flat chance `epsilon` of a uniform pick. `pick` returns the index (len(offered) = skip) and a record."""
    def __init__(self, chooser : CardChooser, counts : Counts, c : float = 0.5, epsilon : float = 0.05, seed : int | str = 0):
        self.chooser, self.counts, self.c, self.epsilon = chooser, counts, c, epsilon
        self.rng = random.Random(seed)

    def pick(self, snap : dict, offered : list[dict]) -> tuple[int, dict]:
        base = self.chooser.scores(snap, offered)
        bonus = [self.c / math.sqrt(self.counts.n(snap["act"], str(card.get("id"))) + 1) for card in offered] + [0.0]
        total = [b + x for b, x in zip(base, bonus)]
        best = max(range(len(base)), key=lambda i: base[i])
        if self.rng.random() < self.epsilon:
            index = self.rng.randrange(len(base))
        else:
            index = max(range(len(total)), key=lambda i: total[i])
        chosen = "SKIP" if index == len(offered) else card_key(offered[index])
        return index, {"act": snap["act"], "floor": snap["floor"], "offered": [card_key(c) for c in offered], "chosen": chosen,
                       "scores": [round(x, 4) for x in base], "bonus": [round(x, 4) for x in bonus], "exploratory": index != best}
