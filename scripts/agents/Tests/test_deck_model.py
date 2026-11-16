"""The deck model (agents/deck_eval/deck_model.py) and the sweep's data helpers (benchmarks/deck_sweep.py)."""
import random

import numpy as np

from agents.deck_eval.deck_model import PairRegression, DeckModel

CARDS = ["C%d" % i for i in range(12)]


def synthetic(n, seed, noise=0.05):
    """Fights whose cost is made from a base value per card and one synergy: C0 + C1 together are worth -0.25 more than apart."""
    r = random.Random(seed)
    base = {c: (-0.04 if c in ("C0", "C1", "C2") else 0.01) for c in CARDS}
    rows, ys = [], []
    for _ in range(n):
        deck = [{"id": c} for c in r.choices(CARDS, k=r.randint(5, 12))]
        ids = {c["id"] for c in deck}
        y = 0.5 + sum(base[c["id"]] for c in deck) - (0.25 if {"C0", "C1"} <= ids else 0.0) + r.gauss(0, noise)
        rows.append((deck, [], "normal", 1.0))
        ys.append(y)
    return rows, ys


def test_the_regression_finds_a_synergy_and_the_good_cards():
    rows, ys = synthetic(600, 1)
    model = PairRegression(lam_base=1.0, lam_pair=5.0).fit(rows, ys)
    assert model.pair[("C0", "C1")] < -0.1
    assert max(abs(v) for p, v in model.pair.items() if p != ("C0", "C1")) < abs(model.pair[("C0", "C1")])
    assert all(model.base[c] < model.base["C9"] for c in ("C0", "C1", "C2"))
    test_rows, test_ys = synthetic(200, 2)
    pred = [model.predict(*x) for x in test_rows]
    assert np.corrcoef(pred, test_ys)[0, 1] > 0.9


def test_gain_is_the_change_in_the_prediction_and_pairs_show_in_it():
    rows, ys = synthetic(600, 3)
    model = PairRegression(lam_base=1.0, lam_pair=5.0).fit(rows, ys)
    deck = [{"id": "C0"}, {"id": "C5"}, {"id": "C6"}]
    with_partner = model.gain(deck, {"id": "C1"}, [], "normal")
    without = model.gain([{"id": "C5"}, {"id": "C6"}], {"id": "C1"}, [], "normal")
    assert with_partner < without - 0.1               # C1 helps more next to C0
    assert isinstance(model, DeckModel) and abs(model.gain(deck, {"id": "C5"}, [], "normal") - (model.predict(deck + [{"id": "C5"}], [], "normal") - model.predict(deck, [], "normal"))) < 1e-12


def test_a_model_survives_saving_and_unseen_cards_count_zero(tmp_path):
    rows, ys = synthetic(200, 4)
    model = PairRegression().fit(rows, ys)
    model.save(tmp_path / "m.json")
    loaded = PairRegression.load(tmp_path / "m.json")
    deck = [{"id": "C0"}, {"id": "C1"}, {"id": "NEVER_SEEN"}]
    assert abs(loaded.predict(deck, [], "normal") - model.predict(deck, [], "normal")) < 1e-9
    assert loaded.predict(deck, [], "normal") == loaded.predict(deck[:2], [], "normal")


def test_a_pair_seen_in_few_fights_stays_near_zero_with_a_strong_penalty():
    rows, ys = synthetic(40, 5)
    weak = PairRegression(lam_base=1.0, lam_pair=1.0).fit(rows, ys)
    strong = PairRegression(lam_base=1.0, lam_pair=500.0).fit(rows, ys)
    assert sum(abs(v) for v in strong.pair.values()) < sum(abs(v) for v in weak.pair.values())

def test_the_sweep_draws_the_same_case_every_time_and_a_deck_grows_with_the_act():
    from benchmarks.deck_sweep import make_case, cost
    a, b = make_case(1, 7), make_case(1, 7)
    assert [c["id"] for c in a["deck"]] == [c["id"] for c in b["deck"]] and a["template"] == b["template"] and a["hp"] == b["hp"]
    sizes = {act: [len(make_case(2, i)["deck"]) for i in range(200) if make_case(2, i)["act"] == act] for act in (1, 3)}
    assert sum(sizes[1]) / len(sizes[1]) < sum(sizes[3]) / len(sizes[3])
    assert cost(False, 10, 50) == 1.0 and cost(True, 10, 50) == 0.2
