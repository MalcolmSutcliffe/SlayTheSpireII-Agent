"""Paired comparison of the root moves.

The tree compares moves with independent noise: a move that is only a little better (Defend+ over Defend) is lost in the
draws and enemy rolls, and the visits settle on whichever got ahead early. Here the picked move and its close rivals are
replayed under the SAME scenarios (shuffle, random rolls) so that noise cancels in the difference. A rival replaces the
picked move only when it is ahead by PAIRED_Z standard errors of that paired difference.

Usage: PairedCheck(mcts).run(picked_root_child). The tree's line and the replay of a line come from the search (mcts)."""
import math

from sts2_lite import rng

from agents.sts2_MCTS.parallel import Rollouts
from agents.sts2_MCTS.stats import PAIRED_Z, settled, spread

PAIRED_VISIT_FRACTION = 0.05     # a root move needs this share of the picked move's visits to be a contender
PAIRED_MAX_CONTENDERS = 4        # contenders besides the picked move


def _is_potion(node) -> bool:
    return node.action is not None and node.action.get("action") == "use_potion"


class PairedCheck:
    def __init__(self, mcts):
        self.mcts = mcts

    def run(self, picked) -> dict | None:
        """Compare `picked` with the root moves close to it in visits. Returns the details (and whether a rival `replaced` it),
        or None when there is nothing to compare."""
        mcts = self.mcts
        n = mcts._search_config.paired_scenarios
        state = mcts._root_node.state
        rivals = sorted((c for c in mcts._root_node.children
                         if c is not picked and c.visits >= max(1, PAIRED_VISIT_FRACTION * picked.visits)),
                        key=lambda c: -c.visits)[:PAIRED_MAX_CONTENDERS]
        if _is_potion(picked) and not any(not _is_potion(r) for r in rivals):
            # a potion needs a non-potion line to beat, however little the tree looked at it
            plain = sorted((c for c in mcts._root_node.children if c is not picked and not _is_potion(c)), key=lambda c: -c.visits)
            rivals = rivals + plain[:1]
        if n < 2 or not rivals:
            return None

        seeds = [rng.randrange(1 << 30) for _ in range(n)]      # fresh scenarios every time
        saved = rng.getstate()                                  # the rollouts reseed the shared source: put it back afterwards
        step = max(2, mcts._search_config.paired_batch) if mcts._search_config.paired_batch > 0 else n
        try:
            # each move is replayed along the line the tree found after it (the second Strike that is lethal), not as its first play
            # followed by the rollout policy, which need not find that line and then rates the move below one that is merely safe
            base_line = self._contender_line(picked)
            lines = [self._contender_line(rival) for rival in rivals]
            diffs = [[] for _ in rivals]
            open_rivals = list(range(len(rivals)))              # those still replayed: a rival that is settled is not replayed again
            base, ran = [], 0
            with Rollouts(mcts, state, mcts._search_config.check_workers) as rollouts:
                for start in range(0, n, step):
                    if not open_rivals:
                        break
                    chunk = seeds[start:start + step]
                    ran += len(chunk)
                    # the picked line and every open rival under the chunk's scenarios, all at once
                    jobs = [(base_line, s) for s in chunk] + [(lines[i], s) for i in open_rivals for s in chunk]
                    ratings = rollouts.run(jobs)
                    base = ratings[:len(chunk)]
                    for k, i in enumerate(list(open_rivals)):
                        rated = ratings[(k + 1) * len(chunk):(k + 2) * len(chunk)]
                        diffs[i] += [r - b for r, b in zip(rated, base)]
                        if step < n and settled(diffs[i]):
                            open_rivals.remove(i)
            results = []
            for rival, d in zip(rivals, diffs):
                mean, se = spread(d)
                results.append((rival, mean, se, len(d)))
        finally:
            rng.setstate(saved)

        # a rival is significantly ahead of the picked move (a zero spread with a positive gap is a sure improvement); a potion move
        # has to be further ahead (see _potion_bar)
        ahead = [r for r in results if r[1] > 0 and r[1] > self._bar(picked, r[0], r[2])]
        best = max(ahead, key=lambda r: r[1] - PAIRED_Z * r[2]) if ahead else None
        final = best[0] if best else picked
        if _is_potion(final):
            # a potion move is only played when it beats every non-potion line; otherwise the best of those is played
            plain = [(picked, 0.0, 0.0, n)] * (not _is_potion(picked)) + [r for r in results if not _is_potion(r[0])]
            gain, se = (best[1], best[2]) if best else (0.0, 0.0)
            if plain and not all(gain - p[1] > self._bar(picked, final, max(se, p[2])) for p in plain):
                best = self._fallback(plain, results, diffs, rivals, picked)
        return {
            "replaced" : best is not None,
            "child" : best[0] if best else picked,
            "scenarios" : n,                    # the most it replays; "scenarios_run" is how many the picked line was replayed under
            "scenarios_run" : ran,
            "compared" : [{"action" : r[0].action, "visits" : r[0].visits, "gain" : r[1], "se" : r[2], "n" : r[3]} for r in results],
        }

    def _fallback(self, plain, results, diffs, rivals, picked):
        """The non-potion move played when the potion is not justified: the tree's own favourite (most visited), unless another plain
        line is ahead of it by PAIRED_Z standard errors of their paired difference. Taking the best mean alone let a line the tree
        had barely visited (end_turn) replace the move it rated best, on noise."""
        plain_nodes = {id(p[0]) for p in plain}
        favourite = max((c for c in self.mcts._root_node.children if id(c) in plain_nodes or c is picked and not _is_potion(c)),
                        key=lambda c: c.visits, default=None)
        if favourite is None or favourite is picked:
            return None if favourite is picked else max(plain, key=lambda r: r[1])
        index = {id(r): i for i, r in enumerate(rivals)}
        fav_i = index.get(id(favourite))
        if fav_i is None:
            return next((r for r in plain if r[0] is favourite), max(plain, key=lambda r: r[1]))
        fav_result = next(r for r in results if r[0] is favourite)
        best = fav_result
        for r in plain:
            if r[0] is favourite:
                continue
            if r[0] is picked:          # the picked move is not a rival: the diffs are measured from it
                d = [-b for b in diffs[fav_i]]
            else:
                d = [a - b for a, b in zip(diffs[index[id(r[0])]], diffs[fav_i])]
            mean, se = spread(d)
            if mean > 0 and mean > PAIRED_Z * se and mean > best[1] - fav_result[1]:
                best = (r[0], r[1], r[2], r[3])
        return best

    def _bar(self, picked, move, se : float) -> float:
        """How far ahead of the reference a move has to be: PAIRED_Z standard errors, and for a potion move potion_z of them plus a
        minimum gain (a potion is gone once drunk, so a doubtful gain is not worth it)."""
        if not _is_potion(move):
            return PAIRED_Z * se
        gate = self.mcts._search_config.potions
        return gate.potion_z * se + gate.potion_min_gain_hp / max(1, self.mcts._starting_hp)

    def _contender_line(self, node) -> list:
        """The root move `node` and the line the tree follows after it (see sts2_MCTS._principal_line), for the paired replay."""
        line, tail = self.mcts._principal_line(node)
        if not line:
            return [node.action]            # a random play: the move itself
        return line + ([tail] if tail is not None else [])
