import random

import numpy as np

from agents.selfplay.run import play_run
from agents.selfplay.value_model import MLP
from agents.strategy.fight_model import FightModel, Vocab, auc, cost, featurize, fight_rows, NPOS


def before(deck, hp=60, act=1, relics=("BURNING_BLOOD",), potions=()):
    return {"act": act, "floor": 5, "ascension": 0, "boss": "THE_KIN_BOSS", "hp": hp, "max_hp": 80, "gold": 50, "deck": list(deck), "relics": list(relics),
            "potions": list(potions), "room": "Elite"}


def fight(deck, won=True, hp_after=40, hp=60, encounter="BYRDONIS_ELITE", kind="Elite", seed=1, mcts=True, error=False):
    return {"encounter": encounter, "kind": kind, "mcts": mcts, "error": error, "before": before(deck, hp), "won": won, "dead": not won, "hp_after": hp_after if won else 0,
            "seed": seed}


def test_fight_rows_keep_the_mcts_fights_the_engine_did_not_fail_in():
    run = {"seed": 3, "fight_log": [fight([], mcts=True), fight([], mcts=False), fight([], error=True)]}
    rows = fight_rows([run])
    assert len(rows) == 1 and rows[0]["seed"] == 3
    assert len(fight_rows([run], mcts_only=False)) == 2
    assert fight_rows([{"seed": 1}]) == []           # a log from before fights were logged


def test_cost_is_the_hp_lost_or_all_of_it_when_lost():
    assert cost(fight([], won=True, hp_after=45, hp=60)) == 15
    assert cost(fight([], won=False, hp=60)) == 60


def test_features_count_the_cards_and_mark_the_encounter_and_kind():
    fs = [fight(["STRIKE_IRONCLAD"] * 4 + ["BASH+"]), fight(["INFLAME"], encounter="X_ELITE", kind="Boss")]
    vocab = Vocab.build(fs, min_count=1)
    X = featurize(fs, vocab)
    names = vocab.names()
    assert X.shape == (2, vocab.size) and len(names) == vocab.size
    assert X[0, names.index("card:STRIKE_IRONCLAD")] == 1.0 and X[0, names.index("upgraded:BASH")] == 0.25
    assert X[0, names.index("enc:BYRDONIS_ELITE")] == 1.0 and X[1, names.index("enc:X_ELITE")] == 1.0
    assert X[0, names.index("kind:Elite")] == 1.0 and X[1, names.index("kind:Boss")] == 1.0
    assert X[0, names.index("relic:BURNING_BLOOD")] == 1.0


def test_a_logistic_mlp_learns_a_probability():
    r = np.random.default_rng(0)
    X = r.standard_normal((2000, 3)).astype(np.float32)
    y = (r.random(2000) < 1 / (1 + np.exp(-2 * X[:, 0]))).astype(np.float32)
    m = MLP(hidden=(8,), epochs=30, lr=3e-3, loss="bce").fit(X[:1500], y[:1500], X[1500:], y[1500:])
    p = m.predict(X[1500:])
    assert ((0 <= p) & (p <= 1)).all() and auc(y[1500:], p) > 0.8
    again = MLP.from_state(m.state())
    assert np.allclose(again.predict(X[:5]), m.predict(X[:5]))


def test_a_fight_model_learns_that_a_card_saves_hp_and_round_trips(tmp_path):
    rnd = random.Random(0)
    fs = []
    for i in range(600):
        has = rnd.random() < 0.5
        deck = ["STRIKE_IRONCLAD"] * 5 + (["SHRUG_IT_OFF"] if has else [])
        lose = rnd.random() < (0.05 if has else 0.4)
        fs.append(fight(deck, won=not lose, hp_after=50 if has else 30, seed=i))
    vocab = Vocab.build(fs, 1)
    X = featurize(fs, vocab)
    yl = np.array([not f["won"] for f in fs], dtype=np.float32)
    won = yl < 0.5
    yh = np.array([f["before"]["hp"] - f["hp_after"] for f in fs], dtype=np.float32)
    model = FightModel(vocab, MLP(hidden=(8,), epochs=60, lr=3e-3, loss="bce").fit(X, yl), MLP(hidden=(8,), epochs=60, lr=3e-3).fit(X[won], yh[won]))
    a, b = model.predict([fight(["STRIKE_IRONCLAD"] * 5 + ["SHRUG_IT_OFF"]), fight(["STRIKE_IRONCLAD"] * 5)])["cost"]
    assert a < b - 10
    model.save(tmp_path / "m")
    again = FightModel.load(tmp_path / "m")
    assert np.allclose(again.predict(fs[:3])["cost"], model.predict(fs[:3])["cost"], atol=1e-4)


def test_a_self_play_run_logs_its_fights():
    run = play_run(5, "rarity", epsilon=0.0)
    log = run["fight_log"]
    assert log and len(log) == run["outcome"]["fights"]
    for f in log:
        assert f["kind"] in ("Monster", "Elite", "Boss") and not f["mcts"] and f["corrected"]
        assert f["before"]["room"] == f["kind"] and f["turns"] >= 1
    assert all(f["won"] for f in log[:-1])
    if not run["outcome"]["won"] and not log[-1]["won"]:
        assert log[-1]["progress"] is not None


def variant(source, changes, hp_after, base=("STRIKE_IRONCLAD",) * 5, won=True, seed=10):
    deck = list(base)
    for c in changes:
        if c["op"] == "add":
            deck.append(c["card"])
        else:
            deck.remove(c["card"])
    f = fight(deck, won=won, hp_after=hp_after, seed=seed)
    return dict(f, source=source, base_deck=list(base), changes=changes)


def test_card_effects_recover_what_the_random_changes_did():
    from agents.strategy.fight_model import card_effects
    rnd = random.Random(1)
    true = {"INFLAME": -6.0, "BASH": 3.0, "IRON_WAVE": 0.0}
    vs = []
    for s in range(300):
        for _ in range(4):
            changes = [{"op": "add", "card": rnd.choice(list(true))} for _ in range(rnd.randint(0, 3))]
            hp_lost = 20 + sum(true[c["card"]] for c in changes) + rnd.gauss(0, 2) + (s % 7)
            vs.append(variant(f"{s}/1/X", changes, 60 - hp_lost, seed=s))
    eff = card_effects(vs, min_n=10)
    for card, value in true.items():
        e, se, n = eff[card]
        assert abs(e - value) < 4 * se + 0.3 and n > 100


def test_the_within_fight_test_scores_a_perfect_model_near_its_ceiling():
    from agents.strategy.fight_model import within_fight
    rnd = random.Random(2)
    vs, truth = [], []
    for s in range(200):
        for k in range(4):
            changes = [] if k == 0 else [{"op": "add", "card": "INFLAME"}] * k
            mean = 30 - 4 * k
            vs.append(variant(f"{s}/1/X", changes, 60 - (mean + rnd.gauss(0, 3))))
            truth.append(mean)
        vs.append(variant(f"{s}/1/X", [], 60 - (30 + rnd.gauss(0, 3))))          # the base deck again: the noise
        truth.append(30)
    wf = within_fight(vs, np.array(truth, dtype=float))
    assert wf["corr"] > 0.8 and abs(wf["r2"] - wf["ceiling"]) < 0.1 and 2 < wf["noise_sd"] < 4
    bad = within_fight(vs, np.zeros(len(vs)))
    assert abs(bad["corr"]) < 1e-6 or np.isnan(bad["corr"])
