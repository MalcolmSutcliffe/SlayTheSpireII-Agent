from agents.base_agent import BaseAgent
from agents.my_agent import MyAgent

from sts2_lite.combat import CombatState, Combat


import json
import subprocess

DO_INTERNAL = False


def act(action):
    if action["action"] == "end_turn":
            subprocess.run(["cli-anything-sts2", "end-turn"])
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
    game_state = subprocess.run(["cli-anything-sts2", "state"], capture_output=True, text=True)
    game_state = json.loads(game_state.stdout)
    combat_state = CombatState.from_dict(game_state)
    
    if DO_INTERNAL:
        while True:
            c = Combat(combat_state)
            print(combat_state.readable())
            print(c.get_available_actions())
            input("waiting for input ... \n")
            action = agent.get_action(c.combat_state, 500)
            print(action)
            c.perform_action(action)

    else:
        while True:
            input("waiting for input ... \n")
            game_state = subprocess.run(["cli-anything-sts2", "state"], capture_output=True, text=True)
            game_state = json.loads(game_state.stdout)
            if game_state["type"] != "decision":
                continue
            if game_state["decision"] != "combat_play":
                continue
            combat_state = CombatState.from_dict(game_state)
            print(combat_state.readable())
            action = agent.get_action(combat_state, 1000)
            act(action)

def main():
    agent = MyAgent()
    run_agent(agent)
    
    



if __name__ == "__main__":
    main()
