"""Benchmark harness. Run from scripts/: python -m pytest benchmarks/Tests"""
import json
import math

import pytest

from sts2_lite import rng
from agents.sts2_MCTS.MCTS import sts2_MCTS
from agents.sts2_MCTS.params import SearchConfig, RolloutPolicy
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

def test_overrides_reach_the_parameters_inside_the_groups():
    c = bench.make_config("baseline", ["p_random_action=0", "win_base=10", "exploration_scale=60", "epsilon=0.01", "focus=first"])
    assert (c.heuristic.p_random_action, c.reward.win_base, c.uct.exploration_scale, c.confidence.epsilon, c.heuristic.focus) == (0.0, 10.0, 60.0, 0.01, "first")

def test_a_table_cannot_be_set_from_the_command_line():
    with pytest.raises(SystemExit):
        bench.parse_overrides(["rarity_weights=1"])

def test_config_survives_a_json_round_trip():
    c = SearchConfig(max_sims=123, exploration=0.7, rollout=RolloutPolicy.RandomAction)
    assert bench.config_from_dict(json.loads(json.dumps(bench.config_dict(c)))) == c

def test_named_config_with_overrides():
    c = bench.make_config("baseline", ["outcome_c=4"])
    assert c.outcome_c == 4.0 and c.max_sims == bench.CONFIGS["baseline"].max_sims


# ---------------------------------------------------------------- states
def test_index_and_smoke_subset():
    full, smoke = bench.load_index(suite="act1"), bench.load_index(smoke=True, suite="act1")
    assert len(full) >= 36 and len({e["file"] for e in full}) == len(full)      # no duplicate entries after merging runs
    assert smoke and all(e["round"] == 1 for e in smoke) and len(smoke) < len(full)

def test_load_state_gives_independent_copies():
    a, b = bench.load_state(SMALL, "act1"), bench.load_state(SMALL, "act1")
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
    state = bench.load_state(SMALL, "act1")
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
        results.append(bench.play_fight(bench.load_state(SMALL, "act1"), SearchConfig(), world_seed=3, search_seed=99))
    assert results[0] == results[1]

def test_world_seed_alone_sets_the_opening(monkeypatch):
    hands = {}
    for search_seed in (1, 2):
        seen = []
        monkeypatch.setattr(sts2_MCTS, "monte_carlo_tree_search", _scripted_search(0, seen))
        bench.play_fight(bench.load_state(SMALL, "act1"), SearchConfig(), world_seed=5, search_seed=search_seed)
        hands[search_seed] = seen
    assert hands[1] == hands[2]

def test_different_world_seeds_give_different_fights(monkeypatch):
    seen_by_seed = []
    for world_seed in range(6):
        seen = []
        monkeypatch.setattr(sts2_MCTS, "monte_carlo_tree_search", _scripted_search(0, seen))
        bench.play_fight(bench.load_state(SMALL, "act1"), SearchConfig(), world_seed=world_seed, search_seed=0)
        seen_by_seed.append(tuple(seen))
    assert len(set(seen_by_seed)) > 1

def test_real_fight_is_reproducible_and_scored():
    run = lambda: bench.play_fight(bench.load_state(SMALL, "act1"), SearchConfig(max_sims=100), world_seed=1, search_seed=2)
    r1, r2 = run(), run()
    assert {k: v for k, v in r1.items() if k != "seconds"} == {k: v for k, v in r2.items() if k != "seconds"}
    assert r1["finished"] and r1["decisions"] > 0
    if r1["won"]:
        assert r1["score"] == r1["hp_lost"] >= 0
    else:
        assert r1["score"] > bench.load_state(SMALL, "act1").player.current_hp


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


# ---------------------------------------------------------------- resources
def test_default_workers_leave_cores_and_memory_free(monkeypatch):
    for cores, expected in ((1, 1), (2, 1), (4, 2), (8, 4), (32, 4)):
        monkeypatch.setattr(bench.os, "cpu_count", lambda c=cores: c)
        assert bench.default_workers() == expected

def test_jobs_run_in_a_pool_of_short_lived_workers():
    assert sorted(bench.map_jobs(abs, [-3, -1, -2], 2, "t")) == [1, 2, 3]


# ---------------------------------------------------------------- subsets
def test_draw_subset_keeps_states_with_a_draw_card_in_hand():
    sub = bench.load_index(subset="draw", suite="act1")
    assert sub and len(sub) < len(bench.load_index(suite="act1"))
    for e in sub:
        assert any(c.card_id.name in bench.DRAW_CARDS for c in bench.load_state(e["file"], "act1").player.hand)

def test_draw_card_names_exist_in_the_sim():
    from sts2_lite.card import CardId
    assert all(n in CardId.__members__ for n in bench.DRAW_CARDS)

def test_unknown_subset_is_rejected():
    with pytest.raises(SystemExit):
        bench.load_index(subset="nope", suite="act1")

def test_subsets_get_their_own_reference_file():
    assert bench.reference_path(suite="act1") == bench.BENCHMARKS / "reference_act1.jsonl"
    assert bench.reference_path("draw", "act1").name == "reference_act1_draw.jsonl"


# ---------------------------------------------------------------- run4 suite and puzzles
def test_run4_suite_has_every_state_file():
    entries = bench.load_index(suite="run4")
    assert len(entries) >= 50
    assert all((bench.states_dir("run4") / e["file"]).exists() for e in entries)

def test_unknown_suite_is_rejected():
    with pytest.raises(SystemExit):
        bench.states_dir("nope")

def test_reference_files_are_per_suite():
    assert bench.reference_path(suite="run4").name == "reference_run4.jsonl"
    assert bench.reference_path("draw", "run4").name == "reference_run4_draw.jsonl"

def test_reference_best_is_the_highest_mean_among_explored_moves_not_the_most_visited():
    runs = [{"pick": "a", "children": [{"key": "a", "visits": 900, "q": 50.0}, {"key": "b", "visits": 90, "q": 99.0},
                                       {"key": "c", "visits": 2, "q": 100.0}]}]
    ref = bench.merge_reference("x.json", runs)
    assert ref["best"] == "b"            # c is too thinly visited to trust

def test_puzzle_labels_and_verdicts():
    state = bench.load_state("decision_00001.json", "run4")
    names = [bench.action_label(state, {"action": "play_card", "card_index": i}) for i in range(len(state.player.hand))]
    assert "BRAND" in names and "STRIKE" in names
    assert bench.action_label(state, {"action": "use_potion", "slot": 0}) == "potion"
    assert bench.action_label(state, {"action": "end_turn"}) == "end_turn"
    assert bench.puzzle_passes({"accept": ["BRAND"]}, "BRAND") and not bench.puzzle_passes({"accept": ["BRAND"]}, "STRIKE")
    assert bench.puzzle_passes({"reject": ["potion"]}, "STRIKE") and not bench.puzzle_passes({"reject": ["potion"]}, "potion")

def test_every_puzzle_names_a_real_state_and_cards_in_its_hand():
    index = {e["file"] for e in bench.load_index(suite="run4")}
    for puzzle in bench.load_puzzles("run4"):
        assert puzzle["file"] in index
        assert ("accept" in puzzle) != ("reject" in puzzle)
        hand = {bench.action_label(bench.load_state(puzzle["file"], "run4"), {"action": "play_card", "card_index": i})
                for i in range(len(bench.load_state(puzzle["file"], "run4").player.hand))} | {"potion", "end_turn"}
        assert set(puzzle.get("accept", puzzle.get("reject"))) <= hand

def test_puzzle_job_reports_the_pick_and_whether_it_failed():
    puzzle = {"file": "decision_00013.json", "reject": ["BRAND"]}
    row = bench._puzzle_job((puzzle, 0, bench.config_dict(SearchConfig(max_sims=200, paired_scenarios=0)), "run4"))
    assert row["label"] in ("BRAND", "STRIKE", "DEFEND", "end_turn") and row["fail"] == int(row["label"] == "BRAND")

def test_puzzles_can_be_compared_like_the_other_suites(tmp_path):
    rows = [{"file": "a", "seed": s, "label": "X", "fail": f, "opinion": False, "sims": 1, "seconds": 0.1} for s, f in enumerate([1, 1, 0, 1])]
    better = [dict(r, fail=0) for r in rows]
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    for path, rs in ((a, rows), (b, better)):
        path.write_text(json.dumps({"type": "header", "suite": "puzzles", "label": path.stem, "commit": None}) + "\n" + "\n".join(json.dumps(r) for r in rs))
    assert "paired Δfail" in bench.compare_files(a, b)
