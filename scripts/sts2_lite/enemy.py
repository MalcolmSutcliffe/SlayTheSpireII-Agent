from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator

import logging
from enum import Enum, auto

from sts2_lite import rng
from sts2_lite.card import Card, CardId
from sts2_lite.creature import Creature
from sts2_lite.enemy_moves import MOVE_TABLES, rat_counter, table_move_id, SPAWN_HP, SPAWN_MOVE, SPAWN_STATUS, TOUGH_ASCENSION, MoveTable
from sts2_lite.damage import modify_damage
from sts2_lite.status import StatusInstance, StatusId

log = logging.getLogger("sts2_lite")
REATTACH_HEAL = 25
STRICT_BRIDGE_CHECKS = False    # True: a disagreement with the game raises BridgeMismatch instead of logging a warning


STUNNED = "STUNNED"     # the game's id for the move of a stunned creature


class BridgeMismatch(AssertionError):
    pass

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
    after_stun : str | None = None    # the move to perform after the STUNNED move (set while move_id == STUNNED)
    counter : int = 0                 # Knowledge Demon: curses cast so far (picks the set offered and when the casting stops)
    off_balance : bool = False        # Bowlbug Rock: an attack of its was fully blocked, so its next move is DIZZY

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
            if "base_damage" in intent:
                # the move's own damage and hits (before Strength, Weak, Vulnerable...): exact, no inference needed
                e.attack_damage = intent["base_damage"]
                e.num_attacks = intent["hits"]
            elif intent["type"] == "Attack":
                # older bridge: the displayed damage; the simulator works the base out of it
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
        # The Lost / The Forgotten: the game does not show what they took; every Smog or Miasma gave them what it took
        for possess, stat in ((StatusId.POSSESS_STRENGTH, StatusId.STRENGTH), (StatusId.POSSESS_SPEED, StatusId.DEXTERITY)):
            if possess in e.status and not e.status[possess].records:
                e.status[possess].records.append([max(0, e.status_amount(stat))])

        monster, _, number = e.enemy_id.rpartition("_")
        e.slot = int(number) if number.isdigit() else 0
        table = MOVE_TABLES.get(monster)
        if table is not None:
            e.moves = table(ascension)
        e._read_move_history(enemy, monster)
        return e

    @staticmethod
    def reads_base_damage(intents : list[dict]) -> bool:
        """True when the bridge gave the move's base damage, so the displayed damage needs no inverting."""
        return any("base_damage" in i for i in intents)

    def _read_move_history(self, raw : dict, monster : str):
        """Current move, streak and once-per-fight moves from the bridge's `move_id` and `move_log` (newest last)."""
        if self.moves is None or "move_id" not in raw:
            return
        if raw["move_id"] == STUNNED:
            follow = raw.get("follow_up_id")
            self.move_id, self.after_stun = STUNNED, table_move_id(monster, follow, self.moves) if follow else None
            self.attack_damage = self.num_attacks = 0
            return
        current = table_move_id(monster, raw["move_id"], self.moves)
        if current is None:
            return
        self.move_id = current
        log = [table_move_id(monster, m, self.moves) for m in raw.get("move_log", ())]
        if log and log[-1] == current:      # the log ends with the current move
            streak = 1
            while streak < len(log) and log[-1 - streak] == current:
                streak += 1
            self.move_streak = streak
            self.used_moves = {m for m in log[:-1] if m is not None}
        if monster == "AEONGLASS":
            self.counter = (log[:-1] if log and log[-1] == current else log).count("INCREASING_INTENSITY")      # WitherUpgradeCount
        elif monster == "TEST_SUBJECT" and current == "MULTI_CLAW":
            self.counter = max(0, int(raw.get("intents", [{}])[0].get("hits", 3)) - 3)       # claws it has gained
        if monster == "WATERFALL_GIANT" and current != "EXPLODE":
            performed = log[:-1] if log and log[-1] == current else log
            self.counter = performed.count("PRESSURE_GUN")          # the Pressure Gun has grown by 5 for each time it fired
        if monster == "GREMLIN_MERC" and StatusId.THIEVERY in self.status:
            performed = log[:-1] if log and log[-1] == current else log        # each attack took the full amount, as far as the bridge can say
            thievery = self.status[StatusId.THIEVERY]
            thievery.records = [[thievery.amount, thievery.amount * len(performed)]]
        if monster == "TWO_TAILED_RAT":
            performed = log[:-1] if log and log[-1] == current else log
            screeches = [i for i, m in enumerate(performed) if m == "SCREECH"]
            gap = len(performed) - 1 - screeches[-1] if screeches else 3
            self.counter = rat_counter(sum(1 for m in performed if m != "CALL_FOR_BACKUP"), max(0, 3 - gap), performed.count("CALL_FOR_BACKUP"))
        if monster == "KNOWLEDGE_DEMON":
            performed = log[:-1] if log and log[-1] == current else log      # the current move has not been performed yet
            self.counter = performed.count("CURSE_OF_KNOWLEDGE")

    @classmethod
    def lie_dead(cls, segment : Enemy) -> Enemy:
        """A killed Decimillipede segment (ReattachPower): out of the fight with only Reattach left, on its dead turn."""
        e = cls.deepcopy(segment)
        e.current_hp, e.block = 0, 0
        e.status = {StatusId.REATTACH : segment.status[StatusId.REATTACH]}
        e.move_id, e.move_streak, e.attack_damage, e.num_attacks, e.after_stun, e.off_balance = "DEAD", 1, 0, 0, None, False
        return e

    @classmethod
    def lie_dead_subject(cls, subject : Enemy) -> Enemy:
        """A killed Test Subject (AdaptablePower): still in the fight, with only the powers that outlive it, and about to respawn."""
        e = cls.deepcopy(subject)
        e.current_hp, e.block = 0, 0
        e.last_index = getattr(subject, "last_index", 0)
        e.status = {sid : inst for sid, inst in subject.status.items() if sid in (StatusId.ADAPTABLE, StatusId.PAINFUL_STABS)}
        e.move_id, e.move_streak, e.attack_damage, e.num_attacks, e.after_stun, e.off_balance = "RESPAWN", 1, 0, 0, None, False
        return e

    @classmethod
    def dormant_subject(cls, ascension : int) -> Enemy:
        """The Test Subject while it is dead: the bridge lists no enemies at all. Its form is not shown, so this is the first one's death."""
        e = cls()
        e.max_hp, e.current_hp, e.enemy_id = (111 if ascension >= TOUGH_ASCENSION else 100), 0, "TEST_SUBJECT_0"
        e.moves = MOVE_TABLES["TEST_SUBJECT"](ascension)
        e.move_id, e.attack_damage, e.num_attacks = "RESPAWN", 0, 0
        e.status = {StatusId.ADAPTABLE : StatusInstance(StatusId.ADAPTABLE, 1)}
        e.last_index = 0
        return e

    @classmethod
    def dormant_segment(cls, monster : str, ascension : int, max_hp : int) -> Enemy:
        """A segment the bridge no longer lists: dead, and about to reattach."""
        e = cls()
        e.max_hp, e.current_hp, e.enemy_id = max_hp, 0, f"{monster}_0"
        e.moves = MOVE_TABLES[monster](ascension)
        e.move_id = "REATTACH"
        e.attack_damage = e.num_attacks = 0
        e.status = {StatusId.REATTACH : StatusInstance(StatusId.REATTACH, REATTACH_HEAL)}
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
        e.num_attacks = e._move_hits(e.moves[e.move_id])
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

    def check_against_bridge(self, raw : dict, player : Creature):
        """Compare the simulator's reading of this enemy with what the game reported. Disagreements are the
        bugs to fix: wrong damage modifiers, a move table that has drifted from the game, a missed move id."""
        problems = []
        for intent in raw.get("intents", ()):
            if "base_damage" not in intent or "damage" not in intent:
                continue
            damage = modify_damage(self.attack_damage, self, player)
            if damage != intent["damage"]:
                problems.append(f"damage {damage} but the game shows {intent['damage']} "
                                f"(base {self.attack_damage}, strength {self.status_amount(StatusId.STRENGTH)})")
            elif damage * self.num_attacks != intent["total_damage"]:
                problems.append(f"{self.num_attacks} hits of {damage} but the game shows a total of {intent['total_damage']}")
        if raw.get("move_id") == STUNNED or self.move_id == STUNNED:
            if (raw.get("move_id") == STUNNED) != (self.move_id == STUNNED):
                problems.append(f"move {self.move_id} but the game says {raw.get('move_id')}")
        elif "move_id" in raw and self.moves is not None and self.move_id is not None:
            if table_move_id(self.enemy_id.rpartition("_")[0], raw["move_id"], self.moves) != self.move_id:
                problems.append(f"move {self.move_id} but the game says {raw['move_id']}")
        if "move_id" in raw and self.moves is None and self.enemy_id.rpartition("_")[0] in MOVE_TABLES:
            problems.append(f"move {raw['move_id']} not in the table")
        for problem in problems:
            message = f"{self.enemy_id}: {problem}"
            if STRICT_BRIDGE_CHECKS:
                raise BridgeMismatch(message)
            log.warning(message)

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
        new_e.after_stun = enemy.after_stun
        new_e.off_balance = enemy.off_balance
        new_e.counter = enemy.counter
        # per-turn flags: Skittish blocks on the first attack of a turn, so a copy made between two attacks must remember the first
        new_e.has_been_attacked_this_turn = enemy.has_been_attacked_this_turn
        new_e.lost_hp_this_turn = enemy.lost_hp_this_turn
        new_e.hp_loss_events = enemy.hp_loss_events
        return new_e

    plating_at_turn_start = False       # its Plating block comes before the player's turn starts (CombatSimulator._start_player_turn)

    def turn_start(self):
        # block lasts until this enemy's own turn (see perform_turn)
        block = self.block
        super().turn_start()
        self.block += block

    def clear_block(self):
        if StatusId.BURROWED not in self.status:        # Burrowed keeps its block
            self.block = 0

    def perform_turn(self, combat : CombatSimulator):
        if not getattr(combat, "blocks_cleared", False):        # the simulator clears everyone's block as the side's turn starts
            self.clear_block()
        if self.move_id == STUNNED:
            self._wake_from_stun(combat)
            return
        performed = self.move_id            # a hit taken while attacking (Thorns) can stun this enemy before the move is over
        if self.num_attacks > 0:
            player = combat.combat_state.player
            damage = combat.calculate_damage(self.attack_damage, self, player)
            lost_before = player.hp_loss_events
            player.apply_attack_damage(damage, self, self.num_attacks)
            stabs = self.status.get(StatusId.PAINFUL_STABS)
            if stabs is not None and player.hp_loss_events > lost_before:       # a Wound for every hit that got through the block
                for _ in range(stabs.amount * (player.hp_loss_events - lost_before)):
                    player.discard_pile.append(Card.create(CardId.WOUND))
            suck = self.status.get(StatusId.SUCK)
            if suck is not None and player.hp_loss_events > lost_before:        # SuckPower: Strength for every hit that got through
                self.apply_status(StatusId.STRENGTH, suck.amount * (player.hp_loss_events - lost_before))
            self.status.pop(StatusId.VIGOR, None)           # VigorPower: spent by the attack
        if self.moves is not None:
            player = combat.combat_state.player
            move = self.moves[performed]
            for status_id, amount in move.player_status:
                player.apply_status(status_id, amount)
            for card_id, count in move.cards:
                for _ in range(count):
                    player.discard_pile.append(Card.create(card_id))
            for card_id, count in move.hand_cards:
                for _ in range(count):
                    player.add_to_hand(Card.create(card_id))
            for card_id, count in move.draw_cards:
                for _ in range(count):
                    player.insert_into_draw_pile(Card.create(card_id))
            if move.summon is not None:
                combat.summon(Enemy.spawn(*move.summon, combat.combat_state.ascension), front=True)
            for monster, slot in move.summons:
                combat.summon(Enemy.spawn(monster, slot, combat.combat_state.ascension), front=True)
            for status_id, amount in move.team_status:
                for ally in combat.combat_state.enemies:
                    ally.apply_status(status_id, amount)
            if move.heal:
                self.current_hp = min(self.max_hp, self.current_hp + move.heal)
            if move.effect is not None:
                move.effect(self, combat)
            self._finish_move(combat, performed)
            if self.off_balance:        # Bowlbug Rock: the attack was fully blocked, so it is stunned and then repeats it
                self.off_balance = False
                self.stun(performed)

    def imbalanced(self):
        """A fully blocked attack of this enemy's (Imbalanced). The Rock finishes its move before it stumbles."""
        self.off_balance = True

    def next_after_current(self) -> str | None:
        """The move the game's state machine rolls after the current one (a stun placed now leads to it)."""
        return self._choose_next(self.moves[self.move_id]) if self.moves is not None else None

    def stun(self, after : str | None = None):
        """The move shown on the next turn becomes STUNNED (the table's own STUN move when it has one), which does nothing.
        `after`: the move that follows it; by default the move that was interrupted (the last one in the game's move log)."""
        if self.moves is None:
            return
        if "STUN" in self.moves:
            self.move_id = "STUN"
        elif self.move_id == STUNNED:
            return
        else:
            self.after_stun = after or self.move_id
            self.move_id = STUNNED
        self.move_streak = 1
        self.attack_damage = 0
        self.num_attacks = 0

    def _wake_from_stun(self, combat : CombatSimulator):
        stunned = self.moves.get(STUNNED)       # a table can give the stun an effect (the Beetle loses its Plating)
        if stunned is not None and stunned.effect is not None:
            stunned.effect(self, combat)
        following = self.moves[self.after_stun]
        self.move_id, self.after_stun = self.after_stun, None
        self.move_streak = 1
        self.attack_damage = self._move_damage(following)
        self.num_attacks = self._move_hits(following)

    def _move_hits(self, move) -> int:
        return move.hits + (move.extra_hits(self) if move.extra_hits is not None else 0)

    def _move_damage(self, move) -> int:
        return move.damage + (self.status_amount(StatusId.DEXTERITY) if move.dex_damage else 0) + (move.extra_damage(self) if move.extra_damage is not None else 0)

    def _finish_move(self, combat : CombatSimulator | None = None, performed : str | None = None):
        performed = performed or self.move_id
        move = self.moves[performed]
        self.used_moves.add(performed)
        if move.block:
            self.apply_block(move.block)
        for status_id, amount in move.self_status:
            self.apply_status(status_id, amount)
        if self.move_id == STUNNED and performed != STUNNED:
            return              # stunned during its own move: the stun is the next intent
        # next intent is chosen now, as the game shows it during the player's turn
        next_id = self._choose_next(move, combat)
        following = self.moves[next_id]
        self.move_streak = self.move_streak + 1 if next_id == self.move_id else 1
        self.move_id = next_id
        self.attack_damage = self._move_damage(following)
        self.num_attacks = self._move_hits(following)

    def _choose_next(self, move, combat : CombatSimulator | None = None) -> str:
        if move.choose is not None:
            return move.choose(self, combat)
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