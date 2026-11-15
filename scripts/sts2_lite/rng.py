"""The random source the simulator draws from. Clones of a state share it.

There is one active generator at a time. By default it is the *search* generator: what the agent's own look-ahead (MCTS, the deck evaluator) uses to
guess at things it cannot see. The sandbox swaps in one of the *game's* streams (`sts2_lite.run.GameRng`) with `use` while it resolves what really
happens, so the two never share a sequence and the agent cannot replay or correlate the game's outcomes."""
import random
from contextlib import contextmanager

_generator = random.Random()
_owner = "search"

# Number of random draws made so far; compare before and after an action to detect randomness.
calls = 0

def current() -> random.Random:
    """The generator draws are made from right now."""
    return _generator

def owner() -> str:
    """Who the active generator belongs to: "search" for the agent's own look-ahead, or "game:<stream>" while the sandbox resolves the real outcome."""
    return _owner

@contextmanager
def use(generator : random.Random, owner_name : str = "search"):
    """Draw from `generator` inside the block, then go back to the previous one (also when the block raises)."""
    global _generator, _owner
    previous = _generator, _owner
    _generator, _owner = generator, owner_name
    try:
        yield generator
    finally:
        _generator, _owner = previous

def _counted(name):
    def wrapper(*args, **kwargs):
        global calls
        calls += 1
        return getattr(_generator, name)(*args, **kwargs)
    wrapper.__name__ = name
    return wrapper

def seed(*args, **kwargs):
    return _generator.seed(*args, **kwargs)

def getstate():
    return _generator.getstate()

def setstate(state):
    return _generator.setstate(state)

shuffle = _counted("shuffle")
randrange = _counted("randrange")
choice = _counted("choice")
choices = _counted("choices")
sample = _counted("sample")
random_float = _counted("random")       # uniform float in [0.0, 1.0)

# Number of times one of several enemies was picked at random (Sword Boomerang, Juggernaut, ...): the bridge cannot tell which
target_rolls = 0

def pick_target(living):
    """One of `living` at random; no roll when there is only one."""
    global target_rolls
    if len(living) == 1:
        return living[0]
    target_rolls += 1
    return choice(living)
