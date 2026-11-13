from __future__ import annotations
"""Act 3 at Ascension 10 has two bosses: when the first falls the game goes straight into the second, and the sim's finished fight is not compared with it."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from agent_tester import chained_into_new_fight

IDS = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "double_boss_ids.json")))


def test_the_next_boss_after_a_predicted_win_is_a_new_fight():
    assert chained_into_new_fight({"predicted_over": True, "before": IDS["before"]}, IDS["after"])


def test_the_same_enemies_are_the_same_fight():
    assert not chained_into_new_fight({"predicted_over": True, "before": IDS["before"]}, IDS["before"])


def test_a_fight_the_sim_did_not_end_is_compared_as_usual():
    assert not chained_into_new_fight({"predicted_over": False, "before": IDS["before"]}, IDS["after"])
    assert not chained_into_new_fight(None, IDS["after"])
