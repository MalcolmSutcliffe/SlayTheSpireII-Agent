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
    ENERGY_NEXT_TURN = auto()       # Relax: energy after the next turn's reset
    DRAW_CARDS_NEXT_TURN = auto()   # Relax: cards added to the next turn's hand draw
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
    IMBALANCED = auto()
    REATTACH = auto()
    PERSONAL_HIVE = auto()
    HARD_TO_KILL = auto()
    TENDER = auto()
    VITAL_SPARK = auto()
    TAINTED = auto()
    BACK_ATTACK_LEFT = auto()
    BACK_ATTACK_RIGHT = auto()
    CRAB_RAGE = auto()
    SURROUNDED = auto()
    CURL_UP = auto()
    HATCH = auto()
    SLUMBER = auto()
    SANDPIT = auto()
    ESCAPE_ARTIST = auto()
    SWIPE = auto()
    FLUTTER = auto()
    BURROWED = auto()
    DISINTEGRATION = auto()
    MIND_ROT = auto()
    SLOTH = auto()
    WASTE_AWAY = auto()
    STOCK = auto()
    GALVANIC = auto()
    PAPER_CUTS = auto()
    POSSESS_STRENGTH = auto()
    POSSESS_SPEED = auto()
    RAMPART = auto()
    SOAR = auto()
    HIGH_VOLTAGE = auto()
    HEX = auto()
    DAMPEN = auto()
    INTANGIBLE = auto()
    ENRAGE = auto()
    ADAPTABLE = auto()
    PAINFUL_STABS = auto()
    NEMESIS = auto()
    CHAINS_OF_BINDING = auto()
    WITHERING_PRESENCE = auto()
    HARDENED_SHELL = auto()
    SURPRISE = auto()
    ASLEEP = auto()
    THIEVERY = auto()
    HEIST = auto()

INFESTED_SPAWNS = 4
CRAB_RAGE_STRENGTH, CRAB_RAGE_BLOCK = 6, 99
SLOTH_LIMIT = 3
GIANT_ABOUT_TO_BLOW_HP = 999999999     # SetMaxAndCurrentHp of the Waterfall Giant once it has been killed with Steam Eruption
HARDENED_SHELL_CAP = 20       # the bridge shows what is left of it this turn (DisplayAmount)

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
    StatusId.SHRINK : StatusBehaviour.DECREASE_BY_ONE,     # a counter that ticks when its owner's side ends; negative is infinite (ShrinkPower)
    StatusId.THORNS : StatusBehaviour.STATIC,
    StatusId.RAVENOUS : StatusBehaviour.STATIC,       # when another enemy dies: stunned, and Strength (_ravenous_on_creature_killed)
    StatusId.ASLEEP : StatusBehaviour.STATIC,           # Lagavulin Matriarch: counts down at the end of the enemy turn (_asleep_on_enemy_turn_end)
    StatusId.SURPRISE : StatusBehaviour.STATIC,         # Gremlin Merc: the Sneaky and Fat Gremlins come out when it dies
    StatusId.THIEVERY : StatusBehaviour.STATIC,         # Gremlin Merc: gold taken per hit move (instanced; records[0] = [amount, gold stolen so far])
    StatusId.HEIST : StatusBehaviour.STATIC,            # Fat Gremlin: the gold it carries, given back when it is killed
    StatusId.HARDENED_SHELL : StatusBehaviour.STATIC,   # caps the hit points lost each turn (Creature._lose_hp_from_damage); records[0][0] = lost so far
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
    StatusId.ENERGY_NEXT_TURN : StatusBehaviour.STATIC,
    StatusId.DRAW_CARDS_NEXT_TURN : StatusBehaviour.STATIC,
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
    StatusId.IMBALANCED : StatusBehaviour.STATIC,     # a fully blocked attack of the owner stuns it
    StatusId.REATTACH : StatusBehaviour.STATIC,     # Decimillipede segment: revives instead of dying
    StatusId.PERSONAL_HIVE : StatusBehaviour.STATIC,     # a powered attack that hits the owner puts Dazed in the draw pile
    StatusId.HARD_TO_KILL : StatusBehaviour.STATIC,     # no single hit does more than this to the owner
    StatusId.TENDER : StatusBehaviour.STATIC,     # amount = cards played this turn; each costs 1 Strength and 1 Dexterity until the turn ends
    StatusId.VITAL_SPARK : StatusBehaviour.STATIC,     # Skills played make the enemy attacks hit harder (Tainted)
    StatusId.TAINTED : StatusBehaviour.STATIC,     # +amount damage from powered attacks until the enemies have acted
    StatusId.BACK_ATTACK_LEFT : StatusBehaviour.STATIC,     # marker: the owner attacks from the left
    StatusId.BACK_ATTACK_RIGHT : StatusBehaviour.STATIC,     # marker: the owner attacks from the right
    StatusId.CRAB_RAGE : StatusBehaviour.STATIC,     # when an ally dies: +6 Strength and 99 Block, once
    StatusId.SURROUNDED : StatusBehaviour.STATIC,     # takes 1.5x from the arm that is behind it
    StatusId.CURL_UP : StatusBehaviour.STATIC,     # block after the first powered attack card that hit the owner
    StatusId.HATCH : StatusBehaviour.STATIC,     # ticks when the enemies' turn ends
    StatusId.SLUMBER : StatusBehaviour.STATIC,     # ticks every enemy turn and when the owner takes damage; wakes at 0
    StatusId.SANDPIT : StatusBehaviour.STATIC,     # ticks when the enemies' turn starts; the player is eaten at 0
    StatusId.ESCAPE_ARTIST : StatusBehaviour.STATIC,     # ticks down to 1 when the enemies' turn ends
    StatusId.SWIPE : StatusBehaviour.STATIC,     # holds a stolen card (not modelled)
    StatusId.FLUTTER : StatusBehaviour.STATIC,     # powered attacks do half; ticks per unblocked hit; stuns at 0
    StatusId.BURROWED : StatusBehaviour.STATIC,     # the owner keeps its block; breaking it stuns the owner
    StatusId.DISINTEGRATION : StatusBehaviour.STATIC,     # the owner takes this much when the player's turn ends
    StatusId.MIND_ROT : StatusBehaviour.STATIC,     # draws this many fewer cards each turn
    StatusId.SLOTH : StatusBehaviour.STATIC,     # at most this many cards a turn
    StatusId.WASTE_AWAY : StatusBehaviour.STATIC,     # this much less maximum energy
    StatusId.STOCK : StatusBehaviour.STATIC,     # Axebot: lives left; it comes back when it dies
    StatusId.GALVANIC : StatusBehaviour.STATIC,     # Globe Head: playing a Power costs the player this many hit points
    StatusId.PAPER_CUTS : StatusBehaviour.STATIC,     # Scroll of Biting: each unblocked attack hit costs this much maximum HP
    StatusId.POSSESS_STRENGTH : StatusBehaviour.STATIC,     # The Lost: gives back the Strength it took when it dies (records[0][0])
    StatusId.RAMPART : StatusBehaviour.STATIC,     # Living Shield: Turret Operators gain this much block as each player turn starts
    StatusId.SOAR : StatusBehaviour.STATIC,     # Owl Magistrate in flight: attacks against it deal half damage
    StatusId.HEX : StatusBehaviour.STATIC,     # Spectral Knight: every card is Ethereal while it lives
    StatusId.DAMPEN : StatusBehaviour.STATIC,     # Magi Knight: upgraded cards are downgraded while it lives
    StatusId.INTANGIBLE : StatusBehaviour.DECREASE_BY_ONE,     # damage taken is capped at 1; ticks at the end of the enemy turn
    StatusId.ENRAGE : StatusBehaviour.STATIC,     # Test Subject: gains this much Strength whenever a Skill is played
    StatusId.ADAPTABLE : StatusBehaviour.STATIC,     # Test Subject: killing it only sends it to its next form (twice)
    StatusId.PAINFUL_STABS : StatusBehaviour.STATIC,     # an attack that gets through Block adds this many Wounds per hit
    StatusId.NEMESIS : StatusBehaviour.STATIC,     # Test Subject's last form: Intangible every other turn (records[0][0]: 1 when it applies it next)
    StatusId.CHAINS_OF_BINDING : StatusBehaviour.STATIC,     # Queen: this many cards a turn are Bound
    StatusId.WITHERING_PRESENCE : StatusBehaviour.STATIC,     # Aeonglass: cards left to play until a Wither
    StatusId.HIGH_VOLTAGE : StatusBehaviour.STATIC,     # Zapbot: Strength at the end of every enemy turn
    StatusId.POSSESS_SPEED : StatusBehaviour.STATIC,     # The Forgotten: gives back the Dexterity it took when it dies
    StatusId.ENTROPY : StatusBehaviour.STATIC,}

DEBUFFS = frozenset({StatusId.WEAK, StatusId.VULNERABLE, StatusId.FRAIL, StatusId.SHRINK,
                     StatusId.CONSTRICT, StatusId.TANGLED, StatusId.RINGING,
                     StatusId.NO_DRAW, StatusId.NO_ENERGY_GAIN, StatusId.MANGLE, StatusId.CONFUSED,
                     StatusId.NO_BLOCK, StatusId.THE_GAMBIT, StatusId.DARK_SHACKLES,
                     StatusId.TENDER, StatusId.TAINTED, StatusId.SURROUNDED, StatusId.DISINTEGRATION, StatusId.MIND_ROT,
                     StatusId.SLOTH, StatusId.WASTE_AWAY, StatusId.HEX, StatusId.DAMPEN, StatusId.CHAINS_OF_BINDING, StatusId.SMOGGY})

def is_debuff(status_id : StatusId, amount : int) -> bool:
    return status_id in DEBUFFS or (status_id in (StatusId.STRENGTH, StatusId.DEXTERITY) and amount < 0)

# Powers that every play adds a separate copy of (PowerInstanceType.Instanced). The bridge lists each copy; the
# state keeps one status whose `records` hold one list per copy: [shown amount, ...what else the copy remembers].
INSTANCED = {
    StatusId.AUTOMATION : (),                   # [cards left until the energy]
    StatusId.PANACHE : (10, 1),                 # [cards left, damage, 1 once the Panache card itself has been played]
    StatusId.THE_BOMB : (40,),                  # [turns left, damage]
    StatusId.ROLLING_BOULDER : (),              # [damage of the next hit]
    StatusId.TORIC_TOUGHNESS : (5,),            # [turns left, block]
    StatusId.THIEVERY : (0,),                   # [gold per steal, gold stolen so far]
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
        if status_id == StatusId.SLOTH:
            return cls(status_id, SLOTH_LIMIT)       # the shown amount is the cards played this turn; the limit is always 3
        if status_id == StatusId.HARDENED_SHELL:
            lost = max(0, HARDENED_SHELL_CAP - amount)
            return cls(status_id, HARDENED_SHELL_CAP, [[lost]] if lost else [])
        if status_id == StatusId.TENDER:
            return cls(status_id, amount, [[amount]])       # the shown amount is the cards played this turn
        return cls(status_id, amount)

    @property
    def shown_amount(self) -> int:
        """The amount the game displays: Hardened Shell shows what is left of this turn's allowance."""
        if self.status_id == StatusId.HARDENED_SHELL:
            return max(0, self.amount - (self.records[0][0] if self.records else 0))
        if self.status_id == StatusId.TENDER:       # TenderPower.DisplayAmount: the cards played this turn (0 until one is), not the stack
            return self.records[0][0] if self.records else 0
        return self.amount

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
    inst = owner.status[StatusId.RITUAL]
    if inst.records:        # RitualPower.WasJustAppliedByEnemy: the turn it was applied on does not count
        inst.records = []
        return
    owner.apply_status(StatusId.STRENGTH, amount)

def _rampart_on_before_player_turn(combat : CombatSimulator, owner : Creature, amount : int):
    # RampartPower.AfterSideTurnStart: the Turret Operators behind the shield gain unpowered block
    for enemy in combat.combat_state.enemies:
        if enemy.enemy_id.startswith("TURRET_OPERATOR") and enemy.current_hp > 0:
            enemy.apply_block(amount)

def _high_voltage_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    owner.apply_status(StatusId.STRENGTH, amount)

def _territorial_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    owner.apply_status(StatusId.STRENGTH, amount)

def _shrink_on_creature_killed(combat : CombatSimulator, owner : Creature, amount : int, killed : Creature):
    # Shrink lasts while the beetle that applied it lives
    if killed.enemy_id.startswith("SHRINKER_BEETLE"):
        del owner.status[StatusId.SHRINK]

def _ravenous_on_creature_killed(combat : CombatSimulator, owner : Creature, amount : int, killed : Creature):
    # RavenousPower.AfterDeath: another enemy died, so the Corpse Slug devours it: stunned, and Strength
    if killed is owner or not hasattr(killed, "enemy_id") or owner.current_hp <= 0:
        return
    owner.stun()
    owner.apply_status(StatusId.STRENGTH, amount)

def _asleep_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    # AsleepPower: the Plating goes a turn before the sleep ends (BeforeSideTurnEndVeryEarly), then one less turn of sleep
    inst = owner.status[StatusId.ASLEEP]
    if inst.amount <= 1:
        owner.status.pop(StatusId.PLATING, None)
    inst.amount -= 1
    if inst.amount <= 0:
        del owner.status[StatusId.ASLEEP]

def _steam_eruption_on_death(combat : CombatSimulator, owner : Creature, amount : int):
    # SteamEruptionPower.AfterDeath: the Waterfall Giant is not removed; it swells to be about to blow with all the steam it built
    cs = combat.combat_state
    owner.max_hp = owner.current_hp = GIANT_ABOUT_TO_BLOW_HP
    owner.block = 0
    owner.move_id, owner.move_streak, owner.attack_damage, owner.num_attacks = "ABOUT_TO_BLOW", 1, 0, 0
    cs.enemies.insert(min(getattr(owner, "last_index", 0), len(cs.enemies)), owner)

def _smoggy_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    # SmoggyPower.AfterCardPlayed: after a Skill every Skill card, in any pile, is afflicted with Smog until the turn ends
    from sts2_lite.card import CardType     # card.py imports this module
    if card.type == CardType.Skill:
        owner.smogged = True

def _smoggy_on_player_turn_ended(combat : CombatSimulator, owner : Creature, amount : int):
    owner.smogged = False           # SmoggyPower.AfterSideTurnEnd

def _surprise_on_death(combat : CombatSimulator, owner : Creature, amount : int):
    # SurprisePower.AfterDeath: the merc's gremlins step out, and the Fat one carries off the gold the merc took
    from sts2_lite.enemy import Enemy
    cs = combat.combat_state
    thievery = owner.status.get(StatusId.THIEVERY)
    stolen = sum(r[1] for r in thievery.records) if thievery is not None else 0
    place = min(getattr(owner, "last_index", 0), len(cs.enemies))
    sneaky = Enemy.spawn("SNEAKY_GREMLIN", 0, cs.ascension)
    fat = Enemy.spawn("FAT_GREMLIN", 0, cs.ascension)
    if stolen > 0:
        fat.apply_status(StatusId.HEIST, stolen)
    combat.summon(sneaky, at=place)
    combat.summon(fat, at=place + 1)

def _hardened_shell_on_side_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    owner.status[StatusId.HARDENED_SHELL].records = []     # BeforeSideTurnStart (either side): the count of hit points lost starts again

def _crab_rage_on_creature_killed(combat : CombatSimulator, owner : Creature, amount : int, killed : Creature):
    # an ally of the crab died: +6 Strength and 99 Block, once
    if killed is owner or not hasattr(killed, "enemy_id") or owner.current_hp <= 0:
        return
    del owner.status[StatusId.CRAB_RAGE]
    owner.apply_status(StatusId.STRENGTH, CRAB_RAGE_STRENGTH)
    owner.apply_block(CRAB_RAGE_BLOCK)

def face_target(player : Creature, target : Creature):
    """SurroundedPower.UpdateDirection: turning to hit an arm that is behind you flips the facing."""
    inst = player.status.get(StatusId.SURROUNDED)
    if inst is None:
        return
    if not inst.records:
        inst.records = [[0]]
    facing = inst.records[0][0]
    if (StatusId.BACK_ATTACK_LEFT if facing == 0 else StatusId.BACK_ATTACK_RIGHT) in target.status:
        inst.records[0][0] = 1 - facing

def _surrounded_on_creature_killed(combat : CombatSimulator, owner : Creature, amount : int, killed : Creature):
    # when only arms of one side are left, the player turns to the first of them
    if not hasattr(killed, "enemy_id"):
        return
    enemies = [e for e in combat.combat_state.enemies if e.current_hp > 0]
    if enemies and (all(StatusId.BACK_ATTACK_LEFT in e.status for e in enemies)
                    or all(StatusId.BACK_ATTACK_RIGHT in e.status for e in enemies)):
        face_target(owner, enemies[0])

def _disintegration_on_player_turn_ended(combat : CombatSimulator, owner : Creature, amount : int):
    owner.apply_damage(amount)      # unpowered: only Block lessens it

def _infested_on_death(combat : CombatSimulator, owner : Creature, amount : int):
    from sts2_lite.enemy import Enemy     # enemy.py imports this module
    for slot in range(INFESTED_SPAWNS):
        combat.summon(Enemy.spawn("WRIGGLER", slot, combat.combat_state.ascension))

def _slow_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    # amount is a percent, as the bridge shows it; resets when the owner's side acts
    owner.status[StatusId.SLOW].amount += 10

def _curl_up_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    # a powered attack of this card hit the owner (see Creature._after_damage): block once the card is done
    if owner.status[StatusId.CURL_UP].records:
        owner.apply_block(amount)
        del owner.status[StatusId.CURL_UP]

def _vital_spark_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    # every Skill is afflicted with Tainted while the owner lives: playing one taints the player until the enemies have acted
    from sts2_lite.card import CardType     # card.py imports this module
    if card.type == CardType.Skill:
        combat.combat_state.player.apply_status(StatusId.TAINTED, amount)

def _tainted_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    del owner.status[StatusId.TAINTED]

def _tender_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    # each card costs 1 Strength and 1 Dexterity until the turn ends; records[0][0] counts the cards (whatever Artifact did)
    inst = owner.status[StatusId.TENDER]
    if not inst.records:
        inst.records.append([0])
    inst.records[0][0] += 1
    owner.apply_status(StatusId.STRENGTH, -1)
    owner.apply_status(StatusId.DEXTERITY, -1)

def _tender_on_player_turn_ended(combat : CombatSimulator, owner : Creature, amount : int):
    inst = owner.status[StatusId.TENDER]
    if inst.records and inst.records[0][0]:
        owner.apply_status(StatusId.STRENGTH, inst.records[0][0], bypass_artifact=True)
        owner.apply_status(StatusId.DEXTERITY, inst.records[0][0], bypass_artifact=True)
        inst.records[0][0] = 0

def _slumber_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    # one less each enemy turn; the owner wakes up (and loses its Plating) when it runs out
    owner.status[StatusId.SLUMBER].amount -= 1
    if owner.status[StatusId.SLUMBER].amount <= 0:
        del owner.status[StatusId.SLUMBER]
        plating = owner.status.pop(StatusId.PLATING, None)
        if plating is not None:
            # Plating's block comes (BeforeSideTurnEndEarly, from the amount it has just lost one of) before the Slumber ends and removes it
            owner.apply_block(plating.amount - (0 if combat.combat_state.turn_number == 1 else 1))

def _hatch_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    owner.status[StatusId.HATCH].amount -= 1
    if owner.status[StatusId.HATCH].amount <= 0:
        del owner.status[StatusId.HATCH]

def _escape_artist_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    if amount > 1:
        owner.status[StatusId.ESCAPE_ARTIST].amount -= 1

def _sandpit_on_enemy_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    # the player is eaten when it reaches zero, before the enemies act
    owner.status[StatusId.SANDPIT].amount -= 1
    if owner.status[StatusId.SANDPIT].amount <= 0:
        del owner.status[StatusId.SANDPIT]
        combat.combat_state.player.current_hp = 0

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
        target = rng.pick_target(living)
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
        attacks = [c for c in owner.hand if c.type == CardType.Attack and not c.unplayable]
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

def _stock_on_death(combat : CombatSimulator, owner : Creature, amount : int):
    # StockPower.AfterDeath: a new Axebot in the same place with one life fewer, opening with Boot Up
    from sts2_lite.enemy import Enemy     # enemy.py imports this module
    monster, _, slot = owner.enemy_id.rpartition("_")
    new = Enemy.spawn(monster, int(slot), combat.combat_state.ascension)
    if amount - 1 > 0:
        new.status[StatusId.STOCK] = StatusInstance(StatusId.STOCK, amount - 1)
    combat.summon(new, at=getattr(owner, "last_index", None))

def _galvanic_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    # every Power card is afflicted with Galvanized while the owner lives: playing one hurts the player (unpowered)
    from sts2_lite.card import CardType     # card.py imports this module
    if card.type == CardType.Power:
        combat.combat_state.player.apply_damage(amount)

def _possess_on_death(stat : StatusId):
    def handler(combat : CombatSimulator, owner : Creature, amount : int):
        # what the owner took from the player returns to the player
        inst = owner.status[StatusId.POSSESS_STRENGTH if stat == StatusId.STRENGTH else StatusId.POSSESS_SPEED]
        if inst.records and inst.records[0][0] > 0:
            combat.combat_state.player.apply_status(stat, inst.records[0][0], bypass_artifact=True)
    return handler

def _hex_on_creature_killed(combat : CombatSimulator, owner : Creature, amount : int, killed : Creature):
    # HexPower.AfterDeath: it goes with the Spectral Knight that applied it
    if killed.enemy_id.startswith("SPECTRAL_KNIGHT"):
        del owner.status[StatusId.HEX]

def downgrade_cards(player):
    """DampenPower.AfterApplied: every upgraded card in the deck becomes its plain version; the upgraded one is kept to come back."""
    for pile in (player.hand, player.draw_pile, player.discard_pile, player.exhaust_pile):
        for i, card in enumerate(pile):
            if card.is_upgraded:
                plain = card.downgraded_copy()
                plain.dampened_from = card
                pile[i] = plain

def _dampen_on_creature_killed(combat : CombatSimulator, owner : Creature, amount : int, killed : Creature):
    # the last Magi Knight that cast it is gone: the cards get their upgrades back
    if not killed.enemy_id.startswith("MAGI_KNIGHT"):
        return
    del owner.status[StatusId.DAMPEN]
    for pile in (owner.hand, owner.draw_pile, owner.discard_pile, owner.exhaust_pile):
        for i, card in enumerate(pile):
            if card.dampened_from is not None:
                pile[i] = card.dampened_from

WITHERING_PRESENCE_CARDS = 6

def _enrage_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    from sts2_lite.card import CardType
    if card.type == CardType.Skill:
        owner.apply_status(StatusId.STRENGTH, amount)

def _withering_presence_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    # the status sits on Aeonglass and counts the player's cards; the last of the six adds a Wither to their hand
    from sts2_lite.card import Card
    inst = owner.status[StatusId.WITHERING_PRESENCE]
    inst.amount -= 1
    if inst.amount <= 0:
        inst.amount = WITHERING_PRESENCE_CARDS
        combat.combat_state.player.add_to_hand(Card.create_wither(combat.wither_level()))

def _nemesis_toggle(combat : CombatSimulator, owner : Creature):
    """NemesisPower.AfterSideTurnEnd: Intangible every other enemy turn (it comes after the turn's own Intangible tick)."""
    inst = owner.status[StatusId.NEMESIS]
    if not inst.records:
        inst.records.append([0])
    inst.records[0][0] ^= 1
    if inst.records[0][0]:
        owner.apply_status(StatusId.INTANGIBLE, 1)
    else:
        owner.status.pop(StatusId.INTANGIBLE, None)

STATUS_HANDLERS : dict[tuple[StatusId, EventType], Callable] = HandlerTable({
    (StatusId.ENRAGE, EventType.CARD_PLAYED) : _enrage_on_card_played,
    (StatusId.WITHERING_PRESENCE, EventType.CARD_PLAYED) : _withering_presence_on_card_played,
    (StatusId.INFERNO, EventType.PLAYER_TURN_START) : _inferno_on_turn_start,
    (StatusId.RITUAL, EventType.ENEMY_TURN_END) : _ritual_on_enemy_turn_end,
    (StatusId.TERRITORIAL, EventType.ENEMY_TURN_END) : _territorial_on_enemy_turn_end,
    (StatusId.SHRINK, EventType.CREATURE_KILLED) : _shrink_on_creature_killed,
    (StatusId.SLOW, EventType.CARD_PLAYED) : _slow_on_card_played,
    (StatusId.CURL_UP, EventType.CARD_PLAYED) : _curl_up_on_card_played,
    (StatusId.SLUMBER, EventType.ENEMY_TURN_END) : _slumber_on_enemy_turn_end,
    (StatusId.CRAB_RAGE, EventType.CREATURE_KILLED) : _crab_rage_on_creature_killed,
    (StatusId.SURROUNDED, EventType.CREATURE_KILLED) : _surrounded_on_creature_killed,
    (StatusId.DISINTEGRATION, EventType.PLAYER_TURN_ENDED) : _disintegration_on_player_turn_ended,
    (StatusId.SANDPIT, EventType.ENEMY_TURN_START) : _sandpit_on_enemy_turn_start,
    (StatusId.HATCH, EventType.ENEMY_TURN_END) : _hatch_on_enemy_turn_end,
    (StatusId.ESCAPE_ARTIST, EventType.ENEMY_TURN_END) : _escape_artist_on_enemy_turn_end,
    (StatusId.VITAL_SPARK, EventType.CARD_PLAYED) : _vital_spark_on_card_played,
    (StatusId.TAINTED, EventType.ENEMY_TURN_END) : _tainted_on_enemy_turn_end,
    (StatusId.TENDER, EventType.CARD_PLAYED) : _tender_on_card_played,
    (StatusId.TENDER, EventType.PLAYER_TURN_ENDED) : _tender_on_player_turn_ended,
    (StatusId.INFESTED, EventType.DEATH) : _infested_on_death,
    (StatusId.HEX, EventType.CREATURE_KILLED) : _hex_on_creature_killed,
    (StatusId.DAMPEN, EventType.CREATURE_KILLED) : _dampen_on_creature_killed,
    (StatusId.RAMPART, EventType.BEFORE_PLAYER_TURN) : _rampart_on_before_player_turn,
    (StatusId.HIGH_VOLTAGE, EventType.ENEMY_TURN_END) : _high_voltage_on_enemy_turn_end,
    (StatusId.STOCK, EventType.DEATH) : _stock_on_death,
    (StatusId.GALVANIC, EventType.CARD_PLAYED) : _galvanic_on_card_played,
    (StatusId.POSSESS_STRENGTH, EventType.DEATH) : _possess_on_death(StatusId.STRENGTH),
    (StatusId.POSSESS_SPEED, EventType.DEATH) : _possess_on_death(StatusId.DEXTERITY),
    (StatusId.ILLUSION, EventType.DEATH) : _illusion_on_death,
    (StatusId.TANGLED, EventType.END_TURN) : _tangled_on_end_turn,
    (StatusId.RINGING, EventType.END_TURN) : _ringing_on_end_turn,
    (StatusId.CONSTRICT, EventType.END_TURN) : _constrict_on_end_turn,
    (StatusId.CONSTRICT, EventType.CREATURE_KILLED) : _constrict_on_creature_killed,
    (StatusId.PLATING, EventType.END_TURN) : _plating_on_end_turn,
    (StatusId.ASLEEP, EventType.ENEMY_TURN_END) : _asleep_on_enemy_turn_end,
    (StatusId.STEAM_ERUPTION, EventType.DEATH) : _steam_eruption_on_death,
    (StatusId.SMOGGY, EventType.CARD_PLAYED) : _smoggy_on_card_played,
    (StatusId.SMOGGY, EventType.PLAYER_TURN_ENDED) : _smoggy_on_player_turn_ended,
    (StatusId.SURPRISE, EventType.DEATH) : _surprise_on_death,
    (StatusId.RAVENOUS, EventType.CREATURE_KILLED) : _ravenous_on_creature_killed,
    (StatusId.HARDENED_SHELL, EventType.BEFORE_PLAYER_TURN) : _hardened_shell_on_side_turn_start,
    (StatusId.HARDENED_SHELL, EventType.ENEMY_TURN_START) : _hardened_shell_on_side_turn_start,
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
