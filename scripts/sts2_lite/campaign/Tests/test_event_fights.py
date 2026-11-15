"""Events that start a fight: the fight is played by the simulator, its rewards come on top of the encounter's, and the Battleworn Dummy has a turn limit."""
import pytest

from agent_runner.decision_builders import build_decision
from sts2_lite.campaign.Tests.test_sandbox import RandomFighter, sim_of
from sts2_lite.event import EVENTS


def scripted(sim, keys):
    queue = list(keys)
    original = sim.ask

    def ask(state):
        if state.get("decision") == "event_choice" and queue:
            titles = [o["title"] for o in state["options"]]
            index = titles.index(queue.pop(0))
            return next(o for o in build_decision(state).options if o.action.get("index") == index)
        return original(state)
    sim.ask = ask
    return sim


def visit(sim, name, keys, monkeypatch):
    monkeypatch.setattr(sim, "next_event", lambda: (name, EVENTS[name]))
    sim.run_state.floor = 10
    scripted(sim, keys).event()
    return sim.run_state


def test_dense_vegetation_trudge_costs_eight_hp_for_gold(monkeypatch):
    sim = sim_of(RandomFighter(), 1)
    gold, hp = sim.run_state.gold, sim.run_state.hp
    r = visit(sim, "DENSE_VEGETATION", ["trudge_on"], monkeypatch)
    assert r.hp == hp - 8 and 61 <= r.gold - gold <= 99 and sim.fights == 0


def test_dense_vegetation_rest_heals_and_then_fights_four_wrigglers(monkeypatch):
    sim = sim_of(RandomFighter(), 2)
    sim.run_state.hp = 1000
    r = visit(sim, "DENSE_VEGETATION", ["rest", "fight"], monkeypatch)
    assert sim.fights == 1 and not r.dead


def test_punch_off_nab_gives_injury_and_a_relic(monkeypatch):
    sim = sim_of(RandomFighter(), 3)
    r = visit(sim, "PUNCH_OFF", ["nab"], monkeypatch)
    assert any(c["id"] == "INJURY" for c in r.deck) and len(r.relics) + r.pending_relics >= 1 and sim.fights == 0


def test_punch_off_fight_pays_a_relic_and_a_potion_on_top(monkeypatch):
    sim = sim_of(RandomFighter(), 4)
    seen = []
    original = sim.rewards
    sim.rewards = lambda enc, extra=(): (seen.append([e[0] for e in extra]), original(enc, extra))[1]
    visit(sim, "PUNCH_OFF", ["i_can_take_them", "fight"], monkeypatch)
    assert sim.fights == 1 and seen == [["relic", "potion"]]


def test_dummy_times_out_without_rewards(monkeypatch):
    sim = sim_of(RandomFighter(), 5)
    sim.rewards = lambda *a, **k: pytest.fail("a timed out dummy pays nothing")
    monkeypatch.setattr(sim, "fight", lambda *a, **k: False)
    visit(sim, "BATTLEWORN_DUMMY", ["setting_3"], monkeypatch)


def test_dummy_win_gives_what_the_setting_promises(monkeypatch):
    sim = sim_of(RandomFighter(), 6)
    monkeypatch.setattr(sim, "fight", lambda *a, **k: True)
    before = sum(bool(c.get("is_upgraded")) for c in sim.run_state.deck)
    r = visit(sim, "BATTLEWORN_DUMMY", ["setting_2"], monkeypatch)
    assert sum(bool(c.get("is_upgraded")) for c in r.deck) == before + 2
    sim = sim_of(RandomFighter(), 7)
    monkeypatch.setattr(sim, "fight", lambda *a, **k: True)
    r = visit(sim, "BATTLEWORN_DUMMY", ["setting_3"], monkeypatch)
    assert len(r.relics) + r.pending_relics >= 1


def test_the_dummy_fight_has_the_settings_hit_points_and_a_turn_limit(monkeypatch):
    from sts2_lite.campaign.combat import start_fight
    sim = sim_of(RandomFighter(), 8)
    for variant, hp in ((1, 75), (2, 150), (3, 300)):
        fight = start_fight(sim.run_state, "BATTLEWORN_DUMMY_EVENT_ENCOUNTER", "monster", sim.game, variant=variant)
        assert [e.current_hp for e in fight.combat_state.enemies] == [hp]
    from sts2_lite.campaign.combat import play_fight
    ran = play_fight(fight, sim.agent, sim.game, sim.search, None, turn_limit=3)
    assert fight.combat_state.turn_number <= 4 and fight.combat_state.enemies[0].current_hp > 0


def test_a_mad_science_card_keeps_its_rider_into_the_fight_and_improvement_upgrades_a_card_afterwards(monkeypatch):
    from sts2_lite.campaign.combat import start_fight
    from sts2_lite.event.run import mad_science_entry
    from sts2_lite.status import StatusId
    sim = sim_of(RandomFighter(), 9)
    sim.run_state.deck.append(mad_science_entry("Power", "IMPROVEMENT"))
    fight = start_fight(sim.run_state, "NIBBITS_WEAK", "monster", sim.game)
    cards = [c for pile in (fight.combat_state.player.hand, fight.combat_state.player.draw_pile) for c in pile if c.card_id.name == "MAD_SCIENCE"]
    assert [c.rider for c in cards] == ["IMPROVEMENT"] and cards[0].type.name == "Power"
    upgraded = sum(bool(c.get("is_upgraded")) for c in sim.run_state.deck)
    monkeypatch.setattr("sts2_lite.campaign.simulator.start_fight", lambda *a, **k: fight)
    monkeypatch.setattr("sts2_lite.campaign.simulator.play_fight", lambda sim_, *a, **k: sim_.combat_state.player.apply_status(StatusId.IMPROVEMENT, 1))
    for enemy in fight.combat_state.enemies:
        enemy.current_hp = 0
    sim.fight(__import__("sts2_lite.encounters", fromlist=["ENCOUNTERS"]).ENCOUNTERS["NIBBITS_WEAK"], "Monster")
    assert sum(bool(c.get("is_upgraded")) for c in sim.run_state.deck) == upgraded + 1


def test_events_walk_the_acts_shuffled_ring_skipping_the_not_allowed_and_the_met():
    sim = sim_of(RandomFighter(), 10)
    sim.start_act(0)
    pool = list(sim.run_state.hidden.events)
    assert set(pool) >= {"BRAIN_LEECH", "WAR_HISTORIAN_REPY"} and len(pool) == len(set(pool))
    met = []
    for _ in range(5):
        name, event = sim.next_event()
        met.append(name)
        sim.run_state.seen_events.append(name)
        assert event is None or (sim.run_state.act in event.acts and event.allowed(sim.run_state))
    assert len(set(met)) == 5
    for _ in range(3 * len(pool)):      # every event met: the ring repeats instead of failing
        name, _ = sim.next_event()
        sim.run_state.seen_events.append(name)
    assert name in pool
    first = sim_of(RandomFighter(), 10)
    first.start_act(0)
    name, _ = first.next_event()
    assert name == next(n for n in pool if n not in EVENTS or (1 in EVENTS[n].acts and EVENTS[n].allowed(first.run_state)))
    other = sim_of(RandomFighter(), 11)
    other.start_act(0)
    assert other.run_state.hidden.events != pool


def test_a_mad_science_card_keeps_its_rider_into_the_fight_and_improvement_upgrades_a_card_afterwards(monkeypatch):
    from sts2_lite.campaign.combat import start_fight
    from sts2_lite.event.run import mad_science_entry
    from sts2_lite.status import StatusId
    sim = sim_of(RandomFighter(), 9)
    sim.run_state.deck.append(mad_science_entry("Power", "IMPROVEMENT"))
    fight = start_fight(sim.run_state, "NIBBITS_WEAK", "monster", sim.game)
    cards = [c for pile in (fight.combat_state.player.hand, fight.combat_state.player.draw_pile) for c in pile if c.card_id.name == "MAD_SCIENCE"]
    assert [c.rider for c in cards] == ["IMPROVEMENT"] and cards[0].type.name == "Power"
    upgraded = sum(bool(c.get("is_upgraded")) for c in sim.run_state.deck)
    monkeypatch.setattr("sts2_lite.campaign.simulator.start_fight", lambda *a, **k: fight)
    monkeypatch.setattr("sts2_lite.campaign.simulator.play_fight", lambda sim_, *a, **k: sim_.combat_state.player.apply_status(StatusId.IMPROVEMENT, 1))
    for enemy in fight.combat_state.enemies:
        enemy.current_hp = 0
    sim.fight(__import__("sts2_lite.encounters", fromlist=["ENCOUNTERS"]).ENCOUNTERS["NIBBITS_WEAK"], "Monster")
    assert sum(bool(c.get("is_upgraded")) for c in sim.run_state.deck) == upgraded + 1


# --- quest cards in the campaign -----------------------------------------------------------------------------------------------------------------------
from sts2_lite.event.run import placeholder_entry
from sts2_lite.map.points import PointType


def test_the_lantern_key_fight_ends_with_the_key_in_the_deck(monkeypatch):
    sim = sim_of(RandomFighter(), 6)
    visit(sim, "THE_LANTERN_KEY", ["keep_the_key", "fight"], monkeypatch)
    assert sim.fights == 1 and any(c["id"] == "LANTERN_KEY" for c in sim.run_state.deck)


def test_with_the_lantern_key_act_3s_next_event_is_war_historian_repy_and_every_unknown_room_is_an_event():
    sim = sim_of(RandomFighter(), 7)
    sim.start_act(2)
    assert sim.next_event()[0] != "WAR_HISTORIAN_REPY"
    sim.run_state.deck.append(placeholder_entry("LANTERN_KEY", "Lantern Key", "Quest"))
    name, event = sim.next_event()
    assert name == "WAR_HISTORIAN_REPY" and event is EVENTS[name]
    rooms = []
    sim.event = lambda: rooms.append("Event")
    sim.fight_room = lambda *a, **k: rooms.append("Fight")
    point = next(p for col in sim.run_state.map.grid for p in col if p is not None and p.type == PointType.UNKNOWN)
    sim.enter(point)
    assert rooms == ["Event"]


def test_the_spoils_map_pays_600_gold_at_the_first_treasure_room_of_act_2():
    sim = sim_of(RandomFighter(), 8)
    sim.start_act(0)
    sim.run_state.deck.append(placeholder_entry("SPOILS_MAP", "Spoils Map", "Quest"))
    sim.start_act(1)
    spot = sim.run_state.hidden.spoils_point
    assert spot is not None and sim.run_state.map.grid[spot[0]][spot[1]].type == PointType.TREASURE
    gold = sim.run_state.gold
    sim.treasure = lambda: None
    sim.enter(sim.run_state.map.grid[spot[0]][spot[1]])
    assert sim.run_state.gold == gold + 600 and not any(c["id"] == "SPOILS_MAP" for c in sim.run_state.deck)


def test_no_spoils_map_no_quest_point():
    sim = sim_of(RandomFighter(), 9)
    sim.start_act(1)
    assert sim.run_state.hidden.spoils_point is None


def test_the_dummy_matches_its_capture_hit_points_and_time_limit():
    import json
    from pathlib import Path
    from sts2_lite.campaign.combat import start_fight
    from sts2_lite.combat import CombatState
    from sts2_lite.status import StatusId
    path = Path(__file__).resolve().parents[4] / "data" / "events" / "battle_worn_dummy.json"
    if not path.exists():
        pytest.skip("no capture")
    real = CombatState.from_dict(json.loads(path.read_text()))
    sim = sim_of(RandomFighter(), 9)
    mine = start_fight(sim.run_state, "BATTLEWORN_DUMMY_EVENT_ENCOUNTER", "monster", sim.game, variant=3).combat_state.enemies[0]
    theirs = real.enemies[0]
    assert (mine.enemy_id, mine.max_hp, mine.current_hp) == (theirs.enemy_id, theirs.max_hp, theirs.current_hp)
    assert mine.status[StatusId.BATTLEWORN_DUMMY_TIME_LIMIT].amount == theirs.status[StatusId.BATTLEWORN_DUMMY_TIME_LIMIT].amount == 3
