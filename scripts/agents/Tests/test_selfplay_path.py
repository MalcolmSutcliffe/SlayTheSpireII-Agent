import pytest

from agents.selfplay.run import play_run


def test_the_score_path_plays_a_whole_run_the_same_way_twice():
    a, b = play_run(3, "rarity", c=0, epsilon=0, path="score"), play_run(3, "rarity", c=0, epsilon=0, path="score")
    assert a["outcome"]["rooms_cleared"] > 0 and [r["room"] for r in a["rooms"]] == [r["room"] for r in b["rooms"]]


def test_an_unknown_path_is_refused():
    with pytest.raises(ValueError):
        play_run(3, "rarity", path="greedy")
