"""What a "?" room turns out to be (UnknownMapPointOdds): each room type's chance grows by its base odds every time it is not rolled, and falls back to the
base when it is. Elites have a negative base and are never rolled. Whatever the sum leaves is an event."""
from __future__ import annotations

from dataclasses import dataclass, field

MONSTER, ELITE, TREASURE, SHOP, EVENT = "Monster", "Elite", "Treasure", "Shop", "Event"
BASE_ODDS = {MONSTER: 0.1, ELITE: -1.0, TREASURE: 0.02, SHOP: 0.03}      # in the order the game rolls them


@dataclass
class UnknownRoomOdds:
    """The odds now (`current`) and what each falls back to (`base`). Draw with `roll(rng, blacklist)`."""
    current : dict[str, float] = field(default_factory=lambda: dict(BASE_ODDS))
    base : dict[str, float] = field(default_factory=lambda: dict(BASE_ODDS))

    @property
    def event_odds(self) -> float:
        return max(0.0, 1.0 - sum(v for v in self.current.values() if v > 0))

    def roll(self, rng, blacklist : frozenset[str] | set[str] = frozenset(), allowed : set[str] | None = None) -> str:
        """The room type of one "?" visited. `allowed` narrows the room types (a relic can) and `blacklist` removes some."""
        types = (set(self.current) | {EVENT}) - set(blacklist)
        if allowed is not None:
            types &= allowed | {EVENT}
        result = EVENT if EVENT in types else sorted(types)[0]
        x = rng.random()
        total = 0.0
        for room, odds in self.current.items():
            if room in types and odds >= 0:
                total += odds
                if x <= total:
                    result = room
                    break
        for room, base in self.base.items():
            if result == room:
                self.current[room] = base
            elif room in types and base >= 0:        # a type that can never be rolled stays where it is
                self.current[room] += base
        return result

    def reset(self):
        """Between acts."""
        self.current = dict(self.base)
