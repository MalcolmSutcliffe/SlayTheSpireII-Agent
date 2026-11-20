import random

import numpy as np

from agents.selfplay.value_model import Ridge
from agents.strategy.effect_model import EffectModel, card_columns, effect, features, held_out, reliability, score, usable
from agents.strategy.experiments import REWARD_POOL, apply, design, job, run_of
from agents.strategy.fight_model import Vocab

STARTER = ["STRIKE_IRONCLAD"] * 5 + ["DEFEND_IRONCLAD"] * 4 + ["BASH"]


def before(deck=STARTER, hp=70):
    return {"act": 1, "floor": 2, "ascension": 0, "boss": None, "hp": hp, "max_hp": 80, "gold": 99, "deck": list(deck), "relics": ["BURNING_BLOOD"], "potions": [],
            "room": "Monster"}


def state(i=0, deck=STARTER):
    return {"source": f"{i}/1/TOADPOLES_WEAK", "encounter": "TOADPOLES_WEAK", "kind": "Monster", "before": before(deck)}


def test_the_design_is_repeatable_and_changes_one_card():
    states = [state(i) for i in range(5)]
    a, b = design(states, 50, 3), design(states, 50, 3)
    assert a == b and [e["i"] for e in a] == list(range(50))
    ops = {e["change"]["op"] for e in a}
    assert ops == {"add", "remove"}
    for e in a:
        alt = apply(e["before"]["deck"], e["change"])
        assert abs(len(alt) - len(e["before"]["deck"])) == 1
        if e["change"]["op"] == "add":
            assert e["change"]["card"].rstrip("+") in REWARD_POOL
        else:
            assert e["change"]["card"] in e["before"]["deck"]


def test_apply_removes_one_copy():
    assert apply(["A", "B", "A"], {"op": "remove", "card": "A"}) == ["B", "A"]
    assert apply(["A"], {"op": "add", "card": "C+"}) == ["A", "C+"]


def test_the_run_is_rebuilt_from_a_snapshot():
    run = run_of(dict(before(), potions=["FIRE_POTION"]), ["BASH+", "STRIKE_IRONCLAD"])
    assert [c["id"] for c in run.deck] == ["BASH", "STRIKE_IRONCLAD"] and run.deck[0].get("is_upgraded")
    assert run.hp == 70 and run.max_hp == 80 and run.relics[0]["id"] == "BURNING_BLOOD" and run.potions[0]["id"] == "FIRE_POTION"


def test_an_experiment_plays_both_decks_on_the_same_seeds_and_repeats():
    exp = dict(state(), i=0, change={"op": "add", "card": "INFLAME"})
    a, b = job((exp, 2, 5)), job((exp, 2, 5))
    assert not a.get("error") and len(a["reps"]) == 2 and a["reps"][0]["seed"] != a["reps"][1]["seed"]
    assert a == b
    for rep in a["reps"]:
        for arm in ("base", "alt"):
            r = rep[arm]
            assert r["cost"] == (70 - r["hp_after"] if r["won"] else 70)


def experiment(i, card, eff, op="add", kind="Elite"):
    return {"i": i, "source": f"{i}/3/X", "encounter": "BYRDONIS_ELITE", "kind": kind, "before": before(), "change": {"op": op, "card": card}, "sims": 5,
            "reps": [{"seed": 1, "base": {"cost": 10.0}, "alt": {"cost": 10.0 + eff + d}} for d in (-1.0, 1.0)]}


def test_effects_reliability_and_the_held_out_split():
    exps = [experiment(i, "INFLAME" if i % 2 else "BASH", -5.0 if i % 2 else 3.0) for i in range(40)]
    assert effect(exps[1]) == -5.0 and effect(exps[0]) == 3.0
    r, ceiling, n = reliability(exps)
    assert n == 40 and r > 0.8 and 0.8 < ceiling <= 1.0
    assert usable([dict(exps[0], reps=[]), dict(exps[0], error="x"), exps[0]]) == [exps[0]]
    held = [held_out(e) for e in experiment_sources(200)]
    assert 0.1 < np.mean(held) < 0.3


def experiment_sources(n):
    return [{"source": f"{i}/1/X"} for i in range(n)]


def test_an_effect_model_learns_which_card_helps(tmp_path):
    rnd = random.Random(0)
    exps = [experiment(i, c, (-6.0 if c == "INFLAME" else 2.0) + rnd.gauss(0, 1)) for i, c in enumerate(rnd.choice(["INFLAME", "BASH"]) for _ in range(200))]
    vocab = Vocab.build([dict(e, before=dict(e["before"], deck=apply(e["before"]["deck"], e["change"]))) for e in exps], 1)
    y = np.array([effect(e) for e in exps], dtype=np.float32)
    assert card_columns(exps[:1], vocab).sum() != 0
    model = EffectModel(vocab, Ridge(1.0).fit(features(exps, vocab), y))
    p = model.predict([experiment(0, "INFLAME", 0), experiment(1, "BASH", 0)])
    assert p[0] < -4 and p[1] > 0
    model.save(tmp_path / "e")
    assert np.allclose(EffectModel.load(tmp_path / "e").predict(exps[:3]), model.predict(exps[:3]), atol=1e-4)


def test_a_quest_card_is_rebuilt_as_a_dead_card():
    run = run_of(before(), ["SPOILS_MAP", "DOWSING", "BYRDONIS_EGG", "BASH"])
    assert [c["id"] for c in run.deck] == ["SPOILS_MAP", "DOWSING", "BYRDONIS_EGG", "BASH"]
    exp = dict(state(deck=STARTER + ["SPOILS_MAP", "DOWSING"]), i=1, change={"op": "remove", "card": "DOWSING"})
    assert not job((exp, 1, 5)).get("error")


def test_a_lost_fight_is_graded_by_the_enemy_hp_left():
    won = {"won": True, "cost": 12.0, "progress": None}
    near, wipe = {"won": False, "cost": 60.0, "progress": 0.9}, {"won": False, "cost": 60.0, "progress": 0.0}
    assert score(won, 60) == 12.0
    assert abs(score(near, 60) - 66.0) < 1e-9 and score(wipe, 60) == 120.0
    assert score(near, 60, "cost") == 60.0


def test_an_experiment_stays_aligned_for_the_whole_fight(monkeypatch):
    import agents.strategy.experiments as experiments
    seen = []
    real = experiments.mcts_fight
    def spy(sim, *args, **kwargs):
        real(sim, *args, **kwargs)
        seen.append((sim.combat_state.player.aligned_shuffle, sim.combat_state.player.aligned_shuffles))
    monkeypatch.setattr(experiments, "mcts_fight", spy)
    exp = dict(state(), i=0, change={"op": "add", "card": "INFLAME"})
    out = job((exp, 1, 5, True))
    assert out["aligned"] and len(seen) == 2
    assert all(seed == out["reps"][0]["seed"] and n >= 1 for seed, n in seen)
    job((exp, 1, 5, False))
    assert seen[-1][0] is None


def test_variants_change_up_to_max_cards_and_share_a_source_seed():
    from agents.strategy.variants import changes_for, design, job
    r = random.Random(0)
    for _ in range(50):
        deck, changes = changes_for(STARTER, r, 4)
        assert len(changes) <= 4 and len(deck) == len(STARTER) + sum(1 if c["op"] == "add" else -1 for c in changes)
    vs = design([state(i) for i in range(3)], 10, 4, 1)
    assert len(vs) == 10 and len({v["source"] for v in vs[:4]}) == 1 and design([state(i) for i in range(3)], 10, 4, 1) == vs
    a, b = job((vs[0], 5)), job((vs[1], 5))
    assert a["game_seed"] == b["game_seed"] and a["seed"] == int(vs[0]["source"].split("/")[0])
    assert {"won", "hp_after", "turns", "base_deck", "changes"} <= set(a) and a["before"]["deck"] == vs[0]["deck"]
