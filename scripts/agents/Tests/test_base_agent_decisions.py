"""The default out-of-combat handlers of BaseAgent: they only keep the run moving."""
import random

from agents.base_agent import BaseAgent
from agents.decision import Decision, Option, KINDS

def decision(kind, options, **player):
    return Decision(kind, {"player": player}, [Option(o["action"], o, o) for o in options])

def act(name, **fields):
    return {"action": name, **fields}

def test_every_kind_has_a_handler():
    agent = BaseAgent()
    for kind in KINDS:
        option = Option("x", act("proceed"))
        assert agent.get_decision(Decision(kind, {}, [option])) is option

def test_card_reward_is_random_over_the_cards_and_skip():
    options = [act("select_card_reward", card_index=0), act("select_card_reward", card_index=1), act("select_card_reward", card_index=2), act("skip_card_reward")]
    d = decision("card_reward", options)
    agent = BaseAgent()
    agent._rng = random.Random(1)
    picks = [agent.get_decision(d) for _ in range(2000)]
    assert all(p in d.options for p in picks)
    for option in d.options:
        assert 0.2 < picks.count(option) / len(picks) < 0.3         # each of the 4 about a quarter, Skip included

def test_card_reward_with_only_skip_skips():
    assert BaseAgent().get_decision(decision("card_reward", [act("skip_card_reward")])).name == "skip_card_reward"

def test_shop_leaves_without_buying():
    d = decision("shop", [act("shop_purchase", index=0), act("proceed")])
    assert BaseAgent().get_decision(d).name == "proceed"

def card(index, rarity, upgraded=False):
    return act("select_card", index=index, rarity=rarity, is_upgraded=upgraded)

def select(screen_type, cards, extra=()):
    d = decision("card_select", list(cards) + list(extra))
    d.state["screen_type"] = screen_type
    return d

def test_card_select_confirms_once_it_can_and_otherwise_picks_the_first_card():
    cards = [card(0, "Basic"), card(1, "Rare")]
    assert BaseAgent().get_decision(select("select", cards, [act("confirm_selection")])).name == "confirm_selection"
    assert BaseAgent().get_decision(select("select", cards)).action["index"] == 0            # a removal or transform: no preference yet

def test_upgrade_prefers_rarity_then_the_last_card():
    agent = BaseAgent()
    pick = lambda cards: agent.get_decision(select("upgrade", cards)).action["index"]
    assert pick([card(0, "Basic"), card(1, "Common"), card(2, "Uncommon"), card(3, "Rare"), card(4, "Basic")]) == 3
    assert pick([card(0, "Rare"), card(1, "Common"), card(2, "Uncommon")]) == 0
    assert pick([card(0, "Common"), card(1, "Uncommon"), card(2, "Common"), card(3, "Uncommon")]) == 3        # ties: the last
    assert pick([card(0, "Basic"), card(1, "Basic"), card(2, "Basic")]) == 2
    assert pick([card(0, "Curse"), card(1, "Basic")]) == 1                                                    # anything else ranks below Basic

def test_upgrade_skips_cards_that_are_already_upgraded_when_it_can():
    agent = BaseAgent()
    cards = [card(0, "Common"), card(1, "Rare", upgraded=True)]
    assert agent.get_decision(select("upgrade", cards)).action["index"] == 0
    assert agent.get_decision(select("upgrade", [card(0, "Rare", upgraded=True)])).action["index"] == 0

def test_works_in_a_subclass_that_skips_the_base_init():
    class Child(BaseAgent):
        def __init__(self): pass
    d = decision("card_reward", [act("select_card_reward", card_index=0)])
    assert Child().get_decision(d).name == "select_card_reward"

def test_rewards_claims_before_proceeding():
    d = decision("rewards", [act("claim_reward", index=0), act("proceed")])
    assert BaseAgent().get_decision(d).name == "claim_reward"
    assert BaseAgent().get_decision(decision("rewards", [act("proceed")])).name == "proceed"


def test_event_option_is_random_among_all():
    from agents.decision import Decision, Option, EVENT
    agent = BaseAgent()
    options = [Option(str(i), {"action": "choose_event_option", "index": i}) for i in range(4)]
    seen = {agent.get_decision(Decision(EVENT, {}, options)).label for _ in range(200)}
    assert seen == {"0", "1", "2", "3"}
