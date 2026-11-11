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
sample = _counted(_generator.sample)
random_float = _counted(_generator.random)       # uniform float in [0.0, 1.0)

# Number of times one of several enemies was picked at random (Sword Boomerang, Juggernaut, ...): the bridge cannot tell which
target_rolls = 0

def pick_target(living):
    """One of `living` at random; no roll when there is only one."""
    global target_rolls
    if len(living) == 1:
        return living[0]
    target_rolls += 1
    return choice(living)
