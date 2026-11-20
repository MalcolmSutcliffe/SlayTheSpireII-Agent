from __future__ import annotations
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from sts2_lite.creature import Creature
    from sts2_lite.combat import CombatSimulator

import re
from enum import Enum, auto

from sts2_lite import rng
from sts2_lite.hooks import HookType, HandlerTable

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
    BLUR = auto()       # block is not cleared at the owner's next turn start (Diamond Diadem); a counter that ticks after that
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
    STAR_NEXT_TURN = auto()         # Hidden Cache: Stars after the next turn's energy reset
    BLACK_HOLE = auto()             # damage to every enemy when Stars are gained and after a card paid with Stars
    CHILD_OF_THE_STARS = auto()     # Block for each Star spent
    CONQUEROR = auto()              # on an enemy: the Sovereign Blade hits it for double (ticks down)
    FURNACE = auto()                # Forge at each turn start
    MONOLOGUE = auto()              # each card played this turn gives Strength until the turn ends
    MONOLOGUE_STRENGTH = auto()     # the Strength Monologue gave this turn (marker, taken back at the end of the turn)
    ORBIT = auto()                  # 1 Energy for every 4 spent (records: [[spent, triggers]])
    PALE_BLUE_DOT = auto()          # draw extra cards next turn after 5 cards in a turn (records: [[turn it fired]])
    PARRY = auto()                  # the Sovereign Blade also gives Block
    PILLAR_OF_CREATION = auto()     # Block when a card is generated
    REFLECT = auto()                # blocked damage from Attacks is dealt back (ticks down at turn start)
    SPECTRUM_SHIFT = auto()         # colorless cards before each hand draw
    ARSENAL = auto()                # Strength for each card generated
    DYING_STAR = auto()             # on an enemy (TemporaryStrength, negative): the Strength it took comes back when its turn ends
    FOREGONE_CONCLUSION = auto()    # next turn: pick cards of the draw pile into the hand, once
    GENESIS = auto()                # Stars at each turn's start
    HIT_THIS_TURN = auto()          # on an enemy: the Attacks that hit it this turn (Beat into Shape; hidden, not a game power)
    MONARCHS_GAZE = auto()          # an enemy hit by an Attack loses Strength until the end of its turn
    MONARCHS_GAZE_STRENGTH_DOWN = auto()    # marker of that loss
    ROYALTIES = auto()              # Gold when the fight is won
    SEEKING_EDGE = auto()           # the Sovereign Blade hits every enemy
    SWORD_SAGE = auto()             # the Sovereign Blade is played this many more times
    TYRANNY = auto()                # draw more at the turn's start, then exhaust as many cards
    VOID_FORM = auto()              # the first cards played each turn are free (records: [[cards played this turn]])
    WRAITH_FORM = auto()            # Dexterity lost at each turn start
    THE_SEALED_THRONE = auto()      # Stars for each card played
    CRUSH_UNDER = auto()            # Crush Under (TemporaryStrengthPower, negative): the Strength it took comes back when the owner's turn ends
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
    # potions (names assumed: the bridge's ids for these are not captured yet)
    REGEN = auto()                  # Regen Potion: heals `amount` at the end of the player's turn, then drops by 1
    DEMISE = auto()                 # Powdered Demise: the enemy loses `amount` HP at the end of each of its turns
    BUFFER = auto()                 # Lucky Tonic: the next time HP would be lost it is not
    DUPLICATION = auto()            # Duplicator potion (the game calls the status DUPLICATION): the next card this turn is played an extra time
    GIGANTIFICATION = auto()        # Gigantification Potion: the next Attack deals triple damage
    CLARITY_EXTRACT = auto()        # Clarity Extract: 1 extra card drawn at the start of each of the next `amount` turns
    RADIANT_TINCTURE = auto()       # Radiant Tincture: 1 extra Energy at the start of each of the next `amount` turns
    REPTILE_TRINKET = auto()        # Reptile Trinket: the Strength it gave this turn, lost when the turn ends
    STRANGLE = auto()               # Mad Science (Choking): whenever the player plays a card this turn, the owner loses this much HP
    CURIOUS = auto()                # Mad Science (Curious): Powers cost 1 less
    IMPROVEMENT = auto()            # Mad Science (Improvement): upgrades a random card of the deck when the combat ends
    HELLO_WORLD = auto()            # Hello World: a random common card joins the hand at the start of each turn
    REBOUND = auto()                # Rebound: the next card played goes on top of the draw pile
    BATTLEWORN_DUMMY_TIME_LIMIT = auto()    # the dummy's: turns left to defeat it (captured: 3 on turn 1)
    FEEDING_FRENZY = auto()         # Feeding Frenzy: the Strength it gave is lost when the turn ends
    FLEX_POTION = auto()            # Flex Potion: the Strength it gave is lost when the turn ends
    SPEED_POTION = auto()           # Speed Potion: the Dexterity it gave is lost when the turn ends
    STRATAGEM = auto()              # Stratagem: whenever the draw pile is shuffled, put `amount` cards of your choice from it into the hand
    POISON = auto()                 # at the start of its owner's turn: loses that much HP (unblockable), then 1 less Poison
    HELICAL_DART = auto()           # Helical Dart (TemporaryDexterityPower): the Dexterity it gave is lost when the turn ends
    ANTICIPATE = auto()             # Anticipate (TemporaryDexterityPower): the Dexterity it gave is lost when the turn ends
    PIERCING_WAIL = auto()          # Piercing Wail (TemporaryStrengthPower, negative): the Strength it took comes back when the owner's turn ends
    ACCELERANT = auto()             # Poison on the enemies triggers this many extra times (PoisonPower.TriggerCount)
    ACCURACY = auto()               # Shivs deal this much more damage
    INFINITE_BLADES = auto()        # before the hand draw: this many Shivs into the hand
    NOXIOUS_FUMES = auto()          # at the start of the player's turn: this much Poison on every enemy
    PHANTOM_BLADES = auto()         # Shivs have Retain; the first Shiv played each turn deals this much more damage
    SPEEDSTER = auto()              # every card drawn outside the hand draw: this much damage to every enemy (Unpowered)
    FREE_SKILL = auto()             # Pounce: the next Skill played costs 0
    AFTERIMAGE = auto()             # after each card played: this much block (what it had when the play began)
    BURST = auto()                  # the next this-many Skills this turn are played twice
    CORROSIVE_WAVE = auto()         # this turn, every card drawn: this much Poison on every enemy
    ENVENOM = auto()                # attack damage that gets through block also Poisons, this much
    FAN_OF_KNIVES = auto()          # Shivs hit every enemy
    MASTER_PLANNER = auto()         # a Skill played gains Sly for good
    NIGHTMARE = auto()              # before the next hand draw: copies of the picked card (Player.nightmares) join the hand
    SERPENT_FORM = auto()           # after each card played: this much damage to a random enemy (Unpowered)
    SHADOW_STEP = auto()            # at the start of the next turn: this much Double Damage
    SHADOWMELD = auto()             # this turn, block gained is doubled (x2 per stack)
    TOOLS_OF_THE_TRADE = auto()     # draw this many more each turn, then discard as many
    TRACKING = auto()               # attacks on a Weak enemy deal (100 + this)% damage
    WELL_LAID_PLANS = auto()        # the hand is not discarded at the end of the turn
    THE_HUNT = auto()               # The Hunt killed: an extra card reward (marker)
    DOUBLE_DAMAGE = auto()          # attacks from cards deal double damage; 1 less at the end of each of the owner's turns
    # the Necrobinder
    DOOM = auto()    # dies at the end of the turn once its HP are no more than this
    BORROWED_TIME = auto()    # every card costs this much more until the turn ends
    CALCIFY = auto()    # Osty's attacks do this much more
    CALL_OF_THE_VOID = auto()    # Ethereal cards from the pool at each turn's start
    COUNTDOWN = auto()    # Doom on a random enemy each turn
    DANSE_MACABRE = auto()    # Block for cards that cost 2 or more
    DEBILITATE = auto()    # an enemy's Vulnerable and Weak count double
    DEMESNE = auto()    # more Energy and cards each turn
    DEVOUR_LIFE = auto()    # a Soul played summons
    ENFEEBLING_TOUCH = auto()    # temporary Strength loss (marker)
    FORBIDDEN_GRIMOIRE = auto()    # a card removal after each fight
    FRIENDSHIP = auto()    # more Energy each turn
    HANG = auto()    # damage multiplier of the next Hang
    HAUNT = auto()    # a Soul played hurts a random enemy
    LETHALITY = auto()    # the first Attack of the turn does more damage
    NECRO_MASTERY = auto()    # Osty's HP lost is dealt to every enemy
    NEUROSURGE = auto()    # Doom on the player each turn
    OBLIVION = auto()    # every card played adds Doom to the enemy
    PAGESTORM = auto()    # drawing an Ethereal card draws more
    REAPER_FORM = auto()    # Attack damage is also Doom
    SENTRY_MODE = auto()    # Sweeping Gazes at each turn's start
    SHROUD = auto()    # Block when Doom is applied
    SIC_EM = auto()    # Osty's hits on the enemy summon
    SLEIGHT_OF_FLESH = auto()    # a debuff applied to an enemy hurts it
    SPIRIT_OF_ASH = auto()    # Block when an Ethereal card is played
    VEILPIERCER = auto()    # the next Ethereal cards are free
    SUMMON_NEXT_TURN = auto()    # Summon at the next turn's start

INFESTED_SPAWNS = 4
CRAB_RAGE_STRENGTH, CRAB_RAGE_BLOCK = 6, 99
SLOTH_LIMIT = 3
GIANT_ABOUT_TO_BLOW_HP = 999999999     # SetMaxAndCurrentHp of the Waterfall Giant once it has been killed with Steam Eruption
HARDENED_SHELL_CAP = 20       # the bridge shows what is left of it this turn (DisplayAmount)

# The few statuses whose amount changes by itself when their owner's side ends its turn; every other status is either static or reacts
# through the event handlers below.
TICKS_DOWN = frozenset({
    StatusId.WEAK, StatusId.VULNERABLE, StatusId.FRAIL,
    StatusId.SHRINK,        # a counter that ticks when its owner's side ends; negative is infinite (ShrinkPower)
    StatusId.PLATING, StatusId.COLOSSUS,
    StatusId.NO_BLOCK,      # ticks when the enemies' turn ends
    StatusId.CONQUEROR,     # ticks when the enemies' turn ends
    StatusId.INTANGIBLE,    # damage taken is capped at 1; ticks at the end of the enemy turn
    StatusId.DEBILITATE,    # ticks when the enemies' turn ends
})
RESETS_EACH_TURN = frozenset({StatusId.SLOW})

DEBUFFS = frozenset({StatusId.DOOM, StatusId.BORROWED_TIME, StatusId.DEBILITATE, StatusId.HANG, StatusId.NEUROSURGE, StatusId.OBLIVION, StatusId.SIC_EM, StatusId.ENFEEBLING_TOUCH, StatusId.DYING_STAR, StatusId.MONARCHS_GAZE_STRENGTH_DOWN, StatusId.CONQUEROR, StatusId.POISON, StatusId.PIERCING_WAIL, StatusId.CRUSH_UNDER, StatusId.WEAK, StatusId.VULNERABLE, StatusId.FRAIL, StatusId.SHRINK,
                     StatusId.CONSTRICT, StatusId.TANGLED, StatusId.RINGING,
                     StatusId.NO_DRAW, StatusId.NO_ENERGY_GAIN, StatusId.MANGLE, StatusId.CONFUSED,
                     StatusId.NO_BLOCK, StatusId.THE_GAMBIT, StatusId.DARK_SHACKLES,
                     StatusId.TENDER, StatusId.TAINTED, StatusId.SURROUNDED, StatusId.DISINTEGRATION, StatusId.MIND_ROT,
                     StatusId.SLOTH, StatusId.WASTE_AWAY, StatusId.HEX, StatusId.DAMPEN, StatusId.CHAINS_OF_BINDING, StatusId.SMOGGY, StatusId.STRANGLE,
                     StatusId.DEMISE})

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

GAME_NAMES = {"RADIANCE" : StatusId.RADIANT_TINCTURE}       # statuses the game names differently from the sim (the id the game sends, without "_POWER")


def status_id_of(game_id : str) -> StatusId:
    """The StatusId of a status as the game sends it ("SKITTISH_POWER")."""
    name = game_id[:-6]
    return GAME_NAMES.get(name) or StatusId[name]


class StatusInstance:
    status_id : StatusId
    amount : int
    records : list[list[int]]

    def __init__(self, status_id : StatusId, amount : int, records : list[list[int]] | None = None):
        self.status_id = status_id
        self.amount = amount
        self.records = records if records is not None else []

    @classmethod
    def from_dict(cls, status : dict):
        status_id = status_id_of(status["id"])
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
    if not hasattr(owner, "enemy_id"):
        return              # the player's Ritual (Mazaleth's Gift) works when the player's turn ends
    inst = owner.status[StatusId.RITUAL]
    if inst.records:        # RitualPower.WasJustAppliedByEnemy: the turn it was applied on does not count
        inst.records = []
        return
    owner.apply_status(StatusId.STRENGTH, amount)

def _ritual_on_end_turn(combat : CombatSimulator, owner : Creature, amount : int):
    if not hasattr(owner, "enemy_id"):
        owner.apply_status(StatusId.STRENGTH, amount)

def _regen_on_end_turn(combat : CombatSimulator, owner : Creature, amount : int):
    owner.current_hp = min(owner.max_hp, owner.current_hp + amount)
    owner.status[StatusId.REGEN].amount -= 1
    if owner.status[StatusId.REGEN].amount <= 0:
        del owner.status[StatusId.REGEN]

def _demise_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    if hasattr(owner, "enemy_id") and owner.current_hp > 0:
        owner.lose_hp(amount)           # HP loss, not damage: block does not stop it

def _duplicator_on_player_turn_ended(combat : CombatSimulator, owner : Creature, amount : int):
    del owner.status[StatusId.DUPLICATION]

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

def _strangle_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    """StranglePower.AfterCardPlayed: the owner loses (Unblockable | Unpowered) the amount it had when the play began, so the card that applied
    or stacked it does not count what it added (apply_fresh notes that in records)."""
    loss = amount - fresh_amount(owner.status.get(StatusId.STRANGLE))
    if loss > 0:
        owner.lose_hp(loss)

def _strangle_on_player_turn_ended(combat : CombatSimulator, owner : Creature, amount : int):
    owner.status.pop(StatusId.STRANGLE, None)

def _rebound_on_player_turn_ended(combat : CombatSimulator, owner : Creature, amount : int):
    owner.status.pop(StatusId.REBOUND, None)         # Rebound does not last between turns

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
    # IllusionPower.ShouldPowerBeRemovedOnDeath: the buffs stay (its own Illusion too); a debuff goes, a temporary one with it
    kept = tuple((sid, st.amount) for sid, st in owner.status.items() if not is_debuff(sid, st.amount) and sid not in (StatusId.ILLUSION, StatusId.MINION))
    combat.combat_state.revivals.append((monster, int(slot), kept) if kept else (monster, int(slot)))      # nothing to keep: the plain pair

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

def _hello_world_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    """HelloWorldPower: a random common card of the character's pool joins the hand."""
    if _own(combat, owner):
        from sts2_lite.card import Card
        from sts2_lite.card.tables import CardRarity, combat_pool
        commons = combat_pool(owner.character, rarity=CardRarity.Common)
        for _ in range(amount):
            owner.add_to_hand(Card.create_generated(rng.choice(commons)))

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

def _stratagem_on_shuffle(combat : CombatSimulator, owner : Creature, amount : int):
    if _own(combat, owner):
        combat.request_stratagem(amount)

def poison_trigger(owner : Creature, accelerant : int = 0):
    """PoisonPower.Trigger: lose the Poison's amount in HP (Unblockable | Unpowered, so Intangible still caps it), then one less if the
    owner lives; TriggerCount times: 1 plus the living opponents' Accelerant, at most the Poison's amount."""
    poison = owner.status.get(StatusId.POISON)
    if poison is None or owner.current_hp <= 0:
        return
    for _ in range(min(poison.amount, 1 + accelerant)):
        owner.lose_hp(poison.amount)
        if owner.current_hp <= 0:
            return
        poison.amount -= 1
        if poison.amount <= 0:
            del owner.status[StatusId.POISON]
            return

def _poison_on_enemy_turn(combat : CombatSimulator, owner : Creature, amount : int):
    if not _own(combat, owner):
        player = combat.combat_state.player
        poison_trigger(owner, player.status_amount(StatusId.ACCELERANT) if player.current_hp > 0 else 0)

def _poison_on_player_turn(combat : CombatSimulator, owner : Creature, amount : int):
    if _own(combat, owner):
        poison_trigger(owner)

def fresh_amount(inst) -> int:
    """What the card being played added to a power that skips that card (Strangle, Afterimage, Serpent Form: they note the amount at BeforeCardPlayed);
    spent once read."""
    if inst is None or not inst.records:
        return 0
    fresh = inst.records[0][0]
    inst.records = []
    return fresh

def _afterimage_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    """AfterimagePower.AfterCardPlayed: Unpowered block (no Dexterity or Frail; Shadowmeld still doubles it)."""
    block = amount - fresh_amount(owner.status.get(StatusId.AFTERIMAGE))
    if block > 0 and _own(combat, owner):
        combat.gain_block(owner, block * 2 ** owner.status_amount(StatusId.SHADOWMELD))

def _serpent_form_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    """SerpentFormPower.AfterCardPlayed: Unpowered damage to a random enemy (Rng.CombatTargets)."""
    damage = amount - fresh_amount(owner.status.get(StatusId.SERPENT_FORM))
    living = [e for e in combat.combat_state.enemies if e.current_hp > 0]
    if damage > 0 and living and _own(combat, owner):
        from sts2_lite import rng
        rng.pick_target(living).apply_damage(damage, owner)

def _this_turn_only(status : StatusId):
    def handler(combat : CombatSimulator, owner : Creature, amount : int):
        owner.status.pop(status, None)
    return handler

def _double_damage_on_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    inst = owner.status[StatusId.DOUBLE_DAMAGE]
    inst.amount -= 1
    if inst.amount <= 0:
        del owner.status[StatusId.DOUBLE_DAMAGE]

def _shadow_step_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    """ShadowStepPower.AfterSideTurnStart: Double Damage, then gone."""
    if _own(combat, owner):
        del owner.status[StatusId.SHADOW_STEP]
        owner.apply_status(StatusId.DOUBLE_DAMAGE, amount)

def _tools_of_the_trade_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    """ToolsOfTheTradePower.AfterPlayerTurnStart: discard as many as it drew extra."""
    if _own(combat, owner):
        combat.request_discard(amount)

def _nightmare_before_hand_draw(combat : CombatSimulator, owner : Creature, amount : int):
    """NightmarePower.BeforeHandDraw: 3 clones of each picked card join the hand, then the power is gone."""
    if not _own(combat, owner):
        return
    from sts2_lite.card import Card
    picks, owner.nightmares = owner.nightmares, []
    del owner.status[StatusId.NIGHTMARE]
    for picked, copies in picks:
        for _ in range(copies):
            clone = Card.create_copy(picked)
            clone.generated = True
            owner.add_to_hand(clone)

def _infinite_blades_before_hand_draw(combat : CombatSimulator, owner : Creature, amount : int):
    """InfiniteBladesPower.BeforeHandDraw: Shivs into the hand (after the block is cleared, before the draw)."""
    if _own(combat, owner):
        combat.create_shivs(amount)

def _noxious_fumes_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    """NoxiousFumesPower.AfterSideTurnStart: Poison on every enemy."""
    if _own(combat, owner):
        from sts2_lite.relic import poison_given      # the relic package imports this module
        for enemy in combat.combat_state.enemies:
            if enemy.current_hp > 0:
                enemy.apply_status(StatusId.POISON, poison_given(owner, amount))

def _calamity_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    # every Attack played adds random Attacks to the hand
    from sts2_lite.card import Card, CardType     # card.py imports this module
    from sts2_lite.card.tables import combat_pool
    if card.type == CardType.Attack:
        attacks = combat_pool(owner.character, CardType.Attack)
        for _ in range(amount):
            owner.add_to_hand(Card.create_generated(rng.choice(attacks)))

def _entropy_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    if _own(combat, owner):
        combat.request_transform(amount)

AXEBOT_RESPAWN_MAX_HP = 10

def _stock_on_death(combat : CombatSimulator, owner : Creature, amount : int):
    # StockPower.AfterDeath: a new Axebot in the same place with one life fewer, opening with Boot Up
    from sts2_lite.enemy import Enemy     # enemy.py imports this module
    monster, _, slot = owner.enemy_id.rpartition("_")
    new = Enemy.spawn(monster, int(slot), combat.combat_state.ascension)
    if amount - 1 > 0:
        new.status[StatusId.STOCK] = StatusInstance(StatusId.STOCK, amount - 1)
    bonus = AXEBOT_RESPAWN_MAX_HP * (2 - (amount - 1))     # Axebot.RespawnMaxHpBonus: +10 Max HP for each life used
    new.max_hp += bonus
    new.current_hp += bonus
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

def nemesis_toggle(combat : CombatSimulator, owner : Creature):
    """NemesisPower.AfterSideTurnEnd: Intangible every other enemy turn (it comes after the turn's own Intangible tick)."""
    inst = owner.status[StatusId.NEMESIS]
    if not inst.records:
        inst.records.append([0])
    inst.records[0][0] ^= 1
    if inst.records[0][0]:
        owner.apply_status(StatusId.INTANGIBLE, 1)
    else:
        owner.status.pop(StatusId.INTANGIBLE, None)

def _black_hole_hit(combat : CombatSimulator, owner : Creature, amount : int):
    """BlackHolePower.DealDamageToAllEnemies: Unpowered damage."""
    for enemy in combat.combat_state.enemies:
        if enemy.current_hp > 0:
            enemy.apply_damage(amount, owner)
    combat.resolve_deaths()

def _black_hole_on_stars_gained(combat : CombatSimulator, owner : Creature, amount : int, gained : int):
    if _own(combat, owner) and gained > 0:
        _black_hole_hit(combat, owner, amount)

def _black_hole_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    if _own(combat, owner) and combat.last_stars_spent > 0:
        _black_hole_hit(combat, owner, amount)

def _child_of_the_stars_on_stars_spent(combat : CombatSimulator, owner : Creature, amount : int, spent : int):
    if _own(combat, owner) and spent > 0:
        combat.gain_block(owner, amount * spent)

def _furnace_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    if _own(combat, owner):
        combat.forge(amount)

def _monologue_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    """MonologuePower.AfterCardPlayed: Strength for every card played after it (the card that played it adds none)."""
    amount -= fresh_amount(owner.status.get(StatusId.MONOLOGUE))
    if amount > 0 and _own(combat, owner):
        from sts2_lite.card.effects import temp_strength
        temp_strength(owner, StatusId.MONOLOGUE_STRENGTH, amount, 1)

def _monologue_on_turn_ended(combat : CombatSimulator, owner : Creature, amount : int):
    owner.status.pop(StatusId.MONOLOGUE, None)

def _orbit_on_energy_spent(combat : CombatSimulator, owner : Creature, amount : int, spent : int):
    """OrbitPower.AfterEnergySpent: every 4 Energy spent pays back `amount` Energy."""
    if not _own(combat, owner) or spent <= 0:
        return
    inst = owner.status[StatusId.ORBIT]
    record = inst.records[0] if inst.records else [0, 0]
    record[0] += spent
    triggers = record[0] // ORBIT_ENERGY - record[1]
    if triggers > 0:
        record[1] += triggers
        combat.gain_energy(amount * triggers)
    inst.records = [record]

def _pale_blue_dot_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    """PaleBlueDotPower.AfterCardPlayed: once a turn, the fifth card played draws cards next turn."""
    if not _own(combat, owner) or combat.combat_state.cards_played < PALE_BLUE_DOT_CARDS:
        return
    inst = owner.status[StatusId.PALE_BLUE_DOT]
    turn = combat.combat_state.player_turn
    if inst.records and inst.records[0][0] == turn:
        return
    inst.records = [[turn]]
    owner.apply_status(StatusId.DRAW_CARDS_NEXT_TURN, amount)

def _pillar_of_creation_on_generated(combat : CombatSimulator, owner : Creature, amount : int, card):
    if _own(combat, owner):
        combat.gain_block(owner, amount)

def _reflect_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    if _own(combat, owner):
        owner.status[StatusId.REFLECT].amount -= 1
        if owner.status[StatusId.REFLECT].amount <= 0:
            del owner.status[StatusId.REFLECT]

def _spectrum_shift_before_turn(combat : CombatSimulator, owner : Creature, amount : int):
    """SpectrumShiftPower.BeforeHandDraw: that many different colorless cards join the hand."""
    if _own(combat, owner):
        from sts2_lite import rng
        from sts2_lite.card.card import Card
        from sts2_lite.event.run import COLORLESS_POOL
        for card_id in rng.sample(list(COLORLESS_POOL), amount):
            owner.add_to_hand(Card.create_generated(card_id))

def _arsenal_on_generated(combat : CombatSimulator, owner : Creature, amount : int, card):
    if _own(combat, owner):
        owner.apply_status(StatusId.STRENGTH, amount)

def _foregone_conclusion_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    """ForegoneConclusionPower.BeforeHandDraw (here after the draw): pick that many cards of the draw pile into the hand; it is then used up."""
    if _own(combat, owner):
        del owner.status[StatusId.FOREGONE_CONCLUSION]
        combat.request_stratagem(amount)

def _tyranny_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    """TyrannyPower.AfterPlayerTurnStart: exhaust that many cards of the hand."""
    if _own(combat, owner) and owner.hand:
        combat.request_choice("tyranny", list(range(len(owner.hand))), "hand", amount)

def _void_form_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    if _own(combat, owner):
        inst = owner.status[StatusId.VOID_FORM]
        inst.records = [[(inst.records[0][0] if inst.records else 0) + 1]]

def _void_form_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    if _own(combat, owner):
        owner.status[StatusId.VOID_FORM].records = [[0]]

def _sealed_throne_on_card_played(combat : CombatSimulator, owner : Creature, amount : int, card):
    """TheSealedThronePower.BeforeCardPlayed: Stars for every card played after it (the card that played it gives none)."""
    amount -= fresh_amount(owner.status.get(StatusId.THE_SEALED_THRONE))
    if amount > 0 and _own(combat, owner):
        combat.gain_stars(amount)

def _wraith_form_on_turn_start(combat : CombatSimulator, owner : Creature, amount : int):
    """WraithFormPower.AfterSideTurnStart: -Dexterity."""
    if _own(combat, owner):
        owner.apply_status(StatusId.DEXTERITY, -amount)

ORBIT_ENERGY = 4
PALE_BLUE_DOT_CARDS = 5

STATUS_HANDLERS : dict[tuple[StatusId, HookType], Callable] = HandlerTable({
    (StatusId.THE_SEALED_THRONE, HookType.CARD_PLAYED) : _sealed_throne_on_card_played,
    (StatusId.WRAITH_FORM, HookType.PLAYER_TURN_START) : _wraith_form_on_turn_start,
    (StatusId.ARSENAL, HookType.CARD_GENERATED) : _arsenal_on_generated,
    (StatusId.FOREGONE_CONCLUSION, HookType.PLAYER_TURN_START) : _foregone_conclusion_on_turn_start,
    (StatusId.TYRANNY, HookType.PLAYER_TURN_START) : _tyranny_on_turn_start,
    (StatusId.VOID_FORM, HookType.CARD_PLAYED) : _void_form_on_card_played,
    (StatusId.VOID_FORM, HookType.BEFORE_PLAYER_TURN) : _void_form_on_turn_start,
    (StatusId.BLACK_HOLE, HookType.STARS_GAINED) : _black_hole_on_stars_gained,
    (StatusId.BLACK_HOLE, HookType.CARD_PLAYED) : _black_hole_on_card_played,
    (StatusId.CHILD_OF_THE_STARS, HookType.STARS_SPENT) : _child_of_the_stars_on_stars_spent,
    (StatusId.FURNACE, HookType.PLAYER_TURN_START) : _furnace_on_turn_start,
    (StatusId.MONOLOGUE, HookType.CARD_PLAYED) : _monologue_on_card_played,
    (StatusId.MONOLOGUE, HookType.PLAYER_TURN_ENDED) : _monologue_on_turn_ended,
    (StatusId.ORBIT, HookType.ENERGY_SPENT) : _orbit_on_energy_spent,
    (StatusId.PALE_BLUE_DOT, HookType.CARD_PLAYED) : _pale_blue_dot_on_card_played,
    (StatusId.PILLAR_OF_CREATION, HookType.CARD_GENERATED) : _pillar_of_creation_on_generated,
    (StatusId.REFLECT, HookType.PLAYER_TURN_START) : _reflect_on_turn_start,
    (StatusId.SPECTRUM_SHIFT, HookType.BEFORE_PLAYER_TURN) : _spectrum_shift_before_turn,
    (StatusId.ENRAGE, HookType.CARD_PLAYED) : _enrage_on_card_played,
    (StatusId.WITHERING_PRESENCE, HookType.CARD_PLAYED) : _withering_presence_on_card_played,
    (StatusId.INFERNO, HookType.PLAYER_TURN_START) : _inferno_on_turn_start,
    (StatusId.HELLO_WORLD, HookType.PLAYER_TURN_START) : _hello_world_on_turn_start,
    (StatusId.RITUAL, HookType.ENEMY_TURN_END) : _ritual_on_enemy_turn_end,
    (StatusId.RITUAL, HookType.END_TURN) : _ritual_on_end_turn,
    (StatusId.REGEN, HookType.END_TURN) : _regen_on_end_turn,
    (StatusId.DEMISE, HookType.ENEMY_TURN_END) : _demise_on_enemy_turn_end,
    (StatusId.DUPLICATION, HookType.PLAYER_TURN_ENDED) : _duplicator_on_player_turn_ended,
    (StatusId.TERRITORIAL, HookType.ENEMY_TURN_END) : _territorial_on_enemy_turn_end,
    (StatusId.SHRINK, HookType.CREATURE_KILLED) : _shrink_on_creature_killed,
    (StatusId.SLOW, HookType.CARD_PLAYED) : _slow_on_card_played,
    (StatusId.CURL_UP, HookType.CARD_PLAYED) : _curl_up_on_card_played,
    (StatusId.SLUMBER, HookType.ENEMY_TURN_END) : _slumber_on_enemy_turn_end,
    (StatusId.CRAB_RAGE, HookType.CREATURE_KILLED) : _crab_rage_on_creature_killed,
    (StatusId.SURROUNDED, HookType.CREATURE_KILLED) : _surrounded_on_creature_killed,
    (StatusId.DISINTEGRATION, HookType.PLAYER_TURN_ENDED) : _disintegration_on_player_turn_ended,
    (StatusId.SANDPIT, HookType.ENEMY_TURN_START) : _sandpit_on_enemy_turn_start,
    (StatusId.HATCH, HookType.ENEMY_TURN_END) : _hatch_on_enemy_turn_end,
    (StatusId.ESCAPE_ARTIST, HookType.ENEMY_TURN_END) : _escape_artist_on_enemy_turn_end,
    (StatusId.VITAL_SPARK, HookType.CARD_PLAYED) : _vital_spark_on_card_played,
    (StatusId.TAINTED, HookType.ENEMY_TURN_END) : _tainted_on_enemy_turn_end,
    (StatusId.TENDER, HookType.CARD_PLAYED) : _tender_on_card_played,
    (StatusId.TENDER, HookType.PLAYER_TURN_ENDED) : _tender_on_player_turn_ended,
    (StatusId.INFESTED, HookType.DEATH) : _infested_on_death,
    (StatusId.HEX, HookType.CREATURE_KILLED) : _hex_on_creature_killed,
    (StatusId.DAMPEN, HookType.CREATURE_KILLED) : _dampen_on_creature_killed,
    (StatusId.RAMPART, HookType.BEFORE_PLAYER_TURN) : _rampart_on_before_player_turn,
    (StatusId.HIGH_VOLTAGE, HookType.ENEMY_TURN_END) : _high_voltage_on_enemy_turn_end,
    (StatusId.STOCK, HookType.DEATH) : _stock_on_death,
    (StatusId.GALVANIC, HookType.CARD_PLAYED) : _galvanic_on_card_played,
    (StatusId.POSSESS_STRENGTH, HookType.DEATH) : _possess_on_death(StatusId.STRENGTH),
    (StatusId.POSSESS_SPEED, HookType.DEATH) : _possess_on_death(StatusId.DEXTERITY),
    (StatusId.ILLUSION, HookType.DEATH) : _illusion_on_death,
    (StatusId.TANGLED, HookType.END_TURN) : _tangled_on_end_turn,
    (StatusId.RINGING, HookType.END_TURN) : _ringing_on_end_turn,
    (StatusId.CONSTRICT, HookType.END_TURN) : _constrict_on_end_turn,
    (StatusId.CONSTRICT, HookType.CREATURE_KILLED) : _constrict_on_creature_killed,
    (StatusId.PLATING, HookType.END_TURN) : _plating_on_end_turn,
    (StatusId.ASLEEP, HookType.ENEMY_TURN_END) : _asleep_on_enemy_turn_end,
    (StatusId.STEAM_ERUPTION, HookType.DEATH) : _steam_eruption_on_death,
    (StatusId.SMOGGY, HookType.CARD_PLAYED) : _smoggy_on_card_played,
    (StatusId.SMOGGY, HookType.PLAYER_TURN_ENDED) : _smoggy_on_player_turn_ended,
    (StatusId.STRANGLE, HookType.CARD_PLAYED) : _strangle_on_card_played,
    (StatusId.INFINITE_BLADES, HookType.BLOCK_CLEARED) : _infinite_blades_before_hand_draw,
    (StatusId.NIGHTMARE, HookType.BLOCK_CLEARED) : _nightmare_before_hand_draw,
    (StatusId.AFTERIMAGE, HookType.CARD_PLAYED) : _afterimage_on_card_played,
    (StatusId.SERPENT_FORM, HookType.CARD_PLAYED) : _serpent_form_on_card_played,
    (StatusId.BURST, HookType.PLAYER_TURN_ENDED) : _this_turn_only(StatusId.BURST),
    (StatusId.CORROSIVE_WAVE, HookType.PLAYER_TURN_ENDED) : _this_turn_only(StatusId.CORROSIVE_WAVE),
    (StatusId.SHADOWMELD, HookType.PLAYER_TURN_ENDED) : _this_turn_only(StatusId.SHADOWMELD),
    (StatusId.DOUBLE_DAMAGE, HookType.PLAYER_TURN_ENDED) : _double_damage_on_turn_end,
    (StatusId.SHADOW_STEP, HookType.PLAYER_TURN_START) : _shadow_step_on_turn_start,
    (StatusId.TOOLS_OF_THE_TRADE, HookType.PLAYER_TURN_START) : _tools_of_the_trade_on_turn_start,
    (StatusId.NOXIOUS_FUMES, HookType.PLAYER_TURN_START) : _noxious_fumes_on_turn_start,
    (StatusId.STRANGLE, HookType.PLAYER_TURN_ENDED) : _strangle_on_player_turn_ended,
    (StatusId.REBOUND, HookType.PLAYER_TURN_ENDED) : _rebound_on_player_turn_ended,
    (StatusId.SURPRISE, HookType.DEATH) : _surprise_on_death,
    (StatusId.RAVENOUS, HookType.CREATURE_KILLED) : _ravenous_on_creature_killed,
    (StatusId.HARDENED_SHELL, HookType.BEFORE_PLAYER_TURN) : _hardened_shell_on_side_turn_start,
    (StatusId.HARDENED_SHELL, HookType.ENEMY_TURN_START) : _hardened_shell_on_side_turn_start,
    (StatusId.SELF_FORMING_CLAY, HookType.PLAYER_TURN_START) : _self_forming_clay_on_turn_start,
    (StatusId.DEMON_FORM, HookType.PLAYER_TURN_START) : _demon_form_on_turn_start,
    (StatusId.FEEL_NO_PAIN, HookType.CARD_EXHAUSTED) : _feel_no_pain_on_exhausted,
    (StatusId.DARK_EMBRACE, HookType.CARD_EXHAUSTED) : _dark_embrace_on_exhausted,
    (StatusId.DARK_EMBRACE, HookType.ETHEREAL_EXHAUSTED) : _dark_embrace_on_ethereal_exhausted,
    (StatusId.JUGGERNAUT, HookType.BLOCK_GAINED) : _juggernaut_on_block_gained,
    (StatusId.RAGE, HookType.CARD_PLAYED) : _rage_on_card_played,
    (StatusId.RAGE, HookType.END_TURN) : _rage_on_end_turn,
    (StatusId.FLAME_BARRIER, HookType.ENEMY_TURN_END) : _flame_barrier_on_enemy_turn_end,
    (StatusId.ONE_TWO_PUNCH, HookType.END_TURN) : _one_two_punch_on_end_turn,
    (StatusId.JUGGLING, HookType.CARD_PLAYED) : _juggling_on_card_played,
    (StatusId.AGGRESSION, HookType.BEFORE_PLAYER_TURN) : _aggression_on_before_player_turn,
    (StatusId.STAMPEDE, HookType.PLAY_PHASE_END) : _stampede_on_end_turn,
    (StatusId.BLOCK_NEXT_TURN, HookType.BLOCK_CLEARED) : _block_next_turn_on_block_cleared,
    (StatusId.TORIC_TOUGHNESS, HookType.BLOCK_CLEARED) : _toric_toughness_on_block_cleared,
    (StatusId.PREP_TIME, HookType.PLAYER_TURN_START) : _prep_time_on_turn_start,
    (StatusId.ROLLING_BOULDER, HookType.PLAYER_TURN_START) : _rolling_boulder_on_turn_start,
    (StatusId.PANACHE, HookType.CARD_PLAYED) : _panache_on_card_played,
    (StatusId.PANACHE, HookType.PLAYER_TURN_ENDED) : _panache_on_player_turn_ended,
    (StatusId.THE_BOMB, HookType.END_TURN) : _the_bomb_on_end_turn,
    (StatusId.MAYHEM, HookType.AUTO_PRE_PLAY) : _mayhem_on_auto_pre_play,
    (StatusId.STRATAGEM, HookType.SHUFFLED) : _stratagem_on_shuffle,
    (StatusId.POISON, HookType.ENEMY_TURN_STARTED) : _poison_on_enemy_turn,
    (StatusId.POISON, HookType.BLOCK_CLEARED) : _poison_on_player_turn,
    (StatusId.CALAMITY, HookType.CARD_PLAYED) : _calamity_on_card_played,
    (StatusId.ENTROPY, HookType.PLAYER_TURN_START) : _entropy_on_turn_start,
})

from sts2_lite import necrobinder as _necrobinder      # the Necrobinder's powers (after the table, which they join)
STATUS_HANDLERS.update(_necrobinder.STATUS_HANDLERS)
