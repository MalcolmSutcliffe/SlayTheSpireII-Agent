from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite.status import StatusId

from sts2_lite.card.card import Card
from sts2_lite.card.ids import CardId

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator

def play_toxic(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    pass        # only its Exhaust keyword

def play_frantic_escape(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """One more turn before the Sandpit closes; every play costs one more energy for the rest of the fight."""
    for enemy in combat.combat_state.enemies:
        if StatusId.SANDPIT in enemy.status:
            enemy.status[StatusId.SANDPIT].amount += 1
    card.energy_cost += 1

def play_knowledge_curse(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    pass        # unplayable

def play_spore_mind(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    pass        # only its Exhaust keyword

def play_beckon(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    pass        # it does nothing; playing it only gets it out of the hand

def play_slimed(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.draw_card()


CURSE_STATUS_PLAYS = {
    CardId.BECKON : play_beckon,
    CardId.DISINTEGRATION : play_knowledge_curse,
    CardId.FRANTIC_ESCAPE : play_frantic_escape,
    CardId.MIND_ROT : play_knowledge_curse,
    CardId.SLIMED : play_slimed,
    CardId.SLOTH : play_knowledge_curse,
    CardId.SPORE_MIND : play_spore_mind,
    CardId.TOXIC : play_toxic,
    CardId.WASTE_AWAY : play_knowledge_curse,
}
