"""Randomness of a sandbox run, split in two so the agent can never see the game's.

`GameRng` is what really happens: card rewards, shuffles, events, map, monster moves. Only the simulator holds it. It has one independent stream per
kind of draw (as the game has its own `RunRngSet`), derived from the run seed, so a new consumer of one stream never shifts the others and a run can be
replayed from its seed. The streams are *not* the game's generator, so a seed from a real run predicts nothing.

`SearchRng` is the agent's own: what it draws from when it simulates something it cannot see. It is never seeded from a `GameRng`.

    game = GameRng(seed=7)
    with game.scope("shuffle"):          # inside, the combat engine draws from the game's shuffle stream
        ...
    with search.scope():                 # inside, it draws from the agent's generator (the default)
        ...
"""
from __future__ import annotations

import hashlib
import random
import secrets
from contextlib import contextmanager

from sts2_lite import rng as sim_rng

STREAMS = (
    "up_front",                 # what is generated when an act starts: monsters, bosses, ancients
    "shuffle",                  # draw pile shuffles
    "combat",                   # everything the engine rolls inside a fight (shuffles, enemy moves, random targets)
    "unknown_room",             # the kind of room behind a "?" on the map
    "map",                      # map layout
    "combat_cards",             # cards made in combat (Attack Potion, Discovery)
    "combat_selection",         # random picks in combat (True Grit, Havoc)
    "combat_targets",           # random targets (Sword Boomerang)
    "combat_costs",             # random energy costs (Confused)
    "monster_ai",               # a monster's random choice of move
    "card_rewards",             # card rewards and the rarity roll
    "potion_rewards",
    "gold",                     # gold rewards
    "relics",                   # relic rewards and the relic bag
    "shop",
    "events",                   # event choice and the numbers an event rolls
    "ancients",                 # the options an ancient (Neow, Orobas, ...) offers
    "rest",
    "treasure",
    "niche",
)



class GameRng:
    """The game's random streams for one run. Never pass this, a stream, or the seed to an agent."""
    def __init__(self, seed : int | None = None):
        self._seed = secrets.randbits(63) if seed is None else int(seed)
        self._streams : dict[str, random.Random] = {}

    def stream(self, name : str) -> random.Random:
        if name not in STREAMS:
            raise KeyError(f"unknown stream {name!r}")
        found = self._streams.get(name)
        if found is None:
            digest = hashlib.sha256(f"{self._seed}/{name}".encode()).digest()
            found = self._streams[name] = random.Random(int.from_bytes(digest[:8], "big"))
        return found

    @contextmanager
    def scope(self, name : str):
        """Inside the block the simulator's own draws (`sts2_lite.rng`) come from this stream."""
        with sim_rng.use(self.stream(name), f"game:{name}") as generator:
            yield generator

    def getstate(self) -> dict[str, tuple]:
        """Every stream's state, to restore later (the verifier replays a run from a point)."""
        return {name: self.stream(name).getstate() for name in STREAMS}

    def setstate(self, state : dict[str, tuple]):
        for name, s in state.items():
            self.stream(name).setstate(s)

    @property
    def seed(self) -> int:
        """For logs and replays by the sandbox itself."""
        return self._seed

    def __repr__(self):
        return "GameRng(<hidden>)"


class SearchRng:
    """The agent's generator: for look-ahead only. Seed it for a reproducible tuning run; the default draws from the operating system."""
    def __init__(self, seed : int | None = None):
        if isinstance(seed, GameRng):
            raise TypeError("a SearchRng is never made from the game's rng")
        self.random = random.Random(seed)

    @contextmanager
    def scope(self):
        with sim_rng.use(self.random, "search") as generator:
            yield generator

    def spawn(self) -> "SearchRng":
        """An independent generator for a worker or one decision, seeded from this one (never from the game)."""
        return SearchRng(self.random.getrandbits(63))

    def __repr__(self):
        return "SearchRng()"
