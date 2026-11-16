"""A bonus for taking a card that pays off late (a scaling Power, an engine piece), which the walks cannot see: they play the rest of the act only.

`prospective_cards.csv` (next to this file) holds the value of each card, 0 to 1 in the `prospect` column (empty: 0). The bonus of a card on offer, in the reward points the walk gains are in:

    bonus = prospect_scale * value * time_weight(progress) * margin_weight(win_rate) / (1 + value of the prospective cards the deck holds already)

- time_weight: 1 at the start of the run, falling to 0 at `prospect_end` of it (a late pick has no fights left to pay off in).
- margin_weight: 0 while the deck loses the walks ahead (`prospect_win_low`), 1 once it wins them comfortably (`prospect_win_high`): a deck that is dying now must not invest.
- held cards: the second and third engine pieces are worth less than the first.
- veto: a card whose walk gain is below -`prospect_veto` gets no bonus at all (it hurts too much now).

The numbers are DeckEvalConfig's (config.py); the benchmarks sweep them with `--deck prospect_scale=0.2`. prospect_scale = 0 turns the whole thing off."""
from __future__ import annotations
import csv
from functools import lru_cache
from pathlib import Path

from agents.deck_eval.config import DEFAULT, DeckEvalConfig

TABLE = Path(__file__).with_name("prospective_cards.csv")


@lru_cache(maxsize=1)
def values(path : str = str(TABLE)) -> dict[str, float]:
    """{card id: value} from the table; a card without a number is worth 0."""
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            text = (row.get("prospect") or "").strip()
            if text:
                out[row["id"]] = max(0.0, min(1.0, float(text)))
    return out


def value(card : dict) -> float:
    return values().get(card.get("id", ""), 0.0)


def time_weight(floor : int, config : DeckEvalConfig = DEFAULT) -> float:
    return max(0.0, 1.0 - (floor / config.run_floors) / config.prospect_end)


def margin_weight(win_rate : float, config : DeckEvalConfig = DEFAULT) -> float:
    low, high = config.prospect_win_low, config.prospect_win_high
    return max(0.0, min(1.0, (win_rate - low) / (high - low)))


def bonus(card : dict, deck : list[dict], floor : int, win_rate : float, gain : float = 0.0, config : DeckEvalConfig = DEFAULT) -> float:
    """The bonus for taking `card` into `deck` (its walk gain `gain`): 0 when it is not prospective, the deck is losing, or the card hurts now."""
    v = value(card)
    if v <= 0 or config.prospect_scale <= 0 or gain < -config.prospect_veto:
        return 0.0
    held = sum(value(c) for c in deck)
    return config.prospect_scale * v * time_weight(floor, config) * margin_weight(win_rate, config) / (1.0 + held)
