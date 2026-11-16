"""What the deck choosers share: the fight pool, the evaluator, and drawing the same sample of upcoming fights for every option of a decision."""
from __future__ import annotations

import math
import random
import time

from agents.deck_eval.config import DEFAULT, DeckEvalConfig
from agents.deck_eval.evaluator import DeckEvaluator
from agents.deck_eval.fight_mix import mix_ahead, pick_fights
from agents.deck_eval.fight_pool import load_pool, target_types
from agents.deck_eval.future_cards import fight_kinds
from agents.deck_eval.route_sim import sample_walks

NOT_GIVEN = object()


class DeckAdvisor:
    def __init__(self, fights : int | None = None, pool=None, route_provider=lambda: None, log=print, seed : int | None = None, config : DeckEvalConfig = DEFAULT):
        """`route_provider()` gives the pathing agent's PlannedRoute (what fights lie ahead), or None. `config` tunes every chooser sharing this advisor
        and the walks they are judged on; `fights` (default: config.default_fights) is how many fights a decision is played on when its chooser does not say."""
        self.config = config
        self.fights = config.default_fights if fights is None else fights
        self.pool = load_pool() if pool is None else pool
        self.evaluator = DeckEvaluator(self.pool, target_types(self.pool), config=config)
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
        count = max(self.config.min_walks, (fights or self.fights) // len(fight_kinds(route, act)))
        return sample_walks(route, act, ctx.get("ascension", 0), count, seed, ctx.get("floor", 1))

    def race(self, decision, candidates : dict, seconds : float, max_walks : int | None = None, route=NOT_GIVEN) -> tuple[dict, int, float]:
        """Plays every candidate on the same fresh walks, a batch at a time, until `seconds` have passed (one batch is always played).
        `max_walks`: default config.max_walks. `route`: the route the walks follow (default: the pathing agent's; None: a new act, as at an ancient's room). `candidates` maps a name to `play(walks) -> list of rewards`, one per walk. Returns ({name: rewards}, walks played, seconds taken):
        the lists are as long as the walks played, walk for walk, so they pair."""
        ctx = decision.state.get("context") or decision.state.get("run") or {}
        act = ctx.get("act", 1)
        route = self.route_provider() if route is NOT_GIVEN else route
        self._calls += 1
        seed, start = self.base + 7000 + self._calls * 1000, time.perf_counter()
        rewards = {name: [] for name in candidates}
        per_batch, max_walks = self.config.batch_walks, self.config.max_walks if max_walks is None else max_walks
        batch = 0
        while True:
            walks = sample_walks(route, act, ctx.get("ascension", 0), per_batch, seed + batch, ctx.get("floor", 1))
            for name, play in candidates.items():
                rewards[name] += play(walks)
            batch += 1
            if time.perf_counter() - start >= seconds or batch * per_batch >= max_walks:
                return rewards, batch * per_batch, time.perf_counter() - start


def paired_gain(with_card : list[float], without : list[float]) -> tuple[float, float]:
    """(mean gain, its standard error) over the fights both decks played."""
    diffs = [a - b for a, b in zip(with_card, without)]
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / max(1, n - 1)
    return mean, math.sqrt(var / n)
