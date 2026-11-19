"""The Regent's cards (RegentCardPool). Stars are spent by the play itself (Card.play_card -> CombatSimulator.spend_stars) before the effect runs."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite.helpers import enemy_at, living_enemies
from sts2_lite.status import StatusId

from sts2_lite.card.card import Card
from sts2_lite.card.effects import PLAIN_DAMAGE, _attack, _gain_block, _vulnerable, _weak, crescent_spear_damage, temp_strength
from sts2_lite.card.ids import CardId
from sts2_lite.card.plays.silent import _hit_all

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


def play_minion_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.combat_state.player.draw_cards(1)

def play_debris(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    pass

# ------------------------------------------------------------ Common

def play_astral_pulse(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit_all(combat, _damage(card, is_upgraded), 2)

def play_begone(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """A card of the hand is transformed into a Minion Strike (upgraded when Begone is)."""
    hand = combat.combat_state.player.hand
    combat.request_choice("begone", list(range(len(hand))), "hand", 1 if is_upgraded else 0)

def play_celestial_might(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index), 4 if is_upgraded else 3)

def play_cloak_of_stars(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 10 if is_upgraded else 7)

def play_collision_course(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.combat_state.player.add_to_hand(Card.create(CardId.DEBRIS))

def play_cosmic_indifference(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 9 if is_upgraded else 6)
    combat.request_choice("to_draw_pile", list(range(len(combat.combat_state.player.discard_pile))), pile="discard")

def play_crescent_spear(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """8 plus 2 (3) for every card with a Star cost the player has in the fight, this one included."""
    _attack(combat, crescent_spear_damage(combat.combat_state.player, 1 if is_upgraded else 0, card), enemy_at(combat, target_index))

def play_crush_under(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Every enemy loses Strength until the end of their turn (CrushUnderPower)."""
    enemies = living_enemies(combat)
    _hit_all(combat, _damage(card, is_upgraded))
    for enemy in enemies:
        if enemy.current_hp > 0:
            temp_strength(enemy, StatusId.CRUSH_UNDER, 2 if is_upgraded else 1, -1, combat)

def play_gather_light(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 11 if is_upgraded else 8)
    combat.gain_stars(1)

def play_glitterstream(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """The next turn's Block is worked out now (Hook.ModifyBlock: Dexterity and Frail), then comes as BlockNextTurnPower."""
    player = combat.combat_state.player
    next_turn = combat.calculate_block(7 if is_upgraded else 5, player)
    _gain_block(combat, 13 if is_upgraded else 11)
    if next_turn > 0:
        player.apply_status(StatusId.BLOCK_NEXT_TURN, next_turn)

def play_glow(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    combat.gain_stars(2 if is_upgraded else 1)
    player.draw_cards(1)
    player.apply_status(StatusId.DRAW_CARDS_NEXT_TURN, 1)

def play_guiding_star(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.combat_state.player.apply_status(StatusId.DRAW_CARDS_NEXT_TURN, 3 if is_upgraded else 2)

def play_hidden_cache(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_stars(1)
    combat.combat_state.player.apply_status(StatusId.STAR_NEXT_TURN, 4 if is_upgraded else 3)

def play_know_thy_place(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _weak(combat, target, 1)
    _vulnerable(combat, target, 1)

def play_patter(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 10 if is_upgraded else 8)
    combat.combat_state.player.apply_status(StatusId.VIGOR, 3 if is_upgraded else 2)

def play_photon_cut(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    player.draw_cards(2 if is_upgraded else 1)
    combat.request_choice("to_draw_pile", list(range(len(player.hand))), pile="hand")

def play_refine_blade(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.forge(12 if is_upgraded else 8, card)
    combat.combat_state.player.apply_status(StatusId.ENERGY_NEXT_TURN, 1)

def play_solar_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.gain_stars(2 if is_upgraded else 1)

def play_spoils_of_battle(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.forge(9 if is_upgraded else 6, card)
    combat.combat_state.player.draw_cards(2)

def play_wrought_in_war(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.forge(9 if is_upgraded else 7, card)


REGENT_PLAYS = {
    CardId.STRIKE_REGENT : play_strike_regent,
    CardId.DEFEND_REGENT : play_defend_regent,
    CardId.FALLING_STAR : play_falling_star,
    CardId.VENERATE : play_venerate,
    CardId.SOVEREIGN_BLADE : play_sovereign_blade,
    CardId.MINION_STRIKE : play_minion_strike,
    CardId.DEBRIS : play_debris,
    CardId.ASTRAL_PULSE : play_astral_pulse,
    CardId.BEGONE : play_begone,
    CardId.CELESTIAL_MIGHT : play_celestial_might,
    CardId.CLOAK_OF_STARS : play_cloak_of_stars,
    CardId.COLLISION_COURSE : play_collision_course,
    CardId.COSMIC_INDIFFERENCE : play_cosmic_indifference,
    CardId.CRESCENT_SPEAR : play_crescent_spear,
    CardId.CRUSH_UNDER : play_crush_under,
    CardId.GATHER_LIGHT : play_gather_light,
    CardId.GLITTERSTREAM : play_glitterstream,
    CardId.GLOW : play_glow,
    CardId.GUIDING_STAR : play_guiding_star,
    CardId.HIDDEN_CACHE : play_hidden_cache,
    CardId.KNOW_THY_PLACE : play_know_thy_place,
    CardId.PATTER : play_patter,
    CardId.PHOTON_CUT : play_photon_cut,
    CardId.REFINE_BLADE : play_refine_blade,
    CardId.SOLAR_STRIKE : play_solar_strike,
    CardId.SPOILS_OF_BATTLE : play_spoils_of_battle,
    CardId.WROUGHT_IN_WAR : play_wrought_in_war,
}
