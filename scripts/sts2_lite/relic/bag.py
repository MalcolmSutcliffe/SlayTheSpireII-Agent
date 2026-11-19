"""Where a relic the game "draws" comes from: the relic grab bag (RelicGrabBag + RelicFactory).

At the start of a run the shared pool and the character's pool are split by rarity and each deque is shuffled once. Relic rewards (elites, treasure, events)
pull from the front of the deque of a rolled rarity, shops from the back; a pulled relic is never seen again. A deque with nothing allowed falls through to the
next rarity (Shop -> Common -> Uncommon -> Rare -> none) and, with nothing at all, to the fallback relic (Circlet)."""
from __future__ import annotations

from typing import Callable

from sts2_lite.relic.pool_data import POOL

RARITIES = ("Common", "Uncommon", "Rare", "Shop")       # the rarities the bag holds
FALLBACK_RELIC = "CIRCLET"
ACT_3_TREASURE_FLOOR = 41           # IsBeforeAct3TreasureChest: TotalFloor < 41 (single player)
RARITY_AFTER = {"Shop": "Common", "Common": "Uncommon", "Uncommon": "Rare"}

RELIC_INFO = {rid: {"rarity": rarity, "shops": shops, "early_only": early, "pool": pool} for rid, rarity, shops, early, pool in POOL}
MERCHANT_BASE_COST = {"Common": 175, "Uncommon": 225, "Rare": 275, "Shop": 200}


def is_allowed(relic_id : str, run) -> bool:
    """RelicModel.IsAllowed(runState): the relics that lose their value late in a run are no longer offered from floor 41 on."""
    info = RELIC_INFO.get(relic_id)
    return not (info and info["early_only"] and run.floor >= ACT_3_TREASURE_FLOOR)


def roll_rarity(rng) -> str:
    """RelicFactory.RollRarity: 50% common, 33% uncommon, 17% rare."""
    x = rng.random()
    return "Common" if x < 0.5 else ("Uncommon" if x < 0.83 else "Rare")


class RelicGrabBag:
    def __init__(self, rng, character : str = "IRONCLAD"):
        self.rng = rng          # the game's "relics" stream: the rarity rolls
        self.deques : dict[str, list[str]] = {r: [] for r in RARITIES}
        for rid, info in RELIC_INFO.items():
            if info["pool"] == "shared" or info["pool"] == character.lower():
                if info["rarity"] in self.deques:
                    self.deques[info["rarity"]].append(rid)
        for deque in self.deques.values():
            rng.shuffle(deque)

    def remove(self, relic_id : str):
        for deque in self.deques.values():
            while relic_id in deque:
                deque.remove(relic_id)

    def _available(self, rarity : str, run, accept : Callable[[str], bool]) -> list[str] | None:
        for deque in self.deques.values():
            deque[:] = [r for r in deque if is_allowed(r, run)]
        while rarity != "None":
            deque = self.deques.get(rarity, [])
            if any(accept(r) for r in deque):
                return deque
            rarity = RARITY_AFTER.get(rarity, "None")
        return None

    def pull(self, rarity : str, run, from_back : bool = False, accept : Callable[[str], bool] = lambda r: True) -> str:
        deque = self._available(rarity, run, accept)
        if deque is None:
            return FALLBACK_RELIC
        for i in (range(len(deque) - 1, -1, -1) if from_back else range(len(deque))):
            if accept(deque[i]):
                return deque.pop(i)
        return FALLBACK_RELIC


def pull_relic(run, rarity : str | None = None, from_back : bool = False, accept : Callable[[str], bool] = lambda r: True) -> str:
    """RelicFactory.PullNextRelicFromFront / FromBack: a relic of `rarity` (rolled when None) that the run has not met."""
    bag = run.hidden.relic_bag
    relic = bag.pull(rarity or roll_rarity(bag.rng), run, from_back, lambda r: accept(r) and not run.has_relic(r))
    bag.remove(relic)
    return relic


def relic_name(relic_id : str) -> str:
    return relic_id.replace("_", " ").title().replace(" Of ", " of ").replace(" The ", " the ")
