import re

from sts2_lite.combat import CombatState, CombatSimulator

from agents.base_agent import BaseAgent
from agents.pathing import PathPlanner
from agents.potion_cycle import FoulPotions, cycle as cycle_potions
from agents.deck_eval.advisor import DeckAdvisor
from agents.deck_eval.ancient_chooser import AncientChooser
from agents.deck_eval.boss_spawner import BOSS_ACTS, normalize_boss_id
from agents.deck_eval.card_reward_chooser import CardRewardChooser
from agents.deck_eval.cards import removal_rank, transform_rank
from agents.deck_eval.config import DEFAULT as DEFAULT_DECK_CONFIG, DeckEvalConfig
from agents.deck_eval.elite_odds import act_id, identify
from agents.deck_eval.event_chooser import EventChooser
from agents.deck_eval.shop_chooser import ShopChooser
from agents.deck_eval.upgrade_chooser import UpgradeChooser
from agents.sts2_MCTS.MCTS import sts2_MCTS
from agents.sts2_MCTS.params import SearchConfig

def enchant_score(card : dict) -> float:
    """How much an enchantment is worth on a card (Sharp, Adroit, Swift ... all pay per play): a card played often and cheaply, one that hits several times, a good card over a Basic one.
    A card that is enchanted already ranks last."""
    if card.get("enchantment") or card.get("enchanted"):
        return -10.0
    text = str(card.get("description", ""))
    hits = 2 if re.search(r"twice|2 times", text, re.I) else int(m.group(1)) if (m := re.search(r"(\d+) times", text)) else 1
    cost = str(card.get("cost", "1"))
    cheap = 1.0 if cost in ("0", "1", "X") else 0.0
    rarity = {"Rare": 1.5, "Uncommon": 1.0, "Common": 0.5}.get(card.get("rarity"), 0.0)
    return hits + cheap + rarity + (0.25 if card.get("is_upgraded") else 0.0)


## MCTS for combat. Every screen outside of combat falls back to BaseAgent's get_decision handlers (override a _get_<screen>_decision to take one over).
class MyAgent(BaseAgent):

    def __init__(self, seed : int | None = None, deck_config : DeckEvalConfig = DEFAULT_DECK_CONFIG):
        """`seed` seeds the deck evaluator's walks (None: drawn at random); `deck_config` tunes every out-of-combat chooser (agents/deck_eval/config.py)."""
        super().__init__()
        self._seed = seed
        self._deck_config = deck_config
        self.name = "MCTS combat agent"
        self._planner = PathPlanner()
        self._advisor = None            # the fight pool and evaluator the deck choosers share: built on first use
        self._card_chooser = None
        self._upgrader = None
        self._shopper = None
        self._fouls = FoulPotions()
        self._eventer = None
        self._ancient = None
        self._mcts = sts2_MCTS()        # kept between calls: the next search reuses the part of this tree the game went into

    def get_combat_action(self, combat_state : CombatState, time_budget):
        self._note_elite(combat_state)
        mcts = self._mcts
        search_config = SearchConfig(time_budget=time_budget)
        c = CombatSimulator(combat_state)
        actions = c.get_available_actions()
        if len(actions) == 1:
            return actions[0]
        action, stats = mcts.monte_carlo_tree_search(combat_state, search_config)
        return action

    

    def _note_elite(self, combat_state : CombatState):
        """In an elite room, remember which elite it is (once): the game deals an act's elites from a bag, so the elites met say which can come next."""
        route = self._planner.route
        if route is None or not route.kinds or route.kinds[0] != "elite" or route.elite_counted:
            return
        boss = normalize_boss_id(route.boss)
        variant = BOSS_ACTS[boss][1] if boss in BOSS_ACTS and route.act == 1 else route.act_model
        self._planner.note_elite(identify(act_id(route.act, variant), [e.enemy_id for e in combat_state.enemies]))

    def _deck_advisor(self):
        if self._advisor is None:
            self._advisor = DeckAdvisor(route_provider=lambda: self._planner.route, seed=self._seed, config=self._deck_config)
        return self._advisor

    def _get_card_reward_decision(self, decision):
        """Each card (and skip) is tried on the same sample of fights: see agents/deck_eval."""
        if self._card_chooser is None:
            self._card_chooser = CardRewardChooser(advisor=self._deck_advisor())
        return self._card_chooser.choose(decision)

    def _upgrade_chooser(self):
        if self._upgrader is None:
            self._upgrader = UpgradeChooser(self._deck_advisor())
        return self._upgrader

    def _get_rest_decision(self, decision):
        """Smith or heal, by what each is worth on the fights ahead."""
        return self._upgrade_chooser().choose_rest(decision) or super()._get_rest_decision(decision)

    def _get_rewards_decision(self, decision):
        """Fruit Juice is drunk; a full belt gives up a Blood Potion / Fruit Juice or its worst potion for a better one on offer (agents/potion_cycle.py); then the rewards are claimed in order."""
        return cycle_potions(decision) or super()._get_rewards_decision(decision)

    def _get_shop_decision(self, decision):
        """Every relic, card and the removal rated by the deck evaluator (a Z-score over deck_config.shop_z to buy): relics first, then potions before an elite, then the best card or removal: see agents/deck_eval/shop_chooser.py."""
        used = self._fouls.choose(decision)          # a Foul Potion thrown at the merchant is 100 gold
        if used is not None:
            return used
        if self._shopper is None:
            self._shopper = ShopChooser(self._deck_advisor())
        return self._shopper.choose(decision)

    def _get_event_decision(self, decision):
        """The option whose outcome walks best through the rest of the act (the engine's event model, then route walks): see agents/deck_eval/event_chooser.py. The ancients' relics are chosen the same way (ancient_chooser.py). Events the engine does not model are BaseAgent's."""
        if self._eventer is None:
            self._eventer, self._ancient = EventChooser(self._deck_advisor()), AncientChooser(self._deck_advisor())
        return self._ancient.choose(decision) or self._eventer.choose(decision) or super()._get_event_decision(decision)

    def _card_to_select(self, decision, picks):
        """A card among `picks` (the ones not picked yet) by what the screen does with it: removals take the worst cards (a curse, a Strike, a Defend, then the lowest rarity), transforms a Strike, a Defend, then the lowest rarity (a curse only becomes another curse),
        an upgrade the card with the best gain on the walks, an enchantment the card that will use it most (see `enchant_score`)."""
        screen = "%s %s" % (decision.state.get("screen_type", ""), decision.state.get("prompt", ""))
        if re.search(r"transform", screen, re.I):
            return min(enumerate(picks), key=lambda item: (transform_rank(item[1].data), item[0]))[1]
        if re.search(r"remove", screen, re.I):
            def worst(item):
                position, option = item
                rank = removal_rank(option.data)
                return (rank if rank is not None else 3, self.RARITY_FOR_UPGRADE.get(option.data.get("rarity"), -1), position)
            return min(enumerate(picks), key=worst)[1]
        if decision.state.get("screen_type") == "upgrade":
            chosen = self._upgrade_chooser().choose_card(decision, picks)
            if chosen is not None:
                return chosen
        elif re.search(r"enchant", screen, re.I):
            return max(enumerate(picks), key=lambda item: (enchant_score(item[1].data), -item[0]))[1]
        return super()._card_to_select(decision, picks)

    def _get_map_decision(self, decision):
        """The path whose walks through the rest of the map do best (deck_eval/path_search.py); the node scores of agents/pathing.py rank the paths to walk."""
        self._planner.advisor = self._deck_advisor()
        return self._planner.choose(decision)
