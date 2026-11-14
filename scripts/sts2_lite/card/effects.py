from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite.relic import RelicId, block_gained, block_multiplier, debuff_multiplier
from sts2_lite.status import StatusId

from sts2_lite.card.constants import ENCHANT_CORRUPTED_DAMAGE, ENCHANT_EMBER_DAMAGE, ENCHANT_INSTINCT_DAMAGE
from sts2_lite.card.ids import CardId, EnchantmentId
from sts2_lite.card.tables import DEFEND_CARDS

if TYPE_CHECKING:
    from sts2_lite.card.card import Card
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.creature import Creature
    from sts2_lite.player import Player

def _attack(combat : CombatSimulator, base : int, target : Creature, hits : int = 1):
    owner = combat.combat_state.player
    card = combat.card_in_play
    if card is not None and card.enchantment is not None:
        base = _enchanted_damage(card, base)
    base += combat.vigor_bonus()
    recompute = None
    if hits > 1 and RelicId.HAND_DRILL in owner.relics:     # a broken block makes later hits Vulnerable
        recompute = lambda: combat.calculate_damage(base, owner, target)
    target.apply_attack_damage(combat.calculate_damage(base, owner, target), owner, hits, recompute)

def _enchanted_damage(card : Card, base):
    """A card's damage enchantment, before Strength and the other modifiers (a float: Corrupted halves are kept)."""
    enchantment = card.enchantment
    if enchantment == EnchantmentId.CORRUPTED:
        return base * ENCHANT_CORRUPTED_DAMAGE
    if enchantment == EnchantmentId.INSTINCT:
        return base * ENCHANT_INSTINCT_DAMAGE
    if enchantment == EnchantmentId.SHARP or enchantment == EnchantmentId.VIGOROUS:
        return base + card.enchant_amount
    if enchantment == EnchantmentId.MOMENTUM:
        return base + card.enchant_bonus
    if enchantment == EnchantmentId.TEZCATARAS_EMBER:
        return base + ENCHANT_EMBER_DAMAGE
    return base

def owner_has_fasten(combat : CombatSimulator, card : Card | None) -> bool:
    """FastenPower.ModifyBlockAdditive: only Defends get the extra block."""
    return card is not None and card.card_id in DEFEND_CARDS and StatusId.FASTEN in combat.combat_state.player.status

def _gain_block(combat : CombatSimulator, base : int):
    card = combat.card_in_play
    if card is not None and card.enchantment == EnchantmentId.NIMBLE:      # adds to the card's own Block, before Dexterity and Frail
        base += card.enchant_amount
    elif card is not None and card.enchantment == EnchantmentId.GOOPY:    # printed block + permanent gains
        base += card.enchant_amount - 1
    if owner_has_fasten(combat, card):
        base += combat.combat_state.player.status_amount(StatusId.FASTEN)
    # Unmovable: doubled while gains from *other* plays this turn < amount (UnmovablePower)
    owner = combat.combat_state.player
    play = combat.play_id
    same_play = play is not None and owner.block_play == play
    from_other_plays = owner.card_blocks_this_turn - (owner.block_play_gains if same_play else 0)
    doubled = from_other_plays < owner.status_amount(StatusId.UNMOVABLE)
    owner.card_blocks_this_turn += 1
    if same_play:
        owner.block_play_gains += 1
    else:
        owner.block_play, owner.block_play_gains = play, 1
    multiplier = 2 if doubled else 1
    if card is not None and StatusId.NO_BLOCK in owner.status:      # NoBlockPower: block from cards (not unpowered block) is nothing
        multiplier = 0
    if owner.relics:
        multiplier *= block_multiplier(owner, combat.card_in_play)     # Vambrace
    block = combat.calculate_block(base, owner, multiplier)
    if owner.relics:
        block_gained(owner, combat.card_in_play, block)
    combat.gain_block(owner, block)
    return block

def _vulnerable(combat : CombatSimulator, target : Creature, amount : int):
    player = combat.combat_state.player
    before = target.status_amount(StatusId.VULNERABLE)
    if player.relics:
        amount *= debuff_multiplier(player, combat.card_in_play, target)      # Unsettling Lamp
    target.apply_status(StatusId.VULNERABLE, amount)
    if target.status_amount(StatusId.VULNERABLE) > before:      # Vicious: not if Artifact stopped it
        player.draw_cards(player.status_amount(StatusId.VICIOUS))

def temp_strength(target : Creature, marker : StatusId, amount : int, sign : int, combat : CombatSimulator | None = None):
    """Strength that is taken back when the target's turn ends (Setup Strike, Mangle). `sign` is -1 for a loss."""
    if sign < 0 and combat is not None and combat.combat_state.player.relics:
        amount *= debuff_multiplier(combat.combat_state.player, combat.card_in_play, target)      # Unsettling Lamp doubles the marker, which doubles the Strength it takes
    before = target.status_amount(marker)
    target.apply_status(marker, amount)
    if target.status_amount(marker) == before:          # Artifact stopped the debuff
        return
    target.apply_status(StatusId.STRENGTH, sign * amount, bypass_artifact=True)

PLAIN_DAMAGE = {        # id : (damage, damage upgraded) of the cards that print one fixed number
    CardId.BYRD_SWOOP : (14, 18), CardId.PECK : (2, 2), CardId.EXTERMINATE : (3, 4), CardId.SQUASH : (10, 12),
    CardId.ANGER : (6, 8), CardId.BASH : (8, 10), CardId.BLUDGEON : (32, 42), CardId.BREAK : (20, 30),
    CardId.BREAKTHROUGH : (9, 13), CardId.CINDER : (18, 24), CardId.CONFLAGRATION : (2, 2),
    CardId.DISMANTLE : (8, 10), CardId.FEED : (10, 12), CardId.FIEND_FIRE : (7, 10), CardId.FIGHT_ME : (5, 6),
    CardId.GIANT_ROCK : (16, 20), CardId.HEADBUTT : (9, 12), CardId.HEMOKINESIS : (15, 20),
    CardId.HOWL_FROM_BEYOND : (16, 21), CardId.IRON_WAVE : (5, 7), CardId.MANGLE : (15, 20),
    CardId.FISTICUFFS : (7, 9), CardId.FLASH_OF_STEEL : (5, 8), CardId.HAND_OF_GREED : (20, 25), CardId.OMNISLICE : (8, 11),
    CardId.ULTIMATE_STRIKE : (14, 20), CardId.SEEKER_STRIKE : (9, 12), CardId.VOLLEY : (10, 14), CardId.DRAMATIC_ENTRANCE : (11, 15),
    CardId.MAUL : (5, 6), CardId.WHISTLE : (33, 44), CardId.MOLTEN_FIST : (10, 14), CardId.NEOWS_FURY : (10, 14), CardId.PACTS_END : (17, 23), CardId.PILLAGE : (6, 9), CardId.POMMEL_STRIKE : (9, 10),
    CardId.BOLAS : (3, 4), CardId.SALVO : (12, 16), CardId.THRUMMING_HATCHET : (11, 14), CardId.JACKPOT : (25, 30),
    CardId.SETUP_STRIKE : (7, 9), CardId.SPITE : (5, 5), CardId.STOMP : (12, 15), CardId.STRIKE_IRONCLAD : (6, 9),
    CardId.SWORD_BOOMERANG : (3, 3), CardId.TEAR_ASUNDER : (5, 7), CardId.THUNDERCLAP : (4, 7),
    CardId.TWIN_STRIKE : (5, 7), CardId.UNRELENTING : (14, 20), CardId.UPPERCUT : (13, 13), CardId.WHIRLWIND : (5, 8),
}

def _strikes(player : Player, in_play : Card | None = None) -> int:
    """Perfected Strike counts every Strike the player has in the fight: hand, draw, discard and exhaust piles
    (so generated and exhausted Strikes count), plus the card being played, which is out of the hand."""
    piles = player.hand + player.draw_pile + player.discard_pile + player.exhaust_pile
    return sum(c.is_strike for c in piles) + (1 if in_play is not None and in_play.is_strike else 0)

def _printed_damage(card : Card, combat : CombatSimulator) -> int:
    """The base damage an Attack in the hand would print right now (Thrash adds this to itself)."""
    player = combat.combat_state.player
    up = 1 if card.is_upgraded else 0
    if card.card_id == CardId.ASHEN_STRIKE:
        return 6 + (4 if up else 3) * len(player.exhaust_pile)
    if card.card_id == CardId.BODY_SLAM:
        return player.block
    if card.card_id == CardId.BULLY:
        return 4
    if card.card_id == CardId.PERFECTED_STRIKE:
        return 6 + (3 if up else 2) * _strikes(player)
    if card.card_id == CardId.RAMPAGE:
        return 9 + card.bonus_damage
    if card.card_id == CardId.MAUL:
        return (6 if up else 5) + card.bonus_damage
    if card.card_id == CardId.THRASH:
        return (6 if up else 4) + card.bonus_damage
    if card.card_id == CardId.MIND_BLAST:
        return len(player.draw_pile)
    if card.card_id == CardId.GOLD_AXE:
        return player.cards_played_total
    if card.card_id == CardId.REND:      # no target in the hand: the printed damage, without the bonus for the debuffs on a target
        return 18 if up else 15
    return PLAIN_DAMAGE[card.card_id][up]

###
### Card Functions, in alphabetical order
###

### Ancient cards that are not in the decompiled source: written from the cards' text
