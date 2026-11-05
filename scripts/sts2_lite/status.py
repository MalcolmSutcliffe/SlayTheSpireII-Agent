from __future__ import annotations
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from sts2_lite.creature import Creature
    from sts2_lite.combat import CombatSimulator

from enum import Enum, auto

from sts2_lite.events import EventType

class StatusId(Enum):
    STRENGTH = auto()
    WEAK = auto()
    VULNERABLE = auto()
    FRAIL = auto()
    DEXTERITY = auto()
    SHRINK = auto()
    THORNS = auto()
    RAVENOUS = auto()
    SUCK = auto()
    SLOW = auto()
    TERRITORIAL = auto()
    CRIMSON_MANTLE = auto()
    INFESTED = auto()
    FREE_ATTACK = auto()
    SLIPPERY = auto()
    RITUAL = auto()
    PLATING = auto()
    SKITTISH = auto()
    SHRIEK = auto()
    VIGOR = auto()
    SMOGGY = auto()
    MINION = auto()
    STEAM_ERUPTION = auto()

class StatusBehaviour(Enum):
    STATIC = auto()
    DECREASE_BY_ONE = auto()
    RESET_TO_ZERO = auto()

STATUS_BEAVIOURS : dict[StatusId, StatusBehaviour] = {
    StatusId.STRENGTH : StatusBehaviour.STATIC,
    StatusId.WEAK : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.VULNERABLE : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.FRAIL : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.DEXTERITY : StatusBehaviour.STATIC,
    StatusId.SHRINK : StatusBehaviour.STATIC,
    StatusId.THORNS : StatusBehaviour.STATIC,
    StatusId.RAVENOUS : StatusBehaviour.STATIC,
    StatusId.SUCK : StatusBehaviour.STATIC,
    StatusId.SLOW : StatusBehaviour.RESET_TO_ZERO,
    StatusId.TERRITORIAL : StatusBehaviour.STATIC,
    StatusId.CRIMSON_MANTLE : StatusBehaviour.STATIC,
    StatusId.INFESTED : StatusBehaviour.STATIC,
    StatusId.FREE_ATTACK : StatusBehaviour.STATIC,
    StatusId.SLIPPERY : StatusBehaviour.STATIC,
    StatusId.RITUAL : StatusBehaviour.STATIC,
    StatusId.PLATING : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.SKITTISH : StatusBehaviour.STATIC,
    StatusId.SHRIEK : StatusBehaviour.STATIC,
    StatusId.VIGOR : StatusBehaviour.STATIC,
    StatusId.SMOGGY : StatusBehaviour.STATIC,
    StatusId.MINION : StatusBehaviour.STATIC,
    StatusId.STEAM_ERUPTION : StatusBehaviour.STATIC,
}

class StatusInstance:
    status_id : StatusId
    amount : int
    behaviour : StatusBehaviour

    def __init__(self, status_id : StatusId, amount : int):
        self.status_id = status_id
        self.amount = amount
        self.behaviour = STATUS_BEAVIOURS[status_id]

    @classmethod
    def from_dict(cls, status : dict):
        return cls(StatusId[status["id"][:-6]], status["amount"])

    @classmethod
    def deepcopy(cls, status : StatusInstance):
        return cls(status.status_id, status.amount)


# ---
# Event handlers: handler(combat, owner, amount, *event_args)
# ---
def _ritual_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    owner.apply_status(StatusId.STRENGTH, amount)

def _territorial_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    owner.apply_status(StatusId.STRENGTH, 1)

def _shrink_on_creature_killed(combat : CombatSimulator, owner : Creature, amount : int, killed : Creature):
    # Shrink lasts while the beetle that applied it lives
    if killed.enemy_id.startswith("SHRINKER_BEETLE"):
        del owner.status[StatusId.SHRINK]

STATUS_HANDLERS : dict[tuple[StatusId, EventType], Callable] = {
    (StatusId.RITUAL, EventType.ENEMY_TURN_END) : _ritual_on_enemy_turn_end,
    (StatusId.TERRITORIAL, EventType.ENEMY_TURN_END) : _territorial_on_enemy_turn_end,
    (StatusId.SHRINK, EventType.CREATURE_KILLED) : _shrink_on_creature_killed,
}
