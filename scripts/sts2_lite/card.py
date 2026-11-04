from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator

from enum import Enum, auto

from sts2_lite.status import StatusId


class CardType(Enum):
    Power = auto()
    Skill = auto()
    Attack = auto()
    Status = auto()

class CardId(Enum):
    STRIKE_IRONCLAD = auto()
    DEFEND_IRONCLAD = auto()
    BASH = auto()
    BLOOD_WALL = auto()
    SLIMED = auto()
    PERFECTED_STRIKE = auto()
    BREAKTHROUGH = auto()
    SHRUG_IT_OFF = auto()
    POMMEL_STRIKE = auto()
    IRON_WAVE = auto()
    THUNDERCLAP = auto()
    INFLAME = auto()
    FIGHT_ME = auto()
    TREMBLE = auto()
    CRIMSON_MANTLE = auto()
    ANGER = auto()
    INFECTION = auto()
    BLUDGEON = auto()
    UNRELENTING = auto()
    BODY_SLAM = auto()
    TWIN_STRIKE = auto()
    DAZED = auto()

class TargetType(Enum):
    AnyEnemy = auto()
    AllEnemies = auto()
    Self = auto()
    NONE = auto()

class Card:
    card_id : CardId
    name : str
    type : CardType
    energy_cost : int | str
    target_type : TargetType
    is_upgraded : bool
    is_unplayable : bool

    def __init__(self):
        pass

    @classmethod
    def from_dict(cls, card : dict):
        new_card = cls()
        new_card.card_id = CardId[card["id"]]
        new_card.type = CardType[card["type"]]
        new_card.name = card["name"]
        new_card.is_unplayable = not card["can_play"]
        if card["cost"] == "X":
            new_card.energy_cost = card["cost"]
        else:
            new_card.energy_cost = int(card["cost"])
        new_card.is_upgraded = card["is_upgraded"]
        if card["target_type"] == "None":
            new_card.target_type = TargetType.NONE
        else:
            new_card.target_type = TargetType[card["target_type"]]
        return new_card

    @classmethod
    def create_copy(cls, card : Card) -> Card:
        new_card = cls()
        new_card.card_id = card.card_id
        new_card.type = card.type
        new_card.name = card.name
        new_card.energy_cost = card.energy_cost
        new_card.target_type = card.target_type
        new_card.is_upgraded = card.is_upgraded
        new_card.is_unplayable = card.is_unplayable
        return new_card

    def play_card(self, combat : CombatSimulator, target_index : int) -> bool:
        energy= combat.combat_state.energy
        
        if self.energy_cost == "X":
            combat.combat_state.energy = 0
            return GET_CARD_FUNCTION[self.card_id](self, combat, target_index, self.is_upgraded, energy)
        else:
            if self.type == CardType.Attack and StatusId.FREE_ATTACK in combat.combat_state.player.status:
                if combat.combat_state.player.status[StatusId.FREE_ATTACK].amount > 0:
                    combat.combat_state.player.status[StatusId.FREE_ATTACK].amount -= 1
                    combat.combat_state.energy += self.energy_cost
            combat.combat_state.energy -= self.energy_cost
            return GET_CARD_FUNCTION[self.card_id](self, combat, target_index, self.is_upgraded)
            
    def can_play_card(self, combat : CombatSimulator, target_index):
        if self.is_unplayable:
            return False
        if type(self.energy_cost) is str and self.energy_cost == "X":
            return True
        if self.type == CardType.Attack and StatusId.FREE_ATTACK in combat.combat_state.player.status:
            if combat.combat_state.player.status[StatusId.FREE_ATTACK].amount > 0:
                return True
        if self.energy_cost <= combat.combat_state.energy:
            return True
        return False

###
### Card Functions
###

def play_strike(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:

    if target_index >= len(combat.combat_state.enemies):
        print("Index out of bounds")
        return False
    
    damage = 6
    if is_upgraded:
        damage = 9
    
    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    damage = combat.calculate_damage(damage, owner, target)
    
    target.apply_attack_damage(damage, owner)
    return True

def play_defend(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    block = 5
    if is_upgraded:
        block = 8
    
    block = combat.calculate_block(block, combat.combat_state.player)
    combat.combat_state.player.apply_block(block)
    return True

def play_bash(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False):
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
    target.apply_attack_damage(damage, owner)
    # apply VULNERABLE status
    target.apply_status(StatusId.VULNERABLE, vuln_amount)
    return True

def play_blood_wall(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False):
    block = 16
    if is_upgraded:
        block = 20
    
    block = combat.calculate_block(block, combat.combat_state.player)
    combat.combat_state.player.apply_block(block)
    combat.combat_state.player.lose_hp(2)
    return True

def play_slimed(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False):
    combat.combat_state.player.draw_card()
    combat.combat_state.player.exhaust_card(card)
    return True

def play_perfected_strike(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False):
    total_strikes = 0
    for card in combat.combat_state.deck:
        if "Strike" in card.name:
            total_strikes += 1
    strike_multiplier = 2
    if is_upgraded:
        strike_multiplier = 3
    damage = 6 + strike_multiplier*(total_strikes-1)

    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    damage = combat.calculate_damage(damage, owner, target)
    target.apply_attack_damage(damage, owner)
    return True

def play_breakthrough(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:

    damage = 9
    if is_upgraded:
        damage = 13
    
    owner = combat.combat_state.player
    for target in combat.combat_state.enemies:
        target = combat.combat_state.enemies[target_index]
        damage = combat.calculate_damage(damage, owner, target)
        target.apply_attack_damage(damage, owner)
    
    return True

def play_shrug_it_off(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    block = 8
    if is_upgraded:
        block = 11
    
    block = combat.calculate_block(block, combat.combat_state.player)
    combat.combat_state.player.apply_block(block)
    combat.combat_state.player.draw_cards(1)
    return True

def play_pommel_strike(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:

    if target_index >= len(combat.combat_state.enemies):
        print("Index out of bounds")
        return False
    
    damage = 9
    draw = 1
    if is_upgraded:
        damage = 10
        draw = 2
    
    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    damage = combat.calculate_damage(damage, owner, target)
    
    target.apply_attack_damage(damage, owner)
    combat.combat_state.player.draw_cards(draw)
    return True

def play_iron_wave(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:

    if target_index >= len(combat.combat_state.enemies):
        print("Index out of bounds")
        return False
    
    damage = 5
    block = 5
    if is_upgraded:
        damage = 7
        block = 7
    
    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    damage = combat.calculate_damage(damage, owner, target)
    block = combat.calculate_block(block, owner)
    
    owner.apply_block(block)
    target.apply_attack_damage(damage, owner)
    return True

def play_thunderclap(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:

    damage = 4
    if is_upgraded:
        damage = 7
    
    owner = combat.combat_state.player
    for target in combat.combat_state.enemies:
        target = combat.combat_state.enemies[target_index]
        damage = combat.calculate_damage(damage, owner, target)
        target.apply_attack_damage(damage, owner)
        target.apply_status(StatusId.VULNERABLE, 1)
    
    return True

def play_inflame(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:
    strength_amount = 2
    if is_upgraded:
        strength_amount = 3
    combat.combat_state.player.apply_status(StatusId.STRENGTH, strength_amount)
    return True

def play_fight_me(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:
    strength_amount = 3
    damage = 5
    if is_upgraded:
        strength_amount = 4
        damage = 6
    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    damage = combat.calculate_damage(damage, owner, target)
    target.apply_attack_damage(damage, owner)
    target.apply_attack_damage(damage, owner)
    owner.apply_status(StatusId.STRENGTH, strength_amount)
    target.apply_status(StatusId.STRENGTH, 1)
    return True

def play_tremble(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:
    if target_index >= len(combat.combat_state.enemies):
        print("Index out of bounds")
        return False
    
    vuln_amount = 3
    if is_upgraded:
        vuln_amount = 4
    
    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    target.apply_status(StatusId.VULNERABLE, vuln_amount)
    owner.exhaust_card(card)
    return True

def play_crimson_mantle(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:
    
    amount = 8
    if is_upgraded:
        amount = 10
    
    owner = combat.combat_state.player
    owner.apply_status(StatusId.CRIMSON_MANTLE, amount)
    return True

def play_anger(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:

    if target_index >= len(combat.combat_state.enemies):
        print("Index out of bounds")
        return False
    
    damage = 6
    if is_upgraded:
        damage = 8
    
    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    damage = combat.calculate_damage(damage, owner, target)

    new_card = Card.create_copy(card)
    owner.discard_pile.append(new_card)
    
    target.apply_attack_damage(damage, owner)
    return True

def play_bludgeon(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:

    if target_index >= len(combat.combat_state.enemies):
        print("Index out of bounds")
        return False
    
    damage = 32
    if is_upgraded:
        damage = 42
    
    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    damage = combat.calculate_damage(damage, owner, target)
    
    target.apply_attack_damage(damage, owner)
    return True

def play_unrelenting(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:
     
    if target_index >= len(combat.combat_state.enemies):
        print("Index out of bounds")
        return False
    
    damage = 14
    if is_upgraded:
        damage = 20
    
    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    damage = combat.calculate_damage(damage, owner, target)
    
    target.apply_attack_damage(damage, owner)

    owner = combat.combat_state.player
    owner.apply_status(StatusId.FREE_ATTACK, 1)
    return True

def play_body_slam(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:
    if target_index >= len(combat.combat_state.enemies):
        print("Index out of bounds")
        return False
    
    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    damage = owner.block
    damage = combat.calculate_damage(damage, owner, target)
    
    target.apply_attack_damage(damage, owner)

def play_twin_strike(card: Card, combat : CombatSimulator, target_index : int, is_upgraded=False) -> bool:

    if target_index >= len(combat.combat_state.enemies):
        print("Index out of bounds")
        return False
    
    damage = 5
    if is_upgraded:
        damage = 7
    
    owner = combat.combat_state.player
    target = combat.combat_state.enemies[target_index]
    damage = combat.calculate_damage(damage, owner, target)
    
    target.apply_attack_damage(damage, owner)
    target.apply_attack_damage(damage, owner)
    return True

###
### map to get function from card id
###


GET_CARD_FUNCTION : dict[CardId, function] = {
    CardId.STRIKE_IRONCLAD : play_strike,
    CardId.DEFEND_IRONCLAD : play_defend,
    CardId.BASH : play_bash,
    CardId.BLOOD_WALL : play_blood_wall,
    CardId.SLIMED : play_slimed,
    CardId.PERFECTED_STRIKE : play_perfected_strike,
    CardId.BREAKTHROUGH : play_breakthrough,
    CardId.SHRUG_IT_OFF : play_shrug_it_off,
    CardId.POMMEL_STRIKE : play_pommel_strike,
    CardId.IRON_WAVE : play_iron_wave,
    CardId.THUNDERCLAP : play_thunderclap,
    CardId.INFLAME : play_inflame,
    CardId.FIGHT_ME : play_fight_me,
    CardId.TREMBLE : play_tremble,
    CardId.CRIMSON_MANTLE : play_crimson_mantle,
    CardId.ANGER : play_anger,
    CardId.BLUDGEON : play_bludgeon,
    CardId.UNRELENTING : play_unrelenting,
    CardId.BODY_SLAM : play_body_slam,
    CardId.TWIN_STRIKE : play_twin_strike,
}