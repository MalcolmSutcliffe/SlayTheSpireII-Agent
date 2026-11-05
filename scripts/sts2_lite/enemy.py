from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator

from enum import Enum, auto

from sts2_lite.creature import Creature
from sts2_lite.enemy_moves import MOVE_TABLES, MoveTable
from sts2_lite.status import StatusInstance, StatusId

class EnemyId(Enum):
    SEAPUNK = auto()

class Enemy(Creature):
    enemy_id : EnemyId
    attack_damage : int
    num_attacks: int = 1
    moves : MoveTable | None = None    # None: repeats attack_damage x num_attacks forever
    move_id : str | None = None

    def __init__(self):
        super().__init__()

    @classmethod
    def from_dict(cls, enemy: dict, ascension : int = 0):
        e = Enemy()
        e.max_hp = enemy["max_hp"]
        e.current_hp = enemy["hp"]
        e.block = enemy["block"]
        e.enemy_id = enemy["entity_id"]
        e.attack_damage = 0
        e.num_attacks = 0
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

        table = MOVE_TABLES.get(e.enemy_id.rsplit("_", 1)[0])
        if table is not None:
            e.moves = table(ascension)
        return e

    def identify_move(self, intents : list[dict], round_number : int):
        """Set the current move from the bridge intents. Call once attack_damage holds base damage.
        Without a unique match the enemy falls back to repeating its attack."""
        if self.moves is None:
            return
        types = frozenset(i["type"].lower() for i in intents)
        found = [m for m, move in self.moves.items() if move.intents == types]
        if len(found) > 1:
            found = [m for m in found if self.moves[m].damage == self.attack_damage] or found
        if len(found) > 1:
            found = [m for m in found if self._in_round(self.moves[m], round_number)] or found
        if len(found) == 1:
            self.move_id = found[0]
        else:
            self.moves = None

    @staticmethod
    def _in_round(move, round_number : int) -> bool:
        if move.round_mod is None:
            return False
        period, remainder = move.round_mod
        return round_number % period == remainder

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
        new_e.moves = enemy.moves
        new_e.move_id = enemy.move_id
        return new_e

    def turn_start(self):
        # block lasts until this enemy's own turn (see perform_turn)
        block = self.block
        super().turn_start()
        self.block += block

    def perform_turn(self, combat : CombatSimulator):
        self.block = 0
        if self.num_attacks > 0:
            player = combat.combat_state.player
            damage = combat.calculate_damage(self.attack_damage, self, player)
            player.apply_attack_damage(damage, self, self.num_attacks)
        if self.moves is not None:
            player = combat.combat_state.player
            for status_id, amount in self.moves[self.move_id].player_status:
                player.apply_status(status_id, amount)
            self._finish_move()

    def _finish_move(self):
        move = self.moves[self.move_id]
        if move.block:
            self.apply_block(move.block)
        for status_id, amount in move.self_status:
            self.apply_status(status_id, amount)
        # next intent is chosen now, as the game shows it during the player's turn
        following = self.moves[move.next_move]
        self.move_id = move.next_move
        self.attack_damage = following.damage
        self.num_attacks = following.hits

    def readable(self) -> str:
        output = ""
        output += self.enemy_id + ":\n"
        output += super().readable()
        output += "\nAttacking for: " + str(self.attack_damage) + "x" + str(self.num_attacks)
        if self.move_id is not None:
            output += "\nMove: " + self.move_id
        return output