from enum import Enum

from sts2_lite.creature import Creature
from sts2_lite.player import Player
from sts2_lite.enemy import Enemy
from sts2_lite.card import TargetType, Card

from sts2_lite.status import StatusId, StatusBehaviour

class CombatState:
    player : Player
    energy : int
    max_energy : int
    enemies : list[Enemy] = []
    turn_number : int
    deck : list[Card]

    def __init__(self):
        pass

    @classmethod
    def from_dict(cls, combat_state : dict):
        cs = cls()
        cs.player = Player.from_dict(combat_state["player"])
        cs.enemies = []
        for enemy in combat_state["enemies"]:
            cs.enemies.append(Enemy.from_dict(enemy))
        cs.turn_number = combat_state["round"]
        cs.energy = combat_state["energy"]
        cs.max_energy = combat_state["max_energy"]
        cs.deck = []
        for card in combat_state["player"]["deck"]:
            cs.deck.append(Card.from_dict(card))
        return cs

    @classmethod
    def deepcopy(cls, combat_state : CombatState) -> CombatState:
        new_cs = cls()
        new_cs.player = Player.deepcopy(combat_state.player)
        new_cs.enemies = []
        for enemy in combat_state.enemies:
            new_cs.enemies.append(Enemy.deepcopy(enemy))
        new_cs.max_energy = combat_state.max_energy
        new_cs.energy = combat_state.energy
        new_cs.turn_number = combat_state.turn_number
        new_cs.deck = []
        for card in combat_state.deck:
            new_cs.deck.append(card)
        return new_cs
        
    def readable(self) -> str:
        output = ""
        output += "Turn : " + str(self.turn_number) + "\n"
        output += "Energy : " + str(self.energy) + "\n"
        output += "Player : \n" + self.player.readable()
        output += "Enemies : \n"
        for enemy in self.enemies:
            output += enemy.readable()
        return output

class Combat:
    combat_state : CombatState
    is_over : bool = False

    def __init__(self, combat_state : CombatState):
        self.combat_state = combat_state
        self._check_is_over()

    ###
    ### Interface points
    ###

    def perform_action(self, action: dict):
        if self.is_over:
            return
        if action["action"] == "end_turn":
            self.end_turn()
            return
        if action["action"] == "play_card":
            self.play_card(action["card_index"], action["target"])
            return

    def play_card(self, card_index : int, target_index : int):
        if self.is_over:
            return
        card = self.combat_state.player.hand[card_index]
        
        if card.play_card(self, target_index):
            if card in self.combat_state.player.hand:
                card = self.combat_state.player.hand.pop(card_index)
                self.combat_state.player.discard_pile.append(card)
        
        for enemy in self.combat_state.enemies:
            if StatusId.SLOW in enemy.status:
                enemy.status[StatusId.SLOW].amount = enemy.status[StatusId.SLOW].amount + 10
        self._remove_dead_enemies()
        self.is_over = self._check_is_over()

    def end_turn(self):
        if self.is_over:
            return
        self.combat_state.energy = 0
        self._discard_hand()
        self._play_enemy_turn()
        self._decrease_statuses()
        self.combat_state.turn_number += 1
        self._check_is_over()
        self._start_player_turn()

    ###
    ### Helper functions
    ###

    def _discard_hand(self):
        self.combat_state.player.discard_pile.extend(self.combat_state.player.hand)
        self.combat_state.player.hand.clear()

    def _start_player_turn(self):
        self.combat_state.energy = self.combat_state.max_energy
        self.combat_state.player.turn_start()
        for enemy in self.combat_state.enemies:
            enemy.turn_start()
        self._decrease_statuses()

    def _play_enemy_turn(self):
        for enemy in self.combat_state.enemies:
            enemy.perform_turn(self)
    
    def _decrease_statuses(self):
        for enemy in self.combat_state.enemies:
            to_remove : list[StatusId] = []
            for status in enemy.status.values():
                if status.behavior == StatusBehaviour.STATIC:
                    pass
                elif status.behavior == StatusBehaviour.RESET_TO_ZERO:
                    status.amount = 0
                elif status.behavior == StatusBehaviour.DECREASE_BY_ONE:
                    status.amount -=1
                    if status.amount <= 0:
                        to_remove.append(status.status_id)
            for id in to_remove:
                del enemy.status[id]

        to_remove : list[StatusId] = []  
        for status in self.combat_state.player.status.values():
            if status.behavior == StatusBehaviour.STATIC:
                pass
            elif status.behavior == StatusBehaviour.RESET_TO_ZERO:
                status.amount = 0
            elif status.behavior == StatusBehaviour.DECREASE_BY_ONE:
                status.amount -=1
                if status.amount <= 0:
                    to_remove.append(status.status_id)
        for id in to_remove:
            del self.combat_state.player.status[id]
    
    def _remove_dead_enemies(self):
        self.combat_state.enemies = [e for e in self.combat_state.enemies if e.current_hp > 0]

    def _check_is_over(self):
        # if player is alive and there is an alive non-minion enemy
        if self.combat_state.player.current_hp <= 0:
            self.is_over = True
            return
        
        for enemy in self.combat_state.enemies:
            if not enemy.is_minion:
                self.is_over = False
                return

        self.is_over = True

    ###
    ### Calculators
    ###

    def get_available_actions(self) -> list[dict]:
        output = []

        for c_i, c in enumerate(self.combat_state.player.hand):
            if c.target_type == TargetType.Self or c.target_type == TargetType.AllEnemies:
                if c.can_play_card(self, 0):
                    output.append({"action" : "play_card", "card_index" : c_i, "target" : 0})
            elif c.target_type == TargetType.AnyEnemy:
                for e_i, e in enumerate(self.combat_state.enemies):
                    if c.can_play_card(self, e_i):
                        output.append({"action" : "play_card", "card_index" : c_i, "target" : e_i, "target_name" : e.enemy_id})

        output.append({"action" : "end_turn"})
        return output

    def calculate_damage(self, initial_damage : int, owner: Creature, target : Creature):
        
        damage = initial_damage
        
        # check owner statuses
        if StatusId.STRENGTH in owner.status:
            damage += owner.status[StatusId.STRENGTH].amount
        if StatusId.WEAK in owner.status:
            damage *= 0.75
        if StatusId.SHRINK in owner.status:
            damage *= 0.7
        
        # check target status
        if StatusId.VULNERABLE in target.status:
            damage *= 1.5
        if StatusId.SLOW in target.status:
            slow_amount = target.status[StatusId.SLOW].amount
            damage *= 1.0 + (float(slow_amount)/10.0)

        
        return int(damage)

    def calculate_block(self, initial_block : int, owner : Creature):
        
        block = initial_block
        
        # check owner statuses
        if StatusId.DEXTERITY in owner.status:
            blcok += owner.status[StatusId.DEXTERITY].amount
        if StatusId.FRAIL in owner.status:
            block *= 0.75
        
        return int(block)