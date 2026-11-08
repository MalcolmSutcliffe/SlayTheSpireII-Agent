"""Benchmark harness. Run from scripts/: python -m pytest benchmarks/Tests"""
import json
import math

import pytest

from sts2_lite import rng
from agents.sts2_MCTS.MCTS import SearchConfig, RolloutPolicy, sts2_MCTS
from benchmarks import bench

SMALL = "f2_r1_Nibbit_163629310124.json"


# ---------------------------------------------------------------- configs
def test_overrides_are_typed_like_the_config_fields():
    o = bench.parse_overrides(["exploration=1.5", "max_sims=500", "early_exit=false",
                               "rollout=FirstAction", "time_budget=none"])
    assert o == {"exploration": 1.5, "max_sims": 500, "early_exit": False,
                 "rollout": RolloutPolicy.FirstAction, "time_budget": None}

def test_unknown_override_is_rejected():
    with pytest.raises(SystemExit):
        bench.parse_overrides(["explortion=1.0"])

def test_config_survives_a_json_round_trip():
    c = SearchConfig(max_sims=123, exploration=0.7, rollout=RolloutPolicy.RandomAction)
    assert bench.config_from_dict(json.loads(json.dumps(bench.config_dict(c)))) == c

def test_named_config_with_overrides():
    c = bench.make_config("baseline", ["outcome_c=4"])
    assert c.outcome_c == 4.0 and c.max_sims == bench.CONFIGS["baseline"].max_sims


# ---------------------------------------------------------------- states
def test_index_and_smoke_subset():
    full, smoke = bench.load_index(), bench.load_index(smoke=True)
    assert len(full) == 36
    assert smoke and all(e["round"] == 1 for e in smoke) and len(smoke) < len(full)

def test_load_state_gives_independent_copies():
    a, b = bench.load_state(SMALL), bench.load_state(SMALL)
    a.player.current_hp -= 10
    assert b.player.current_hp == a.player.current_hp + 10


# ---------------------------------------------------------------- reference and decisions
def _run(pick, children):
    return {"pick": pick, "children": [{"key": k, "visits": n, "q": q} for k, n, q in children]}

def test_reference_merges_q_by_visits_and_flags_agreement():
    runs = [_run("a", [("a", 300, 0.5), ("b", 100, 0.4)]),
            _run("a", [("a", 100, 0.7), ("b", 300, 0.2)])]
    ref = bench.merge_reference("f", runs)
    assert ref["q"]["a"] == pytest.approx((300 * 0.5 + 100 * 0.7) / 400)
    assert ref["q"]["b"] == pytest.approx((100 * 0.4 + 300 * 0.2) / 400)
    assert ref["best"] in ("a", "b") and ref["visits"]["a"] == 400
    assert ref["stable"]
    assert not bench.merge_reference("f", runs[:1] + [_run("b", [("a", 1, 0.0), ("b", 5, 0.0)])])["stable"]

def test_regret_is_the_value_given_up():
    k_best, k_close, k_bad = (bench.action_key({"action": "play_card", "card_index": i}) for i in range(3))
    ref = {"q": {k_best: 0.80, k_close: 0.795, k_bad: 0.5}, "best": k_best, "stable": True}
    assert bench.score_decision(ref, {"action": "play_card", "card_index": 0}) == \
        {"regret": 0.0, "agree": True, "exact": True, "stable": True}
    close = bench.score_decision(ref, {"card_index": 1, "action": "play_card"})     # key order irrelevant
    assert close["agree"] and not close["exact"] and close["regret"] == pytest.approx(0.005)
    assert bench.score_decision(ref, {"action": "play_card", "card_index": 2})["regret"] == pytest.approx(0.3)

def test_search_is_reproducible_by_seed():
    state = bench.load_state(SMALL)
    a1, s1 = bench.run_search(state, SearchConfig(max_sims=200), seed=4)
    a2, s2 = bench.run_search(state, SearchConfig(max_sims=200), seed=4)
    assert a1 == a2 and [c["visits"] for c in s1["children"]] == [c["visits"] for c in s2["children"]]


# ---------------------------------------------------------------- fights
def _scripted_search(burn, record=None):
    """Replaces the search: records the hand at each decision, burns `burn` search-stream draws, plays the first action."""
    from sts2_lite.combat import CombatSimulator
    def search(self, state, config=None):
        if record is not None:
            record.append(tuple(sorted(c.card_id.value for c in state.player.hand)))
        for _ in range(burn):
            rng.random_float()
        action = CombatSimulator(state).get_available_actions()[0]
        return action, {"children": [], "num_sims": 1, "time_taken": 0.0, "exit_reason": "MAX_SIMS"}
    return search

def test_search_rng_use_does_not_change_the_world(monkeypatch):
    results = []
    for burn in (0, 7):
        monkeypatch.setattr(sts2_MCTS, "monte_carlo_tree_search", _scripted_search(burn))
        results.append(bench.play_fight(bench.load_state(SMALL), SearchConfig(), world_seed=3, search_seed=99))
    assert results[0] == results[1]

def test_world_seed_alone_sets_the_opening(monkeypatch):
    hands = {}
    for search_seed in (1, 2):
        seen = []
        monkeypatch.setattr(sts2_MCTS, "monte_carlo_tree_search", _scripted_search(0, seen))
        bench.play_fight(bench.load_state(SMALL), SearchConfig(), world_seed=5, search_seed=search_seed)
        hands[search_seed] = seen
    assert hands[1] == hands[2]

def test_different_world_seeds_give_different_fights(monkeypatch):
    seen_by_seed = []
    for world_seed in range(6):
        seen = []
        monkeypatch.setattr(sts2_MCTS, "monte_carlo_tree_search", _scripted_search(0, seen))
        bench.play_fight(bench.load_state(SMALL), SearchConfig(), world_seed=world_seed, search_seed=0)
        seen_by_seed.append(tuple(seen))
    assert len(set(seen_by_seed)) > 1

def test_real_fight_is_reproducible_and_scored():
    run = lambda: bench.play_fight(bench.load_state(SMALL), SearchConfig(max_sims=100), world_seed=1, search_seed=2)
    r1, r2 = run(), run()
    assert {k: v for k, v in r1.items() if k != "seconds"} == {k: v for k, v in r2.items() if k != "seconds"}
    assert r1["finished"] and r1["decisions"] > 0
    if r1["won"]:
        assert r1["score"] == r1["hp_lost"] >= 0
    else:
        assert r1["score"] > bench.load_state(SMALL).player.current_hp


# ---------------------------------------------------------------- comparison and io
def test_paired_diff_matches_on_file_and_seed():
    a = [{"file": "x", "seed": s, "score": 10} for s in range(5)]
    b = [{"file": "x", "seed": s, "score": 7} for s in range(5)] + [{"file": "y", "seed": 0, "score": 0}]
    d = bench.paired_diff(a, b, "score")
    assert d["n"] == 5 and d["mean"] == pytest.approx(-3) and d["ci95"] == 0.0 and d["significant"]

def test_noisy_equal_runs_are_within_noise():
    a = [{"file": "x", "seed": s, "score": s % 3} for s in range(30)]
    b = [{"file": "x", "seed": s, "score": (s + 1) % 3} for s in range(30)]
    assert not bench.paired_diff(a, b, "score")["significant"]

def test_results_files_round_trip_and_compare(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path)
    rows = lambda score: [{"file": "x", "seed": s, "won": True, "hp_lost": score, "score": score, "turns": 3,
                           "finished": True, "decisions": 4, "sims": 400, "seconds": 0.1} for s in range(4)]
    pa = bench.write_results("fights", "a", SearchConfig(), rows(10), {"seeds": 4})
    pb = bench.write_results("fights", "b", SearchConfig(exploration=1.0), rows(8), {"seeds": 4})
    header, back = bench.read_results(pa)
    assert header["suite"] == "fights" and header["config"]["exploration"] == SearchConfig().exploration
    assert back == rows(10)
    report = bench.compare_files(pa, pb)
    assert "Δscore (B-A) = -2.0000" in report

def test_cannot_compare_different_suites(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path)
    pa = bench.write_results("fights", "a", SearchConfig(), [], {})
    pb = bench.write_results("decisions", "b", SearchConfig(), [], {})
    with pytest.raises(SystemExit):
        bench.compare_files(pa, pb)
