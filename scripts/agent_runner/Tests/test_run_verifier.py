"""The run verifier: it must stay quiet about a run the model itself plays, and catch each kind of difference a real run could show."""
import copy
import json

import pytest

from agent_runner.run_verifier import RunVerifier, replay, deck_counter
from agents.base_agent import BaseAgent
from sts2_lite.campaign import RunSimulator
from sts2_lite import rng
from sts2_lite.combat import CombatSimulator


class Prober(BaseAgent):
    """Plays random legal moves everywhere and tells a verifier about every screen and action, as the RunManager does with a real game."""

    def __init__(self, verifier : RunVerifier):
        super().__init__()
        self.verifier = verifier
        self.fighting = False

    def get_decision(self, decision):
        self.fighting = False
        option = rng.current().choice(decision.options)
        self.verifier.state(decision.state)
        self.verifier.acted(option.action)
        return option

    def get_combat_action(self, combat_state, time_budget=None):
        if not self.fighting:
            self.fighting = True
            self.verifier.interrupted()
        return rng.current().choice(CombatSimulator(combat_state).get_available_actions())


def probe(seed, ascension=0, hp=3000, gold=None, relics=()):
    verifier = RunVerifier(log_path=None, echo=False)
    sim = RunSimulator(Prober(verifier), seed=seed, ascension=ascension, search_seed=0, time_budget=None)
    sim.run_state.hp = sim.run_state.max_hp = hp
    if gold is not None:
        sim.run_state.gold = gold
    sim.run_state.relics += [{"id": r, "name": r} for r in relics]
    sim.run()
    return verifier


def errors_of(verifier):
    return [str(f) for f in verifier.errors]


@pytest.mark.parametrize("seed,ascension", [(1, 0), (2, 3), (3, 6), (4, 10)])
def test_the_model_agrees_with_itself(seed, ascension):
    verifier = probe(seed, ascension, gold=600)
    assert verifier.checked > 20
    assert errors_of(verifier) == []


def test_the_model_agrees_with_itself_with_relics_in_the_shop_and_at_rest():
    verifier = probe(5, 0, gold=900, relics=("MEMBERSHIP_CARD", "REGAL_PILLOW", "THE_COURIER"))
    assert errors_of(verifier) == []


# --- hand-made screens
PLAYER = {"hp": 50, "max_hp": 80, "gold": 100, "potion_slots": 3, "open_potion_slots": 3, "potions": [], "relics": [{"id": "BURNING_BLOOD"}],
          "deck": [{"id": "STRIKE_IRONCLAD", "type": "Attack", "is_upgraded": False, "can_upgrade": True},
                   {"id": "DEFEND_IRONCLAD", "type": "Skill", "is_upgraded": False, "can_upgrade": True}]}


def screen(decision, player=None, floor=3, **fields):
    return {"type": "decision", "decision": decision, "context": {"act": 1, "floor": floor, "ascension": 0}, "player": {**copy.deepcopy(PLAYER), **(player or {})}, **fields}


def rest(player=None, floor=3, proceed=False):
    return screen("rest_site", player, floor, can_proceed=proceed,
                  options=[{"index": 0, "id": "HEAL", "name": "Rest", "is_enabled": True}, {"index": 1, "id": "SMITH", "name": "Smith", "is_enabled": True}])


def verifier():
    return RunVerifier(log_path=None, echo=False)


def feed(v, *steps):
    for step in steps:
        if isinstance(step, dict) and "decision" in step:
            v.state(step)
        else:
            v.acted(step)
    return v


def test_rest_heals_thirty_percent():
    v = feed(verifier(), rest(), {"action": "choose_rest_option", "index": 0}, rest({"hp": 74}, proceed=True))
    assert errors_of(v) == []
    v = feed(verifier(), rest(), {"action": "choose_rest_option", "index": 0}, rest({"hp": 70}, proceed=True))
    assert [f.rule for f in v.errors] == ["episode.hp"]


def test_rest_heal_is_capped_at_max_hp():
    v = feed(verifier(), rest({"hp": 70}), {"action": "choose_rest_option", "index": 0}, rest({"hp": 80}, proceed=True))
    assert errors_of(v) == []


def test_smith_upgrades_exactly_the_chosen_card():
    deck = PLAYER["deck"]
    pick = screen("card_select", cards=[dict(c, index=i) for i, c in enumerate(deck)], selected=[], can_confirm=False, can_cancel=True)
    done = rest({"deck": [dict(deck[0], is_upgraded=True), deck[1]]}, proceed=True)
    v = feed(verifier(), rest(), {"action": "choose_rest_option", "index": 1}, pick, {"action": "select_card", "index": 0}, {"action": "confirm_selection"}, done)
    assert errors_of(v) == []
    wrong = rest({"deck": [deck[0], dict(deck[1], is_upgraded=True)]}, proceed=True)
    v = feed(verifier(), rest(), {"action": "choose_rest_option", "index": 1}, pick, {"action": "select_card", "index": 0}, {"action": "confirm_selection"}, wrong)
    assert [f.rule for f in v.errors] == ["episode.deck"]


def test_a_cancelled_smith_changes_nothing():
    deck = PLAYER["deck"]
    pick = screen("card_select", cards=[dict(c, index=i) for i, c in enumerate(deck)], selected=[], can_confirm=False, can_cancel=True)
    v = feed(verifier(), rest(), {"action": "choose_rest_option", "index": 1}, pick, {"action": "cancel_selection"}, rest())
    assert errors_of(v) == []


def test_anything_unaccounted_for_is_an_error():
    v = feed(verifier(), rest(), {"action": "proceed"}, screen("map_select", {"gold": 130}, 3, choices=[{"index": 0, "type": "Monster", "col": 1, "row": 4}]))
    assert [f.rule for f in v.errors] == ["episode.gold"]


def shop(player=None, items=None):
    items = items or [{"index": 0, "category": "card", "cost": 50, "is_stocked": True, "can_afford": True, "card_id": "BASH", "card_rarity": "Basic"}]
    return screen("shop", player, 5, items=items, can_proceed=True)


def test_a_purchase_costs_its_price_and_adds_the_card():
    bought = {"gold": 50, "deck": PLAYER["deck"] + [{"id": "BASH", "type": "Attack", "is_upgraded": False}]}
    v = feed(verifier(), shop(), {"action": "shop_purchase", "index": 0}, shop(bought))
    assert [f.rule for f in v.errors if f.rule.startswith("episode")] == []
    short = {"gold": 40, "deck": bought["deck"]}
    v = feed(verifier(), shop(), {"action": "shop_purchase", "index": 0}, shop(short))
    assert "episode.gold" in [f.rule for f in v.errors]


def test_a_shop_price_the_model_cannot_roll_is_an_error():
    items = [{"index": 0, "category": "card", "cost": 90, "is_stocked": True, "card_id": "BASH", "card_rarity": "Common"}]
    v = feed(verifier(), shop(items=items))
    assert "shop.price" in [f.rule for f in v.errors]


def test_the_shop_stock_has_the_shape_of_the_model():
    v = feed(verifier(), shop())
    assert "shop.stock" in [f.rule for f in v.errors]


def test_an_unmodelled_relic_is_a_warning_once():
    v = verifier()
    for _ in range(3):
        v.state(rest({"relics": [{"id": "NOT_A_RELIC_AT_ALL"}]}))
    assert [f.rule for f in v.findings].count("unknown.relic") == 1 and v.errors == []


def test_a_fight_in_between_ends_the_episode():
    v = feed(verifier(), rest(), {"action": "choose_rest_option", "index": 0})
    v.interrupted()
    v.state(rest({"hp": 1}, proceed=True))
    assert errors_of(v) == []


def test_a_repeated_screen_forgets_the_action_that_did_nothing():
    v = feed(verifier(), rest(), {"action": "choose_rest_option", "index": 0}, rest(), {"action": "choose_rest_option", "index": 0}, rest({"hp": 74}, proceed=True))
    assert errors_of(v) == []


def test_gold_reward_and_relic_pickup():
    rewards = screen("combat_rewards", items=[{"index": 0, "type": "gold", "description": "15 gold"}, {"index": 1, "type": "relic", "description": "Obtain Strawberry"}],
                     can_proceed=True)
    v = feed(verifier(), rewards, {"action": "claim_reward", "index": 0}, screen("combat_rewards", {"gold": 115}, items=rewards["items"][1:], can_proceed=True))
    assert errors_of(v) == []
    after = {"relics": PLAYER["relics"] + [{"id": "STRAWBERRY"}], "max_hp": 87, "hp": 57}
    v = feed(verifier(), rewards, {"action": "claim_reward", "index": 1}, screen("combat_rewards", after, items=rewards["items"][:1], can_proceed=True))
    assert errors_of(v) == []
    v = feed(verifier(), rewards, {"action": "claim_reward", "index": 1}, screen("combat_rewards", dict(after, max_hp=80, hp=50), items=rewards["items"][:1], can_proceed=True))
    assert "episode.max_hp" in [f.rule for f in v.errors]


def test_card_reward_pick_adds_that_card():
    rewards = screen("combat_rewards", items=[{"index": 0, "type": "card", "description": "Add a card to your deck"}], can_proceed=True)
    offer = screen("card_reward", cards=[{"index": 0, "id": "ANGER", "rarity": "Common", "is_upgraded": False}, {"index": 1, "id": "POMMEL_STRIKE", "rarity": "Common", "is_upgraded": False},
                                         {"index": 2, "id": "TWIN_STRIKE", "rarity": "Common", "is_upgraded": False}], can_skip=True)
    taken = {"deck": PLAYER["deck"] + [{"id": "POMMEL_STRIKE", "type": "Attack", "is_upgraded": False}]}
    v = feed(verifier(), rewards, {"action": "claim_reward", "index": 0}, offer, {"action": "select_card_reward", "card_index": 1},
             screen("combat_rewards", taken, items=[], can_proceed=True))
    assert errors_of(v) == []
    wrong = {"deck": PLAYER["deck"] + [{"id": "ANGER", "type": "Attack", "is_upgraded": False}]}
    v = feed(verifier(), rewards, {"action": "claim_reward", "index": 0}, offer, {"action": "select_card_reward", "card_index": 1},
             screen("combat_rewards", wrong, items=[], can_proceed=True))
    assert [f.rule for f in v.errors] == ["episode.deck"]


def test_recording_and_replay(tmp_path):
    path = tmp_path / "run.jsonl"
    v = RunVerifier(log_path=None, record_path=str(path), echo=False)
    feed(v, rest(), {"action": "choose_rest_option", "index": 0}, rest({"hp": 70}, proceed=True))
    assert [f.rule for f in v.errors] == ["episode.hp"]
    again = replay(str(path))
    assert [f.rule for f in again.errors] == ["episode.hp"]
    assert len(path.read_text().splitlines()) == 3


def test_findings_are_logged(tmp_path):
    log = tmp_path / "findings.jsonl"
    v = RunVerifier(log_path=str(log), echo=False)
    feed(v, rest(), {"action": "choose_rest_option", "index": 0}, rest({"hp": 70}, proceed=True))
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    assert lines[0]["rule"] == "episode.hp" and lines[0]["expected"] == 74 and lines[0]["actual"] == 70


# --- the RunManager hands the verifier what it sees
class Screens:
    """A game that shows screens one after the other, moving on whenever a command arrives."""
    def __init__(self, screens):
        from agent_runner.game_client import GameClient
        self.screens, self.index, self.commands = screens, 0, []
        outer = self

        class Client(GameClient):
            def get_state(self):
                return json.loads(json.dumps(outer.screens[outer.index]))

            def settled(self, game_state, cards_owed=None):
                return game_state

            def wait_for_change(self, before):
                return True

            def command(self, *args):
                outer.commands.append(list(args))
                outer.index = min(outer.index + 1, len(outer.screens) - 1)
        self.client = Client()


def test_the_run_manager_feeds_the_verifier(tmp_path, monkeypatch):
    from agent_runner import run_manager
    monkeypatch.setattr(run_manager.time, "sleep", lambda s: None)
    game = Screens([rest(), rest({"hp": 70}, proceed=True), rest({"hp": 70}, proceed=True)])
    log = tmp_path / "mismatches.jsonl"
    manager = run_manager.RunManager(BaseAgent(), verify=True, log_path=str(log), client=game.client)
    manager.tick()
    manager.tick()
    findings = [json.loads(line) for line in (tmp_path / "run_mismatches.jsonl").read_text().splitlines()]
    assert [f["rule"] for f in findings] == ["episode.hp"]
    assert (tmp_path / "run_states.jsonl").exists()


def test_the_verifier_is_off_without_a_log_and_never_stops_the_run(tmp_path, monkeypatch, capsys):
    from agent_runner import run_manager
    monkeypatch.setattr(run_manager.time, "sleep", lambda s: None)
    assert run_manager.RunManager.default_verifier("/dev/null") is None
    game = Screens([rest(), rest({"hp": 70}, proceed=True)])
    manager = run_manager.RunManager(BaseAgent(), verify=True, log_path=str(tmp_path / "m.jsonl"), client=game.client)

    def broken(state):
        raise RuntimeError("boom")
    manager.run_verifier.state = broken
    manager.tick()
    assert manager.run_verifier is None and game.commands
    assert "switched off" in capsys.readouterr().out


def test_a_screen_without_deck_and_relics_borrows_them_and_does_not_compare_them():
    bare = lambda gold, items=None: {**shop(items=items), "player": {"hp": 50, "max_hp": 80, "gold": gold, "potion_slots": 3, "open_potion_slots": 3, "potions": []}}
    items = [{"index": 0, "category": "card", "cost": 50, "is_stocked": True, "can_afford": True, "card_id": "BASH", "card_rarity": "Basic"}]
    v = verifier()
    v.state(rest())                                         # shows the deck and relics
    v.acted({"action": "proceed"})
    v.state(bare(100, items))                               # the shop does not
    v.acted({"action": "shop_purchase", "index": 0})
    v.state(bare(50, items))
    assert [f.rule for f in v.errors if f.rule.startswith("episode")] == []
    v.acted({"action": "shop_purchase", "index": 0})
    v.state(bare(5, items))                                 # gold is still compared: 50 - 50 = 0
    assert [f.rule for f in v.errors if f.rule.startswith("episode")] == ["episode.gold"]
