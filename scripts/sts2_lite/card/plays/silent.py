"""The Silent's cards (SilentCardPool)."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.helpers import enemy_at, living_enemies
from sts2_lite.status import StatusId

from sts2_lite.card.card import Card
from sts2_lite.card.effects import PLAIN_DAMAGE, _attack, _debuff, _gain_block, _weak, temp_strength
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


def _damage(card : Card, is_upgraded : bool) -> int:
    return PLAIN_DAMAGE[card.card_id][is_upgraded]

def _hit_all(combat : CombatSimulator, damage : int, times : int = 1):
    """TargetingAllOpponents, WithHitCount(times): every living enemy, once per hit."""
    for _ in range(times):
        for target in living_enemies(combat):
            _attack(combat, damage, target)
        combat.resolve_deaths()

# ------------------------------------------------------------ Common

def play_anticipate(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """AnticipatePower (TemporaryDexterityPower): Dexterity until the end of the turn."""
    player = combat.combat_state.player
    amount = 4 if is_upgraded else 2
    player.apply_status(StatusId.ANTICIPATE, amount)
    player.apply_status(StatusId.DEXTERITY, amount)

def play_backflip(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)
    combat.combat_state.player.draw_cards(2)

def play_blade_dance(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.create_shivs(4 if is_upgraded else 3)

def play_cloak_and_dagger(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 6)
    combat.create_shivs(2 if is_upgraded else 1)

def play_dagger_spray(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit_all(combat, _damage(card, is_upgraded), 2)

def play_dagger_throw(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.resolve_deaths()
    combat.combat_state.player.draw_cards(1)
    combat.request_discard(1)

def play_deadly_poison(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _debuff(combat, enemy_at(combat, target_index), StatusId.POISON, 7 if is_upgraded else 5)

def play_deflect(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 7 if is_upgraded else 4)

def play_dodge_and_roll(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """The block actually gained comes again next turn (BlockNextTurnPower)."""
    gained = _gain_block(combat, 6 if is_upgraded else 4)
    if gained > 0:
        combat.combat_state.player.apply_status(StatusId.BLOCK_NEXT_TURN, gained)

def play_flick_flack(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit_all(combat, _damage(card, is_upgraded))

def play_leading_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.create_shivs(2)

def play_piercing_wail(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """PiercingWailPower (TemporaryStrengthPower, negative): every enemy loses Strength until the end of its turn."""
    for target in living_enemies(combat):
        temp_strength(target, StatusId.PIERCING_WAIL, 8 if is_upgraded else 6, -1, combat)

def play_poisoned_stab(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    _debuff(combat, target, StatusId.POISON, 4 if is_upgraded else 3)

def play_predator(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.combat_state.player.apply_status(StatusId.DRAW_CARDS_NEXT_TURN, 2)

def play_prepared(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    count = 2 if is_upgraded else 1
    combat.combat_state.player.draw_cards(count)
    combat.request_discard(count)

def play_ricochet(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """TargetingRandomOpponents: each hit picks a living enemy at random."""
    for _ in range(5 if is_upgraded else 4):
        living = living_enemies(combat)
        if not living:
            break
        _attack(combat, _damage(card, is_upgraded), rng.pick_target(living))
        combat.resolve_deaths()

def play_snakebite(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _debuff(combat, enemy_at(combat, target_index), StatusId.POISON, 10 if is_upgraded else 7)

def play_sucker_punch(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    _weak(combat, target, 2 if is_upgraded else 1)

def play_untouchable(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 9 if is_upgraded else 6)


SILENT_PLAYS = {
    CardId.DEFEND_SILENT : play_defend_silent,
    CardId.NEUTRALIZE : play_neutralize,
    CardId.SHIV : _plain_attack,
    CardId.STRIKE_SILENT : _plain_attack,
    CardId.SURVIVOR : play_survivor,
    CardId.ANTICIPATE : play_anticipate,
    CardId.BACKFLIP : play_backflip,
    CardId.BLADE_DANCE : play_blade_dance,
    CardId.CLOAK_AND_DAGGER : play_cloak_and_dagger,
    CardId.DAGGER_SPRAY : play_dagger_spray,
    CardId.DAGGER_THROW : play_dagger_throw,
    CardId.DEADLY_POISON : play_deadly_poison,
    CardId.DEFLECT : play_deflect,
    CardId.DODGE_AND_ROLL : play_dodge_and_roll,
    CardId.FLICK_FLACK : play_flick_flack,
    CardId.LEADING_STRIKE : play_leading_strike,
    CardId.PIERCING_WAIL : play_piercing_wail,
    CardId.POISONED_STAB : play_poisoned_stab,
    CardId.PREDATOR : play_predator,
    CardId.PREPARED : play_prepared,
    CardId.RICOCHET : play_ricochet,
    CardId.SLICE : _plain_attack,
    CardId.SNAKEBITE : play_snakebite,
    CardId.SUCKER_PUNCH : play_sucker_punch,
    CardId.UNTOUCHABLE : play_untouchable,
}
