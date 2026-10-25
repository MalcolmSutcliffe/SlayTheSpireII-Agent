from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator

from enum import Enum, auto

from sts2_lite.creature import Creature
from sts2_lite.status import StatusInstance, StatusId

class EnemyId(Enum):
    SEAPUNK = auto()

class Enemy(Creature):
    enemy_id : EnemyId
    attack_damage : int
    num_attacks: int = 1

    def __init__(self):
        super().__init__()

    @classmethod
    def from_dict(cls, enemy: dict):
        e = Enemy()
        e.max_hp = enemy["max_hp"]
        e.current_hp = enemy["hp"]
        e.block = enemy["block"]
        e.enemy_id = enemy["entity_id"]
        e.attack_damage = 0
        for intent in enemy["intents"]:
            if intent["type"] == "Attack":
                label = intent["label"].split("x")
                e.attack_damage = int(label[0])
                if len(label) > 1:
                    e.num_attacks = int(label[1])
                else:
                    e.num_attacks = 1
                
        e.status = {}
        for s in enemy["status"]:
            e.status[StatusId[s["id"][:-6]]] = StatusInstance.from_dict(s)

        if StatusId.MINION in e.status:
            e.is_minion = True
        return e

    @classmethod
    def deepcopy(cls, enemy : Enemy) -> Enemy:
        new_e = cls()
        new_e.max_hp = enemy.max_hp
        new_e.current_hp = enemy.current_hp
        new_e.block = enemy.block
        new_e.is_minion = enemy.is_minion
        new_e.enemy_id = enemy.enemy_id
        new_e.status = {}
        for s in enemy.status.values():
            new_e.status[s.status_id] = StatusInstance.deepcopy(s)
        new_e.attack_damage = enemy.attack_damage
        new_e.num_attacks = enemy.num_attacks
        return new_e

    def perform_turn(self, combat : CombatSimulator):
        for i in range(self.num_attacks):
            combat.combat_state.player.apply_damage(self.attack_damage)
        if StatusId.TERRITORIAL in self.status:
            self.apply_status(StatusId.STRENGTH, 1)
        if StatusId.RITUAL in self.status:
            self.apply_status(StatusId.STRENGTH, self.status[StatusId.RITUAL].amount)

    def readable(self) -> str:
        output = ""
        output += self.enemy_id + ":\n"
        output += super().readable()
        output += "\nAttacking for: " + str(self.attack_damage) + "x" + str(self.num_attacks)
        return output