import numpy as np

from agents.deck_eval.card_reward_chooser import decide
from agents.deck_eval.config import DEFAULT
from agents.selfplay import choosers, suite
from agents.selfplay.choosers import make_chooser
from agents.selfplay.label import play_labeled_run
from agents.selfplay.pick_model import PickModel, PickChooser, baselines, card_rows, features, pick_values, screens_of
from agents.selfplay.value_model import MLP, Ridge, Vocab


def snap(deck, floor=3):
    return {"act": 1, "floor": floor, "ascension": 0, "boss": "THE_KIN_BOSS", "hp": 60, "max_hp": 80, "gold": 99, "deck": list(deck), "relics": ["BURNING_BLOOD"],
            "potions": [], "room": "Monster", "reward": True}


def label(key, gain, se=0.1, bonus=0.0, rarity="Common", ctype="Attack"):
    return {"key": key, "type": ctype, "rarity": rarity, "gain": gain, "se": se, "bonus": bonus, "win_rate": 0.5}


def screen(labels, teacher, seed=1, deck=("STRIKE_IRONCLAD",) * 5):
    return {"seed": seed, "snap": snap(deck), "labels": labels, "teacher": teacher, "needed": 0.1, "early": False}


def test_decide_takes_the_best_card_only_when_it_clears_the_noise_and_the_floor():
    rows = [(0.5, 0.1, "a"), (2.0, 1.5, "b")]          # the best card is too noisy to clear 1.5 standard errors
    best, take, needed = decide(rows, 1.0, False, DEFAULT)
    assert best[2] == "b" and not take and needed == DEFAULT.card_z * 1.5 + DEFAULT.card_floor
    best, take, _ = decide([(0.5, 0.1, "a")], 1.0, False, DEFAULT)
    assert take
    assert decide([], 1.0, False, DEFAULT) == (None, False, 0.0)


def test_sample_weights_pull_the_fit_towards_the_heavy_rows():
    X = np.array([[0.0], [0.0], [1.0], [1.0]], dtype=np.float32)
    y = np.array([0.0, 2.0, 1.0, 1.0], dtype=np.float32)          # at x = 0: 0 (heavy) or 2 (light)
    w = np.array([100.0, 1.0, 1.0, 1.0])
    plain, weighted = Ridge(1e-6).fit(X, y), Ridge(1e-6).fit(X, y, w=w)
    assert abs(plain.predict(X[:1])[0] - 1.0) < 1e-3 and weighted.predict(X[:1])[0] < 0.1
    mlp = MLP(hidden=(4,), epochs=300, lr=1e-2, batch=4, patience=1000).fit(X, y, X, y, w, w)
    assert mlp.predict(X[:1])[0] < 0.5


def test_features_carry_the_card_and_what_it_adds_to_the_deck():
    vocab = Vocab(["BASH", "INFLAME", "STRIKE_IRONCLAD"], ["BURNING_BLOOD"], ["THE_KIN_BOSS"])
    s = snap(["STRIKE_IRONCLAD"] * 5)
    X = features([s, s], ["INFLAME", "BASH+"], vocab)
    which = X[:, -4:]
    assert list(which[0]) == [0, 1, 0, 0] and list(which[1]) == [1, 0, 0, 1]
    diff = X[:, vocab.size:2 * vocab.size]
    names = vocab.names()
    assert diff[0, names.index("card:INFLAME")] > 0 and diff[1, names.index("upgraded:BASH")] > 0
    assert np.allclose(X[0, :vocab.size], X[1, :vocab.size])


def test_pick_values_score_the_pick_by_its_label_and_skip_below_the_margin():
    screens = [screen([label("A", 1.0, bonus=0.5), label("B", -0.5)], 0), screen([label("A", -1.0), label("B", -0.2)], 2)]
    _, _, _, _, at = card_rows(screens)
    pred = np.array([1.0, 0.0, -1.0, 0.3])
    values, picks = pick_values(screens, pred, at, margin=0.0)
    assert list(picks) == [0, 1] and np.allclose(values, [1.5, -0.2])
    values, picks = pick_values(screens, pred, at, margin=0.5)
    assert list(picks) == [0, 2] and np.allclose(values, [1.5, 0.0])
    base = baselines(screens)
    assert np.allclose(base["teacher (on its labels)"], [1.5, 0.0]) and np.allclose(base["best by labels"], [1.5, 0.0]) and np.allclose(base["always skip"], 0.0)


def test_a_pick_model_learns_which_card_the_walks_like_and_round_trips(tmp_path, monkeypatch):
    good, bad = label("INFLAME", 1.0), label("BASH", -1.0)
    screens = [screen([dict(good, gain=1.0 + 0.1 * (i % 3)), dict(bad, gain=-1.0 - 0.1 * (i % 2))], 0, seed=i) for i in range(60)]
    vocab = Vocab.build([s["snap"] for s in screens] + [snap(["INFLAME", "BASH"])] * 40, 1)
    snaps, keys, y, se, at = card_rows(screens)
    model = PickModel(vocab, Ridge(1.0).fit(features(snaps, keys, vocab), y), margin=0.25)
    g = model.gains(snap(["STRIKE_IRONCLAD"] * 5), ["INFLAME", "BASH"])
    assert g[0] > 0.5 and g[1] < -0.5
    monkeypatch.setattr(suite, "OUT_ROOT", tmp_path)
    model.save(tmp_path / "models" / "t" / "ridge")
    choosers._pick_model.cache_clear()
    chooser = make_chooser("pick:t/ridge")
    assert isinstance(chooser, PickChooser) and chooser.margin == 0.25
    scores = chooser.scores(snap(["STRIKE_IRONCLAD"] * 5), [{"id": "INFLAME", "type": "Power", "rarity": "Uncommon"}, {"id": "BASH", "type": "Attack", "rarity": "Basic"}])
    assert scores[0] > scores[2] > scores[1]
    assert make_chooser("pick:t/ridge:3.5").margin == 3.5


def test_a_labeled_run_rates_every_reward_and_is_repeatable():
    a, b = play_labeled_run(3, fights=6, epsilon=0.0), play_labeled_run(3, fights=6, epsilon=0.0)
    assert a["outcome"] == b["outcome"] and [p["chosen"] for p in a["picks"]] == [p["chosen"] for p in b["picks"]]
    assert a["picks"] and a["labeled"]
    for p in a["picks"]:
        assert len(p["labels"]) == len(p["offered"]) and p["route"]
        assert all({"gain", "se", "bonus"} <= set(c) for c in p["labels"])
        teacher = "SKIP" if p["teacher"] == len(p["offered"]) else p["offered"][p["teacher"]]
        assert p["chosen"] == teacher and not p["exploratory"]
        assert p["after"]["deck"] == p["snap"]["deck"] + ([] if teacher == "SKIP" else [teacher])
    assert len(screens_of([a])) == len(a["picks"])
