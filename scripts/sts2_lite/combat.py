from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatState

from sts2_lite.creature import Creature
from sts2_lite.player import Player
from sts2_lite.enemy import Enemy
from sts2_lite.card import TargetType, CardType, Card
from sts2_lite.damage import modify_damage, base_from_displayed
from sts2_lite.events import EventType

from sts2_lite.status import StatusId, StatusBehaviour, STATUS_HANDLERS

class CombatState:
    player : Player
    energy : int
    max_energy : int
    enemies : list[Enemy]
    turn_number : int
    deck : list[Card]

    def __init__(self):
        self.enemies = []

    @classmethod
    def from_dict(cls, combat_state : dict):
        cs = cls()
        cs.player = Player.from_dict(combat_state["player"])
        cs.enemies = []
        ascension = combat_state.get("context", {}).get("ascension", 0)
        for enemy in combat_state["enemies"]:
            cs.enemies.append(Enemy.from_dict(enemy, ascension))
        cs.turn_number = combat_state["round"]
        for enemy, raw in zip(cs.enemies, combat_state["enemies"]):
            if enemy.num_attacks > 0:
                enemy.attack_damage = base_from_displayed(enemy.attack_damage, enemy, cs.player)
            enemy.identify_move(raw["intents"], cs.turn_number)
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

class IllegalActionError(ValueError):
    """Raised when an action is not legal in the current state."""

class CombatSimulator:
    combat_state : CombatState
    is_over : bool = False

    def __init__(self, combat_state : CombatState):
        self.combat_state = combat_state
        self._check_is_over()

    ###
    ### Events
    ###

    def fire(self, event : EventType, *args):
        """Call the status handler for each (status, event) pair in the state."""
        cs = self.combat_state
        for creature in [cs.player, *cs.enemies]:
            for status_id, inst in list(creature.status.items()):  # copy: handlers add statuses
                handler = STATUS_HANDLERS.get((status_id, event))
                if handler is not None:
                    handler(self, creature, inst.amount, *args)

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
        
        hand = self.combat_state.player.hand
        if not 0 <= card_index < len(hand):
            raise IllegalActionError(f"card_index {card_index} not in hand of {len(hand)}")
        card = hand[card_index]
        if not card.can_play_card(self, target_index):
            raise IllegalActionError(f"{card.name} cannot be played (energy {self.combat_state.energy})")

        # the card leaves the hand first; it reaches its pile after the card-played hooks
        hand.pop(card_index)
        try:
            card.play_card(self, target_index)
        except ValueError:
            hand.insert(card_index, card)
            raise

        self.fire(EventType.CARD_PLAYED, card)
        self._move_played_card(card)

        self._remove_dead_enemies()
        self._check_is_over()

    def _move_played_card(self, card : Card):
        player = self.combat_state.player
        if card.type == CardType.Power or card in player.exhaust_pile:
            return
        if card.exhausts:
            player.exhaust_card(card)
            self.fire(EventType.CARD_EXHAUSTED, card)
        else:
            player.discard_pile.append(card)

    def end_turn(self):
        if self.is_over:
            return

        self.fire(EventType.END_TURN)
        
        self._discard_hand()
        self._play_enemy_turn()
        self._decrease_statuses(self.combat_state.player)
        for e in self.combat_state.enemies:
            self._decrease_statuses(e)
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

    def _decrease_statuses(self, creature : Creature):
        to_remove : list[StatusId] = []
        for s in creature.status.values():
            if s.behaviour == StatusBehaviour.STATIC:
                continue
            elif s.behaviour == StatusBehaviour.DECREASE_BY_ONE:
                s.amount = s.amount -1
                if s.amount <= 0:
                    to_remove.append(s.status_id)
            elif s.behaviour == StatusBehaviour.RESET_TO_ZERO:
                s.amount = 0
        for s in to_remove:
            del creature.status[s]

    def _play_enemy_turn(self):
        for enemy in self.combat_state.enemies:
            enemy.perform_turn(self)
        self.fire(EventType.ENEMY_TURN_END)
    
    def _remove_dead_enemies(self):
        dead = [e for e in self.combat_state.enemies if e.current_hp <= 0]
        self.combat_state.enemies = [e for e in self.combat_state.enemies if e.current_hp > 0]
        for enemy in dead:
            self.fire(EventType.CREATURE_KILLED, enemy)

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
            if c.target_type in (TargetType.Self, TargetType.AllEnemies, TargetType.NONE):
                if c.can_play_card(self, 0):
                    output.append({"action" : "play_card", "card_index" : c_i, "target" : 0})
            elif c.target_type == TargetType.AnyEnemy:
                for e_i, e in enumerate(self.combat_state.enemies):
                    if c.can_play_card(self, e_i):
                        output.append({"action" : "play_card", "card_index" : c_i, "target" : e_i, "target_name" : e.enemy_id})

        output.append({"action" : "end_turn"})
        return output

    def calculate_damage(self, initial_damage : int, owner: Creature, target : Creature) -> int:
        return modify_damage(initial_damage, owner, target)

    def calculate_block(self, initial_block : int, owner : Creature) -> int:
        # Dexterity, then Frail
        block = initial_block + owner.status_amount(StatusId.DEXTERITY)
        if StatusId.FRAIL in owner.status:
            block *= 0.75
        return max(0, int(block))
