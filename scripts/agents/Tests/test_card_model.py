import random

import numpy as np

from agents.selfplay.value_model import MLP, demean, group_codes
from agents.strategy.card_model import CardModel, WithinRidge, demean_rows, interactions, measured_pair, sources, with_deck
from agents.strategy.fight_model import Vocab, cost, featurize, within_fight

BASE = ["STRIKE_IRONCLAD"] * 5 + ["DEFEND_IRONCLAD"] * 4


def variant(source, kind, base, changes, cost_hp, seed):
    deck = list(base)
    for c in changes:
        if c["op"] == "add":
            deck.append(c["card"])
        else:
            deck.remove(c["card"])
    hp = 70
    return {"source": source, "encounter": "BYRDONIS_ELITE" if kind == "Elite" else "THE_KIN_BOSS", "kind": kind, "mcts": True, "seed": seed,
            "before": {"act": 1, "floor": 5, "ascension": 0, "hp": hp, "max_hp": 80, "gold": 0, "deck": deck, "relics": [], "potions": [], "room": kind},
            "base_deck": list(base), "changes": changes, "won": True, "dead": False, "hp_after": hp - cost_hp}


def true_cost(kind, deck):
    """INFLAME is worth 6 HP in a boss fight and 1 in an elite; BODY_SLAM 4 only with BARRICADE in the deck; BASH costs 2."""
    c = deck.count("INFLAME") * (-6.0 if kind == "Boss" else -1.0) + 2.0 * deck.count("BASH")
    if "BARRICADE" in deck:
        c -= 4.0 * deck.count("BODY_SLAM")
    return c


def synthetic(n_sources=500, per=6, noise=1.5, seed=0):
    r = random.Random(seed)
    out = []
    for s in range(n_sources):
        kind = "Boss" if s % 2 else "Elite"
        base = BASE + (["BARRICADE"] if s % 4 < 2 else [])
        offset = r.uniform(5, 40)          # where the run is: the same for the whole group, much bigger than the cards
        for _ in range(per):
            changes = [{"op": "add", "card": r.choice(["INFLAME", "BASH", "BODY_SLAM", "IRON_WAVE"])} for _ in range(r.randint(0, 3))]
            deck = base + [c["card"] for c in changes]
            out.append(variant(f"{s}/1/X", kind, base, changes, offset + true_cost(kind, deck) - true_cost(kind, base) + r.gauss(0, noise), seed=s))
    return out


def test_demean_takes_each_group_s_mean_off():
    codes = group_codes(["b", "a", "b", "a", "c"])
    assert list(codes) == [0, 1, 0, 1, 2]
    v = np.array([1.0, 2.0, 3.0, 6.0, 5.0])
    assert np.allclose(demean(v, codes), [-1, -2, 1, 2, 0])
    F = np.stack([v, 2 * v], 1)
    assert np.allclose(demean_rows(F, codes), np.stack([demean(v, codes), 2 * demean(v, codes)], 1))


def test_a_within_group_mlp_learns_the_differences_not_the_offsets():
    r = np.random.default_rng(0)
    groups = np.repeat(np.arange(400), 5)
    X = r.standard_normal((2000, 3)).astype(np.float32)
    y = (3 * X[:, 0] + r.uniform(-50, 50, 400)[groups] + 0.3 * r.standard_normal(2000)).astype(np.float32)
    m = MLP(hidden=(8,), epochs=60, lr=3e-3).fit(X[:1500], y[:1500], X[1500:], y[1500:], groups=groups[:1500], gval=groups[1500:])
    p = m.predict(X[1500:])
    assert np.corrcoef(demean(p, groups[1500:]), demean(y[1500:], groups[1500:]))[0, 1] > 0.95


def test_the_ridge_learns_a_card_s_value_by_kind_of_fight_and_round_trips(tmp_path):
    vs = synthetic()
    vocab = Vocab.build(vs, 1)
    sel = [vocab.card_at[c] for c in ("INFLAME", "BODY_SLAM", "BASH")]
    X = featurize(vs, vocab)
    model = CardModel(vocab, WithinRidge(1.0).fit(interactions(X, vocab, sel), [cost(v) for v in vs], [v["source"] for v in vs]), sel)
    srcs = sources(vs)
    boss, elite = [f for f in srcs if f["kind"] == "Boss"], [f for f in srcs if f["kind"] == "Elite"]
    assert abs(model.delta(boss, "INFLAME").mean() + 6) < 1 and abs(model.delta(elite, "INFLAME").mean() + 1) < 1
    assert abs(model.delta(srcs, "BASH").mean() - 2) < 0.5
    wf = within_fight(vs, model.score(vs))
    assert wf["corr"] > 0.8
    model.save(tmp_path / "m")
    again = CardModel.load(tmp_path / "m")
    assert np.allclose(again.score(vs[:10]), model.score(vs[:10]), atol=1e-3)


def test_the_measured_pair_finds_a_synergy_and_no_false_one():
    vs = synthetic(n_sources=800)
    e, se, n = measured_pair(vs, "BARRICADE", "BODY_SLAM")
    assert abs(e + 4) < 4 * se + 0.3 and n > 100
    e, se, _ = measured_pair(vs, "BARRICADE", "BASH")
    assert abs(e) < 4 * se + 0.3


def test_with_deck_leaves_the_fight_alone():
    v = synthetic(2, 1)[0]
    w = with_deck(v, ["BASH"])
    assert w["before"]["deck"] == ["BASH"] and v["before"]["deck"] != ["BASH"] and w["before"]["hp"] == v["before"]["hp"]
