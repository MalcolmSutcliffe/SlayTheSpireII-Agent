from __future__ import annotations
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from sts2_lite.creature import Creature
    from sts2_lite.combat import CombatSimulator

from enum import Enum, auto

from sts2_lite import rng
from sts2_lite.events import EventType

class StatusId(Enum):
    STRENGTH = auto()
    WEAK = auto()
    VULNERABLE = auto()
    FRAIL = auto()
    DEXTERITY = auto()
    SHRINK = auto()
    THORNS = auto()
    RAVENOUS = auto()
    SUCK = auto()
    SLOW = auto()
    TERRITORIAL = auto()
    CRIMSON_MANTLE = auto()
    INFESTED = auto()
    FREE_ATTACK = auto()
    SLIPPERY = auto()
    RITUAL = auto()
    PLATING = auto()
    SKITTISH = auto()
    SHRIEK = auto()
    VIGOR = auto()
    SMOGGY = auto()
    MINION = auto()
    STEAM_ERUPTION = auto()
    TANGLED = auto()
    CONSTRICT = auto()
    ARTIFACT = auto()
    ILLUSION = auto()
    PLOW = auto()
    RINGING = auto()
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
    UNMOVABLE = auto()
    VICIOUS = auto()
    AGGRESSION = auto()
    NO_DRAW = auto()
    NO_ENERGY_GAIN = auto()
    SETUP_STRIKE = auto()
    MANGLE = auto()
    HELLRAISER = auto()
    INFERNO = auto()
    SELF_FORMING_CLAY = auto()

INFESTED_SPAWNS = 4

class StatusBehaviour(Enum):
    STATIC = auto()
    DECREASE_BY_ONE = auto()
    RESET_TO_ZERO = auto()

STATUS_BEAVIOURS : dict[StatusId, StatusBehaviour] = {
    StatusId.STRENGTH : StatusBehaviour.STATIC,
    StatusId.WEAK : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.VULNERABLE : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.FRAIL : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.DEXTERITY : StatusBehaviour.STATIC,
    StatusId.SHRINK : StatusBehaviour.STATIC,
    StatusId.THORNS : StatusBehaviour.STATIC,
    StatusId.RAVENOUS : StatusBehaviour.STATIC,
    StatusId.SUCK : StatusBehaviour.STATIC,
    StatusId.SLOW : StatusBehaviour.RESET_TO_ZERO,
    StatusId.TERRITORIAL : StatusBehaviour.STATIC,
    StatusId.CRIMSON_MANTLE : StatusBehaviour.STATIC,
    StatusId.INFESTED : StatusBehaviour.STATIC,
    StatusId.FREE_ATTACK : StatusBehaviour.STATIC,
    StatusId.SLIPPERY : StatusBehaviour.STATIC,
    StatusId.RITUAL : StatusBehaviour.STATIC,
    StatusId.PLATING : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.SKITTISH : StatusBehaviour.STATIC,
    StatusId.SHRIEK : StatusBehaviour.STATIC,
    StatusId.VIGOR : StatusBehaviour.STATIC,
    StatusId.SMOGGY : StatusBehaviour.STATIC,
    StatusId.MINION : StatusBehaviour.STATIC,
    StatusId.STEAM_ERUPTION : StatusBehaviour.STATIC,
    StatusId.TANGLED : StatusBehaviour.STATIC,
    StatusId.CONSTRICT : StatusBehaviour.STATIC,
    StatusId.ARTIFACT : StatusBehaviour.STATIC,
    StatusId.ILLUSION : StatusBehaviour.STATIC,
    StatusId.PLOW : StatusBehaviour.STATIC,
    StatusId.RINGING : StatusBehaviour.STATIC,
    StatusId.BARRICADE : StatusBehaviour.STATIC,
    StatusId.COLOSSUS : StatusBehaviour.DECREASE_BY_ONE,
    StatusId.CORRUPTION : StatusBehaviour.STATIC,
    StatusId.CRUELTY : StatusBehaviour.STATIC,
    StatusId.DARK_EMBRACE : StatusBehaviour.STATIC,
    StatusId.DEMON_FORM : StatusBehaviour.STATIC,
    StatusId.FEEL_NO_PAIN : StatusBehaviour.STATIC,
    StatusId.FLAME_BARRIER : StatusBehaviour.STATIC,
    StatusId.JUGGERNAUT : StatusBehaviour.STATIC,
    StatusId.JUGGLING : StatusBehaviour.STATIC,
    StatusId.ONE_TWO_PUNCH : StatusBehaviour.STATIC,
    StatusId.PYRE : StatusBehaviour.STATIC,
    StatusId.RAGE : StatusBehaviour.STATIC,
    StatusId.RUPTURE : StatusBehaviour.STATIC,
    StatusId.STAMPEDE : StatusBehaviour.STATIC,
    StatusId.UNMOVABLE : StatusBehaviour.STATIC,
    StatusId.VICIOUS : StatusBehaviour.STATIC,
    StatusId.AGGRESSION : StatusBehaviour.STATIC,
    StatusId.NO_DRAW : StatusBehaviour.STATIC,          # both are removed when the player's turn ends
    StatusId.NO_ENERGY_GAIN : StatusBehaviour.STATIC,
    StatusId.SETUP_STRIKE : StatusBehaviour.STATIC,     # the Strength is returned when the owner's turn ends
    StatusId.MANGLE : StatusBehaviour.STATIC,
    StatusId.HELLRAISER : StatusBehaviour.STATIC,
    StatusId.INFERNO : StatusBehaviour.STATIC,
    StatusId.SELF_FORMING_CLAY : StatusBehaviour.STATIC,     # paid out and removed at the start of the next turn
}

DEBUFFS = frozenset({StatusId.WEAK, StatusId.VULNERABLE, StatusId.FRAIL, StatusId.SHRINK,
                     StatusId.CONSTRICT, StatusId.TANGLED, StatusId.RINGING,
                     StatusId.NO_DRAW, StatusId.NO_ENERGY_GAIN, StatusId.MANGLE})

def is_debuff(status_id : StatusId, amount : int) -> bool:
    return status_id in DEBUFFS or (status_id == StatusId.STRENGTH and amount < 0)

class StatusInstance:
    status_id : StatusId
    amount : int
    behaviour : StatusBehaviour

    def __init__(self, status_id : StatusId, amount : int):
        self.status_id = status_id
        self.amount = amount
        self.behaviour = STATUS_BEAVIOURS[status_id]

    @classmethod
    def from_dict(cls, status : dict):
        return cls(StatusId[status["id"][:-6]], status["amount"])

    @classmethod
    def deepcopy(cls, status : StatusInstance):
        return cls(status.status_id, status.amount)


# ---
# Event handlers: handler(combat, owner, amount, *event_args)
# ---
def _ritual_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    owner.apply_status(StatusId.STRENGTH, amount)

def _territorial_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    owner.apply_status(StatusId.STRENGTH, amount)

def _shrink_on_creature_killed(combat : CombatSimulator, owner : Creature, amount : int, killed : Creature):
    # Shrink lasts while the beetle that applied it lives
    if killed.enemy_id.startswith("SHRINKER_BEETLE"):
        del owner.status[StatusId.SHRINK]

def _infested_on_death(combat : CombatSimulator, owner : Creature, amount : int):
    from sts2_lite.enemy import Enemy     # enemy.py imports this module
    for slot in range(INFESTED_SPAWNS):
        combat.summon(Enemy.spawn("WRIGGLER", slot, combat.combat_state.ascension))

def _slow_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    # amount is a percent, as the bridge shows it; resets when the owner's side acts
    owner.status[StatusId.SLOW].amount += 10

def _tangled_on_end_turn(combat : CombatSimulator, owner : Creature, amount : int):
    # attacks cost more for the one turn it was applied for
    del owner.status[StatusId.TANGLED]

def _constrict_on_end_turn(combat : CombatSimulator, owner : Creature, amount : int):
    owner.apply_damage(amount)

def _constrict_on_creature_killed(combat : CombatSimulator, owner : Creature, amount : int, killed : Creature):
    # lasts while the strangler that applied it lives
    if killed.enemy_id.startswith("SLITHERING_STRANGLER"):
        del owner.status[StatusId.CONSTRICT]

def _illusion_on_death(combat : CombatSimulator, owner : Creature, amount : int):
    # comes back at full hit points at the end of the enemy turn
    monster, _, slot = owner.enemy_id.rpartition("_")
    combat.combat_state.revivals.append((monster, int(slot)))

def _ringing_on_end_turn(combat : CombatSimulator, owner : Creature, amount : int):
    # lasts for the one player turn after it was applied
    del owner.status[StatusId.RINGING]

def _own(combat : CombatSimulator, owner : Creature) -> bool:
    return owner is combat.combat_state.player

def _self_forming_clay_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    if _own(combat, owner):
        del owner.status[StatusId.SELF_FORMING_CLAY]
        combat.gain_block(owner, amount)

def _plating_on_end_turn(combat : CombatSimulator, owner : Creature, amount : int):
    # the player's Plating pays out as the turn ends
    if _own(combat, owner):
        combat.gain_block(owner, amount)

def _demon_form_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    owner.apply_status(StatusId.STRENGTH, amount)

def _feel_no_pain_on_exhausted(combat : CombatSimulator, owner : Creature, amount : int, card):
    combat.gain_block(owner, amount)

def _dark_embrace_on_exhausted(combat : CombatSimulator, owner : Creature, amount : int, card):
    # ethereal exhausts draw after the hand is discarded (see _dark_embrace_on_ethereal_exhausted)
    if not combat.ethereal_exhaust:
        owner.draw_cards(amount)

def _dark_embrace_on_ethereal_exhausted(combat : CombatSimulator, owner : Creature, amount : int, count : int):
    owner.draw_cards(amount * count)

def _juggernaut_on_block_gained(combat : CombatSimulator, owner : Creature, amount : int, creature : Creature, gained : int):
    if creature is not owner:
        return
    living = [e for e in combat.combat_state.enemies if e.current_hp > 0]
    if living:
        target = living[0] if len(living) == 1 else rng.choice(living)
        target.apply_damage(amount)

def _rage_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    from sts2_lite.card import CardType     # card.py imports this module
    if card.type == CardType.Attack:
        combat.gain_block(owner, amount)

def _rage_on_end_turn(combat : CombatSimulator, owner : Creature, amount : int):
    del owner.status[StatusId.RAGE]

def _flame_barrier_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    del owner.status[StatusId.FLAME_BARRIER]

def _one_two_punch_on_end_turn(combat : CombatSimulator, owner : Creature, amount : int):
    del owner.status[StatusId.ONE_TWO_PUNCH]

def _juggling_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    from sts2_lite.card import Card, CardType
    if card.type != CardType.Attack or owner.attacks_played_this_turn != 3:
        return
    for _ in range(amount):
        copy = Card.create_copy(card)
        if len(owner.hand) < 10:
            owner.hand.append(copy)
        else:
            owner.discard_pile.append(copy)

def _aggression_on_before_player_turn(combat : CombatSimulator, owner : Creature, amount : int):
    # random attacks from the discard pile return to the hand, upgraded
    from sts2_lite.card import CardType
    attacks = [c for c in owner.discard_pile if c.type == CardType.Attack]
    if len(attacks) > amount:
        rng.shuffle(attacks)
        attacks = attacks[:amount]
    for card in attacks:
        if len(owner.hand) >= 10:
            break
        owner.discard_pile = [c for c in owner.discard_pile if c is not card]
        owner.hand.append(card.upgraded_copy() if card.is_upgradable else card)

def _stampede_on_end_turn(combat : CombatSimulator, owner : Creature, amount : int):
    from sts2_lite.card import CardType
    for _ in range(amount):
        attacks = [c for c in owner.hand if c.type == CardType.Attack and not c.is_unplayable]
        if not attacks:
            return
        combat.auto_play(attacks[0] if len(attacks) == 1 else rng.choice(attacks))

def _inferno_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    # the player loses HP at the start of every turn; each loss hurts all enemies (see CombatSimulator._inferno)
    mark = owner.hp_loss_events
    owner.lose_hp(max(1, owner.inferno_plays))
    combat._after_hp_loss(mark)

STATUS_HANDLERS : dict[tuple[StatusId, EventType], Callable] = {
    (StatusId.INFERNO, EventType.PLAYER_TURN_START) : _inferno_on_turn_start,
    (StatusId.RITUAL, EventType.ENEMY_TURN_END) : _ritual_on_enemy_turn_end,
    (StatusId.TERRITORIAL, EventType.ENEMY_TURN_END) : _territorial_on_enemy_turn_end,
    (StatusId.SHRINK, EventType.CREATURE_KILLED) : _shrink_on_creature_killed,
    (StatusId.SLOW, EventType.CARD_PLAYED) : _slow_on_card_played,
    (StatusId.INFESTED, EventType.DEATH) : _infested_on_death,
    (StatusId.ILLUSION, EventType.DEATH) : _illusion_on_death,
    (StatusId.TANGLED, EventType.END_TURN) : _tangled_on_end_turn,
    (StatusId.RINGING, EventType.END_TURN) : _ringing_on_end_turn,
    (StatusId.CONSTRICT, EventType.END_TURN) : _constrict_on_end_turn,
    (StatusId.CONSTRICT, EventType.CREATURE_KILLED) : _constrict_on_creature_killed,
    (StatusId.PLATING, EventType.END_TURN) : _plating_on_end_turn,
    (StatusId.SELF_FORMING_CLAY, EventType.PLAYER_TURN_START) : _self_forming_clay_on_turn_start,
    (StatusId.DEMON_FORM, EventType.PLAYER_TURN_START) : _demon_form_on_turn_start,
    (StatusId.FEEL_NO_PAIN, EventType.CARD_EXHAUSTED) : _feel_no_pain_on_exhausted,
    (StatusId.DARK_EMBRACE, EventType.CARD_EXHAUSTED) : _dark_embrace_on_exhausted,
    (StatusId.DARK_EMBRACE, EventType.ETHEREAL_EXHAUSTED) : _dark_embrace_on_ethereal_exhausted,
    (StatusId.JUGGERNAUT, EventType.BLOCK_GAINED) : _juggernaut_on_block_gained,
    (StatusId.RAGE, EventType.CARD_PLAYED) : _rage_on_card_played,
    (StatusId.RAGE, EventType.END_TURN) : _rage_on_end_turn,
    (StatusId.FLAME_BARRIER, EventType.ENEMY_TURN_END) : _flame_barrier_on_enemy_turn_end,
    (StatusId.ONE_TWO_PUNCH, EventType.END_TURN) : _one_two_punch_on_end_turn,
    (StatusId.JUGGLING, EventType.CARD_PLAYED) : _juggling_on_card_played,
    (StatusId.AGGRESSION, EventType.BEFORE_PLAYER_TURN) : _aggression_on_before_player_turn,
    (StatusId.STAMPEDE, EventType.PLAY_PHASE_END) : _stampede_on_end_turn,
}
