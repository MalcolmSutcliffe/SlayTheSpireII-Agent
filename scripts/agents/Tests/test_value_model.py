import numpy as np

from agents.selfplay.choosers import Explorer, Counts
from agents.selfplay.value_model import MLP, ModelChooser, POSITION_NAMES, Ridge, ValueModel, Vocab, featurize, rows_of


def snap(deck, floor=3, hp=60, room="Monster", boss="THE_KIN_BOSS", relics=("BURNING_BLOOD",)):
    return {"act": 1, "floor": floor, "ascension": 2, "boss": boss, "hp": hp, "max_hp": 80, "gold": 99, "deck": list(deck), "relics": list(relics), "potions": [], "room": room}


def test_rows_target_is_the_rooms_still_cleared_and_capped():
    run = {"seed": 1, "rooms": [snap([]), snap([]), snap([]), snap([])], "outcome": {"rooms_cleared": 3}}
    snaps, y, seeds = rows_of([run], horizon=2)
    assert list(y) == [2, 2, 1, 0] and list(seeds) == [1] * 4


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
