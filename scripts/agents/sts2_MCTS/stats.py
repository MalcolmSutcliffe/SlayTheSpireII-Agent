"""The statistical constants and the paired-difference helper that the root-move checks (MCTS, order_check) share."""
import math

Z_SCORE = 2.33
TIE_MARGIN = 0.01                # root moves this close to the best (and not significantly worse) are tied
PAIRED_Z = Z_SCORE               # a contender replaces the picked move only when it is ahead by this many standard errors


def spread(diffs : list[float]) -> tuple[float, float]:
    """The mean of paired differences and its standard error."""
    count = len(diffs)
    mean = sum(diffs) / count
    var = sum((d - mean) ** 2 for d in diffs) / (count - 1)
    return mean, math.sqrt(var / count)
