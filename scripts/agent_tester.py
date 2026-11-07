from agents.base_agent import BaseAgent
from agents.my_agent import MyAgent

from sts2_lite.combat import CombatState, CombatSimulator
from sts2_lite.selection import game_index


import json
import subprocess

DO_INTERNAL = False

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
        if action.get("pile", "hand") == "hand":
            subprocess.run(["cli-anything-sts2", "combat-select-card", str(action["card_index"])])
        else:
            # a pile screen lists the pile in the game's own order: find the card there
            index = game_index(action, game_state["cards"], skip=picked_on_screen)
            if index is None:
                print("card", action["card_id"], "is not in the game's list - pick it in the game")
                return
            subprocess.run(["cli-anything-sts2", "select-card", str(index)])
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

def run_agent(agent : BaseAgent):
    
    
    if DO_INTERNAL:
        with open("example_output.json", "r") as f:
            game_state = json.load(f)
        combat_state = CombatState.from_dict(game_state)
        c = CombatSimulator(combat_state)
        # c.perform_action({'action': 'play_card', 'card_index': 3, 'target': 1, 'target_name': 'PHANTASMAL_GARDENER_1'})
        action = agent.get_action(c.combat_state)
        print(action)
    else:
        game_state = subprocess.run(["cli-anything-sts2", "state"], capture_output=True, text=True)
        game_state = json.loads(game_state.stdout)
        combat_state = CombatState.from_dict(game_state)
        previous = None     # state after the last action: the bridge reports no per-turn history
        while True:
            input("waiting for input ... \n")
            game_state = subprocess.run(["cli-anything-sts2", "state"], capture_output=True, text=True)
            game_state = json.loads(game_state.stdout)
            if game_state["type"] != "decision":
                continue
            decision = game_state["decision"]
            if decision not in ("combat_play", "hand_select", "card_select"):
                continue
            if decision == "card_select" and game_state.get("screen_type") != "NCombatPileCardSelectScreen":
                continue                # not a pick made during combat
            choosing_optionally = previous is not None and previous.pending_choice is not None and previous.pending_choice.optional
            if decision != "combat_play" and game_state.get("can_confirm") and not choosing_optionally:
                picked_on_screen.clear()
                confirm_if_ready()      # a card is already picked; only the confirmation is missing
                continue                # (an "up to N" screen can be confirmed from the start: the agent decides)
            if decision != "combat_play" and previous is not None and previous.pending_choice is not None:
                # the sim knows what this pick is for; a pile screen has no fight data to load
                combat_state = CombatState.deepcopy(previous)
            elif decision != "card_select":
                combat_state = CombatState.from_dict(game_state)
                combat_state.carry_turn_counters(previous)
                combat_state.carry_known_top(previous)    # cards the agent put on top (Headbutt)
                combat_state.carry_combat_counters(previous)    # HP-loss events (Tear Asunder), Inferno plays
            else:
                print("cannot read this card selection - pick it in the game")
                continue
            # print(combat_state.readable())
            action = agent.get_action(combat_state, 5000)
            print(action)
            previous = CombatState.deepcopy(combat_state)
            CombatSimulator(previous).perform_action(action)
            act(action, game_state, picking_more=previous.pending_choice is not None)

def main():
    agent = MyAgent()
    run_agent(agent)
    
    

if __name__ == "__main__":
    main()
