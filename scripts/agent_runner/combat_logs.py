"""What a combat run writes down: the decision log, one summary line per fight, the turn-start captures, saved states and engine mismatches.
Plain functions over game states and records; nothing here talks to the game."""
import functools
import json
import re
from datetime import datetime
from pathlib import Path

from sts2_lite.card import CardId
from sts2_lite.combat import CombatState
from agents.verify import snapshot

###
### Logging what the agent decided
###

def describe_action(action : dict, combat_state : CombatState) -> str:
    """A readable name for an action: "STRIKE_IRONCLAD+ -> LEAF_SLIME_M_0", "end_turn", "pick HEADBUTT" ..."""
    kind = action["action"]
    if kind == "play_card":
        hand = combat_state.player.hand
        card = hand[action["card_index"]] if action["card_index"] < len(hand) else None
        name = card.card_id.name + ("+" if card.is_upgraded else "") if card is not None else f"card {action['card_index']}"
        return f"{name} -> {action['target_name']}" if "target_name" in action else name
    if kind == "use_potion":
        return f"drink {action.get('potion_id', action['slot'])}" + (f" -> {action['target_name']}" if "target_name" in action else "")
    if kind == "choose_card":
        return f"pick {action['card_id']}{'+' if action.get('is_upgraded') else ''} ({action.get('pile', 'hand')})"
    return kind

def install_search_hook() -> dict:
    """Remembers the MCTS searcher of the latest decision (the agent does not keep it) without touching the agent:
    wraps monte_carlo_tree_search. Returns {"last": searcher | None, "stats": its returned stats | None, "module": the MCTS module | None}."""
    holder = {"last": None, "stats": None, "module": None}
    try:
        import importlib
        module = importlib.import_module("agents.sts2_MCTS.MCTS")
        cls = module.sts2_MCTS
    except (ImportError, AttributeError):
        return holder
    holder["module"] = module
    original = cls.monte_carlo_tree_search
    if getattr(original, "_remembers_searcher", False):
        original = original._original
    @functools.wraps(original)          # keeps the search's signature for anything that inspects it
    def wrapper(self, *args, **kwargs):
        holder["last"] = self
        result = original(self, *args, **kwargs)
        # search returns (action, stats); stats carry num_sims, time_taken, exit_reason
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
            holder["stats"] = result[1]
        return result
    wrapper._remembers_searcher = True
    wrapper._original = original
    cls.monte_carlo_tree_search = wrapper
    return holder

def tree_stats(root, limit : int = 400_000) -> dict:
    """Size and depth of the search tree under `root` (chance nodes and decision nodes; a node with several parents counts once)."""
    seen, stack, deepest = {id(root)}, [root], 0
    while stack and len(seen) < limit:
        node = stack.pop()
        deepest = max(deepest, getattr(node, "depth", 0))
        kids = getattr(node, "children", None)
        if kids is None:
            kids = list(getattr(node, "outcomes", {}).values())
        for kid in kids:
            if id(kid) not in seen:
                seen.add(id(kid))
                stack.append(kid)
    return {"tree_nodes": len(seen), "tree_depth": deepest - getattr(root, "depth", 0), "tree_capped": bool(stack)}

def log_decision(path : str | None, game_state : dict, combat_state : CombatState, action : dict, seconds : float, holder : dict, number : int,
                 time_budget : float):
    """One JSON line per decision: the situation, the move, and what the search saw (sims, time, every root move's visits and mean reward).
    `time_budget`: what the agent was given to think, to tell a search that ran out of time from one that was sure."""
    player = game_state.get("player") or {}
    record = {
        "n": number,
        "time": datetime.now().isoformat(timespec="seconds"),
        "floor": (game_state.get("context") or {}).get("floor"),
        "round": game_state.get("round"),
        "hp": player.get("hp"), "max_hp": player.get("max_hp"), "block": player.get("block"),
        "energy": game_state.get("energy"),
        "hand": [c.card_id.name + ("+" if c.is_upgraded else "") for c in combat_state.player.hand],
        "enemies": [{"name": e.get("name"), "hp": e.get("hp"), "block": e.get("block"), "intents": e.get("intents")}
                    for e in game_state.get("enemies", [])],
        "chosen": describe_action(action, combat_state),
        "seconds": round(seconds, 3),
        "sims": None, "stopped_by": None, "moves": None,
    }
    searcher, stats = holder.get("last"), holder.get("stats")
    if stats is not None:               # reported by the search itself
        record["sims"] = stats.get("num_sims")
        record["stopped_by"] = stats.get("exit_reason")
        record["reused"] = stats.get("reused")                  # the tree of the last search was kept (and how many visits it came with)
        record["inherited_visits"] = stats.get("inherited_visits")
        order = stats.get("order")                              # another order of the turn's plain plays was tried (None: nothing to compare)
        if order is not None:
            record["order"] = {k: order[k] for k in ("replaced", "plays", "distinct", "error") if k in order}
            best = max(order.get("compared", []), key=lambda c: c["gain"], default=None)
            if best is not None:
                record["order"]["best_gain"] = round(best["gain"], 4)
                record["order"]["best_first"] = describe_action(best["first"], combat_state)
        record["moves"] = [{"move": describe_action(c["action"], combat_state), "visits": c["visits"],
                            "mean": round(c["q"], 4)} for c in stats.get("children", [])]
    elif searcher is not None and getattr(searcher, "_root_node", None) is not None:
        record["sims"] = searcher._num_sims
        record["moves"] = [{"move": describe_action(c.action, combat_state), "visits": c.visits,
                            "mean": round(c.total_reward / c.visits, 4) if c.visits else None}
                           for c in searcher._root_node.children]
        module = holder.get("module")
        if module is not None:          # older search without stats: infer why it ended
            config_class = getattr(module, "SearchConfig", None)
            if config_class is not None and searcher._num_sims >= config_class().max_sims:
                record["stopped_by"] = "sim cap"
            elif seconds >= time_budget - 0.05:
                record["stopped_by"] = "time"
            else:
                record["stopped_by"] = "confidence"
    if searcher is not None and getattr(searcher, "_root_node", None) is not None:
        try:
            record.update(tree_stats(searcher._root_node))
        except Exception:                   # the tree is the agent's; a change in its layout must not stop a run
            pass
    holder["last"] = holder["stats"] = None
    if path:
        with open(path, "a") as f:
            f.write(json.dumps(record) + "\n")
    return record

###
### One summary line per fight
###

def fight_start(game_state : dict) -> dict:
    """The record of a fight that has just begun (the first play state of it)."""
    player = game_state.get("player") or {}
    context = game_state.get("context") or {}
    return {
        "floor": context.get("floor"), "act": context.get("act"), "ascension": context.get("ascension"),
        "room_type": game_state.get("room_type"),
        "enemies": [e.get("name") for e in game_state.get("enemies", [])],
        "start_hp": player.get("hp"), "max_hp": player.get("max_hp"), "start_time": datetime.now().isoformat(timespec="seconds"),
        "end_hp": player.get("hp"), "rounds": game_state.get("round"), "hp_at_round_start": {},
        "decisions": 0, "search_seconds": 0.0, "sims": 0, "stopped_by": {}, "max_tree_depth": 0, "mismatches": 0, "potions_used": 0,
        "_potions": len(potions_of(game_state)),
    }

def fight_update(fight : dict, game_state : dict, record : dict | None = None, mismatched : bool = False):
    """Fold one play state (and, once the agent has decided, its decision record) into the fight."""
    player = game_state.get("player") or {}
    if player.get("hp") is not None:
        fight["end_hp"] = player["hp"]
    rnd = game_state.get("round")
    if rnd is not None:
        fight["rounds"] = max(fight["rounds"] or 0, rnd)
        fight["hp_at_round_start"].setdefault(str(rnd), player.get("hp"))
    potions = len(potions_of(game_state))
    if potions < fight["_potions"]:
        fight["potions_used"] += fight["_potions"] - potions
    fight["_potions"] = potions
    if mismatched:
        fight["mismatches"] += 1
    if record:
        fight["decisions"] += 1
        fight["search_seconds"] = round(fight["search_seconds"] + (record.get("seconds") or 0), 3)
        fight["sims"] += record.get("sims") or 0
        reason = record.get("stopped_by")
        if reason:
            fight["stopped_by"][reason] = fight["stopped_by"].get(reason, 0) + 1
        fight["max_tree_depth"] = max(fight["max_tree_depth"], record.get("tree_depth") or 0)

def fight_end(fight : dict, away_state : dict) -> dict:
    """The finished summary: the player's HP once the fight is over (the reward screen still shows it) and whether it was won."""
    player = away_state.get("player") or {}
    if player.get("hp") is not None:
        fight["end_hp"] = player["hp"]
    name = f"{away_state.get('decision')} {away_state.get('type')} {away_state.get('screen_type')}".lower()
    lost = fight["end_hp"] is not None and fight["end_hp"] <= 0 or "game_over" in name or "death" in name
    out = {k: v for k, v in fight.items() if not k.startswith("_")}
    out.update({"outcome": "lost" if lost else "won", "hp_lost": (fight["start_hp"] or 0) - (fight["end_hp"] or 0),
                "end_time": datetime.now().isoformat(timespec="seconds"), "ended_on": away_state.get("decision") or away_state.get("type")})
    return out

def write_fight(path : str, summary : dict):
    with open(path, "a") as f:
        f.write(json.dumps(summary) + "\n")

def capture_turn_start(game_state : dict, directory : str) -> str:
    """Saves the state the agent is about to act on at the start of a turn (raw bridge output, as in data/enemies) so the
    benchmark can replay it, and adds one line to index.jsonl. Returns the file name."""
    floor = (game_state.get("context") or {}).get("floor")
    names = [e.get("name", "?") for e in game_state.get("enemies", [])]
    enemies = "+".join(sorted(set(re.sub(r"[^A-Za-z0-9]+", "_", n).strip("_") for n in names))) or "unknown"
    name = f"f{floor if floor is not None else 'x'}_r{game_state.get('round')}_{enemies}_{datetime.now().strftime('%H%M%S%f')}.json"
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(game_state, indent=1))
    player = game_state.get("player") or {}
    with open(folder / "index.jsonl", "a") as f:
        f.write(json.dumps({"file": name, "floor": floor, "round": game_state.get("round"), "enemies": names,
                            "hp": player.get("hp"), "max_hp": player.get("max_hp"),
                            "hand": [c.get("name") for c in game_state.get("hand", [])]}) + "\n")
    return name


###
### Engine mismatches
###

def log_mismatch(path : str, batch : dict, after, diffs : list[str], predicted : CombatState | None, actual : CombatState | None):
    """One JSON line: the state before the action(s), the actions, the state after, and what differed."""
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "floor": (batch["before"].get("context") or {}).get("floor"),
        "actions": batch["actions"],
        "random_step": batch.get("random_step", False),
        "differences": diffs,
        "before": batch["before"],
        "after": after,
        "sim_after": snapshot(predicted) if predicted is not None else None,
        "game_after": snapshot(actual) if actual is not None else None,
    }
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")
    tag = " (random step: hand contents are not trusted)" if record["random_step"] else ""
    print(f"MISMATCH{tag}: {len(diffs)} difference(s) after {[a['action'] for a in batch['actions']]}")
    for d in diffs[:6]:
        print("   ", d)
    if len(diffs) > 6:
        print(f"    ... and {len(diffs) - 6} more in {path}")

def unimplemented_cards(game_state : dict) -> dict[str, list[str]]:
    """Bridge card ids the sim loads as NOT_IMPLEMENTED (a Wound stand-in), by pile."""
    player = game_state.get("player") or {}
    piles = {"hand": game_state.get("hand") or player.get("hand") or []}
    for name in ("draw_pile", "discard_pile", "exhaust_pile"):
        piles[name] = player.get(name) or []
    found = {}
    for name, cards in piles.items():
        ids = [c.get("id") for c in cards if c.get("id") not in CardId.__members__ or c.get("id") == "NOT_IMPLEMENTED"]
        if ids:
            found[name] = ids
    return found

def report_unimplemented(game_state : dict, log_path : str, reported : set[str]):
    """Logs an engine mismatch the first time a run meets a card the sim does not implement."""
    found = unimplemented_cards(game_state)
    new = sorted({cid for ids in found.values() for cid in ids} - reported)
    if not new:
        return
    reported.update(new)
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "floor": (game_state.get("context") or {}).get("floor"),
        "kind": "not_implemented",
        "actions": [],
        "random_step": False,
        "differences": [f"card {cid} is not implemented in the sim (loaded as a Wound)" for cid in new],
        "piles": found,
        "before": game_state,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")
    print(f"MISMATCH: not implemented in the sim: {', '.join(new)}")

def potions_of(state : dict) -> list:
    return sorted(str(p.get("id")) for p in ((state.get("player") or {}).get("potions") or []))

def save_decision_state(state_dir : str, number : int, game_state : dict):
    """The exact state the agent saw at decision `number`, so a strange decision can be replayed (the decision log keeps only a summary)."""
    path = Path(state_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / f"decision_{number:05d}.json").write_text(json.dumps(game_state))
