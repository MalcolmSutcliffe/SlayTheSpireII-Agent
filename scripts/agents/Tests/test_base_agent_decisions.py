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

def test_card_select_confirms_once_it_can():
    assert BaseAgent().get_decision(decision("card_select", [act("select_card", index=0), act("confirm_selection")])).name == "confirm_selection"
    assert BaseAgent().get_decision(decision("card_select", [act("select_card", index=0)])).name == "select_card"

def test_works_in_a_subclass_that_skips_the_base_init():
    class Child(BaseAgent):
        def __init__(self): pass
    d = decision("card_reward", [act("select_card_reward", card_index=0)])
    assert Child().get_decision(d).name == "select_card_reward"

def test_rewards_claims_before_proceeding():
    d = decision("rewards", [act("claim_reward", index=0), act("proceed")])
    assert BaseAgent().get_decision(d).name == "claim_reward"
    assert BaseAgent().get_decision(decision("rewards", [act("proceed")])).name == "proceed"
