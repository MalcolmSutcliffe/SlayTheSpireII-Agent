from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite.relic import RelicId, block_gained, block_multiplier, debuff_multiplier, poison_given
from sts2_lite.status import StatusId

from sts2_lite.card.constants import ENCHANT_CORRUPTED_DAMAGE, ENCHANT_EMBER_DAMAGE, ENCHANT_INSTINCT_DAMAGE, MAD_SCIENCE_DAMAGE
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
    if card is not None and card.card_id is CardId.SHIV:
        base += shiv_bonus(owner)
    recompute = None
    if hits > 1 and RelicId.HAND_DRILL in owner.relics:     # a broken block makes later hits Vulnerable
        recompute = lambda: combat.calculate_damage(base, owner, target)
    target.apply_attack_damage(combat.calculate_damage(base, owner, target), owner, hits, recompute)

def shiv_bonus(player) -> int:
    """AccuracyPower and PhantomBladesPower (ModifyDamageAdditive): Shivs hit harder; Phantom Blades only until a Shiv play has finished this turn."""
    status = player.status
    if StatusId.ACCURACY not in status and StatusId.PHANTOM_BLADES not in status:
        return 0
    bonus = player.status_amount(StatusId.ACCURACY)
    if player.shivs_played_this_turn == 0:
        bonus += player.status_amount(StatusId.PHANTOM_BLADES)
    return bonus

def apply_fresh(combat : CombatSimulator, target : Creature, status : StatusId, amount : int, debuff : bool = False):
    """A power that the card being played does not trigger (Strangle, Afterimage, Serpent Form note the amount at BeforeCardPlayed):
    records[0][0] holds what this play added (status.fresh_amount)."""
    before = target.status_amount(status)
    if debuff:
        _debuff(combat, target, status, amount)
    else:
        target.apply_status(status, amount)
    inst = target.status.get(status)
    added = target.status_amount(status) - before
    if inst is not None and added > 0 and combat.card_in_play is not None:
        inst.records = [[(inst.records[0][0] if inst.records else 0) + added]]

def apply_strangle(combat : CombatSimulator, target : Creature, amount : int):
    apply_fresh(combat, target, StatusId.STRANGLE, amount, debuff=True)

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

def _debuff(combat : CombatSimulator, target : Creature, status : StatusId, amount : int):
    """A debuff from the card being played (Unsettling Lamp doubles it)."""
    player = combat.combat_state.player
    if player.relics:
        if status is StatusId.POISON:
            amount = poison_given(player, amount)
        amount *= debuff_multiplier(player, combat.card_in_play, target)
    target.apply_status(status, amount)

def _weak(combat : CombatSimulator, target : Creature, amount : int):
    _debuff(combat, target, StatusId.WEAK, amount)

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
    CardId.BACKSTAB : (11, 15),
    CardId.DASH : (10, 13),
    CardId.ECHOING_SLASH : (10, 13),
    CardId.FINISHER : (6, 8),
    CardId.FLECHETTES : (5, 7),
    CardId.PINPOINT : (15, 19),
    CardId.POUNCE : (14, 20),
    CardId.SKEWER : (8, 11),
    CardId.STRANGLE : (8, 10),
    CardId.STRIKE_SILENT : (6, 9), CardId.STRIKE_REGENT : (6, 9), CardId.FALLING_STAR : (8, 12), CardId.SOVEREIGN_BLADE : (10, 10), CardId.MINION_STRIKE : (6, 9),
    CardId.ASTRAL_PULSE : (6, 8), CardId.CELESTIAL_MIGHT : (6, 6), CardId.COLLISION_COURSE : (10, 14), CardId.CRUSH_UNDER : (8, 9), CardId.GUIDING_STAR : (12, 13),
    CardId.PHOTON_CUT : (10, 13), CardId.SOLAR_STRIKE : (9, 10), CardId.WROUGHT_IN_WAR : (7, 9), CardId.MINION_DIVE_BOMB : (13, 16),
    CardId.DEVASTATE : (35, 45), CardId.GAMMA_BLAST : (13, 18), CardId.HEGEMONY : (15, 18), CardId.KINGLY_KICK : (27, 35), CardId.KINGLY_PUNCH : (8, 10),
    CardId.LUNAR_BLAST : (4, 5), CardId.RADIATE : (3, 4), CardId.SHINING_STRIKE : (8, 11), CardId.STARDUST : (5, 7), CardId.SUPERMASSIVE : (5, 5),
    CardId.BEAT_INTO_SHAPE : (5, 7), CardId.BOMBARDMENT : (18, 24), CardId.COMET : (33, 44), CardId.METEOR_SHOWER : (14, 21), CardId.SUPPRESS : (11, 17), CardId.CRASH_LANDING : (21, 26), CardId.DYING_STAR : (9, 11),
    CardId.HEAVENLY_DRILL : (8, 10), CardId.HEIRLOOM_HAMMER : (20, 25), CardId.MAKE_IT_SO : (6, 9), CardId.SEVEN_STARS : (7, 7), CardId.KNOCKOUT_BLOW : (30, 38), CardId.NEUTRALIZE : (3, 4), CardId.SHIV : (4, 6),
    CardId.DAGGER_SPRAY : (4, 6), CardId.DAGGER_THROW : (9, 12), CardId.FLICK_FLACK : (7, 9), CardId.LEADING_STRIKE : (3, 6),
    CardId.POISONED_STAB : (6, 8), CardId.PREDATOR : (15, 20), CardId.RICOCHET : (3, 3), CardId.SLICE : (6, 9), CardId.SUCKER_PUNCH : (8, 10),
    CardId.BYRD_SWOOP : (14, 18), CardId.CLASH : (14, 18), CardId.REBOUND : (9, 12), CardId.RIP_AND_TEAR : (7, 9), CardId.PECK : (2, 2), CardId.EXTERMINATE : (3, 4), CardId.SQUASH : (10, 12),
    CardId.ANGER : (6, 8), CardId.BASH : (8, 10), CardId.BLUDGEON : (32, 42), CardId.BREAK : (20, 30),
    CardId.BREAKTHROUGH : (9, 13), CardId.CINDER : (18, 24), CardId.CONFLAGRATION : (2, 2),
    CardId.DISMANTLE : (8, 10), CardId.FEED : (10, 12), CardId.FIEND_FIRE : (7, 10), CardId.FIGHT_ME : (5, 6),
    CardId.GIANT_ROCK : (20, 24), CardId.HEADBUTT : (9, 12), CardId.HEMOKINESIS : (15, 20),
    CardId.HOWL_FROM_BEYOND : (18, 24), CardId.IRON_WAVE : (5, 7), CardId.MANGLE : (20, 26),
    CardId.FISTICUFFS : (7, 9), CardId.FLASH_OF_STEEL : (5, 8), CardId.HAND_OF_GREED : (20, 25), CardId.OMNISLICE : (8, 11),
    CardId.ULTIMATE_STRIKE : (14, 20), CardId.SEEKER_STRIKE : (9, 12), CardId.VOLLEY : (10, 14), CardId.DRAMATIC_ENTRANCE : (11, 15),
    CardId.MAUL : (5, 6), CardId.WHISTLE : (33, 44), CardId.MOLTEN_FIST : (10, 14), CardId.NEOWS_FURY : (10, 14), CardId.PACTS_END : (18, 24), CardId.PILLAGE : (6, 9), CardId.POMMEL_STRIKE : (9, 10),
    CardId.BOLAS : (3, 4), CardId.SALVO : (12, 16), CardId.THRUMMING_HATCHET : (11, 14), CardId.JACKPOT : (25, 30),
    CardId.SETUP_STRIKE : (7, 9), CardId.SPITE : (5, 5), CardId.STOMP : (12, 15), CardId.STRIKE_IRONCLAD : (6, 9),
    CardId.SWORD_BOOMERANG : (3, 3), CardId.TEAR_ASUNDER : (5, 7), CardId.THUNDERCLAP : (4, 7),
    CardId.TWIN_STRIKE : (5, 7), CardId.UNRELENTING : (14, 20), CardId.UPPERCUT : (13, 13), CardId.WHIRLWIND : (5, 8),
}

SILENT_FIXED_DAMAGE = {CardId.ASSASSINATE : (10, 13), CardId.GRAND_FINALE : (60, 75), CardId.THE_HUNT : (10, 15)}      # damage of the Rares that print one number

def star_cost_cards(player : Player, in_play : Card | None = None) -> int:
    """Cards with a Star cost in the fight (CrescentSpear counts PlayerCombatState.AllCards: every pile, and the card being played)."""
    piles = player.hand + player.draw_pile + player.discard_pile + player.exhaust_pile
    return sum(c.star_cost is not None for c in piles) + (1 if in_play is not None and in_play.star_cost is not None else 0)

def crescent_spear_damage(player : Player, up : int, in_play : Card | None = None) -> int:
    return 8 + (3 if up else 2) * star_cost_cards(player, in_play)

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
        return 10 + card.bonus_damage
    if card.card_id == CardId.MAUL:
        return (6 if up else 5) + card.bonus_damage
    if card.card_id == CardId.THRASH:
        return (6 if up else 4) + card.bonus_damage
    if card.card_id == CardId.SOVEREIGN_BLADE:
        return 10 + card.bonus_damage
    if card.card_id == CardId.CRESCENT_SPEAR:
        return crescent_spear_damage(player, up)
    if card.card_id == CardId.KINGLY_PUNCH:
        return (10 if up else 8) + card.bonus_damage
    if card.card_id == CardId.SUPERMASSIVE:
        return 5 + (4 if up else 3) * player.cards_generated
    if card.card_id == CardId.MIND_BLAST:
        return len(player.draw_pile)
    if card.card_id == CardId.GOLD_AXE:
        return player.cards_played_total
    if card.card_id == CardId.REND:      # no target in the hand: the printed damage, without the bonus for the debuffs on a target
        return 12 if up else 10
    if card.card_id == CardId.MAD_SCIENCE:      # an Attack Mad Science: 12 a hit whatever its rider
        return MAD_SCIENCE_DAMAGE
    # the Silent's Attacks whose damage is worked out (CalculatedDamage.Calculate(null)) or printed once
    if card.card_id == CardId.MURDER:
        return 1 + player.cards_drawn
    if card.card_id == CardId.MEMENTO_MORI:
        return (11 + 5 * player.discards_this_turn) if up else (9 + 4 * player.discards_this_turn)
    if card.card_id == CardId.PRECISE_CUT:
        return max(0, (16 if up else 13) - 2 * len(player.hand))
    if card.card_id in SILENT_FIXED_DAMAGE:
        return SILENT_FIXED_DAMAGE[card.card_id][up]
    return PLAIN_DAMAGE[card.card_id][up]

###
### Card Functions, in alphabetical order
###

### Ancient cards that are not in the decompiled source: written from the cards' text
