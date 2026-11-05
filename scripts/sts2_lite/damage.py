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


def modify_damage(base : int, attacker : Creature, target : Creature, card : Card | None = None) -> int:
    # Strength and relics add, then Weak, Vulnerable, Shrink and Slow multiply; truncated once at the end.
    # `card` is the card being played, which some relics care about (Strike Dummy). Relics also change Weak and Vulnerable.
    damage = base + attacker.status_amount(StatusId.STRENGTH)
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
        damage *= damage_multiplier(attacker, card)         # Pen Nib
    if StatusId.COLOSSUS in target.status and StatusId.VULNERABLE in attacker.status:
        damage *= COLOSSUS_MULTIPLIER
    if StatusId.SHRINK in attacker.status:
        damage *= SHRINK_MULTIPLIER
    if StatusId.SLOW in target.status:
        damage *= 1 + target.status[StatusId.SLOW].amount / 100
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
