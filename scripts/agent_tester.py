from agents.base_agent import BaseAgent
from agents.my_agent import MyAgent

from sts2_lite.card import CardType
from sts2_lite.combat import CombatState, CombatSimulator
from sts2_lite.selection import game_index
from sts2_lite.verify import compare, snapshot, is_random_step

import argparse
import json
import subprocess
import time
from datetime import datetime

DO_INTERNAL = False

POLL_SECONDS = 0.4              # between state reads while the game is busy or it is not the agent's turn
TURN_CHANGE_TIMEOUT = 10.0      # seconds to wait for the round number to advance after End Turn
SETTLE_READS = 3               # identical reads in a row before a state is trusted
SETTLE_INTERVAL = 0.25          # seconds between those reads
LOCKED_READS = 8                # reads of locked-looking cards (about 3 s) before the agent acts anyway
ACTION_TIMEOUT = 8.0            # seconds to wait for the game to react to a play_card / end_turn
DEFAULT_LOG = "engine_mismatches.jsonl"

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

picked_on_screen = []       # game indices already selected on an "up to N" pile screen (Neow's Fury)

def act(action, game_state=None, picking_more=False):
    """`picking_more`: the sim still waits for a pick after this action, so the screen must not be confirmed yet."""
    if action["action"] == "end_turn":
            subprocess.run(["cli-anything-sts2", "end-turn"])
    if action["action"] == "choose_card":
        # both kinds of screen number only the selectable cards, in the game's own order: find the card there
        index = game_index(action, game_state["cards"], skip=picked_on_screen)
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
        # stop an "up to N" pick with what is selected so far
        picked_on_screen.clear()
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

def kind_of(game_state : dict) -> str:
    """What the loop should do with a state: "play" (agent's turn), "pick" (a card choice during combat),
    "busy" (combat, but the game is animating or it is the enemies' turn) or "away" (not in combat)."""
    if game_state.get("type") != "decision":
        return "busy"
    decision = game_state.get("decision")
    if decision == "combat_play":
        if game_state.get("turn") != "player" or game_state.get("is_play_phase") is False:
            return "busy"
        return "play"
    if decision == "hand_select":
        return "pick"
    if decision == "card_select" and game_state.get("screen_type") == "NCombatPileCardSelectScreen":
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

def settled(game_state : dict) -> dict:
    """A card's cost is paid before its effect lands, and a turn starts in stages: take the first state that
    reads the same SETTLE_READS times in a row."""
    stable = 1
    for _ in range(40):
        time.sleep(SETTLE_INTERVAL)
        again = get_state()
        if dump(again) == dump(game_state):
            stable += 1
            if stable >= SETTLE_READS:
                return again
        else:
            stable, game_state = 1, again
    return game_state

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

def verify_step(batch : dict, game_state : dict, actual : CombatState, log_path : str) -> bool:
    """Compare the state the sim predicted after the batch of actions with the one the game now reports."""
    diffs = compare(batch["predicted"], actual, random_step=batch["random_step"])
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

def run_agent(agent : BaseAgent, step : bool = False, verify : bool = True, log_path : str = DEFAULT_LOG):
    if DO_INTERNAL:
        with open("example_output.json", "r") as f:
            game_state = json.load(f)
        combat_state = CombatState.from_dict(game_state)
        c = CombatSimulator(combat_state)
        # c.perform_action({'action': 'play_card', 'card_index': 3, 'target': 1, 'target_name': 'PHANTASMAL_GARDENER_1'})
        action = agent.get_action(c.combat_state)
        print(action)
        return

    previous = None     # state after the last action: the bridge reports no per-turn history
    batch = None        # actions since the last point the sim and the game could be compared
    waiting_for = None  # what the loop last said it was waiting on, so it says so once
    ended = None        # {"round", "time"} of the last End Turn, until the next round starts
    locked_reads = 0
    checked = mismatched = 0
    try:
        while True:
            game_state = get_state()
            kind = kind_of(game_state)

            if kind == "away":
                if batch is not None and verify and batch["predicted"] is not None:
                    verify_combat_end(batch, game_state, log_path)
                    checked += 1
                previous = batch = None             # nothing carries from one combat to the next
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

            game_state = settled(game_state)
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
            elif kind == "pick" and decision != "hand_select":
                print("cannot read this card selection - pick it in the game")
                time.sleep(1.0)
                continue
            else:
                combat_state = CombatState.from_dict(game_state)
                combat_state.carry_turn_counters(previous)
                combat_state.carry_known_top(previous)    # cards the agent put on top (Headbutt)
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
                    batch = None

            if step:
                input("waiting for input ... \n")
            action = agent.get_action(combat_state, 5000)
            print(action)

            if batch is None:
                batch = {"before": game_state, "actions": [], "before_sim": CombatState.deepcopy(combat_state)}
            batch["actions"].append(action)
            previous = CombatState.deepcopy(combat_state)
            simulator = CombatSimulator(previous)
            simulator.perform_action(action)
            picking_more = previous.pending_choice is not None
            batch["predicted"] = None if picking_more else previous
            batch["predicted_over"] = simulator.is_over
            batch["random_step"] = is_random_step(batch["before_sim"], previous, batch["actions"])

            before = dump(game_state)
            if action["action"] == "end_turn":
                ended = {"round": game_state.get("round"), "time": time.time()}
            act(action, game_state, picking_more)
            if action["action"] in ("play_card", "end_turn") and not wait_for_change(before):
                print("the game did not react to", action)
                log_mismatch(log_path, batch, get_state(), [f"the game ignored {action}, which the sim treats as legal"],
                             previous, None)
                input("fix it in the game, then press Enter ... \n")
                previous = batch = None
    except KeyboardInterrupt:
        print(f"\nstopped. {checked} step(s) checked, {mismatched} with differences" + (f" (see {log_path})" if mismatched else ""))

def main():
    parser = argparse.ArgumentParser(description="Let the agent play every combat; compare the sim with the game after each action.")
    parser.add_argument("--step", action="store_true", help="wait for Enter before every action")
    parser.add_argument("--no-verify", action="store_true", help="do not compare the sim with the game")
    parser.add_argument("--log", default=DEFAULT_LOG, help="where differences are written (JSON lines)")
    args = parser.parse_args()
    agent = MyAgent()
    run_agent(agent, step=args.step, verify=not args.no_verify, log_path=args.log)

if __name__ == "__main__":
    main()
