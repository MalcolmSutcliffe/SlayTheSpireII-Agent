from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.helpers import enemy_at, living_enemies
from sts2_lite.relic import debuff_multiplier
from sts2_lite.status import StatusId

from sts2_lite.card.card import Card
from sts2_lite.card.effects import PLAIN_DAMAGE, _attack, _gain_block, _vulnerable, temp_strength, apply_strangle
from sts2_lite.card.constants import MAD_SCIENCE_BLOCK, MAD_SCIENCE_DAMAGE
from sts2_lite.card.ids import CardId, CardType
from sts2_lite.card.tables import combat_pool

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator

def play_abundance(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # three different Powers, Upgraded; the one picked joins the hand for free this turn (the game's own three are adopted)
    powers = combat_pool(combat.combat_state.player.character, CardType.Power)
    combat.request_discovery([Card.create_generated(cid, True) for cid in rng.sample(powers, min(3, len(powers)))])

def play_apotheosis(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    for pile in (player.hand, player.draw_pile, player.discard_pile, player.exhaust_pile):
        for i, c in enumerate(pile):
            if c.is_upgradable:
                pile[i] = c.upgraded_copy()         # in place: a known top card stays where it is

def play_apparition(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.INTANGIBLE, 1)

def play_brightest_flame(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    amount = 3 if is_upgraded else 2
    combat.gain_energy(amount)
    player.draw_cards(amount)
    player.lose_max_hp(2)

def play_maul(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # `card` is this play's own copy; every Maul of the fight grows, in every pile
    target = enemy_at(combat, target_index)
    _attack(combat, (6 if is_upgraded else 5) + card.bonus_damage, target, 2)
    step = 3 if is_upgraded else 2
    card.bonus_damage += step
    player = combat.combat_state.player
    for pile in (player.hand, player.draw_pile, player.discard_pile, player.exhaust_pile):
        for c in pile:
            if c.card_id == CardId.MAUL:
                c.bonus_damage += step

def play_relax(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 18 if is_upgraded else 16)
    player = combat.combat_state.player
    player.apply_status(StatusId.ENERGY_NEXT_TURN, 3 if is_upgraded else 2)
    player.apply_status(StatusId.DRAW_CARDS_NEXT_TURN, 3 if is_upgraded else 2)

def play_whistle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
    if target.current_hp > 0:
        target.stun()           # the move it was about to make comes after the stun

def play_wish(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    draw = combat.combat_state.player.draw_pile
    combat.request_choice("draw_to_hand", list(range(len(draw))), pile="draw")

def play_giant_rock(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 20 if is_upgraded else 16, target)

def play_luminesce(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_energy(3 if is_upgraded else 2)

# ---- event cards
TORIC_TOUGHNESS_TURNS = 2

METAMORPHOSIS_CARDS = (3, 5)

ENLIGHTENMENT_COST = 1

def play_byrd_swoop(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index))

def play_peck(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index), 4 if is_upgraded else 3)

def play_exterminate(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for _ in range(4):                  # each hit goes to every living enemy
        for target in living_enemies(combat):
            _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
        combat.resolve_deaths()

def play_squash(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
    _vulnerable(combat, target, 3 if is_upgraded else 2)

def play_enlightenment(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Cards in hand (this one is in play, not in hand): cost reduced to 1 this turn, or this combat if upgraded."""
    hand = combat.combat_state.player.hand
    for i, c in enumerate(hand):
        hand[i] = c.reduced_to(ENLIGHTENMENT_COST, this_combat=is_upgraded)

def play_metamorphosis(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """CardFactory.GetForCombat (repeats allowed): random Attacks from the pool, free this combat, each at a random place
    in the draw pile."""
    attacks = combat_pool(combat.combat_state.player.character, CardType.Attack)
    made = [Card.create_generated(rng.choice(attacks)).free_this_combat()
            for _ in range(METAMORPHOSIS_CARDS[is_upgraded])]
    for new_card in made:
        combat.combat_state.player.insert_into_draw_pile(new_card)

def play_toric_toughness(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Block now; the power gains that same (already modified) block, unpowered, after the block is cleared for 2 turns."""
    block = _gain_block(combat, 7 if is_upgraded else 5)
    combat.combat_state.player.add_instance(StatusId.TORIC_TOUGHNESS, [TORIC_TOUGHNESS_TURNS, block])

FEEDING_FRENZY_STRENGTH = (5, 7)

def play_feeding_frenzy(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    temp_strength(combat.combat_state.player, StatusId.FEEDING_FRENZY, FEEDING_FRENZY_STRENGTH[bool(is_upgraded)], 1)


# --- Trash Heap's cards
def play_clash(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index))      # playable only while the hand holds nothing but Attacks (Card.can_play_card)

def play_dual_wield(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    hand = combat.combat_state.player.hand
    combat.request_choice("dual_wield", [i for i, c in enumerate(hand) if c.type in (CardType.Attack, CardType.Power)], amount=2 if is_upgraded else 1)

def play_entrench(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if player.block > 0:
        combat.gain_block(player, player.block)         # Unpowered: Dexterity and Frail do not touch it

def play_caltrops(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.THORNS, 5 if is_upgraded else 3)

def play_distraction(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    skills = combat_pool(combat.combat_state.player.character, CardType.Skill)
    combat.combat_state.player.add_to_hand(Card.create_generated(rng.choice(skills)).free_this_turn())

def play_outmaneuver(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.ENERGY_NEXT_TURN, 3 if is_upgraded else 2)

def play_hello_world(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.HELLO_WORLD, 1)

def play_rebound(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index))
    combat.combat_state.player.apply_status(StatusId.REBOUND, 1)

def play_rip_and_tear(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for _ in range(2):
        living = living_enemies(combat)
        if not living:
            break
        _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], rng.pick_target(living))
        combat.resolve_deaths()

def play_stack(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, (3 if is_upgraded else 0) + len(combat.combat_state.player.discard_pile))


MAD_SCIENCE_WEAK, MAD_SCIENCE_VULNERABLE, MAD_SCIENCE_HITS, MAD_SCIENCE_STRANGLE = 2, 2, 3, 6
MAD_SCIENCE_ENERGY, MAD_SCIENCE_DRAW, MAD_SCIENCE_STAT = 2, 3, 2


def _debuff(combat : CombatSimulator, target, status : StatusId, amount : int):
    player = combat.combat_state.player
    target.apply_status(status, amount * debuff_multiplier(player, combat.card_in_play, target) if player.relics else amount)


def _curious_discount(player):
    """Curious: every Power in every pile costs 1 less (the card is replaced: piles share their cards between states)."""
    for pile in (player.hand, player.draw_pile, player.discard_pile):
        for i, c in enumerate(pile):
            if c.type == CardType.Power and c.energy_cost != "X" and c.energy_cost > 0:
                cheaper = Card.create_copy(c)
                cheaper.energy_cost = c.energy_cost - 1
                if c.restore_cost is not None:
                    cheaper.restore_cost = max(0, c.restore_cost - 1)
                pile[i] = cheaper


def play_mad_science(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Tinker Time's card: a 12 damage Attack, an 8 Block Skill or a Power, plus the rider the player picked."""
    player = combat.combat_state.player
    rider = card.rider
    if card.type == CardType.Attack:
        target = enemy_at(combat, target_index)
        _attack(combat, MAD_SCIENCE_DAMAGE, target, MAD_SCIENCE_HITS if rider == "VIOLENCE" else 1)
        if rider == "SAPPING":
            _debuff(combat, target, StatusId.WEAK, MAD_SCIENCE_WEAK)
            _vulnerable(combat, target, MAD_SCIENCE_VULNERABLE)
        elif rider == "CHOKING" and target.current_hp > 0:
            apply_strangle(combat, target, MAD_SCIENCE_STRANGLE)
    elif card.type == CardType.Skill:
        _gain_block(combat, MAD_SCIENCE_BLOCK)
        if rider == "ENERGIZED":
            combat.gain_energy(MAD_SCIENCE_ENERGY)
        elif rider == "WISDOM":
            player.draw_cards(MAD_SCIENCE_DRAW)
        elif rider == "CHAOS":
            player.add_to_hand(Card.create_generated(rng.choice(combat_pool(player.character))).free_this_turn())
    else:
        if rider == "EXPERTISE":
            player.apply_status(StatusId.STRENGTH, MAD_SCIENCE_STAT)
            player.apply_status(StatusId.DEXTERITY, MAD_SCIENCE_STAT)
        elif rider == "CURIOUS":
            player.apply_status(StatusId.CURIOUS, 1)
            _curious_discount(player)
        elif rider == "IMPROVEMENT":
            player.apply_status(StatusId.IMPROVEMENT, 1)


ANCIENT_EVENT_PLAYS = {
    CardId.ABUNDANCE : play_abundance,
    CardId.APOTHEOSIS : play_apotheosis,
    CardId.APPARITION : play_apparition,
    CardId.BRIGHTEST_FLAME : play_brightest_flame,
    CardId.BYRD_SWOOP : play_byrd_swoop,
    CardId.ENLIGHTENMENT : play_enlightenment,
    CardId.EXTERMINATE : play_exterminate,
    CardId.FEEDING_FRENZY : play_feeding_frenzy,
    CardId.GIANT_ROCK : play_giant_rock,
    CardId.LUMINESCE : play_luminesce,
    CardId.MAD_SCIENCE : play_mad_science,
    CardId.CLASH : play_clash, CardId.DUAL_WIELD : play_dual_wield, CardId.ENTRENCH : play_entrench, CardId.CALTROPS : play_caltrops,
    CardId.DISTRACTION : play_distraction, CardId.OUTMANEUVER : play_outmaneuver, CardId.HELLO_WORLD : play_hello_world,
    CardId.REBOUND : play_rebound, CardId.RIP_AND_TEAR : play_rip_and_tear, CardId.STACK : play_stack,
    CardId.MAUL : play_maul,
    CardId.METAMORPHOSIS : play_metamorphosis,
    CardId.PECK : play_peck,
    CardId.RELAX : play_relax,
    CardId.SQUASH : play_squash,
    CardId.TORIC_TOUGHNESS : play_toric_toughness,
    CardId.WHISTLE : play_whistle,
    CardId.WISH : play_wish,
}
