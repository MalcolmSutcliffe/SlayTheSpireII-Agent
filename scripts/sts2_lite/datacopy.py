"""`copy.deepcopy` for the run's plain data (the deck, relics and potions: dicts and lists of strings and numbers), without its per-object dispatch.

The result is the same as copy.deepcopy's: a dict or a list met twice is copied once (the memo), keys are copied too, and anything that is not
a plain dict, list or atomic value (a tuple, an enum, a dict subclass, an object) is handed to copy.deepcopy with the same memo.

The fast path is `marshal`, which copies dicts, lists, strings and numbers in C, keeps the order of every dict, keeps floats bit for bit and
keeps a container that is met twice shared (marshal references any object it meets more than once). It refuses anything else (an enum, an
object, a dict or list subclass): that data goes the slower way below."""
from __future__ import annotations
import copy
import marshal

_ATOMIC = frozenset((str, int, float, bool, type(None)))


def _copy(x, memo : dict):
    cls = type(x)
    if cls in _ATOMIC:
        return x
    y = memo.get(id(x))
    if y is not None:
        return y
    if cls is dict:
        y = {}
        memo[id(x)] = y
        for k, v in x.items():
            y[k if type(k) in _ATOMIC else _copy(k, memo)] = v if type(v) in _ATOMIC else _copy(v, memo)
        _keep_alive(x, memo)
        return y
    if cls is list:
        y = []
        memo[id(x)] = y
        append = y.append
        for v in x:
            append(v if type(v) in _ATOMIC else _copy(v, memo))
        _keep_alive(x, memo)
        return y
    return copy.deepcopy(x, memo)


def _keep_alive(x, memo : dict):
    """What copy.deepcopy does after copying a container: the original is held in the memo, so its id cannot be reused while the copy runs."""
    try:
        memo[id(memo)].append(x)
    except KeyError:
        memo[id(memo)] = [x]


def deepcopy_data(x):
    """copy.deepcopy(x), faster for plain JSON-like data."""
    cls = type(x)
    if cls in _ATOMIC:
        return x
    if cls is list or cls is dict:
        try:
            return marshal.loads(marshal.dumps(x))
        except ValueError:          # something marshal does not know: copy it the slower way
            pass
    return _copy(x, {})
