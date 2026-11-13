"""Everything that talks to the live game through cli-anything-sts2: read its state, send it an action.
The loop and the combat code only ever go through a GameClient, so a test can hand them a scripted one instead."""
import json
import subprocess
import time

from sts2_lite.selection import game_index

CLI = "cli-anything-sts2"
POLL_SECONDS = 0.4              # between state reads while the game is busy or it is not the agent's turn
SETTLE_READS = 3                # identical reads in a row before a state is trusted
SETTLE_INTERVAL = 0.25          # seconds between those reads
ACTION_TIMEOUT = 8.0            # seconds to wait for the game to react to a play_card / end_turn

def dump(game_state : dict) -> str:
    return json.dumps(game_state, sort_keys=True)

def pile_total(game_state : dict) -> int:
    """Cards in the hand and the three piles. A card being played or auto-played sits in none of them."""
    player = game_state.get("player") or {}
    return len(game_state.get("hand") or []) + sum(player.get(k, 0) or 0 for k in ("draw_pile_count", "discard_pile_count", "exhaust_pile_count"))


class GameClient:
    """The live game: `get_state` reads it, `act` sends it an action, and the rest are the waiting and clicking that go with them."""

    def __init__(self):
        self.picked_on_screen = []      # game indices already selected on an "up to N" pile screen (Neow's Fury)

    def command(self, *args : str):
        return subprocess.run([CLI, *args])

    ###
    ### Reading the game
    ###

    def get_state(self) -> dict:
        result = subprocess.run([CLI, "state"], capture_output=True, text=True)
        return json.loads(result.stdout)

    def settled(self, game_state : dict, cards_owed : int | None = None) -> dict:
        """A card's cost is paid before its effect lands, and a turn starts in stages: take the first state that
        reads the same SETTLE_READS times in a row. `cards_owed`: a card being played, auto-played (Havoc) or exhausted
        (Toasty Mittens) is in limbo, and the game can pause there with the same state on every read: wait until the hand and piles hold
        the number of cards the sim expects."""
        stable = 1
        for _ in range(40 if cards_owed is None else 60):
            time.sleep(SETTLE_INTERVAL)
            again = self.get_state()
            if dump(again) == dump(game_state):
                stable += 1
                if stable >= SETTLE_READS and (cards_owed is None or pile_total(again) == cards_owed):
                    return again
            else:
                stable, game_state = 1, again
        return game_state

    def wait_for_change(self, before : str) -> bool:
        """After an action: wait until the game reports something other than `before`. False if it never does."""
        deadline = time.time() + ACTION_TIMEOUT
        while time.time() < deadline:
            time.sleep(POLL_SECONDS)
            if dump(self.get_state()) != before:
                return True
        return False

    ###
    ### Sending to the game
    ###

    def confirm_if_ready(self):
        """A picked card still has to be confirmed once the game allows it."""
        state = self.get_state()
        if not state.get("can_confirm"):
            return
        if state.get("decision") == "hand_select":
            self.command("combat-confirm-selection")
        elif state.get("decision") == "card_select":
            self.command("confirm-selection")

    def auto_pick(self, game_state : dict):
        """The sim settled a pick by itself because every card on offer was the same (Armaments with two Defends), but the
        game still shows the screen: select the first card and confirm."""
        command = "combat-select-card" if game_state.get("decision") == "hand_select" else "select-card"
        self.command(command, str(game_state["cards"][0]["index"]))
        self.confirm_if_ready()

    def act(self, action : dict, game_state : dict | None = None, picking_more : bool = False):
        """`picking_more`: the sim still waits for a pick after this action, so the screen must not be confirmed yet."""
        if action["action"] == "end_turn":
            self.command("end-turn")
        if action["action"] == "use_potion":
            command = ["use-potion", str(action["slot"])]        # the command's format is a guess: check it once on a real run
            if "target_name" in action:
                command += ["--target", action["target_name"]]
            self.command(*command)
        if action["action"] == "choose_card":
            # both kinds of screen number only the selectable cards, in the game's own order: find the card there
            # the in-combat hand screen drops a picked card from its list and renumbers the rest, so earlier picks must not be skipped there;
            # a pile screen keeps its list, and the picked indices stay
            index = game_index(action, game_state["cards"], skip=self.picked_on_screen if action.get("pile", "hand") != "hand" else ())
            if index is None:
                print("card", action["card_id"], "is not in the game's list - pick it in the game")
                return
            command = "combat-select-card" if action.get("pile", "hand") == "hand" else "select-card"
            self.command(command, str(index))
            self.picked_on_screen.append(index)
            if not picking_more:
                self.picked_on_screen.clear()
                self.confirm_if_ready()
        if action["action"] == "confirm_choice":
            # stop an "up to N" pick with what is selected so far; a "choose a card" screen (Discovery) has no confirm: skip it
            self.picked_on_screen.clear()
            if game_state is not None and game_state.get("screen_type") == "choose":
                self.command("cancel-selection")
            else:
                self.confirm_if_ready()
        if action["action"] == "play_card":
            if "target_name" in action:
                self.command("play-card", str(action["card_index"]), "--target", action["target_name"])
            else:
                self.command("play-card", str(action["card_index"]))
