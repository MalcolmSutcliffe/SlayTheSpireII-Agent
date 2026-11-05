from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite.status import StatusId

if TYPE_CHECKING:
    from sts2_lite.creature import Creature

WEAK_MULTIPLIER = 0.75
VULNERABLE_MULTIPLIER = 1.5
SHRINK_MULTIPLIER = 0.7


def modify_damage(base : int, attacker : Creature, target : Creature) -> int:
    # Strength, Weak, Vulnerable, then Shrink; truncated once at the end
    damage = base + attacker.status_amount(StatusId.STRENGTH)
    if StatusId.WEAK in attacker.status:
        damage *= WEAK_MULTIPLIER
    if StatusId.VULNERABLE in target.status:
        damage *= VULNERABLE_MULTIPLIER
    if StatusId.SHRINK in attacker.status:
        damage *= SHRINK_MULTIPLIER
    return max(0, int(damage))


def base_from_displayed(displayed : int, attacker : Creature, target : Creature) -> int:
    """Base damage that modify_damage turns into `displayed`.
    Truncation can map several bases to one value (only when the net multiplier
    is below 1); the largest is returned. Falls back to `displayed` if none match."""
    limit = 2 * displayed + abs(attacker.status_amount(StatusId.STRENGTH)) + 10
    for base in range(limit, -1, -1):
        if modify_damage(base, attacker, target) == displayed:
            return base
    return displayed
