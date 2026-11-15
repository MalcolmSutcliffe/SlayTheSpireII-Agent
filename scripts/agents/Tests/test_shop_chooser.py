"""What the shop chooser buys: relics whose Z-score clears Z, then (potions before an elite, then) the card or removal with the best Z-score over Z.
The analysis itself (`ShopChooser._analyse`) is replaced by canned rows in the decision tests; the last tests run it on the engine."""
from types import SimpleNamespace

import pytest

from agents.decision import Decision, Option, SHOP
from agents.deck_eval import shop_chooser
from agents.deck_eval.shop_chooser import Row, ShopChooser, card_to_remove, removal_rank


def item(i, category, cost, **kw):
    return {"index": i, "category": category, "cost": cost, "is_stocked": True, "can_afford": True, **kw}

def relic(i, cost, relic_id=None):
    return item(i, "relic", cost, relic_id=relic_id or "RELIC_%d" % i)

def screen(items, deck=()):
    opts = [Option(f"buy {i['index']}", {"action": "shop_purchase", "index": i["index"]}, i) for i in items]
    opts.append(Option("leave shop", {"action": "proceed"}))
    return Decision(SHOP, {"items": items, "player": {"gold": 999, "deck": list(deck)}}, opts)

class Canned(ShopChooser):
    """A chooser whose analysis gives `scores`: item index -> (gain, z). It remembers which relics it was asked about."""
    def __init__(self, scores, kinds=()):
        super().__init__(SimpleNamespace(route_provider=lambda: SimpleNamespace(kinds=list(kinds)), pool=[], log=lambda *_: None))
        self.scores, self.asked = scores, None

    def _analyse(self, decision, relics, buys):
        self.asked = [o.data["index"] for o in relics]
        kinds = {"relic": "relic", "card": "card", "card_removal": "removal"}
        rated = relics + [o for o in buys if o.data["category"] in ("card", "card_removal")]          # as the real analysis: relics only from `relics`
        return [Row(o, kinds[o.data["category"]], *self.scores[o.data["index"]]) for o in rated if o.data["index"] in self.scores]

def decide(items, scores, kinds=()):
    chooser = Canned(scores, kinds)
    return chooser.choose(screen(items)), chooser


def test_a_relic_over_the_z_score_is_bought_the_best_first():
    items = [relic(0, 250), relic(1, 200), relic(3, 100)]
    picked, _ = decide(items, {0: (0.9, 1.6), 1: (0.5, 2.4), 3: (0.3, 1.0)})
    assert picked.data["index"] == 1

def test_a_relic_under_the_z_score_is_not_bought():
    items = [relic(0, 250), relic(1, 200)]
    assert decide(items, {0: (0.9, 1.4), 1: (0.5, 1.5)})[0].name == "proceed"          # the score has to be over 1.5

def test_the_shops_own_third_relic_is_judged_like_the_others():
    items = [relic(0, 250), relic(1, 200), relic(2, 100)]
    picked, chooser = decide(items, {0: (0.1, 0.5), 1: (0.1, 0.5), 2: (0.9, 2.0)})
    assert chooser.asked == [0, 1, 2] and picked.data["index"] == 2
    assert decide(items, {0: (0.1, 0.5), 1: (0.1, 0.5), 2: (0.2, 1.0)})[0].name == "proceed"

def test_a_relic_without_an_id_cannot_be_played_and_is_left():
    items = [item(0, "relic", 100)]
    assert decide(items, {0: (9.0, 9.0)})[1].asked == []

def test_a_relic_comes_before_a_better_scoring_card():
    items = [relic(0, 150), item(1, "card", 60, card_id="BASH")]
    assert decide(items, {0: (0.4, 1.6), 1: (2.0, 5.0)})[0].data["index"] == 0

def test_the_card_or_removal_with_the_best_z_score_is_bought():
    items = [item(0, "card", 60, card_id="BASH"), item(1, "card", 50, card_id="ANGER"), item(2, "card_removal", 75)]
    assert decide(items, {0: (1.5, 2.0), 1: (0.6, 3.2), 2: (0.4, 2.5)})[0].data["index"] == 1
    assert decide(items, {0: (1.5, 2.0), 1: (0.6, 1.2), 2: (0.4, 2.5)})[0].data["index"] == 2

def test_a_card_under_the_z_score_is_not_bought():
    items = [item(0, "card", 60, card_id="BASH"), item(1, "card_removal", 75)]
    assert decide(items, {0: (1.5, 1.2), 1: (0.4, 1.5)})[0].name == "proceed"

def test_the_best_z_score_beats_the_biggest_gain():
    items = [item(0, "card", 60, card_id="BASH"), item(1, "card", 60, card_id="ANGER")]
    assert decide(items, {0: (3.0, 1.8), 1: (0.5, 4.0)})[0].data["index"] == 1

def test_a_sure_gain_scores_over_any_z():
    items = [item(0, "card", 60, card_id="BASH"), item(1, "card", 60, card_id="ANGER")]
    assert decide(items, {0: (0.5, 40.0), 1: (0.4, float("inf"))})[0].data["index"] == 1

def test_potions_come_after_the_relics_and_before_the_cards_when_an_elite_is_near():
    items = [item(0, "potion", 50, potion_id="FIRE_POTION"), item(1, "card", 60, card_id="BASH"), relic(2, 150)]
    kinds = ["x", "combat", "elite"]
    assert decide(items, {1: (2.0, 5.0)}, kinds)[0].data["index"] == 0
    assert decide(items, {1: (2.0, 5.0), 2: (0.5, 2.0)}, kinds)[0].data["index"] == 2
    assert decide(items, {1: (2.0, 5.0)}, ["x", "combat", "combat", "combat", "elite"])[0].data["index"] == 1

def test_potions_are_bought_when_the_boss_is_near_too():
    items = [item(0, "potion", 50, potion_id="FIRE_POTION")]
    assert decide(items, {}, ["x", "combat", "rest", "boss"])[0].data["index"] == 0
    assert decide(items, {}, ["x", "combat", "combat", "rest", "boss"])[0].name == "proceed"          # more than 3 rooms ahead
    assert decide(items, {}, ["boss"])[0].name == "proceed"          # the room the agent is in is not ahead

def test_nothing_to_buy_leaves():
    assert decide([item(0, "potion", 50, potion_id="FIRE_POTION")], {}, ["x", "combat", "combat", "combat", "elite"])[0].name == "proceed"


def test_card_cost_and_target_come_from_the_constants():
    adv = SimpleNamespace(route_provider=lambda: None, pool=[], log=lambda *_: None)
    c = ShopChooser(adv).card_dict(item(0, "card", 50, card_id="BASH", card_name="Bash", card_type="Attack", card_rarity="Basic"))
    assert (c["cost"], c["target_type"]) == (2, "AnyEnemy")
    assert ShopChooser(adv).card_dict(item(0, "card", 50, card_id="WHIRLWIND", card_name="W", card_type="Attack"))["cost"] == "X"

def test_removal_priority():
    deck = [{"id": "STRIKE_IRONCLAD"}, {"id": "DEFEND_IRONCLAD"}, {"id": "DOUBT", "type": "Curse"}, {"id": "BASH"}]
    assert card_to_remove(deck) == 2
    assert card_to_remove(deck[:2]) == 0
    assert card_to_remove(deck[1:2]) == 0
    assert card_to_remove([{"id": "BASH"}]) is None
    assert removal_rank({"id": "STRIKE_IRONCLAD", "removable": False}) is None


# ---------------------------------------------------------------- on the engine
from agents.Tests.test_deck_eval import POOL, _player, _walk_run, needs_pool
from agents.deck_eval.advisor import DeckAdvisor
from agents.deck_eval.evaluator import DeckEvaluator
from agents.deck_eval.fight_pool import target_types
from agents.deck_eval.route_sim import RouteSimulator, ShopRelicPlan, sample_walks
from agents.pathing import PlannedRoute


def _walk():
    return sample_walks(PlannedRoute(["combat", "rest", "combat", "boss"], 4, 1, None, "OVERGROWTH"), 1, 0, 1, 3)[0]

@needs_pool
def test_a_bought_relic_is_paid_for_and_picked_up_as_the_engine_does():
    ev, walk = DeckEvaluator(POOL, target_types(POOL)), _walk()
    run = _walk_run(walk, hp=70, max_hp=80)
    run.gold = 300
    sim = RouteSimulator(run, walk, ev.config, ShopRelicPlan("STRAWBERRY", 120))
    sim.reseed("shop")
    sim.buy_relic(sim.opening)
    assert run.gold == 180 and run.max_hp == 87 and run.has_relic("STRAWBERRY")          # Strawberry: +7 max HP

@needs_pool
def test_a_walk_with_a_bought_relic_pairs_with_the_walk_without_it():
    ev, walk = DeckEvaluator(POOL, target_types(POOL)), _walk()
    p = {**_player(), "gold": 300}
    plain = ev.score_walks(p["deck"], p, [walk]).rewards
    bought = ev.score_walks(p["deck"], p, [walk], ShopRelicPlan("STRAWBERRY", 120)).rewards
    again = ev.score_walks(p["deck"], p, [walk], ShopRelicPlan("STRAWBERRY", 120)).rewards
    assert bought == again and len(plain) == len(bought) == 1

@needs_pool
def test_the_analysis_rates_every_candidate_and_the_choice_is_one_of_the_options(monkeypatch):
    monkeypatch.setattr(shop_chooser, "SHOP_SECONDS", 0.2)
    logged = []
    advisor = DeckAdvisor(pool=POOL, log=logged.append, route_provider=lambda: PlannedRoute(["combat", "shop", "combat", "boss"], 4, 1, None, "OVERGROWTH"))
    p = {**_player(), "gold": 400}
    items = [relic(0, 150, "STRAWBERRY"), relic(1, 200, "ANCHOR"), relic(2, 100, "VAJRA"), item(3, "card", 60, card_id="BASH", card_name="Bash", card_type="Attack", card_rarity="Basic"),
             item(4, "card_removal", 75)]
    decision = Decision(SHOP, {"items": items, "player": p, "context": {"act": 1, "floor": 5}}, screen(items).options)
    rows = ShopChooser(advisor)._analyse(decision, [o for o in decision.options if o.data.get("category") == "relic" and o.data["index"] != 2], [o for o in decision.options if o.name == "shop_purchase"])
    assert sorted(r.option.data["index"] for r in rows) == [0, 1, 3, 4] and {r.kind for r in rows} == {"relic", "card", "removal"}
    assert logged and "needs z over" in logged[0]
    chosen = ShopChooser(advisor).choose(decision)
    assert chosen in decision.options
