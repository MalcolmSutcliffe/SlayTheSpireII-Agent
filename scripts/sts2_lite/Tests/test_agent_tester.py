"""The agent_tester loop, driven by scripted game states instead of the bridge."""
import json
import sys
import types
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"

@pytest.fixture
def tester(monkeypatch):
    for name in ("agents", "agents.base_agent", "agents.my_agent"):       # the real agents are not under test
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    sys.modules["agents.base_agent"].BaseAgent = object
    sys.modules["agents.my_agent"].MyAgent = object
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2]))
    sys.modules.pop("agent_tester", None)
    import agent_tester
    monkeypatch.setattr(agent_tester.time, "sleep", lambda s: None)
    yield agent_tester
    sys.modules.pop("agent_tester", None)

class FakeGame:
    """get_state walks through `states`; each act() moves on to the next one. Past the end, or after
    `max_reads` reads of a state nobody acts on: Ctrl-C."""
    def __init__(self, states, max_reads=300):
        self.states, self.index, self.acted, self.reads, self.max_reads = states, 0, [], 0, max_reads
    def get_state(self):
        self.reads += 1
        if self.index >= len(self.states) or self.reads > self.max_reads:
            raise KeyboardInterrupt
        return json.loads(json.dumps(self.states[self.index]))
    def act(self, action, game_state=None, picking_more=False):
        self.acted.append(action)
        self.index += 1
        self.reads = 0

class FirstActionAgent:
    def get_action(self, combat_state, budget=0):
        from sts2_lite.combat import CombatSimulator
        return CombatSimulator(combat_state).get_available_actions()[0]

def capture():
    return json.loads((DATA / "relics" / "spiked_gauntlets.json").read_text())

def run(tester, monkeypatch, states, tmp_path):
    game = FakeGame(states)
    monkeypatch.setattr(tester, "get_state", game.get_state)
    monkeypatch.setattr(tester, "act", game.act)
    log = tmp_path / "log.jsonl"
    tester.run_agent(FirstActionAgent(), log_path=str(log))
    return game, log


def test_kind_of_classifies_states(tester):
    play = capture()
    assert tester.kind_of(play) == "play"
    assert tester.kind_of({**play, "turn": "enemy"}) == "busy"
    assert tester.kind_of({**play, "is_play_phase": False}) == "busy"
    assert tester.kind_of({**play, "enemies": []}) == "busy"        # between a kill and the spawns it triggers
    assert tester.kind_of({**play, "enemies": [{"hp": 5}]}) == "play"
    assert tester.kind_of({"type": "decision", "decision": "map_select"}) == "away"
    assert tester.kind_of({"type": "decision", "decision": "hand_select"}) == "pick"
    assert tester.kind_of({"type": "decision", "decision": "card_select", "screen_type": "NCombatPileCardSelectScreen"}) == "pick"
    assert tester.kind_of({"type": "decision", "decision": "card_select", "screen_type": "NDeckCardSelectScreen"}) == "away"

def test_a_difference_after_an_action_is_logged(tester, monkeypatch, tmp_path):
    before = capture()
    after = capture()
    after["player"]["hp"] -= 7             # the sim has no reason to predict this
    game, log = run(tester, monkeypatch, [before, after], tmp_path)
    assert len(game.acted) == 2            # the agent acted on both states
    entries = [json.loads(l) for l in log.read_text().splitlines()]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["actions"][0]["action"] == "play_card"
    assert any("player hp" in d for d in entry["differences"])
    assert entry["before"]["player"]["hp"] == 80 and entry["after"]["player"]["hp"] == 73
    assert entry["sim_after"]["player"]["hp"] == 80 and entry["game_after"]["player"]["hp"] == 73

def test_leaving_combat_while_the_sim_continues_is_logged(tester, monkeypatch, tmp_path):
    away = {"type": "decision", "decision": "card_reward"}
    game, log = run(tester, monkeypatch, [capture(), away, away], tmp_path)
    entries = [json.loads(l) for l in log.read_text().splitlines()]
    assert entries and "ended the combat" in entries[0]["differences"][0]

def test_nothing_is_acted_on_outside_combat(tester, monkeypatch, tmp_path):
    away = {"type": "decision", "decision": "map_select"}
    game, log = run(tester, monkeypatch, [away], tmp_path)
    assert game.acted == [] and not log.exists()

def test_the_enemy_turn_is_waited_out(tester, monkeypatch, tmp_path):
    busy = {**capture(), "turn": "enemy"}
    game, _ = run(tester, monkeypatch, [busy], tmp_path)
    assert game.acted == []


def test_right_after_end_turn_the_same_round_is_not_the_players_turn(tester):
    state = capture()
    ended = {"round": state["round"], "time": tester.time.time()}
    assert tester.turn_is_changing(state, ended)
    assert not tester.turn_is_changing({**state, "round": state["round"] + 1}, ended)
    new_round = {**state, "round": state["round"] + 1}
    assert tester.turn_is_changing({**new_round, "hand": [], "energy": 0}, ended)      # new round, nothing drawn yet
    assert not tester.turn_is_changing(state, None)
    assert not tester.turn_is_changing(state, {**ended, "time": ended["time"] - tester.TURN_CHANGE_TIMEOUT - 1})   # an extra turn

def test_affordable_cards_all_shown_unplayable_look_locked(tester):
    from sts2_lite.combat import CombatState
    cs = CombatState.from_dict(capture())
    assert not tester.cards_look_locked(cs)
    for card in cs.player.hand:
        card.is_unplayable = True
    assert tester.cards_look_locked(cs)
    cs.energy = 0
    assert not tester.cards_look_locked(cs) or any(c.energy_cost == 0 or c.energy_cost == "X" for c in cs.player.hand)

def test_the_agent_does_not_act_while_cards_are_locked(tester, monkeypatch, tmp_path):
    locked = capture()
    for card in locked["hand"] + locked["player"]["hand"]:
        card["can_play"] = False
    monkeypatch.setattr(tester, "LOCKED_READS", 1000)
    game, _ = run(tester, monkeypatch, [locked], tmp_path)
    assert game.acted == []

def test_locked_cards_that_never_unlock_are_acted_on_eventually(tester, monkeypatch, tmp_path):
    locked = capture()
    for card in locked["hand"] + locked["player"]["hand"]:
        card["can_play"] = False
    monkeypatch.setattr(tester, "LOCKED_READS", 3)
    game, _ = run(tester, monkeypatch, [locked], tmp_path)
    assert [a["action"] for a in game.acted] == ["end_turn"]


def test_settled_needs_several_identical_reads(tester, monkeypatch):
    first, second = capture(), capture()
    second["energy"] -= 1
    reads = iter([first, second, second, second, second])
    monkeypatch.setattr(tester, "get_state", lambda: next(reads))
    assert tester.settled(first)["energy"] == second["energy"]         # the first state was still changing


def test_a_fight_that_has_just_loaded_is_waited_on_until_the_hand_is_drawn(tester, monkeypatch):
    away = {"type": "decision", "decision": "map_select"}
    loading = {**capture(), "hand": [], "energy": 0}
    loading["player"] = {**loading["player"], "hand": [], "energy": 0}
    drawn = capture()
    reads, acted = [], []
    script = [away, loading, loading, loading, drawn]
    def get_state():
        reads.append(1)
        if len(reads) > 40:
            raise KeyboardInterrupt
        return json.loads(json.dumps(script[min(len(reads) - 1, len(script) - 1)]))
    monkeypatch.setattr(tester, "get_state", get_state)
    monkeypatch.setattr(tester, "act", lambda action, state=None, more=False: acted.append((len(reads), action)))
    monkeypatch.setattr(tester, "LOCKED_READS", 1000)
    tester.run_agent(FirstActionAgent(), log_path="/dev/null")
    assert acted and acted[0][0] >= 5          # nothing was done while the hand was empty and the energy 0
    assert acted[0][1]["action"] == "play_card"


class Commands:
    """Records the cli-anything-sts2 commands the tester would run."""
    def __init__(self):
        self.run = []
    def __call__(self, args, *a, **k):
        self.run.append(args[1:])
        return types.SimpleNamespace(stdout="{}", returncode=0)

def select_screen(cards):
    return {"type": "decision", "decision": "hand_select", "mode": "upgrade_select", "can_confirm": False,
            "cards": [{"index": i, "id": c[0], "is_upgraded": c[1]} for i, c in enumerate(cards)]}

def test_a_hand_pick_is_sent_as_the_index_on_the_select_screen(tester, monkeypatch):
    """The screen lists only the selectable cards: the Strike is hand card 3 but screen card 1."""
    commands = Commands()
    monkeypatch.setattr(tester.subprocess, "run", commands)
    monkeypatch.setattr(tester, "get_state", lambda: select_screen([("DEFEND_IRONCLAD", False), ("STRIKE_IRONCLAD", False), ("DEFEND_IRONCLAD", False)]))
    screen = select_screen([("DEFEND_IRONCLAD", False), ("STRIKE_IRONCLAD", False), ("DEFEND_IRONCLAD", False)])
    action = {"action": "choose_card", "card_index": 3, "pile": "hand", "card_id": "STRIKE_IRONCLAD", "is_upgraded": False}
    tester.act(action, screen)
    assert ["combat-select-card", "1"] in commands.run

def test_two_picks_of_identical_cards_use_different_screen_indices(tester, monkeypatch):
    commands = Commands()
    monkeypatch.setattr(tester.subprocess, "run", commands)
    monkeypatch.setattr(tester, "get_state", lambda: {"can_confirm": False})
    screen = select_screen([("DEFEND_IRONCLAD", False), ("DEFEND_IRONCLAD", False)])
    action = {"action": "choose_card", "card_index": 0, "pile": "hand", "card_id": "DEFEND_IRONCLAD", "is_upgraded": False}
    tester.picked_on_screen.clear()
    tester.act(action, screen, picking_more=True)
    tester.act(action, screen, picking_more=True)
    assert [c for c in commands.run if c[0] == "combat-select-card"] == [["combat-select-card", "0"], ["combat-select-card", "1"]]
    tester.picked_on_screen.clear()

def test_a_pick_the_sim_already_made_is_clicked_for_it(tester, monkeypatch):
    """Two identical Defends: the sim upgrades one without asking, the game still shows the screen."""
    case = json.loads((DATA / "log_cases" / "armaments_identical_defends.json").read_text())
    screen = json.loads((DATA / "log_cases" / "armaments_select_screen.json").read_text())
    done = json.loads((DATA / "log_cases" / "armaments_choose_defend.json").read_text())["after"]
    commands = Commands()
    states = [case["before"], screen, screen, done]
    reads = []
    def get_state():
        reads.append(1)
        if len(reads) > 120:
            raise KeyboardInterrupt
        position = 0 if not commands.run else (1 if not any(c[0] == "combat-select-card" for c in commands.run) else 3)
        return json.loads(json.dumps(states[position]))
    played = []
    def fake_act(action, game_state=None, picking_more=False):
        played.append(action)
        commands.run.append(("play",))
    monkeypatch.setattr(tester.subprocess, "run", commands)
    monkeypatch.setattr(tester, "get_state", get_state)
    monkeypatch.setattr(tester, "act", fake_act)
    monkeypatch.setattr(tester, "input", lambda *a: "", raising=False)
    class Armaments:
        calls = 0
        def get_action(self, cs, budget=0):
            Armaments.calls += 1
            if Armaments.calls > 1:
                raise KeyboardInterrupt         # the fight is over for this test
            return case["actions"][0]
    tester.run_agent(Armaments(), log_path="/dev/null")
    assert ["combat-select-card", "0"] in commands.run

def choose_screen():
    return {"type": "decision", "decision": "card_select", "screen_type": "choose", "can_confirm": False, "can_skip": True,
            "cards": [{"index": i, "id": c, "is_upgraded": False} for i, c in enumerate(["HEADBUTT", "STONE_ARMOR", "WHIRLWIND"])]}

def test_a_choose_screen_is_a_pick_and_is_skipped_with_cancel(tester, monkeypatch):
    """Discovery's offer: pick = select-card (no confirm on this screen), the sim's skip = cancel-selection."""
    commands = Commands()
    monkeypatch.setattr(tester.subprocess, "run", commands)
    monkeypatch.setattr(tester, "get_state", choose_screen)
    assert tester.kind_of(choose_screen()) == "away"         # rewards and events use this screen too
    assert tester.kind_of(choose_screen(), expecting_choice=True) == "pick"
    tester.act({"action": "choose_card", "card_index": 2, "pile": "offer", "card_id": "WHIRLWIND", "is_upgraded": False}, choose_screen())
    assert ["select-card", "2"] in commands.run and not any("confirm" in c[0] for c in commands.run)
    commands.run.clear()
    tester.act({"action": "confirm_choice"}, choose_screen())
    assert commands.run == [["cancel-selection"]] or ["cancel-selection"] in [c[1:] if c[0] == "cli-anything-sts2" else c for c in commands.run]

def test_toolbox_screen_is_a_pick_without_skip_and_the_sim_has_no_state_for_it(tester):
    """Toolbox offers 3 colorless cards before the first hand is drawn (no skip): there is no combat state yet, so the
    tester can only recognise the screen and leave the pick to the player."""
    screen = json.loads((DATA / "relics" / "toolbox_select.json").read_text())
    assert tester.kind_of(screen, expecting_choice=True) == "pick" and not screen["can_skip"] and not screen["can_cancel"]
    assert [c["id"] for c in screen["cards"]] == ["BEAT_DOWN", "IMPATIENCE", "OMNISLICE"]
