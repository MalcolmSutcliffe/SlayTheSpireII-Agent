from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator, CombatState

from sts2_lite.status import StatusInstance, StatusId, is_debuff
from sts2_lite.card import Card, CardId
from sts2_lite.relic import RelicId, STURDY_CLAMP_BLOCK, modify_hp_loss, dealt_hp_loss, after_damage_given

# statuses whose owner reacts to being hit (see Creature._after_damage)
REACTIVE_STATUSES = frozenset({StatusId.BURROWED, StatusId.PERSONAL_HIVE, StatusId.CURL_UP, StatusId.SLUMBER, StatusId.FLUTTER})


class Creature:
    max_hp : int
    current_hp : int
    block : int
    status : dict[StatusId, StatusInstance]
    is_minion : bool
    has_been_attacked_this_turn : bool
    lost_hp_this_turn : bool
    relics = ()         # only the player holds relics (Player.relics); empty for everything else

    def __init__(self, max_hp=1, current_hp=1, block=0, status=None, is_minion=False):
        self.max_hp=max_hp
        self.current_hp=current_hp
        self.block=block
        self.status = {} if status is None else status
        self.is_minion=is_minion
        self.has_been_attacked_this_turn = False
        self.lost_hp_this_turn = False
        self.hp_loss_events = 0     # running total of times hit points were lost
        self.damage_taken = 0       # running total of damage received, blocked or not (DamageResult.TotalDamage + Overkill)
        self.hp_lost_log = []       # amounts lost since the simulator last reacted (relics that react to damage)

    plating_at_turn_start = True    # the player's Plating pays out at end of turn instead

    def status_amount(self, status_id : StatusId) -> int:
        s = self.status.get(status_id)
        return s.amount if s is not None else 0

    def lose_hp(self, hp_loss : int):
        if hp_loss > 0 and self.relics:
            hp_loss = modify_hp_loss(self, hp_loss)
        if hp_loss > 0:
            self.lost_hp_this_turn = True
            self.hp_loss_events += 1
        self.current_hp -= hp_loss
        if self.current_hp <= 0:
            self.die()

    def block_kept_at_turn_start(self) -> int:
        """The block this creature keeps when its turn starts: all of it with Barricade, up to 10 with Sturdy Clamp."""
        if StatusId.BARRICADE in self.status:
            return self.block
        if self.relics and RelicId.STURDY_CLAMP in self.relics:
            return min(self.block, STURDY_CLAMP_BLOCK)
        return 0

    def turn_start(self):
        self.block = self.block_kept_at_turn_start()
        self.has_been_attacked_this_turn = False
        self.lost_hp_this_turn = False
        if StatusId.PLATING in self.status and self.plating_at_turn_start:
            self.apply_block(self.status[StatusId.PLATING].amount)

    def turn_end(self):
        pass

    def apply_attack_damage(self, damage :int, sender : Creature, hits : int = 1, recompute=None):
        """`recompute`: damage is re-modified per hit (each hit is its own CreatureCmd.Damage)."""
        first_attack = not self.has_been_attacked_this_turn
        self.has_been_attacked_this_turn = True
        for hit in range(hits):
            if sender.current_hp <= 0:
                break
            if hit and recompute is not None:
                damage = recompute()
            if StatusId.THORNS in self.status:
                sender.apply_damage(self.status[StatusId.THORNS].amount, self)
            self.apply_damage(damage, sender, True)
            if StatusId.FLAME_BARRIER in self.status:       # after the hit, unlike Thorns
                sender.apply_damage(self.status[StatusId.FLAME_BARRIER].amount, self)
        if first_attack and StatusId.SKITTISH in self.status:
            self.apply_block(self.status[StatusId.SKITTISH].amount)

    def apply_damage(self, damage: int, dealer : Creature | None = None, powered : bool = False):
        """`dealer`: who deals it (player relics react); `powered`: an attack (ValueProp.IsPoweredAttack)."""
        if damage <= 0:
            return
        if StatusId.HARD_TO_KILL in self.status:
            damage = min(damage, self.status[StatusId.HARD_TO_KILL].amount)       # ModifyDamageCap; also caps what block absorbs
        hp_before = self.current_hp
        broken = False
        if self.block > 0:
            if self.block > damage:
                self.block -= damage
                self.damage_taken += damage
                self._after_damage(0, False, powered, dealer)
                return
            damage -= self.block
            self.damage_taken += self.block
            self.block = 0
            broken = True
        if damage > 0:
            self._lose_hp_from_damage(damage, dealer, powered)
        if dealer is not None and dealer.relics and dealer is not self:
            after_damage_given(dealer, self, broken)
        if self.current_hp > 0:
            self._after_damage(hp_before - self.current_hp, broken, powered, dealer)

    def _after_damage(self, unblocked : int, block_broken : bool, powered : bool, dealer : Creature | None):
        """AfterDamageReceived / AfterBlockBroken / AfterDamageGiven: runs for fully blocked hits too, never for a kill."""
        if unblocked == 0 and dealer is not None and dealer is not self and StatusId.IMBALANCED in dealer.status:
            dealer.imbalanced()
        if not self.status or REACTIVE_STATUSES.isdisjoint(self.status):
            return
        if block_broken and StatusId.BURROWED in self.status:
            del self.status[StatusId.BURROWED]      # leaving it clears the block
            self.block = 0
            self.stun("BITE")
        if powered and dealer is not None and StatusId.PERSONAL_HIVE in self.status:
            add = getattr(dealer, "insert_into_draw_pile", None)
            if add is not None:             # Osty's hits count for its owner; only the player has a draw pile
                for _ in range(self.status[StatusId.PERSONAL_HIVE].amount):
                    add(Card.create(CardId.DAZED))
        if powered and dealer is not None and StatusId.CURL_UP in self.status and not self.status[StatusId.CURL_UP].records:
            self.status[StatusId.CURL_UP].records.append([1])       # the card that did this earns the block once it finishes
        if unblocked > 0:
            if StatusId.SLUMBER in self.status:
                self._lose_status_amount(StatusId.SLUMBER, 1, lambda: self.stun("ROLL_OUT"))
            if powered and StatusId.FLUTTER in self.status:
                self._lose_status_amount(StatusId.FLUTTER, 1, lambda: self.stun(self.next_after_current()))

    def _lose_status_amount(self, status_id : StatusId, amount : int, when_gone):
        """PowerCmd.Decrement: the power is removed at zero, and `when_gone` runs."""
        inst = self.status[status_id]
        inst.amount -= amount
        if inst.amount <= 0:
            del self.status[status_id]
            when_gone()

    def next_after_current(self) -> str | None:
        return None

    def _lose_hp_from_damage(self, damage : int, dealer : Creature | None, powered : bool):
        if StatusId.SLIPPERY in self.status and self.status[StatusId.SLIPPERY].amount > 0:
            damage = 1
            self.status[StatusId.SLIPPERY].amount -= 1
            if self.status[StatusId.SLIPPERY].amount == 0:
                del self.status[StatusId.SLIPPERY]
        
        if self.relics:
            damage = modify_hp_loss(self, damage)
            if damage <= 0:
                return
        if powered and dealer is not None and dealer.relics and dealer is not self:
            damage = dealt_hp_loss(dealer, damage)        # The Boot (AfterOstyLate: after Slippery)

        self.damage_taken += damage
        self.current_hp -= damage
        self.lost_hp_this_turn = True
        self.hp_loss_events += 1
        
        if powered and StatusId.THE_GAMBIT in self.status:      # The Gambit: any unblocked attack damage kills
            del self.status[StatusId.THE_GAMBIT]
            self.die()
        elif self.current_hp <= 0:
            self.die()
        elif StatusId.PLOW in self.status and self.current_hp <= self.status[StatusId.PLOW].amount:
            self.lose_plow()

    def lose_plow(self):
        """Plow breaks the first time hit points reach its amount: Strength is lost and the creature is stunned."""
        del self.status[StatusId.PLOW]
        self.status.pop(StatusId.STRENGTH, None)
        self.stun()

    def stun(self, after : str | None = None):
        pass

    def apply_block(self, block: int):
        self.block += block

    def apply_status(self, status: StatusId, amount : int, bypass_artifact : bool = False):
        if self.current_hp <= 0:
            return                  # dead creatures receive no powers (Creature.CanReceivePowers)
        if not bypass_artifact and StatusId.ARTIFACT in self.status and is_debuff(status, amount):
            self.status[StatusId.ARTIFACT].amount -= 1      # Artifact negates the whole debuff
            if self.status[StatusId.ARTIFACT].amount <= 0:
                del self.status[StatusId.ARTIFACT]
            return
        if status in self.status:
            self.status[status].amount += amount
            if status is StatusId.THORNS and self.status[status].amount <= 0:
                del self.status[status]         # the Spiny Toad takes its spikes back
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