from types import SimpleNamespace

from agents.decision import Decision, Option, SHOP
from agents.deck_eval.shop_chooser import ShopChooser, card_to_remove, removal_rank


def item(i, category, cost, **kw):
    return {"index": i, "category": category, "cost": cost, "is_stocked": True, "can_afford": True, **kw}


def chooser(kinds=()):
    adv = SimpleNamespace(route_provider=lambda: SimpleNamespace(kinds=list(kinds)), pool=[], log=lambda *_: None)
    return ShopChooser(adv)


def decide(items, kinds=()):
    opts = [Option(f"buy {i['index']}", {"action": "shop_purchase", "index": i["index"]}, i) for i in items]
    opts.append(Option("leave shop", {"action": "proceed"}))
    return chooser(kinds).choose(Decision(SHOP, {"items": items, "player": {"gold": 999, "deck": []}}, opts))


def test_never_the_third_relic_and_cheapest_first():
    items = [item(0, "relic", 250), item(1, "relic", 200), item(2, "relic", 100)]
    assert decide(items).data["index"] == 1          # the 100 gold relic is the shop's own: never bought
    assert decide(items[:2]).data["index"] == 1
    assert decide(items[:1]).data["index"] == 0


def test_card_cost_and_target_come_from_the_constants():
    c = chooser().card_dict(item(0, "card", 50, card_id="BASH", card_name="Bash", card_type="Attack", card_rarity="Basic"))
    assert (c["cost"], c["target_type"]) == (2, "AnyEnemy")
    assert chooser().card_dict(item(0, "card", 50, card_id="WHIRLWIND", card_name="W", card_type="Attack"))["cost"] == "X"


def test_relic_before_potion():
    items = [item(0, "potion", 50, potion_id="BLOOD_POTION"), item(1, "relic", 150)]
    assert decide(items, ["combat", "elite"]).data["index"] == 1


def test_potions_only_with_an_elite_within_three_rooms():
    items = [item(0, "potion", 50, potion_id="FIRE_POTION")]
    assert decide(items, ["x", "combat", "combat", "combat", "elite"]).name == "proceed"
    assert decide(items, ["x", "combat", "elite"]).name == "shop_purchase"


def test_removal_priority():
    deck = [{"id": "STRIKE_IRONCLAD"}, {"id": "DEFEND_IRONCLAD"}, {"id": "DOUBT", "type": "Curse"}, {"id": "BASH"}]
    assert card_to_remove(deck) == 2
    assert card_to_remove(deck[:2]) == 0
    assert card_to_remove(deck[1:2]) == 0
    assert card_to_remove([{"id": "BASH"}]) is None
    assert removal_rank({"id": "STRIKE_IRONCLAD", "removable": False}) is None
