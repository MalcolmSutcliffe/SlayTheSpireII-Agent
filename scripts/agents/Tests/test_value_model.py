import numpy as np

from agents.selfplay import choosers, suite
from agents.selfplay.choosers import Explorer, Counts, make_chooser
from agents.selfplay.value_model import MLP, ModelChooser, POSITION_NAMES, Ridge, Rows, ValueModel, Vocab, featurize, rows_of, sequence_of, td_targets


def snap(deck, floor=3, hp=60, room="Monster", boss="THE_KIN_BOSS", relics=("BURNING_BLOOD",)):
    return {"act": 1, "floor": floor, "ascension": 2, "boss": boss, "hp": hp, "max_hp": 80, "gold": 99, "deck": list(deck), "relics": list(relics), "potions": [], "room": room}


def test_rows_target_is_the_rooms_still_cleared_and_capped():
    run = {"seed": 1, "rooms": [snap([]), snap([]), snap([]), snap([])], "outcome": {"rooms_cleared": 3}}
    snaps, y, seeds = rows_of([run], horizon=2)
    assert list(y) == [2, 2, 1, 0] and list(seeds) == [1] * 4
    snaps, y, seeds = rows_of([run])
    assert list(y) == [3, 2, 1, 0]          # no cap by default


def after(deck, room="Monster"):
    return dict(snap(deck, room=room), reward=True)


def test_after_reward_states_sit_between_the_rooms_with_one_more_room_cleared():
    run = {"seed": 1, "rooms": [snap(["A"]), snap(["A", "B"]), snap(["A", "B"])],
           "picks": [{"room": 1, "after": after(["A", "B"])}, {"room": 2, "after": after(["A", "B"])}, {"room": 2, "chosen": "SKIP"}],   # the last: an old log line
           "outcome": {"rooms_cleared": 2}}
    seq = sequence_of(run)
    assert [done for _, done in seq] == [0, 1, 1, 2, 2]
    assert [bool(s.get("reward")) for s, _ in seq] == [False, True, False, True, False]
    rows = Rows([run])
    assert list(rows.mc()) == [2, 1, 1, 0, 0]


def test_td_targets_go_from_the_outcome_to_one_step_and_the_model():
    runs = [{"seed": 1, "rooms": [snap([])] * 4, "outcome": {"rooms_cleared": 3}}, {"seed": 2, "rooms": [snap([])] * 2, "outcome": {"rooms_cleared": 2}}]
    rows = Rows(runs)
    v = np.array([10, 20, 30, 40, 50, 60], dtype=np.float32)
    assert list(td_targets(rows, v, lam=1.0)) == list(rows.mc()) == [3, 2, 1, 0, 2, 1]
    assert list(td_targets(rows, v, lam=0.0)) == [21, 31, 41, 0, 61, 1]          # one room, then V of the next state; a run's last state is its outcome
    half = td_targets(rows, v, lam=0.5)
    assert half[2] == 1 + 0.5 * 40 + 0.5 * 0 and half[1] == 1 + 0.5 * 30 + 0.5 * half[2]
    assert list(td_targets(rows, None, lam=1.0, gamma=0.5)) == [1.75, 1.5, 1, 0, 1.5, 1]


def test_features_count_cards_upgrades_and_room():
    snaps = [snap(["BASH", "BASH+", "STRIKE_IRONCLAD"]) for _ in range(50)]
    vocab = Vocab.build(snaps, min_count=10)
    X = featurize([snaps[0], snap(["BASH"], room="Elite")], vocab)
    assert X.shape == (2, vocab.size)
    names = vocab.names()
    assert len(names) == vocab.size
    bash, upgraded = names.index("card:BASH"), names.index("upgraded:BASH")
    assert X[0, bash] == 0.5 and X[0, upgraded] == 0.25 and X[1, bash] == 0.25
    assert X[0, names.index("room:Monster")] == 1.0 and X[1, names.index("room:Elite")] == 1.0
    assert X[0, names.index("after_reward")] == 0.0 and featurize([after(["BASH"])], vocab)[0, names.index("after_reward")] == 1.0


def test_ridge_and_mlp_learn_a_simple_target_and_save_round_trips(tmp_path):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(600, 5)).astype(np.float32)
    y = (2 * X[:, 0] - X[:, 1]).astype(np.float32)
    ridge = Ridge(1.0).fit(X, y)
    assert np.mean((ridge.predict(X) - y) ** 2) < 0.01
    mlp = MLP(hidden=(16,), epochs=300, lr=1e-2, weight_decay=0.0, patience=300, batch=100).fit(X, y, X, y)
    assert np.mean((mlp.predict(X) - y) ** 2) < 0.5
    snaps = [snap(["BASH", "STRIKE_IRONCLAD"]) for _ in range(60)]
    vocab = Vocab.build(snaps, min_count=10)
    Xs = featurize(snaps, vocab)
    for model in (Ridge(10.0).fit(Xs, np.arange(60, dtype=np.float32)), MLP(hidden=(4,), epochs=2).fit(Xs, np.arange(60, dtype=np.float32))):
        value_model = ValueModel(vocab, model)
        value_model.save(tmp_path / type(model).__name__)
        again = ValueModel.load(tmp_path / type(model).__name__)
        assert np.allclose(value_model.values(snaps[:3]), again.values(snaps[:3]), atol=1e-4)


def test_model_chooser_scores_gains_and_skip_is_zero():
    snaps = [snap(["BASH"] * (i % 3 + 1)) for i in range(60)]
    vocab = Vocab.build(snaps, min_count=10)
    y = np.array([len(s["deck"]) for s in snaps], dtype=np.float32)
    model = ValueModel(vocab, Ridge(0.1).fit(featurize(snaps, vocab), y))
    scores = ModelChooser(model).scores(snap(["BASH"]), [{"id": "BASH"}])
    assert len(scores) == 2 and scores[1] == 0.0 and scores[0] > 0
    index, record = Explorer(ModelChooser(model), Counts(), c=0.0, epsilon=0.0).pick(snap(["BASH"]), [{"id": "BASH"}])
    assert record["chosen"] == "BASH"
    upgraded = ModelChooser(model).scores(snap(["BASH"]), [{"id": "BASH", "is_upgraded": True}])
    assert upgraded[0] != scores[0]         # scored as BASH+ (no column of its own here, but no BASH count either)


def test_the_pilot_has_its_own_block_and_a_snapshot_without_one_is_the_mcts():
    snaps = [snap(["BASH", "INFLAME"]) for _ in range(50)]
    vocab = Vocab.build(snaps, min_count=10)
    names = vocab.names()
    assert len(names) == vocab.size
    rollout, agent = featurize([dict(snaps[0], pilot="rollout"), snaps[0]], vocab)
    pilot, mcts_bash, bash = names.index("pilot_mcts"), names.index("mcts_card:BASH"), names.index("card:BASH")
    assert rollout[pilot] == 0 and rollout[mcts_bash] == 0 and rollout[bash] == 0.25
    assert agent[pilot] == 1 and agent[mcts_bash] == agent[bash] == 0.25
    assert featurize([dict(snaps[0], pilot="mcts:100:big")], vocab)[0, pilot] == 1


def test_rows_carry_the_runs_pilot_and_leave_out_engine_errors():
    runs = [{"seed": 1, "pilot": "mcts:100:big", "rooms": [snap([])] * 2, "outcome": {"rooms_cleared": 1}},
            {"seed": 2, "rooms": [snap([])] * 3, "outcome": {"rooms_cleared": 3}},
            {"seed": 3, "rooms": [snap([])] * 3, "outcome": {"rooms_cleared": 2, "cause": "engine error"}},
            {"seed": 4, "rooms": [], "outcome": {"rooms_cleared": 0, "cause": "engine error: timed out after 900 s"}}]
    rows = Rows(runs)
    assert [s["pilot"] for s in rows.snaps] == ["mcts:100:big"] * 2 + ["rollout"] * 3
    assert sorted(set(rows.seeds)) == [1, 2] and sorted(set(rows.episode)) == [0, 1]


def test_the_model_chooser_skips_below_its_floor_and_loads_by_name(tmp_path, monkeypatch):
    snaps = [snap(["BASH"] * (i % 3 + 1)) for i in range(60)]
    vocab = Vocab.build(snaps, min_count=10)
    y = np.array([len(s["deck"]) for s in snaps], dtype=np.float32)
    model = ValueModel(vocab, Ridge(0.1).fit(featurize(snaps, vocab), y))
    gain = ModelChooser(model).scores(snap(["BASH"]), [{"id": "BASH"}])[0]
    assert ModelChooser(model, floor=gain + 1).scores(snap(["BASH"]), [{"id": "BASH"}])[1] == gain + 1
    monkeypatch.setattr(suite, "OUT_ROOT", tmp_path)
    choosers._value_model.cache_clear()
    model.save(tmp_path / "models" / "g0" / "ridge")
    loaded = make_chooser("model:g0/ridge:0.5")
    assert loaded.floor == 0.5 and np.isclose(loaded.scores(snap(["BASH"]), [{"id": "BASH"}])[0], gain, atol=1e-4)
    choosers._value_model.cache_clear()
