"""Turns a normalized out-of-combat state into a Decision: the legal options of that screen, each with the action that carries it out.
A screen with nothing to click yet (loading, animating) gives no options, and the runner waits."""
from collections import Counter

from agents.decision import (Decision, Option, MAP, CARD_REWARD, REWARDS, REST, SHOP, EVENT, CARD_SELECT, RELIC, TREASURE)

PROCEED = {"action": "proceed"}

def _open_potion_slots(state : dict) -> int | None:
    return (state.get("player") or {}).get("open_potion_slots")

def _proceed(state : dict, label : str = "proceed") -> list[Option]:
    return [Option(label, dict(PROCEED))] if state.get("can_proceed") else []

def map_options(state : dict) -> list[Option]:
    return [Option(f"{c.get('type')} ({c.get('col')},{c.get('row')})", {"action": "choose_map_node", "index": c["index"]}, c)
            for c in state.get("choices") or []]

def card_reward_options(state : dict) -> list[Option]:
    options = [Option(c.get("name") or c.get("id") or "card", {"action": "select_card_reward", "card_index": c["index"]}, c)
               for c in state.get("cards") or []]
    if state.get("can_skip"):
        options.append(Option("skip", {"action": "skip_card_reward"}))
    return options

def reward_key(item : dict) -> tuple:
    """What makes two reward items the same thing: the game lists a skipped card reward again, and indices move as other rewards are claimed."""
    return (item.get("type"), item.get("description"))

def rewards_options(state : dict, declined : Counter | None = None) -> list[Option]:
    """`declined`: reward keys the agent chose to skip (a card reward it declined stays in the list); that many of each are left out."""
    options = []
    left = Counter(declined or {})
    for item in state.get("items") or []:
        if item.get("type") == "potion" and _open_potion_slots(state) == 0:
            continue            # no room: the click would do nothing
        if left[reward_key(item)] > 0:
            left[reward_key(item)] -= 1
            continue
        options.append(Option(item.get("description") or item.get("type") or "reward", {"action": "claim_reward", "index": item["index"]}, item))
    return options + _proceed(state)

def rest_options(state : dict) -> list[Option]:
    options = [Option(o.get("name") or o.get("id") or "option", {"action": "choose_rest_option", "index": o["index"]}, o)
               for o in state.get("options") or [] if o.get("is_enabled", True)]
    return options + _proceed(state)

def shop_options(state : dict) -> list[Option]:
    options = []
    for item in state.get("items") or []:
        if not item.get("is_stocked", True) or not item.get("can_afford", False):
            continue
        if item.get("category") == "potion" and _open_potion_slots(state) == 0:
            continue
        label = f"buy {item.get('name') or item.get('id') or item.get('category')} ({item.get('cost')}g)"
        options.append(Option(label, {"action": "shop_purchase", "index": item["index"]}, item))
    return options + _proceed(state, "leave shop")

def event_options(state : dict) -> list[Option]:
    if state.get("in_dialogue"):
        return [Option("continue dialogue", {"action": "advance_dialogue"})]
    return [Option(o.get("title") or "option", {"action": "choose_event_option", "index": o["index"]}, o)
            for o in state.get("options") or [] if not o.get("is_locked")]

def card_select_options(state : dict) -> list[Option]:
    options = [Option(c.get("name") or c.get("id") or "card", {"action": "select_card", "index": c["index"]}, c) for c in state.get("cards") or []]
    if state.get("can_confirm"):
        options.append(Option("confirm", {"action": "confirm_selection"}))
    if state.get("can_skip") or state.get("can_cancel"):
        options.append(Option("cancel", {"action": "cancel_selection"}))
    return options

def relic_options(state : dict) -> list[Option]:
    options = [Option(r.get("name") or r.get("id") or "relic", {"action": "select_relic", "index": r["index"]}, r) for r in state.get("relics") or []]
    if state.get("can_skip"):
        options.append(Option("skip", {"action": "skip_relic_selection"}))
    return options

def treasure_options(state : dict) -> list[Option]:
    options = [Option(r.get("name") or r.get("id") or "relic", {"action": "claim_treasure_relic", "index": r["index"]}, r) for r in state.get("relics") or []]
    return options + _proceed(state)

BUILDERS = {
    "map_select": (MAP, map_options),
    "card_reward": (CARD_REWARD, card_reward_options),
    "combat_rewards": (REWARDS, rewards_options),
    "rest_site": (REST, rest_options),
    "shop": (SHOP, shop_options),
    "event_choice": (EVENT, event_options),
    "card_select": (CARD_SELECT, card_select_options),
    "relic_select": (RELIC, relic_options),
    "treasure": (TREASURE, treasure_options),
}

def build_decision(state : dict, declined : Counter | None = None) -> Decision | None:
    """None for a state that is not a screen the agent decides on (the main menu, game over, an overlay, combat); a Decision
    with no options for a screen that has nothing to click yet."""
    if state.get("type") != "decision" or state.get("decision") not in BUILDERS:
        return None
    kind, build = BUILDERS[state["decision"]]
    return Decision(kind, state, rewards_options(state, declined) if kind == REWARDS else build(state))
