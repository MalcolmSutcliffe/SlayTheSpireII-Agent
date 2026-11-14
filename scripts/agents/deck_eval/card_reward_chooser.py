"""Picks a card reward by trying each choice (and skipping) on the same sample of upcoming fights.

A card is taken only when it clearly beats skipping: its average gain over the fights (each fight played with and without the card, same
dice) must exceed Z standard errors of that gain plus a floor. The floor falls as the deck grows, since a card dilutes a big deck less."""
from __future__ import annotations
import math
import time

from agents.decision import Decision, Option
from agents.deck_eval.advisor import DeckAdvisor, DEFAULT_FIGHTS

Z = 2.0                     # standard errors the gain has to clear
FLOOR_AT_10_CARDS = 0.3     # reward points (a win is ~20, so 0.3 is ~1.5% of one): the smallest gain worth a card in a 10 card deck
MIN_FLOOR_DECK = 10


def skip_floor(deck_size : int) -> float:
    return FLOOR_AT_10_CARDS * MIN_FLOOR_DECK / max(MIN_FLOOR_DECK, deck_size)


def paired_gain(with_card : list[float], without : list[float]) -> tuple[float, float]:
    """(mean gain, its standard error) over the fights both decks played."""
    diffs = [a - b for a, b in zip(with_card, without)]
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / max(1, n - 1)
    return mean, math.sqrt(var / n)


class CardRewardChooser:
    def __init__(self, fights : int = DEFAULT_FIGHTS, pool=None, route_provider=lambda: None, log=print, advisor : DeckAdvisor | None = None):
        self.advisor = advisor or DeckAdvisor(fights, pool, route_provider, log)
        self.evaluator, self.log = self.advisor.evaluator, self.advisor.log

    def choose(self, decision : Decision) -> Option:
        player = decision.player
        deck = player.get("deck") or []
        mix, fights, seed, _ = self.advisor.sample(decision)
        start = time.perf_counter()
        skip = next((o for o in decision.options if o.action.get("action") == "skip_card_reward"), None)
        base = self.evaluator.score(deck, player, fights, seed)
        rows = []       # (gain, se, option, name, score)
        for opt in decision.options:
            card = opt.data or {}
            if opt is skip or "id" not in card:
                continue
            score = self.evaluator.score(deck + [card], player, fights, seed)
            gain, se = paired_gain(score.rewards, base.rewards)
            rows.append((gain, se, opt, card.get("name", opt.label), score))
        best = max(rows, key=lambda r: r[0], default=None)
        if best is None:
            return skip or decision.options[0]
        needed = Z * best[1] + skip_floor(len(deck)) if best else 0.0
        take = best is not None and best[0] > needed
        chosen = best[2] if take else (skip or best[2])
        self.log("card reward act %d (weak %.0f normal %.0f elite %.0f boss %.1f, %d fights, %.1fs, base win %.0f%%): " %
                 (mix.act, mix.weak, mix.normal, mix.elite, mix.boss, len(fights), time.perf_counter() - start, 100 * base.win_rate) +
                 ", ".join("%s %+.2f±%.2f (win %.0f%%)" % (n, g, se, 100 * s.win_rate) for g, se, o, n, s in rows) +
                 (" | needs > %.2f -> %s" % (needed, "take " + best[3] if take else "skip")) if best else "no cards")
        return chosen
