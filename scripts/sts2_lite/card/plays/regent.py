"""The Regent's cards (RegentCardPool). Stars are spent by the play itself (Card.play_card -> CombatSimulator.spend_stars) before the effect runs."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite.helpers import enemy_at, living_enemies
from sts2_lite.status import StatusId

from sts2_lite.card.card import Card
from sts2_lite.card.effects import PLAIN_DAMAGE, _attack, _gain_block, _vulnerable, _weak
from sts2_lite.card.ids import CardId

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator


def _damage(card : Card, is_upgraded : bool) -> int:
    return PLAIN_DAMAGE[card.card_id][is_upgraded]

# ------------------------------------------------------------ Basic

def play_strike_regent(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_defend_regent(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)

def play_falling_star(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    if target.current_hp > 0:
        _weak(combat, target, 1)
        _vulnerable(combat, target, 1)

def play_venerate(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_stars(3 if is_upgraded else 2)

# ------------------------------------------------------------ Token

def play_sovereign_blade(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """10 damage plus everything Forge has added (SeekingEdge hits every enemy, Parry adds Block: later)."""
    _attack(combat, 10 + card.bonus_damage, enemy_at(combat, target_index))


REGENT_PLAYS = {
    CardId.STRIKE_REGENT : play_strike_regent,
    CardId.DEFEND_REGENT : play_defend_regent,
    CardId.FALLING_STAR : play_falling_star,
    CardId.VENERATE : play_venerate,
    CardId.SOVEREIGN_BLADE : play_sovereign_blade,
}
