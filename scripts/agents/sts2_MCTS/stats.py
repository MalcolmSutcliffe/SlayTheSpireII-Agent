"""The statistical constants and the paired-difference helper that the root-move checks (MCTS, order_check) share."""
import math

Z_SCORE = 2.33
TIE_MARGIN = 0.01                # root moves this close to the best (and not significantly worse) are tied
PAIRED_Z = Z_SCORE               # a contender replaces the picked move only when it is ahead by this many standard errors

# Batched paired comparisons (paired_check.py, order_check.py): the scenarios are replayed in batches and a line stops being replayed once it is settled.
SETTLE_Z = 3.0                   # a line is settled as ahead at this many standard errors: stricter than PAIRED_Z, as the test is repeated after every batch
SETTLE_REGRET = 0.005            # ... or when it is not expected to be ahead by more than this (reward units, a quarter of an HP at 50 HP)
SETTLE_MIN_SCENARIOS = 100       # ... but never before this many scenarios: a rare difference needs some to show up


def spread(diffs : list[float]) -> tuple[float, float]:
    """The mean of paired differences and its standard error."""
    count = len(diffs)
    mean = sum(diffs) / count
    var = sum((d - mean) ** 2 for d in diffs) / (count - 1)
    return mean, math.sqrt(var / count)


def expected_excess(mean : float, se : float) -> float:
    """E[max(0, X)] for X normal with this mean and standard deviation: what is expected to be gained by taking a move whose true value
    exceeds the leader's by X, when only `mean` and `se` of the difference are known. (se = 0: a known difference.)"""
    if se <= 0.0:
        return max(0.0, mean)
    d = mean / se
    return mean * 0.5 * (1.0 + math.erf(d / math.sqrt(2.0))) + se * math.exp(-0.5 * d * d) / math.sqrt(2.0 * math.pi)

def settled(diffs : list[float]) -> bool:
    """Nothing more is to be learned from replaying this line against the picked one: it is ahead (by SETTLE_Z standard errors), or it is
    not expected to be ahead by more than SETTLE_REGRET. `diffs` are its paired differences so far (its outcome minus the picked line's)."""
    if len(diffs) < max(2, SETTLE_MIN_SCENARIOS):
        return False
    mean, se = spread(diffs)
    return (mean > 0 and mean > SETTLE_Z * se) or expected_excess(mean, se) <= SETTLE_REGRET
