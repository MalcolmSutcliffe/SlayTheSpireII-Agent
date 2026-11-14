"""The opening the sim builds for a fight (start-of-combat relics, Innate cards) against the first state the game sent, for every captured fight."""
import json
from pathlib import Path

import pytest

from agents.verify_opening import opening_diffs
from sts2_lite import rng
from sts2_lite.relic.combat_start import undo_enemy_effects

RUNS = Path(__file__).resolve().parents[3] / "data" / "runs"
# openings the engine does not reproduce yet: a card or status the game adds at the start of the fight that is not modelled
KNOWN_GAPS = {"run2/f13", "run2/f17", "run3/f7", "run7/f48"}


def captures():
    for path in sorted(RUNS.rglob("f*_r1_*.json")):
        state = json.loads(path.read_text())
        if state.get("decision") == "combat_play" and state.get("round") == 1 and "player" in state:
            yield path, state


def known_gap(path : Path) -> bool:
    text = path.as_posix()
    return any(gap.split("/")[0] in text and f"/{gap.split('/')[1]}_" in text for gap in KNOWN_GAPS)


@pytest.mark.parametrize("path, state", list(captures()), ids=lambda value: value.name if isinstance(value, Path) else "")
def test_opening_matches_the_game(path, state):
    if known_gap(path):
        pytest.skip("known engine gap")
    rng.seed(1)
    diffs, predicted, actual = opening_diffs(state)
    assert diffs == []


def test_undo_enemy_effects_takes_marbles_and_mask_off():
    enemies = [{"hp": 20, "max_hp": 30, "status": [{"id": "VULNERABLE_POWER", "amount": 1}, {"id": "WEAK_POWER", "amount": 1}, {"id": "STRENGTH_POWER", "amount": 3}]}]
    undo_enemy_effects(enemies, [{"id": "BAG_OF_MARBLES"}, {"id": "RED_MASK"}])
    assert [power["id"] for power in enemies[0]["status"]] == ["STRENGTH_POWER"]
