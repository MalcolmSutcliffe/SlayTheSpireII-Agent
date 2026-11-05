from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.creature import Creature
    from sts2_lite.enemy import Enemy
    from sts2_lite.player import Player

import re
from enum import Enum, auto

from sts2_lite import rng
from sts2_lite.events import EventType
from sts2_lite.status import StatusId
from sts2_lite.relic import block_multiplier, block_gained, debuff_multiplier, x_bonus, before_card_played, snapshot, restore


class CardType(Enum):
    Power = auto()
    Skill = auto()
    Attack = auto()
    Status = auto()

class CardId(Enum):
    STRIKE_IRONCLAD = auto()
    DEFEND_IRONCLAD = auto()
    BASH = auto()
    BLOOD_WALL = auto()
    SLIMED = auto()
    PERFECTED_STRIKE = auto()
    BREAKTHROUGH = auto()
    SHRUG_IT_OFF = auto()
    POMMEL_STRIKE = auto()
    IRON_WAVE = auto()
    THUNDERCLAP = auto()
    INFLAME = auto()
    FIGHT_ME = auto()
    TREMBLE = auto()
    CRIMSON_MANTLE = auto()
    ANGER = auto()
    INFECTION = auto()
    BLUDGEON = auto()
    UNRELENTING = auto()
    BODY_SLAM = auto()
    TWIN_STRIKE = auto()
    DAZED = auto()
    WOUND = auto()
    BREAK = auto()
    HEMOKINESIS = auto()
    DISMANTLE = auto()
    BULLY = auto()
    ASHEN_STRIKE = auto()
    MOLTEN_FIST = auto()
    UPPERCUT = auto()
    SWORD_BOOMERANG = auto()
    WHIRLWIND = auto()
    SPITE = auto()
    CINDER = auto()
    IMPERVIOUS = auto()
    EVIL_EYE = auto()
    TAUNT = auto()
    SECOND_WIND = auto()
    BLOODLETTING = auto()
    FEED = auto()
    DOMINATE = auto()
    ARMAMENTS = auto()
    AGGRESSION = auto()
    HEADBUTT = auto()
    TRUE_GRIT = auto()
    BURNING_PACT = auto()
    HAVOC = auto()
    BARRICADE = auto()
    COLOSSUS = auto()
    CORRUPTION = auto()
    CRUELTY = auto()
    DARK_EMBRACE = auto()
    DEMON_FORM = auto()
    FEEL_NO_PAIN = auto()
    FLAME_BARRIER = auto()
    JUGGERNAUT = auto()
    JUGGLING = auto()
    ONE_TWO_PUNCH = auto()
    PYRE = auto()
    RAGE = auto()
    RUPTURE = auto()
    STAMPEDE = auto()
    STONE_ARMOR = auto()
    UNMOVABLE = auto()
    VICIOUS = auto()
    BATTLE_TRANCE = auto()
    CASCADE = auto()
    CONFLAGRATION = auto()
    DRUM_OF_BATTLE = auto()
    EXPECT_A_FIGHT = auto()
    FIEND_FIRE = auto()
    FORGOTTEN_RITUAL = auto()
    HOWL_FROM_BEYOND = auto()
    INFERNAL_BLADE = auto()
    NOT_YET = auto()
    OFFERING = auto()
    PACTS_END = auto()
    BRAND = auto()
    GIANT_ROCK = auto()
    HELLRAISER = auto()
    INFERNO = auto()
    MANGLE = auto()
    PILLAGE = auto()
    PRIMAL_FORCE = auto()
    RAMPAGE = auto()
    SETUP_STRIKE = auto()
    STOKE = auto()
    STOMP = auto()
    TEAR_ASUNDER = auto()
    THRASH = auto()

INFECTION_DAMAGE = 3

# energy cost change when upgraded (the rest of an upgrade is read from is_upgraded when the card is played)
UPGRADE_COST_CHANGE = {
    CardId.BARRICADE : -1, CardId.CORRUPTION : -1, CardId.DARK_EMBRACE : -1, CardId.STAMPEDE : -1,
    CardId.UNMOVABLE : -1, CardId.HAVOC : -1, CardId.EXPECT_A_FIGHT : -1, CardId.INFERNAL_BLADE : -1,
    CardId.BODY_SLAM : -1, CardId.HELLRAISER : -1,
}

# cards with the Exhaust keyword
EXHAUSTING_CARDS = frozenset({CardId.SLIMED, CardId.TREMBLE, CardId.IMPERVIOUS, CardId.MOLTEN_FIST,
                              CardId.FEED, CardId.DOMINATE, CardId.FIEND_FIRE, CardId.FORGOTTEN_RITUAL,
                              CardId.INFERNAL_BLADE, CardId.NOT_YET, CardId.OFFERING})

# cards with the Unplayable keyword
UNPLAYABLE_CARDS = frozenset({CardId.DAZED, CardId.WOUND, CardId.INFECTION})

# cards with the Ethereal keyword: exhausted instead of discarded if still in hand at end of turn
ETHEREAL_CARDS = frozenset({CardId.DAZED})

class TargetType(Enum):
    AnyEnemy = auto()
    AllEnemies = auto()
    Self = auto()
    RandomEnemy = auto()
    NONE = auto()

class Card:
    card_id : CardId
    name : str
    type : CardType
    energy_cost : int | str
    target_type : TargetType
    is_upgraded : bool
    is_unplayable : bool
    restore_cost : int | str | None = None     # set while the cost is changed for this turn: the cost it gets back
    bonus_damage : int = 0                     # damage Rampage and Thrash have gained this combat
    shown_damage : int | None = None           # the damage printed on the card when it was loaded from the game

    def __init__(self):
        pass

    @property
    def exhausts(self) -> bool:
        return self.card_id in EXHAUSTING_CARDS

    @property
    def ethereal(self) -> bool:
        return self.card_id in ETHEREAL_CARDS

    @classmethod
    def from_dict(cls, card : dict):
        new_card = cls()
        new_card.card_id = CardId[card["id"]]
        new_card.type = CardType[card["type"]]
        new_card.name = card["name"]
        new_card.is_unplayable = not card["can_play"]
        if card["cost"] == "X":
            new_card.energy_cost = card["cost"]
        else:
            new_card.energy_cost = int(card["cost"])
        new_card.is_upgraded = card["is_upgraded"]
        if new_card.card_id == CardId.STOMP and new_card.energy_cost < 3:
            new_card.restore_cost = 3           # the shown cost already includes this turn's Attacks
        match = re.search(r"Deal\s+(\d+)", card.get("description") or "")
        new_card.shown_damage = int(match.group(1)) if match else None
        if card["target_type"] == "None":
            new_card.target_type = TargetType.NONE
        else:
            new_card.target_type = TargetType[card["target_type"]]
        return new_card

    @classmethod
    def create_slimed(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.SLIMED, "Slimed", CardType.Status
        c.energy_cost, c.target_type = 1, TargetType.NONE
        c.is_upgraded = c.is_unplayable = False
        return c

    @classmethod
    def create_infection(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.INFECTION, "Infection", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_dazed(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.DAZED, "Dazed", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_wound(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.WOUND, "Wound", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create(cls, card_id : CardId) -> Card:
        """A fresh copy of a card that enemies add to the player's piles."""
        return GENERATED_CARDS[card_id]()

    @classmethod
    def create_generated(cls, card_id : CardId, upgraded : bool = False) -> Card:
        """A fresh copy of a card that a card effect adds to the player's piles (Infernal Blade, Stoke)."""
        name, card_type, cost, target = GENERATABLE_CARDS.get(card_id) or TOKEN_CARDS[card_id]
        c = cls()
        c.card_id, c.name, c.type = card_id, name, card_type
        c.energy_cost, c.target_type = cost, target
        c.is_upgraded = c.is_unplayable = False
        return c.upgraded_copy() if upgraded else c

    def cheaper_this_turn(self, amount : int) -> Card:
        """A copy that costs `amount` less until the end of the turn (Stomp)."""
        new_card = Card.create_copy(self)
        if new_card.restore_cost is None:
            new_card.restore_cost = self.energy_cost
        new_card.energy_cost = max(0, self.energy_cost - amount)
        return new_card

    @property
    def is_strike(self) -> bool:
        return self.card_id in STRIKE_CARDS

    @property
    def is_upgradable(self) -> bool:
        return not self.is_upgraded and self.type != CardType.Status

    def upgraded_copy(self) -> Card:
        """A new, upgraded copy; the original is left alone because piles are shared between simulated states."""
        if not self.is_upgradable:
            raise ValueError(f"{self.name} cannot be upgraded")
        new_card = Card.create_copy(self)
        new_card.is_upgraded = True
        if not new_card.name.endswith("+"):
            new_card.name += "+"
        if new_card.energy_cost != "X":
            new_card.energy_cost = max(0, new_card.energy_cost + UPGRADE_COST_CHANGE.get(self.card_id, 0))
        return new_card

    def on_turn_end_in_hand(self, combat : CombatSimulator):
        if self.card_id == CardId.INFECTION:
            combat.combat_state.player.apply_damage(INFECTION_DAMAGE)

    @classmethod
    def create_copy(cls, card : Card) -> Card:
        new_card = cls()
        new_card.card_id = card.card_id
        new_card.type = card.type
        new_card.name = card.name
        new_card.energy_cost = card.energy_cost
        new_card.target_type = card.target_type
        new_card.is_upgraded = card.is_upgraded
        new_card.is_unplayable = card.is_unplayable
        new_card.restore_cost = card.restore_cost
        new_card.bonus_damage = card.bonus_damage
        return new_card

    def current_cost(self, player) -> int | str:
        """Energy cost now: the base cost plus Tangled on attacks."""
        if self.energy_cost == "X":
            return self.energy_cost
        if self.type == CardType.Skill and StatusId.CORRUPTION in player.status:
            return 0
        if self.type != CardType.Attack:
            return self.energy_cost
        return self.energy_cost + player.status_amount(StatusId.TANGLED)

    def play_card(self, combat : CombatSimulator, target_index : int, free : bool = False):
        """Play the card. Raises ValueError if it cannot be played; state is restored.
        A free play (auto-play) costs nothing and does not use up Free Attack."""
        player = combat.combat_state.player
        energy = combat.combat_state.energy
        cost = 0 if free else self.current_cost(player)
        free_attack = player.status.get(StatusId.FREE_ATTACK)
        free_attack_amount = free_attack.amount if free_attack else 0
        play = GET_CARD_FUNCTION[self.card_id]
        saved = snapshot(player) if player.relics else None

        try:
            if self.energy_cost == "X":
                x = energy + x_bonus(player) if player.relics else energy        # Chemical X
                if saved:
                    before_card_played(combat, self, 0 if free else energy)
                if not free:
                    combat.combat_state.energy = 0
                play(self, combat, target_index, self.is_upgraded, x)
            else:
                spent = cost
                if self.type == CardType.Attack and free_attack_amount > 0 and not free:
                    free_attack.amount -= 1
                    combat.combat_state.energy += cost
                    spent = 0
                if saved:
                    before_card_played(combat, self, spent)
                combat.combat_state.energy -= cost
                play(self, combat, target_index, self.is_upgraded)
        except ValueError:
            combat.combat_state.energy = energy
            if free_attack:
                free_attack.amount = free_attack_amount
            if saved:
                restore(player, saved)
            raise

        if self.type == CardType.Attack and StatusId.ONE_TWO_PUNCH in player.status:
            self._replay(combat, target_index, x if self.energy_cost == "X" else None)

    def _replay(self, combat : CombatSimulator, target_index : int, x):
        """One-Two Punch: play an attack a second time, skipping a target that has died."""
        player = combat.combat_state.player
        punch = player.status[StatusId.ONE_TWO_PUNCH]
        punch.amount -= 1
        if punch.amount <= 0:
            del player.status[StatusId.ONE_TWO_PUNCH]
        if self.target_type == TargetType.AnyEnemy and combat.combat_state.enemies[target_index].current_hp <= 0:
            return
        if x is None:
            GET_CARD_FUNCTION[self.card_id](self, combat, target_index, self.is_upgraded)
        else:
            GET_CARD_FUNCTION[self.card_id](self, combat, target_index, self.is_upgraded, x)

    def can_play_card(self, combat : CombatSimulator, target_index):
        if self.is_unplayable:
            return False
        if StatusId.RINGING in combat.combat_state.player.status and combat.combat_state.cards_played >= 1:
            return False
        if type(self.energy_cost) is str and self.energy_cost == "X":
            return True
        if self.type == CardType.Attack and StatusId.FREE_ATTACK in combat.combat_state.player.status:
            if combat.combat_state.player.status[StatusId.FREE_ATTACK].amount > 0:
                return True
        if self.current_cost(combat.combat_state.player) <= combat.combat_state.energy:
            return True
        return False

###
### Helpers
###

def _enemy(combat : CombatSimulator, target_index : int) -> Enemy:
    if not 0 <= target_index < len(combat.combat_state.enemies):
        raise ValueError(f"Target index {target_index} out of bounds")
    return combat.combat_state.enemies[target_index]

def _living(combat : CombatSimulator) -> list[Enemy]:
    return [e for e in combat.combat_state.enemies if e.current_hp > 0]

def _attack(combat : CombatSimulator, base : int, target : Creature, hits : int = 1):
    owner = combat.combat_state.player
    target.apply_attack_damage(combat.calculate_damage(base, owner, target), owner, hits)

def _gain_block(combat : CombatSimulator, base : int):
    # Unmovable doubles the first block gains from cards each turn
    owner = combat.combat_state.player
    doubled = owner.card_blocks_this_turn < owner.status_amount(StatusId.UNMOVABLE)
    owner.card_blocks_this_turn += 1
    multiplier = 2 if doubled else 1
    if owner.relics:
        multiplier *= block_multiplier(owner, combat.card_in_play)     # Vambrace
    block = combat.calculate_block(base, owner, multiplier)
    if owner.relics:
        block_gained(owner, combat.card_in_play, block)
    combat.gain_block(owner, block)

def _vulnerable(combat : CombatSimulator, target : Creature, amount : int):
    player = combat.combat_state.player
    before = target.status_amount(StatusId.VULNERABLE)
    if player.relics:
        amount *= debuff_multiplier(player, combat.card_in_play, target)      # Unsettling Lamp
    target.apply_status(StatusId.VULNERABLE, amount)
    if target.status_amount(StatusId.VULNERABLE) > before:      # Vicious: not if Artifact stopped it
        player.draw_cards(player.status_amount(StatusId.VICIOUS))

def _temp_strength(target : Creature, marker : StatusId, amount : int, sign : int, combat : CombatSimulator | None = None):
    """Strength that is taken back when the target's turn ends (Setup Strike, Mangle). `sign` is -1 for a loss."""
    if sign < 0 and combat is not None and combat.combat_state.player.relics:
        amount *= debuff_multiplier(combat.combat_state.player, combat.card_in_play, target)      # Unsettling Lamp doubles the marker, which doubles the Strength it takes
    before = target.status_amount(marker)
    target.apply_status(marker, amount)
    if target.status_amount(marker) == before:          # Artifact stopped the debuff
        return
    target.apply_status(StatusId.STRENGTH, sign * amount, bypass_artifact=True)

PLAIN_DAMAGE = {        # id : (damage, damage upgraded) of the cards that print one fixed number
    CardId.ANGER : (6, 8), CardId.BASH : (8, 10), CardId.BLUDGEON : (32, 42), CardId.BREAK : (20, 30),
    CardId.BREAKTHROUGH : (9, 13), CardId.CINDER : (18, 24), CardId.CONFLAGRATION : (2, 2),
    CardId.DISMANTLE : (8, 10), CardId.FEED : (10, 12), CardId.FIEND_FIRE : (7, 10), CardId.FIGHT_ME : (5, 6),
    CardId.GIANT_ROCK : (16, 20), CardId.HEADBUTT : (9, 12), CardId.HEMOKINESIS : (15, 20),
    CardId.HOWL_FROM_BEYOND : (16, 21), CardId.IRON_WAVE : (5, 7), CardId.MANGLE : (15, 20),
    CardId.MOLTEN_FIST : (10, 14), CardId.PACTS_END : (17, 23), CardId.PILLAGE : (6, 9), CardId.POMMEL_STRIKE : (9, 10),
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
    if card.card_id == CardId.THRASH:
        return (6 if up else 4) + card.bonus_damage
    return PLAIN_DAMAGE[card.card_id][up]

###
### Card Functions, in alphabetical order
###

def play_aggression(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.AGGRESSION, 1)

def play_anger(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    combat.combat_state.player.discard_pile.append(Card.create_copy(card))
    _attack(combat, 8 if is_upgraded else 6, target)

def play_armaments(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 5)
    player = combat.combat_state.player
    upgradable = [i for i, c in enumerate(player.hand) if c.is_upgradable]
    if is_upgraded:
        for i in upgradable:
            player.upgrade_card(player.hand[i])
    else:
        combat.request_choice("upgrade", upgradable)

def play_ashen_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    per_exhausted = 4 if is_upgraded else 3
    _attack(combat, 6 + per_exhausted * len(combat.combat_state.player.exhaust_pile), target)

def play_barricade(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if StatusId.BARRICADE not in player.status:
        player.apply_status(StatusId.BARRICADE, 1)

def play_bash(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 10 if is_upgraded else 8, target)
    _vulnerable(combat, target, 3 if is_upgraded else 2)

def play_battle_trance(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.draw_cards(4 if is_upgraded else 3)
    if StatusId.NO_DRAW not in player.status:       # it does not stack
        player.apply_status(StatusId.NO_DRAW, 1)

def play_blood_wall(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 20 if is_upgraded else 16)
    combat.combat_state.player.lose_hp(2)

def play_bloodletting(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.lose_hp(3)
    combat.gain_energy(3 if is_upgraded else 2)

def play_bludgeon(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 42 if is_upgraded else 32, target)

def play_body_slam(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, combat.combat_state.player.block, target)

def play_brand(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.lose_hp(1)
    if player.current_hp > 0:
        player.apply_status(StatusId.STRENGTH, 2 if is_upgraded else 1)     # before the pick; same result
        combat.request_choice("exhaust", list(range(len(player.hand))))

def play_break(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 30 if is_upgraded else 20, target)
    _vulnerable(combat, target, 7 if is_upgraded else 5)

def play_breakthrough(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.lose_hp(1)
    for target in list(combat.combat_state.enemies):
        _attack(combat, 13 if is_upgraded else 9, target)

def play_bully(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    per_vulnerable = 3 if is_upgraded else 2
    _attack(combat, 4 + per_vulnerable * target.status_amount(StatusId.VULNERABLE), target)

def play_burning_pact(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    hand = combat.combat_state.player.hand
    combat.request_choice("exhaust", list(range(len(hand))), amount=3 if is_upgraded else 2)

def play_cascade(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    player = combat.combat_state.player
    # the cards are all taken off the top first, then played in that order
    taken = []
    for _ in range(x + (1 if is_upgraded else 0)):
        top = player.take_top()
        if top is None:
            break
        taken.append(top)
    for top in taken:
        if combat.is_over:
            break
        if top.card_id in UNPLAYABLE_CARDS:
            player.discard_pile.append(top)         # an unplayable card goes to the discard pile unplayed
        else:
            combat.auto_play(top)

def play_cinder(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 24 if is_upgraded else 18, target)
    hand = combat.combat_state.player.hand
    if hand:
        victim = hand[0] if len(hand) == 1 else rng.choice(hand)
        combat.combat_state.player.exhaust_card(victim)
        combat.fire(EventType.CARD_EXHAUSTED, victim)

def play_colossus(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)
    combat.combat_state.player.apply_status(StatusId.COLOSSUS, 1)

def play_conflagration(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in _living(combat):
        _attack(combat, 2, target, 5 if is_upgraded else 4)

def play_corruption(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if StatusId.CORRUPTION not in player.status:
        player.apply_status(StatusId.CORRUPTION, 1)

def play_crimson_mantle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.CRIMSON_MANTLE, 10 if is_upgraded else 8)

def play_cruelty(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.CRUELTY, 50 if is_upgraded else 25)

def play_dark_embrace(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.DARK_EMBRACE, 1)

def play_defend(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)

def play_demon_form(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.DEMON_FORM, 3 if is_upgraded else 2)

def play_dismantle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    hits = 2 if StatusId.VULNERABLE in target.status else 1
    _attack(combat, 10 if is_upgraded else 8, target, hits)

def play_dominate(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _vulnerable(combat, target, 2 if is_upgraded else 1)
    combat.combat_state.player.apply_status(StatusId.STRENGTH, target.status_amount(StatusId.VULNERABLE))

def play_drum_of_battle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.draw_cards(2)        # the energy comes when the card is exhausted

def play_evil_eye(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    gains = 2 if combat.combat_state.player.cards_exhausted_this_turn > 0 else 1
    for _ in range(gains):
        _gain_block(combat, 11 if is_upgraded else 8)

def play_expect_a_fight(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    combat.gain_energy(sum(1 for c in player.hand if c.type == CardType.Attack))
    player.apply_status(StatusId.NO_ENERGY_GAIN, 1)

def play_feed(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 12 if is_upgraded else 10, target)
    if target.current_hp <= 0 and StatusId.MINION not in target.status:
        gain = 4 if is_upgraded else 3
        player = combat.combat_state.player
        player.max_hp += gain
        player.current_hp += gain

def play_feel_no_pain(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.FEEL_NO_PAIN, 4 if is_upgraded else 3)

def play_fiend_fire(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    player = combat.combat_state.player
    exhausted = list(player.hand)
    for victim in exhausted:
        player.exhaust_card(victim)
        combat.fire(EventType.CARD_EXHAUSTED, victim)
    if exhausted:
        _attack(combat, 10 if is_upgraded else 7, target, len(exhausted))

def play_fight_me(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 6 if is_upgraded else 5, target, 2)
    combat.combat_state.player.apply_status(StatusId.STRENGTH, 4 if is_upgraded else 3)
    target.apply_status(StatusId.STRENGTH, 1)

def play_flame_barrier(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 16 if is_upgraded else 12)
    combat.combat_state.player.apply_status(StatusId.FLAME_BARRIER, 6 if is_upgraded else 4)

def play_forgotten_ritual(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    if combat.combat_state.player.cards_exhausted_this_turn > 0:
        combat.gain_energy(4 if is_upgraded else 3)

def play_giant_rock(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 20 if is_upgraded else 16, target)

def play_havoc(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if not player.draw_pile:
        player.shuffle_discard_into_draw()
    if not player.draw_pile:
        return
    top = player.draw_pile[-1]
    if player.known_top == 0:
        player.unknown_draws += 1   # the top card is unknown to the agent, so this is a chance event
    if top.type == CardType.Status:
        player.exhaust_card(top)
        combat.fire(EventType.CARD_EXHAUSTED, top)
    else:
        combat.auto_play(top, force_exhaust=True)

def play_headbutt(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 12 if is_upgraded else 9, target)
    combat.request_choice("to_draw_pile", list(range(len(combat.combat_state.player.discard_pile))), pile="discard")

def play_hellraiser(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if StatusId.HELLRAISER not in player.status:
        player.apply_status(StatusId.HELLRAISER, 1)

def play_hemokinesis(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    combat.combat_state.player.lose_hp(2)
    _attack(combat, 20 if is_upgraded else 15, target)

def play_howl_from_beyond(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in _living(combat):
        _attack(combat, 21 if is_upgraded else 16, target)

def play_impervious(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 40 if is_upgraded else 30)

def play_infernal_blade(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    new_card = Card.create_generated(rng.choice(INFERNAL_BLADE_POOL))
    new_card.restore_cost, new_card.energy_cost = new_card.energy_cost, 0
    combat.combat_state.player.add_to_hand(new_card)

def play_inferno(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.apply_status(StatusId.INFERNO, 9 if is_upgraded else 6)
    player.inferno_plays += 1

def play_inflame(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.STRENGTH, 3 if is_upgraded else 2)

def play_iron_wave(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _gain_block(combat, 7 if is_upgraded else 5)
    _attack(combat, 7 if is_upgraded else 5, target)

def play_juggernaut(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.JUGGERNAUT, 8 if is_upgraded else 6)

def play_juggling(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.JUGGLING, 1)

def play_mangle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 20 if is_upgraded else 15, target)
    _temp_strength(target, StatusId.MANGLE, 15 if is_upgraded else 10, -1, combat)

def play_molten_fist(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 14 if is_upgraded else 10, target)
    vulnerable = target.status_amount(StatusId.VULNERABLE)
    if target.current_hp > 0 and vulnerable > 0:
        _vulnerable(combat, target, vulnerable)

def play_not_yet(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.current_hp = min(player.max_hp, player.current_hp + (13 if is_upgraded else 10))

def play_offering(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.lose_hp(6)
    if player.current_hp > 0:
        combat.gain_energy(2)
        player.draw_cards(5 if is_upgraded else 3)

def play_one_two_punch(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.ONE_TWO_PUNCH, 2 if is_upgraded else 1)

def play_pacts_end(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    if len(combat.combat_state.player.exhaust_pile) >= 3:
        for target in _living(combat):
            _attack(combat, 23 if is_upgraded else 17, target)

def play_perfected_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    strikes = _strikes(combat.combat_state.player, card)
    _attack(combat, 6 + (3 if is_upgraded else 2) * strikes, target)

def play_pillage(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 9 if is_upgraded else 6, target)
    player = combat.combat_state.player
    while True:                 # draw until something that is not an Attack comes up, or the hand is full
        drawn = player.draw_card()
        if drawn is None or drawn.type != CardType.Attack or len(player.hand) >= 10:
            break

def play_pommel_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 10 if is_upgraded else 9, target)
    combat.combat_state.player.draw_cards(2 if is_upgraded else 1)

def play_primal_force(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    hand = combat.combat_state.player.hand
    for i, c in enumerate(hand):
        if c.type == CardType.Attack:
            hand[i] = Card.create_generated(CardId.GIANT_ROCK, is_upgraded)

def play_pyre(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    energy = 2 if is_upgraded else 1
    combat.combat_state.player.apply_status(StatusId.PYRE, energy)
    combat.combat_state.max_energy += energy

def play_rage(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.RAGE, 5 if is_upgraded else 3)

def play_rampage(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # `card` is this play's own copy (see CombatSimulator.private_copy), so it can remember the growth
    target = _enemy(combat, target_index)
    _attack(combat, 9 + card.bonus_damage, target)
    card.bonus_damage += 9 if is_upgraded else 5

def play_rupture(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.RUPTURE, 2 if is_upgraded else 1)

def play_second_wind(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    for victim in [c for c in player.hand if c.type != CardType.Attack]:
        player.exhaust_card(victim)
        combat.fire(EventType.CARD_EXHAUSTED, victim)
        _gain_block(combat, 7 if is_upgraded else 5)

def play_setup_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 9 if is_upgraded else 7, target)
    _temp_strength(combat.combat_state.player, StatusId.SETUP_STRIKE, 3 if is_upgraded else 2, 1)

def play_shrug_it_off(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 11 if is_upgraded else 8)
    combat.combat_state.player.draw_cards(1)

def play_slimed(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.draw_card()

def play_spite(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    repeat = 3 if is_upgraded else 2
    _attack(combat, 5, target, repeat if combat.combat_state.player.lost_hp_this_turn else 1)

def play_stampede(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.STAMPEDE, 1)

def play_stoke(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    exhausted = list(player.hand)
    for victim in exhausted:
        player.exhaust_card(victim)
        combat.fire(EventType.CARD_EXHAUSTED, victim)
    for _ in exhausted:         # a random card (repeats allowed) for each one exhausted
        player.add_to_hand(Card.create_generated(rng.choice(STOKE_POOL), is_upgraded))

def play_stomp(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in _living(combat):
        _attack(combat, 15 if is_upgraded else 12, target)

def play_stone_armor(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.PLATING, 6 if is_upgraded else 4)

def play_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 9 if is_upgraded else 6, target)

def play_sword_boomerang(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for _ in range(4 if is_upgraded else 3):
        living = _living(combat)
        if not living:
            break
        target = living[0] if len(living) == 1 else rng.choice(living)
        _attack(combat, 3, target)
        combat.resolve_deaths()

def play_taunt(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _gain_block(combat, 8 if is_upgraded else 7)
    _vulnerable(combat, target, 2 if is_upgraded else 1)

def play_tear_asunder(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    # one hit, and one more for every time the player has lost HP in this fight
    _attack(combat, 7 if is_upgraded else 5, target, 1 + combat.combat_state.player.hp_loss_events)

def play_thrash(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # `card` is this play's own copy (see CombatSimulator.private_copy), so it can remember the growth
    target = _enemy(combat, target_index)
    player = combat.combat_state.player
    _attack(combat, (6 if is_upgraded else 4) + card.bonus_damage, target, 2)
    attacks = [c for c in player.hand if c.type == CardType.Attack]
    if attacks:
        victim = attacks[0] if len(attacks) == 1 else rng.choice(attacks)
        from sts2_lite.creature import Creature      # card.py is imported by creature.py's package
        card.bonus_damage += combat.calculate_damage(_printed_damage(victim, combat), player, Creature())
        player.exhaust_card(victim)
        combat.fire(EventType.CARD_EXHAUSTED, victim)

def play_thunderclap(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in list(combat.combat_state.enemies):
        _attack(combat, 7 if is_upgraded else 4, target)
        _vulnerable(combat, target, 1)

def play_tremble(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _vulnerable(combat, target, 4 if is_upgraded else 3)

def play_true_grit(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 9 if is_upgraded else 7)
    player = combat.combat_state.player
    hand = player.hand
    if is_upgraded:
        combat.request_choice("exhaust", list(range(len(hand))))
    elif hand:
        victim = hand[0] if len(hand) == 1 else rng.choice(hand)
        player.exhaust_card(victim)
        combat.fire(EventType.CARD_EXHAUSTED, victim)

def play_twin_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 7 if is_upgraded else 5, target, 2)

def play_unmovable(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.UNMOVABLE, 1)

def play_unrelenting(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 20 if is_upgraded else 14, target)
    combat.combat_state.player.apply_status(StatusId.FREE_ATTACK, 1)

def play_uppercut(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 13, target)
    debuff = 2 if is_upgraded else 1
    player = combat.combat_state.player
    target.apply_status(StatusId.WEAK, debuff * debuff_multiplier(player, combat.card_in_play, target) if player.relics else debuff)
    _vulnerable(combat, target, debuff)

def play_vicious(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.VICIOUS, 2 if is_upgraded else 1)

def play_whirlwind(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    for _ in range(x):
        for target in _living(combat):
            _attack(combat, 8 if is_upgraded else 5, target)
        combat.resolve_deaths()

###
### map to get function from card id
###

GET_CARD_FUNCTION : dict[CardId, function] = {
    CardId.AGGRESSION : play_aggression,
    CardId.ANGER : play_anger,
    CardId.ARMAMENTS : play_armaments,
    CardId.ASHEN_STRIKE : play_ashen_strike,
    CardId.BARRICADE : play_barricade,
    CardId.BASH : play_bash,
    CardId.BATTLE_TRANCE : play_battle_trance,
    CardId.BLOODLETTING : play_bloodletting,
    CardId.BLOOD_WALL : play_blood_wall,
    CardId.BLUDGEON : play_bludgeon,
    CardId.BODY_SLAM : play_body_slam,
    CardId.BRAND : play_brand,
    CardId.BREAK : play_break,
    CardId.BREAKTHROUGH : play_breakthrough,
    CardId.BULLY : play_bully,
    CardId.BURNING_PACT : play_burning_pact,
    CardId.CASCADE : play_cascade,
    CardId.CINDER : play_cinder,
    CardId.COLOSSUS : play_colossus,
    CardId.CONFLAGRATION : play_conflagration,
    CardId.CORRUPTION : play_corruption,
    CardId.CRIMSON_MANTLE : play_crimson_mantle,
    CardId.CRUELTY : play_cruelty,
    CardId.DARK_EMBRACE : play_dark_embrace,
    CardId.DEFEND_IRONCLAD : play_defend,
    CardId.DEMON_FORM : play_demon_form,
    CardId.DISMANTLE : play_dismantle,
    CardId.DOMINATE : play_dominate,
    CardId.DRUM_OF_BATTLE : play_drum_of_battle,
    CardId.EVIL_EYE : play_evil_eye,
    CardId.EXPECT_A_FIGHT : play_expect_a_fight,
    CardId.FEED : play_feed,
    CardId.FEEL_NO_PAIN : play_feel_no_pain,
    CardId.FIEND_FIRE : play_fiend_fire,
    CardId.FIGHT_ME : play_fight_me,
    CardId.FLAME_BARRIER : play_flame_barrier,
    CardId.FORGOTTEN_RITUAL : play_forgotten_ritual,
    CardId.GIANT_ROCK : play_giant_rock,
    CardId.HAVOC : play_havoc,
    CardId.HEADBUTT : play_headbutt,
    CardId.HELLRAISER : play_hellraiser,
    CardId.HEMOKINESIS : play_hemokinesis,
    CardId.HOWL_FROM_BEYOND : play_howl_from_beyond,
    CardId.IMPERVIOUS : play_impervious,
    CardId.INFERNAL_BLADE : play_infernal_blade,
    CardId.INFERNO : play_inferno,
    CardId.INFLAME : play_inflame,
    CardId.IRON_WAVE : play_iron_wave,
    CardId.JUGGERNAUT : play_juggernaut,
    CardId.JUGGLING : play_juggling,
    CardId.MANGLE : play_mangle,
    CardId.MOLTEN_FIST : play_molten_fist,
    CardId.NOT_YET : play_not_yet,
    CardId.OFFERING : play_offering,
    CardId.ONE_TWO_PUNCH : play_one_two_punch,
    CardId.PACTS_END : play_pacts_end,
    CardId.PERFECTED_STRIKE : play_perfected_strike,
    CardId.PILLAGE : play_pillage,
    CardId.POMMEL_STRIKE : play_pommel_strike,
    CardId.PRIMAL_FORCE : play_primal_force,
    CardId.PYRE : play_pyre,
    CardId.RAGE : play_rage,
    CardId.RAMPAGE : play_rampage,
    CardId.RUPTURE : play_rupture,
    CardId.SECOND_WIND : play_second_wind,
    CardId.SETUP_STRIKE : play_setup_strike,
    CardId.SHRUG_IT_OFF : play_shrug_it_off,
    CardId.SLIMED : play_slimed,
    CardId.SPITE : play_spite,
    CardId.STAMPEDE : play_stampede,
    CardId.STOKE : play_stoke,
    CardId.STOMP : play_stomp,
    CardId.STONE_ARMOR : play_stone_armor,
    CardId.STRIKE_IRONCLAD : play_strike,
    CardId.SWORD_BOOMERANG : play_sword_boomerang,
    CardId.TAUNT : play_taunt,
    CardId.TEAR_ASUNDER : play_tear_asunder,
    CardId.THRASH : play_thrash,
    CardId.THUNDERCLAP : play_thunderclap,
    CardId.TREMBLE : play_tremble,
    CardId.TRUE_GRIT : play_true_grit,
    CardId.TWIN_STRIKE : play_twin_strike,
    CardId.UNMOVABLE : play_unmovable,
    CardId.UNRELENTING : play_unrelenting,
    CardId.UPPERCUT : play_uppercut,
    CardId.VICIOUS : play_vicious,
    CardId.WHIRLWIND : play_whirlwind,
}

# the Ironclad cards that card effects can add to the player's piles (no Basic or Ancient cards, Feed and Not Yet
# can't be generated, Tank and Demonic Shield are multiplayer only): (name, type, cost, target)
S, A, ALL, RAND = TargetType.Self, TargetType.AnyEnemy, TargetType.AllEnemies, TargetType.RandomEnemy
GENERATABLE_CARDS = {
    CardId.AGGRESSION : ("Aggression", CardType.Power, 1, S),
    CardId.ANGER : ("Anger", CardType.Attack, 0, A),
    CardId.ARMAMENTS : ("Armaments", CardType.Skill, 1, S),
    CardId.ASHEN_STRIKE : ("Ashen Strike", CardType.Attack, 1, A),
    CardId.BARRICADE : ("Barricade", CardType.Power, 3, S),
    CardId.BATTLE_TRANCE : ("Battle Trance", CardType.Skill, 0, S),
    CardId.BLOOD_WALL : ("Blood Wall", CardType.Skill, 2, S),
    CardId.BLOODLETTING : ("Bloodletting", CardType.Skill, 0, S),
    CardId.BLUDGEON : ("Bludgeon", CardType.Attack, 3, A),
    CardId.BODY_SLAM : ("Body Slam", CardType.Attack, 1, A),
    CardId.BRAND : ("Brand", CardType.Skill, 0, S),
    CardId.BREAKTHROUGH : ("Breakthrough", CardType.Attack, 1, ALL),
    CardId.BULLY : ("Bully", CardType.Attack, 0, A),
    CardId.BURNING_PACT : ("Burning Pact", CardType.Skill, 1, S),
    CardId.CASCADE : ("Cascade", CardType.Skill, "X", S),
    CardId.CINDER : ("Cinder", CardType.Attack, 2, A),
    CardId.COLOSSUS : ("Colossus", CardType.Skill, 1, S),
    CardId.CONFLAGRATION : ("Conflagration", CardType.Attack, 1, ALL),
    CardId.CRIMSON_MANTLE : ("Crimson Mantle", CardType.Power, 1, S),
    CardId.CRUELTY : ("Cruelty", CardType.Power, 1, S),
    CardId.DARK_EMBRACE : ("Dark Embrace", CardType.Power, 2, S),
    CardId.DEMON_FORM : ("Demon Form", CardType.Power, 3, S),
    CardId.DISMANTLE : ("Dismantle", CardType.Attack, 1, A),
    CardId.DOMINATE : ("Dominate", CardType.Skill, 1, A),
    CardId.DRUM_OF_BATTLE : ("Drum of Battle", CardType.Skill, 1, S),
    CardId.EVIL_EYE : ("Evil Eye", CardType.Skill, 1, S),
    CardId.EXPECT_A_FIGHT : ("Expect a Fight", CardType.Skill, 2, S),
    CardId.FEEL_NO_PAIN : ("Feel No Pain", CardType.Power, 1, S),
    CardId.FIEND_FIRE : ("Fiend Fire", CardType.Attack, 2, A),
    CardId.FIGHT_ME : ("Fight Me", CardType.Attack, 2, A),
    CardId.FLAME_BARRIER : ("Flame Barrier", CardType.Skill, 2, S),
    CardId.FORGOTTEN_RITUAL : ("Forgotten Ritual", CardType.Skill, 1, S),
    CardId.HAVOC : ("Havoc", CardType.Skill, 1, S),
    CardId.HEADBUTT : ("Headbutt", CardType.Attack, 1, A),
    CardId.HELLRAISER : ("Hellraiser", CardType.Power, 2, S),
    CardId.HEMOKINESIS : ("Hemokinesis", CardType.Attack, 1, A),
    CardId.HOWL_FROM_BEYOND : ("Howl from Beyond", CardType.Attack, 3, ALL),
    CardId.IMPERVIOUS : ("Impervious", CardType.Skill, 2, S),
    CardId.INFERNAL_BLADE : ("Infernal Blade", CardType.Skill, 1, S),
    CardId.INFERNO : ("Inferno", CardType.Power, 1, S),
    CardId.INFLAME : ("Inflame", CardType.Power, 1, S),
    CardId.IRON_WAVE : ("Iron Wave", CardType.Attack, 1, A),
    CardId.JUGGERNAUT : ("Juggernaut", CardType.Power, 2, S),
    CardId.JUGGLING : ("Juggling", CardType.Power, 1, S),
    CardId.MANGLE : ("Mangle", CardType.Attack, 3, A),
    CardId.MOLTEN_FIST : ("Molten Fist", CardType.Attack, 1, A),
    CardId.OFFERING : ("Offering", CardType.Skill, 0, S),
    CardId.ONE_TWO_PUNCH : ("One-Two Punch", CardType.Skill, 1, S),
    CardId.PACTS_END : ("Pact's End", CardType.Attack, 0, ALL),
    CardId.PERFECTED_STRIKE : ("Perfected Strike", CardType.Attack, 2, A),
    CardId.PILLAGE : ("Pillage", CardType.Attack, 1, A),
    CardId.POMMEL_STRIKE : ("Pommel Strike", CardType.Attack, 1, A),
    CardId.PRIMAL_FORCE : ("Primal Force", CardType.Skill, 0, S),
    CardId.PYRE : ("Pyre", CardType.Power, 2, S),
    CardId.RAGE : ("Rage", CardType.Skill, 0, S),
    CardId.RAMPAGE : ("Rampage", CardType.Attack, 1, A),
    CardId.RUPTURE : ("Rupture", CardType.Power, 1, S),
    CardId.SECOND_WIND : ("Second Wind", CardType.Skill, 1, S),
    CardId.SETUP_STRIKE : ("Setup Strike", CardType.Attack, 1, A),
    CardId.SHRUG_IT_OFF : ("Shrug It Off", CardType.Skill, 1, S),
    CardId.SPITE : ("Spite", CardType.Attack, 0, A),
    CardId.STAMPEDE : ("Stampede", CardType.Power, 2, S),
    CardId.STOKE : ("Stoke", CardType.Skill, 1, S),
    CardId.STOMP : ("Stomp", CardType.Attack, 3, ALL),
    CardId.STONE_ARMOR : ("Stone Armor", CardType.Power, 1, S),
    CardId.SWORD_BOOMERANG : ("Sword Boomerang", CardType.Attack, 1, RAND),
    CardId.TAUNT : ("Taunt", CardType.Skill, 1, A),
    CardId.TEAR_ASUNDER : ("Tear Asunder", CardType.Attack, 2, A),
    CardId.THRASH : ("Thrash", CardType.Attack, 1, A),
    CardId.THUNDERCLAP : ("Thunderclap", CardType.Attack, 1, ALL),
    CardId.TREMBLE : ("Tremble", CardType.Skill, 1, A),
    CardId.TRUE_GRIT : ("True Grit", CardType.Skill, 1, S),
    CardId.TWIN_STRIKE : ("Twin Strike", CardType.Attack, 1, A),
    CardId.UNMOVABLE : ("Unmovable", CardType.Power, 2, S),
    CardId.UNRELENTING : ("Unrelenting", CardType.Attack, 2, A),
    CardId.UPPERCUT : ("Uppercut", CardType.Attack, 2, A),
    CardId.VICIOUS : ("Vicious", CardType.Power, 1, S),
    CardId.WHIRLWIND : ("Whirlwind", CardType.Attack, "X", ALL),
}
TOKEN_CARDS = {CardId.GIANT_ROCK : ("Giant Rock", CardType.Attack, 1, A)}      # made by Primal Force
INFERNAL_BLADE_POOL = [cid for cid, (_, card_type, _, _) in GENERATABLE_CARDS.items() if card_type == CardType.Attack]
STOKE_POOL = list(GENERATABLE_CARDS)

# cards with the Strike tag (Hellraiser plays them when they are drawn)
STRIKE_CARDS = frozenset({CardId.STRIKE_IRONCLAD, CardId.PERFECTED_STRIKE, CardId.POMMEL_STRIKE, CardId.TWIN_STRIKE,
                          CardId.ASHEN_STRIKE, CardId.SETUP_STRIKE})

GENERATED_CARDS = {
    CardId.SLIMED : Card.create_slimed,
    CardId.INFECTION : Card.create_infection,
    CardId.DAZED : Card.create_dazed,
    CardId.WOUND : Card.create_wound,
}
