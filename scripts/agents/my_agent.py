from agents.base_agent import BaseAgent
from agents.pathing import PathPlanner

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
        self._planner = PathPlanner()
        self._card_chooser = None       # built on the first card reward (it reads the fight pool from data/runs)
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

    

    def _get_card_reward_decision(self, decision):
        """Each card (and skip) is tried on the same sample of fights: see agents/deck_eval."""
        if self._card_chooser is None:
            from agents.deck_eval.card_reward_chooser import CardRewardChooser
            self._card_chooser = CardRewardChooser(route_provider=lambda: self._planner.route)
        return self._card_chooser.choose(decision)

    def _get_map_decision(self, decision):
        """The route with the highest node score: see agents/pathing.py."""
        return self._planner.choose(decision)
