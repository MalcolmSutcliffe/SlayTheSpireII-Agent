from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import Combat

from enum import Enum, auto

from sts2_lite.status import StatusId


class CardType(Enum):
    Power = auto()
    Skill = auto()
    Attack = auto()

class CardId(Enum):
    STRIKE_IRONCLAD = auto()
    DEFEND_IRONCLAD = auto()
    BASH = auto()

class TargetType(Enum):
    AnyEnemy = auto()
    AllEnemies = auto()
    Self = auto()

class Card:
    card_id : CardId
    type : CardType
    energy_cost : int | str
    target_type : TargetType
    is_upgraded : bool
    
    def __init__(self, card : dict):
        self.card_id = CardId[card["id"]]
        self.type = card["type"]
        if card["cost"] == "X":
            self.energy_cost = card["cost"]
        else:
            self.energy_cost = int(card["cost"])
        self.is_upgraded = card["is_upgraded"]
        self.target_type = TargetType[card["target_type"]]

    def play_card(self, combat : Combat, target_index : int) -> bool:
        energy= combat.combat_state.energy
        
        if self.energy_cost == "X":
            combat.combat_state.energy = 0
            return GET_CARD_FUNCTION[self.card_id](combat, target_index, self.is_upgraded, energy)
        else:
            combat.combat_state.energy -= self.energy_cost
            return GET_CARD_FUNCTION[self.card_id](combat, target_index, self.is_upgraded)
            
    def can_play_card(self, combat : Combat, target_index):
        if type(self.energy_cost) is str and self.energy_cost == "X":
            return True
        if self.energy_cost <= combat.combat_state.energy:
            return True
        return False

###
### Card Functions
###

def play_strike(combat : Combat, target_index : int, is_upgraded=False) -> bool:

    if target_index >= len(combat.combat_state.enemies):
        print("Index out of bounds")
        return False
    
    damage = 6
    if is_upgraded:
        damage = 9
    
    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    damage = combat.calculate_damage(damage, owner, target)
    
    target.apply_damage(damage)
    return True

def play_defend(combat : Combat, target_index=0, is_upgraded=False):
    block = 5
    if is_upgraded:
        block = 8
    
    block = combat.calculate_block(block, combat.combat_state.player)
    combat.combat_state.player.apply_block(block)
    return True


def play_bash(combat : Combat, target_index : int, is_upgraded=False):
    if target_index >= len(combat.combat_state.enemies):
        print("Index out of bounds")
        return False
    
    damage = 8
    vuln_amount = 2
    if is_upgraded:
        damage = 10
        vuln_amount = 3
    
    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    damage = combat.calculate_damage(damage, owner, target)
    target.apply_damage(damage)
    # apply VULNERABLE status
    target.apply_status(StatusId.VULNERABLE, vuln_amount)
    return True

###
### map to get function from card id
###


GET_CARD_FUNCTION : dict[CardId, function] = {
    CardId.STRIKE_IRONCLAD : play_strike,
    CardId.DEFEND_IRONCLAD : play_defend,
    CardId.BASH : play_bash
}