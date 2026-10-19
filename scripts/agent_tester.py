from agents.base_agent import BaseAgent
from agents.my_agent import MyAgent

from sts2_env.run.run_manager import RunManager, SUPPORTED_CHARACTER_IDS


import json
import subprocess


def run_agent():
    # set up new mgr
    seed = 0;

def act(action):
    if action["action"] == "end_turn":
            subprocess.run(["cli-anything-sts2", "end-turn"])
    if action["action"] == "play_card":
        if "target_name" in action:
            subprocess.run(["cli-anything-sts2", 
                            "play-card", 
                            str(action["hand_index"]),
                            "--target", 
                            action["target_name"] + "_0"])
        else:
            subprocess.run(["cli-anything-sts2", "play-card", str(action["hand_index"])])

def main():
    agent = MyAgent()
    # get state from command line
    # make RunManager 
    # get agent output
    seed = 0
    mgr = RunManager(seed = seed, ascension_level=0, start_with_neow=True) # ironclad ascension 0 ...
    game_state = subprocess.run(["cli-anything-sts2", "state"], capture_output=True, text=True)
    game_state = json.loads(game_state.stdout)
    if game_state["type"] != "decision":
        return
    if game_state["decision"] != "combat_play":
        return
    mgr.align_to_combat_state(game_state)
    action = agent.get_action(mgr, 10)
    print(action)
    act(action)
    



if __name__ == "__main__":
    main()
