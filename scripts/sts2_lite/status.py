from __future__ import annotations
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from sts2_lite.creature import Creature
    from sts2_lite.combat import CombatSimulator

import re
from enum import Enum, auto

from sts2_lite import rng
from sts2_lite.events import EventType, HandlerTable

class StatusId(Enum):
    __hash__ = object.__hash__      # members are singletons; Enum.__hash__ is pure Python
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
    DIAMOND_DIADEM = auto()
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
    CONFUSED = auto()
    RETAIN_HAND = auto()
    NO_BLOCK = auto()
    BLOCK_NEXT_TURN = auto()
    FASTEN = auto()
    PREP_TIME = auto()
    DARK_SHACKLES = auto()
    AUTOMATION = auto()
    PANACHE = auto()
    ROLLING_BOULDER = auto()
    THE_BOMB = auto()
    TORIC_TOUGHNESS = auto()
    THE_GAMBIT = auto()
    MAYHEM = auto()
    NOSTALGIA = auto()
    CALAMITY = auto()
    ENTROPY = auto()

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
    StatusId.DIAMOND_DIADEM : StatusBehaviour.STATIC,
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
    StatusId.CONFUSED : StatusBehaviour.STATIC,     # Snecko Eye; rolls drawn cards' costs (Player.draw_card)
    StatusId.RETAIN_HAND : StatusBehaviour.STATIC,      # one less each time the player's turn ends (CombatSimulator.end_turn)
    StatusId.NO_BLOCK : StatusBehaviour.DECREASE_BY_ONE,    # ticks when the enemies' turn ends
    StatusId.BLOCK_NEXT_TURN : StatusBehaviour.STATIC,
    StatusId.FASTEN : StatusBehaviour.STATIC,
    StatusId.PREP_TIME : StatusBehaviour.STATIC,
    StatusId.DARK_SHACKLES : StatusBehaviour.STATIC,    # the Strength is returned when the owner's turn ends
    StatusId.AUTOMATION : StatusBehaviour.STATIC,
    StatusId.PANACHE : StatusBehaviour.STATIC,
    StatusId.ROLLING_BOULDER : StatusBehaviour.STATIC,
    StatusId.THE_BOMB : StatusBehaviour.STATIC,
    StatusId.TORIC_TOUGHNESS : StatusBehaviour.STATIC,     # ticks itself after the block is cleared
    StatusId.THE_GAMBIT : StatusBehaviour.STATIC,
    StatusId.MAYHEM : StatusBehaviour.STATIC,
    StatusId.NOSTALGIA : StatusBehaviour.STATIC,
    StatusId.CALAMITY : StatusBehaviour.STATIC,
    StatusId.ENTROPY : StatusBehaviour.STATIC,
}

DEBUFFS = frozenset({StatusId.WEAK, StatusId.VULNERABLE, StatusId.FRAIL, StatusId.SHRINK,
                     StatusId.CONSTRICT, StatusId.TANGLED, StatusId.RINGING,
                     StatusId.NO_DRAW, StatusId.NO_ENERGY_GAIN, StatusId.MANGLE, StatusId.CONFUSED,
                     StatusId.NO_BLOCK, StatusId.THE_GAMBIT, StatusId.DARK_SHACKLES})

def is_debuff(status_id : StatusId, amount : int) -> bool:
    return status_id in DEBUFFS or (status_id == StatusId.STRENGTH and amount < 0)

# Powers that every play adds a separate copy of (PowerInstanceType.Instanced). The bridge lists each copy; the
# state keeps one status whose `records` hold one list per copy: [shown amount, ...what else the copy remembers].
INSTANCED = {
    StatusId.AUTOMATION : (),                   # [cards left until the energy]
    StatusId.PANACHE : (10, 1),                 # [cards left, damage, 1 once the Panache card itself has been played]
    StatusId.THE_BOMB : (40,),                  # [turns left, damage]
    StatusId.ROLLING_BOULDER : (),              # [damage of the next hit]
    StatusId.TORIC_TOUGHNESS : (5,),            # [turns left, block]
}
# what an instanced copy's extra number is read from in the bridge's description (default: "N damage")
INSTANCED_TEXT = {StatusId.TORIC_TOUGHNESS : r"(\d+)\D{0,20}?Block"}
AUTOMATION_CARDS, PANACHE_CARDS = 10, 5
ROLLING_BOULDER_STEP = 5

class StatusInstance:
    status_id : StatusId
    amount : int
    behaviour : StatusBehaviour
    records : list[list[int]]

    def __init__(self, status_id : StatusId, amount : int, records : list[list[int]] | None = None):
        self.status_id = status_id
        self.amount = amount
        self.behaviour = STATUS_BEAVIOURS[status_id]
        self.records = records if records is not None else []

    @classmethod
    def from_dict(cls, status : dict):
        status_id = StatusId[status["id"][:-6]]
        amount = status["amount"]
        if status_id in INSTANCED:      # what the copy remembers beyond its shown amount is read from the text
            damage = re.search(INSTANCED_TEXT.get(status_id, r"(\d+)\s+damage"), status.get("description") or "")
            extra = (int(damage.group(1)),) if damage and INSTANCED[status_id] else INSTANCED[status_id]
            if status_id == StatusId.PANACHE:
                extra = (extra[0], 1)       # the card that applied it has been played if it is on the board
            return cls(status_id, amount, [[amount, *extra]])
        return cls(status_id, amount)

    @classmethod
    def deepcopy(cls, status : StatusInstance):
        return cls(status.status_id, status.amount, [r[:] for r in status.records] if status.records else None)

    def merge(self, other : StatusInstance):
        """A further copy of an instanced power."""
        self.records.extend(other.records)
        self.sync()

    def sync(self):
        self.amount = sum(r[0] for r in self.records)


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
        target.apply_damage(amount, owner)

def _rage_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    from sts2_lite.card import CardType     # card.py imports this module
    if card.type == CardType.Attack:
        combat.gain_block(owner, amount)

def _rage_on_end_turn(combat : CombatSimulator, owner : Creature, amount : int):
    del owner.status[StatusId.RAGE]

def _flame_barrier_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    del owner.status[StatusId.FLAME_BARRIER]

def _diamond_diadem_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    del owner.status[StatusId.DIAMOND_DIADEM]

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

def _block_next_turn_on_block_cleared(combat : CombatSimulator, owner : Creature, amount : int):
    # Prolong: the block comes back as soon as the old block is gone, unpowered
    if _own(combat, owner):
        del owner.status[StatusId.BLOCK_NEXT_TURN]
        combat.gain_block(owner, amount)

def _toric_toughness_on_block_cleared(combat : CombatSimulator, owner : Creature, amount : int):
    # ToricToughnessPower.AfterBlockCleared, per copy: unpowered block, then one turn less (fires under Barricade too)
    if not _own(combat, owner):
        return
    inst = owner.status[StatusId.TORIC_TOUGHNESS]
    kept = []
    for record in inst.records:
        combat.gain_block(owner, record[1])
        record[0] -= 1
        if record[0] > 0:
            kept.append(record)
    inst.records = kept
    if kept:
        inst.sync()
    else:
        del owner.status[StatusId.TORIC_TOUGHNESS]

def _prep_time_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    if _own(combat, owner):
        owner.apply_status(StatusId.VIGOR, amount)

def _hit_all_enemies(combat : CombatSimulator, owner : Creature, damage : int):
    """Unpowered damage from the player to every enemy still alive."""
    for enemy in [e for e in combat.combat_state.enemies if e.current_hp > 0]:
        enemy.apply_damage(damage, owner)

def _rolling_boulder_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    # every copy hits all enemies, then grows
    inst = owner.status[StatusId.ROLLING_BOULDER]
    for record in inst.records:
        _hit_all_enemies(combat, owner, record[0])
        record[0] += ROLLING_BOULDER_STEP
    inst.sync()
    combat.resolve_deaths()

def _panache_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    inst = owner.status[StatusId.PANACHE]
    for record in inst.records:
        if not record[2]:       # the card that applied this copy is not counted by it
            record[2] = 1
            continue
        record[0] -= 1
        if record[0] <= 0:
            _hit_all_enemies(combat, owner, record[1])
            record[0] = PANACHE_CARDS
    inst.sync()

def _panache_on_player_turn_ended(combat : CombatSimulator, owner : Creature, amount : int):
    inst = owner.status[StatusId.PANACHE]
    for record in inst.records:
        record[0] = PANACHE_CARDS
    inst.sync()

def _the_bomb_on_end_turn(combat : CombatSimulator, owner : Creature, amount : int):
    inst = owner.status[StatusId.THE_BOMB]
    kept = []
    for record in inst.records:
        if record[0] > 1:
            record[0] -= 1
            kept.append(record)
        else:
            _hit_all_enemies(combat, owner, record[1])
    inst.records = kept
    if kept:
        inst.sync()
    else:
        del owner.status[StatusId.THE_BOMB]

def _mayhem_on_auto_pre_play(combat : CombatSimulator, owner : Creature, amount : int):
    combat.auto_play_from_top(amount)

def _calamity_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    # every Attack played adds random Attacks to the hand
    from sts2_lite.card import Card, CardType, INFERNAL_BLADE_POOL     # card.py imports this module
    if card.type == CardType.Attack:
        for _ in range(amount):
            owner.add_to_hand(Card.create_generated(rng.choice(INFERNAL_BLADE_POOL)))

def _entropy_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    if _own(combat, owner):
        combat.request_transform(amount)

STATUS_HANDLERS : dict[tuple[StatusId, EventType], Callable] = HandlerTable({
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
    (StatusId.DIAMOND_DIADEM, EventType.ENEMY_TURN_END) : _diamond_diadem_on_enemy_turn_end,
    (StatusId.ONE_TWO_PUNCH, EventType.END_TURN) : _one_two_punch_on_end_turn,
    (StatusId.JUGGLING, EventType.CARD_PLAYED) : _juggling_on_card_played,
    (StatusId.AGGRESSION, EventType.BEFORE_PLAYER_TURN) : _aggression_on_before_player_turn,
    (StatusId.STAMPEDE, EventType.PLAY_PHASE_END) : _stampede_on_end_turn,
    (StatusId.BLOCK_NEXT_TURN, EventType.BLOCK_CLEARED) : _block_next_turn_on_block_cleared,
    (StatusId.TORIC_TOUGHNESS, EventType.BLOCK_CLEARED) : _toric_toughness_on_block_cleared,
    (StatusId.PREP_TIME, EventType.PLAYER_TURN_START) : _prep_time_on_turn_start,
    (StatusId.ROLLING_BOULDER, EventType.PLAYER_TURN_START) : _rolling_boulder_on_turn_start,
    (StatusId.PANACHE, EventType.CARD_PLAYED) : _panache_on_card_played,
    (StatusId.PANACHE, EventType.PLAYER_TURN_ENDED) : _panache_on_player_turn_ended,
    (StatusId.THE_BOMB, EventType.END_TURN) : _the_bomb_on_end_turn,
    (StatusId.MAYHEM, EventType.AUTO_PRE_PLAY) : _mayhem_on_auto_pre_play,
    (StatusId.CALAMITY, EventType.CARD_PLAYED) : _calamity_on_card_played,
    (StatusId.ENTROPY, EventType.PLAYER_TURN_START) : _entropy_on_turn_start,
})
