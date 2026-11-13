import random

from sts2_lite.combat import CombatState, CombatSimulator

from agents.decision import Decision, Option, MAP, CARD_REWARD, REWARDS, REST, SHOP, EVENT, CARD_SELECT, RELIC, TREASURE

REST_HEAL_BELOW = 0.7       # the default agent rests when HP is under this share of max HP, and upgrades a card otherwise

## Base class for an agent. Recieves a game state as an input and returns an action.
class BaseAgent:
    name = "Barkus"

    def __init__(self):
        self._rng = random.Random()

    def get_combat_action(self, combat_state : CombatState, time_budget : float | None = None):
        """The action to play in a fight: one of CombatSimulator(combat_state).get_available_actions(). `time_budget`: seconds the agent may think."""
        c = CombatSimulator(combat_state)
        actions = c.get_available_actions()
        return actions[0]

    ###
    ### Outside of combat: one handler per screen, each returning one of decision.options.
    ### The defaults only keep the run moving; an agent overrides the screens it has an opinion on.
    ###

    def get_decision(self, decision : Decision) -> Option:
        handler = {MAP: self._get_map_decision, CARD_REWARD: self._get_card_reward_decision, REWARDS: self._get_rewards_decision,
                   REST: self._get_rest_decision, SHOP: self._get_shop_decision, EVENT: self._get_event_decision,
                   CARD_SELECT: self._get_card_select_decision, RELIC: self._get_relic_decision,
                   TREASURE: self._get_treasure_decision}[decision.kind]
        return handler(decision)

    def _rng_choice(self, options : list[Option]) -> Option:
        if not hasattr(self, "_rng"):       # a subclass that does not call BaseAgent.__init__
            self._rng = random.Random()
        return self._rng.choice(options)

    def _get_map_decision(self, decision : Decision) -> Option:
        return decision.options[0]

    def _get_card_reward_decision(self, decision : Decision) -> Option:
        return self._rng_choice(decision.options)       # uniformly at random among the cards and Skip: with 3 cards Skip comes 1 time in 4

    def _get_rewards_decision(self, decision : Decision) -> Option:
        claims = decision.options_named("claim_reward")
        return claims[0] if claims else decision.options[0]

    def _get_rest_decision(self, decision : Decision) -> Option:
        by_id = {o.data.get("id"): o for o in decision.options_named("choose_rest_option")}
        player = decision.player
        hurt = player.get("hp", 0) < REST_HEAL_BELOW * player.get("max_hp", 1)
        for wanted in (("HEAL", "SMITH") if hurt else ("SMITH", "HEAL")):
            if wanted in by_id:
                return by_id[wanted]
        return decision.options[0]

    def _get_shop_decision(self, decision : Decision) -> Option:
        leave = decision.options_named("proceed")
        return leave[0] if leave else decision.options[0]       # buys nothing

    def _get_event_decision(self, decision : Decision) -> Option:
        return decision.options[0]

    RARITY_FOR_UPGRADE = {"Rare": 3, "Uncommon": 2, "Common": 1, "Basic": 0}       # anything else (a curse, a status) ranks below Basic

    def _get_card_select_decision(self, decision : Decision) -> Option:
        confirm = decision.options_named("confirm_selection")
        if confirm:
            return confirm[0]
        picks = decision.options_named("select_card")
        if not picks:
            return decision.options[0]
        if decision.state.get("screen_type") == "upgrade":
            return self._card_to_upgrade(picks)
        return picks[0]

    def _card_to_upgrade(self, picks : list[Option]) -> Option:
        """A card not upgraded yet, rarest first (Rare, Uncommon, Common, Basic); of equal rarity the last one on the screen."""
        def rank(item):
            position, option = item
            return (not option.data.get("is_upgraded", False), self.RARITY_FOR_UPGRADE.get(option.data.get("rarity"), -1), position)
        return max(enumerate(picks), key=rank)[1]

    def _get_relic_decision(self, decision : Decision) -> Option:
        picks = decision.options_named("select_relic")
        return picks[0] if picks else decision.options[0]

    def _get_treasure_decision(self, decision : Decision) -> Option:
        claims = decision.options_named("claim_treasure_relic")
        return claims[0] if claims else decision.options[0]
