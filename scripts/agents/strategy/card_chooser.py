"""A card chooser on the strength model: take the card that most lowers what the act's big fights are expected to cost.

  make_chooser("strength:s1[:MARGIN]")     (the model saved in data/selfplay/models/strength/s1)

For a reward screen, the run as it is (snapshot: HP, deck, relics, act) faces the act's boss and its elites. Each offered card is scored by
    -(boss_weight * delta cost[boss] + elite_weight * mean over the act's elites of delta cost[elite])
delta being the change in the fight's expected cost (HP: P(lose) * HP + (1 - P(lose)) * HP lost if won) from adding the card (strength_model.delta),
and skipping scores MARGIN (default 0): a card is taken only when it saves more than MARGIN HP. Every card dilutes the deck (deck size moves the strength
too), so a weak card scores below skipping.

A card the variants never added at random (fewer than `min_random` times; model.randomized) has a value the model learnt from self-play decks alone,
where a card's presence goes with how the run went: it is scored as a card of no value of its own (it still dilutes), not by that value."""
from __future__ import annotations
import functools

import numpy as np

from agents.selfplay.choosers import base_id, card_key

NEUTRAL = "__NEUTRAL__"          # a card id outside any vocab: counts toward the deck size, adds no value


@functools.lru_cache(maxsize=4)
def load_strength(name : str):
    from agents.selfplay.suite import OUT_ROOT
    from agents.strategy.strength_model import StrengthModel
    folder = OUT_ROOT / "models" / "strength" / name
    if not (folder / "model.npz").exists():
        raise ValueError(f"no strength model at {folder} (fit one with: python -m agents.strategy.strength_model --out ...)")
    return StrengthModel.load(folder)


class StrengthChooser:
    def __init__(self, model, margin : float = 0.0, boss_weight : float = 1.0, elite_weight : float = 1.0, min_random : int = 30):
        self.model, self.margin, self.boss_weight, self.elite_weight, self.min_random = model, margin, boss_weight, elite_weight, min_random

    def trusted(self, key : str) -> bool:
        return self.model.randomized.get(base_id(key), 0) >= self.min_random

    def targets(self, snap : dict) -> list[tuple[dict, float]]:
        """(fight row, weight): the act's boss, and its elites sharing elite_weight."""
        before = dict(snap, room="Boss")
        out = [({"encounter": snap.get("boss"), "kind": "Boss", "before": before}, self.boss_weight)] if snap.get("boss") else []
        elites = self.model.elites.get(str(snap.get("boss"))) or self.model.elites.get(f"act:{snap.get('act')}") or [None]
        out += [({"encounter": e, "kind": "Elite", "before": dict(snap, room="Elite")}, self.elite_weight / len(elites)) for e in elites]
        return out

    def savings(self, snap : dict, keys : list[str]) -> np.ndarray:
        """HP saved over the act's big fights (weighted) by adding each card; positive helps."""
        targets = self.targets(snap)
        added = [k if self.trusted(k) else NEUTRAL for k in keys]
        rows = [dict(f, before=dict(f["before"], deck=list(snap["deck"]) + ([k] if k else []))) for f, _ in targets for k in [None] + added]
        c = self.model.predict(rows)["cost"].reshape(len(targets), len(keys) + 1)
        w = np.array([w for _, w in targets])
        return -(w @ (c[:, 1:] - c[:, :1]))

    def scores(self, snap, offered):
        return [float(x) for x in self.savings(snap, [card_key(c) for c in offered])] + [self.margin]
