from __future__ import annotations
from typing import TYPE_CHECKING, Callable

from sts2_lite import rng
from sts2_lite.helpers import living_enemies, player_of
from sts2_lite.status import StatusId

from sts2_lite.relic.ids import BRILLIANT_SCARF_CARDS, FAN_EVERY, KUNAI_EVERY, KUSARIGAMA_EVERY, LETTER_OPENER_DAMAGE, LETTER_OPENER_EVERY, NUNCHAKU_EVERY, RelicId, RelicInstance, SHURIKEN_EVERY
from sts2_lite.relic.modifiers import PAELS_LEGION_COOLDOWN

if TYPE_CHECKING:
    from sts2_lite.card import Card
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.creature import Creature

VELVET_CHOKER_CARDS = 6

DIAMOND_DIADEM_CARDS = 2

def free_by_relic(owner : Creature) -> bool:
    """BrilliantScarf: the 5th card played (not auto-played) this turn costs 0."""
    scarf = owner.relics.get(RelicId.BRILLIANT_SCARF)
    return scarf is not None and _count(scarf) == BRILLIANT_SCARF_CARDS - 1

def blocks_play(owner : Creature) -> bool:
    """VelvetChoker.ShouldPlay: no cards after 6 in a turn (auto-plays too)."""
    choker = owner.relics.get(RelicId.VELVET_CHOKER)
    return choker is not None and _count(choker) >= VELVET_CHOKER_CARDS

def extra_plays(owner : Creature) -> int:
    """ThrowingAxe.ModifyCardPlayCount: the first card of the fight is played twice."""
    axe = owner.relics.get(RelicId.THROWING_AXE)
    if axe is None or axe.used:
        return 0
    axe.used = True
    return 1

# ---
# After a card has been played.
# ---
def _vambrace_card_played(relic : RelicInstance, card : Card):
    if relic.triggering is card:
        relic.used = True
        relic.triggering = None

def _lamp_card_played(relic : RelicInstance, card : Card):
    if relic.triggering is card:
        relic.used = True
        relic.triggering = None

def _paels_legion_card_played(relic : RelicInstance, card : Card):
    """PaelsLegion.AfterCardPlayed: the doubled play starts the Cooldown."""
    if relic.triggering is card:
        relic.counter = PAELS_LEGION_COOLDOWN
        relic.triggering = None

CARD_PLAYED : dict[RelicId, Callable[[RelicInstance, Card], None]] = {
    RelicId.VAMBRACE : _vambrace_card_played,
    RelicId.PAELS_LEGION : _paels_legion_card_played,
    RelicId.UNSETTLING_LAMP : _lamp_card_played,
}

def after_card_played(owner : Creature, card : Card):
    for relic_id, relic in owner.relics.items():
        if relic_id in CARD_PLAYED:
            CARD_PLAYED[relic_id](relic, card)

def release_card(owner : Creature):
    """A card play that failed leaves nothing for the relics to finish."""
    for relic in owner.relics.values():
        relic.triggering = None

# ---
# Relics that count what the player does. `counter` is the number the game shows; the bridge reports it, so a state loaded
# in the middle of a fight starts from the right count. Some have a per-turn flag in `used` and a bit set in `value`.
# ---
_TYPES = None       # (Attack, Skill, Power), loaded on first use: card.py imports this module

def _card_types():
    global _TYPES
    if _TYPES is None:
        from sts2_lite.card import CardType
        _TYPES = (CardType.Attack, CardType.Skill, CardType.Power)
    return _TYPES

def _count(relic : RelicInstance) -> int:
    return relic.counter or 0

def _hurt_all(combat : CombatSimulator, amount : int):
    """Damage that ignores Strength, Vulnerable and the like (the game's Unpowered damage)."""
    player = combat.combat_state.player
    for enemy in living_enemies(combat):
        enemy.apply_damage(amount, player)
    combat.resolve_deaths()

def _hurt_random(combat : CombatSimulator, amount : int):
    """Unpowered damage to one random hittable enemy (Rng.CombatTargets)."""
    living = living_enemies(combat)
    if living:
        (rng.pick_target(living)).apply_damage(amount, combat.combat_state.player)
        combat.resolve_deaths()

# --- before a card is played: function(combat, relic, card, energy_spent)
PEN_NIB_EVERY = 10

INTIMIDATING_HELMET_ENERGY = 2

INTIMIDATING_HELMET_BLOCK = 4

def _pen_nib_before(combat, relic, card, energy_spent):
    if card.type is not _card_types()[0]:
        return
    relic.counter = (_count(relic) + 1) % PEN_NIB_EVERY
    if relic.counter == 0:
        relic.triggering = card         # this Attack deals double damage

def _intimidating_helmet_before(combat, relic, card, energy_spent):
    if energy_spent >= INTIMIDATING_HELMET_ENERGY:
        combat.gain_block(combat.combat_state.player, INTIMIDATING_HELMET_BLOCK)

def _music_box_before(combat, relic, card, energy_spent):
    if relic.triggering is None and not relic.used and card.type is _card_types()[0]:
        relic.triggering = card

BEFORE_CARD_PLAYED : dict[RelicId, Callable] = {
    RelicId.MUSIC_BOX : _music_box_before,
    RelicId.PEN_NIB : _pen_nib_before,
    RelicId.INTIMIDATING_HELMET : _intimidating_helmet_before,
}

def before_card_played(combat : CombatSimulator, card : Card, energy_spent : int):
    for relic_id, relic in list(combat.combat_state.player.relics.items()):
        if relic_id in BEFORE_CARD_PLAYED:
            BEFORE_CARD_PLAYED[relic_id](combat, relic, card, energy_spent)

# --- damage multipliers: function(relic, card) -> factor
def _pen_nib_damage(relic : RelicInstance, card : Card | None, in_play : bool) -> int:
    """PenNib.ModifyDamageMultiplicative: doubles the triggering card, or a previewed card when the counter is 9."""
    if card is None:
        return 1
    if relic.triggering is None:
        return 2 if not in_play and _count(relic) == PEN_NIB_EVERY - 1 else 1
    return 2 if relic.triggering is card else 1

DAMAGE_MULTIPLIER : dict[RelicId, Callable[[RelicInstance, Card | None, bool], int]] = {
    RelicId.PEN_NIB : _pen_nib_damage,
}

def damage_multiplier(attacker : Creature, card : Card | None, in_play : bool = True) -> int:
    factor = 1
    for relic_id, relic in attacker.relics.items():
        if relic_id in DAMAGE_MULTIPLIER:
            factor *= DAMAGE_MULTIPLIER[relic_id](relic, card, in_play)
    return factor

# --- events: function(combat, relic, *args), the same arguments as the HookType they are registered for
def _every(relic : RelicInstance, limit : int) -> bool:
    """Count one more; true (and the count starts again) when `limit` is reached."""
    relic.counter = _count(relic) + 1
    if relic.counter >= limit:
        relic.counter -= limit
        return True
    return False

def _on_attack(handler):
    def run(combat, relic, card):
        if card.type is _card_types()[0]:
            handler(combat, relic)
    return run

def _on_skill(handler):
    def run(combat, relic, card):
        if card.type is _card_types()[1]:
            handler(combat, relic)
    return run

def _on_power(handler):
    def run(combat, relic, card):
        if card.type is _card_types()[2]:
            handler(combat, relic)
    return run

# Pen Nib
def _pen_nib_played(combat, relic, card):
    if relic.triggering is card:
        relic.triggering = None

KUSARIGAMA_DAMAGE, FAN_BLOCK = 6, 4

def _nunchaku(combat, relic):
    if _every(relic, NUNCHAKU_EVERY):
        combat.gain_energy(1)

def _kunai(combat, relic):
    if _every(relic, KUNAI_EVERY):
        player_of(combat).apply_status(StatusId.DEXTERITY, 1)

def _shuriken(combat, relic):
    if _every(relic, SHURIKEN_EVERY):
        player_of(combat).apply_status(StatusId.STRENGTH, 1)

def _kusarigama(combat, relic):
    if _every(relic, KUSARIGAMA_EVERY):
        _hurt_random(combat, KUSARIGAMA_DAMAGE)

def _ornamental_fan(combat, relic):
    if _every(relic, FAN_EVERY):
        combat.gain_block(player_of(combat), FAN_BLOCK)

TUNING_FORK_EVERY, TUNING_FORK_BLOCK = 10, 7

def _letter_opener(combat, relic):
    if _every(relic, LETTER_OPENER_EVERY):
        _hurt_all(combat, LETTER_OPENER_DAMAGE)

def _tuning_fork(combat, relic):
    if _every(relic, TUNING_FORK_EVERY):
        combat.gain_block(player_of(combat), TUNING_FORK_BLOCK)

# one of each type in a turn: bits of `value`, and `used` once it has paid out
SEEN_ATTACK, SEEN_SKILL, SEEN_POWER = 1, 2, 4

def _rainbow_ring(combat, relic, card):
    if relic.used:
        return
    attack, skill, power = _card_types()
    relic.value |= SEEN_ATTACK if card.type is attack else SEEN_SKILL if card.type is skill else SEEN_POWER if card.type is power else 0
    if relic.value == SEEN_ATTACK | SEEN_SKILL | SEEN_POWER:
        relic.used = True
        player_of(combat).apply_status(StatusId.STRENGTH, 1)
        player_of(combat).apply_status(StatusId.DEXTERITY, 1)

# every card played this turn
def _pocketwatch_played(combat, relic, card):
    relic.counter = _count(relic) + 1

POCKETWATCH_LIMIT, POCKETWATCH_DRAW = 3, 3

def _pocketwatch_turn(combat, relic):
    """Few cards last turn: draw more this turn (`value` is what the hand draw gets added)."""
    relic.value = POCKETWATCH_DRAW if _count(relic) <= POCKETWATCH_LIMIT and combat.combat_state.player_turn > 1 else 0     # nothing was played "last turn" on the first
    relic.counter = 0

HAND_DRAW_FIXED : dict[RelicId, int] = {RelicId.PAELS_BLOOD : 1, RelicId.SNECKO_EYE : 2, RelicId.FIDDLE : 2}

HAND_DRAW_SET = frozenset({RelicId.POCKETWATCH, RelicId.RING_OF_THE_DRAKE, RelicId.POLLINOUS_CORE})   # `value`, set at BEFORE_PLAYER_TURN

def hand_draw_bonus(owner : Creature) -> int:
    """Hook.ModifyHandDraw (all additive, so ModifyHandDrawLate order doesn't matter)."""
    bonus = 0
    for relic_id, relic in owner.relics.items():
        if relic_id in HAND_DRAW_FIXED:
            bonus += HAND_DRAW_FIXED[relic_id]
        elif relic_id in HAND_DRAW_SET:
            bonus += relic.value
    return bonus

def blocks_draw(owner : Creature) -> bool:
    """Fiddle.ShouldDraw: no draws outside the hand draw (the enemy-turn exception never draws in the sim)."""
    return RelicId.FIDDLE in owner.relics

RING_OF_THE_DRAKE_TURNS, RING_OF_THE_DRAKE_DRAW = 3, 2

POLLINOUS_CORE_TURNS, POLLINOUS_CORE_DRAW = 4, 2

def _ring_of_the_drake_turn(combat, relic):
    relic.value = RING_OF_THE_DRAKE_DRAW if combat.combat_state.player_turn <= RING_OF_THE_DRAKE_TURNS else 0

def _pollinous_core_turn(combat, relic):
    """TurnsSeen++ before the draw; +2 and reset at 4. Reads 4 while flashing, which is 0."""
    relic.counter = _count(relic) % POLLINOUS_CORE_TURNS + 1
    relic.value = 0
    if relic.counter == POLLINOUS_CORE_TURNS:
        relic.counter, relic.value = 0, POLLINOUS_CORE_DRAW

# an Attack played this turn: `used`
def _attack_seen(combat, relic):
    relic.used = True

ART_OF_WAR_ENERGY, RIPPLE_BASIN_BLOCK = 1, 4

def _art_of_war_turn(combat, relic):
    if not relic.used:                  # no Attack last turn
        combat.gain_energy(ART_OF_WAR_ENERGY)
    relic.used = False

def _ripple_basin_end(combat, relic):
    if not relic.used:
        combat.gain_block(player_of(combat), RIPPLE_BASIN_BLOCK)

# Powers
PERMAFROST_BLOCK = 7

def _permafrost(combat, relic):
    if not relic.used:
        relic.used = True
        combat.gain_block(player_of(combat), PERMAFROST_BLOCK)

def _game_piece(combat, relic):
    player_of(combat).draw_cards(1)

def _mummified_hand(combat, relic):
    """MummifiedHand.AfterCardPlayed: first non-empty of base>0 and costs now, costs now, base>0, any."""
    from sts2_lite.card import Card
    player = player_of(combat)
    hand = player.hand
    def base(c):
        cost = c.restore_cost if c.restore_cost is not None else c.energy_cost
        return 0 if cost == "X" else cost
    def now(c):
        cost = c.current_cost(player)
        return 0 if cost == "X" else cost
    candidates = ([i for i, c in enumerate(hand) if base(c) > 0 and now(c) > 0]
                  or [i for i, c in enumerate(hand) if now(c) > 0]
                  or [i for i, c in enumerate(hand) if base(c) > 0]
                  or list(range(len(hand))))
    if not candidates:
        return
    index = candidates[0] if len(candidates) == 1 else rng.choice(candidates)
    card = hand[index]
    if card.energy_cost == "X" or card.energy_cost == 0:
        return                  # already free
    hand[index] = card.free_this_turn()          # SetToFreeThisTurn

# Attacks and Skills
DAUGHTER_OF_THE_WIND_BLOCK = 1

def _daughter_of_the_wind(combat, relic, card):
    if card.type is _card_types()[0]:
        combat.gain_block(player_of(combat), DAUGHTER_OF_THE_WIND_BLOCK)

def upgraded_after_play(owner : Creature, card : Card) -> Card:
    """Razor Tooth upgrades an Attack or Skill the moment it has been played. Returns the card to put in its pile."""
    if RelicId.RAZOR_TOOTH not in owner.relics or card.type not in _card_types()[:2] or not card.is_upgradable:
        return card
    return owner.upgrade_card(card) or card.upgraded_copy()

# exhausting cards
JOSS_PAPER_EVERY, CHARONS_ASHES_DAMAGE = 5, 3

def _joss_paper_draw(combat, relic):
    draws, relic.counter = divmod(_count(relic), JOSS_PAPER_EVERY)
    if draws:
        player_of(combat).draw_cards(draws)

def _joss_paper_exhausted(combat, relic, card):
    if combat.ethereal_exhaust:
        return                          # counted once the hand has been discarded
    relic.counter = _count(relic) + 1
    _joss_paper_draw(combat, relic)

def _joss_paper_ethereal(combat, relic, count):
    relic.counter = _count(relic) + count
    _joss_paper_draw(combat, relic)

def _burning_sticks(combat, relic, card):
    if not relic.used and card.type is _card_types()[1]:
        from sts2_lite.card import Card
        relic.used = True
        player_of(combat).add_to_hand(Card.create_copy(card))

def _charons_ashes(combat, relic, card):
    _hurt_all(combat, CHARONS_ASHES_DAMAGE)

LOST_WISP_DAMAGE, FORGOTTEN_SOUL_DAMAGE = 8, 1

IRON_CLUB_EVERY = 4

def _lost_wisp(combat, relic):
    _hurt_all(combat, LOST_WISP_DAMAGE)

def _forgotten_soul(combat, relic, card):
    _hurt_random(combat, FORGOTTEN_SOUL_DAMAGE)

def _iron_club(combat, relic, card):
    """Counter = CardsPlayed % 4; reads 4 while flashing, which is 0."""
    relic.counter = _count(relic) % IRON_CLUB_EVERY + 1
    if relic.counter == IRON_CLUB_EVERY:
        relic.counter = 0
        player_of(combat).draw_cards(1)

def _music_box(combat, relic, card):
    """MusicBox: the first Attack each turn adds an Ethereal clone of itself to the hand."""
    if relic.triggering is card:
        from sts2_lite.card import Card, CardKeyword
        player_of(combat).add_to_hand(Card.create_copy(card).with_keyword(CardKeyword.ETHEREAL))
        relic.used = True
        relic.triggering = None

def _count_card(combat, relic, card):
    relic.counter = _count(relic) + 1

def _count_manual_card(combat, relic, card):
    if not combat.auto_playing:
        relic.counter = _count(relic) + 1

def _count_scarf(combat, relic, card):
    if not combat.auto_playing:
        relic.counter = min(_count(relic) + 1, BRILLIANT_SCARF_CARDS)      # the game stops counting at 5: the counter is hidden from then on

def _diamond_diadem(combat, relic):
    if _count(relic) <= DIAMOND_DIADEM_CARDS and StatusId.DIAMOND_DIADEM not in player_of(combat).status:
        player_of(combat).apply_status(StatusId.DIAMOND_DIADEM, 1)
    relic.counter = 0

def _reset_counter(combat, relic):
    relic.counter = 0

def _new_turn_rainbow(combat, relic):
    relic.value = 0
    relic.used = False

def _new_turn_flag(combat, relic):
    relic.used = False
