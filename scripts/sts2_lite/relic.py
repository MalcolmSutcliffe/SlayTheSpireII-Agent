from __future__ import annotations
from typing import TYPE_CHECKING, Callable

from enum import Enum, auto

from sts2_lite import rng
from sts2_lite.events import EventType, HandlerTable
from sts2_lite.status import StatusId

if TYPE_CHECKING:
    from sts2_lite.card import Card
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.creature import Creature
    from sts2_lite.player import Player


class RelicId(Enum):
    __hash__ = object.__hash__      # members are singletons; Enum.__hash__ is pure Python
    STRIKE_DUMMY = auto()
    MINIATURE_CANNON = auto()
    PAPER_PHROG = auto()
    PAPER_KRANE = auto()
    VAMBRACE = auto()
    TUNGSTEN_ROD = auto()
    BEATING_REMNANT = auto()
    RUINED_HELMET = auto()
    UNSETTLING_LAMP = auto()
    CHEMICAL_X = auto()
    ICE_CREAM = auto()
    RINGING_TRIANGLE = auto()
    STURDY_CLAMP = auto()
    LIZARD_TAIL = auto()
    PEN_NIB = auto()
    NUNCHAKU = auto()
    KUNAI = auto()
    SHURIKEN = auto()
    KUSARIGAMA = auto()
    LETTER_OPENER = auto()
    ORNAMENTAL_FAN = auto()
    TUNING_FORK = auto()
    RAINBOW_RING = auto()
    POCKETWATCH = auto()
    ART_OF_WAR = auto()
    RIPPLE_BASIN = auto()
    PERMAFROST = auto()
    GAME_PIECE = auto()
    MUMMIFIED_HAND = auto()
    RAZOR_TOOTH = auto()
    DAUGHTER_OF_THE_WIND = auto()
    INTIMIDATING_HELMET = auto()
    JOSS_PAPER = auto()
    BURNING_STICKS = auto()
    CHARONS_ASHES = auto()
    CANDELABRA = auto()
    CHANDELIER = auto()
    HAPPY_FLOWER = auto()
    CAPTAINS_WHEEL = auto()
    HORN_CLEAT = auto()
    SPARKLING_ROUGE = auto()
    MERCURY_HOURGLASS = auto()
    STONE_CALENDAR = auto()
    BRIMSTONE = auto()
    ORICHALCUM = auto()
    CLOAK_CLASP = auto()
    SCREAMING_FLAGON = auto()
    PARRYING_SHIELD = auto()
    CENTENNIAL_PUZZLE = auto()
    GREMLIN_HORN = auto()
    PENDULUM = auto()
    THE_ABACUS = auto()
    UNCEASING_TOP = auto()
    DEMON_TONGUE = auto()
    RED_SKULL = auto()
    SELF_FORMING_CLAY = auto()
    BREAD = auto()
    MEAT_ON_THE_BONE = auto()
    BURNING_BLOOD = auto()
    BLACK_BLOOD = auto()
    GHOST_SEED = auto()
    SAI = auto()
    MR_STRUGGLES = auto()
    PAELS_TEARS = auto()
    PAELS_FLESH = auto()
    LOST_WISP = auto()
    FORGOTTEN_SOUL = auto()
    IRON_CLUB = auto()
    HAND_DRILL = auto()
    THE_BOOT = auto()
    FAKE_ORICHALCUM = auto()
    FAKE_STRIKE_DUMMY = auto()
    FAKE_HAPPY_FLOWER = auto()
    PAELS_BLOOD = auto()
    RING_OF_THE_DRAKE = auto()
    POLLINOUS_CORE = auto()
    FIDDLE = auto()
    SNECKO_EYE = auto()
    BRILLIANT_SCARF = auto()
    VELVET_CHOKER = auto()
    THROWING_AXE = auto()
    MUSIC_BOX = auto()
    DIAMOND_DIADEM = auto()
    CROSSBOW = auto()
    BIIIG_HUG = auto()
    RUNIC_PYRAMID = auto()
    TOASTY_MITTENS = auto()
    HISTORY_COURSE = auto()
    SPIKED_GAUNTLETS = auto()
    PHILOSOPHERS_STONE = auto()
    SEAL_OF_GOLD = auto()
    PAELS_EYE = auto()
    PAELS_LEGION = auto()
    REPTILE_TRINKET = auto()
    BELT_BUCKLE = auto()


# What the bridge calls a relic's state (if it reports one) when `used` is true.
# The game marks Vambrace, Unsettling Lamp and Burning Sticks "Active" until they trigger, and a spent Lizard Tail "Disabled".
# Art of War and Ripple Basin are "Active" until an Attack is played in the turn; Rainbow Ring is "Active" once it has triggered.
# (Checked against the game source and saved states. A relic added by console in the middle of a fight stays "Normal" until its next reset.)
# Rainbow Ring also reports `types_played`, the bits of what it has seen this turn (see SEEN_ATTACK below).
USED_STATUS : dict[RelicId, frozenset[str]] = {
    RelicId.VAMBRACE : frozenset({"Normal"}),
    RelicId.UNSETTLING_LAMP : frozenset({"Normal"}),
    RelicId.LIZARD_TAIL : frozenset({"Disabled"}),
    RelicId.BURNING_STICKS : frozenset({"Normal"}),
    RelicId.ART_OF_WAR : frozenset({"Normal"}),
    RelicId.RIPPLE_BASIN : frozenset({"Normal"}),
    RelicId.RAINBOW_RING : frozenset({"Active"}),
    RelicId.RED_SKULL : frozenset({"Active"}),       # the Strength is on
    RelicId.THROWING_AXE : frozenset({"Normal"}),    # Active until the first card is played twice
}

# `used` of these means "this turn" (it is cleared when the next turn starts), so it is only carried within a turn.
PER_TURN_FLAG = frozenset({RelicId.ART_OF_WAR, RelicId.RIPPLE_BASIN, RelicId.RAINBOW_RING, RelicId.DEMON_TONGUE,
                           RelicId.MUSIC_BOX})

# The bridge reports these every time, so a state that was read is never overruled by one the simulator remembers.
ALWAYS_REPORTED = frozenset({RelicId.RED_SKULL})


class RelicInstance:
    relic_id : RelicId
    counter : int | None        # the number the game shows on the relic, for relics that count something
    used : bool                 # the effect that works once has been spent (Vambrace, Ruined Helmet, Unsettling Lamp, Lizard Tail)
    value : int                 # a total kept for the turn (damage taken so far, for Beating Remnant)
    triggering : Card | None    # the card whose effects the relic is still working on (Vambrace, Unsettling Lamp)

    def __init__(self, relic_id : RelicId, counter : int | None = None, used : bool = False, value : int = 0):
        self.relic_id = relic_id
        self.counter = counter
        self.used = used
        self.value = value
        self.triggering = None

    @classmethod
    def from_dict(cls, relic : dict) -> RelicInstance | None:
        """None for a relic that has no effect in combat (or is not modelled yet)."""
        relic_id = RelicId.__members__.get(relic["id"])
        if relic_id is None:
            return None
        used = relic.get("status") in USED_STATUS.get(relic_id, ()) or bool(relic.get("spent"))
        counter = relic.get("counter")
        if relic_id is RelicId.BRILLIANT_SCARF and counter is None:
            counter = BRILLIANT_SCARF_CARDS         # ShowCounter is false once 5 cards are played
        if counter is not None and counter == FLASHES_AT_FULL_COUNT.get(relic_id):
            counter = 0         # these relics show their full count while they flash, which is a reset to 0 (Letter Opener: until the next card is played)
        return cls(relic_id, counter, used, relic.get("types_played") or 0)

    @classmethod
    def deepcopy(cls, relic : RelicInstance) -> RelicInstance:
        new = cls(relic.relic_id, relic.counter, relic.used, relic.value)
        new.triggering = relic.triggering
        return new


# ---
# Damage: function(relic, card) -> extra damage. `card` is the card being played, None for damage that is not from a card.
# ---
STRIKE_DUMMY_BONUS = 3
FAKE_STRIKE_DUMMY_BONUS = 1
MINIATURE_CANNON_BONUS = 3

def _strike_dummy_damage(relic : RelicInstance, card : Card | None) -> int:
    return STRIKE_DUMMY_BONUS if card is not None and card.is_strike else 0

def _fake_strike_dummy_damage(relic : RelicInstance, card : Card | None) -> int:
    return FAKE_STRIKE_DUMMY_BONUS if card is not None and card.is_strike else 0

def _miniature_cannon_damage(relic : RelicInstance, card : Card | None) -> int:
    return MINIATURE_CANNON_BONUS if card is not None and card.is_upgraded else 0

DAMAGE_ADDITIVE : dict[RelicId, Callable[[RelicInstance, Card | None], int]] = {
    RelicId.STRIKE_DUMMY : _strike_dummy_damage,
    RelicId.FAKE_STRIKE_DUMMY : _fake_strike_dummy_damage,
    RelicId.MINIATURE_CANNON : _miniature_cannon_damage,
}


def damage_bonus(attacker : Creature, card : Card | None) -> int:
    """Extra damage the attacker's relics add to an attack from `card`."""
    relics = getattr(attacker, "relics", None)
    if not relics:
        return 0
    return sum(DAMAGE_ADDITIVE[relic_id](relic, card) for relic_id, relic in relics.items() if relic_id in DAMAGE_ADDITIVE)


# ---
# Vulnerable and Weak: a change to the multiplier the status applies.
# ---
VULNERABLE_BONUS : dict[RelicId, float] = {RelicId.PAPER_PHROG : 0.25}      # the attacker's relics: 1.5x becomes 1.75x
WEAK_PENALTY : dict[RelicId, float] = {RelicId.PAPER_KRANE : 0.15}          # the target's relics: a Weak attacker deals 0.6x

def vulnerable_bonus(attacker : Creature) -> float:
    return sum(bonus for relic_id, bonus in VULNERABLE_BONUS.items() if relic_id in attacker.relics)

def weak_multiplier(target : Creature, base : float) -> float:
    """What a Weak attacker's damage is multiplied by when it attacks `target`."""
    return round(base - sum(penalty for relic_id, penalty in WEAK_PENALTY.items() if relic_id in target.relics), 10)


# ---
# Block from a card: Vambrace doubles the block of the first card that gives any, once per fight.
# ---
def _vambrace_block(relic : RelicInstance, card : Card | None) -> int:
    if relic.used or card is None:
        return 1
    return 2 if relic.triggering is None or relic.triggering is card else 1

def _vambrace_block_gained(relic : RelicInstance, card : Card | None, amount : int):
    if not relic.used and card is not None and amount > 0 and relic.triggering is None:
        relic.triggering = card

# Pael's Legion: `counter` is the Cooldown (the bridge shows it while > 0); doubles card block while it is <= 0.
PAELS_LEGION_COOLDOWN = 2

def _paels_legion_block(relic : RelicInstance, card : Card | None) -> int:
    """PaelsLegion.ModifyBlockMultiplicative: x2 for own card block while Cooldown <= 0."""
    return 2 if card is not None and not relic.counter else 1

def _paels_legion_block_gained(relic : RelicInstance, card : Card | None, amount : int):
    """PaelsLegion.AfterModifyingBlockAmount: remember the first play it doubled."""
    if card is not None and amount > 0 and not relic.counter and relic.triggering is None:
        relic.triggering = card

BLOCK_MULTIPLIER : dict[RelicId, Callable[[RelicInstance, Card | None], int]] = {
    RelicId.VAMBRACE : _vambrace_block,
    RelicId.PAELS_LEGION : _paels_legion_block,
}
BLOCK_GAINED : dict[RelicId, Callable[[RelicInstance, Card | None, int], None]] = {
    RelicId.VAMBRACE : _vambrace_block_gained,
    RelicId.PAELS_LEGION : _paels_legion_block_gained,
}

def block_multiplier(owner : Creature, card : Card | None) -> int:
    multiplier = 1
    for relic_id, relic in owner.relics.items():
        if relic_id in BLOCK_MULTIPLIER:
            multiplier *= BLOCK_MULTIPLIER[relic_id](relic, card)
    return multiplier

def block_gained(owner : Creature, card : Card | None, amount : int):
    """The block a card has just given (after every multiplier)."""
    for relic_id, relic in owner.relics.items():
        if relic_id in BLOCK_GAINED:
            BLOCK_GAINED[relic_id](relic, card, amount)


# ---
# Debuffs a card puts on an enemy: Unsettling Lamp doubles every debuff of the first card that applies one, once per fight.
# ---
def debuff_multiplier(owner : Creature, card : Card | None, target : Creature) -> int:
    lamp = owner.relics.get(RelicId.UNSETTLING_LAMP)
    if lamp is None or lamp.used or card is None or target is owner or target.current_hp <= 0:
        return 1                    # a dead target is never debuffed, so it doesn't trigger the Lamp
    if lamp.triggering is None:
        lamp.triggering = card
    return 2 if lamp.triggering is card else 1


# ---
# Strength the player gains: Ruined Helmet doubles the first gain of the fight.
# ---
def strength_received(owner : Creature, amount : int) -> int:
    helmet = owner.relics.get(RelicId.RUINED_HELMET)
    if helmet is None or helmet.used:
        return amount
    helmet.used = True
    return amount * 2


# ---
# X-cost cards: added to the energy spent.
# ---
X_BONUS : dict[RelicId, int] = {RelicId.CHEMICAL_X : 2}

def x_bonus(owner : Creature) -> int:
    return sum(bonus for relic_id, bonus in X_BONUS.items() if relic_id in owner.relics)


# ---
# Hit points lost (after block): function(relic, amount) -> amount. They run in the order the relics are held.
# ---
TUNGSTEN_ROD_REDUCTION = 1
BEATING_REMNANT_LIMIT = 20      # per turn, counted from the start of the player's turn

def _tungsten_rod_loss(relic : RelicInstance, amount : int) -> int:
    return max(0, amount - TUNGSTEN_ROD_REDUCTION)

def _beating_remnant_loss(relic : RelicInstance, amount : int) -> int:
    return max(0, min(amount, BEATING_REMNANT_LIMIT - relic.value))

HP_LOSS : dict[RelicId, Callable[[RelicInstance, int], int]] = {
    RelicId.TUNGSTEN_ROD : _tungsten_rod_loss,
    RelicId.BEATING_REMNANT : _beating_remnant_loss,
}

def modify_hp_loss(owner : Creature, amount : int) -> int:
    for relic_id, relic in owner.relics.items():
        if relic_id in HP_LOSS:
            amount = HP_LOSS[relic_id](relic, amount)
    remnant = owner.relics.get(RelicId.BEATING_REMNANT)
    if remnant is not None:
        remnant.value += amount
    if amount > 0:
        owner.hp_lost_log.append(amount)        # the simulator tells the relics that react to it (CombatSimulator._sync_hp)
    return amount


# ---
# Block that survives the start of the owner's turn (Sturdy Clamp).
# ---
STURDY_CLAMP_BLOCK = 10


# ---
# Lizard Tail brings the owner back from death, once, at half its maximum hit points.
# ---
def lizard_tail_revive(owner : Creature) -> bool:
    tail = owner.relics.get(RelicId.LIZARD_TAIL)
    if tail is None or tail.used:
        return False
    tail.used = True
    owner.current_hp = max(1, owner.max_hp // 2)
    return True


# ---
# Damage the player deals (CreatureCmd.Damage, dealer = player).
# ---
THE_BOOT_MINIMUM = 5
HAND_DRILL_VULNERABLE = 2

def dealt_hp_loss(dealer : Creature, amount : int) -> int:
    """TheBoot.ModifyHpLostAfterOstyLate: powered attack HP loss in [1, 4] becomes 5."""
    if 0 < amount < THE_BOOT_MINIMUM and RelicId.THE_BOOT in dealer.relics:
        return THE_BOOT_MINIMUM
    return amount

def after_damage_given(dealer : Creature, target : Creature, block_broken : bool):
    """HandDrill.AfterDamageGiven: 2 Vulnerable on block break; no card source (no Lamp), applier is the player (Vicious)."""
    if block_broken and RelicId.HAND_DRILL in dealer.relics and target.current_hp > 0:
        before = target.status_amount(StatusId.VULNERABLE)
        target.apply_status(StatusId.VULNERABLE, HAND_DRILL_VULNERABLE)
        if target.status_amount(StatusId.VULNERABLE) > before:
            dealer.draw_cards(dealer.status_amount(StatusId.VICIOUS))


# ---
# Card play rules.
# ---
BRILLIANT_SCARF_CARDS = 5
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

def _living(combat : CombatSimulator):
    return [e for e in combat.combat_state.enemies if e.current_hp > 0]

def _hurt_all(combat : CombatSimulator, amount : int):
    """Damage that ignores Strength, Vulnerable and the like (the game's Unpowered damage)."""
    player = combat.combat_state.player
    for enemy in _living(combat):
        enemy.apply_damage(amount, player)
    combat.resolve_deaths()

def _hurt_random(combat : CombatSimulator, amount : int):
    """Unpowered damage to one random hittable enemy (Rng.CombatTargets)."""
    living = _living(combat)
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


# --- events: function(combat, relic, *args), the same arguments as the EventType they are registered for
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

def _player(combat):
    return combat.combat_state.player

# Pen Nib
def _pen_nib_played(combat, relic, card):
    if relic.triggering is card:
        relic.triggering = None

# every few Attacks
NUNCHAKU_EVERY, KUNAI_EVERY, SHURIKEN_EVERY, KUSARIGAMA_EVERY, FAN_EVERY = 10, 3, 3, 3, 3
KUSARIGAMA_DAMAGE, FAN_BLOCK = 6, 4

def _nunchaku(combat, relic):
    if _every(relic, NUNCHAKU_EVERY):
        combat.gain_energy(1)

def _kunai(combat, relic):
    if _every(relic, KUNAI_EVERY):
        _player(combat).apply_status(StatusId.DEXTERITY, 1)

def _shuriken(combat, relic):
    if _every(relic, SHURIKEN_EVERY):
        _player(combat).apply_status(StatusId.STRENGTH, 1)

def _kusarigama(combat, relic):
    if _every(relic, KUSARIGAMA_EVERY):
        _hurt_random(combat, KUSARIGAMA_DAMAGE)

def _ornamental_fan(combat, relic):
    if _every(relic, FAN_EVERY):
        combat.gain_block(_player(combat), FAN_BLOCK)

# every few Skills
LETTER_OPENER_EVERY, LETTER_OPENER_DAMAGE = 3, 5
TUNING_FORK_EVERY, TUNING_FORK_BLOCK = 10, 7

def _letter_opener(combat, relic):
    if _every(relic, LETTER_OPENER_EVERY):
        _hurt_all(combat, LETTER_OPENER_DAMAGE)

def _tuning_fork(combat, relic):
    if _every(relic, TUNING_FORK_EVERY):
        combat.gain_block(_player(combat), TUNING_FORK_BLOCK)

# one of each type in a turn: bits of `value`, and `used` once it has paid out
SEEN_ATTACK, SEEN_SKILL, SEEN_POWER = 1, 2, 4

def _rainbow_ring(combat, relic, card):
    if relic.used:
        return
    attack, skill, power = _card_types()
    relic.value |= SEEN_ATTACK if card.type is attack else SEEN_SKILL if card.type is skill else SEEN_POWER if card.type is power else 0
    if relic.value == SEEN_ATTACK | SEEN_SKILL | SEEN_POWER:
        relic.used = True
        _player(combat).apply_status(StatusId.STRENGTH, 1)
        _player(combat).apply_status(StatusId.DEXTERITY, 1)

# every card played this turn
def _pocketwatch_played(combat, relic, card):
    relic.counter = _count(relic) + 1

POCKETWATCH_LIMIT, POCKETWATCH_DRAW = 3, 3

def _pocketwatch_turn(combat, relic):
    """Few cards last turn: draw more this turn (`value` is what the hand draw gets added)."""
    relic.value = POCKETWATCH_DRAW if _count(relic) <= POCKETWATCH_LIMIT else 0
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
        combat.gain_block(_player(combat), RIPPLE_BASIN_BLOCK)

# Powers
PERMAFROST_BLOCK = 7

def _permafrost(combat, relic):
    if not relic.used:
        relic.used = True
        combat.gain_block(_player(combat), PERMAFROST_BLOCK)

def _game_piece(combat, relic):
    _player(combat).draw_cards(1)

def _mummified_hand(combat, relic):
    """MummifiedHand.AfterCardPlayed: first non-empty of base>0 and costs now, costs now, base>0, any."""
    from sts2_lite.card import Card
    player = _player(combat)
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
        combat.gain_block(_player(combat), DAUGHTER_OF_THE_WIND_BLOCK)

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
        _player(combat).draw_cards(draws)

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
        _player(combat).add_to_hand(Card.create_copy(card))

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
        _player(combat).draw_cards(1)

def _music_box(combat, relic, card):
    """MusicBox: the first Attack each turn adds an Ethereal clone of itself to the hand."""
    if relic.triggering is card:
        from sts2_lite.card import Card, CardKeyword
        _player(combat).add_to_hand(Card.create_copy(card).with_keyword(CardKeyword.ETHEREAL))
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
    if _count(relic) <= DIAMOND_DIADEM_CARDS and StatusId.DIAMOND_DIADEM not in _player(combat).status:
        _player(combat).apply_status(StatusId.DIAMOND_DIADEM, 1)
    relic.counter = 0

def _reset_counter(combat, relic):
    relic.counter = 0

def _new_turn_rainbow(combat, relic):
    relic.value = 0
    relic.used = False

def _new_turn_flag(combat, relic):
    relic.used = False


# --- relics that act on a particular turn, or on every turn after the first.
# A relic that only acts on turn 1 (Lantern, Akabeko, Anchor, Bag of Preparation...) is not modelled: its effect is already in
# the state the bridge gives us, and the simulation never plays turn 1 again.
def _turn(combat) -> int:
    """PlayerCombatState.TurnNumber (relics count player turns, not rounds)."""
    return combat.combat_state.player_turn

CANDELABRA_TURN, CANDELABRA_ENERGY = 2, 2
CHANDELIER_TURN, CHANDELIER_ENERGY = 3, 3
HAPPY_FLOWER_TURNS = {RelicId.HAPPY_FLOWER : 3, RelicId.FAKE_HAPPY_FLOWER : 5}
FLASHES_AT_FULL_COUNT = {**HAPPY_FLOWER_TURNS, RelicId.LETTER_OPENER : LETTER_OPENER_EVERY, RelicId.PENDULUM : 3, RelicId.NUNCHAKU : NUNCHAKU_EVERY}    # Pendulum: DisplayAmount is Turns while it activates; Nunchaku shows 10 after the tenth Attack, which has already paid out
HORN_CLEAT_TURN, HORN_CLEAT_BLOCK = 2, 14
CAPTAINS_WHEEL_TURN, CAPTAINS_WHEEL_BLOCK = 3, 18
SPARKLING_ROUGE_TURN = 3
MERCURY_HOURGLASS_DAMAGE = 3
STONE_CALENDAR_TURN, STONE_CALENDAR_DAMAGE = 7, 52
BRIMSTONE_SELF, BRIMSTONE_ENEMY = 2, 1
ORICHALCUM_BLOCK = {RelicId.ORICHALCUM : 6, RelicId.FAKE_ORICHALCUM : 3}
SCREAMING_FLAGON_DAMAGE = 20
PARRYING_SHIELD_BLOCK, PARRYING_SHIELD_DAMAGE = 10, 6

def _candelabra(combat, relic):
    if _turn(combat) == CANDELABRA_TURN:
        combat.gain_energy(CANDELABRA_ENERGY)

def _chandelier(combat, relic):
    if _turn(combat) == CHANDELIER_TURN:
        combat.gain_energy(CHANDELIER_ENERGY)

def _happy_flower(combat, relic):
    """The counter is the turns seen since the last energy. It reads 3 for a moment while the relic flashes, which is 0."""
    turns = HAPPY_FLOWER_TURNS[relic.relic_id]
    relic.counter = (_count(relic) % turns + 1) % turns
    if relic.counter == 0:
        combat.gain_energy(1)

def _horn_cleat(combat, relic):
    if _turn(combat) == HORN_CLEAT_TURN:
        combat.gain_block(_player(combat), HORN_CLEAT_BLOCK)

def _captains_wheel(combat, relic):
    if _turn(combat) == CAPTAINS_WHEEL_TURN:
        combat.gain_block(_player(combat), CAPTAINS_WHEEL_BLOCK)

def _sparkling_rouge(combat, relic):
    if _turn(combat) == SPARKLING_ROUGE_TURN:
        _player(combat).apply_status(StatusId.STRENGTH, 1)
        _player(combat).apply_status(StatusId.DEXTERITY, 1)

def _mercury_hourglass(combat, relic):
    _hurt_all(combat, MERCURY_HOURGLASS_DAMAGE)

def _brimstone(combat, relic):
    _player(combat).apply_status(StatusId.STRENGTH, BRIMSTONE_SELF)
    for enemy in _living(combat):
        enemy.apply_status(StatusId.STRENGTH, BRIMSTONE_ENEMY)

def _stone_calendar(combat, relic):
    if _turn(combat) == STONE_CALENDAR_TURN:
        _hurt_all(combat, STONE_CALENDAR_DAMAGE)

def _orichalcum_check(combat, relic):
    """Looked at before anything else ends the turn: only block you already had counts (`value`: there was none)."""
    relic.value = 1 if _player(combat).block == 0 else 0

def _orichalcum(combat, relic):
    if relic.value:
        combat.gain_block(_player(combat), ORICHALCUM_BLOCK[relic.relic_id])
    relic.value = 0

def _cloak_clasp(combat, relic):
    if _player(combat).hand:
        combat.gain_block(_player(combat), len(_player(combat).hand))

def _screaming_flagon(combat, relic):
    if not _player(combat).hand:
        _hurt_all(combat, SCREAMING_FLAGON_DAMAGE)

SAI_BLOCK = 7
PAELS_TEARS_ENERGY = 2

def _crossbow(combat, relic):
    """Crossbow.AfterSideTurnStart: a random Attack from the character pool, free this turn."""
    from sts2_lite.card import Card, INFERNAL_BLADE_POOL
    _player(combat).add_to_hand(Card.create_generated(rng.choice(INFERNAL_BLADE_POOL)).free_this_turn())     # X stays X

TOASTY_MITTENS_STRENGTH = 1
PHILOSOPHERS_STONE_STRENGTH = 1

def _toasty_mittens(combat, relic):
    """ToastyMittens.BeforeHandDraw: exhaust the top card of the draw pile (reshuffling first), +1 Strength."""
    player = _player(combat)
    top = player.take_top()
    if top is not None:
        player.exhaust_card(top)
        combat.fire(EventType.CARD_EXHAUSTED, top)
    player.apply_status(StatusId.STRENGTH, TOASTY_MITTENS_STRENGTH)

def _history_course_record(combat, relic, card):
    """Remember the last Attack or Skill of the turn; `used` is set while History Course's own dupe plays."""
    if not relic.used and card.type in _card_types()[:2]:
        relic.triggering = card
        relic.value = combat.card_x if card.energy_cost == "X" else 0

def _history_course(combat, relic):
    """HistoryCourse.AfterAutoPrePlayPhaseEntered: from turn 2, play a dupe of last turn's last Attack or Skill."""
    from sts2_lite.card import Card
    card, relic.triggering, x = relic.triggering, None, relic.value
    if card is None or _turn(combat) <= 1:
        return
    relic.used = True
    try:
        combat.auto_play(Card.create_copy(card), dupe=True, x_value=x if card.energy_cost == "X" else None)
    finally:
        relic.used = False

def _sai(combat, relic):
    combat.gain_block(_player(combat), SAI_BLOCK)

def _mr_struggles(combat, relic):
    _hurt_all(combat, _turn(combat))

def _paels_tears_check(combat, relic):
    """PaelsTears.BeforeSideTurnEnd: `value` = energy was left over."""
    relic.value = 1 if combat.combat_state.energy > 0 else 0

def _paels_tears(combat, relic):
    if relic.value:
        combat.gain_energy(PAELS_TEARS_ENERGY)

SEAL_OF_GOLD_ENERGY = 1
SEAL_OF_GOLD_GOLD = 5

def _seal_of_gold(combat, relic):
    """SealOfGold.AfterSideTurnStart: Gold >= 5 -> GainEnergy(1), then LoseGold(5)."""
    player = _player(combat)
    if player.gold >= SEAL_OF_GOLD_GOLD:
        combat.gain_energy(SEAL_OF_GOLD_ENERGY)
        player.gold -= SEAL_OF_GOLD_GOLD

def _paels_legion_turn(combat, relic):
    """PaelsLegion.AfterSideTurnStart: Cooldown--; ready again at 0."""
    if relic.counter:
        relic.counter -= 1

def _paels_eye_ready(combat, relic) -> bool:
    """PaelsEye: !UsedThisCombat && !AnyCardsPlayedThisTurn (auto-plays don't count)."""
    return not relic.used and combat.combat_state.cards_played == 0

def _paels_eye_exhaust(combat, relic):
    """PaelsEye.BeforeSideTurnEndEarly: exhaust the hand (a snapshot; cards drawn meanwhile stay)."""
    if not _paels_eye_ready(combat, relic):
        return
    player = _player(combat)
    for card in list(player.hand):
        player.exhaust_card(card)
        combat.fire(EventType.CARD_EXHAUSTED, card)

def take_extra_turn(combat) -> bool:
    """PaelsEye.ShouldTakeExtraTurn, then AfterTakingExtraTurn (UsedThisCombat = true)."""
    relic = _player(combat).relics.get(RelicId.PAELS_EYE)
    if relic is None or not _paels_eye_ready(combat, relic):
        return False
    relic.used = True
    return True

def _parrying_shield(combat, relic):
    if _player(combat).block >= PARRYING_SHIELD_BLOCK:
        _hurt_random(combat, PARRYING_SHIELD_DAMAGE)

EVENT_HANDLERS : dict[tuple[RelicId, EventType], Callable] = HandlerTable({
    (RelicId.PEN_NIB, EventType.CARD_PLAYED) : _pen_nib_played,
    (RelicId.NUNCHAKU, EventType.CARD_PLAYED) : _on_attack(_nunchaku),
    (RelicId.KUNAI, EventType.CARD_PLAYED) : _on_attack(_kunai),
    (RelicId.SHURIKEN, EventType.CARD_PLAYED) : _on_attack(_shuriken),
    (RelicId.KUSARIGAMA, EventType.CARD_PLAYED) : _on_attack(_kusarigama),
    (RelicId.ORNAMENTAL_FAN, EventType.CARD_PLAYED) : _on_attack(_ornamental_fan),
    (RelicId.LETTER_OPENER, EventType.CARD_PLAYED) : _on_skill(_letter_opener),
    (RelicId.TUNING_FORK, EventType.CARD_PLAYED) : _on_skill(_tuning_fork),
    (RelicId.RAINBOW_RING, EventType.CARD_PLAYED) : _rainbow_ring,
    (RelicId.POCKETWATCH, EventType.CARD_PLAYED) : _pocketwatch_played,
    (RelicId.ART_OF_WAR, EventType.CARD_PLAYED) : _on_attack(_attack_seen),
    (RelicId.RIPPLE_BASIN, EventType.CARD_PLAYED) : _on_attack(_attack_seen),
    (RelicId.PERMAFROST, EventType.CARD_PLAYED) : _on_power(_permafrost),
    (RelicId.GAME_PIECE, EventType.CARD_PLAYED) : _on_power(_game_piece),
    (RelicId.MUMMIFIED_HAND, EventType.CARD_PLAYED) : _on_power(_mummified_hand),
    (RelicId.DAUGHTER_OF_THE_WIND, EventType.CARD_PLAYED) : _daughter_of_the_wind,
    (RelicId.JOSS_PAPER, EventType.CARD_EXHAUSTED) : _joss_paper_exhausted,
    (RelicId.JOSS_PAPER, EventType.ETHEREAL_EXHAUSTED) : _joss_paper_ethereal,
    (RelicId.BURNING_STICKS, EventType.CARD_EXHAUSTED) : _burning_sticks,
    (RelicId.CHARONS_ASHES, EventType.CARD_EXHAUSTED) : _charons_ashes,
    (RelicId.FORGOTTEN_SOUL, EventType.CARD_EXHAUSTED) : _forgotten_soul,
    (RelicId.LOST_WISP, EventType.CARD_PLAYED) : _on_power(_lost_wisp),
    (RelicId.IRON_CLUB, EventType.CARD_PLAYED) : _iron_club,
    (RelicId.MUSIC_BOX, EventType.CARD_PLAYED) : _music_box,
    (RelicId.BRILLIANT_SCARF, EventType.CARD_PLAYED) : _count_scarf,
    (RelicId.VELVET_CHOKER, EventType.CARD_PLAYED) : _count_card,
    (RelicId.DIAMOND_DIADEM, EventType.CARD_PLAYED) : _count_card,
    (RelicId.DIAMOND_DIADEM, EventType.END_TURN) : _diamond_diadem,
    (RelicId.MUSIC_BOX, EventType.BEFORE_PLAYER_TURN) : _new_turn_flag,
    (RelicId.BRILLIANT_SCARF, EventType.BEFORE_PLAYER_TURN) : _reset_counter,
    (RelicId.VELVET_CHOKER, EventType.BEFORE_PLAYER_TURN) : _reset_counter,
    # the start of the turn, after the hand is drawn
    (RelicId.CANDELABRA, EventType.PLAYER_TURN_START) : _candelabra,
    (RelicId.CHANDELIER, EventType.PLAYER_TURN_START) : _chandelier,
    (RelicId.HAPPY_FLOWER, EventType.PLAYER_TURN_START) : _happy_flower,
    (RelicId.MERCURY_HOURGLASS, EventType.PLAYER_TURN_START) : _mercury_hourglass,
    (RelicId.BRIMSTONE, EventType.PLAYER_TURN_START) : _brimstone,
    (RelicId.FAKE_HAPPY_FLOWER, EventType.PLAYER_TURN_START) : _happy_flower,
    (RelicId.SAI, EventType.PLAYER_TURN_START) : _sai,
    (RelicId.TOASTY_MITTENS, EventType.BEFORE_PLAYER_TURN) : _toasty_mittens,
    (RelicId.HISTORY_COURSE, EventType.CARD_PLAYED) : _history_course_record,
    (RelicId.HISTORY_COURSE, EventType.AUTO_PRE_PLAY) : _history_course,
    (RelicId.CROSSBOW, EventType.PLAYER_TURN_START) : _crossbow,
    (RelicId.MR_STRUGGLES, EventType.PLAYER_TURN_START) : _mr_struggles,
    (RelicId.PAELS_TEARS, EventType.PLAYER_TURN_START) : _paels_tears,
    (RelicId.SEAL_OF_GOLD, EventType.PLAYER_TURN_START) : _seal_of_gold,
    (RelicId.PAELS_LEGION, EventType.PLAYER_TURN_START) : _paels_legion_turn,
    # after block is cleared, before the hand draw
    (RelicId.HORN_CLEAT, EventType.BLOCK_CLEARED) : _horn_cleat,
    (RelicId.CAPTAINS_WHEEL, EventType.BLOCK_CLEARED) : _captains_wheel,
    (RelicId.SPARKLING_ROUGE, EventType.BLOCK_CLEARED) : _sparkling_rouge,
    # the end of the player's turn
    (RelicId.ORICHALCUM, EventType.PLAY_PHASE_END) : _orichalcum_check,
    (RelicId.ORICHALCUM, EventType.END_TURN) : _orichalcum,
    (RelicId.FAKE_ORICHALCUM, EventType.PLAY_PHASE_END) : _orichalcum_check,
    (RelicId.FAKE_ORICHALCUM, EventType.END_TURN) : _orichalcum,
    (RelicId.PAELS_TEARS, EventType.END_TURN) : _paels_tears_check,
    (RelicId.PAELS_EYE, EventType.TURN_END_EARLY) : _paels_eye_exhaust,
    (RelicId.CLOAK_CLASP, EventType.END_TURN) : _cloak_clasp,
    (RelicId.SCREAMING_FLAGON, EventType.END_TURN) : _screaming_flagon,
    (RelicId.STONE_CALENDAR, EventType.END_TURN) : _stone_calendar,
    (RelicId.PARRYING_SHIELD, EventType.PLAYER_TURN_ENDED) : _parrying_shield,
    (RelicId.RIPPLE_BASIN, EventType.END_TURN) : _ripple_basin_end,
    (RelicId.KUSARIGAMA, EventType.END_TURN) : _reset_counter,
    # the start of the next turn, before the hand is drawn
    (RelicId.KUNAI, EventType.BEFORE_PLAYER_TURN) : _reset_counter,
    (RelicId.SHURIKEN, EventType.BEFORE_PLAYER_TURN) : _reset_counter,
    (RelicId.ORNAMENTAL_FAN, EventType.BEFORE_PLAYER_TURN) : _reset_counter,
    (RelicId.LETTER_OPENER, EventType.BEFORE_PLAYER_TURN) : _reset_counter,
    (RelicId.RAINBOW_RING, EventType.BEFORE_PLAYER_TURN) : _new_turn_rainbow,
    (RelicId.POCKETWATCH, EventType.BEFORE_PLAYER_TURN) : _pocketwatch_turn,
    (RelicId.RING_OF_THE_DRAKE, EventType.BEFORE_PLAYER_TURN) : _ring_of_the_drake_turn,
    (RelicId.POLLINOUS_CORE, EventType.BEFORE_PLAYER_TURN) : _pollinous_core_turn,
    (RelicId.ART_OF_WAR, EventType.BEFORE_PLAYER_TURN) : _art_of_war_turn,
    (RelicId.RIPPLE_BASIN, EventType.BEFORE_PLAYER_TURN) : _new_turn_flag,
})


# ---
# Reactions: HP lost, shuffles, kills, an empty hand
# ---
CENTENNIAL_PUZZLE_CARDS = 3
GREMLIN_HORN_ENERGY = 1
GREMLIN_HORN_CARDS = 1
PENDULUM_TURNS = 3
ABACUS_BLOCK = 6
RED_SKULL_STRENGTH = 3
SELF_FORMING_CLAY_BLOCK = 3

def _centennial_puzzle(combat, relic, amount):
    if not relic.used:
        relic.used = True
        _player(combat).draw_cards(CENTENNIAL_PUZZLE_CARDS)

def _gremlin_horn(combat, relic, creature):
    if creature is not _player(combat):
        combat.gain_energy(GREMLIN_HORN_ENERGY)
        _player(combat).draw_cards(GREMLIN_HORN_CARDS)

def _pendulum(combat, relic):
    relic.counter = (_count(relic) % PENDULUM_TURNS + 1) % PENDULUM_TURNS    # it reads 3 for a moment while it flashes, which is 0
    if relic.counter == 0:
        _player(combat).draw_cards(1)

def _biiig_hug(combat, relic):
    """BiiigHug.AfterShuffle: a Soot at a random place in the new draw pile."""
    from sts2_lite.card import Card
    _player(combat).insert_into_draw_pile(Card.create_soot())

def _abacus(combat, relic):
    combat.gain_block(_player(combat), ABACUS_BLOCK)

def _unceasing_top(combat, relic):
    _player(combat).draw_cards(1)

def _demon_tongue(combat, relic, amount):
    """The first time hit points are lost on the player's own turn they are healed back."""
    if combat.in_enemy_turn or relic.used:
        return
    relic.used = True
    player = _player(combat)
    player.current_hp = min(player.max_hp, player.current_hp + amount)

def _demon_tongue_reset(combat, relic):
    relic.used = False

def _red_skull(combat, relic):
    player = _player(combat)
    low = player.current_hp * 2 <= player.max_hp
    if low and not relic.used:
        relic.used = True
        player.apply_status(StatusId.STRENGTH, RED_SKULL_STRENGTH)
    elif not low and relic.used:
        relic.used = False
        player.apply_status(StatusId.STRENGTH, -RED_SKULL_STRENGTH)

def _self_forming_clay(combat, relic, amount):
    _player(combat).apply_status(StatusId.SELF_FORMING_CLAY, SELF_FORMING_CLAY_BLOCK)

EVENT_HANDLERS.update({
    (RelicId.CENTENNIAL_PUZZLE, EventType.HP_LOST) : _centennial_puzzle,
    (RelicId.GREMLIN_HORN, EventType.CREATURE_KILLED) : _gremlin_horn,
    (RelicId.PENDULUM, EventType.PLAYER_TURN_START) : _pendulum,
    (RelicId.THE_ABACUS, EventType.SHUFFLED) : _abacus,
    (RelicId.BIIIG_HUG, EventType.SHUFFLED) : _biiig_hug,
    (RelicId.UNCEASING_TOP, EventType.HAND_EMPTIED) : _unceasing_top,
    (RelicId.DEMON_TONGUE, EventType.HP_LOST) : _demon_tongue,
    (RelicId.DEMON_TONGUE, EventType.BEFORE_PLAYER_TURN) : _demon_tongue_reset,
    (RelicId.RED_SKULL, EventType.HP_CHANGED) : _red_skull,
    (RelicId.SELF_FORMING_CLAY, EventType.HP_LOST) : _self_forming_clay,
})

# ---
# Max energy and victory.
# ---
BREAD_ENERGY = 1
PAELS_FLESH_ENERGY = 1
MEAT_ON_THE_BONE_HEAL = 12
VICTORY_HEAL : dict[RelicId, int] = {RelicId.BURNING_BLOOD : 6, RelicId.BLACK_BLOOD : 12}     # AfterCombatVictory

REPTILE_TRINKET_STRENGTH = 3
BELT_BUCKLE_DEXTERITY = 2

def dexterity_bonus(owner : Creature) -> int:
    """Belt Buckle: 2 additional Dexterity while the player holds no Potions (assumed to count for card Block only, like Dexterity)."""
    if RelicId.BELT_BUCKLE in owner.relics and not getattr(owner, "potions", True):
        return BELT_BUCKLE_DEXTERITY
    return 0

def max_energy_gain(owner : Creature, turn : int) -> int:
    """ModifyMaxEnergy: Bread +1 from turn 2, Pael's Flesh +1 from turn 3 (player turns). The bridge already includes them once
    active, so each is added only on the turn it starts."""
    if turn == 2 and RelicId.BREAD in owner.relics:
        return BREAD_ENERGY
    if turn == 3 and RelicId.PAELS_FLESH in owner.relics:
        return PAELS_FLESH_ENERGY
    return 0

def victory_heal(owner : Creature):
    """Meat on the Bone (victory early: +12 if HP <= floor(max / 2)), then Burning Blood / Black Blood."""
    if RelicId.MEAT_ON_THE_BONE in owner.relics and owner.current_hp <= owner.max_hp // 2:
        owner.current_hp = min(owner.max_hp, owner.current_hp + MEAT_ON_THE_BONE_HEAL)
    for relic_id, heal in VICTORY_HEAL.items():
        if relic_id in owner.relics:
            owner.current_hp = min(owner.max_hp, owner.current_hp + heal)

def fire_relics(combat : CombatSimulator, event : EventType, *args):
    handlers = EVENT_HANDLERS.by_event.get(event)
    if handlers is None:
        return
    for relic_id, relic in list(combat.combat_state.player.relics.items()):
        handler = handlers.get(relic_id)
        if handler is not None:
            handler(combat, relic, *args)


# ---
# A card play that fails is undone: the counters and the block go back.
# ---
def snapshot(owner : Creature):
    return owner.block, {relic_id : (relic.counter, relic.used, relic.value, relic.triggering) for relic_id, relic in owner.relics.items()}

def restore(owner : Creature, saved):
    owner.block = saved[0]
    for relic_id, (counter, used, value, triggering) in saved[1].items():
        relic = owner.relics[relic_id]
        relic.counter, relic.used, relic.value, relic.triggering = counter, used, value, triggering
