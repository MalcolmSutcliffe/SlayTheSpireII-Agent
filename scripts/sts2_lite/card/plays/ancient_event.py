from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.helpers import enemy_at, living_enemies
from sts2_lite.status import StatusId

from sts2_lite.card.card import Card
from sts2_lite.card.effects import PLAIN_DAMAGE, _attack, _gain_block, _vulnerable
from sts2_lite.card.ids import CardId, CardType
from sts2_lite.card.tables import GENERATABLE_CARDS, INFERNAL_BLADE_POOL

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator

def play_abundance(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # three different Powers, Upgraded; the one picked joins the hand for free this turn (the game's own three are adopted)
    powers = [cid for cid, (_, card_type, _, _) in GENERATABLE_CARDS.items() if card_type == CardType.Power]
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
    player.lose_max_hp(1)

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
    made = [Card.create_generated(rng.choice(INFERNAL_BLADE_POOL)).free_this_combat()
            for _ in range(METAMORPHOSIS_CARDS[is_upgraded])]
    for new_card in made:
        combat.combat_state.player.insert_into_draw_pile(new_card)

def play_toric_toughness(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Block now; the power gains that same (already modified) block, unpowered, after the block is cleared for 2 turns."""
    block = _gain_block(combat, 7 if is_upgraded else 5)
    combat.combat_state.player.add_instance(StatusId.TORIC_TOUGHNESS, [TORIC_TOUGHNESS_TURNS, block])


ANCIENT_EVENT_PLAYS = {
    CardId.ABUNDANCE : play_abundance,
    CardId.APOTHEOSIS : play_apotheosis,
    CardId.APPARITION : play_apparition,
    CardId.BRIGHTEST_FLAME : play_brightest_flame,
    CardId.BYRD_SWOOP : play_byrd_swoop,
    CardId.ENLIGHTENMENT : play_enlightenment,
    CardId.EXTERMINATE : play_exterminate,
    CardId.GIANT_ROCK : play_giant_rock,
    CardId.LUMINESCE : play_luminesce,
    CardId.MAUL : play_maul,
    CardId.METAMORPHOSIS : play_metamorphosis,
    CardId.PECK : play_peck,
    CardId.RELAX : play_relax,
    CardId.SQUASH : play_squash,
    CardId.TORIC_TOUGHNESS : play_toric_toughness,
    CardId.WHISTLE : play_whistle,
    CardId.WISH : play_wish,
}
