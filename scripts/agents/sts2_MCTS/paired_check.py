"""Paired comparison of the root moves.

The tree compares moves with independent noise: a move that is only a little better (Defend+ over Defend) is lost in the
draws and enemy rolls, and the visits settle on whichever got ahead early. Here the picked move and its close rivals are
replayed under the SAME scenarios (shuffle, random rolls) so that noise cancels in the difference. A rival replaces the
picked move only when it is ahead by PAIRED_Z standard errors of that paired difference.

Usage: PairedCheck(mcts).run(picked_root_child). The tree's line and the replay of a line come from the search (mcts)."""
import math

from sts2_lite import rng

from agents.sts2_MCTS.stats import PAIRED_Z, spread

PAIRED_VISIT_FRACTION = 0.05     # a root move needs this share of the picked move's visits to be a contender
PAIRED_MAX_CONTENDERS = 4        # contenders besides the picked move


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
        if n < 2 or not rivals:
            return None

        seeds = [rng.randrange(1 << 30) for _ in range(n)]      # fresh scenarios every time
        saved = rng.getstate()                                  # the rollouts reseed the shared source: put it back afterwards
        try:
            # each move is replayed along the line the tree found after it (the second Strike that is lethal), not as its first play
            # followed by the rollout policy, which need not find that line and then rates the move below one that is merely safe
            base = [mcts._paired_line_rollout(state, self._contender_line(picked), s) for s in seeds]
            results = []
            for rival in rivals:
                line = self._contender_line(rival)
                diffs = [mcts._paired_line_rollout(state, line, s) - b for s, b in zip(seeds, base)]
                mean, se = spread(diffs)
                results.append((rival, mean, se))
        finally:
            rng.setstate(saved)

        # a rival is significantly ahead of the picked move (a zero spread with a positive gap is a sure improvement)
        ahead = [r for r in results if r[1] > 0 and r[1] > PAIRED_Z * r[2]]
        best = max(ahead, key=lambda r: r[1] - PAIRED_Z * r[2]) if ahead else None
        return {
            "replaced" : best is not None,
            "child" : best[0] if best else picked,
            "scenarios" : n,
            "compared" : [{"action" : r[0].action, "visits" : r[0].visits, "gain" : r[1], "se" : r[2]} for r in results],
        }

    def _contender_line(self, node) -> list:
        """The root move `node` and the line the tree follows after it (see sts2_MCTS._principal_line), for the paired replay."""
        line, tail = self.mcts._principal_line(node)
        if not line:
            return [node.action]            # a random play: the move itself
        return line + ([tail] if tail is not None else [])
