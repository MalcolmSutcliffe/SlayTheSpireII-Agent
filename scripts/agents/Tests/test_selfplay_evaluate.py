from agents.selfplay.evaluate import mean_se, report


def result(chooser, seed, rooms, chosen=("BASH",)):
    return {"chooser": chooser, "seed": seed, "pilot": "rollout", "outcome": {"rooms_cleared": rooms, "act": 1 + rooms // 17, "won": False},
            "picks": [{"act": 1, "offered": ["BASH"], "chosen": c} for c in chosen]}


def test_mean_and_standard_error():
    m, se = mean_se([1, 2, 3, 4])
    assert m == 2.5 and abs(se - (5 / 3 / 4) ** 0.5) < 1e-9


def test_the_report_pairs_the_seeds():
    results = [result("rarity", s, 10 + s % 3) for s in range(30)] + [result("model:x", s, 13 + s % 3, ("INFLAME",)) for s in range(30)]
    text = report(results, ["rarity", "model:x"])
    assert "model:x vs rarity on the same 30 seeds: +3.00 ± 0.00" in text and "better" in text.replace("no clear", "")
    assert "INFLAME 30" in text


def test_a_seed_that_timed_out_is_left_out_for_every_chooser():
    results = [result("rarity", s, 10) for s in range(5)] + [result("model:x", s, 12) for s in range(5)]
    results[7]["outcome"]["cause"] = "engine error: timed out after 900 s"          # model:x on seed 2
    text = report(results, ["rarity", "model:x"])
    assert "on the same 4 seeds" in text and "left out: 1 seed(s) where a run timed out: 2" in text
