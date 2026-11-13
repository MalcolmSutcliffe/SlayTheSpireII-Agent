from __future__ import annotations
from typing import TYPE_CHECKING, Callable

from sts2_lite.status import StatusId

from sts2_lite.relic.ids import RelicId, RelicInstance

if TYPE_CHECKING:
    from sts2_lite.card import Card
    from sts2_lite.creature import Creature

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
