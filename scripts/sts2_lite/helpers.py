"""Small lookups on a CombatSimulator that the card, potion and relic modules share."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.enemy import Enemy
    from sts2_lite.player import Player


def player_of(combat : CombatSimulator) -> Player:
    return combat.combat_state.player

def living_enemies(combat : CombatSimulator) -> list[Enemy]:
    return [e for e in combat.combat_state.enemies if e.current_hp > 0]

def enemy_at(combat : CombatSimulator, target_index : int) -> Enemy:
    if not 0 <= target_index < len(combat.combat_state.enemies):
        raise ValueError(f"Target index {target_index} out of bounds")
    return combat.combat_state.enemies[target_index]
