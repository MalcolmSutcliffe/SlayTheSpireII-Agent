from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator, CombatState

from sts2_lite.status import StatusInstance, StatusId

class Creature:
    max_hp : int
    current_hp : int
    block : int
    status : dict[StatusId, StatusInstance] = {}
    is_minion : bool
    has_been_attacked_this_turn : bool

    def __init__(self, max_hp=1, current_hp=1, block=0, status = {}, is_minion=False):
        self.max_hp=max_hp
        self.current_hp=current_hp
        self.block=block
        self.status=status
        self.is_minion=is_minion
        self.has_been_attacked_this_turn = False

    def register_events(self, combat : CombatSimulator):
        for s in self.status.values():
            s.register_events(combat)

    def lose_hp(self, hp_loss : int):
        self.current_hp -= hp_loss
        if self.current_hp <= 0:
            self.die()

    def turn_start(self):
        self.block = 0
        self.has_been_attacked_this_turn = False
        if StatusId.PLATING in self.status:
            self.apply_block(self.status[StatusId.PLATING].amount)

    def turn_end(self):
        pass

    def apply_attack_damage(self, damage :int, sender : Creature):
        if StatusId.THORNS in self.status:
            sender.apply_damage(self.status[StatusId.THORNS].amount)
        self.apply_damage(damage)

    def apply_damage(self, damage: int):
        if self.block > 0:
            if self.block >= damage:
                self.block -= damage
                return
            else:
                damage -= self.block
                self.block = 0
        if StatusId.SLIPPERY in self.status and self.status[StatusId.SLIPPERY].amount > 0:
            damage = 1
            self.status[StatusId.SLIPPERY].amount -= 1
        self.current_hp -= damage
        if self.current_hp <= 0:
            self.die()
        if StatusId.SKITTISH in self.status and self.has_been_attacked_this_turn == False:
            self.apply_block(self.status[StatusId.SKITTISH].amount)
        self.has_been_attacked_this_turn = True

    def apply_block(self, block: int):
        self.block += block

    def apply_status(self, status: StatusId, amount : int):
        if status in self.status:
            self.status[status].amount += amount
        else:
            self.status[status] = StatusInstance(status, amount)

    def die(self):
        self.current_hp = 0

    def readable(self) -> str:
        output = ""
        output += "max_hp : " + str(self.max_hp) + "\n"
        output += "current_hp : " + str(self.current_hp) + "\n"
        output += "block : " + str(self.block) + "\n"
        if len(self.status.keys()) > 0:
            output += "status : \n"
            for s in self.status.values():
                output += str(s.status_id) + " " + str(s.amount)
        return output