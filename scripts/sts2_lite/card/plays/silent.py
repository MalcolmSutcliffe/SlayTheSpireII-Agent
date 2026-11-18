"""The Silent's cards (SilentCardPool)."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite.helpers import enemy_at

from sts2_lite.card.card import Card
from sts2_lite.card.effects import PLAIN_DAMAGE, _attack, _gain_block, _weak
from sts2_lite.card.ids import CardId

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator


def _plain_attack(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index))

def play_defend_silent(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)

def play_neutralize(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
    if target.current_hp > 0:
        _weak(combat, target, 2 if is_upgraded else 1)

def play_survivor(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 11 if is_upgraded else 8)
    combat.request_discard(1)


SILENT_PLAYS = {
    CardId.DEFEND_SILENT : play_defend_silent,
    CardId.NEUTRALIZE : play_neutralize,
    CardId.SHIV : _plain_attack,
    CardId.STRIKE_SILENT : _plain_attack,
    CardId.SURVIVOR : play_survivor,
}
