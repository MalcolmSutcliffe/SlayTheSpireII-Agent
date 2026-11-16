"""A bonus for taking a card that pays off late (a scaling Power, an engine piece), which the walks cannot see: they play the rest of the act only.

`prospective_cards.csv` (next to this file) holds the value of each card, 0 to 1 in the `prospect` column (empty: 0). The bonus of a card on offer, in the reward points the walk gains are in:

    bonus = PROSPECT_SCALE * value * time_weight(progress) * margin_weight(win_rate) / (1 + value of the prospective cards the deck holds already)

- time_weight: 1 at the start of the run, falling to 0 at PROSPECT_END of it (a late pick has no fights left to pay off in).
- margin_weight: 0 while the deck loses the walks ahead (WIN_LOW), 1 once it wins them comfortably (WIN_HIGH): a deck that is dying now must not invest.
- held cards: the second and third engine pieces are worth less than the first.
- VETO: a card whose walk gain is below -VETO gets no bonus at all (it hurts too much now).

All constants are module-level so the benchmarks can sweep them (`--set agents.deck_eval.prospect.PROSPECT_SCALE=0.2`). PROSPECT_SCALE = 0 turns the whole thing off."""
from __future__ import annotations
import csv
from functools import lru_cache
from pathlib import Path

TABLE = Path(__file__).with_name("prospective_cards.csv")
PROSPECT_SCALE = 0.10       # reward points of a value-1 card at the start of a winning run (a good short-term pick gains about 0.03 to 0.1)
PROSPECT_END = 0.8          # share of the run (floors / RUN_FLOORS) at which the time weight reaches 0
RUN_FLOORS = 48
WIN_LOW, WIN_HIGH = 0.5, 0.85
VETO = 0.03


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


def time_weight(floor : int) -> float:
    return max(0.0, 1.0 - (floor / RUN_FLOORS) / PROSPECT_END)


def margin_weight(win_rate : float) -> float:
    return max(0.0, min(1.0, (win_rate - WIN_LOW) / (WIN_HIGH - WIN_LOW)))


def bonus(card : dict, deck : list[dict], floor : int, win_rate : float, gain : float = 0.0) -> float:
    """The bonus for taking `card` into `deck` (its walk gain `gain`): 0 when it is not prospective, the deck is losing, or the card hurts now."""
    v = value(card)
    if v <= 0 or PROSPECT_SCALE <= 0 or gain < -VETO:
        return 0.0
    held = sum(value(c) for c in deck)
    return PROSPECT_SCALE * v * time_weight(floor) * margin_weight(win_rate) / (1.0 + held)
