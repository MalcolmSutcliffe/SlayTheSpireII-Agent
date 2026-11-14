"""Potions: what the player carries (Potion), every potion an Ironclad can use (PotionId, POTION_INFO) and what using one does.

Source of the list and the numbers: the Slay the Spire 2 wiki's potion list (the decompiled source has no potion models), so the
effects below are as the wiki words them. Where the wording leaves the game's rule open the choice made here is marked "assumed" and
should be checked against a capture. Potions of the other characters are left out.

A potion is used with the action {"action": "use_potion", "slot": n, "target": enemy index, "target_name": enemy id}; the slot is the
game's own slot number (it stays put when another potion leaves)."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable, NamedTuple

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.creature import Creature

from sts2_lite import rng
from sts2_lite.helpers import player_of, living_enemies
from sts2_lite.card import Card, CardType, TargetType, GENERATABLE_CARDS, COLORLESS_CARDS, STRIKE_CARDS, temp_strength
from sts2_lite.hooks import HookType
from sts2_lite.relic import RelicId, REPTILE_TRINKET_STRENGTH
from sts2_lite.status import StatusId

DEFAULT_POTION_SLOTS = 3


class PotionRarity(Enum):
    __hash__ = object.__hash__      # members are singletons; Enum.__hash__ is pure Python
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()
    SPECIAL = auto()                # events and the like: never in a random drop


class PotionId(Enum):
    """Every potion an Ironclad can hold. Use it to key a score table, e.g. {PotionId.FAIRY_IN_A_BOTTLE: 30, ...}."""
    __hash__ = object.__hash__
    # common
    ATTACK_POTION = auto()
    BLOCK_POTION = auto()
    COLORLESS_POTION = auto()
    DEXTERITY_POTION = auto()
    ENERGY_POTION = auto()
    EXPLOSIVE_AMPOULE = auto()
    FIRE_POTION = auto()
    FLEX_POTION = auto()
    POWER_POTION = auto()
    SKILL_POTION = auto()
    SPEED_POTION = auto()
    STRENGTH_POTION = auto()
    SWIFT_POTION = auto()
    VULNERABLE_POTION = auto()
    WEAK_POTION = auto()
    BLOOD_POTION = auto()               # Ironclad
    # uncommon
    BLESSING_OF_THE_FORGE = auto()
    CLARITY_EXTRACT = auto()
    CURE_ALL = auto()
    DUPLICATOR = auto()
    FORTIFIER = auto()
    FYSH_OIL = auto()
    GAMBLERS_BREW = auto()
    HEART_OF_IRON = auto()
    LIQUID_BRONZE = auto()
    POTION_OF_BINDING = auto()
    POWDERED_DEMISE = auto()
    RADIANT_TINCTURE = auto()
    REGEN_POTION = auto()
    STABLE_SERUM = auto()
    TOUCH_OF_INSANITY = auto()
    ASHWATER = auto()                   # Ironclad
    # rare
    BEETLE_JUICE = auto()
    BOTTLED_POTENTIAL = auto()
    DISTILLED_CHAOS = auto()
    DROPLET_OF_PRECOGNITION = auto()
    ENTROPIC_BREW = auto()
    FAIRY_IN_A_BOTTLE = auto()
    FRUIT_JUICE = auto()
    GIGANTIFICATION_POTION = auto()
    LIQUID_MEMORIES = auto()
    LUCKY_TONIC = auto()
    MAZALETHS_GIFT = auto()
    OROBIC_ACID = auto()
    SHACKLING_POTION = auto()
    SHIP_IN_A_BOTTLE = auto()
    SNECKO_OIL = auto()
    SOLDIERS_STEW = auto()              # Ironclad
    # special
    AMBERGRIS = auto()
    FOUL_POTION = auto()
    GLOWWATER_POTION = auto()
    POTION_SHAPED_ROCK = auto()

    @property
    def info(self) -> PotionInfo:
        return POTION_INFO[self]

    @property
    def rarity(self) -> PotionRarity:
        return POTION_INFO[self].rarity

    @classmethod
    def from_game_id(cls, game_id : str) -> PotionId | None:
        """The potion a bridge id names ("FAIRY_IN_A_BOTTLE"); None for one the sim does not know (another character's, or a new one).
        Punctuation and case are ignored, so "GAMBLERS_BREW" and "GAMBLER_S_BREW" both find Gambler's Brew."""
        return _BY_NORMALISED_NAME.get(_normalise(game_id))


def _normalise(name : str) -> str:
    return "".join(ch for ch in str(name).upper() if ch.isalnum())


class PotionInfo(NamedTuple):
    name : str
    rarity : PotionRarity
    target : TargetType             # Self for the potions that act on the player (the game's AnyPlayer too), AnyEnemy for the ones that need an enemy picked
    combat_usable : bool = True     # False: it works by itself (Fairy in a Bottle)


C, U, R, S = PotionRarity.COMMON, PotionRarity.UNCOMMON, PotionRarity.RARE, PotionRarity.SPECIAL
ME, ONE, ALL = TargetType.Self, TargetType.AnyEnemy, TargetType.AllEnemies

POTION_INFO : dict[PotionId, PotionInfo] = {
    PotionId.ATTACK_POTION : PotionInfo("Attack Potion", C, ME), PotionId.BLOCK_POTION : PotionInfo("Block Potion", C, ME),
    PotionId.COLORLESS_POTION : PotionInfo("Colorless Potion", C, ME), PotionId.DEXTERITY_POTION : PotionInfo("Dexterity Potion", C, ME),
    PotionId.ENERGY_POTION : PotionInfo("Energy Potion", C, ME), PotionId.EXPLOSIVE_AMPOULE : PotionInfo("Explosive Ampoule", C, ALL),
    PotionId.FIRE_POTION : PotionInfo("Fire Potion", C, ONE), PotionId.FLEX_POTION : PotionInfo("Flex Potion", C, ME),
    PotionId.POWER_POTION : PotionInfo("Power Potion", C, ME), PotionId.SKILL_POTION : PotionInfo("Skill Potion", C, ME),
    PotionId.SPEED_POTION : PotionInfo("Speed Potion", C, ME), PotionId.STRENGTH_POTION : PotionInfo("Strength Potion", C, ME),
    PotionId.SWIFT_POTION : PotionInfo("Swift Potion", C, ME), PotionId.VULNERABLE_POTION : PotionInfo("Vulnerable Potion", C, ONE),
    PotionId.WEAK_POTION : PotionInfo("Weak Potion", C, ONE), PotionId.BLOOD_POTION : PotionInfo("Blood Potion", C, ME),
    PotionId.BLESSING_OF_THE_FORGE : PotionInfo("Blessing of the Forge", U, ME), PotionId.CLARITY_EXTRACT : PotionInfo("Clarity Extract", U, ME),
    PotionId.CURE_ALL : PotionInfo("Cure All", U, ME), PotionId.DUPLICATOR : PotionInfo("Duplicator", U, ME),
    PotionId.FORTIFIER : PotionInfo("Fortifier", U, ME), PotionId.FYSH_OIL : PotionInfo("Fysh Oil", U, ME),
    PotionId.GAMBLERS_BREW : PotionInfo("Gambler's Brew", U, ME), PotionId.HEART_OF_IRON : PotionInfo("Heart of Iron", U, ME),
    PotionId.LIQUID_BRONZE : PotionInfo("Liquid Bronze", U, ME), PotionId.POTION_OF_BINDING : PotionInfo("Potion of Binding", U, ALL),
    PotionId.POWDERED_DEMISE : PotionInfo("Powdered Demise", U, ONE), PotionId.RADIANT_TINCTURE : PotionInfo("Radiant Tincture", U, ME),
    PotionId.REGEN_POTION : PotionInfo("Regen Potion", U, ME), PotionId.STABLE_SERUM : PotionInfo("Stable Serum", U, ME),
    PotionId.TOUCH_OF_INSANITY : PotionInfo("Touch of Insanity", U, ME), PotionId.ASHWATER : PotionInfo("Ashwater", U, ME),
    PotionId.BEETLE_JUICE : PotionInfo("Beetle Juice", R, ONE), PotionId.BOTTLED_POTENTIAL : PotionInfo("Bottled Potential", R, ME),
    PotionId.DISTILLED_CHAOS : PotionInfo("Distilled Chaos", R, ME), PotionId.DROPLET_OF_PRECOGNITION : PotionInfo("Droplet of Precognition", R, ME),
    PotionId.ENTROPIC_BREW : PotionInfo("Entropic Brew", R, ME), PotionId.FAIRY_IN_A_BOTTLE : PotionInfo("Fairy in a Bottle", R, ME, False),
    PotionId.FRUIT_JUICE : PotionInfo("Fruit Juice", R, ME), PotionId.GIGANTIFICATION_POTION : PotionInfo("Gigantification Potion", R, ME),
    PotionId.LIQUID_MEMORIES : PotionInfo("Liquid Memories", R, ME), PotionId.LUCKY_TONIC : PotionInfo("Lucky Tonic", R, ME),
    PotionId.MAZALETHS_GIFT : PotionInfo("Mazaleth's Gift", R, ME), PotionId.OROBIC_ACID : PotionInfo("Orobic Acid", R, ME),
    PotionId.SHACKLING_POTION : PotionInfo("Shackling Potion", R, ALL), PotionId.SHIP_IN_A_BOTTLE : PotionInfo("Ship in a Bottle", R, ME),
    PotionId.SNECKO_OIL : PotionInfo("Snecko Oil", R, ME), PotionId.SOLDIERS_STEW : PotionInfo("Soldier's Stew", R, ME),
    PotionId.AMBERGRIS : PotionInfo("Ambergris", S, ME), PotionId.FOUL_POTION : PotionInfo("Foul Potion", S, ALL),
    PotionId.GLOWWATER_POTION : PotionInfo("Glowwater Potion", S, ME), PotionId.POTION_SHAPED_ROCK : PotionInfo("Potion-Shaped Rock", S, ONE),
}
_BY_NORMALISED_NAME = {_normalise(p.name): p for p in PotionId}
_BY_NORMALISED_NAME.update({_normalise(info.name): p for p, info in POTION_INFO.items()})

# what Entropic Brew and Alchemize can make (rolled by rarity as in the first game: 65 / 25 / 10), assumed; Entropic Brew makes no Entropic Brew (assumed)
RANDOM_POTION_WEIGHTS = {C : 65, U : 25, R : 10}
RANDOM_POTION_POOL = {rarity : [p for p, info in POTION_INFO.items() if info.rarity == rarity] for rarity in RANDOM_POTION_WEIGHTS}


@dataclass(frozen=True)
class Potion:
    potion_id : PotionId
    slot : int

    @property
    def info(self) -> PotionInfo:
        return POTION_INFO[self.potion_id]


# ---
# Numbers (the wiki's)
# ---
BLOCK_POTION_BLOCK = 12
ENERGY_POTION_ENERGY = 2
EXPLOSIVE_AMPOULE_DAMAGE = 10
FIRE_POTION_DAMAGE = 20
POTION_SHAPED_ROCK_DAMAGE = 15
FOUL_POTION_DAMAGE = 12
FLEX_STRENGTH, SPEED_DEXTERITY = 5, 5
STRENGTH_POTION_STRENGTH, DEXTERITY_POTION_DEXTERITY = 2, 2
SWIFT_CARDS, CURE_ALL_CARDS, SNECKO_CARDS, GLOWWATER_CARDS, BOTTLED_POTENTIAL_CARDS = 3, 2, 7, 10, 5
VULNERABLE_POTION, WEAK_POTION = 3, 3
BLOOD_POTION_HEAL, AMBERGRIS_HEAL, FAIRY_HEAL = 0.20, 0.50, 0.30        # shares of Max HP; rounded down (assumed)
POWDERED_DEMISE_LOSS, REGEN_AMOUNT = 9, 5
SHACKLING_STRENGTH = 7
HEART_OF_IRON_PLATING, LIQUID_BRONZE_THORNS = 7, 3
SHIP_IN_A_BOTTLE_BLOCK = 10
BEETLE_JUICE_TURNS = 4
FRUIT_JUICE_MAX_HP = 5
STABLE_SERUM_TURNS = 2
CLARITY_TURNS, RADIANT_TURNS = 3, 3
OFFERS = 3
SNECKO_MAX_COST = 3


# ---
# Helpers
# ---


def _target(combat : CombatSimulator, target_index : int):
    return combat.combat_state.enemies[target_index]

def _heal(creature : Creature, amount : int):
    creature.current_hp = min(creature.max_hp, creature.current_hp + amount)

def _hit(combat : CombatSimulator, target : Creature, amount : int):
    """Damage that is not an attack: no Strength, Vulnerable or the like (assumed to be Unpowered, as the first game's potions are)."""
    target.apply_damage(amount, player_of(combat), False)

def _type_pool(card_type : CardType) -> list:
    return [cid for cid, (_, kind, _, _) in GENERATABLE_CARDS.items() if kind == card_type]

def _offer(combat : CombatSimulator, pool : list):
    """Choose 1 of 3 different random cards; the one taken is free to play this turn."""
    combat.request_discovery([Card.create_generated(cid) for cid in rng.sample(pool, min(OFFERS, len(pool)))])

def _generate_free(combat : CombatSimulator, pool : list):
    player_of(combat).add_to_hand(Card.create_generated(rng.choice(pool)).free_this_turn())

def _all_cards(player) -> list[tuple[list, int]]:
    return [(pile, i) for pile in (player.hand, player.draw_pile, player.discard_pile, player.exhaust_pile) for i in range(len(pile))]


# ---
# Effects: effect(combat, target_index)
# ---
def _attack_potion(combat, t): _offer(combat, _type_pool(CardType.Attack))
def _skill_potion(combat, t): _offer(combat, _type_pool(CardType.Skill))
def _power_potion(combat, t): _offer(combat, _type_pool(CardType.Power))
def _colorless_potion(combat, t): _offer(combat, list(COLORLESS_CARDS))

def _orobic_acid(combat, t):
    for card_type in (CardType.Attack, CardType.Skill, CardType.Power):
        _generate_free(combat, _type_pool(card_type))

def _block_potion(combat, t): combat.gain_block(player_of(combat), BLOCK_POTION_BLOCK)     # assumed not changed by Dexterity or Frail
def _dexterity_potion(combat, t): player_of(combat).apply_status(StatusId.DEXTERITY, DEXTERITY_POTION_DEXTERITY)
def _strength_potion(combat, t): player_of(combat).apply_status(StatusId.STRENGTH, STRENGTH_POTION_STRENGTH)
def _fysh_oil(combat, t):
    player_of(combat).apply_status(StatusId.STRENGTH, 1)
    player_of(combat).apply_status(StatusId.DEXTERITY, 1)

def _flex_potion(combat, t): temp_strength(player_of(combat), StatusId.FLEX_POTION, FLEX_STRENGTH, 1)

def _speed_potion(combat, t):
    player = player_of(combat)
    player.apply_status(StatusId.SPEED_POTION, SPEED_DEXTERITY)
    player.apply_status(StatusId.DEXTERITY, SPEED_DEXTERITY)

def _energy_potion(combat, t): combat.gain_energy(ENERGY_POTION_ENERGY)
def _swift_potion(combat, t): player_of(combat).draw_cards(SWIFT_CARDS)
def _cure_all(combat, t):
    combat.gain_energy(1)
    player_of(combat).draw_cards(CURE_ALL_CARDS)

def _explosive_ampoule(combat, t):
    for enemy in living_enemies(combat):
        _hit(combat, enemy, EXPLOSIVE_AMPOULE_DAMAGE)

def _fire_potion(combat, t): _hit(combat, _target(combat, t), FIRE_POTION_DAMAGE)
def _potion_shaped_rock(combat, t): _hit(combat, _target(combat, t), POTION_SHAPED_ROCK_DAMAGE)

def _foul_potion(combat, t):
    """12 damage to everyone: every enemy and the player."""
    for enemy in living_enemies(combat):
        _hit(combat, enemy, FOUL_POTION_DAMAGE)
    player_of(combat).apply_damage(FOUL_POTION_DAMAGE, None, False)

def _vulnerable_potion(combat, t): _target(combat, t).apply_status(StatusId.VULNERABLE, VULNERABLE_POTION)
def _weak_potion(combat, t): _target(combat, t).apply_status(StatusId.WEAK, WEAK_POTION)
def _beetle_juice(combat, t): _target(combat, t).apply_status(StatusId.SHRINK, BEETLE_JUICE_TURNS)      # assumed: the Shrink the Shrinker Beetle uses

def _potion_of_binding(combat, t):
    for enemy in living_enemies(combat):
        enemy.apply_status(StatusId.WEAK, 1)
        enemy.apply_status(StatusId.VULNERABLE, 1)

def _shackling_potion(combat, t):
    """All enemies lose 7 Strength this turn: it comes back when the enemy turn is over."""
    for enemy in living_enemies(combat):
        temp_strength(enemy, StatusId.DARK_SHACKLES, SHACKLING_STRENGTH, -1, combat)

def _powdered_demise(combat, t): _target(combat, t).apply_status(StatusId.DEMISE, POWDERED_DEMISE_LOSS)
def _regen_potion(combat, t): player_of(combat).apply_status(StatusId.REGEN, REGEN_AMOUNT)
def _heart_of_iron(combat, t): player_of(combat).apply_status(StatusId.PLATING, HEART_OF_IRON_PLATING)
def _liquid_bronze(combat, t): player_of(combat).apply_status(StatusId.THORNS, LIQUID_BRONZE_THORNS)
def _lucky_tonic(combat, t): player_of(combat).apply_status(StatusId.BUFFER, 1)
def _mazaleths_gift(combat, t): player_of(combat).apply_status(StatusId.RITUAL, 1)

def _fortifier(combat, t):
    player = player_of(combat)
    combat.gain_block(player, player.block * 2)         # triple

def _ship_in_a_bottle(combat, t):
    combat.gain_block(player_of(combat), SHIP_IN_A_BOTTLE_BLOCK)
    player_of(combat).apply_status(StatusId.BLOCK_NEXT_TURN, SHIP_IN_A_BOTTLE_BLOCK)

def _blood_potion(combat, t):
    player = player_of(combat)
    _heal(player, int(player.max_hp * BLOOD_POTION_HEAL))

def _fruit_juice(combat, t):
    player = player_of(combat)
    player.max_hp += FRUIT_JUICE_MAX_HP
    player.current_hp += FRUIT_JUICE_MAX_HP

def _ambergris(combat, t):
    """Heals half; in a fight it also gives an extra turn (taken when this one ends)."""
    player = player_of(combat)
    _heal(player, int(player.max_hp * AMBERGRIS_HEAL))
    player.extra_turn_pending = True

def _blessing_of_the_forge(combat, t):
    player = player_of(combat)
    for card in list(player.hand):
        player.upgrade_card(card)

def _clarity_extract(combat, t):
    player_of(combat).draw_cards(1)
    player_of(combat).apply_status(StatusId.CLARITY_EXTRACT, CLARITY_TURNS)

def _radiant_tincture(combat, t):
    combat.gain_energy(1)
    player_of(combat).apply_status(StatusId.RADIANT_TINCTURE, RADIANT_TURNS)

def _duplicator(combat, t): player_of(combat).apply_status(StatusId.DUPLICATION, 1)
def _gigantification(combat, t): player_of(combat).apply_status(StatusId.GIGANTIFICATION, 1)
def _stable_serum(combat, t): player_of(combat).apply_status(StatusId.RETAIN_HAND, STABLE_SERUM_TURNS)

def _gamblers_brew(combat, t):
    """Discard any number of cards, then draw that many (the count is `amount` of the pending choice)."""
    combat.request_choice("discard_any", list(range(len(player_of(combat).hand))), "hand", 0)

def _touch_of_insanity(combat, t):
    combat.request_choice("free_card", list(range(len(player_of(combat).hand))), "hand")

def _ashwater(combat, t):
    hand = player_of(combat).hand
    combat.request_choice("exhaust_any", list(range(len(hand))), "hand", len(hand))

def _droplet_of_precognition(combat, t):
    combat.request_choice("draw_to_hand", list(range(len(player_of(combat).draw_pile))), pile="draw")

def _liquid_memories(combat, t):
    combat.request_choice("to_hand_free", list(range(len(player_of(combat).discard_pile))), pile="discard")

def _distilled_chaos(combat, t): combat.auto_play_from_top(3)

def _bottled_potential(combat, t):
    player = player_of(combat)
    player.draw_pile.extend(player.hand)
    player.draw_pile.extend(player.discard_pile)
    player.hand, player.discard_pile = [], []
    player.known_top = 0
    player.shuffle_draw_pile()
    player.draw_cards(BOTTLED_POTENTIAL_CARDS)

def _glowwater_potion(combat, t):
    player = player_of(combat)
    for card in list(player.hand):
        player.exhaust_card(card)
        combat.fire(HookType.CARD_EXHAUSTED, card)
    player.draw_cards(GLOWWATER_CARDS)

def _snecko_oil(combat, t):
    """Draw 7, then every card in the hand costs a random 0-3 this turn."""
    player = player_of(combat)
    player.draw_cards(SNECKO_CARDS)
    for i, card in enumerate(player.hand):
        if card.energy_cost == "X" or card.unplayable or card.is_unplayable:
            continue
        new_card = Card.create_copy(card)
        if new_card.restore_cost is None:
            new_card.restore_cost = card.energy_cost
        new_card.energy_cost = rng.randrange(SNECKO_MAX_COST + 1)
        player.hand[i] = new_card

def _soldiers_stew(combat, t):
    """Every card with the Strike tag, wherever it is, gets 1 Replay for the rest of the combat."""
    player = player_of(combat)
    for pile, i in _all_cards(player):
        if pile[i].card_id in STRIKE_CARDS:
            copy = Card.create_copy(pile[i])        # cards are shared between simulated states
            copy.replay += 1
            pile[i] = copy

def procure_random_potion(player, exclude=()) -> Potion | None:
    """A random potion (rarity 65 / 25 / 10, as in the first game, assumed) goes into the lowest free slot; None when every slot is full.
    The wiki: Alchemize and Entropic Brew (in a fight) never make Fruit Juice."""
    taken = {p.slot for p in player.potions}
    slot = next((s for s in range(player.potion_slots) if s not in taken), None)
    if slot is None:
        return None
    rarity = rng.choices(list(RANDOM_POTION_WEIGHTS), weights=list(RANDOM_POTION_WEIGHTS.values()))[0]
    potion = Potion(rng.choice([p for p in RANDOM_POTION_POOL[rarity] if p not in exclude]), slot)
    player.potions.append(potion)
    return potion

def _entropic_brew(combat, t):
    player = player_of(combat)
    while procure_random_potion(player, exclude=(PotionId.FRUIT_JUICE, PotionId.ENTROPIC_BREW)) is not None:
        pass

def _nothing(combat, t): pass       # Fairy in a Bottle: works by itself (Player.die)

EFFECTS : dict[PotionId, Callable] = {
    PotionId.ATTACK_POTION : _attack_potion, PotionId.BLOCK_POTION : _block_potion, PotionId.COLORLESS_POTION : _colorless_potion,
    PotionId.DEXTERITY_POTION : _dexterity_potion, PotionId.ENERGY_POTION : _energy_potion, PotionId.EXPLOSIVE_AMPOULE : _explosive_ampoule,
    PotionId.FIRE_POTION : _fire_potion, PotionId.FLEX_POTION : _flex_potion, PotionId.POWER_POTION : _power_potion,
    PotionId.SKILL_POTION : _skill_potion, PotionId.SPEED_POTION : _speed_potion, PotionId.STRENGTH_POTION : _strength_potion,
    PotionId.SWIFT_POTION : _swift_potion, PotionId.VULNERABLE_POTION : _vulnerable_potion, PotionId.WEAK_POTION : _weak_potion,
    PotionId.BLOOD_POTION : _blood_potion, PotionId.BLESSING_OF_THE_FORGE : _blessing_of_the_forge, PotionId.CLARITY_EXTRACT : _clarity_extract,
    PotionId.CURE_ALL : _cure_all, PotionId.DUPLICATOR : _duplicator, PotionId.FORTIFIER : _fortifier, PotionId.FYSH_OIL : _fysh_oil,
    PotionId.GAMBLERS_BREW : _gamblers_brew, PotionId.HEART_OF_IRON : _heart_of_iron, PotionId.LIQUID_BRONZE : _liquid_bronze,
    PotionId.POTION_OF_BINDING : _potion_of_binding, PotionId.POWDERED_DEMISE : _powdered_demise, PotionId.RADIANT_TINCTURE : _radiant_tincture,
    PotionId.REGEN_POTION : _regen_potion, PotionId.STABLE_SERUM : _stable_serum, PotionId.TOUCH_OF_INSANITY : _touch_of_insanity,
    PotionId.ASHWATER : _ashwater, PotionId.BEETLE_JUICE : _beetle_juice, PotionId.BOTTLED_POTENTIAL : _bottled_potential,
    PotionId.DISTILLED_CHAOS : _distilled_chaos, PotionId.DROPLET_OF_PRECOGNITION : _droplet_of_precognition, PotionId.ENTROPIC_BREW : _entropic_brew,
    PotionId.FAIRY_IN_A_BOTTLE : _nothing, PotionId.FRUIT_JUICE : _fruit_juice, PotionId.GIGANTIFICATION_POTION : _gigantification,
    PotionId.LIQUID_MEMORIES : _liquid_memories, PotionId.LUCKY_TONIC : _lucky_tonic, PotionId.MAZALETHS_GIFT : _mazaleths_gift,
    PotionId.OROBIC_ACID : _orobic_acid, PotionId.SHACKLING_POTION : _shackling_potion, PotionId.SHIP_IN_A_BOTTLE : _ship_in_a_bottle,
    PotionId.SNECKO_OIL : _snecko_oil, PotionId.SOLDIERS_STEW : _soldiers_stew, PotionId.AMBERGRIS : _ambergris, PotionId.FOUL_POTION : _foul_potion,
    PotionId.GLOWWATER_POTION : _glowwater_potion, PotionId.POTION_SHAPED_ROCK : _potion_shaped_rock,
}
assert set(EFFECTS) == set(PotionId) == set(POTION_INFO)


# ---
# Using a potion
# ---
def usable_potion_actions(combat : CombatSimulator) -> list[dict]:
    """The use_potion actions open now: one per potion, and per living enemy for the ones that need a target."""
    actions = []
    for potion in player_of(combat).potions:
        info = potion.info
        if not info.combat_usable:
            continue
        base = {"action" : "use_potion", "slot" : potion.slot, "potion_id" : potion.potion_id.name}
        if info.target == TargetType.AnyEnemy:
            for index, enemy in enumerate(combat.combat_state.enemies):
                if enemy.current_hp > 0:
                    actions.append({**base, "target" : index, "target_name" : enemy.enemy_id})
        else:
            actions.append({**base, "target" : 0})
    return actions

def use_potion(combat : CombatSimulator, slot : int, target_index : int = 0):
    from sts2_lite.combat import IllegalActionError
    cs = combat.combat_state
    player = cs.player
    if cs.pending_choice is not None:
        raise IllegalActionError("a card choice must be made first")
    potion = next((p for p in player.potions if p.slot == slot), None)
    if potion is None:
        raise IllegalActionError(f"there is no potion in slot {slot}")
    if not potion.info.combat_usable:
        raise IllegalActionError(f"{potion.info.name} cannot be used in a fight")
    if potion.info.target == TargetType.AnyEnemy and not (0 <= target_index < len(cs.enemies) and cs.enemies[target_index].current_hp > 0):
        raise IllegalActionError(f"{potion.info.name} needs a living enemy as its target")
    hp_loss_mark = player.hp_loss_events
    player.potions.remove(potion)
    EFFECTS[potion.potion_id](combat, target_index)
    if RelicId.REPTILE_TRINKET in player.relics:
        temp_strength(player, StatusId.REPTILE_TRINKET, REPTILE_TRINKET_STRENGTH, 1)
    combat.after_potion(hp_loss_mark)
