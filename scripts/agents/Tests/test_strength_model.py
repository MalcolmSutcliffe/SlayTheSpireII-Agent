import math
import random

import numpy as np

from agents.strategy.fight_model import Vocab
from agents.strategy.strength_model import StrengthModel, context_columns, group_index

BASE = ["STRIKE_IRONCLAD"] * 5 + ["DEFEND_IRONCLAD"] * 4 + ["BASH"]
TRUE = {"INFLAME": -0.6, "SHRUG_IT_OFF": -0.3, "IRON_WAVE": 0.0, "CLUMSY": 0.5}


def fight(deck, kind, offset, r, source, seed):
    """Lost with chance sigmoid(offset + sum of TRUE values); HP lost if won 20 + 8 * strength."""
    s = sum(TRUE.get(c, 0.0) for c in deck)
    lose = r.random() < 1 / (1 + math.exp(-(offset + s)))
    hp = 60
    lost_hp = max(0.0, 20 + 8 * s + r.gauss(0, 3))
    return {"source": source, "encounter": "BYRDONIS_ELITE" if kind == "Elite" else "THE_KIN_BOSS", "kind": kind, "seed": seed, "mcts": True,
            "before": {"act": 1, "floor": 5, "ascension": 0, "hp": hp, "max_hp": 80, "gold": 0, "deck": deck, "relics": [], "potions": [], "room": kind},
            "won": not lose, "dead": lose, "hp_after": 0 if lose else hp - lost_hp, "changes": [], "base_deck": BASE}


def synthetic(n=1500, per=6, seed=0):
    r = random.Random(seed)
    out = []
    for s in range(n):
        kind = "Boss" if s % 2 else "Elite"
        offset = (0.5 if kind == "Boss" else -1.5) + r.gauss(0, 0.5)
        for _ in range(per):
            deck = BASE + [r.choice(list(TRUE)) for _ in range(r.randint(0, 3))]
            out.append(fight(deck, kind, offset, r, f"{s}/1/X", s))
    return out


def test_the_model_recovers_the_card_values_and_the_kind_of_fight():
    fs = synthetic()
    train, val = [f for f in fs if f["seed"] % 5], [f for f in fs if f["seed"] % 5 == 0]
    vocab = Vocab.build(train, 1)
    m = StrengthModel(vocab, context_columns(vocab), group_index(fs))
    m.fit(m.data(train), m.data(val), steps=1500, l2={"v": 0.1, "vu": 0.1})
    v = m.card_values()
    s = lambda c: v[c] * math.exp(-float(m.p["alpha"]) * math.log(len(BASE) / 15))
    assert s("INFLAME") < s("SHRUG_IT_OFF") < s("IRON_WAVE") < s("CLUMSY")
    assert abs(s("INFLAME") - s("CLUMSY") - (-1.1)) < 0.35
    boss = [f for f in val if f["kind"] == "Boss"][:50]
    elite = [f for f in val if f["kind"] == "Elite"][:50]
    assert m.predict(boss)["p_lose"].mean() > m.predict(elite)["p_lose"].mean() + 0.2
    # the link: a card moves the cost more in the fight nearer to losing (the boss, where P(lose) is nearer 1/2)
    assert abs(m.delta(boss, "INFLAME").mean()) > abs(m.delta(elite, "INFLAME").mean())


def test_save_and_load_give_the_same_predictions(tmp_path):
    fs = synthetic(200, 4)
    vocab = Vocab.build(fs, 1)
    m = StrengthModel(vocab, context_columns(vocab), group_index(fs))
    m.fit(m.data(fs), steps=50)
    m.save(tmp_path / "s")
    again = StrengthModel.load(tmp_path / "s")
    new = [dict(f, source=None) for f in fs[:20]]          # a fight it has not seen: no group effect
    assert np.allclose(again.predict(new)["cost"], m.predict(new)["cost"])


def test_the_context_columns_leave_out_the_deck():
    fs = synthetic(10, 2)
    vocab = Vocab.build(fs, 1)
    names = vocab.names()
    kept = [names[j] for j in context_columns(vocab)]
    assert not any(n.startswith(("card:", "upgraded:", "does:")) for n in kept) and "deck_size" not in kept and "kind:Boss" in kept
