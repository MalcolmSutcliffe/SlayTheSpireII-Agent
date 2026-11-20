from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite.status import StatusId
from sts2_lite.relic.ids import RelicId
from sts2_lite.relic import damage_bonus, damage_multiplier, vulnerable_bonus, weak_multiplier

if TYPE_CHECKING:
    from sts2_lite.card import Card
    from sts2_lite.creature import Creature

WEAK_MULTIPLIER = 0.75
VULNERABLE_MULTIPLIER = 1.5
SHRINK_MULTIPLIER = 0.7
COLOSSUS_MULTIPLIER = 0.5
FLUTTER_MULTIPLIER = 0.5
SOAR_MULTIPLIER = 0.5
SURROUND_MULTIPLIER = 1.5
GIGANTIFICATION_MULTIPLIER = 3      # Gigantification Potion: the next Attack

# game uses decimal; guards float truncation (62.999... -> 63)
EPSILON = 1e-9


def surround_facing(target : Creature) -> int:
    """Which way a Surrounded creature faces: 0 Right (the default), 1 Left. The game's power keeps it; the bridge does not
    report it, so it lives in the status's records and load time works it out from the enemies' shown damage."""
    records = target.status[StatusId.SURROUNDED].records
    return records[0][0] if records else 0


def attacks_from_behind(attacker : Creature, target : Creature) -> bool:
    """Surrounded: facing Right the arm on the left is behind the target, facing Left the one on the right."""
    behind = StatusId.BACK_ATTACK_RIGHT if surround_facing(target) else StatusId.BACK_ATTACK_LEFT
    return behind in attacker.status


def modify_damage(base : int, attacker : Creature, target : Creature, card : Card | None = None, in_play : bool = True, owner : Creature | None = None) -> int:
    # Strength, Tainted and relics add, then Weak, Vulnerable, Shrink and Slow multiply; truncated once at the end.
    # `card`: damage source for relic checks. `in_play`: False when previewed from hand (Thrash's victim).
    # `owner`: the player whose Osty is the attacker (Pen Nib and Lethality are the player's; Osty has no Strength or relics of its own).
    damage = base + attacker.status_amount(StatusId.STRENGTH) + target.status_amount(StatusId.TAINTED)
    if StatusId.VIGOR in attacker.status and hasattr(attacker, "enemy_id"):
        damage += attacker.status[StatusId.VIGOR].amount        # VigorPower: an enemy's next attack (the player's is spent by the simulator)
    if attacker.relics:
        damage += damage_bonus(attacker, card)
    if StatusId.WEAK in attacker.status:
        weak = weak_multiplier(target, WEAK_MULTIPLIER) if target.relics else WEAK_MULTIPLIER
        if StatusId.DEBILITATE in attacker.status:
            weak += weak - 1                         # DebilitatePower.ModifyWeakMultiplier
        damage *= weak
    if StatusId.VULNERABLE in target.status:
        multiplier = VULNERABLE_MULTIPLIER + attacker.status_amount(StatusId.CRUELTY) / 100
        if attacker.relics:
            multiplier += vulnerable_bonus(attacker)
        if StatusId.DEBILITATE in target.status:
            multiplier += multiplier - 1            # DebilitatePower.ModifyVulnerableMultiplier
        damage *= multiplier
    if StatusId.CONQUEROR in target.status and card is not None and card.card_id.name == "SOVEREIGN_BLADE":
        damage *= 2                         # ConquerorPower: the Sovereign Blade hits it for double
    holder = owner if owner is not None else attacker
    if holder.relics:
        damage *= damage_multiplier(holder, card, in_play)        # Pen Nib
    if card is not None and StatusId.HANG in target.status and card.card_id.name == "HANG":
        damage *= target.status[StatusId.HANG].amount            # HangPower: the Hang card hits for as many times as it has been applied
    if card is not None and StatusId.LETHALITY in holder.status and card.type.name == "Attack" and getattr(holder, "attacks_played_this_turn", 1) == 0:
        damage *= 1 + holder.status[StatusId.LETHALITY].amount / 100        # LethalityPower: the first Attack of the turn
    if StatusId.COLOSSUS in target.status and StatusId.VULNERABLE in attacker.status:
        damage *= COLOSSUS_MULTIPLIER
    if StatusId.FLUTTER in target.status:
        damage *= FLUTTER_MULTIPLIER
    if StatusId.SOAR in target.status:
        damage *= SOAR_MULTIPLIER
    if StatusId.SURROUNDED in target.status and attacks_from_behind(attacker, target):
        damage *= SURROUND_MULTIPLIER
    if card is not None and StatusId.DOUBLE_DAMAGE in attacker.status:
        damage *= 2                         # DoubleDamagePower (Shadow Step)
    if card is not None and StatusId.TRACKING in attacker.status and StatusId.WEAK in target.status:
        damage *= 1 + attacker.status[StatusId.TRACKING].amount / 100       # TrackingPower
    if StatusId.GIGANTIFICATION in attacker.status and card is not None and card.type.name == "Attack":
        damage *= GIGANTIFICATION_MULTIPLIER
    if StatusId.SHRINK in attacker.status:
        damage *= SHRINK_MULTIPLIER
    if StatusId.SLOW in target.status:
        damage *= 1 + target.status[StatusId.SLOW].amount / 100
    if target.relics and RelicId.UNDYING_SIGIL in target.relics and hasattr(attacker, "enemy_id") and attacker.current_hp <= attacker.status_amount(StatusId.DOOM):
        damage *= 0.5                       # UndyingSigil: a creature that Doom is about to take hits for half
    return max(0, int(damage + EPSILON))


def bases_from_displayed(displayed : int, attacker : Creature, target : Creature) -> set[int]:
    """Every base damage that modify_damage turns into `displayed` (truncation maps several bases to one value)."""
    limit = 2 * displayed + abs(attacker.status_amount(StatusId.STRENGTH)) + 10
    return {base for base in range(limit + 1) if modify_damage(base, attacker, target) == displayed}

def base_from_displayed(displayed : int, attacker : Creature, target : Creature) -> int:
    """Base damage that modify_damage turns into `displayed`.
    Truncation can map several bases to one value (only when the net multiplier
    is below 1); the largest is returned. Falls back to `displayed` if none match."""
    limit = 2 * displayed + abs(attacker.status_amount(StatusId.STRENGTH)) + 10
    for base in range(limit, -1, -1):
        if modify_damage(base, attacker, target) == displayed:
            return base
    return displayed
