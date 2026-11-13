"""Monsters that appear in the middle of a fight (summoned, laid, called for backup): their hit points, first move and statuses."""
from __future__ import annotations

from sts2_lite.status import StatusId
from sts2_lite.enemy_moves.core import tough


# monsters that appear mid-fight: (min hp, max hp, tough min hp, tough max hp)
SPAWN_HP = {
    "SNEAKY_GREMLIN": (10, 14, 11, 15),
    "FAT_GREMLIN": (13, 17, 14, 18),
    "GAS_BOMB": (7, 7, 8, 8),
    "TWO_TAILED_RAT": (17, 21, 18, 22),
    "WRIGGLER": (17, 21, 18, 22),
    "EYE_WITH_TEETH": (6, 6, 6, 6),
    "PARAFRIGHT": (21, 21, 21, 21),
    "TOUGH_EGG": (14, 18, 15, 19),
    "AXEBOT": (70, 78, 76, 86),
    "ZAPBOT": (18, 23, 19, 24),
    "STABBOT": (18, 23, 19, 24),
    "NOISEBOT": (18, 23, 19, 24),
    "GUARDBOT": (16, 20, 17, 21),
}

# the move a summoned monster starts on (default SPAWNED) and the statuses it starts with
SPAWN_MOVE = {"GAS_BOMB": "EXPLODE", "TWO_TAILED_RAT": "SCRATCH", "EYE_WITH_TEETH": "DISTRACT", "PARAFRIGHT": "SLAM", "TOUGH_EGG": "HATCH", "AXEBOT": "BOOT_UP",
              "ZAPBOT": "ZAP", "STABBOT": "STAB", "GUARDBOT": "GUARD", "NOISEBOT": "NOISE"}
SPAWN_STATUS = {"GAS_BOMB": ((StatusId.MINION, 1),), "EYE_WITH_TEETH": ((StatusId.ILLUSION, 1), (StatusId.MINION, 1)),
                "PARAFRIGHT": ((StatusId.ILLUSION, 1), (StatusId.MINION, 1)),
                "TOUGH_EGG": ((StatusId.HATCH, 2), (StatusId.MINION, 1)),
                "ZAPBOT": ((StatusId.MINION, 1), (StatusId.HIGH_VOLTAGE, 2)),
                "STABBOT": ((StatusId.MINION, 1),), "GUARDBOT": ((StatusId.MINION, 1),), "NOISEBOT": ((StatusId.MINION, 1),)}      # laid during the enemy turn, so it counts down from 2

# summoner -> (summoning move, summoned monster, slot): the monster is missing from a bridge
# state when it has been killed, and returns at the end of the enemy turn
SUMMONS = {"FOGMOG": ("ILLUSION", "EYE_WITH_TEETH", 0),
           "THE_OBSCURA": ("ILLUSION", "PARAFRIGHT", 0)}


