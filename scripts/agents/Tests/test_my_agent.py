"""MyAgent follows the BaseAgent protocol: get_combat_action searches with MCTS, every other screen goes through get_decision."""
import json

from data_paths import RELICS
from agents.base_agent import BaseAgent
from agents.decision import Decision, Option
from agents.my_agent import MyAgent
from sts2_lite.combat import CombatState, CombatSimulator

def state():
    return CombatState.from_dict(json.loads((RELICS / "spiked_gauntlets.json").read_text()))

def test_my_agent_is_a_base_agent_with_the_combat_method():
    agent = MyAgent()
    assert isinstance(agent, BaseAgent) and not hasattr(agent, "get_action")
    assert callable(agent.get_combat_action) and callable(agent.get_decision)

def test_combat_goes_through_the_search():
    agent, cs = MyAgent(), state()
    assert len(CombatSimulator(cs).get_available_actions()) > 1
    calls = []
    sentinel = CombatSimulator(cs).get_available_actions()[-1]
    def search(combat_state, config):
        calls.append(config.time_budget)
        return sentinel, None
    agent._mcts.monte_carlo_tree_search = search
    assert agent.get_combat_action(cs, 0.25) is sentinel
    assert calls == [0.25]

def test_combat_returns_a_legal_action_from_a_real_search():
    cs = state()
    action = MyAgent().get_combat_action(cs, 0.2)
    assert action in CombatSimulator(cs).get_available_actions()

def test_a_single_legal_action_skips_the_search():
    agent, cs = MyAgent(), state()
    only = CombatSimulator(cs).get_available_actions()[0]
    class OneAction:
        def __init__(self, c): pass
        def get_available_actions(self): return [only]
    import agents.my_agent as module
    original, module.CombatSimulator = module.CombatSimulator, OneAction
    try:
        agent._mcts.monte_carlo_tree_search = lambda *a: (_ for _ in ()).throw(AssertionError("searched"))
        assert agent.get_combat_action(cs, 1) is only
    finally:
        module.CombatSimulator = original

def test_out_of_combat_screens_use_the_base_defaults():
    agent = MyAgent()
    d = Decision("shop", {}, [Option("buy", {"action": "shop_purchase", "index": 0}), Option("leave", {"action": "proceed"})])
    assert agent.get_decision(d).name == "proceed"

def test_the_base_agent_takes_a_time_budget_too():
    cs = state()
    assert BaseAgent().get_combat_action(cs, 3.0) in CombatSimulator(cs).get_available_actions()
