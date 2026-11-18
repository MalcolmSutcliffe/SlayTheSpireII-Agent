"""What to buy in a shop, one purchase per call (the shop screen comes back after each one, with the new gold and deck).

Everything is judged by the deck evaluator: each candidate is played on the same walks through the rest of the act (the engine's run simulator: the fights one after the other
with the HP carried over, the rest sites, rewards and relics: see route_sim and DeckEvaluator.score_walks) and compared with buying nothing, walk for walk. A candidate's
price is paid in its walks (the gold is gone from the shops ahead). Its Z-score is the mean gain over the standard error of the gain.
In order:
  1. among the relics, cards and the card removal whose Z-score is over `shop_z`, the one with the most gain per gold (relics are played by the engine's own pickup, route_sim.ShopRelicPlan; the shop's own relic,
     the 3rd one listed, is judged like the others). The card removed is chosen first: a curse, else a Strike, else a Defend; with none of those left no removal is considered.
  2. potions, when the planned route meets an elite or the boss within the next `potion_lookahead` rooms: the best valued first (RewardParams.potion_bonus)
  3. otherwise leave.
In the last shop the agent plans to visit in act 3 (the planned route has no shop after this one) the Z-score asked for is `last_shop_z` (0.1) instead of `shop_z`: there is no later shop for the gold.
The analysis runs for at most `shop_seconds`: as many walks as fit, every candidate (relics, cards and the removal) on each.
The numbers are DeckEvalConfig's (config.py).
"""
from __future__ import annotations
from typing import NamedTuple

from sts2_lite.card.constants import CARD_ENERGY_COST_AND_TARGET
from sts2_lite.card.ids import CardId
from sts2_lite.potion import PotionId

from agents.decision import Decision, Option
from agents.deck_eval.advisor import DeckAdvisor, paired_gain
from agents.deck_eval.cards import card_to_remove, removal_rank  # noqa: F401  (removal_rank: re-exported for the tests)
from agents.deck_eval.route_sim import ShopRelicPlan
from agents.sts2_MCTS.params import RewardParams

DANGEROUS_ROOMS = ("elite", "boss")
POTION_BONUS = RewardParams()


def potion_value(item : dict) -> float:
    potion = PotionId.from_game_id(item.get("potion_id"))
    return POTION_BONUS.potion_bonus.get(potion, POTION_BONUS.default_potion_bonus)


def _z(gain : float, se : float) -> float:
    return gain / se if se > 0 else (float("inf") if gain > 0 else 0.0)


class Row(NamedTuple):
    option : Option
    kind : str          # "relic", "card" or "removal"
    gain : float
    z : float


def best(rows : list[Row]) -> Row:
    """The row with the most gain per gold (a free item counts its whole gain, a cost of 1 gold at least)."""
    return max(rows, key=lambda r: (r.gain / max(1, r.option.data.get("cost", 0)), r.z))


def last_shop(route) -> bool:
    """The planned route is in act 3 and has no shop after the one the agent is in (`kinds[0]`)."""
    return route is not None and getattr(route, "act", None) == 3 and "shop" not in list(route.kinds)[1:]


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
        leave = next((o for o in decision.options if o.name == "proceed"), None) or Option("leave shop", {"action": "proceed"})
        relics = [o for o in buys if o.data.get("category") == "relic" and o.data.get("relic_id")]

        cfg = self.advisor.config
        rows = self._analyse(decision, relics, buys)
        route = self.advisor.route_provider()
        last = last_shop(route)
        worth = [r for r in rows if r.z > (cfg.last_shop_z if last else cfg.shop_z)]
        if worth:
            return best(worth).option

        if route is not None and any(kind in DANGEROUS_ROOMS for kind in route.kinds[1:1 + cfg.potion_lookahead]):
            sozu = any(r.get("id") == "SOZU" for r in decision.player.get("relics") or [] if isinstance(r, dict))
            potions = [] if sozu else [o for o in buys if o.data.get("category") == "potion"]      # Sozu: a bought potion never arrives
            if potions:
                return max(potions, key=lambda o: (potion_value(o.data), -o.data.get("cost", 0)))

        return leave

    def _analyse(self, decision : Decision, relics : list[Option], buys : list[Option]) -> list[Row]:
        """Every relic, card and the removal played on the same walks as buying nothing: a Row for each (empty when there is nothing to buy)."""
        player = decision.player
        deck, gold = player.get("deck") or [], player.get("gold", 0)
        paid = lambda cost: {**player, "gold": max(0, gold - cost)}
        ev = self.advisor.evaluator
        candidates = []     # (option, kind, play(walks) -> rewards)
        for o in relics:
            plan = ShopRelicPlan(o.data["relic_id"], o.data.get("cost", 0))
            candidates.append((o, "relic", lambda walks, plan=plan: ev.score_walks(deck, player, walks, plan).rewards))
        for o in buys:
            item = o.data
            if item.get("category") == "card" and item.get("card_id"):
                new_deck, after = deck + [self.card_dict(item)], paid(item.get("cost", 0))
                candidates.append((o, "card", lambda walks, d=new_deck, p=after: ev.score_walks(d, p, walks).rewards))
            elif item.get("category") == "card_removal":
                i = card_to_remove(deck)
                if i is not None:
                    new_deck, after = deck[:i] + deck[i + 1:], paid(item.get("cost", 0))
                    candidates.append((o, "removal", lambda walks, d=new_deck, p=after: ev.score_walks(d, p, walks).rewards))
        if not candidates:
            return []
        plays = {"base": lambda walks: ev.score_walks(deck, player, walks).rewards}
        plays.update({k: play for k, (_, _, play) in enumerate(candidates)})
        cfg = self.advisor.config
        rewards, count, seconds = self.advisor.race(decision, plays, cfg.shop_seconds)
        rows = []
        for k, (o, kind, _) in enumerate(candidates):
            gain, se = paired_gain(rewards[k], rewards["base"])
            rows.append(Row(o, kind, gain, _z(gain, se)))
        self.advisor.log("shop (%d gold, %d walks through the route ahead, %.1fs of %.0fs): " % (gold, count, seconds, cfg.shop_seconds) +
                         ", ".join("%s %+.2f (z %.1f)" % (r.option.label, r.gain, r.z) for r in sorted(rows, key=lambda r: -r.z)) + "; needs z over %.1f" % (cfg.last_shop_z if last_shop(self.advisor.route_provider()) else cfg.shop_z))
        return rows
