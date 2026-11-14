"""The agent_runner package (runner, combat session, game client, logs), driven by scripted game states instead of the bridge."""
import importlib
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest
from agent_runner import combat_logs, combat_session, game_client, run_manager
from data_paths import RELICS, VERIFIER


real_verify_opening = combat_session.verify_opening


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr(combat_session, "verify_opening", lambda game_state, log_path: True)      # the fights below are not real openings (see the opening tests)
    for name in ("agents.base_agent", "agents.my_agent"):       # the real agents are not under test (agents.verify is real)
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    sys.modules["agents.base_agent"].BaseAgent = object
    sys.modules["agents.my_agent"].MyAgent = object
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2]))
    sys.modules.pop("agent_runner.runner", None)        # only the runner takes the stubbed agents; the other modules are shared with this file
    runner = importlib.import_module("agent_runner.runner")
    monkeypatch.setattr(run_manager.time, "sleep", lambda s: None)
    yield runner
    sys.modules.pop("agent_runner.runner", None)

class FakeGame(game_client.GameClient):
    """get_state walks through `states`; each act() moves on to the next one. Past the end, or after
    `max_reads` reads of a state nobody acts on: Ctrl-C."""
    def __init__(self, states, max_reads=300):
        super().__init__()
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
    def get_combat_action(self, combat_state, budget=0):
        from sts2_lite.combat import CombatSimulator
        return CombatSimulator(combat_state).get_available_actions()[0]

def capture():
    return json.loads((RELICS / "spiked_gauntlets.json").read_text())

def fake_client(get_state=None, act=None):
    """A GameClient whose reading and/or sending is replaced by the given functions."""
    client = game_client.GameClient()
    if get_state is not None:
        client.get_state = get_state
    if act is not None:
        client.act = act
    return client

def run(runner, monkeypatch, states, tmp_path, game=None):
    game = game or FakeGame(states)
    log = tmp_path / "log.jsonl"
    runner.run_agent(FirstActionAgent(), log_path=str(log), client=game)
    return game, log


def test_kind_of_classifies_states(runner):
    play = capture()
    assert combat_session.kind_of(play) == "play"
    assert combat_session.kind_of({**play, "turn": "enemy"}) == "busy"
    assert combat_session.kind_of({**play, "is_play_phase": False}) == "busy"
    assert combat_session.kind_of({**play, "enemies": []}) == "busy"        # between a kill and the spawns it triggers
    assert combat_session.kind_of({**play, "enemies": [{"hp": 5}]}) == "play"
    torn_down = {**play, "player": {k: v for k, v in play["player"].items() if k != "max_hp"}}
    assert combat_session.kind_of(torn_down) == "busy"          # the fight is ending: the player's data is incomplete
    assert combat_session.kind_of({**play, "player": {}}) == "busy"
    assert combat_session.kind_of({k: v for k, v in play.items() if k != "player"}) == "busy"
    assert combat_session.kind_of({"type": "decision", "decision": "map_select"}) == "away"
    assert combat_session.kind_of({"type": "decision", "decision": "hand_select"}) == "pick"
    assert combat_session.kind_of({"type": "decision", "decision": "card_select", "screen_type": "NCombatPileCardSelectScreen"}) == "pick"
    assert combat_session.kind_of({"type": "decision", "decision": "card_select", "screen_type": "NDeckCardSelectScreen"}) == "away"

def test_a_difference_after_an_action_is_logged(runner, monkeypatch, tmp_path):
    before = capture()
    after = capture()
    after["player"]["hp"] -= 7             # the sim has no reason to predict this
    game, log = run(runner, monkeypatch, [before, after], tmp_path)
    assert len(game.acted) == 2            # the agent acted on both states
    entries = [json.loads(l) for l in log.read_text().splitlines()]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["actions"][0]["action"] == "play_card"
    assert any("player hp" in d for d in entry["differences"])
    assert entry["before"]["player"]["hp"] == 80 and entry["after"]["player"]["hp"] == 73
    assert entry["sim_after"]["player"]["hp"] == 80 and entry["game_after"]["player"]["hp"] == 73

def test_leaving_combat_while_the_sim_continues_is_logged(runner, monkeypatch, tmp_path):
    away = {"type": "decision", "decision": "card_reward"}
    game, log = run(runner, monkeypatch, [capture(), away, away], tmp_path)
    entries = [json.loads(l) for l in log.read_text().splitlines()]
    assert entries and "ended the combat" in entries[0]["differences"][0]

def test_nothing_is_acted_on_outside_combat(runner, monkeypatch, tmp_path):
    away = {"type": "decision", "decision": "map_select"}
    game, log = run(runner, monkeypatch, [away], tmp_path)
    assert game.acted == [] and not log.exists()

def test_the_enemy_turn_is_waited_out(runner, monkeypatch, tmp_path):
    busy = {**capture(), "turn": "enemy"}
    game, _ = run(runner, monkeypatch, [busy], tmp_path)
    assert game.acted == []


def test_right_after_end_turn_the_same_round_is_not_the_players_turn(runner):
    state = capture()
    ended = {"round": state["round"], "time": run_manager.time.time()}
    assert combat_session.turn_is_changing(state, ended)
    assert not combat_session.turn_is_changing({**state, "round": state["round"] + 1}, ended)
    new_round = {**state, "round": state["round"] + 1}
    assert combat_session.turn_is_changing({**new_round, "hand": [], "energy": 0}, ended)      # new round, nothing drawn yet
    assert not combat_session.turn_is_changing(state, None)
    assert not combat_session.turn_is_changing(state, {**ended, "time": ended["time"] - combat_session.TURN_CHANGE_TIMEOUT - 1})   # an extra turn

def test_affordable_cards_all_shown_unplayable_look_locked(runner):
    from sts2_lite.combat import CombatState
    cs = CombatState.from_dict(capture())
    assert not combat_session.cards_look_locked(cs)
    for card in cs.player.hand:
        card.is_unplayable = True
    assert combat_session.cards_look_locked(cs)
    cs.energy = 0
    assert not combat_session.cards_look_locked(cs) or any(c.energy_cost == 0 or c.energy_cost == "X" for c in cs.player.hand)

def test_the_agent_does_not_act_while_cards_are_locked(runner, monkeypatch, tmp_path):
    locked = capture()
    for card in locked["hand"] + locked["player"]["hand"]:
        card["can_play"] = False
    monkeypatch.setattr(combat_session, "LOCKED_READS", 1000)
    game, _ = run(runner, monkeypatch, [locked], tmp_path)
    assert game.acted == []

def test_locked_cards_that_never_unlock_are_acted_on_eventually(runner, monkeypatch, tmp_path):
    locked = capture()
    for card in locked["hand"] + locked["player"]["hand"]:
        card["can_play"] = False
    monkeypatch.setattr(combat_session, "LOCKED_READS", 3)
    game, _ = run(runner, monkeypatch, [locked], tmp_path)
    assert [a["action"] for a in game.acted] == ["end_turn"]


def test_settled_needs_several_identical_reads(runner, monkeypatch):
    first, second = capture(), capture()
    second["energy"] -= 1
    reads = iter([first, second, second, second, second])
    client = fake_client(get_state=lambda: next(reads))
    assert client.settled(first)["energy"] == second["energy"]         # the first state was still changing


def test_settled_after_havoc_waits_for_the_card_it_played_to_land(runner, monkeypatch):
    """Havoc's card sits in neither the hand nor a pile while the game pauses on it: identical reads are not enough."""
    whole = capture()
    owed = game_client.pile_total(whole)
    limbo = {**whole, "player": {**whole["player"], "discard_pile_count": whole["player"]["discard_pile_count"] - 1}}
    assert game_client.pile_total(limbo) == owed - 1
    monkeypatch.setattr(run_manager.time, "sleep", lambda s: None)
    reads = iter([limbo] * 6 + [whole] * 6)
    client = fake_client(get_state=lambda: next(reads))
    assert game_client.pile_total(client.settled(limbo, owed)) == owed


def test_a_fight_that_has_just_loaded_is_waited_on_until_the_hand_is_drawn(runner, monkeypatch):
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
    client = fake_client(get_state, lambda action, state=None, more=False: acted.append((len(reads), action)))
    monkeypatch.setattr(combat_session, "LOCKED_READS", 1000)
    runner.run_agent(FirstActionAgent(), log_path="/dev/null", client=client)
    assert acted and acted[0][0] >= 5          # nothing was done while the hand was empty and the energy 0
    assert acted[0][1]["action"] == "play_card"


class Commands:
    """Records the cli-anything-sts2 commands the runner would run."""
    def __init__(self):
        self.run = []
    def __call__(self, args, *a, **k):
        self.run.append(args[1:])
        return types.SimpleNamespace(stdout="{}", returncode=0)

def select_screen(cards):
    return {"type": "decision", "decision": "hand_select", "mode": "upgrade_select", "can_confirm": False,
            "cards": [{"index": i, "id": c[0], "is_upgraded": c[1]} for i, c in enumerate(cards)]}

def test_a_hand_pick_is_sent_as_the_index_on_the_select_screen(runner, monkeypatch):
    """The screen lists only the selectable cards: the Strike is hand card 3 but screen card 1."""
    commands = Commands()
    monkeypatch.setattr(subprocess, "run", commands)
    client = fake_client(get_state=lambda: select_screen([("DEFEND_IRONCLAD", False), ("STRIKE_IRONCLAD", False), ("DEFEND_IRONCLAD", False)]))
    screen = select_screen([("DEFEND_IRONCLAD", False), ("STRIKE_IRONCLAD", False), ("DEFEND_IRONCLAD", False)])
    action = {"action": "choose_card", "card_index": 3, "pile": "hand", "card_id": "STRIKE_IRONCLAD", "is_upgraded": False}
    client.act(action, screen)
    assert ["combat-select-card", "1"] in commands.run

def test_two_picks_of_identical_cards_on_a_pile_screen_use_different_indices(runner, monkeypatch):
    commands = Commands()
    monkeypatch.setattr(subprocess, "run", commands)
    client = fake_client(get_state=lambda: {"can_confirm": False})
    screen = select_screen([("DEFEND_IRONCLAD", False), ("DEFEND_IRONCLAD", False)])
    action = {"action": "choose_card", "card_index": 0, "pile": "discard", "card_id": "DEFEND_IRONCLAD", "is_upgraded": False}
    client.act(action, screen, picking_more=True)
    client.act(action, screen, picking_more=True)
    assert [c for c in commands.run if c[0] == "select-card"] == [["select-card", "0"], ["select-card", "1"]]

def test_the_hand_screen_renumbers_after_a_pick_so_identical_cards_reuse_the_index(runner, monkeypatch):
    commands = Commands()
    monkeypatch.setattr(subprocess, "run", commands)
    client = fake_client(get_state=lambda: {"can_confirm": False})
    screen = select_screen([("DEFEND_IRONCLAD", False), ("DEFEND_IRONCLAD", False)])
    action = {"action": "choose_card", "card_index": 0, "pile": "hand", "card_id": "DEFEND_IRONCLAD", "is_upgraded": False}
    client.act(action, screen, picking_more=True)
    client.act(action, screen, picking_more=True)
    assert [c for c in commands.run if c[0] == "combat-select-card"] == [["combat-select-card", "0"], ["combat-select-card", "0"]]

def test_a_pick_the_sim_already_made_is_clicked_for_it(runner, monkeypatch):
    """Two identical Defends: the sim upgrades one without asking, the game still shows the screen."""
    case = json.loads((VERIFIER / "log_cases" / "armaments_identical_defends.json").read_text())
    screen = json.loads((VERIFIER / "log_cases" / "armaments_select_screen.json").read_text())
    done = json.loads((VERIFIER / "log_cases" / "armaments_choose_defend.json").read_text())["after"]
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
    monkeypatch.setattr(subprocess, "run", commands)
    client = fake_client(get_state, fake_act)
    monkeypatch.setattr(combat_session, "input", lambda *a: "", raising=False)
    class Armaments:
        calls = 0
        def get_combat_action(self, cs, budget=0):
            Armaments.calls += 1
            if Armaments.calls > 1:
                raise KeyboardInterrupt         # the fight is over for this test
            return case["actions"][0]
    runner.run_agent(Armaments(), log_path="/dev/null", client=client)
    assert ["combat-select-card", "0"] in commands.run

def choose_screen():
    return {"type": "decision", "decision": "card_select", "screen_type": "choose", "can_confirm": False, "can_skip": True,
            "cards": [{"index": i, "id": c, "is_upgraded": False} for i, c in enumerate(["HEADBUTT", "STONE_ARMOR", "WHIRLWIND"])]}

def test_a_choose_screen_is_a_pick_and_is_skipped_with_cancel(runner, monkeypatch):
    """Discovery's offer: pick = select-card (no confirm on this screen), the sim's skip = cancel-selection."""
    commands = Commands()
    monkeypatch.setattr(subprocess, "run", commands)
    client = fake_client(get_state=choose_screen)
    assert combat_session.kind_of(choose_screen()) == "away"         # rewards and events use this screen too
    assert combat_session.kind_of(choose_screen(), expecting_choice=True) == "pick"
    client.act({"action": "choose_card", "card_index": 2, "pile": "offer", "card_id": "WHIRLWIND", "is_upgraded": False}, choose_screen())
    assert ["select-card", "2"] in commands.run and not any("confirm" in c[0] for c in commands.run)
    commands.run.clear()
    client.act({"action": "confirm_choice"}, choose_screen())
    assert commands.run == [["cancel-selection"]] or ["cancel-selection"] in [c[1:] if c[0] == "cli-anything-sts2" else c for c in commands.run]

def test_toolbox_screen_is_a_pick_without_skip_and_the_sim_has_no_state_for_it(runner):
    """Toolbox offers 3 colorless cards before the first hand is drawn (no skip): there is no combat state yet, so the
    runner can only recognise the screen and leave the pick to the player."""
    screen = json.loads((RELICS / "toolbox_select.json").read_text())
    assert combat_session.kind_of(screen, expecting_choice=True) == "pick" and not screen["can_skip"] and not screen["can_cancel"]
    assert [c["id"] for c in screen["cards"]] == ["BEAT_DOWN", "IMPATIENCE", "OMNISLICE"]


def run_capturing(runner, monkeypatch, states, tmp_path, directory):
    game = FakeGame(states)
    runner.run_agent(FirstActionAgent(), log_path=str(tmp_path / "log.jsonl"), capture_dir=str(directory), client=game)
    return game

def test_the_first_state_of_every_round_is_captured(runner, monkeypatch, tmp_path):
    first, next_round, same_round = capture(), capture(), capture()
    first["round"] = 4
    next_round["round"] = same_round["round"] = 5
    out = tmp_path / "bench"
    run_capturing(runner, monkeypatch, [first, next_round, same_round], tmp_path, out)
    files = sorted(p for p in out.glob("*.json"))
    assert len(files) == 2
    assert "_r4_" in files[0].name and "_r5_" in files[1].name
    assert json.loads(files[0].read_text()) == first
    lines = [json.loads(l) for l in (out / "index.jsonl").read_text().splitlines()]
    assert [l["round"] for l in lines] == [4, 5]
    assert {l["file"] for l in lines} == {p.name for p in files}
    assert lines[0]["hp"] == first["player"]["hp"] and lines[0]["enemies"]

def test_the_file_name_holds_the_floor_and_the_enemies(runner):
    state = capture()
    state["context"] = {"floor": 7}
    state["enemies"] = [{"name": "Phrog Parasite"}, {"name": "Wriggler"}, {"name": "Wriggler"}]
    assert combat_logs.capture_turn_start.__name__
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        name = combat_logs.capture_turn_start(state, d)
    assert name.startswith(f"f7_r{state['round']}_Phrog_Parasite+Wriggler_")

def test_nothing_is_captured_unless_asked_or_when_it_is_not_the_players_turn(runner, monkeypatch, tmp_path):
    enemy_turn = {**capture(), "turn": "enemy"}
    out = tmp_path / "bench"
    run_capturing(runner, monkeypatch, [enemy_turn], tmp_path, out)
    assert not out.exists()
    run(runner, monkeypatch, [capture()], tmp_path)
    assert not (tmp_path / "bench").exists()

def test_a_new_fight_captures_its_first_round_again(runner, monkeypatch, tmp_path):
    class LeavesCombat(FakeGame):
        def get_state(self):
            state = super().get_state()
            if state.get("decision") == "map_select":
                self.index += 1         # nobody acts outside combat: the game moves on by itself
            return state
    fight_one, away, fight_two = capture(), {"type": "decision", "decision": "map_select"}, capture()
    fight_one["round"] = fight_two["round"] = 1
    out = tmp_path / "bench"
    game = LeavesCombat([fight_one, away, away, away, fight_two])      # one away read goes to wait_for_change
    runner.run_agent(FirstActionAgent(), log_path=str(tmp_path / "log.jsonl"), capture_dir=str(out), client=game)
    assert len(list(out.glob("*.json"))) == 2


def test_describe_action_names_cards_targets_and_picks(runner):
    from sts2_lite.combat import CombatState
    state = CombatState.from_dict(capture())
    hand = state.player.hand
    assert combat_logs.describe_action({"action": "end_turn"}, state) == "end_turn"
    plain = combat_logs.describe_action({"action": "play_card", "card_index": 0, "target": 0}, state)
    assert plain == hand[0].card_id.name + ("+" if hand[0].is_upgraded else "")
    assert combat_logs.describe_action({"action": "play_card", "card_index": 0, "target": 0, "target_name": "E_0"}, state).endswith(" -> E_0")
    assert combat_logs.describe_action({"action": "choose_card", "card_id": "HEADBUTT", "is_upgraded": True, "pile": "discard"}, state) == "pick HEADBUTT+ (discard)"

def test_every_decision_is_logged_with_the_situation_and_the_move(runner, monkeypatch, tmp_path):
    game = FakeGame([capture(), capture()])
    path = tmp_path / "decisions.jsonl"
    runner.run_agent(FirstActionAgent(), log_path=str(tmp_path / "log.jsonl"), decision_log=str(path), client=game)
    lines = [json.loads(l) for l in path.read_text().splitlines()]
    assert lines and lines[0]["n"] == 1
    first = lines[0]
    assert first["hand"] and first["enemies"] and first["chosen"]
    assert first["hp"] == capture()["player"]["hp"] and first["energy"] == capture()["energy"]
    assert first["seconds"] >= 0
    assert first["sims"] is None and first["moves"] is None          # this agent runs no search

def test_nothing_is_logged_unless_asked(runner, monkeypatch, tmp_path):
    run(runner, monkeypatch, [capture()], tmp_path)
    assert not (tmp_path / "decisions.jsonl").exists()

def test_the_search_behind_a_decision_is_logged(runner, monkeypatch, tmp_path):
    """The agent's MCTS is wrapped to remember its searcher: sims, why it stopped and every root move's visits and mean."""
    class Child:
        def __init__(self, action, visits, total):
            self.action, self.visits, self.total_reward = action, visits, total
    class Root:
        children = [Child({"action": "end_turn"}, 10, -2.0), Child({"action": "play_card", "card_index": 0, "target": 0}, 90, 45.0)]
    class FakeMCTS:
        _root_node, _num_sims = None, 0
        def monte_carlo_tree_search(self, state, budget=0):
            self._root_node, self._num_sims = Root, 100
            return {"action": "play_card", "card_index": 0, "target": 0}
    module = types.ModuleType("agents.sts2_MCTS.MCTS")
    module.sts2_MCTS, module.SearchConfig = FakeMCTS, lambda: types.SimpleNamespace(max_sims=3000)
    monkeypatch.setitem(sys.modules, "agents.sts2_MCTS.MCTS", module)
    class SearchAgent:
        def get_combat_action(self, combat_state, budget=0):
            return FakeMCTS().monte_carlo_tree_search(combat_state, budget)
    game = FakeGame([capture(), capture()])
    path = tmp_path / "decisions.jsonl"
    runner.run_agent(SearchAgent(), log_path=str(tmp_path / "log.jsonl"), decision_log=str(path), client=game)
    first = json.loads(path.read_text().splitlines()[0])
    assert first["sims"] == 100 and first["stopped_by"] == "confidence"       # far below the time budget and the cap
    assert [m["visits"] for m in first["moves"]] == [10, 90]
    assert first["moves"][0]["move"] == "end_turn" and first["moves"][1]["mean"] == 0.5
    assert first["chosen"] == first["moves"][1]["move"]


def test_the_search_reported_stats_are_logged(runner, monkeypatch, tmp_path):
    """A search returning (action, stats) is logged from its stats: sims, exit reason and root moves."""
    play = {"action": "play_card", "card_index": 0, "target": 0}
    stats = {"children": [{"action": {"action": "end_turn"}, "visits": 30, "q": -0.25},
                          {"action": play, "visits": 170, "q": 0.61234}],
             "num_sims": 200, "time_taken": 0.4, "exit_reason": "STATISTICAL_CONFIDENCE"}
    class FakeMCTS:
        def monte_carlo_tree_search(self, state, config=None):
            return play, stats
    module = types.ModuleType("agents.sts2_MCTS.MCTS")
    module.sts2_MCTS, module.SearchConfig = FakeMCTS, lambda: types.SimpleNamespace(max_sims=3000)
    monkeypatch.setitem(sys.modules, "agents.sts2_MCTS.MCTS", module)
    class SearchAgent:
        def get_combat_action(self, combat_state, budget=0):
            action, _ = FakeMCTS().monte_carlo_tree_search(combat_state)
            return action
    game = FakeGame([capture(), capture()])
    path = tmp_path / "decisions.jsonl"
    runner.run_agent(SearchAgent(), log_path=str(tmp_path / "log.jsonl"), decision_log=str(path), client=game)
    first = json.loads(path.read_text().splitlines()[0])
    assert first["sims"] == 200 and first["stopped_by"] == "STATISTICAL_CONFIDENCE"
    assert [m["visits"] for m in first["moves"]] == [30, 170]
    assert first["moves"][1]["mean"] == 0.6123


# ------------------------------------------------------------ cards the sim does not implement
def _with_unknown(card_id="MADE_UP_CARD", pile="draw_pile"):
    state = capture()
    template = dict(state["hand"][0])
    template.update(id=card_id, name="Made Up")
    if pile == "hand":
        state["hand"] = state["hand"] + [template]
    else:
        state["player"][pile] = list(state["player"][pile]) + [template]
    return state

def test_unimplemented_cards_are_found_in_every_pile(runner):
    assert combat_logs.unimplemented_cards(capture()) == {}
    for pile in ("hand", "draw_pile", "discard_pile", "exhaust_pile"):
        assert combat_logs.unimplemented_cards(_with_unknown(pile=pile)) == {pile: ["MADE_UP_CARD"]}

def test_an_unimplemented_card_is_logged_once_per_run(runner, monkeypatch, tmp_path):
    _, log = run(runner, monkeypatch, [_with_unknown(), _with_unknown()], tmp_path)
    records = [json.loads(line) for line in log.read_text().splitlines()]
    unknown = [r for r in records if r.get("kind") == "not_implemented"]
    assert len(unknown) == 1
    assert unknown[0]["differences"] == ["card MADE_UP_CARD is not implemented in the sim (loaded as a Wound)"]
    assert unknown[0]["piles"] == {"draw_pile": ["MADE_UP_CARD"]}

def test_implemented_states_log_nothing_extra(runner, monkeypatch, tmp_path):
    _, log = run(runner, monkeypatch, [capture(), capture()], tmp_path)
    text = log.read_text() if log.exists() else ""
    assert "not_implemented" not in text


def test_the_state_behind_a_decision_can_be_saved_for_replay(runner, tmp_path):
    state = capture()
    combat_logs.save_decision_state(str(tmp_path / "states"), 7, state)
    saved = json.loads((tmp_path / "states" / "decision_00007.json").read_text())
    assert saved == state


# ---------------------------------------------------------------- fight summaries and tree size (--fight-log)
class _Node:
    def __init__(self, parent=None):
        self.parent, self.depth, self.children = parent, (parent.depth + 1 if parent else 0), []
        if parent and hasattr(parent, "children"):
            parent.children.append(self)

class _Chance:
    def __init__(self, parent):
        self.parent, self.depth, self.outcomes = parent, parent.depth + 1, {}
        parent.children.append(self)

def test_tree_stats_count_nodes_and_depth_through_chance_nodes(runner):
    root = _Node()
    a, b = _Node(root), _Node(root)
    chance = _Chance(a)
    chance.outcomes[("x",)] = _Node(chance)
    stats = combat_logs.tree_stats(root)
    assert stats == {"tree_nodes": 5, "tree_depth": 3, "tree_capped": False}

def test_a_fight_is_summarised_from_its_play_states(runner):
    state = capture()
    state["context"] = {"act": 1, "floor": 5, "ascension": 9}
    state["room_type"] = "monster"
    fight = combat_logs.fight_start(state)
    assert (fight["floor"], fight["ascension"], fight["start_hp"]) == (5, 9, state["player"]["hp"])
    later = json.loads(json.dumps(state))
    later["round"] = (state.get("round") or 1) + 1
    later["player"]["hp"] = state["player"]["hp"] - 12
    combat_logs.fight_update(fight, later, {"seconds": 1.5, "sims": 800, "stopped_by": "STATISTICAL_CONFIDENCE", "tree_depth": 7})
    combat_logs.fight_update(fight, later, {"seconds": 0.5, "sims": 200, "stopped_by": "time", "tree_depth": 4}, mismatched=True)
    away = {"type": "decision", "decision": "combat_rewards"}
    summary = combat_logs.fight_end(fight, away)
    assert summary["outcome"] == "won" and summary["hp_lost"] == 12 and summary["decisions"] == 2
    assert summary["sims"] == 1000 and summary["search_seconds"] == 2.0 and summary["max_tree_depth"] == 7
    assert summary["stopped_by"] == {"STATISTICAL_CONFIDENCE": 1, "time": 1} and summary["mismatches"] == 1
    assert not any(k.startswith("_") for k in summary)

def test_a_fight_that_ends_on_the_death_screen_is_a_loss(runner):
    fight = combat_logs.fight_start(capture())
    assert combat_logs.fight_end(fight, {"type": "decision", "decision": "game_over"})["outcome"] == "lost"
    assert combat_logs.fight_end(fight, {"player": {"hp": 0}})["outcome"] == "lost"

def test_potions_used_in_a_fight_are_counted(runner):
    state = capture()
    state["player"]["potions"] = [{"id": "A"}, {"id": "B"}]
    fight = combat_logs.fight_start(state)
    state["player"]["potions"] = [{"id": "A"}]
    combat_logs.fight_update(fight, state)
    assert fight["potions_used"] == 1

def test_the_fight_log_gets_one_line_per_fight_with_the_decision_totals(runner, monkeypatch, tmp_path):
    first, second = capture(), capture()
    second["player"]["hp"] -= 7
    away = {"type": "decision", "decision": "card_reward", "player": {"hp": second["player"]["hp"]}}
    game = FakeGame([first, second, away, away])
    fights = tmp_path / "fights.jsonl"
    runner.run_agent(FirstActionAgent(), log_path=str(tmp_path / "log.jsonl"), fight_log=str(fights), client=game)
    rows = [json.loads(l) for l in fights.read_text().splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["outcome"] == "won" and row["hp_lost"] == 7 and row["decisions"] == 2
    assert row["start_hp"] == 80 and row["end_hp"] == 73 and row["enemies"]


# ---------------------------------------------------------------- run folders: runs/<run>/
def test_a_run_keeps_everything_under_its_folder(runner, tmp_path):
    paths = runner.run_paths("run3-a9", decisions=True, fights=True, states=True, captures=True, runs_dir=tmp_path)
    folder = tmp_path / "run3-a9"
    assert folder.is_dir()
    assert paths == {"log_path": str(folder / "mismatches.jsonl"), "decision_log": str(folder / "decisions.jsonl"),
                     "fight_log": str(folder / "fights.jsonl"), "state_dir": str(folder / "states"),
                     "capture_dir": str(folder / "captures"), "first_decision": 0}

def test_only_the_aspects_asked_for_get_a_path(runner, tmp_path):
    paths = runner.run_paths("r", fights=True, runs_dir=tmp_path)
    assert paths["fight_log"] and not (paths["decision_log"] or paths["state_dir"] or paths["capture_dir"])
    assert paths["log_path"].endswith("mismatches.jsonl")

@pytest.mark.parametrize("name", ["", ".", "..", "a/b", "../x", "/abs"])
def test_a_run_name_is_a_folder_name_not_a_path(runner, tmp_path, name):
    with pytest.raises(ValueError):
        runner.run_paths(name, runs_dir=tmp_path)

def test_a_run_folder_with_data_is_not_reused_by_accident(runner, tmp_path):
    runner.run_paths("run3", runs_dir=tmp_path)             # empty folder: fine, also a second time
    runner.run_paths("run3", runs_dir=tmp_path)
    (tmp_path / "run3" / "decisions.jsonl").write_text("{}\n")
    with pytest.raises(FileExistsError):
        runner.run_paths("run3", decisions=True, runs_dir=tmp_path)

def test_appending_carries_the_decision_numbers_on(runner, tmp_path):
    folder = tmp_path / "run3"
    (folder / "states").mkdir(parents=True)
    for n in (1, 2, 7):
        (folder / "states" / f"decision_{n:05d}.json").write_text("{}")
    (folder / "decisions.jsonl").write_text("{}\n" * 3)
    assert runner.run_paths("run3", decisions=True, states=True, append=True, runs_dir=tmp_path)["first_decision"] == 7
    (folder / "decisions.jsonl").write_text("{}\n" * 9)
    assert runner.run_paths("run3", decisions=True, append=True, runs_dir=tmp_path)["first_decision"] == 9

def test_decisions_are_numbered_from_first_decision(runner, monkeypatch, tmp_path):
    game = FakeGame([capture()])
    runner.run_agent(FirstActionAgent(), log_path=str(tmp_path / "log.jsonl"), state_dir=str(tmp_path / "states"), first_decision=41, client=game)
    assert [p.name for p in (tmp_path / "states").iterdir()] == ["decision_00042.json"]

def run_main(runner, monkeypatch, tmp_path, argv):
    calls = []
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(runner, "MyAgent", lambda: "agent")
    monkeypatch.setattr(runner, "run_agent", lambda agent, **kw: calls.append((agent, kw)))
    runner.main(argv)
    return calls

def test_main_with_a_run_and_flags_saves_there(runner, monkeypatch, tmp_path):
    (agent, kw), = run_main(runner, monkeypatch, tmp_path, ["run3-a9", "--decisions", "--states"])
    assert kw["decision_log"] == str(tmp_path / "run3-a9" / "decisions.jsonl") and kw["state_dir"] == str(tmp_path / "run3-a9" / "states")
    assert kw["fight_log"] is None and kw["capture_dir"] is None and kw["verify"] is True

def test_main_all_saves_every_aspect(runner, monkeypatch, tmp_path):
    (_, kw), = run_main(runner, monkeypatch, tmp_path, ["r", "--all", "--no-verify", "--step"])
    assert all(kw[k] for k in ("decision_log", "fight_log", "state_dir", "capture_dir")) and kw["verify"] is False and kw["step"] is True

def test_main_with_no_run_saves_nothing_but_the_mismatch_log(runner, monkeypatch, tmp_path):
    (_, kw), = run_main(runner, monkeypatch, tmp_path, [])
    assert kw["log_path"] == runner.DEFAULT_LOG and set(kw) <= {"log_path", "step", "verify"}
    assert not list(tmp_path.iterdir())

@pytest.mark.parametrize("argv", [["--decisions"], ["--all"], ["--append"]])
def test_saving_needs_a_run_name(runner, monkeypatch, tmp_path, argv):
    with pytest.raises(SystemExit):
        run_main(runner, monkeypatch, tmp_path, argv)

def test_main_refuses_a_run_folder_that_has_data(runner, monkeypatch, tmp_path):
    (tmp_path / "old").mkdir()
    (tmp_path / "old" / "fights.jsonl").write_text("{}\n")
    with pytest.raises(SystemExit):
        run_main(runner, monkeypatch, tmp_path, ["old", "--fights"])


def test_potion_actions_are_described_and_sent(runner, monkeypatch):
    action = {"action": "use_potion", "slot": 1, "potion_id": "FIRE_POTION", "target": 0, "target_name": "LEAF_SLIME_M_0"}
    assert combat_logs.describe_action(action, None) == "drink FIRE_POTION -> LEAF_SLIME_M_0"
    assert combat_logs.describe_action({"action": "use_potion", "slot": 0, "potion_id": "BLOCK_POTION"}, None) == "drink BLOCK_POTION"
    sent = []
    monkeypatch.setattr(subprocess, "run", lambda command, *a, **k: sent.append(command))
    client = game_client.GameClient()
    client.act(action)
    client.act({"action": "use_potion", "slot": 0, "potion_id": "BLOCK_POTION"})
    assert sent == [["cli-anything-sts2", "use-potion", "1", "--target", "LEAF_SLIME_M_0"], ["cli-anything-sts2", "use-potion", "0"]]


# ---------------------------------------------------------------- the loop's less common branches
def test_a_card_already_picked_on_the_screen_is_confirmed_without_deciding(runner, monkeypatch, tmp_path):
    pick = {"type": "decision", "decision": "hand_select", "can_confirm": True, "cards": [{"index": 0, "id": "DEFEND_IRONCLAD", "is_upgraded": False}], "player": {}}
    confirmed = []
    game = FakeGame([pick])
    monkeypatch.setattr(game, "confirm_if_ready", lambda: confirmed.append(1))
    game, _ = run(runner, monkeypatch, None, tmp_path, game=game)
    assert confirmed and game.acted == []

def test_a_card_screen_that_cannot_be_read_is_left_to_the_player(runner, monkeypatch, tmp_path, capsys):
    screen = {"type": "decision", "decision": "card_select", "screen_type": "NCombatPileCardSelectScreen", "cards": [{"index": 0}]}
    game, _ = run(runner, monkeypatch, [screen], tmp_path)
    assert game.acted == [] and "cannot read this card selection" in capsys.readouterr().out

def test_an_action_the_game_ignores_is_logged_and_the_loop_goes_on(runner, monkeypatch, tmp_path, capsys):
    prompts = []
    game = FakeGame([capture(), capture()])
    monkeypatch.setattr(game, "wait_for_change", lambda before: False)
    monkeypatch.setattr(combat_session, "input", lambda *a: prompts.append(a[0]) or "", raising=False)
    game, log = run(runner, monkeypatch, None, tmp_path, game=game)
    assert prompts and "the game did not react" in capsys.readouterr().out
    entry = json.loads(log.read_text().splitlines()[0])
    assert "the game ignored" in entry["differences"][0]

def test_the_next_fight_starts_clean(runner, monkeypatch, tmp_path, capsys):
    away = {"type": "decision", "decision": "map_select"}
    game, _ = run(runner, monkeypatch, [capture(), away, capture()], tmp_path)
    assert len(game.acted) == 1 and "waiting for the next fight" in capsys.readouterr().out


def test_a_fights_first_state_is_checked_against_the_sims_opening(runner, monkeypatch, tmp_path):
    monkeypatch.setattr(combat_session, "verify_opening", real_verify_opening)
    bad = capture()
    bad["player"]["energy"] = bad["energy"] = bad["max_energy"] + 1       # the sim opens the fight with 3
    game, log = run(runner, monkeypatch, [bad], tmp_path)
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["actions"] == [{"action": "combat_start"}] and any("energy" in d for d in entry["differences"])

def test_the_opening_is_checked_once_per_fight(runner, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(combat_session, "verify_opening", lambda game_state, log_path: calls.append(1) or True)
    run(runner, monkeypatch, [capture(), capture()], tmp_path)
    assert len(calls) == 1         # the second state of a fight is not an opening

def test_a_check_that_cannot_run_does_not_stop_the_run(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(combat_session, "opening_diffs", lambda state: 1 / 0)
    assert real_verify_opening({}, str(tmp_path / "log.jsonl")) is True
    assert "could not be checked" in capsys.readouterr().out
