from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator, CombatState

from sts2_lite.status import StatusInstance, StatusId, is_debuff

class Creature:
    max_hp : int
    current_hp : int
    block : int
    status : dict[StatusId, StatusInstance]
    is_minion : bool
    has_been_attacked_this_turn : bool
    lost_hp_this_turn : bool

    def __init__(self, max_hp=1, current_hp=1, block=0, status=None, is_minion=False):
        self.max_hp=max_hp
        self.current_hp=current_hp
        self.block=block
        self.status = {} if status is None else status
        self.is_minion=is_minion
        self.has_been_attacked_this_turn = False
        self.lost_hp_this_turn = False
        self.hp_loss_events = 0     # running total of times hit points were lost

    plating_at_turn_start = True    # the player's Plating pays out at end of turn instead

    def status_amount(self, status_id : StatusId) -> int:
        s = self.status.get(status_id)
        return s.amount if s is not None else 0

    def lose_hp(self, hp_loss : int):
        if hp_loss > 0:
            self.lost_hp_this_turn = True
            self.hp_loss_events += 1
        self.current_hp -= hp_loss
        if self.current_hp <= 0:
            self.die()

    def turn_start(self):
        if StatusId.BARRICADE not in self.status:
            self.block = 0
        self.has_been_attacked_this_turn = False
        self.lost_hp_this_turn = False
        if StatusId.PLATING in self.status and self.plating_at_turn_start:
            self.apply_block(self.status[StatusId.PLATING].amount)

    def turn_end(self):
        pass

    def apply_attack_damage(self, damage :int, sender : Creature, hits : int = 1):
        first_attack = not self.has_been_attacked_this_turn
        self.has_been_attacked_this_turn = True
        for _ in range(hits):
            if sender.current_hp <= 0:
                break
            if StatusId.THORNS in self.status:
                sender.apply_damage(self.status[StatusId.THORNS].amount)
            self.apply_damage(damage)
            if StatusId.FLAME_BARRIER in self.status:       # after the hit, unlike Thorns
                sender.apply_damage(self.status[StatusId.FLAME_BARRIER].amount)
        if first_attack and StatusId.SKITTISH in self.status:
            self.apply_block(self.status[StatusId.SKITTISH].amount)

    def apply_damage(self, damage: int):
        if damage <= 0:
            return

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
            if self.status[StatusId.SLIPPERY].amount == 0:
                del self.status[StatusId.SLIPPERY]
        
        self.current_hp -= damage
        self.lost_hp_this_turn = True
        self.hp_loss_events += 1
        
        if self.current_hp <= 0:
            self.die()
        elif StatusId.PLOW in self.status and self.current_hp <= self.status[StatusId.PLOW].amount:
            self.lose_plow()

    def lose_plow(self):
        """Plow breaks the first time hit points reach its amount: Strength is lost and the creature is stunned."""
        del self.status[StatusId.PLOW]
        self.status.pop(StatusId.STRENGTH, None)
        self.stun()

    def stun(self):
        pass

    def apply_block(self, block: int):
        self.block += block

    def apply_status(self, status: StatusId, amount : int, bypass_artifact : bool = False):
        if not bypass_artifact and StatusId.ARTIFACT in self.status and is_debuff(status, amount):
            self.status[StatusId.ARTIFACT].amount -= 1      # Artifact negates the whole debuff
            if self.status[StatusId.ARTIFACT].amount <= 0:
                del self.status[StatusId.ARTIFACT]
            return
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