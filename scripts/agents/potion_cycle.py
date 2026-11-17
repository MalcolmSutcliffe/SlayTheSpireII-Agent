"""Potion cycling on the rewards screen: what to drink or throw away so a better potion fits on the belt.

  - Fruit Juice (+max HP) is drunk as soon as the agent holds it: it is worth the same now as later.
  - A Foul Potion is used in a shop: the merchant pays 100 gold for each one thrown at him (`foul_at_shop`).
  - With the belt full and a potion on offer, a Blood Potion or Fruit Juice is drunk first (they can be used out of combat, so the slot is freed at no loss);
    otherwise the held potion of the least value is thrown away when the offered one is worth more (RewardParams.potion_bonus, the same prices as the shop's).
The game lets only potions with `PotionUsage.AnyTime` be drunk outside a fight (Blood Potion and Fruit Juice, as far as the decompiled game shows), so no other potion is ever drunk here.
The actions are `use_potion` and `discard_potion` with the belt slot (agent_runner/executors.py sends them; the bridge's `discard_potion` is in BridgeMod.Actions.cs)."""
from __future__ import annotations

from sts2_lite.potion import PotionId

from agents.decision import Decision, Option, potion_option
from agents.sts2_MCTS.params import RewardParams

PRICES = RewardParams()
DRINK_FIRST = (PotionId.BLOOD_POTION, PotionId.FRUIT_JUICE)          # drunk before anything is thrown away
DRINK_AT_ONCE = (PotionId.FRUIT_JUICE,)


def potion_of(entry : dict) -> PotionId | None:
    """The potion of a belt entry or a reward / shop item."""
    return PotionId.from_game_id(entry.get("potion_id") or entry.get("id"))

def value(entry : dict) -> float:
    potion = potion_of(entry)
    return PRICES.potion_bonus.get(potion, PRICES.default_potion_bonus)

def _drink(entry : dict) -> Option:
    return potion_option("use", entry)

def _discard(entry : dict) -> Option:
    return potion_option("discard", entry)

def held(decision : Decision) -> list[dict]:
    return [p for p in decision.player.get("potions") or [] if p and p.get("slot") is not None]

def cycle(decision : Decision) -> Option | None:
    """The potion action to take on this rewards screen (drink, or throw away), or None to go on with the rewards."""
    belt = held(decision)
    for p in belt:
        if potion_of(p) in DRINK_AT_ONCE:
            return _drink(p)
    if decision.player.get("open_potion_slots") != 0 or not belt:
        return None                                  # room for it: the potion is simply claimed
    offered = [item for item in decision.state.get("items") or [] if item.get("type") == "potion"]
    if not offered or any(r.get("id") == "SOZU" for r in decision.player.get("relics") or [] if isinstance(r, dict)):
        return None                                  # Sozu: the potion on offer never arrives, so nothing is thrown away for it
    best = max(offered, key=value)
    for p in belt:
        if potion_of(p) in DRINK_FIRST:
            return _drink(p)
    worst = min(belt, key=lambda p: (value(p), -p["slot"]))
    return _discard(worst) if value(best) > value(worst) else None


class FoulPotions:
    """Uses the Foul Potions held on arriving at a shop, one per call (the shop screen comes back after each). A use that did not take (the same count of potions after a try) is not repeated in that shop."""
    def __init__(self):
        self._tried : tuple | None = None          # (floor, potions held when the last use was sent)

    def choose(self, decision : Decision) -> Option | None:
        fouls = [p for p in held(decision) if potion_of(p) == PotionId.FOUL_POTION]
        if not fouls:
            return None
        ctx = decision.state.get("context") or decision.state.get("run") or {}
        mark = (ctx.get("floor"), len(held(decision)))
        if self._tried == mark:
            return None
        self._tried = mark
        return _drink(fouls[0])
