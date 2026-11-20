import random

import pytest

from agents.strategy.synergy import cells, design, interactions, parse_blocks

STARTER = ["STRIKE_IRONCLAD"] * 5 + ["DEFEND_IRONCLAD"] * 4 + ["BASH"]


def state(k, deck=STARTER, kind="Elite"):
    return {"source": f"{k}/3/BYRDONIS_ELITE", "encounter": "BYRDONIS_ELITE", "kind": kind,
            "before": {"act": 1, "floor": 5, "ascension": 0, "hp": 60, "max_hp": 80, "gold": 0, "deck": list(deck), "relics": [], "potions": [], "room": kind}}


def test_blocks_parse_with_their_controls_and_reject_unknown_cards():
    b = parse_blocks("BARRICADE:BODY_SLAM,~POMMEL_STRIKE; INFLAME:TWIN_STRIKE")
    assert b[0] == {"anchor": "BARRICADE", "partners": ["BODY_SLAM", "POMMEL_STRIKE"], "controls": ["POMMEL_STRIKE"]}
    assert b[1]["anchor"] == "INFLAME" and b[1]["controls"] == []
    with pytest.raises(ValueError):
        parse_blocks("BARRICADE:NOT_A_CARD")


def test_the_design_plays_every_cell_on_decks_without_the_block_s_cards():
    blocks = parse_blocks("BARRICADE:BODY_SLAM,SHRUG_IT_OFF")
    states = [state(k) for k in range(5)] + [state(9, STARTER + ["BODY_SLAM+"])]
    plan = design(states, blocks, 4, seed=1)
    assert len(plan) == 4 * len(cells(blocks[0])) == 4 * 6
    assert all("9/" not in v["source"] for v in plan)          # its deck already holds a partner
    unit = [v for v in plan if v["unit"] == "0/0"]
    assert {(v["a"], v["b"]) for v in unit} == set(cells(blocks[0]))
    assert len({v["source"] for v in unit}) == 1
    both = next(v for v in unit if v["a"] and v["b"] == "BODY_SLAM")
    assert both["deck"] == STARTER + ["BARRICADE", "BODY_SLAM"] and [c["card"] for c in both["changes"]] == ["BARRICADE", "BODY_SLAM"]
    assert design(states, blocks, 4, seed=1) == plan and [v["i"] for v in plan] == list(range(len(plan)))


def test_interactions_recover_a_synergy_and_its_absence():
    blocks = parse_blocks("BARRICADE:BODY_SLAM,~POMMEL_STRIKE")
    plan = design([state(k) for k in range(300)], blocks, 300, seed=2)
    r = random.Random(3)
    rows = []
    offset = {}
    for v in plan:
        base = offset.setdefault(v["unit"], r.uniform(10, 40))
        c = base + (1.0 if v["a"] else 0) + (2.0 if v["b"] == "BODY_SLAM" else 0) - (5.0 if v["a"] and v["b"] == "BODY_SLAM" else 0) + r.gauss(0, 3)
        rows.append(dict(v, before=dict(v["before"], deck=v["deck"]), won=True, dead=False, hp_after=60 - c))
    res = interactions(rows)
    syn, ctl = res[("BARRICADE", "BODY_SLAM")], res[("BARRICADE", "POMMEL_STRIKE")]
    assert syn["n"] == 300 and abs(syn["effect"] + 5) < 4 * syn["se"] and abs(ctl["effect"]) < 4 * ctl["se"]
    assert abs(syn["main_a"] - 1) < 1 and abs(syn["main_b"] - 2) < 1
    rows = [x for x in rows if not (x["unit"] == "0/0" and x["a"] is None and x["b"] is None)]      # an incomplete unit is left out
    assert interactions(rows)[("BARRICADE", "BODY_SLAM")]["n"] == 299


def test_basic_partners_and_reps():
    blocks = parse_blocks("RUPTURE:STRIKE_IRONCLAD,DEFEND_IRONCLAD")
    plan = design([state(k) for k in range(5)], blocks, 3, seed=1, reps=2)
    assert len(plan) == 3 * 2 * 6                       # starter decks hold Strikes and Defends and still qualify
    assert {v["unit"] for v in plan} == {f"0/{j}/{r}" for j in range(3) for r in range(2)}
    one = next(v for v in plan if v["a"] and v["b"] == "STRIKE_IRONCLAD")
    assert one["deck"].count("STRIKE_IRONCLAD") == 6
