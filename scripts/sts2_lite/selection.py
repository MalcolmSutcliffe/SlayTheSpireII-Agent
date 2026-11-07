"""Matching a choice made in the sim to the card list the game shows for it."""


def game_index(action : dict, cards : list[dict], skip=()) -> int | None:
    """Index in the game's card list of the card an action picks: the first one with the same id and
    upgrade state, since the sim's pile order need not match the game's. `skip`: indices already picked
    on this screen (an "up to N" pick can take two identical cards). None if there is no such card."""
    for card in cards:
        if card["index"] not in skip and card["id"] == action["card_id"] and card["is_upgraded"] == action["is_upgraded"]:
            return card["index"]
    return None
