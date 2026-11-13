"""Loads saved bridge states: data/enemies/<act>/<enemy>/<name>.json"""
import json

from data_paths import ENEMIES
from sts2_lite.combat import CombatState

DATA = ENEMIES
ACT1 = "act1_overgrowth"
HIVE = "act2_hive"
GLORY = "act3_glory"
UNDERDOCKS = "act1_underdocks"

def raw(enemy : str, name : str, act : str = ACT1) -> dict:
    return json.loads((DATA / act / enemy / f"{name}.json").read_text())

def load(enemy : str, name : str, act : str = ACT1) -> CombatState:
    return CombatState.from_dict(raw(enemy, name, act))
