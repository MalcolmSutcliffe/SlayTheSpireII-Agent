import random
import re

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

    rest_heal_below = REST_HEAL_BELOW

    def _get_rest_decision(self, decision : Decision) -> Option:
        by_id = {o.data.get("id"): o for o in decision.options_named("choose_rest_option")}
        player = decision.player
        hurt = player.get("hp", 0) < self.rest_heal_below * player.get("max_hp", 1)
        for wanted in (("HEAL", "SMITH") if hurt else ("SMITH", "HEAL")):
            if wanted in by_id:
                return by_id[wanted]
        return decision.options[0]

    def _get_shop_decision(self, decision : Decision) -> Option:
        leave = decision.options_named("proceed")
        return leave[0] if leave else decision.options[0]       # buys nothing

    def _get_event_decision(self, decision : Decision) -> Option:
        return self._rng_choice(decision.options)       # events and ancients: any option, for variety

    RARITY_FOR_UPGRADE = {"Rare": 3, "Uncommon": 2, "Common": 1, "Basic": 0}       # anything else (a curse, a status) ranks below Basic

    def _get_card_select_decision(self, decision : Decision) -> Option:
        """A card screen that wants N cards ("Choose 3 cards to Enchant."): pick one card per call until N are picked, then confirm once.
        The game's screen does not mark the cards picked so far (the engine's does: a `selected` list), so the picks are counted here."""
        confirm = decision.options_named("confirm_selection")
        picks = decision.options_named("select_card")
        wanted = self._cards_wanted(decision.state.get("prompt"))
        selected = decision.state.get("selected")
        if selected is not None:        # the screen lists what is picked: its cards are the ones still on offer
            done, left = len(selected), picks
        else:
            done, left = self._picked_so_far(decision, picks)
        if confirm and (wanted is None or done >= wanted or not left):
            self._screen_picks = None
            return confirm[0]
        if not left:
            return decision.options[0]
        choice = self._card_to_select(decision, left)
        if selected is None and self._screen_picks is not None:
            self._screen_picks[1].append(choice.action["index"])
        return choice

    @staticmethod
    def _cards_wanted(prompt) -> int | None:
        """How many cards a screen asks for: "Choose 5 cards to Remove." -> 5, "Choose a card to Upgrade." -> 1, no such prompt -> None."""
        match = re.search(r"Choose (\d+|an?) cards?", prompt or "")
        if not match:
            return None
        return 1 if match.group(1) in ("a", "an") else int(match.group(1))

    _screen_picks = None

    def _picked_so_far(self, decision : Decision, picks : list[Option]) -> tuple[int, list[Option]]:
        """(the number of cards picked on this screen, the cards still on offer): a screen is the same one while its prompt and cards are.
        The key is the screen's whole card list, not `picks`: the runner drops a card the game did not seem to react to (the first pick of two changes nothing on the screen),
        and a key built from what is left would start the count again when the preview comes up."""
        key = (decision.state.get("prompt"), tuple((c.get("index"), c.get("id")) for c in decision.state.get("cards") or ()) or tuple(o.data.get("id") for o in picks))
        if self._screen_picks is None or self._screen_picks[0] != key:
            self._screen_picks = (key, [])
        taken = self._screen_picks[1]
        return len(taken), [o for o in picks if o.action["index"] not in taken]

    def _card_to_select(self, decision : Decision, picks : list[Option]) -> Option:
        """The card to pick among `picks`: an upgrade takes the best card to upgrade, anything else the first."""
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
