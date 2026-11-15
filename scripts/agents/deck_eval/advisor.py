"""What the deck choosers share: the fight pool, the evaluator, and drawing the same sample of upcoming fights for every option of a decision."""
from __future__ import annotations

import random
import time

from agents.deck_eval.evaluator import DeckEvaluator
from agents.deck_eval.fight_mix import mix_ahead, pick_fights
from agents.deck_eval.fight_pool import load_pool, target_types
from agents.deck_eval.future_cards import fight_kinds
from agents.deck_eval.route_sim import sample_walks

DEFAULT_FIGHTS = 400
BATCH_WALKS = 2            # walks played at a time by `race` (the clock is checked between batches)
MAX_WALKS = 800            # most walks a race plays, whatever its time
MIN_WALKS = 6              # fewest walks through the route ahead a decision is played on


NOT_GIVEN = object()


class DeckAdvisor:
    def __init__(self, fights : int = DEFAULT_FIGHTS, pool=None, route_provider=lambda: None, log=print, seed : int | None = None):
        """`route_provider()` gives the pathing agent's PlannedRoute (what fights lie ahead), or None."""
        self.fights = fights
        self.pool = load_pool() if pool is None else pool
        self.evaluator = DeckEvaluator(self.pool, target_types(self.pool))
        self.route_provider = route_provider
        self.log = log
        self._calls = 0
        self.base = (random.SystemRandom().randrange(1, 10_000) if seed is None else seed) * 1_000_000       # every run draws its own walks: nothing of the real run's seed is in them, and the same `seed` replays the same walks

    def sample(self, decision, fights : int | None = None):
        """(mix, fights, seed, ascension): `fights` (default: the advisor's) fights lying ahead of this decision; every option is played on all of them with the same dice."""
        ctx = decision.state.get("context") or decision.state.get("run") or {}
        mix = mix_ahead(ctx.get("act", 1), self.route_provider())
        self._calls += 1
        seed = self.base + 1000 + self._calls
        ascension = ctx.get("ascension", 0)
        return mix, pick_fights(self.pool, mix, fights or self.fights, seed, ascension), seed, ascension

    def walks(self, decision, fights : int | None = None):
        """The walks through the rest of the act on the engine's run simulator (route_sim), as many as hold about `fights` fights. Each deck of a
        decision is played on all of them (DeckEvaluator.score_walks), so they compare walk by walk."""
        ctx = decision.state.get("context") or decision.state.get("run") or {}
        act, route = ctx.get("act", 1), self.route_provider()
        self._calls += 1
        seed = self.base + 5000 + self._calls
        count = max(MIN_WALKS, (fights or self.fights) // len(fight_kinds(route, act)))
        return sample_walks(route, act, ctx.get("ascension", 0), count, seed, ctx.get("floor", 1))

    def race(self, decision, candidates : dict, seconds : float, max_walks : int = MAX_WALKS, route=NOT_GIVEN) -> tuple[dict, int, float]:
        """Plays every candidate on the same fresh walks, a batch at a time, until `seconds` have passed (one batch is always played).
        `route`: the route the walks follow (default: the pathing agent's; None: a new act, as at an ancient's room). `candidates` maps a name to `play(walks) -> list of rewards`, one per walk. Returns ({name: rewards}, walks played, seconds taken):
        the lists are as long as the walks played, walk for walk, so they pair."""
        ctx = decision.state.get("context") or decision.state.get("run") or {}
        act = ctx.get("act", 1)
        route = self.route_provider() if route is NOT_GIVEN else route
        self._calls += 1
        seed, start = self.base + 7000 + self._calls * 1000, time.perf_counter()
        rewards = {name: [] for name in candidates}
        batch = 0
        while True:
            walks = sample_walks(route, act, ctx.get("ascension", 0), BATCH_WALKS, seed + batch, ctx.get("floor", 1))
            for name, play in candidates.items():
                rewards[name] += play(walks)
            batch += 1
            if time.perf_counter() - start >= seconds or batch * BATCH_WALKS >= max_walks:
                return rewards, batch * BATCH_WALKS, time.perf_counter() - start
