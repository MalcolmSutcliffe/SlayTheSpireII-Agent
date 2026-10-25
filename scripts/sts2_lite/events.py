### File for all "Events" that relics and powers can "hook" into
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator, CombatState
    from sts2_lite.creature import Creature

from enum import Enum, auto

from sts2_lite.card import Card

class EventType(Enum):
    MODIFY_DAMAGE_ADDITIVE = auto()
    MODIFY_DAMAGE_MULTIPLICITIVE = auto()
    MODIFY_BLOCK_ADDITIVE = auto()
    MODIFY_BLOCK_MULTIPLICITIVE = auto()
    END_TURN = auto()
    CARD_PLAYED = auto()
    CREATURE_KILLED = auto()

class Listener:
    uid : int
    event : EventType
    on_event : function

    def __init__(self, uid : int, event : EventType, on_event : function):
        self.uid = uid
        self.event = event
        self.on_event = on_event

class EventManager:
    _listeners : dict[EventType, list[Listener]]
    _uid_gen : int = 0

    def __init__(self):
        self._listeners = {}
        self._uid_gen = 0

    def add_listener(self, event : EventType, listener : function):
        new_listener = Listener(self._generate_uid(), event, listener)
        self._listeners[event].append(new_listener)

    def remove_listener(self, event : EventType, id : int):
        for l in self._listeners[event]:
            if l.uid == id:
                self._listeners[event].remove(l)
                del l
                return
    
    # modifiers:
    def modify_damage(self, initial_damage : int, owner : Creature, target : Creature) -> int:
        damage = initial_damage
        
        # additive
        for l in self._listeners[EventType.MODIFY_DAMAGE_ADDITIVE]:
            damage = l(damage, owner, target)

        # multiplicitive
        for l in self._listeners[EventType.MODIFY_DAMAGE_MULTIPLICITIVE]:
            damage = l(damage, owner, target)

        return damage

    def modify_block(self, initial_block : int, target: Creature) -> int:
        block = initial_block

        # additive
        for l in self._listeners[EventType.MODIFY_BLOCK_ADDITIVE]:
            block = l(block, target)

        # multiplicitive
        for l in self._listeners[EventType.MODIFY_BLOCK_MULTIPLICITIVE]:
            block = l(block, target)

        return block
    
    # FIRE
    def on_end_turn(self):
        for f in self._listeners[EventType.END_TURN]:
            f()

    def on_card_played(self, card : Card):
        for f in self._listeners[EventType.CARD_PLAYED]:
            f(card)

    def _generate_uid(self) -> int:
        self._uid_gen += 1
        return self._uid_gen
