"""What the route ahead holds for a deck: the rooms left on the planned route (`route_steps`), the act they are played in, and the card-reward
model the walks' stand-in agent uses (route_sim.WalkAgent takes a card with chance EXTRA_CARD_SHARE of the act; `extra_cards` draws cards with the
rarity odds of a card reward, for the benchmarks that build decks)."""
from __future__ import annotations
import random

from sts2_lite.card.constants import CARD_ENERGY_COST_AND_TARGET
from sts2_lite.card.ids import CardId, CardType
from sts2_lite.card.tables import CARD_RARITY, GENERATABLE_CARDS

from agents.deck_eval.fight_mix import NEW_ACT_ELITES, NEW_ACT_NORMALS
from agents.deck_eval.fight_pool import WEAK_FIGHTS

# A card reward offers roughly 60% commons, 25% uncommons, 15% rares, and the rare share grows with every reward seen.
RARE_START, RARE_PER_CARD, RARE_MAX = 0.15, 0.01, 0.30
UNCOMMON = 0.25
# A later deck is more complete, so each fight k ahead gets fewer than k cards in the later acts (the act the fight is played in)
EXTRA_CARD_SHARE = {1: 0.8, 2: 0.5, 3: 0.3}
EXTRA_TYPES = {CardId.FEED : CardType.Attack, CardId.NOT_YET : CardType.Skill}      # Ironclad cards missing from GENERATABLE_CARDS (name, type)


def _pool() -> dict[str, list[dict]]:
    by_rarity = {"Common": [], "Uncommon": [], "Rare": []}
    for card, rarity in CARD_RARITY.items():
        if rarity.name not in by_rarity:
            continue
        if card in GENERATABLE_CARDS:
            name, ctype, cost, target = GENERATABLE_CARDS[card]
        elif card in EXTRA_TYPES:
            name, ctype, (cost, target) = card.name.replace("_", " ").title(), EXTRA_TYPES[card], CARD_ENERGY_COST_AND_TARGET[card]
        else:
            continue            # colorless and other cards a reward does not offer an Ironclad
        by_rarity[rarity.name].append({"id": card.name, "name": name, "type": ctype.name, "cost": cost, "target_type": target.name})
    return by_rarity


CARD_POOL = _pool()


def route_steps(route, act : int) -> list[str]:
    """The rooms ahead that matter for a deck, in the order of the route: the kinds of its fights ("combat" is weak while the act's first combats last),
    "rest" for a rest site, "treasure" for the treasure room and "shop" for a shop and "unknown" for a "?" room. A new act (or no route) has no rest sites in it: only the fights an act is expected to hold."""
    if route is None or not route.kinds or route.kinds[0] == "boss":
        weak = WEAK_FIGHTS.get(act if route is None or not route.kinds else min(3, act + 1), 2)
        middle = []
        for i in range(max(NEW_ACT_NORMALS, NEW_ACT_ELITES)):
            middle += (["normal"] if i < NEW_ACT_NORMALS else []) + (["elite"] if i < NEW_ACT_ELITES else [])
        return ["weak"] * weak + middle + ["boss"]
    weak_left = max(0, WEAK_FIGHTS.get(act, 2) - route.combats_before - (route.kinds[0] == "combat"))
    steps = []
    for kind in route.kinds[1:]:
        if kind == "combat":
            steps.append("weak" if weak_left > 0 else "normal")
            weak_left -= 1
        elif kind in ("elite", "boss", "rest", "treasure", "shop", "unknown"):
            steps.append(kind)
    return steps


def fight_kinds(route, act : int) -> list[str]:
    """The kinds of the fights ahead, in the order of the route."""
    return [k for k in route_steps(route, act) if k in ("weak", "normal", "elite", "boss")] or ["normal"]


def extra_cards(n : int, r : random.Random) -> list[dict]:
    """`n` cards drawn like card rewards: the rare odds start at RARE_START and grow by RARE_PER_CARD with every card."""
    cards = []
    for i in range(n):
        rare = min(RARE_MAX, RARE_START + RARE_PER_CARD * i)
        roll = r.random()
        rarity = "Rare" if roll < rare else "Uncommon" if roll < rare + UNCOMMON else "Common"
        cards.append(dict(r.choice(CARD_POOL[rarity])))
    return cards


def fight_act(route, act : int) -> int:
    """The act the fights ahead are played in: a boss reward looks at the next act."""
    return min(3, act + 1) if route is not None and route.kinds and route.kinds[0] == "boss" else act

