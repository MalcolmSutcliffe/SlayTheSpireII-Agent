from agents.base_agent import BaseAgent

from sts2_lite.combat import CombatState, Combat

from agents.MCTS import sts2_MCTS
    
# Phase constants
PHASE_MAP_CHOICE = "MAP_CHOICE"
PHASE_COMBAT = "COMBAT"
PHASE_CARD_REWARD = "CARD_REWARD"
PHASE_BOSS_RELIC = "BOSS_RELIC"
PHASE_SHOP = "SHOP"
PHASE_REST_SITE = "REST_SITE"
PHASE_EVENT = "EVENT"
PHASE_TREASURE = "TREASURE"
PHASE_RUN_OVER = "RUN_OVER"

## Base class for an agent. Recieves a game state as an input and returns an action.
class MyAgent(BaseAgent):

    def __init__(self):
        self.name = "MCTS combat agent"

    def get_action(self, combat_state : CombatState, num_sims = 100):
        mcts = sts2_MCTS()
        c = Combat(combat_state)
        actions = c.get_available_actions()
        if len(actions) == 1:
            return actions[0]
        return mcts.monte_carlo_tree_search(combat_state, num_sims)

    