"""Picks a card reward by trying each choice (and skipping) on the same sample of upcoming fights.

A card is taken only when it clearly beats skipping: its average gain over the fights (each fight played with and without the card, same
dice) must exceed Z standard errors of that gain plus a floor. The floor falls as the deck's win rate falls (a weak deck needs the help).

With USE_FUTURE the fights are walks through the rest of the act on the engine's run simulator (route_sim: the cards, relics and potions the deck gains on the way come from the engine's own rewards),
and the current-deck pass is skipped altogether: every fight of the time budget goes to the future-deck pass."""
from __future__ import annotations
import math
import time

from agents.decision import Decision, Option
from agents.deck_eval.advisor import DeckAdvisor

Z = 1.5                     # standard errors the gain has to clear (a wrong skip costs about as much as a wrong take)
FLOOR = 0.3                 # reward points (a win is ~20, so 0.3 is ~1.5% of one): the smallest gain worth a card
EARLY_FLOOR = 0.15          # the same for the first EARLY_REWARDS card rewards of a run: a starter deck nearly always takes a card
EARLY_REWARDS = 3
FULL_FLOOR_WIN_RATE = 0.8   # the floor applies in full from this win rate on the fights ahead; a weaker deck needs help, so the floor shrinks with it
BUDGET_SECONDS = 8.0        # thinking time of an ordinary card reward; the number of fights is set from it (a pilot of PILOT_FIGHTS measures the speed)
BIG_BUDGET_SECONDS = 15.0   # the first EARLY_REWARDS picks and the boss reward shape the whole run: they get longer
PILOT_FIGHTS = 100
USE_FUTURE = True           # True: decide on the future-deck gain alone (the whole budget, no current-deck pass); False: decide on the current deck and also log the future-deck gain
FUTURE_SHARE = 0.5          # with USE_FUTURE False: the log-only future-deck pass gets this share of the fights of the main pass, and of the time budget
MIN_FIGHTS, MAX_FIGHTS = 400, 12000
MIN_FUTURE_FIGHTS = 200     # with USE_FUTURE False: fewest fights of the log-only future-deck pass (a fixed `fights`, as tests use, scales it down instead)
#              # sims per card reward (about 10 times what a quick decision needs)


def skip_floor(early : bool = False, win_rate : float = 1.0) -> float:
    """The smallest gain worth a card: falls as the deck's win rate falls below FULL_FLOOR_WIN_RATE (the deck's size does not matter)."""
    return (EARLY_FLOOR if early else FLOOR) * min(1.0, win_rate / FULL_FLOOR_WIN_RATE)


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
            count = fights_for(BIG_BUDGET_SECONDS if big else BUDGET_SECONDS, (time.perf_counter() - clock) / len(pilot[1]), (offered + 1) * (1 if USE_FUTURE else 1 + FUTURE_SHARE))
        mix, fights, seed, _ = self.advisor.sample(decision, 1 if USE_FUTURE else count)       # the mix for the log (the future pass draws its own fights)
        start = time.perf_counter()
        skip = next((o for o in decision.options if o.action.get("action") == "skip_card_reward"), None)
        base, rows = None, []       # the current-deck pass: rows are (gain, se, option, name, score); not played when the future-deck pass decides
        if not USE_FUTURE:
            base = self.evaluator.score(deck, player, fights, seed)
            for opt in decision.options:
                card = opt.data or {}
                if opt is skip or "id" not in card:
                    continue
                score = self.evaluator.score(deck + [card], player, fights, seed)
                gain, se = paired_gain(score.rewards, base.rewards)
                rows.append((gain, se, opt, card.get("name", opt.label), score))
        if USE_FUTURE:
            future_fights = count
        else:
            future_fights = max(1, int(count * FUTURE_SHARE)) if self.fights is not None else max(MIN_FUTURE_FIGHTS, int(count * FUTURE_SHARE))
        future = self.future_rows(decision, deck, player, route, skip, future_fights)
        deciding = future if USE_FUTURE else {"rows": rows, "base": base, "fights": fights}
        best = max(deciding["rows"], key=lambda r: r[0], default=None)
        if best is None:
            return skip or decision.options[0]
        needed = Z * best[1] + skip_floor(early, deciding["base"].win_rate)
        take = best[0] > needed
        chosen = best[2] if take else (skip or best[2])
        self.log("card reward act %d (weak %.0f normal %.0f elite %.0f%s boss %.1f%s, %d fights, %.1fs, base win %.0f%%)%s | needs > %.2f -> %s" %
                 (mix.act, mix.weak, mix.normal, mix.elite, " [" + "/".join(mix.elites) + "]" if mix.elites else "", mix.boss, " [" + mix.boss_id + "]" if mix.boss_id else "", len(deciding["fights"]), time.perf_counter() - start, 100 * deciding["base"].win_rate,
                  (": " + ", ".join("%s %+.2f±%.2f (win %.0f%%)" % (n, g, se, 100 * s.win_rate) for g, se, o, n, s in rows)) if rows else "",
                  needed, "take " + best[3] if take else "skip"))
        self.log("  walking the rest of the act (%d walks of %.1f fights, %.0f%% get through): " %
                 (future["walks"], len(future["fights"]) / max(1, future["walks"]), 100 * future["base"].win_rate) +
                 ", ".join("%s %+.2f±%.2f (win %.0f%%)" % (n, g, se, 100 * s.win_rate) for g, se, o, n, s in future["rows"]))
        return chosen

    def future_rows(self, decision : Decision, deck : list[dict], player : dict, route, skip, count : int) -> dict:
        """Each option's gain over the deck as it is, on walks through the rest of the act on the engine's run simulator (route_sim): the fights one after the
        other with the HP carried over, the rest sites, the treasure room, the potions, gold and card rewards, and the relics the elites drop, all as the engine
        does them. A deck is rated by how far it gets and how healthy, so the fights it is weakest in weigh the most (the ones it dies in cost it all the fights
        after them). `count` is the fights to play: the walks are as many as fit. Returns the rows, the base score, the walks and their fights."""
        walks = self.advisor.walks(decision, count)
        base = self.evaluator.score_walks(deck, player, walks)
        rows = []
        for opt in decision.options:
            card = opt.data or {}
            if opt is skip or "id" not in card:
                continue
            score = self.evaluator.score_walks(deck + [card], player, walks)
            gain, se = paired_gain(score.rewards, base.rewards)
            rows.append((gain, se, opt, card.get("name", opt.label), score))
        return {"rows": rows, "base": base, "fights": [f for w in walks for f in range(w.fights)], "walks": len(walks)}
