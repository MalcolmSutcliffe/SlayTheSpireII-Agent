from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator

from enum import Enum, auto

from sts2_lite import rng
from sts2_lite.card import Card
from sts2_lite.creature import Creature
from sts2_lite.enemy_moves import MOVE_TABLES, SPAWN_HP, SPAWN_MOVE, SPAWN_STATUS, TOUGH_ASCENSION, MoveTable
from sts2_lite.status import StatusInstance, StatusId

class EnemyId(Enum):
    SEAPUNK = auto()

class Enemy(Creature):
    enemy_id : EnemyId
    attack_damage : int
    num_attacks: int = 1
    moves : MoveTable | None = None    # None: repeats attack_damage x num_attacks forever
    move_id : str | None = None
    move_streak : int = 1    # times in a row the current move has been chosen
    damage_candidates : set[int] | None = None     # every base damage that shows as the intent (Weak and Strength truncate)
    slot : int = 0           # position among enemies of its kind (the number in its entity id)

    def __init__(self):
        super().__init__()
        self.used_moves = set()    # moves already performed, for once-per-fight branches

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

        monster, _, number = e.enemy_id.rpartition("_")
        e.slot = int(number) if number.isdigit() else 0
        table = MOVE_TABLES.get(monster)
        if table is not None:
            e.moves = table(ascension)
        return e

    @classmethod
    def spawn(cls, monster : str, slot : int, ascension : int) -> Enemy:
        """A new enemy for a summon: random hit points, opening move chosen by the table."""
        low, high, tough_low, tough_high = SPAWN_HP[monster]
        if ascension >= TOUGH_ASCENSION:
            low, high = tough_low, tough_high
        e = cls()
        e.max_hp = e.current_hp = rng.randrange(low, high + 1) if low < high else low
        e.enemy_id = f"{monster}_{slot}"
        e.slot = slot
        e.moves = MOVE_TABLES[monster](ascension)
        e.move_id = SPAWN_MOVE.get(monster, "SPAWNED")
        e.attack_damage = e.moves[e.move_id].damage
        e.num_attacks = e.moves[e.move_id].hits
        for status_id, amount in SPAWN_STATUS.get(monster, ()):
            e.status[status_id] = StatusInstance(status_id, amount)
        e.is_minion = StatusId.MINION in e.status
        return e

    def identify_move(self, intents : list[dict], round_number : int):
        """Set the current move from the bridge intents. Call once attack_damage holds base damage.
        Without a unique match the enemy falls back to repeating its attack."""
        if self.moves is None:
            return
        types = frozenset(i["type"].lower() for i in intents)
        found = [m for m, move in self.moves.items() if move.from_bridge and move.intents == types]
        if len(found) > 1:
            damages = self.damage_candidates if self.damage_candidates else {self.attack_damage}
            found = [m for m in found if self.moves[m].damage in damages] or found
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
        new_e.damage_candidates = enemy.damage_candidates
        new_e.num_attacks = enemy.num_attacks
        new_e.moves = enemy.moves
        new_e.move_id = enemy.move_id
        new_e.move_streak = enemy.move_streak
        new_e.used_moves = set(enemy.used_moves)
        new_e.slot = enemy.slot
        # per-turn flags: Skittish blocks on the first attack of a turn, so a copy made between two attacks must remember the first
        new_e.has_been_attacked_this_turn = enemy.has_been_attacked_this_turn
        new_e.lost_hp_this_turn = enemy.lost_hp_this_turn
        new_e.hp_loss_events = enemy.hp_loss_events
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
            for card_id, count in self.moves[self.move_id].cards:
                for _ in range(count):
                    player.discard_pile.append(Card.create(card_id))
            move = self.moves[self.move_id]
            if move.summon is not None:
                combat.summon(Enemy.spawn(*move.summon, combat.combat_state.ascension), front=True)
            self._finish_move()

    def stun(self):
        """The move shown on the next turn is replaced by the table's STUN move."""
        if self.moves is None or "STUN" not in self.moves:
            return
        self.move_id = "STUN"
        self.move_streak = 1
        self.attack_damage = 0
        self.num_attacks = 0

    def _finish_move(self):
        move = self.moves[self.move_id]
        self.used_moves.add(self.move_id)
        if move.block:
            self.apply_block(move.block)
        for status_id, amount in move.self_status:
            self.apply_status(status_id, amount)
        # next intent is chosen now, as the game shows it during the player's turn
        next_id = self._choose_next(move)
        following = self.moves[next_id]
        self.move_streak = self.move_streak + 1 if next_id == self.move_id else 1
        self.move_id = next_id
        self.attack_damage = following.damage
        self.num_attacks = following.hits

    def _choose_next(self, move) -> str:
        if move.next_by_slot:
            return move.next_by_slot[self.slot % len(move.next_by_slot)]
        if not move.branches:
            return move.next_move
        allowed = [b for b in move.branches
                   if not (b.move == self.move_id and self.move_streak >= b.max_streak)
                   and not (b.once and b.move in self.used_moves)]
        if len(allowed) == 1:
            return allowed[0].move
        if len({b.weight for b in allowed}) == 1:
            return rng.choice(allowed).move
        return rng.choices(allowed, weights=[b.weight for b in allowed])[0].move

    def readable(self) -> str:
        output = ""
        output += self.enemy_id + ":\n"
        output += super().readable()
        output += "\nAttacking for: " + str(self.attack_damage) + "x" + str(self.num_attacks)
        if self.move_id is not None:
            output += "\nMove: " + self.move_id
        return output