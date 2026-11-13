from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite.status import StatusId
from sts2_lite.relic import damage_bonus, damage_multiplier, vulnerable_bonus, weak_multiplier

if TYPE_CHECKING:
    from sts2_lite.card import Card
    from sts2_lite.creature import Creature

WEAK_MULTIPLIER = 0.75
VULNERABLE_MULTIPLIER = 1.5
SHRINK_MULTIPLIER = 0.7
COLOSSUS_MULTIPLIER = 0.5
DIAMOND_DIADEM_MULTIPLIER = 0.5
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


def modify_damage(base : int, attacker : Creature, target : Creature, card : Card | None = None, in_play : bool = True) -> int:
    # Strength, Tainted and relics add, then Weak, Vulnerable, Shrink and Slow multiply; truncated once at the end.
    # `card`: damage source for relic checks. `in_play`: False when previewed from hand (Thrash's victim).
    damage = base + attacker.status_amount(StatusId.STRENGTH) + target.status_amount(StatusId.TAINTED)
    if StatusId.VIGOR in attacker.status and hasattr(attacker, "enemy_id"):
        damage += attacker.status[StatusId.VIGOR].amount        # VigorPower: an enemy's next attack (the player's is spent by the simulator)
    if attacker.relics:
        damage += damage_bonus(attacker, card)
    if StatusId.WEAK in attacker.status:
        damage *= weak_multiplier(target, WEAK_MULTIPLIER) if target.relics else WEAK_MULTIPLIER
    if StatusId.VULNERABLE in target.status:
        multiplier = VULNERABLE_MULTIPLIER + attacker.status_amount(StatusId.CRUELTY) / 100
        if attacker.relics:
            multiplier += vulnerable_bonus(attacker)
        damage *= multiplier
    if attacker.relics:
        damage *= damage_multiplier(attacker, card, in_play)        # Pen Nib
    if StatusId.COLOSSUS in target.status and StatusId.VULNERABLE in attacker.status:
        damage *= COLOSSUS_MULTIPLIER
    if StatusId.DIAMOND_DIADEM in target.status:
        damage *= DIAMOND_DIADEM_MULTIPLIER
    if StatusId.FLUTTER in target.status:
        damage *= FLUTTER_MULTIPLIER
    if StatusId.SOAR in target.status:
        damage *= SOAR_MULTIPLIER
    if StatusId.SURROUNDED in target.status and attacks_from_behind(attacker, target):
        damage *= SURROUND_MULTIPLIER
    if StatusId.GIGANTIFICATION in attacker.status and card is not None and card.type.name == "Attack":
        damage *= GIGANTIFICATION_MULTIPLIER
    if StatusId.SHRINK in attacker.status:
        damage *= SHRINK_MULTIPLIER
    if StatusId.SLOW in target.status:
        damage *= 1 + target.status[StatusId.SLOW].amount / 100
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
