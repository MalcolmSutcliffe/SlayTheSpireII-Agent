"""Out-of-combat decisions: the Decision builders, the executors' commands, and RunManager routing a scripted run (no game, no CLI)."""
import json
import random

import pytest
from agent_runner import decision_builders, executors, run_manager
from agent_runner.game_client import GameClient
from agents.base_agent import BaseAgent
from agents.decision import Decision, Option


def state(decision, **fields):
    return {"type": "decision", "decision": decision, "context": {"act": 1, "floor": 3}, "player": {"hp": 50, "max_hp": 80, "open_potion_slots": 1}, **fields}

def names(options):
    return [o.action["action"] for o in options]

def build(s):
    return decision_builders.build_decision(s)


###
### Builders
###

def test_screens_the_agent_does_not_decide_on_have_no_decision():
    for s in ({"type": "status", "decision": "menu"}, {"type": "decision", "decision": "game_over"}, {"type": "decision", "decision": "combat_play"},
              {"type": "decision", "decision": "overlay"}):
        assert build(s) is None

def test_a_screen_with_nothing_to_click_has_no_options():
    assert build(state("map_select", choices=[])).options == []
    assert build(state("combat_rewards", items=[], can_proceed=False)).options == []

def test_map_options_are_the_next_nodes():
    d = build(state("map_select", choices=[{"index": 0, "type": "Monster", "col": 1, "row": 2}, {"index": 1, "type": "RestSite", "col": 3, "row": 2}]))
    assert d.kind == "map"
    assert [o.action for o in d.options] == [{"action": "choose_map_node", "index": 0}, {"action": "choose_map_node", "index": 1}]
    assert d.options[1].data["type"] == "RestSite"

def test_card_reward_offers_each_card_and_skip_when_allowed():
    s = state("card_reward", cards=[{"index": 0, "name": "Bash"}, {"index": 1, "name": "Anger"}], can_skip=True)
    assert [o.action for o in build(s).options] == [{"action": "select_card_reward", "card_index": 0}, {"action": "select_card_reward", "card_index": 1},
                                                    {"action": "skip_card_reward"}]
    assert names(build({**s, "can_skip": False}).options) == ["select_card_reward"] * 2

def test_rewards_hide_a_potion_with_no_free_slot_and_proceed_only_when_enabled():
    items = [{"index": 0, "type": "gold"}, {"index": 1, "type": "potion"}]
    full = build(state("combat_rewards", items=items, can_proceed=True, player={"open_potion_slots": 0}))
    assert [o.action.get("index") for o in full.options] == [0, None] and names(full.options) == ["claim_reward", "proceed"]
    roomy = build(state("combat_rewards", items=items, can_proceed=False))
    assert [o.action.get("index") for o in roomy.options] == [0, 1]

def test_rest_options_skip_disabled_ones():
    s = state("rest_site", options=[{"index": 0, "id": "HEAL", "is_enabled": True}, {"index": 1, "id": "SMITH", "is_enabled": False}], can_proceed=False)
    assert [o.data["id"] for o in build(s).options] == ["HEAL"]
    assert names(build({**s, "can_proceed": True}).options) == ["choose_rest_option", "proceed"]

def test_shop_offers_only_what_can_be_bought():
    items = [{"index": 0, "category": "card", "cost": 50, "is_stocked": True, "can_afford": True},
             {"index": 1, "category": "relic", "cost": 200, "is_stocked": True, "can_afford": False},
             {"index": 2, "category": "card", "cost": 60, "is_stocked": False, "can_afford": True},
             {"index": 3, "category": "potion", "cost": 40, "is_stocked": True, "can_afford": True}]
    d = build(state("shop", items=items, can_proceed=True, player={"open_potion_slots": 0}))
    assert [o.action for o in d.options] == [{"action": "shop_purchase", "index": 0}, {"action": "proceed"}]
    assert build(state("shop", items=items, can_proceed=False)).options[-1].action == {"action": "proceed"}      # the inventory covers the button after a purchase

def test_event_options_and_dialogue():
    s = state("event_choice", options=[{"index": 0, "title": "Pray", "is_locked": False}, {"index": 1, "title": "Locked", "is_locked": True}], in_dialogue=False)
    assert [o.action for o in build(s).options] == [{"action": "choose_event_option", "index": 0}]
    assert [o.action for o in build({**s, "in_dialogue": True}).options] == [{"action": "advance_dialogue"}]

def test_card_select_offers_cards_then_confirm_and_cancel():
    s = state("card_select", cards=[{"index": 0}, {"index": 1}], can_confirm=False, can_skip=False, can_cancel=False)
    assert names(build(s).options) == ["select_card", "select_card"]
    assert names(build({**s, "can_confirm": True, "can_cancel": True}).options) == ["select_card", "select_card", "confirm_selection", "cancel_selection"]
    assert names(build({**s, "can_skip": True}).options)[-1] == "cancel_selection"

def test_relic_and_treasure_options():
    r = build(state("relic_select", relics=[{"index": 0, "name": "A"}], can_skip=True))
    assert [o.action for o in r.options] == [{"action": "select_relic", "index": 0}, {"action": "skip_relic_selection"}]
    t = build(state("treasure", relics=[{"index": 0, "name": "A"}], can_proceed=True))
    assert [o.action for o in t.options] == [{"action": "claim_treasure_relic", "index": 0}, {"action": "proceed"}]


###
### Executors
###

@pytest.mark.parametrize("action, command", [
    ({"action": "choose_map_node", "index": 2}, ["choose-map", "2"]),
    ({"action": "choose_event_option", "index": 1}, ["event", "1"]),
    ({"action": "advance_dialogue"}, ["advance-dialogue"]),
    ({"action": "choose_rest_option", "index": 0}, ["rest", "0"]),
    ({"action": "shop_purchase", "index": 4}, ["shop-buy", "4"]),
    ({"action": "claim_reward", "index": 3}, ["claim-reward", "3"]),
    ({"action": "select_card_reward", "card_index": 1}, ["pick-card-reward", "1"]),
    ({"action": "skip_card_reward"}, ["skip-card-reward"]),
    ({"action": "proceed"}, ["proceed"]),
    ({"action": "select_card", "index": 5}, ["select-card", "5"]),
    ({"action": "confirm_selection"}, ["confirm-selection"]),
    ({"action": "cancel_selection"}, ["cancel-selection"]),
    ({"action": "select_relic", "index": 0}, ["select-relic", "0"]),
    ({"action": "skip_relic_selection"}, ["skip-relic-selection"]),
    ({"action": "claim_treasure_relic", "index": 1}, ["claim-treasure-relic", "1"]),
])
def test_every_action_has_its_command(action, command):
    assert executors.command_for(action) == command

def test_an_unknown_action_is_refused():
    with pytest.raises(ValueError):
        executors.command_for({"action": "teleport"})

def test_every_option_a_builder_makes_can_be_executed():
    s = [state("map_select", choices=[{"index": 0}]), state("card_reward", cards=[{"index": 0}], can_skip=True),
         state("combat_rewards", items=[{"index": 0, "type": "gold"}], can_proceed=True), state("rest_site", options=[{"index": 0}], can_proceed=True),
         state("shop", items=[{"index": 0, "can_afford": True}], can_proceed=True), state("event_choice", options=[{"index": 0}]),
         state("event_choice", in_dialogue=True), state("card_select", cards=[{"index": 0}], can_confirm=True, can_cancel=True),
         state("relic_select", relics=[{"index": 0}], can_skip=True), state("treasure", relics=[{"index": 0}], can_proceed=True)]
    for st in s:
        for option in build(st).options:
            executors.command_for(option.action)


###
### RunManager
###

class Scripted(GameClient):
    """The game as a list of screens. A command moves on to the next screen when `advance` allows it; every command is recorded."""
    def __init__(self, screens, advance=lambda command, index: True):
        super().__init__()
        self.screens, self.index, self.commands, self.advance = screens, 0, [], advance
    def get_state(self):
        return json.loads(json.dumps(self.screens[self.index]))
    def settled(self, game_state, cards_owed=None):
        return game_state
    def wait_for_change(self, before):
        return json.dumps(self.screens[self.index], sort_keys=True) != before
    def command(self, *args):
        self.commands.append(list(args))
        if self.advance(args, self.index) and self.index < len(self.screens) - 1:
            self.index += 1

@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(run_manager.time, "sleep", lambda s: None)

def manager(screens, agent=None, advance=lambda command, index: True):
    client = Scripted(screens, advance)
    return run_manager.RunManager(agent or BaseAgent(), verify=False, client=client), client

def test_a_scripted_run_through_every_screen():
    screens = [
        state("map_select", choices=[{"index": 0, "type": "Monster"}, {"index": 1, "type": "RestSite"}]),
        state("combat_rewards", items=[{"index": 0, "type": "gold", "description": "10 gold"}], can_proceed=True),
        state("combat_rewards", items=[], can_proceed=True),
        state("card_reward", cards=[{"index": 0, "name": "Bash"}], can_skip=False),
        state("rest_site", options=[{"index": 0, "id": "HEAL", "is_enabled": True}, {"index": 1, "id": "SMITH", "is_enabled": True}], can_proceed=False),
        state("card_select", cards=[{"index": 0}, {"index": 1}], can_confirm=False),
        state("card_select", cards=[{"index": 0}, {"index": 1}], can_confirm=True),
        state("shop", items=[{"index": 0, "category": "card", "cost": 50, "is_stocked": True, "can_afford": True}], can_proceed=True),
        state("event_choice", options=[{"index": 0, "title": "Go"}], in_dialogue=True),
        state("event_choice", options=[{"index": 0, "title": "Go"}], in_dialogue=False),
        state("relic_select", relics=[{"index": 0, "name": "R"}], can_skip=True),
        state("treasure", relics=[{"index": 0, "name": "T"}], can_proceed=False),
        state("treasure", relics=[], can_proceed=True),
        {"type": "decision", "decision": "game_over"},
    ]
    m, client = manager(screens)
    for _ in range(len(screens) - 1):
        m.tick()
    assert client.commands == [["choose-map", "0"], ["claim-reward", "0"], ["proceed"], ["pick-card-reward", "0"],
                               ["rest", "0"],                  # 50/80 HP is under 70%: heal
                               ["select-card", "0"], ["confirm-selection"], ["proceed"],
                               ["advance-dialogue"], ["event", "0"], ["select-relic", "0"], ["claim-treasure-relic", "0"], ["proceed"]]
    assert [h["kind"] for h in m.run_state.history][:3] == ["map", "rewards", "rewards"]
    assert m.run_state.act == 1 and m.run_state.floor == 3

def test_hurt_rests_and_healthy_upgrades():
    options = [{"index": 0, "id": "HEAL", "is_enabled": True}, {"index": 1, "id": "SMITH", "is_enabled": True}]
    hurt = state("rest_site", options=options, can_proceed=False, player={"hp": 20, "max_hp": 80})
    healthy = state("rest_site", options=options, can_proceed=False, player={"hp": 70, "max_hp": 80})
    m, client = manager([hurt, hurt]); m.tick()
    assert client.commands == [["rest", "0"]]
    m, client = manager([healthy, healthy]); m.tick()
    assert client.commands == [["rest", "1"]]

def test_card_reward_default_picks_at_random_and_skip_is_one_of_the_options():
    cards = [{"index": i, "name": f"C{i}"} for i in range(3)]
    picked = []
    for seed in range(400):
        agent = BaseAgent(); agent._rng = random.Random(seed)
        m, client = manager([state("card_reward", cards=cards, can_skip=True)] * 2, agent); m.tick()
        picked.append(tuple(client.commands[0]))
    assert set(picked) == {("pick-card-reward", "0"), ("pick-card-reward", "1"), ("pick-card-reward", "2"), ("skip-card-reward",)}
    assert 0.18 < picked.count(("skip-card-reward",)) / len(picked) < 0.32          # about 1 in 4

def test_not_a_decision_screen_only_waits(capsys):
    m, client = manager([{"type": "decision", "decision": "game_over"}] * 3)
    m.tick(); m.tick()
    assert client.commands == [] and capsys.readouterr().out.count("waiting for the next fight") == 1

def test_an_action_the_game_ignores_is_not_repeated():
    screen = state("map_select", choices=[{"index": 0, "type": "A"}, {"index": 1, "type": "B"}])
    m, client = manager([screen], advance=lambda command, index: False)
    m.tick(); m.tick(); m.tick()
    assert client.commands == [["choose-map", "0"], ["choose-map", "1"]]       # the second time the next option, then nothing left to try

def test_an_option_that_is_not_on_the_screen_is_replaced(capsys):
    class Cheater(BaseAgent):
        def get_decision(self, decision):
            return Option("teleport", {"action": "proceed"})
    m, client = manager([state("map_select", choices=[{"index": 2, "type": "A"}])] * 2, Cheater())
    m.tick()
    assert client.commands == [["choose-map", "2"]] and "not on the map screen" in capsys.readouterr().out

def test_the_agent_decides_what_is_sent():
    class AlwaysLast(BaseAgent):
        def get_decision(self, decision):
            return decision.options[-1]
    m, client = manager([state("map_select", choices=[{"index": 0}, {"index": 1}, {"index": 2}])] * 2, AlwaysLast())
    m.tick()
    assert client.commands == [["choose-map", "2"]]


###
### Skipped card rewards
###

class Skipper(BaseAgent):
    """Skips every card reward, otherwise the defaults."""
    def _get_card_reward_decision(self, decision):
        return decision.options_named("skip_card_reward")[0]

CARD = {"index": 0, "type": "card", "description": "Add a card to your deck"}
GOLD = {"index": 1, "type": "gold", "description": "10 gold"}

def test_a_skipped_card_reward_is_not_claimed_again():
    offer = state("card_reward", cards=[{"index": 0, "name": "Bash"}], can_skip=True)
    screens = [state("combat_rewards", items=[CARD], can_proceed=True), offer,
               state("combat_rewards", items=[CARD], can_proceed=True),        # the game keeps listing it
               state("map_select", choices=[{"index": 0}]), state("map_select", choices=[{"index": 0}])]
    m, client = manager(screens, Skipper())
    for _ in range(4):
        m.tick()
    assert client.commands == [["claim-reward", "0"], ["skip-card-reward"], ["proceed"], ["choose-map", "0"]]

def test_other_rewards_are_still_claimed_after_a_skip():
    offer = state("card_reward", cards=[{"index": 0, "name": "Bash"}], can_skip=True)
    screens = [state("combat_rewards", items=[CARD, GOLD], can_proceed=True), offer,
               state("combat_rewards", items=[CARD, GOLD], can_proceed=True), state("combat_rewards", items=[CARD], can_proceed=True),
               state("combat_rewards", items=[CARD], can_proceed=True)]
    m, client = manager(screens, Skipper())
    for _ in range(4):
        m.tick()
    assert client.commands == [["claim-reward", "0"], ["skip-card-reward"], ["claim-reward", "1"], ["proceed"]]

def test_only_the_skipped_one_of_two_card_rewards_is_left_out():
    offer = state("card_reward", cards=[{"index": 0, "name": "Bash"}], can_skip=True)
    two = [{**CARD, "index": 0}, {**CARD, "index": 1}]
    screens = [state("combat_rewards", items=two, can_proceed=True), offer, state("combat_rewards", items=two, can_proceed=True),
               state("combat_rewards", items=two, can_proceed=True)]
    m, client = manager(screens, Skipper())
    for _ in range(3):
        m.tick()
    assert client.commands == [["claim-reward", "0"], ["skip-card-reward"], ["claim-reward", "1"]]       # the other card reward is still new

def test_a_picked_card_declines_nothing():
    offer = state("card_reward", cards=[{"index": 0, "name": "Bash"}], can_skip=False)
    screens = [state("combat_rewards", items=[CARD], can_proceed=True), offer, state("combat_rewards", items=[CARD], can_proceed=True), offer]
    m, client = manager(screens, BaseAgent())
    for _ in range(3):
        m.tick()
    assert [c[0] for c in client.commands] == ["claim-reward", "pick-card-reward", "claim-reward"]       # a new reward screen, nothing declined

def test_declined_rewards_are_forgotten_on_the_next_screen():
    m, client = manager([state("map_select", choices=[{"index": 0}])] * 2)
    m.declined[("card", "Add a card to your deck")] += 1
    m.opened = CARD
    m.tick()
    assert not m.declined and m.opened is None

def test_declined_rewards_are_forgotten_when_a_fight_starts():
    import json as _json
    from agent_runner import combat_session
    m, client = manager([state("map_select", choices=[])])
    m.declined[("card", "x")] += 1
    m.opened = CARD
    m.combat.handle = lambda kind, game_state: None
    m.client.get_state = lambda: {"type": "decision", "decision": "hand_select", "cards": []}
    m.tick()
    assert not m.declined and m.opened is None

def test_the_builder_leaves_out_declined_items_only():
    from collections import Counter
    s = state("combat_rewards", items=[CARD, GOLD], can_proceed=True)
    assert names(decision_builders.build_decision(s, Counter({("card", "Add a card to your deck"): 1})).options) == ["claim_reward", "proceed"]
    assert names(decision_builders.build_decision(s).options) == ["claim_reward", "claim_reward", "proceed"]


def test_an_upgrade_screen_picks_the_rarest_card_through_the_manager():
    cards = [{"index": 0, "rarity": "Basic"}, {"index": 1, "rarity": "Rare"}, {"index": 2, "rarity": "Common"}, {"index": 3, "rarity": "Rare"}]
    screen = state("card_select", screen_type="upgrade", cards=cards, can_confirm=False)
    m, client = manager([screen] * 2)
    m.tick()
    assert client.commands == [["select-card", "3"]]
