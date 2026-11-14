"""What the deck choosers share: the fight pool, the evaluator, and drawing the same sample of upcoming fights for every option of a decision."""
from __future__ import annotations

from agents.deck_eval.evaluator import DeckEvaluator
from agents.deck_eval.fight_mix import mix_ahead, pick_fights
from agents.deck_eval.fight_pool import load_pool, target_types

DEFAULT_FIGHTS = 400


class DeckAdvisor:
    def __init__(self, fights : int = DEFAULT_FIGHTS, pool=None, route_provider=lambda: None, log=print):
        """`route_provider()` gives the pathing agent's PlannedRoute (what fights lie ahead), or None."""
        self.fights = fights
        self.pool = load_pool() if pool is None else pool
        self.evaluator = DeckEvaluator(self.pool, target_types(self.pool))
        self.route_provider = route_provider
        self.log = log
        self._calls = 0

    def sample(self, decision, fights : int | None = None):
        """(mix, fights, seed, ascension): `fights` (default: the advisor's) fights lying ahead of this decision; every option is played on all of them with the same dice."""
        ctx = decision.state.get("context") or decision.state.get("run") or {}
        mix = mix_ahead(ctx.get("act", 1), self.route_provider())
        self._calls += 1
        seed = 1000 + self._calls
        ascension = ctx.get("ascension", 0)
        return mix, pick_fights(self.pool, mix, fights or self.fights, seed, ascension), seed, ascension
