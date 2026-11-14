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
        self._advisor = None            # the fight pool and evaluator the deck choosers share: built on first use (it reads data/runs)
        self._card_chooser = None
        self._upgrader = None
        self._shopper = None
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

    

    def _deck_advisor(self):
        if self._advisor is None:
            from agents.deck_eval.advisor import DeckAdvisor
            self._advisor = DeckAdvisor(route_provider=lambda: self._planner.route)
        return self._advisor

    def _get_card_reward_decision(self, decision):
        """Each card (and skip) is tried on the same sample of fights: see agents/deck_eval."""
        if self._card_chooser is None:
            from agents.deck_eval.card_reward_chooser import CardRewardChooser
            self._card_chooser = CardRewardChooser(advisor=self._deck_advisor())
        return self._card_chooser.choose(decision)

    def _upgrade_chooser(self):
        if self._upgrader is None:
            from agents.deck_eval.upgrade_chooser import UpgradeChooser
            self._upgrader = UpgradeChooser(self._deck_advisor())
        return self._upgrader

    def _get_rest_decision(self, decision):
        """Smith or heal, by what each is worth on the fights ahead."""
        return self._upgrade_chooser().choose_rest(decision) or super()._get_rest_decision(decision)

    def _get_shop_decision(self, decision):
        """Relics, then potions before an elite, then the cards and removals that clearly help: see agents/deck_eval/shop_chooser.py."""
        if self._shopper is None:
            from agents.deck_eval.shop_chooser import ShopChooser
            self._shopper = ShopChooser(self._deck_advisor())
        return self._shopper.choose(decision)

    def _get_card_select_decision(self, decision):
        picks = decision.options_named("select_card")
        if picks and not decision.options_named("confirm_selection") and "remove" in str(decision.state.get("screen_type", "")).lower():
            from agents.deck_eval.shop_chooser import removal_rank
            ranked = [(removal_rank(o.data), -i, o) for i, o in enumerate(picks) if removal_rank(o.data) is not None]
            if ranked:      # a curse, else a Strike, else a Defend
                return min(ranked, key=lambda r: (r[0], -r[1]))[2]
        if picks and not decision.options_named("confirm_selection") and decision.state.get("screen_type") == "upgrade":
            chosen = self._upgrade_chooser().choose_card(decision, picks)
            if chosen is not None:
                return chosen
        return super()._get_card_select_decision(decision)

    def _get_map_decision(self, decision):
        """The route with the highest node score: see agents/pathing.py."""
        return self._planner.choose(decision)
