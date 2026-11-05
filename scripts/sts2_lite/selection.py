"""Matching a choice made in the sim to the card list the game shows for it."""


def game_index(action : dict, cards : list[dict]) -> int | None:
    """Index in the game's card list of the card an action picks: the first one with the same id and
    upgrade state, since the sim's pile order need not match the game's. None if there is no such card."""
    for card in cards:
        if card["id"] == action["card_id"] and card["is_upgraded"] == action["is_upgraded"]:
            return card["index"]
    return None
