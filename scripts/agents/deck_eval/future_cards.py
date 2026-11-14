"""The fights ahead one by one, each with the cards the deck is expected to have gained by then.

A fight n fights away (the boss of a route with 6 fights left is 6 away) is played with n extra cards, one per fight on the way: the
cards a reward would give. Only fights count, not shops, "?" rooms or rest sites. A sample draws its fights equally from the fights
ahead of the route. The extra cards are drawn by the rarity odds of a card reward and are the same for every deck of a decision, so the
comparison between decks stays paired."""
from __future__ import annotations
import random

from sts2_lite.card.constants import CARD_ENERGY_COST_AND_TARGET
from sts2_lite.card.ids import CardId, CardType
from sts2_lite.card.tables import CARD_RARITY, GENERATABLE_CARDS

from agents.deck_eval.fight_mix import kind_templates, mix_ahead, new_act_mix, NEW_ACT_ELITES, NEW_ACT_NORMALS
from agents.deck_eval.fight_pool import FightTemplate, WEAK_FIGHTS

# A card reward offers roughly 60% commons, 25% uncommons, 15% rares, and the rare share grows with every reward seen.
RARE_START, RARE_PER_CARD, RARE_MAX = 0.15, 0.01, 0.30
UNCOMMON = 0.25
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


def fight_kinds(route, act : int) -> list[str]:
    """The kinds of the fights ahead, in the order of the route ("combat" is weak while the act's first combats last)."""
    if route is None or not route.kinds or route.kinds[0] == "boss":
        weak = WEAK_FIGHTS.get(act if route is None or not route.kinds else min(3, act + 1), 2)
        middle = []
        for i in range(max(NEW_ACT_NORMALS, NEW_ACT_ELITES)):
            middle += (["normal"] if i < NEW_ACT_NORMALS else []) + (["elite"] if i < NEW_ACT_ELITES else [])
        return ["weak"] * weak + middle + ["boss"]
    weak_left = max(0, WEAK_FIGHTS.get(act, 2) - route.combats_before - (route.kinds[0] == "combat"))
    kinds = []
    for kind in route.kinds[1:]:
        if kind == "combat":
            kinds.append("weak" if weak_left > 0 else "normal")
            weak_left -= 1
        elif kind in ("elite", "boss"):
            kinds.append(kind)
    return kinds or ["normal"]


def extra_cards(n : int, r : random.Random) -> list[dict]:
    """`n` cards drawn like card rewards: the rare odds start at RARE_START and grow by RARE_PER_CARD with every card."""
    cards = []
    for i in range(n):
        rare = min(RARE_MAX, RARE_START + RARE_PER_CARD * i)
        roll = r.random()
        rarity = "Rare" if roll < rare else "Uncommon" if roll < rare + UNCOMMON else "Common"
        cards.append(dict(r.choice(CARD_POOL[rarity])))
    return cards


def sample_future(pool : list[FightTemplate], route, act : int, ascension : int, n : int, seed : int) -> tuple[list[FightTemplate], list[list[dict]]]:
    """`n` fights, each drawn with equal chance from the fights ahead, and for each the cards gained on the way to it
    (the first fight ahead gets 1 card, the k-th gets k). Same seed -> same fights and cards."""
    r = random.Random(seed)
    kinds = fight_kinds(route, act)
    mix = mix_ahead(act, route)
    templates = kind_templates(pool, mix, ascension)
    fights, extras = [], []
    for _ in range(n):
        position = r.randrange(len(kinds))
        fights.append(r.choice(templates(kinds[position])))
        extras.append(extra_cards(position + 1, r))
    return fights, extras
