"""Single seedable random source for the simulator. Clones of a state share it."""
import random

_generator = random.Random()

# Number of random draws made so far; compare before and after an action to detect randomness.
calls = 0

def _counted(fn):
    def wrapper(*args, **kwargs):
        global calls
        calls += 1
        return fn(*args, **kwargs)
    return wrapper

seed = _generator.seed
getstate = _generator.getstate
setstate = _generator.setstate
shuffle = _counted(_generator.shuffle)
randrange = _counted(_generator.randrange)
choice = _counted(_generator.choice)
choices = _counted(_generator.choices)
