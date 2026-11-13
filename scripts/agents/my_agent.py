from agents.base_agent import BaseAgent

from sts2_lite.combat import CombatState, CombatSimulator

from agents.sts2_MCTS.MCTS import sts2_MCTS
from agents.sts2_MCTS.params import SearchConfig
    
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

## MCTS for combat. Every screen outside of combat falls back to BaseAgent's get_decision handlers (override a _get_<screen>_decision to take one over).
class MyAgent(BaseAgent):

    def __init__(self):
        super().__init__()
        self.name = "MCTS combat agent"
        self._mcts = sts2_MCTS()        # kept between calls: the next search reuses the part of this tree the game went into

    def get_combat_action(self, combat_state : CombatState, time_budget):
        mcts = self._mcts
        search_config = SearchConfig(time_budget=time_budget)
        c = CombatSimulator(combat_state)
        actions = c.get_available_actions()
        if len(actions) == 1:
            return actions[0]
        action, stats = mcts.monte_carlo_tree_search(combat_state, search_config)
        return action

    
