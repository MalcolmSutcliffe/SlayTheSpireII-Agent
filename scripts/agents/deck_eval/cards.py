"""Small card helpers the choosers and the walks' stand-in agent share: which cards go first when the deck loses one, and the rarity order."""
from __future__ import annotations

RARITY_RANK = {"Rare": 3, "Uncommon": 2, "Common": 1}       # anything else (Basic, a curse, a status) ranks 0
SHOP_RELIC_POSITION = 2     # a shop lists its own relic 3rd: the shop chooser judges it like the others, the walks' stand-in shopper (route_sim.WalkAgent) never buys it


def removal_rank(card : dict) -> int | None:
    """0 curse, 1 Strike, 2 Defend; None for a card the agent keeps (or cannot remove)."""
    if card.get("removable") is False:
        return None
    if card.get("type") == "Curse" or card.get("rarity") == "Curse":
        return 0
    card_id = str(card.get("id", ""))
    if card_id.startswith("STRIKE"):
        return 1
    if card_id.startswith("DEFEND"):
        return 2
    return None


def is_curse(card : dict) -> bool:
    return card.get("type") == "Curse" or card.get("rarity") == "Curse"


def transform_rank(card : dict) -> tuple:
    """The order to transform cards in (lowest first): a Strike, a Defend, then the lowest rarity. A curse only turns into another curse, so it goes last."""
    card_id = str(card.get("id", ""))
    if is_curse(card):
        return (9, 0)
    if card_id.startswith("STRIKE"):
        return (0, 0)
    if card_id.startswith("DEFEND"):
        return (1, 0)
    return (2, {"Basic": 0, "Common": 1, "Uncommon": 2, "Rare": 3}.get(card.get("rarity"), 4))


def card_to_remove(deck : list[dict]) -> int | None:
    """Index in `deck` of the card to remove: the lowest rank, the first of its kind."""
    ranked = [(removal_rank(c), i) for i, c in enumerate(deck) if removal_rank(c) is not None]
    return min(ranked)[1] if ranked else None
