from agents.Tests.test_strength_model import BASE, synthetic
from agents.selfplay.choosers import Explorer, Counts
from agents.strategy.card_chooser import StrengthChooser
from agents.strategy.fight_model import Vocab
from agents.strategy.strength_model import StrengthModel, context_columns, describe, group_index

SNAP = {"act": 1, "floor": 5, "ascension": 0, "boss": "THE_KIN_BOSS", "hp": 60, "max_hp": 80, "gold": 0, "deck": list(BASE), "relics": [], "potions": []}


def model():
    fs = synthetic(600, 6)
    for f in fs:                     # the synthetic decks' extra cards count as random adds
        f["changes"] = [{"op": "add", "card": c} for c in f["before"]["deck"][len(BASE):]]
    vocab = Vocab.build(fs, 1)
    m = StrengthModel(vocab, context_columns(vocab), group_index(fs))
    m.fit(m.data(fs), steps=600, l2={"v": 0.1, "vu": 0.1})
    describe(m, fs)
    return m


def test_it_takes_the_helpful_card_and_skips_the_harmful_one():
    m = model()
    ch = StrengthChooser(m)
    s = ch.scores(SNAP, [{"id": "INFLAME"}, {"id": "CLUMSY"}])
    assert s[0] > s[2] > s[1]                       # Inflame saves HP, skipping is 0, Clumsy costs HP
    pick, rec = Explorer(ch, Counts(), c=0, epsilon=0).pick(SNAP, [{"id": "CLUMSY"}])
    assert rec["chosen"] == "SKIP"


def test_a_card_never_added_at_random_scores_as_a_card_of_no_value():
    m = model()
    m.randomized.pop("INFLAME")
    ch = StrengthChooser(m)
    s = ch.savings(SNAP, ["INFLAME", "SOME_UNKNOWN_CARD"])
    assert abs(s[0] - s[1]) < 1e-9


def test_the_targets_are_the_boss_and_the_act_s_elites():
    m = model()
    m.elites = {"THE_KIN_BOSS": ["A_ELITE", "B_ELITE"], "act:2": ["C_ELITE"]}
    t = StrengthChooser(m, elite_weight=1.0).targets(SNAP)
    assert [(f["encounter"], f["kind"], w) for f, w in t] == [("THE_KIN_BOSS", "Boss", 1.0), ("A_ELITE", "Elite", 0.5), ("B_ELITE", "Elite", 0.5)]
    t = StrengthChooser(m).targets(dict(SNAP, act=2, boss="UNSEEN_BOSS"))
    assert [f["encounter"] for f, _ in t] == ["UNSEEN_BOSS", "C_ELITE"]
