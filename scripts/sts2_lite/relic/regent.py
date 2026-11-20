"""The Regent's relics that act in combat. Divine Right, Orange Dough and Fencing Manual act when the fight opens (combat_start.py)."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite.helpers import player_of
from sts2_lite.status import StatusId

if TYPE_CHECKING:
    from sts2_lite.card import Card
    from sts2_lite.relic.ids import RelicInstance

GALACTIC_DUST_STARS, GALACTIC_DUST_BLOCK = 10, 10
LUNAR_PASTRY_STARS = 1
MINI_REGENT_STRENGTH = 1
REGALITE_BLOCK = 4

def _galactic_dust(combat, relic : RelicInstance, spent : int):
    """GalacticDust.AfterStarsSpent: every 10 Stars spent give 10 Block (Unpowered)."""
    total = (relic.counter or 0) + spent
    if total >= GALACTIC_DUST_STARS:
        combat.gain_block(player_of(combat), total // GALACTIC_DUST_STARS * GALACTIC_DUST_BLOCK)
    relic.counter = total % GALACTIC_DUST_STARS

def _lunar_pastry(combat, relic : RelicInstance):
    """LunarPastry.AfterSideTurnEnd: a Star at the end of every turn."""
    combat.gain_stars(LUNAR_PASTRY_STARS)

def _mini_regent(combat, relic : RelicInstance, spent : int):
    """MiniRegent.AfterStarsSpent: the first Stars spent each turn give Strength."""
    if not relic.used:
        relic.used = True
        player_of(combat).apply_status(StatusId.STRENGTH, MINI_REGENT_STRENGTH)

def _regalite(combat, relic : RelicInstance, card : Card):
    """Regalite.AfterCardGeneratedForCombat: Block for the first card made up each turn."""
    if not relic.used:
        relic.used = True
        combat.gain_block(player_of(combat), REGALITE_BLOCK)

def _new_turn(combat, relic : RelicInstance):
    relic.used = False

def _vitruvian_minion_damage(relic : RelicInstance, card : Card | None, in_play : bool) -> int:
    """VitruvianMinion.ModifyDamageMultiplicative: the Minion cards (Minion Strike, Dive Bomb, Sacrifice) do double."""
    return 2 if card is not None and card.is_minion else 1

def _vitruvian_minion_block(relic : RelicInstance, card : Card | None) -> int:
    return 2 if card is not None and card.is_minion else 1
