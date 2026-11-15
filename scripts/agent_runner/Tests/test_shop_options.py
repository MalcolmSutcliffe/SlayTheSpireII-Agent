from agent_runner.decision_builders import shop_options


def test_leaving_is_offered_while_the_inventory_covers_the_button():
    state = {"can_proceed": False, "items": [{"index": 0, "category": "relic", "cost": 100, "is_stocked": True, "can_afford": False}]}
    assert [o.action["action"] for o in shop_options(state)] == ["proceed"]


def test_purchase_labels_name_the_item():
    state = {"items": [{"index": 0, "category": "relic", "relic_name": "Anchor", "cost": 90, "is_stocked": True, "can_afford": True}]}
    assert shop_options(state)[0].label == "buy Anchor (90g)"


def test_card_reward_alternatives_become_options_without_a_card_id():
    from agent_runner import decision_builders, executors
    state = {"cards": [{"index": 0, "id": "ANGER", "name": "Anger"}], "can_skip": True,
             "alternatives": [{"index": 0, "id": "SKIP", "name": "Skip"}, {"index": 1, "id": "REROLL", "name": "Reroll"}, {"index": 2, "id": "SACRIFICE", "name": "Sacrifice"}]}
    options = decision_builders.card_reward_options(state)
    alts = [o for o in options if o.action["action"] == "card_reward_alternative"]
    assert [o.action["option_id"] for o in alts] == ["REROLL", "SACRIFICE"] and all("id" not in o.data for o in alts)
    assert options[-1].action["action"] == "skip_card_reward"
    assert executors.command_for(alts[0].action) == ["card-reward-alternative", "REROLL"]
