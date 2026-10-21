from enum import Enum, auto

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

STATUS_BEHAVIOURS : dict[StatusId, StatusBehaviour]= {
    StatusId.STRENGTH : StatusBehaviour.STATIC,
    StatusId.DEXTERITY : StatusBehaviour.STATIC,
    StatusId.THORNS : StatusBehaviour.STATIC,
    StatusId.SUCK : StatusBehaviour.STATIC,
    StatusId.SHRINK : StatusBehaviour.STATIC,
    StatusId.RAVENOUS : StatusBehaviour.STATIC,
    StatusId.TERRITORIAL : StatusBehaviour.STATIC,
    StatusId.CRIMSON_MANTLE : StatusBehaviour.STATIC,
    StatusId.FREE_ATTACK : StatusBehaviour.STATIC,
    StatusId.INFESTED : StatusBehaviour.STATIC,
    StatusId.SLIPPERY : StatusBehaviour.STATIC,
    StatusId.RITUAL : StatusBehaviour.STATIC,
    StatusId.SKITTISH : StatusBehaviour.STATIC,
    StatusId.SHRIEK : StatusBehaviour.STATIC,
    StatusId.VIGOR : StatusBehaviour.STATIC,
    StatusId.SMOGGY : StatusBehaviour.STATIC,
    StatusId.MINION : StatusBehaviour.STATIC,
    StatusId.STEAM_ERUPTION : StatusBehaviour.STATIC,
    StatusId.WEAK : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.VULNERABLE : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.FRAIL : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.PLATING : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.SLOW : StatusBehaviour.RESET_TO_ZERO,
}

class Status:
    status_id : StatusId
    amount : int
    behavior : StatusBehaviour


    def __init__(self, status_id : StatusId, amount : int):
        self.status_id = status_id
        self.amount = amount
        self.behavior = STATUS_BEHAVIOURS[status_id]

    @classmethod
    def from_dict(cls, status : dict):
        return cls(StatusId[status["id"][:-6]], status["amount"])

    @classmethod
    def deepcopy(cls, status : Status):
        return cls(status.status_id, status.amount)
