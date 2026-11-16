"""The screens an agent decides on, in the shape the bridge reports them (`agent_runner.decision_builders` turns each into the legal options)."""
from __future__ import annotations

from sts2_lite.datacopy import deepcopy_data

from sts2_lite.map import ActMap
from sts2_lite.run import RunState


def context(run : RunState) -> dict:
    return {"act": run.act, "floor": run.floor, "ascension": run.ascension}


def player(run : RunState) -> dict:
    out = run.player_dict()
    out["open_potion_slots"] = max(0, run.potion_slots - len(run.potions))
    out["deck"] = deepcopy_data(run.deck)
    return out


def screen(run : RunState, decision : str, **fields) -> dict:
    return {"type": "decision", "decision": decision, "context": context(run), "player": player(run), **fields}


def card_view(card : dict, index : int) -> dict:
    return {**{k: v for k, v in card.items() if not k.startswith("_")}, "index": index}


def map_select(run : RunState, act_map : ActMap, choices, visited, boss_id : str | None) -> dict:
    here = run.position
    return screen(run, "map_select", choices=[{"index": i, "type": p.type.bridge_name, "col": p.col, "row": p.row} for i, p in enumerate(choices)],
                  **act_map.to_bridge(visited, here), boss={"encounter": boss_id}, act_model=run.act_id)


def combat_rewards(run : RunState, rewards) -> dict:
    return screen(run, "combat_rewards", items=[{"index": i, "type": r.kind, "description": r.description()} for i, r in enumerate(rewards)], can_proceed=True)


def card_reward(run : RunState, offers, alternatives=()) -> dict:
    """`alternatives`: the options besides taking a card and skipping (REROLL from Driftwood, SACRIFICE from Pael's Wing), as ids."""
    return screen(run, "card_reward", cards=[card_view(o, i) for i, o in enumerate(offers)], can_skip=True,
                  alternatives=[{"index": i, "id": a, "name": a.title()} for i, a in enumerate(alternatives)])


REST_NAMES = {"HEAL": "Rest", "SMITH": "Smith"}


def rest_site(run : RunState, names : list[str], can_smith : bool, can_proceed : bool, disabled : tuple = ()) -> dict:
    """The options still open at a rest site (HEAL, SMITH, DIG, ...); `can_proceed` once one has been used."""
    options = [{"index": i, "id": n, "name": REST_NAMES.get(n, n.title()), "is_enabled": can_smith if n == "SMITH" else n not in disabled} for i, n in enumerate(names)]
    return screen(run, "rest_site", options=options, can_proceed=can_proceed)


def card_select(run : RunState, screen_type : str, cards : list[dict], selected : list[int], can_confirm : bool, can_cancel : bool) -> dict:
    return screen(run, "card_select", screen_type=screen_type, cards=[card_view(c, i) for i, c in enumerate(cards) if i not in selected],
                  selected=[card_view(cards[i], i) for i in selected], can_confirm=can_confirm, can_cancel=can_cancel)


def event_choice(run : RunState, event_id : str, options : list) -> dict:
    return screen(run, "event_choice", event_id=event_id, in_dialogue=False,
                  options=[{"index": i, "title": o.key, "is_locked": o.locked} for i, o in enumerate(options)])


def treasure(run : RunState, relics : list[dict], can_proceed : bool) -> dict:
    return screen(run, "treasure", relics=[{**r, "index": i} for i, r in enumerate(relics)], can_proceed=can_proceed)


def shop(run : RunState, items : list[dict], fake_merchant : bool = False) -> dict:
    return screen(run, "shop", items=items, can_proceed=True, **({"is_fake_merchant": True} if fake_merchant else {}))
