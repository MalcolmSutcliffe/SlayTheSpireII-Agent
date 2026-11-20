"""The Necrobinder's relics that act in combat. Bound Phylactery / Phylactery Unbound summon every turn (the first summon of a fight, Big Hat and Funerary Mask
are in combat_start.py); Bone Flute and Book Repair Knife are in necrobinder.py; Undying Sigil is in damage.py."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.helpers import player_of
from sts2_lite.necrobinder import summon

if TYPE_CHECKING:
    from sts2_lite.card import Card
    from sts2_lite.relic.ids import RelicInstance

BOUND_PHYLACTERY_SUMMON = 1
PHYLACTERY_UNBOUND_COMBAT, PHYLACTERY_UNBOUND_TURN = 5, 2
IVORY_TILE_THRESHOLD, IVORY_TILE_ENERGY = 3, 1

def _bound_phylactery(combat, relic : RelicInstance):
    """BoundPhylactery.AfterEnergyResetLate: from the second turn on."""
    if combat.combat_state.player_turn != 1:
        summon(player_of(combat), BOUND_PHYLACTERY_SUMMON)

def _phylactery_unbound(combat, relic : RelicInstance):
    """PhylacteryUnbound.AfterSideTurnStart: every turn."""
    summon(player_of(combat), PHYLACTERY_UNBOUND_TURN)

def _ivory_tile(combat, relic : RelicInstance, card : Card):
    if combat.last_energy_paid >= IVORY_TILE_THRESHOLD:
        combat.gain_energy(IVORY_TILE_ENERGY)

def _bookmark(combat, relic : RelicInstance):
    """Bookmark.AfterFlush: a random retained card that costs energy is 1 cheaper until played."""
    player = player_of(combat)
    options = [i for i, c in enumerate(player.hand) if c.energy_cost != "X" and c.current_cost(player) > 0]
    if options:
        i = rng.choice(options)
        player.hand[i] = player.hand[i].cheaper_until_played(1)
