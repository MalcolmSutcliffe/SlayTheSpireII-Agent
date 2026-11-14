"""What to buy in a shop, one purchase per call (the shop screen comes back after each one, with the new gold and deck).

In order:
  1. a relic, if one can be afforded (the cheapest: prices are random, and the dearer uncommon and rare ones are overpriced); never the shop's own relic, the 3rd one listed (too situational for the agent to judge)
  2. potions, when the planned route meets an elite within the next 3 rooms: the best valued first (RewardParams.potion_bonus)
  3. a card, or a card removal, when the deck with it beats the deck without by Z standard errors on the fights ahead (the best gain first).
     The card removed is chosen first: a curse, else a Strike, else a Defend; with none of those left no removal is considered.
  4. otherwise leave."""
from __future__ import annotations
import time

from sts2_lite.card.constants import CARD_ENERGY_COST_AND_TARGET
from sts2_lite.card.ids import CardId
from sts2_lite.potion import PotionId

from agents.decision import Decision, Option
from agents.deck_eval.advisor import DeckAdvisor
from agents.deck_eval.card_reward_chooser import paired_gain
from agents.sts2_MCTS.params import RewardParams

SHOP_FIGHTS = 250
Z = 2.0
ELITE_LOOKAHEAD = 3         # rooms on the planned route
SHOP_RELIC_POSITION = 2     # the 3rd relic listed
POTION_BONUS = RewardParams()


def removal_rank(card : dict) -> int | None:
    """0 curse, 1 Strike, 2 Defend; None for a card the agent keeps (or cannot remove)."""
    if card.get("removable") is False:
        return None
    if card.get("type") == "Curse" or card.get("rarity") == "Curse":
        return 0
    card_id = str(card.get("id", ""))
    if card_id.startswith("STRIKE"):
        return 1
    if card_id.startswith("DEFEND"):
        return 2
    return None


def card_to_remove(deck : list[dict]) -> int | None:
    """Index in `deck` of the card to remove: the lowest rank, the first of its kind."""
    ranked = [(removal_rank(c), i) for i, c in enumerate(deck) if removal_rank(c) is not None]
    return min(ranked)[1] if ranked else None


def potion_value(item : dict) -> float:
    potion = PotionId.from_game_id(item.get("potion_id"))
    return POTION_BONUS.potion_bonus.get(potion, POTION_BONUS.default_potion_bonus)


def _z(gain : float, se : float) -> float:
    return gain / se if se > 0 else (float("inf") if gain > 0 else 0.0)


class ShopChooser:
    def __init__(self, advisor : DeckAdvisor):
        self.advisor = advisor

    def card_dict(self, item : dict) -> dict:
        """The deck entry for a shop card: the energy cost and target come from the card constants (the shop shows only gold)."""
        cost, target = CARD_ENERGY_COST_AND_TARGET.get(CardId.__members__.get(item["card_id"]), (1, None))
        return {"id": item["card_id"], "name": item.get("card_name", item["card_id"]), "type": item.get("card_type"),
                "rarity": item.get("card_rarity"), "cost": cost, "target_type": target.name if target is not None else None, "is_upgraded": False}

    def choose(self, decision : Decision) -> Option:
        buys = [o for o in decision.options if o.name == "shop_purchase"]
        leave = next((o for o in decision.options if o.name == "proceed"), decision.options[-1])
        items = decision.state.get("items") or []
        relic_items = [i for i in items if i.get("category") == "relic"]
        shop_relic = relic_items[SHOP_RELIC_POSITION]["index"] if len(relic_items) > SHOP_RELIC_POSITION else None

        relics = [o for o in buys if o.data.get("category") == "relic" and o.data.get("index") != shop_relic]
        if relics:
            return min(relics, key=lambda o: o.data.get("cost", 0))

        route = self.advisor.route_provider()
        if route is not None and "elite" in route.kinds[1:1 + ELITE_LOOKAHEAD]:
            potions = [o for o in buys if o.data.get("category") == "potion"]
            if potions:
                return max(potions, key=lambda o: (potion_value(o.data), -o.data.get("cost", 0)))

        picked = self._best_deck_change(decision, buys)
        return picked or leave

    def _best_deck_change(self, decision : Decision, buys : list[Option]) -> Option | None:
        deck = decision.player.get("deck") or []
        candidates = []     # (option, the deck after it)
        for o in buys:
            item = o.data
            if item.get("category") == "card" and item.get("card_id"):
                candidates.append((o, deck + [self.card_dict(item)]))
            elif item.get("category") == "card_removal":
                i = card_to_remove(deck)
                if i is not None:
                    candidates.append((o, deck[:i] + deck[i + 1:]))
        if not candidates:
            return None
        mix, fights, seed, _ = self.advisor.sample(decision, SHOP_FIGHTS)
        ev, player, start = self.advisor.evaluator, decision.player, time.perf_counter()
        base = ev.score(deck, player, fights, seed)
        rows = []
        for o, new_deck in candidates:
            gain, se = paired_gain(ev.score(new_deck, player, fights, seed).rewards, base.rewards)
            rows.append((gain, _z(gain, se), o))
        worth = [r for r in rows if r[1] > Z]
        self.advisor.log("shop (%d gold, %d fights, %.1fs): " % (player.get("gold", 0), len(fights), time.perf_counter() - start) +
                         ", ".join("%s %+.2f (z %.1f)" % (r[2].label, r[0], r[1]) for r in sorted(rows, key=lambda r: -r[0])) +
                         (" -> " + max(worth, key=lambda r: r[0])[2].label if worth else " -> nothing worth it"))
        return max(worth, key=lambda r: r[0])[2] if worth else None
