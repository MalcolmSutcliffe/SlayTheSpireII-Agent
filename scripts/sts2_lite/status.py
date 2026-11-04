from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.status import StatusInstance
    from sts2_lite.creature import Creature
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.events import EventType

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

class StatusInstance:
    status_id : StatusId
    amount : int
    owner : Creature

    def __init__(self, status_id : StatusId, amount : int, owner: Creature):
        self.status_id = status_id
        self.amount = amount
        self.owner = owner

    def register_events(combat : CombatSimulator):
        pass

    @classmethod
    def from_dict(cls, status : dict):
        return cls(StatusId[status["id"][:-6]], status["amount"])

    @classmethod
    def deepcopy(cls, status : StatusInstance):
        return cls(status.status_id, status.amount)


# ---
# Status classes
# ---
class Strength(StatusInstance):
    def __init__(self, amount :int, owner : Creature):
        super().__init__(StatusId.STRENGTH, amount, owner)

    def register_event(self, combat : CombatSimulator):
        combat.event_manager.add_listener(EventType.MODIFY_DAMAGE_ADDITIVE, self.damage_modifier)

    def damage_modifier(self, damage : int, owner : Creature, target : Creature):
        if self.owner == owner:
            return damage + self.amount

# ---
# Status factory
# --- 
def create_status(status_id : StatusId, amount : int, owner : Creature, combat : CombatSimulator) -> StatusInstance:
    return STATUS_GENERATORS[status_id](amount, owner, combat)

def create_strength(amount : int, owner : Creature) -> Strength:
    return Strength(amount, owner)

STATUS_GENERATORS : dict[StatusId, function] = {
    StatusId.STRENGTH : create_strength
}

