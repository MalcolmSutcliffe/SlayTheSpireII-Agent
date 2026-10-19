import copy

from agents.base_agent import BaseAgent

from sts2_env.run.run_manager import RunManager
from sts2_env.run.run_state import PlayerState
from sts2_env.core.combat import CombatState
from sts2_env.core.creature import Creature

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

    def get_action(self, mgr : RunManager, num_sims = 100) -> dict:
        if mgr.phase == PHASE_COMBAT:
            return self._get_combat_action(mgr, num_sims)
        actions = mgr.get_available_actions()
        return actions[0]

    def _get_combat_action(self, mgr : RunManager, num_sims):

        # run Monte Carlo Tree Search on combat to decide card to play

        actions = mgr.get_available_actions()

        if mgr.phase != PHASE_COMBAT:
            return actions[0]

        # copy run manager state
        mgr_copy = copy.deepcopy(mgr)

        mcts = sts2_MCTS()

        best_move = mcts.monte_carlo_tree_search(mgr_copy, num_sims)
        return best_move

    def _rate_combat_state(self, combat_state : CombatState) -> float:
        current_hp = combat_state.player.current_hp
        max_hp = combat_state.player.max_hp
        
        return float(current_hp) / max_hp

    def _rate_run_state(self, mgr : RunManager) -> float:
        # returns = % of total max HP (overlooks a lot for now, but good for combat)

        current_hp = mgr.get_combat_state().player.current_hp
        max_hp = mgr.get_combat_state().max_hp

        return float(current_hp) / max_hp

    def _is_combat_over(self, combat_state : CombatState):
        return combat_state.is_over
    