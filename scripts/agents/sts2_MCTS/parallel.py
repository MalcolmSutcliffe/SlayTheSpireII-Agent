from __future__ import annotations
"""Replaying lines under scenarios on several processes, for the paired check and the order check.

A replay (sts2_MCTS._paired_line_rollout) depends only on the state, the line and the seed, so the replays are independent and the
result does not depend on how many processes run them. The processes are forked once per check, after the search is done, so they
share the search object and the state as they are (copy on write) and only the lines and seeds go to them and the ratings come back.
Without `fork` (or with one worker) the replays run in this process, one after the other."""
import multiprocessing

_CONTEXT = None      # (mcts, state) of the pool being started: the forked processes inherit it


def _replay(job):
    mcts, state = _CONTEXT
    line, seed = job
    return mcts._paired_line_rollout(state, line, seed)


class Rollouts:
    """`with Rollouts(mcts, state, workers) as r: ratings = r.run([(line, seed), ...])` : the rating of each line replayed from `state`
    under its seed, in the order given."""

    def __init__(self, mcts, state, workers : int):
        self.mcts, self.state, self.workers = mcts, state, workers
        self.pool = None

    def __enter__(self):
        global _CONTEXT
        if self.workers > 1 and "fork" in multiprocessing.get_all_start_methods():
            _CONTEXT = (self.mcts, self.state)
            try:
                self.pool = multiprocessing.get_context("fork").Pool(self.workers)
            except (OSError, AssertionError):       # AssertionError: this process is a daemonic pool worker (a benchmark running on several processes), which may not have children: replay here
                self.pool = None
        return self

    def __exit__(self, *exc):
        global _CONTEXT
        if self.pool is not None:
            self.pool.terminate()
            self.pool.join()
            self.pool = None
        _CONTEXT = None
        return False

    def run(self, jobs : list) -> list[float]:
        if self.pool is None or len(jobs) < 2:
            return [self.mcts._paired_line_rollout(self.state, line, seed) for line, seed in jobs]
        return self.pool.map(_replay, jobs, chunksize=max(1, len(jobs) // (4 * self.workers)))
