from agents.base_agent import BaseAgent
from agents.my_agent import MyAgent

from sts2_lite import rng
from sts2_lite.card import CardId, CardType
from sts2_lite.combat import CombatState, CombatSimulator
from sts2_lite.selection import game_index
from sts2_lite.verify import compare, snapshot, is_random_step, is_unpredictable_step, some_target_roll_matches

import argparse
import functools
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

POLL_SECONDS = 0.4              # between state reads while the game is busy or it is not the agent's turn
TURN_CHANGE_TIMEOUT = 10.0      # seconds to wait for the round number to advance after End Turn
SETTLE_READS = 3                # identical reads in a row before a state is trusted
SETTLE_INTERVAL = 0.25          # seconds between those reads
LOCKED_READS = 8                # reads of locked-looking cards (about 3 s) before the agent acts anyway
ACTION_TIMEOUT = 8.0            # seconds to wait for the game to react to a play_card / end_turn
DEFAULT_LOG = "engine_mismatches.jsonl"     # where differences go when no run is named
RUNS_DIR = Path(__file__).resolve().parent / "runs"

TIME_BUDGET_SECONDS = 10.0       # Max time allocated for agent to think

def get_state() -> dict:
    result = subprocess.run(["cli-anything-sts2", "state"], capture_output=True, text=True)
    return json.loads(result.stdout)

def confirm_if_ready():
    """A picked card still has to be confirmed once the game allows it."""
    state = get_state()
    if not state.get("can_confirm"):
        return
    if state.get("decision") == "hand_select":
        subprocess.run(["cli-anything-sts2", "combat-confirm-selection"])
    elif state.get("decision") == "card_select":
        subprocess.run(["cli-anything-sts2", "confirm-selection"])

act3_boss_floors : set[int] = set()     # floors of the Act 3 boss fights seen in this run

def is_final_fight(game_state : dict, seen_floors : set[int]) -> bool:
    """True in the fight after which the run is won. Act 3's boss is the last fight; from Ascension 10 there is a second final boss,
    so the last fight is the Act 3 boss fight that comes after another one (a floor not seen before). `seen_floors` is filled here.
    Restarting the agent in the middle of the second boss fight reads it as the first: potions stay priced, which is the safe side."""
    context = game_state.get("context") or game_state.get("run") or {}
    if game_state.get("room_type") != "boss" or context.get("act", 0) < 3:
        return False
    floor = context.get("floor")
    others = {f for f in seen_floors if f != floor}
    seen_floors.add(floor)
    return context.get("ascension", 0) < 10 or bool(others)

picked_on_screen = []       # game indices already selected on an "up to N" pile screen (Neow's Fury)

def act(action, game_state=None, picking_more=False):
    """`picking_more`: the sim still waits for a pick after this action, so the screen must not be confirmed yet."""
    if action["action"] == "end_turn":
            subprocess.run(["cli-anything-sts2", "end-turn"])
    if action["action"] == "use_potion":
        command = ["cli-anything-sts2", "use-potion", str(action["slot"])]        # the command's format is a guess: check it once on a real run
        if "target_name" in action:
            command += ["--target", action["target_name"]]
        subprocess.run(command)
    if action["action"] == "choose_card":
        # both kinds of screen number only the selectable cards, in the game's own order: find the card there
        # the in-combat hand screen drops a picked card from its list and renumbers the rest, so earlier picks must not be skipped there;
        # a pile screen keeps its list, and the picked indices stay
        index = game_index(action, game_state["cards"], skip=picked_on_screen if action.get("pile", "hand") != "hand" else ())
        if index is None:
            print("card", action["card_id"], "is not in the game's list - pick it in the game")
            return
        command = "combat-select-card" if action.get("pile", "hand") == "hand" else "select-card"
        subprocess.run(["cli-anything-sts2", command, str(index)])
        picked_on_screen.append(index)
        if not picking_more:
            picked_on_screen.clear()
            confirm_if_ready()
    if action["action"] == "confirm_choice":
        # stop an "up to N" pick with what is selected so far; a "choose a card" screen (Discovery) has no confirm: skip it
        picked_on_screen.clear()
        if game_state is not None and game_state.get("screen_type") == "choose":
            subprocess.run(["cli-anything-sts2", "cancel-selection"])
        else:
            confirm_if_ready()
    if action["action"] == "play_card":
        if "target_name" in action:
            subprocess.run(["cli-anything-sts2",
                            "play-card",
                            str(action["card_index"]),
                            "--target",
                            action["target_name"]])
        else:
            subprocess.run(["cli-anything-sts2", "play-card", str(action["card_index"])])


###
### Reading the game
###

def in_subject_fight(combat_state : CombatState | None) -> bool:
    """The fight the simulated state belongs to has the Test Subject in it, alive or lying dead."""
    return combat_state is not None and any(e.enemy_id.startswith("TEST_SUBJECT") for e in combat_state.enemies + combat_state.dormant)

def kind_of(game_state : dict, expecting_choice : bool = False, subject_fight : bool = False) -> str:
    """What the loop should do with a state: "play" (agent's turn), "pick" (a card choice during combat),
    "busy" (combat, but the game is animating or it is the enemies' turn) or "away" (not in combat).
    `subject_fight`: the fight is against the Test Subject, which is not listed while it lies dead between its forms: an empty enemy list
    in the player's turn is then a turn to play (the cards that need a target cannot be played, so it ends the turn), not a fight being set up."""
    if game_state.get("type") != "decision":
        return "busy"
    decision = game_state.get("decision")
    if decision == "combat_play":
        if game_state.get("turn") != "player" or game_state.get("is_play_phase") is False:
            return "busy"
        if game_state.get("enemies") == [] and not subject_fight:
            return "busy"       # the killed enemy is gone but its spawns (Phrog Parasite's Wrigglers) are not there yet, or the fight is ending
        if not all(key in (game_state.get("player") or {}) for key in ("hp", "max_hp", "block", "status", "hand")):
            return "busy"       # the player's data is gone as the last enemy dies and the fight is torn down
        return "play"
    if decision == "hand_select":
        return "pick"
    if decision == "card_select" and game_state.get("screen_type") == "NCombatPileCardSelectScreen":
        return "pick"
    if decision == "card_select" and game_state.get("screen_type") == "choose" and expecting_choice:     # Discovery's offer
        return "pick"
    return "away"

def turn_is_changing(game_state : dict, ended : dict | None) -> bool:
    """The bridge never reports the play phase. After End Turn it still says "player" while the enemies act, then the
    round number advances before the next hand is drawn and the energy refilled (hand empty, energy 0).
    `ended`: the round the agent ended (and when). Wait for a started turn, but not forever: an extra turn
    (Pael's Eye) keeps the round number."""
    if ended is None or time.time() - ended["time"] >= TURN_CHANGE_TIMEOUT:
        return False
    if game_state.get("round") == ended["round"]:
        return True
    return not game_state.get("hand") and game_state.get("energy") == 0

def cards_look_locked(combat_state : CombatState) -> bool:
    """Affordable cards that the game shows as unplayable although nothing in the rules explains it: the game is not
    in its play phase (the sim already clears the flag for Ringing and Normality)."""
    energy = combat_state.energy
    affordable = [c for c in combat_state.player.hand
                  if not c.unplayable and c.type not in (CardType.Status, CardType.Curse) and (c.energy_cost == "X" or c.energy_cost <= energy)]
    return bool(affordable) and all(c.is_unplayable for c in affordable)

def auto_pick(game_state : dict):
    """The sim settled a pick by itself because every card on offer was the same (Armaments with two Defends), but the
    game still shows the screen: select the first card and confirm."""
    command = "combat-select-card" if game_state.get("decision") == "hand_select" else "select-card"
    subprocess.run(["cli-anything-sts2", command, str(game_state["cards"][0]["index"])])
    confirm_if_ready()

def dump(game_state : dict) -> str:
    return json.dumps(game_state, sort_keys=True)

def pile_total(game_state : dict) -> int:
    """Cards in the hand and the three piles. A card being played or auto-played sits in none of them."""
    player = game_state.get("player") or {}
    return len(game_state.get("hand") or []) + sum(player.get(k, 0) or 0 for k in ("draw_pile_count", "discard_pile_count", "exhaust_pile_count"))

def settled(game_state : dict, cards_owed : int | None = None) -> dict:
    """A card's cost is paid before its effect lands, and a turn starts in stages: take the first state that
    reads the same SETTLE_READS times in a row. `cards_owed`: a card being played, auto-played (Havoc) or exhausted
    (Toasty Mittens) is in limbo, and the game can pause there with the same state on every read: wait until the hand and piles hold
    the number of cards the sim expects."""
    stable = 1
    for _ in range(40 if cards_owed is None else 60):
        time.sleep(SETTLE_INTERVAL)
        again = get_state()
        if dump(again) == dump(game_state):
            stable += 1
            if stable >= SETTLE_READS and (cards_owed is None or pile_total(again) == cards_owed):
                return again
        else:
            stable, game_state = 1, again
    return game_state

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

def log_decision(path : str | None, game_state : dict, combat_state : CombatState, action : dict, seconds : float, holder : dict, number : int):
    """One JSON line per decision: the situation, the move, and what the search saw (sims, time, every root move's visits and mean reward)."""
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
            if searcher._num_sims >= getattr(module, "DEFAULT_MAX_SIMS", float("inf")):
                record["stopped_by"] = "sim cap"
            elif seconds >= TIME_BUDGET_SECONDS - 0.05:
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
    """Saves the state the agent is about to act on at the start of a turn (raw bridge output, as in Tests/data) so the
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

def wait_for_change(before : str) -> bool:
    """After an action: wait until the game reports something other than `before`. False if it never does."""
    deadline = time.time() + ACTION_TIMEOUT
    while time.time() < deadline:
        time.sleep(POLL_SECONDS)
        if dump(get_state()) != before:
            return True
    return False


###
### Checking the sim against the game
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

def verify_step(batch : dict, game_state : dict, actual : CombatState, log_path : str) -> bool:
    """Compare the state the sim predicted after the batch of actions with the one the game now reports."""
    drank = any(a["action"] == "use_potion" for a in batch["actions"])
    if potions_of(batch["before"]) != potions_of(game_state) and not drank:
        print("a potion changed during this step without the agent using one (Fairy in a Bottle?): not compared")
        return True
    if batch.get("unpredictable"):
        print("a card played a random card from the draw pile that the agent could not see (Havoc): not compared")
        return True
    diffs = compare(batch["predicted"], actual, random_step=batch["random_step"], random_target=batch.get("random_target", False))
    if diffs and batch.get("random_target") and some_target_roll_matches(batch["before_sim"], batch["actions"], actual, batch["random_step"]):
        diffs = []          # the game hit other enemies than the sim did, and the damage differs because the enemies do
    if diffs:
        log_mismatch(log_path, batch, game_state, diffs, batch["predicted"], actual)
    return not diffs

def verify_combat_end(batch : dict, game_state : dict, log_path : str):
    """The game left combat after the batch: the sim must have ended it too."""
    if not batch["predicted_over"]:
        log_mismatch(log_path, batch, game_state, ["the game ended the combat but the sim did not"], batch["predicted"], None)


###
### The loop
###

def save_decision_state(state_dir : str, number : int, game_state : dict):
    """The exact state the agent saw at decision `number`, so a strange decision can be replayed (the decision log keeps only a summary)."""
    path = Path(state_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / f"decision_{number:05d}.json").write_text(json.dumps(game_state))

def run_paths(run : str, decisions : bool = False, fights : bool = False, states : bool = False, captures : bool = False,
              append : bool = False, runs_dir : Path | None = None) -> dict:
    """Where one run keeps its data: runs/<run>/ holds mismatches.jsonl always, and decisions.jsonl, fights.jsonl, states/ and
    captures/ for the aspects asked for. A directory that already has files in it is refused unless `append` (a stopped run
    that carries on): the numbers of the saved states would otherwise start again at 1 and overwrite the old ones.
    Returns the keyword arguments of run_agent."""
    runs_dir = runs_dir or RUNS_DIR
    if not run or Path(run).name != run or run in (".", ".."):
        raise ValueError(f"a run is a folder name inside {runs_dir.name}/, not a path: {run!r}")
    directory = runs_dir / run
    if directory.exists() and any(directory.iterdir()) and not append:
        raise FileExistsError(f"{directory} already has data; pick another run name, or add --append to carry on in it")
    directory.mkdir(parents=True, exist_ok=True)
    first = 0
    if append:
        numbers = [int(m.group(1)) for p in (directory / "states").glob("decision_*.json") if (m := re.fullmatch(r"decision_(\d+)\.json", p.name))]
        log = directory / "decisions.jsonl"
        first = max(numbers + [sum(1 for _ in open(log)) if log.exists() else 0])
    return {
        "log_path": str(directory / "mismatches.jsonl"),
        "decision_log": str(directory / "decisions.jsonl") if decisions else None,
        "fight_log": str(directory / "fights.jsonl") if fights else None,
        "state_dir": str(directory / "states") if states else None,
        "capture_dir": str(directory / "captures") if captures else None,
        "first_decision": first,
    }

def run_agent(agent : BaseAgent, step : bool = False, verify : bool = True, log_path : str = DEFAULT_LOG, capture_dir : str | None = None,
              decision_log : str | None = None, state_dir : str | None = None, fight_log : str | None = None, first_decision : int = 0):
    previous = None     # state after the last action: the bridge reports no per-turn history
    batch = None        # actions since the last point the sim and the game could be compared
    waiting_for = None  # what the loop last said it was waiting on, so it says so once
    ended = None        # {"round", "time"} of the last End Turn, until the next round starts
    captured_round = None   # round whose first state was saved to capture_dir
    search = install_search_hook() if (decision_log or fight_log) else None
    fight = None                # summary of the fight in progress (--fight-log)
    decisions = first_decision     # numbers the decision log and the saved states
    just_mismatched = False
    locked_reads = 0
    checked = mismatched = 0
    reported_cards = set()      # NOT_IMPLEMENTED card ids already logged this run
    cards_owed = None           # how many cards the hand and piles must hold once the last action has finished
    try:
        while True:
            game_state = get_state()
            kind = kind_of(game_state, previous is not None and previous.pending_choice is not None, in_subject_fight(previous))

            if kind == "away":
                if fight is not None and fight_log:
                    write_fight(fight_log, fight_end(fight, game_state))
                fight = None
                if batch is not None and verify and batch["predicted"] is not None:
                    verify_combat_end(batch, game_state, log_path)
                    checked += 1
                previous = batch = None             # nothing carries from one combat to the next
                captured_round = None
                ended = {"round": 0, "time": time.time()}       # the next fight's first turn is set up in stages, like any turn
                picked_on_screen.clear()
                message = f"not in combat ({game_state.get('decision', game_state.get('type'))}) - waiting for the next fight"
                if message != waiting_for:
                    print(message)
                    waiting_for = message
                time.sleep(1.0)
                continue
            waiting_for = None
            if kind == "play" and turn_is_changing(game_state, ended):
                kind = "busy"
            if kind == "busy":
                time.sleep(POLL_SECONDS)
                continue
            if kind == "play":
                ended = None

            game_state = settled(game_state, cards_owed)
            cards_owed = None
            if kind_of(game_state, previous is not None and previous.pending_choice is not None, in_subject_fight(previous)) != kind:
                continue            # the game moved on while the state settled (the last enemy died and the fight is torn down): read it again
            decision = game_state["decision"]

            choosing_optionally = previous is not None and previous.pending_choice is not None and previous.pending_choice.optional
            if kind == "pick" and game_state.get("can_confirm") and not choosing_optionally:
                picked_on_screen.clear()
                confirm_if_ready()      # a card is already picked; only the confirmation is missing
                continue                # (an "up to N" screen can be confirmed from the start: the agent decides)

            if kind == "pick" and previous is not None and previous.pending_choice is None and batch is not None \
                    and batch["predicted"] is not None and game_state.get("cards"):
                before = dump(game_state)
                auto_pick(game_state)
                if not wait_for_change(before):
                    print("the game did not react to the automatic pick - pick it in the game")
                    input("press Enter when done ... \n")
                continue

            if kind == "pick" and previous is not None and previous.pending_choice is not None:
                # the sim knows what this pick is for; a pile screen has no fight data to load
                combat_state = CombatState.deepcopy(previous)
                combat_state.adopt_offer(game_state.get("cards") or [])     # options the sim drew at random (Seeker Strike)
            elif kind == "pick" and decision != "hand_select":
                print("cannot read this card selection - pick it in the game")
                time.sleep(1.0)
                continue
            else:
                combat_state = CombatState.from_dict(game_state)
                combat_state.final_fight = is_final_fight(game_state, act3_boss_floors)
                report_unimplemented(game_state, log_path, reported_cards)
                combat_state.carry_turn_counters(previous)
                combat_state.carry_known_top(previous)    # cards the agent put on top (Headbutt)
                combat_state.carry_boss_state(previous)         # the form of a dead Test Subject
                combat_state.carry_combat_counters(previous)    # HP-loss events (Tear Asunder), Inferno plays
                if cards_look_locked(combat_state):
                    locked_reads += 1
                    if locked_reads < LOCKED_READS:
                        time.sleep(POLL_SECONDS)        # not the play phase yet: neither act nor compare
                        continue
                    print("cards stay locked although they are affordable - acting anyway")
                locked_reads = 0
                if batch is not None and batch["predicted"] is not None:
                    if verify:
                        checked += 1
                        if not verify_step(batch, game_state, combat_state, log_path):
                            mismatched += 1
                            just_mismatched = True
                    batch = None

            if fight_log and kind == "play":
                if fight is None:
                    fight = fight_start(game_state)
                fight_update(fight, game_state, mismatched=just_mismatched)
            just_mismatched = False

            if capture_dir and kind == "play" and game_state.get("round") != captured_round:
                captured_round = game_state.get("round")
                print("captured", capture_turn_start(game_state, capture_dir))

            if step:
                input("waiting for input ... \n")
            started = time.perf_counter()
            action = agent.get_action(combat_state, TIME_BUDGET_SECONDS)
            decisions += 1
            if state_dir:
                save_decision_state(state_dir, decisions, game_state)
            if decision_log or fight_log:
                record = log_decision(decision_log, game_state, combat_state, action, time.perf_counter() - started, search, decisions)
                if fight is not None:
                    fight_update(fight, game_state, record)

            if batch is None:
                batch = {"before": game_state, "actions": [], "before_sim": CombatState.deepcopy(combat_state)}
            batch["actions"].append(action)
            previous = CombatState.deepcopy(combat_state)
            simulator = CombatSimulator(previous)
            rolls = rng.target_rolls
            simulator.perform_action(action)
            batch["random_target"] = batch.get("random_target", False) or rng.target_rolls != rolls     # the game may have hit another enemy
            picking_more = previous.pending_choice is not None
            batch["predicted"] = None if picking_more else previous
            batch["predicted_over"] = simulator.is_over
            batch["random_step"] = is_random_step(batch["before_sim"], previous, batch["actions"])
            batch["unpredictable"] = batch.get("unpredictable", False) or is_unpredictable_step(batch["before_sim"], batch["actions"])

            if batch["predicted"] is not None:
                p = batch["predicted"].player
                cards_owed = len(p.hand) + len(p.draw_pile) + len(p.discard_pile) + len(p.exhaust_pile)     # wait for every card to land
            before = dump(game_state)
            if action["action"] == "end_turn":
                ended = {"round": game_state.get("round"), "time": time.time()}
            act(action, game_state, picking_more)
            if action["action"] in ("play_card", "end_turn", "use_potion") and not wait_for_change(before):
                print("the game did not react to", action)
                log_mismatch(log_path, batch, get_state(), [f"the game ignored {action}, which the sim treats as legal"],
                             previous, None)
                input("fix it in the game, then press Enter ... \n")
                previous = batch = None
    except KeyboardInterrupt:
        print(f"\nstopped. {checked} step(s) checked, {mismatched} with differences" + (f" (see {log_path})" if mismatched else ""))

def main(argv : list[str] | None = None):
    parser = argparse.ArgumentParser(description="Let the agent play every combat; compare the sim with the game after each action. "
                                     "Name a run to keep its data in runs/<run>/ (mismatches.jsonl is always written there).")
    parser.add_argument("run", nargs="?", default=None, help="folder name for this run's data inside runs/, e.g. run3-a9")
    parser.add_argument("--decisions", action="store_true", help="save decisions.jsonl: every move with its sims, time, and each move's visits and mean reward")
    parser.add_argument("--fights", action="store_true", help="save fights.jsonl: one line per fight with enemies, HP at the start and end, rounds, outcome, search totals and the deepest tree")
    parser.add_argument("--states", action="store_true", help="save states/decision_NNNNN.json: the game state behind every decision (numbers match --decisions)")
    parser.add_argument("--captures", action="store_true", help="save captures/: the state at the start of every turn (benchmark material)")
    parser.add_argument("--all", action="store_true", help="save decisions, fights, states and captures")
    parser.add_argument("--append", action="store_true", help="carry on in a run folder that already has data (decision numbers continue)")
    parser.add_argument("--step", action="store_true", help="wait for Enter before every action")
    parser.add_argument("--no-verify", action="store_true", help="do not compare the sim with the game")
    args = parser.parse_args(argv)
    wanted = {"decisions": args.decisions or args.all, "fights": args.fights or args.all,
              "states": args.states or args.all, "captures": args.captures or args.all}
    if args.run is None and (any(wanted.values()) or args.append):
        parser.error("name the run (e.g. run3-a9) to save anything")
    if args.run is None:
        kwargs = {"log_path": DEFAULT_LOG}
    else:
        try:
            kwargs = run_paths(args.run, append=args.append, **wanted)
        except (ValueError, FileExistsError) as error:
            parser.error(str(error))
        print(f"saving to {RUNS_DIR / args.run}: mismatches" + "".join(f", {name}" for name, on in wanted.items() if on))
    agent = MyAgent()
    run_agent(agent, step=args.step, verify=not args.no_verify, **kwargs)

if __name__ == "__main__":
    main()
