from agent_runner.decision_builders import shop_options


def test_leaving_is_offered_while_the_inventory_covers_the_button():
    state = {"can_proceed": False, "items": [{"index": 0, "category": "relic", "cost": 100, "is_stocked": True, "can_afford": False}]}
    assert [o.action["action"] for o in shop_options(state)] == ["proceed"]


def test_purchase_labels_name_the_item():
    state = {"items": [{"index": 0, "category": "relic", "relic_name": "Anchor", "cost": 90, "is_stocked": True, "can_afford": True}]}
    assert shop_options(state)[0].label == "buy Anchor (90g)"
