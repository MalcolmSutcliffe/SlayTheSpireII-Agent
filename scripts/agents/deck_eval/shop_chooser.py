"""What to buy in a shop, one purchase per call (the shop screen comes back after each one, with the new gold and deck).

Everything is judged by the deck evaluator: each candidate is played on the same walks through the rest of the act (the engine's run simulator: the fights one after the other
with the HP carried over, the rest sites, rewards and relics: see route_sim and DeckEvaluator.score_walks) and compared with buying nothing, walk for walk. A candidate's
price is paid in its walks (the gold is gone from the shops ahead). Its Z-score is the mean gain over the standard error of the gain.
In order:
  1. a relic whose Z-score is over Z, the best Z-score first (relics are played by the engine's own pickup, route_sim.ShopRelicPlan); the shop's own relic (the 3rd one listed) is judged like the others
  2. potions, when the planned route meets an elite or the boss within the next 3 rooms: the best valued first (RewardParams.potion_bonus)
  3. a card or a card removal: the one with the best Z-score, if it is over Z. The card removed is chosen first: a curse, else a Strike, else a Defend; with none of those left no removal is considered.
  4. otherwise leave.
The analysis runs for at most SHOP_SECONDS: as many walks as fit, every candidate (relics, cards and the removal) on each.
"""
from __future__ import annotations
from typing import NamedTuple

from sts2_lite.card.constants import CARD_ENERGY_COST_AND_TARGET
from sts2_lite.card.ids import CardId
from sts2_lite.potion import PotionId

from agents.decision import Decision, Option
from agents.deck_eval.advisor import DeckAdvisor
from agents.deck_eval.card_reward_chooser import paired_gain
from agents.deck_eval.route_sim import ShopRelicPlan
from agents.sts2_MCTS.params import RewardParams

SHOP_SECONDS = 15.0         # the most time the deck analysis of one shop screen may take (relics, cards and the removal are all played)
Z = 1.5                     # the Z-score a purchase has to clear
POTION_LOOKAHEAD = 3        # rooms on the planned route: an elite or the boss within them is a reason to buy potions
DANGEROUS_ROOMS = ("elite", "boss")
SHOP_RELIC_POSITION = 2     # the 3rd relic listed, the shop's own: judged like the others here, but the walks' stand-in shopper (route_sim.WalkAgent) still never buys it
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


class Row(NamedTuple):
    option : Option
    kind : str          # "relic", "card" or "removal"
    gain : float
    z : float


def best(rows : list[Row]) -> Row:
    return max(rows, key=lambda r: (r.z, r.gain))


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

        rows = self._analyse(decision, relics, buys)
        worth = [r for r in rows if r.kind == "relic" and r.z > Z]
        if worth:
            return best(worth).option

        route = self.advisor.route_provider()
        if route is not None and any(kind in DANGEROUS_ROOMS for kind in route.kinds[1:1 + POTION_LOOKAHEAD]):
            potions = [o for o in buys if o.data.get("category") == "potion"]
            if potions:
                return max(potions, key=lambda o: (potion_value(o.data), -o.data.get("cost", 0)))

        worth = [r for r in rows if r.kind != "relic" and r.z > Z]
        return best(worth).option if worth else leave

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
        rewards, count, seconds = self.advisor.race(decision, plays, SHOP_SECONDS)
        rows = []
        for k, (o, kind, _) in enumerate(candidates):
            gain, se = paired_gain(rewards[k], rewards["base"])
            rows.append(Row(o, kind, gain, _z(gain, se)))
        self.advisor.log("shop (%d gold, %d walks through the route ahead, %.1fs of %.0fs): " % (gold, count, seconds, SHOP_SECONDS) +
                         ", ".join("%s %+.2f (z %.1f)" % (r.option.label, r.gain, r.z) for r in sorted(rows, key=lambda r: -r.z)) + "; needs z over %.1f" % Z)
        return rows
