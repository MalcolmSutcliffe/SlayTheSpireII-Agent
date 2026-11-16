"""Picks a card reward by trying each choice (and skipping) on the same walks through the rest of the act.

The walks are played on the engine's run simulator (route_sim: the cards, relics and potions the deck gains on the way come from the engine's own
rewards); every option plays the same walks with the same dice, so the gains pair walk by walk. A card is taken only when it clearly beats skipping:
its mean gain must exceed `card_z` standard errors of that gain plus a floor. The floor falls as the deck's win rate falls (a weak deck needs the help).
A prospect bonus (prospect.py) adds the late pay-off of engine cards, which a walk through one act cannot see. The numbers are DeckEvalConfig's (config.py)."""
from __future__ import annotations
import time

from agents.decision import Decision, Option
from agents.deck_eval.advisor import DeckAdvisor, paired_gain  # noqa: F401  (paired_gain: re-exported for the tests)
from agents.deck_eval import prospect
from agents.deck_eval.config import DEFAULT, DeckEvalConfig
from agents.deck_eval.fight_mix import mix_ahead


def skip_floor(early : bool = False, win_rate : float = 1.0, config : DeckEvalConfig = DEFAULT) -> float:
    """The smallest gain worth a card: falls as the deck's win rate falls below config.full_floor_win_rate (the deck's size does not matter)."""
    return (config.card_early_floor if early else config.card_floor) * min(1.0, win_rate / config.full_floor_win_rate)


def fights_for(budget : float, seconds_per_fight : float, decks : int, config : DeckEvalConfig = DEFAULT) -> int:
    """How many fights fit the time budget when `decks` decks (every card on offer, and the deck as it is) each play all of them."""
    return int(min(config.max_fights, max(config.min_fights, budget / (max(seconds_per_fight, 1e-6) * decks))))


class CardRewardChooser:
    def __init__(self, fights : int | None = None, pool=None, route_provider=lambda: None, log=print, advisor : DeckAdvisor | None = None):
        self.advisor = advisor or DeckAdvisor(fights, pool, route_provider, log)
        self.fights = fights        # a fixed number of fights (tests); None: as many as fit the time budget
        self.evaluator, self.log, self.config = self.advisor.evaluator, self.advisor.log, self.advisor.config
        self._rewards = 0           # card rewards decided in this run
        self._floor = 0

    def choose(self, decision : Decision) -> Option:
        player = decision.player
        deck = player.get("deck") or []
        ctx = decision.state.get("context") or decision.state.get("run") or {}
        floor = ctx.get("floor", 0)
        if floor < self._floor:         # a new run
            self._rewards = 0
        self._floor = floor
        cfg = self.config
        early = self._rewards < cfg.early_rewards
        self._rewards += 1
        route = self.advisor.route_provider()
        big = early or (route is not None and bool(route.kinds) and route.kinds[0] == "boss")
        skip = next((o for o in decision.options if o.action.get("action") == "skip_card_reward"), None)
        count = self.fights if self.fights is not None else self._fights_in_budget(decision, deck, player, big)
        start = time.perf_counter()
        future = self.future_rows(decision, deck, player, route, skip, count)
        base = future["base"]
        bonuses = {id(r[2]): prospect.bonus(r[2].data or {}, deck, floor, base.win_rate, r[0], cfg) for r in future["rows"]}      # late pay-off the walks cannot see
        rows = [(g + bonuses[id(o)], se, o, n, sc) for g, se, o, n, sc in future["rows"]]
        best = max(rows, key=lambda r: r[0], default=None)
        if best is None:
            return skip or decision.options[0]
        needed = cfg.card_z * best[1] + skip_floor(early, base.win_rate, cfg)
        take = best[0] > needed
        chosen = best[2] if take else (skip or best[2])
        mix = mix_ahead(ctx.get("act", 1), route)
        self.log("card reward act %d (weak %.0f normal %.0f elite %.0f%s boss %.1f%s, %d fights, %.1fs, base win %.0f%%) | needs > %.2f -> %s" %
                 (mix.act, mix.weak, mix.normal, mix.elite, " [" + "/".join(mix.elites) + "]" if mix.elites else "", mix.boss, " [" + mix.boss_id + "]" if mix.boss_id else "",
                  len(future["fights"]), time.perf_counter() - start, 100 * base.win_rate, needed, "take " + best[3] if take else "skip"))
        self.log("  walking the rest of the act (%d walks of %.1f fights, %.0f%% get through): " %
                 (future["walks"], len(future["fights"]) / max(1, future["walks"]), 100 * base.win_rate) +
                 ", ".join("%s %+.2f±%.2f (win %.0f%%)" % (n, g, se, 100 * s.win_rate) for g, se, o, n, s in future["rows"]) +
                 ("; prospect bonus " + ", ".join("%s %+.2f" % (n, bonuses.get(id(o), 0)) for g, se, o, n, s in future["rows"] if bonuses.get(id(o))) if any(bonuses.values()) else ""))
        return chosen

    def _fights_in_budget(self, decision : Decision, deck : list[dict], player : dict, big : bool) -> int:
        """How many fights fit this reward's time budget: a pilot of config.pilot_fights fights measures how fast this deck plays."""
        cfg = self.config
        offered = sum(1 for o in decision.options if "id" in (o.data or {}))
        _, fights, seed, _ = self.advisor.sample(decision, cfg.pilot_fights)
        clock = time.perf_counter()
        self.evaluator.score(deck, player, fights, seed)
        return fights_for(cfg.card_big_seconds if big else cfg.card_seconds, (time.perf_counter() - clock) / len(fights), offered + 1, cfg)

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
