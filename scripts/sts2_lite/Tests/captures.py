"""Loads saved bridge states: data/<act>/<enemy>/<name>.json"""
import json
from pathlib import Path

from sts2_lite.combat import CombatState

DATA = Path(__file__).parent / "data"
ACT1 = "act1_overgrowth"
HIVE = "act2_hive"

def raw(enemy : str, name : str, act : str = ACT1) -> dict:
    return json.loads((DATA / act / enemy / f"{name}.json").read_text())

def load(enemy : str, name : str, act : str = ACT1) -> CombatState:
    return CombatState.from_dict(raw(enemy, name, act))
