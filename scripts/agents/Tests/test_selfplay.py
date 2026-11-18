import gzip
import json

import pytest

from agents.selfplay import suite
from agents.selfplay.choosers import Counts, Explorer, RarityChooser, RandomChooser, base_id, card_key, make_chooser
import time

from agents.selfplay import run as run_module
from agents.selfplay.run import Pilot, parse_pilot, play_run, play_run_guarded
from agents.deck_eval.fight_pool import load_pool

needs_pool = pytest.mark.skipif(not load_pool(), reason="the engine has no encounters")


def card(card_id, rarity="Common", upgraded=False):
    return {"id": card_id, "rarity": rarity, "is_upgraded": upgraded}


def test_card_keys():
    assert card_key(card("BASH", upgraded=True)) == "BASH+"
    assert base_id("BASH+") == "BASH" and base_id("BASH") == "BASH"


def test_counts_count_each_card_once_per_act_and_round_trip():
    counts = Counts()
    counts.add_run([{"act": 1, "chosen": "BASH"}, {"act": 1, "chosen": "BASH+"}, {"act": 2, "chosen": "BASH"}, {"act": 1, "chosen": "SKIP"}])
    assert counts.n(1, "BASH") == 1 and counts.n(2, "BASH") == 1 and counts.n(1, "SKIP") == 0
    other = Counts.from_json(counts.to_json())
    other.merge(counts)
    assert other.n(1, "BASH") == 2


def test_a_card_that_was_tried_often_is_explored_less():
    snap = {"act": 1, "floor": 3}
    offered = [card("INFLAME", "Uncommon"), card("BASH", "Common")]
    chooser = RarityChooser(0)
    fresh = Explorer(chooser, Counts(), c=5.0, epsilon=0.0)
    index, record = fresh.pick(snap, offered)
    assert record["bonus"][0] == record["bonus"][1] == 5.0
    tried = Counts({(1, "INFLAME"): 99})
    index, record = Explorer(chooser, tried, c=5.0, epsilon=0.0).pick(snap, offered)
    assert record["bonus"][0] < record["bonus"][1] and record["bonus"][1] == 5.0


def test_the_bonus_makes_an_untried_card_win_and_the_pick_is_marked_exploratory():
    snap = {"act": 1, "floor": 3}
    offered = [card("RARE_ONE", "Rare"), card("NEVER_SEEN", "Common")]
    counts = Counts({(1, "RARE_ONE"): 1000})
    index, record = Explorer(RarityChooser(0), counts, c=10.0, epsilon=0.0).pick(snap, offered)
    assert record["chosen"] == "NEVER_SEEN" and record["exploratory"]
    index, record = Explorer(RarityChooser(0), Counts(), c=0.0, epsilon=0.0).pick(snap, offered)
    assert record["chosen"] == "RARE_ONE" and not record["exploratory"]


def test_skip_is_an_option_and_epsilon_can_pick_anything():
    snap = {"act": 1, "floor": 3}
    offered = [card("A"), card("B")]
    picks = {Explorer(RandomChooser(i), Counts(), c=0.0, epsilon=1.0, seed=i).pick(snap, offered)[1]["chosen"] for i in range(60)}
    assert picks == {"A", "B", "SKIP"}


def test_unknown_chooser():
    with pytest.raises(ValueError):
        make_chooser("nope")


@needs_pool
def test_a_run_is_repeatable_and_logs_its_rooms_and_picks():
    a, b = play_run(7, "rarity", epsilon=0.0), play_run(7, "rarity", epsilon=0.0)
    assert a == b
    out = a["outcome"]
    assert out["rooms_cleared"] <= len(a["rooms"]) and 0 <= out["act"] <= 3
    assert all({"act", "floor", "boss", "hp", "deck", "relics", "potions"} <= set(room) for room in a["rooms"])
    for pick in a["picks"]:
        assert pick["chosen"] == "SKIP" or pick["chosen"] in pick["offered"]
        assert len(pick["scores"]) == len(pick["offered"]) + 1
        room = a["rooms"][pick["room"] - 1]
        assert pick["after"]["reward"] and pick["after"]["room"] == room["room"] and pick["after"]["floor"] == room["floor"]
        if pick["chosen"] != "SKIP":
            assert pick["after"]["deck"][-1] == pick["chosen"]
            if pick["room"] < len(a["rooms"]):          # the next room's deck has the card the run picked
                assert a["rooms"][pick["room"]]["deck"].count(pick["chosen"]) >= pick["after"]["deck"].count(pick["chosen"])
    json.dumps(a)


@needs_pool
def test_the_suite_resumes_where_it_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr(suite, "OUT_ROOT", tmp_path)
    base = ["--out", "t", "--chooser", "random", "--workers", "1", "--batch", "2"]
    assert suite.main(base + ["--runs", "4"]) == 0
    assert suite.main(base + ["--runs", "6"]) == 0
    seeds = [run["seed"] for run in suite.read_runs(tmp_path / "t" / "runs.jsonl.gz")]
    assert sorted(seeds) == [1, 2, 3, 4, 5, 6]
    assert suite.main(["--out", "t", "--chooser", "rarity", "--runs", "1"]) == 1          # other settings: refused, nothing written


def test_ascension_mix():
    assert suite.parse_ascensions("10") == [10]
    assert suite.parse_ascensions("0-3") == [0, 1, 2, 3]
    assert suite.parse_ascensions("0,5,10,10") == [0, 5, 10, 10]
    assert {suite.ascension_of(s, [0, 5, 10]) for s in range(200)} == {0, 5, 10}
    assert suite.ascension_of(3, [0, 5, 10]) == suite.ascension_of(3, [0, 5, 10])


def test_pilots():
    assert parse_pilot("rollout") == Pilot() and parse_pilot("rollout").name == "rollout"
    big = parse_pilot("mcts:100:big")
    assert big.name == "mcts:100:big" and big.mcts_plays("Elite") and big.mcts_plays("Boss") and not big.mcts_plays("Monster")
    every = parse_pilot("mcts:50")
    assert every.mcts_plays("Monster") and every.search_config().max_sims == 50 and every.search_config().paired_scenarios == 0
    for bad in ("mcts", "mcts:0", "mcts:x", "mcts:10:small", "greedy"):
        with pytest.raises(ValueError):
            parse_pilot(bad)


@needs_pool
@pytest.mark.slow
def test_an_mcts_pilot_plays_the_elites_and_bosses_and_the_run_is_repeatable():
    a, b = play_run(4, "rarity", epsilon=0.0, pilot="mcts:10:big"), play_run(4, "rarity", epsilon=0.0, pilot="mcts:10:big")
    assert a == b and a["pilot"] == "mcts:10:big"
    rollout = play_run(4, "rarity", epsilon=0.0)
    assert rollout["pilot"] == "rollout" and rollout["outcome"]["mcts_decisions"] == 0
    assert a["outcome"]["mcts_decisions"] > 0 or not any(r["room"] in ("Elite", "Boss") for r in a["rooms"])


def test_a_stuck_run_is_given_up_and_logged_as_an_engine_error(monkeypatch):
    monkeypatch.setattr(run_module, "play_run", lambda seed, *a, **k: time.sleep(5))
    start = time.perf_counter()
    out = play_run_guarded(9, "rarity", None, 0.5, 0.05, 3, pilot="mcts:100:big", timeout=1)
    assert time.perf_counter() - start < 3
    assert out["seed"] == 9 and out["ascension"] == 3 and out["pilot"] == "mcts:100:big" and out["rooms"] == [] and out["picks"] == []
    assert out["outcome"]["cause"].startswith("engine error: timed out")
    monkeypatch.setattr(run_module, "play_run", lambda seed, *a, **k: {"seed": seed})
    assert play_run_guarded(4, timeout=1) == {"seed": 4}          # a run in time comes back as it is
