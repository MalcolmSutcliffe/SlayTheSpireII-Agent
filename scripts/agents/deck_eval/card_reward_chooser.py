"""Picks a card reward by trying each choice (and skipping) on the same sample of upcoming fights.

A card is taken only when it clearly beats skipping: its average gain over the fights (each fight played with and without the card, same
dice) must exceed Z standard errors of that gain plus a floor. The floor falls as the deck grows (a card dilutes a big deck less) and as the deck's win rate falls (a weak deck needs the help)."""
from __future__ import annotations
import math
import time

from agents.decision import Decision, Option
from agents.deck_eval.advisor import DeckAdvisor

Z = 1.5                     # standard errors the gain has to clear (a wrong skip costs about as much as a wrong take)
FLOOR_AT_10_CARDS = 0.3     # reward points (a win is ~20, so 0.3 is ~1.5% of one): the smallest gain worth a card in a 10 card deck
EARLY_FLOOR_AT_10_CARDS = 0.15      # the same for the first EARLY_REWARDS card rewards of a run: a starter deck nearly always takes a card
EARLY_REWARDS = 3
MIN_FLOOR_DECK = 10
FULL_FLOOR_WIN_RATE = 0.8   # the floor applies in full from this win rate on the fights ahead; a weaker deck needs help, so the floor shrinks with it
BUDGET_SECONDS = 8.0        # thinking time of an ordinary card reward; the number of fights is set from it (a pilot of PILOT_FIGHTS measures the speed)
BIG_BUDGET_SECONDS = 15.0   # the first EARLY_REWARDS picks and the boss reward shape the whole run: they get longer
PILOT_FIGHTS = 100
MIN_FIGHTS, MAX_FIGHTS = 400, 12000
#              # sims per card reward (about 10 times what a quick decision needs)


def skip_floor(deck_size : int, early : bool = False, win_rate : float = 1.0) -> float:
    """The smallest gain worth a card: falls as the deck grows, and as the deck's win rate falls below FULL_FLOOR_WIN_RATE."""
    base = EARLY_FLOOR_AT_10_CARDS if early else FLOOR_AT_10_CARDS
    return base * MIN_FLOOR_DECK / max(MIN_FLOOR_DECK, deck_size) * min(1.0, win_rate / FULL_FLOOR_WIN_RATE)


def fights_for(budget : float, seconds_per_fight : float, decks : int) -> int:
    """How many fights fit the time budget when `decks` decks (every card on offer, and the deck as it is) each play all of them."""
    return int(min(MAX_FIGHTS, max(MIN_FIGHTS, budget / (max(seconds_per_fight, 1e-6) * decks))))


def paired_gain(with_card : list[float], without : list[float]) -> tuple[float, float]:
    """(mean gain, its standard error) over the fights both decks played."""
    diffs = [a - b for a, b in zip(with_card, without)]
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / max(1, n - 1)
    return mean, math.sqrt(var / n)


class CardRewardChooser:
    def __init__(self, fights : int | None = None, pool=None, route_provider=lambda: None, log=print, advisor : DeckAdvisor | None = None):
        self.advisor = advisor or DeckAdvisor(fights or 400, pool, route_provider, log)
        self.fights = fights        # a fixed number of fights (tests); None: as many as fit the time budget
        self.evaluator, self.log = self.advisor.evaluator, self.advisor.log
        self._rewards = 0           # card rewards decided in this run
        self._floor = 0

    def choose(self, decision : Decision) -> Option:
        player = decision.player
        deck = player.get("deck") or []
        floor = (decision.state.get("context") or decision.state.get("run") or {}).get("floor", 0)
        if floor < self._floor:         # a new run
            self._rewards = 0
        self._floor = floor
        early = self._rewards < EARLY_REWARDS
        self._rewards += 1
        route = self.advisor.route_provider()
        big = early or (route is not None and bool(route.kinds) and route.kinds[0] == "boss")
        count = self.fights
        if count is None:
            offered = sum(1 for o in decision.options if "id" in (o.data or {}))
            pilot = self.advisor.sample(decision, PILOT_FIGHTS)
            clock = time.perf_counter()
            self.evaluator.score(deck, player, pilot[1], pilot[2])
            count = fights_for(BIG_BUDGET_SECONDS if big else BUDGET_SECONDS, (time.perf_counter() - clock) / len(pilot[1]), offered + 1)
        mix, fights, seed, _ = self.advisor.sample(decision, count)
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
        needed = Z * best[1] + skip_floor(len(deck), early, base.win_rate) if best else 0.0
        take = best is not None and best[0] > needed
        chosen = best[2] if take else (skip or best[2])
        self.log("card reward act %d (weak %.0f normal %.0f elite %.0f boss %.1f, %d fights, %.1fs, base win %.0f%%): " %
                 (mix.act, mix.weak, mix.normal, mix.elite, mix.boss, len(fights), time.perf_counter() - start, 100 * base.win_rate) +
                 ", ".join("%s %+.2f±%.2f (win %.0f%%)" % (n, g, se, 100 * s.win_rate) for g, se, o, n, s in rows) +
                 (" | needs > %.2f -> %s" % (needed, "take " + best[3] if take else "skip")) if best else "no cards")
        return chosen
