"""Enemy move tables. A move table maps move id -> Move; each move names its follow-up."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sts2_lite import rng
from sts2_lite.card import Card, CARD_RARITY, CardId, CardRarity, EnchantmentId
from sts2_lite.status import StatusId

TOUGH_ASCENSION = 8      # more hit points and block
DEADLY_ASCENSION = 9     # more damage and strength


@dataclass(frozen=True)
class Branch:
    """A random follow-up option; max_streak caps how many times in a row this move may be used."""
    move: str
    max_streak: int = 1
    once: bool = False       # may be used only once per fight
    weight: int = 1          # relative chance among the allowed options


@dataclass(frozen=True)
class Move:
    intents: frozenset[str]                    # lowercase bridge intent types
    next_move: str
    damage: int = 0
    hits: int = 0
    block: int = 0
    self_status: tuple[tuple[StatusId, int], ...] = ()
    player_status: tuple[tuple[StatusId, int], ...] = ()
    round_mod: tuple[int, int] | None = None   # (period, remainder): tells apart moves with the same intent
    cards: tuple[tuple[CardId, int], ...] = ()  # cards added to the player's discard pile
    next_by_slot: tuple[str, ...] = ()         # next move chosen by the enemy's slot, used instead of next_move
    branches: tuple[Branch, ...] = ()          # random follow-up; used instead of next_move when set
    summon: tuple[str, int] | None = None      # (monster, slot) added to the fight when the move is performed
    from_bridge: bool = True                   # False: looks like another move, so never picked when reading the bridge
    hand_cards: tuple[tuple[CardId, int], ...] = ()     # cards added to the player's hand (the discard pile when the hand is full)
    draw_cards: tuple[tuple[CardId, int], ...] = ()     # cards shuffled into the player's draw pile
    summons: tuple[tuple[str, int], ...] = ()  # (monster, slot) pairs added when the move is performed, like `summon`
    team_status: tuple[tuple[StatusId, int], ...] = ()  # applied to every living enemy, the mover included
    heal: int = 0                              # hit points the mover recovers
    choose: Callable | None = None             # (enemy, combat) -> next move key; used instead of next_move and branches
    effect: Callable | None = None             # (enemy, combat) run when the move is performed, for anything above
    extra_hits: Callable | None = None         # (enemy) -> hits added to `hits` (the Test Subject's claws grow)
    extra_damage: Callable | None = None       # (enemy) -> damage added to `damage` (the Waterfall Giant's Pressure Gun grows)
    dex_damage: bool = False                   # the move's damage grows by the mover's Dexterity (The Forgotten's Dread)


MoveTable = dict[str, Move]


def _deadly(ascension : int, base : int, deadly : int) -> int:
    return deadly if ascension >= DEADLY_ASCENSION else base


def _tough(ascension : int, base : int, tough : int) -> int:
    return tough if ascension >= TOUGH_ASCENSION else base


def nibbit(ascension : int) -> MoveTable:
    return {
        "BUTT": Move(frozenset({"attack"}), "SLICE",
                     damage=_deadly(ascension, 12, 13), hits=1),
        "SLICE": Move(frozenset({"attack", "defend"}), "HISS",
                      damage=_deadly(ascension, 6, 7), hits=1, block=_tough(ascension, 5, 6)),
        "HISS": Move(frozenset({"buff"}), "BUTT",
                     self_status=((StatusId.STRENGTH, _deadly(ascension, 2, 3)),)),
    }


def shrinker_beetle(ascension : int) -> MoveTable:
    return {
        "SHRINK": Move(frozenset({"debuffstrong"}), "CHOMP",
                       player_status=((StatusId.SHRINK, -1),)),
        "CHOMP": Move(frozenset({"attack"}), "STOMP",
                      damage=_deadly(ascension, 7, 8), hits=1),
        "STOMP": Move(frozenset({"attack"}), "CHOMP",
                      damage=_deadly(ascension, 13, 14), hits=1),
    }


def fuzzy_wurm_crawler(ascension : int) -> MoveTable:
    # goop, inhale, goop, goop, inhale, ...; both goops look the same, so rounds tell them apart
    return {
        "FIRST_GOOP": Move(frozenset({"attack"}), "INHALE",
                           damage=_deadly(ascension, 4, 6), hits=1, round_mod=(3, 1)),
        "INHALE": Move(frozenset({"buff"}), "GOOP",
                       self_status=((StatusId.STRENGTH, 7),)),
        "GOOP": Move(frozenset({"attack"}), "FIRST_GOOP",
                     damage=_deadly(ascension, 4, 6), hits=1, round_mod=(3, 0)),
    }


def leaf_slime_s(ascension : int) -> MoveTable:
    return {
        "BUTT": Move(frozenset({"attack"}), "GOOP",
                     damage=_deadly(ascension, 3, 4), hits=1),
        "GOOP": Move(frozenset({"statuscard"}), "BUTT", cards=((CardId.SLIMED, 1),)),
    }


def twig_slime_s(ascension : int) -> MoveTable:
    return {
        "BUTT": Move(frozenset({"attack"}), "BUTT",
                     damage=_deadly(ascension, 4, 5), hits=1),
    }


def leaf_slime_m(ascension : int) -> MoveTable:
    return {
        "STICKY_SHOT": Move(frozenset({"statuscard"}), "CLUMP_SHOT", cards=((CardId.SLIMED, 2),)),
        "CLUMP_SHOT": Move(frozenset({"attack"}), "STICKY_SHOT",
                           damage=_deadly(ascension, 8, 9), hits=1),
    }


def twig_slime_m(ascension : int) -> MoveTable:
    follow = (Branch("CLUMP_SHOT", max_streak=2), Branch("STICKY_SHOT"))
    return {
        "STICKY_SHOT": Move(frozenset({"statuscard"}), "", cards=((CardId.SLIMED, 1),), branches=follow),
        "CLUMP_SHOT": Move(frozenset({"attack"}), "",
                           damage=_deadly(ascension, 11, 12), hits=1, branches=follow),
    }


def byrdonis(ascension : int) -> MoveTable:
    return {
        "SWOOP": Move(frozenset({"attack"}), "PECK",
                      damage=_deadly(ascension, 17, 19), hits=1),
        "PECK": Move(frozenset({"attack"}), "SWOOP",
                     damage=_deadly(ascension, 3, 4), hits=3),
    }


def bygone_effigy(ascension : int) -> MoveTable:
    return {
        "SLEEP": Move(frozenset({"sleep"}), "WAKE"),
        "WAKE": Move(frozenset({"buff"}), "SLASH",
                     self_status=((StatusId.STRENGTH, 10),)),
        "SLASH": Move(frozenset({"attack"}), "SLASH",
                      damage=_deadly(ascension, 13, 15), hits=1),
    }


def phrog_parasite(ascension : int) -> MoveTable:
    return {
        "INFECT": Move(frozenset({"statuscard"}), "LASH", cards=((CardId.INFECTION, 3),)),
        "LASH": Move(frozenset({"attack"}), "INFECT",
                     damage=_deadly(ascension, 4, 5), hits=4),
    }


def wriggler(ascension : int) -> MoveTable:
    # slots 0 and 2 open with a bite, slots 1 and 3 with a wriggle
    return {
        "SPAWNED": Move(frozenset({"stun"}), "", next_by_slot=("BITE", "WRIGGLE", "BITE", "WRIGGLE")),
        "BITE": Move(frozenset({"attack"}), "WRIGGLE",
                     damage=_deadly(ascension, 6, 7), hits=1),
        "WRIGGLE": Move(frozenset({"buff", "statuscard"}), "BITE",
                        cards=((CardId.INFECTION, 1),), self_status=((StatusId.STRENGTH, 2),)),
    }


def mawler(ascension : int) -> MoveTable:
    follow = (Branch("RIP_AND_TEAR"), Branch("ROAR", once=True), Branch("CLAW"))
    return {
        "RIP_AND_TEAR": Move(frozenset({"attack"}), "",
                             damage=_deadly(ascension, 14, 16), hits=1, branches=follow),
        "ROAR": Move(frozenset({"debuff"}), "",
                     player_status=((StatusId.VULNERABLE, 3),), branches=follow),
        "CLAW": Move(frozenset({"attack"}), "",
                     damage=_deadly(ascension, 4, 5), hits=2, branches=follow),
    }


def vine_shambler(ascension : int) -> MoveTable:
    return {
        "SWIPE": Move(frozenset({"attack"}), "GRASPING_VINES",
                      damage=_deadly(ascension, 6, 7), hits=2),
        "GRASPING_VINES": Move(frozenset({"attack", "carddebuff"}), "CHOMP",
                               damage=_deadly(ascension, 8, 9), hits=1,
                               player_status=((StatusId.TANGLED, 1),)),
        "CHOMP": Move(frozenset({"attack"}), "SWIPE",
                      damage=_deadly(ascension, 16, 18), hits=1),
    }


def snapping_jaxfruit(ascension : int) -> MoveTable:
    return {
        "ENERGY_ORB": Move(frozenset({"attack", "buff"}), "ENERGY_ORB",
                           damage=_deadly(ascension, 3, 4), hits=1,
                           self_status=((StatusId.STRENGTH, 2),)),
    }


def flyconid(ascension : int) -> MoveTable:
    follow = (Branch("VULNERABLE_SPORES", weight=3), Branch("FRAIL_SPORES", weight=2), Branch("SMASH"))
    return {
        "VULNERABLE_SPORES": Move(frozenset({"debuff"}), "",
                                  player_status=((StatusId.VULNERABLE, 2),), branches=follow),
        "FRAIL_SPORES": Move(frozenset({"attack", "debuff"}), "",
                             damage=_deadly(ascension, 8, 9), hits=1,
                             player_status=((StatusId.FRAIL, 2),), branches=follow),
        "SMASH": Move(frozenset({"attack"}), "",
                      damage=_deadly(ascension, 11, 12), hits=1, branches=follow),
    }


def slithering_strangler(ascension : int) -> MoveTable:
    after_constrict = (Branch("THWACK"), Branch("LASH"))
    return {
        "CONSTRICT": Move(frozenset({"debuff"}), "",
                          player_status=((StatusId.CONSTRICT, 3),), branches=after_constrict),
        "THWACK": Move(frozenset({"attack", "defend"}), "CONSTRICT",
                       damage=_deadly(ascension, 7, 8), hits=1, block=5),
        "LASH": Move(frozenset({"attack"}), "CONSTRICT",
                     damage=_deadly(ascension, 12, 13), hits=1),
    }


def inklet(ascension : int) -> MoveTable:
    # the middle inklet opens with a whirlwind; the bridge shows each one's current move
    return {
        "JAB": Move(frozenset({"attack"}), "",
                    damage=_deadly(ascension, 3, 4), hits=1,
                    branches=(Branch("PIERCING_GAZE"), Branch("WHIRLWIND"))),
        "WHIRLWIND": Move(frozenset({"attack"}), "JAB",
                          damage=_deadly(ascension, 2, 3), hits=3),
        "PIERCING_GAZE": Move(frozenset({"attack"}), "JAB",
                              damage=_deadly(ascension, 10, 11), hits=1),
    }


def cubex_construct(ascension : int) -> MoveTable:
    # charge, blast, blast, expel, then blast, blast, expel...; the two blasts look alike,
    # so the round number tells them apart (the cycle starts on round 1)
    strength = ((StatusId.STRENGTH, 2),)
    return {
        "CHARGE_UP": Move(frozenset({"buff"}), "REPEATER_BLAST", self_status=strength),
        "REPEATER_BLAST": Move(frozenset({"attack", "buff"}), "REPEATER_BLAST_2",
                               damage=_deadly(ascension, 7, 8), hits=1,
                               self_status=strength, round_mod=(3, 2)),
        "REPEATER_BLAST_2": Move(frozenset({"attack", "buff"}), "EXPEL",
                                 damage=_deadly(ascension, 7, 8), hits=1,
                                 self_status=strength, round_mod=(3, 0)),
        "EXPEL": Move(frozenset({"attack"}), "REPEATER_BLAST",
                      damage=_deadly(ascension, 5, 6), hits=2),
    }


def assassin_ruby_raider(ascension : int) -> MoveTable:
    return {
        "KILLSHOT": Move(frozenset({"attack"}), "KILLSHOT",
                         damage=_deadly(ascension, 10, 11), hits=1),
    }


def axe_ruby_raider(ascension : int) -> MoveTable:
    # the two swings look alike, so the round number tells them apart (the cycle starts on round 1)
    swing = dict(intents=frozenset({"attack", "defend"}), damage=_deadly(ascension, 5, 6), hits=1,
                 block=_deadly(ascension, 5, 6))
    return {
        "SWING_1": Move(next_move="SWING_2", round_mod=(3, 1), **swing),
        "SWING_2": Move(next_move="BIG_SWING", round_mod=(3, 2), **swing),
        "BIG_SWING": Move(frozenset({"attack"}), "SWING_1",
                          damage=_deadly(ascension, 12, 13), hits=1),
    }


def brute_ruby_raider(ascension : int) -> MoveTable:
    return {
        "BEAT": Move(frozenset({"attack"}), "ROAR",
                     damage=_deadly(ascension, 7, 8), hits=1),
        "ROAR": Move(frozenset({"buff"}), "BEAT", self_status=((StatusId.STRENGTH, 3),)),
    }


def crossbow_ruby_raider(ascension : int) -> MoveTable:
    return {
        "RELOAD": Move(frozenset({"defend"}), "FIRE", block=3),
        "FIRE": Move(frozenset({"attack"}), "RELOAD",
                     damage=_deadly(ascension, 14, 16), hits=1),
    }


def tracker_ruby_raider(ascension : int) -> MoveTable:
    return {
        "TRACK": Move(frozenset({"debuff"}), "HOUNDS", player_status=((StatusId.FRAIL, 2),)),
        "HOUNDS": Move(frozenset({"attack"}), "HOUNDS",
                       damage=1, hits=_deadly(ascension, 8, 9)),
    }


def fogmog(ascension : int) -> MoveTable:
    swipe = dict(intents=frozenset({"attack", "buff"}), damage=_deadly(ascension, 8, 9), hits=1,
                 self_status=((StatusId.STRENGTH, 1),))
    return {
        "ILLUSION": Move(frozenset({"summon"}), "SWIPE", summon=("EYE_WITH_TEETH", 0)),
        "SWIPE": Move(next_move="", branches=(Branch("SWIPE_RANDOM", weight=2), Branch("HEADBUTT", weight=3)),
                      **swipe),
        # the same swipe, reached from a random choice; it always leads to a headbutt
        "SWIPE_RANDOM": Move(next_move="HEADBUTT", from_bridge=False, **swipe),
        "HEADBUTT": Move(frozenset({"attack"}), "SWIPE",
                         damage=_deadly(ascension, 14, 16), hits=1),
    }


def eye_with_teeth(ascension : int) -> MoveTable:
    return {
        "DISTRACT": Move(frozenset({"statuscard"}), "DISTRACT", cards=((CardId.DAZED, 3),)),
    }


def vantom(ascension : int) -> MoveTable:
    return {
        "INK_BLOT": Move(frozenset({"attack"}), "INKY_LANCE",
                         damage=_deadly(ascension, 7, 8), hits=1),
        "INKY_LANCE": Move(frozenset({"attack"}), "DISMEMBER",
                           damage=_deadly(ascension, 6, 7), hits=2),
        "DISMEMBER": Move(frozenset({"attack", "statuscard"}), "PREPARE",
                          damage=_deadly(ascension, 26, 30), hits=1, cards=((CardId.WOUND, 3),)),
        "PREPARE": Move(frozenset({"buff"}), "INK_BLOT",
                        self_status=((StatusId.STRENGTH, 2),)),
    }


def ceremonial_beast(ascension : int) -> MoveTable:
    # Plow breaks once the beast is hit down to its amount; it is then stunned and starts phase two
    return {
        "STAMP": Move(frozenset({"buff"}), "PLOW",
                      self_status=((StatusId.PLOW, _deadly(ascension, 150, 160)),)),
        "PLOW": Move(frozenset({"attack", "buff"}), "PLOW",
                     damage=_deadly(ascension, 18, 20), hits=1, self_status=((StatusId.STRENGTH, 2),)),
        "STUN": Move(frozenset({"stun"}), "BEAST_CRY"),
        "BEAST_CRY": Move(frozenset({"debuff"}), "STOMP",
                          player_status=((StatusId.RINGING, 1),)),
        "STOMP": Move(frozenset({"attack"}), "CRUSH",
                      damage=_deadly(ascension, 15, 17), hits=1),
        "CRUSH": Move(frozenset({"attack", "buff"}), "BEAST_CRY",
                      damage=_deadly(ascension, 17, 19), hits=1,
                      self_status=((StatusId.STRENGTH, _deadly(ascension, 3, 4)),)),
    }


def kin_follower(ascension : int) -> MoveTable:
    return {
        "QUICK_SLASH": Move(frozenset({"attack"}), "BOOMERANG", damage=5, hits=1),
        "BOOMERANG": Move(frozenset({"attack"}), "POWER_DANCE", damage=2, hits=2),
        "POWER_DANCE": Move(frozenset({"buff"}), "QUICK_SLASH",
                            self_status=((StatusId.STRENGTH, _deadly(ascension, 2, 3)),)),
    }


def kin_priest(ascension : int) -> MoveTable:
    # a four round cycle starting on round 1
    orb = _deadly(ascension, 8, 9)
    return {
        "ORB_OF_FRAILTY": Move(frozenset({"attack", "debuff"}), "ORB_OF_WEAKNESS", damage=orb, hits=1,
                               player_status=((StatusId.FRAIL, 1),), round_mod=(4, 1)),
        "ORB_OF_WEAKNESS": Move(frozenset({"attack", "debuff"}), "BEAM", damage=orb, hits=1,
                                player_status=((StatusId.WEAK, 1),), round_mod=(4, 2)),
        "BEAM": Move(frozenset({"attack"}), "RITUAL", damage=3, hits=3),
        "RITUAL": Move(frozenset({"buff"}), "ORB_OF_FRAILTY",
                       self_status=((StatusId.STRENGTH, _deadly(ascension, 2, 3)),)),
    }


EGG_SLOTS = 5
HATCHLING_HP = ((19, 22), (20, 23))     # (base, tough) hit points of a hatched Tough Egg

# monsters that appear mid-fight: (min hp, max hp, tough min hp, tough max hp)
SPAWN_HP = {
    "SNEAKY_GREMLIN": (10, 14, 11, 15),
    "FAT_GREMLIN": (13, 17, 14, 18),
    "GAS_BOMB": (7, 7, 8, 8),
    "TWO_TAILED_RAT": (17, 21, 18, 22),
    "WRIGGLER": (17, 21, 18, 22),
    "EYE_WITH_TEETH": (6, 6, 6, 6),
    "PARAFRIGHT": (21, 21, 21, 21),
    "TOUGH_EGG": (14, 18, 15, 19),
    "AXEBOT": (70, 78, 76, 86),
    "ZAPBOT": (18, 23, 19, 24),
    "STABBOT": (18, 23, 19, 24),
    "NOISEBOT": (18, 23, 19, 24),
    "GUARDBOT": (16, 20, 17, 21),
}

# the move a summoned monster starts on (default SPAWNED) and the statuses it starts with
SPAWN_MOVE = {"GAS_BOMB": "EXPLODE", "TWO_TAILED_RAT": "SCRATCH", "EYE_WITH_TEETH": "DISTRACT", "PARAFRIGHT": "SLAM", "TOUGH_EGG": "HATCH", "AXEBOT": "BOOT_UP",
              "ZAPBOT": "ZAP", "STABBOT": "STAB", "GUARDBOT": "GUARD", "NOISEBOT": "NOISE"}
SPAWN_STATUS = {"GAS_BOMB": ((StatusId.MINION, 1),), "EYE_WITH_TEETH": ((StatusId.ILLUSION, 1), (StatusId.MINION, 1)),
                "PARAFRIGHT": ((StatusId.ILLUSION, 1), (StatusId.MINION, 1)),
                "TOUGH_EGG": ((StatusId.HATCH, 2), (StatusId.MINION, 1)),
                "ZAPBOT": ((StatusId.MINION, 1), (StatusId.HIGH_VOLTAGE, 2)),
                "STABBOT": ((StatusId.MINION, 1),), "GUARDBOT": ((StatusId.MINION, 1),), "NOISEBOT": ((StatusId.MINION, 1),)}      # laid during the enemy turn, so it counts down from 2

# summoner -> (summoning move, summoned monster, slot): the monster is missing from a bridge
# state when it has been killed, and returns at the end of the enemy turn
SUMMONS = {"FOGMOG": ("ILLUSION", "EYE_WITH_TEETH", 0),
           "THE_OBSCURA": ("ILLUSION", "PARAFRIGHT", 0)}


# ---------------------------------------------------------------- Act 2: the Hive
def bowlbug_egg(ascension : int) -> MoveTable:
    return {
        "BITE": Move(frozenset({"attack", "defend"}), "BITE",
                     damage=_deadly(ascension, 7, 8), hits=1, block=_deadly(ascension, 7, 8)),
    }


def bowlbug_nectar(ascension : int) -> MoveTable:
    return {
        "THRASH": Move(frozenset({"attack"}), "BUFF", damage=3, hits=1),
        "BUFF": Move(frozenset({"buff"}), "THRASH2", self_status=((StatusId.STRENGTH, _deadly(ascension, 15, 16)),)),
        "THRASH2": Move(frozenset({"attack"}), "THRASH2", damage=3, hits=1),
    }


def bowlbug_silk(ascension : int) -> MoveTable:
    return {
        "TOXIC_SPIT": Move(frozenset({"debuff"}), "THRASH", player_status=((StatusId.WEAK, 1),)),
        "THRASH": Move(frozenset({"attack"}), "TOXIC_SPIT", damage=_deadly(ascension, 4, 5), hits=2),
    }


def bowlbug_rock(ascension : int) -> MoveTable:
    # Imbalanced: when an attack of its is fully blocked it is stunned after finishing it (Enemy.imbalanced)
    return {
        "HEADBUTT": Move(frozenset({"attack"}), "HEADBUTT", damage=_deadly(ascension, 15, 16), hits=1),
    }


def chomper(ascension : int) -> MoveTable:
    return {
        "CLAMP": Move(frozenset({"attack"}), "SCREECH", damage=_deadly(ascension, 8, 9), hits=2),
        "SCREECH": Move(frozenset({"statuscard"}), "CLAMP", cards=((CardId.DAZED, 3),)),
    }


def spiny_toad(ascension : int) -> MoveTable:
    # the spikes are Thorns 5, taken back by the explosion
    return {
        "PROTRUDING_SPIKES": Move(frozenset({"buff"}), "SPIKE_EXPLOSION", self_status=((StatusId.THORNS, 5),)),
        "SPIKE_EXPLOSION": Move(frozenset({"attack"}), "TONGUE_LASH", damage=_deadly(ascension, 23, 25), hits=1,
                                self_status=((StatusId.THORNS, -5),)),
        "TONGUE_LASH": Move(frozenset({"attack"}), "PROTRUDING_SPIKES", damage=_deadly(ascension, 17, 19), hits=1),
    }


def myte(ascension : int) -> MoveTable:
    return {
        "TOXIC": Move(frozenset({"statuscard"}), "BITE", hand_cards=((CardId.TOXIC, 2),)),
        "BITE": Move(frozenset({"attack"}), "SUCK", damage=_deadly(ascension, 13, 15), hits=1),
        "SUCK": Move(frozenset({"attack", "buff"}), "TOXIC", damage=_deadly(ascension, 4, 6), hits=1,
                     self_status=((StatusId.STRENGTH, _deadly(ascension, 2, 3)),)),
    }


def parafright(ascension : int) -> MoveTable:
    return {
        "SLAM": Move(frozenset({"attack"}), "SLAM", damage=_deadly(ascension, 16, 17), hits=1),
    }


def the_obscura(ascension : int) -> MoveTable:
    after = (Branch("PIERCING_GAZE"), Branch("WAIL"), Branch("HARDENING_STRIKE"))      # never the same move twice in a row
    return {
        "ILLUSION": Move(frozenset({"summon"}), "", branches=after, summon=("PARAFRIGHT", 0)),
        "PIERCING_GAZE": Move(frozenset({"attack"}), "", branches=after, damage=_deadly(ascension, 10, 11), hits=1),
        "WAIL": Move(frozenset({"buff"}), "", branches=after, team_status=((StatusId.STRENGTH, 3),)),
        "HARDENING_STRIKE": Move(frozenset({"attack", "defend"}), "", branches=after,
                                 damage=_deadly(ascension, 6, 7), hits=1, block=_deadly(ascension, 6, 7)),
    }


def _pheromone_spit(enemy, combat):
    # Personal Hive grows up to 3 (with 1 Strength each time); after that it is 2 Strength
    if enemy.status_amount(StatusId.PERSONAL_HIVE) < 3:
        enemy.apply_status(StatusId.PERSONAL_HIVE, 1)
        enemy.apply_status(StatusId.STRENGTH, 1)
    else:
        enemy.apply_status(StatusId.STRENGTH, 2)


def exoskeleton(ascension : int) -> MoveTable:
    # after a skitter it is always the mandibles (neither may repeat); after the mandibles it enrages
    either = (Branch("SKITTER"), Branch("MANDIBLES"))
    return {
        "SKITTER": Move(frozenset({"attack"}), "", branches=either, damage=1, hits=_deadly(ascension, 3, 4)),
        "MANDIBLES": Move(frozenset({"attack"}), "ENRAGE", damage=_deadly(ascension, 8, 9), hits=1),
        "ENRAGE": Move(frozenset({"buff"}), "", branches=either, self_status=((StatusId.STRENGTH, 2),)),
    }


def hunter_killer(ascension : int) -> MoveTable:
    after = (Branch("BITE"), Branch("PUNCTURE", max_streak=2))
    return {
        "TENDERIZING_GOOP": Move(frozenset({"debuff"}), "", branches=after, player_status=((StatusId.TENDER, 1),)),
        "BITE": Move(frozenset({"attack"}), "", branches=after, damage=_deadly(ascension, 17, 19), hits=1),
        "PUNCTURE": Move(frozenset({"attack"}), "", branches=after, damage=_deadly(ascension, 7, 8), hits=3),
    }


def entomancer(ascension : int) -> MoveTable:
    return {
        "BEES": Move(frozenset({"attack"}), "SPEAR", damage=3, hits=_deadly(ascension, 7, 8)),
        "SPEAR": Move(frozenset({"attack"}), "PHEROMONE_SPIT", damage=_deadly(ascension, 18, 20), hits=1),
        "PHEROMONE_SPIT": Move(frozenset({"buff"}), "BEES", effect=_pheromone_spit),
    }


def infested_prism(ascension : int) -> MoveTable:
    spark = _deadly(ascension, 2, 3)
    return {
        "JAB": Move(frozenset({"attack"}), "RADIATE", damage=_deadly(ascension, 15, 17), hits=1),
        "RADIATE": Move(frozenset({"attack", "defend"}), "WHIRLWIND",
                        damage=_deadly(ascension, 11, 13), hits=1, block=_deadly(ascension, 11, 13)),
        "WHIRLWIND": Move(frozenset({"attack"}), "PULSATE", damage=_deadly(ascension, 5, 6), hits=3),
        "PULSATE": Move(frozenset({"attack", "buff", "defend"}), "JAB", damage=_deadly(ascension, 8, 10), hits=1,
                        block=_tough(ascension, 20, 22), self_status=((StatusId.VITAL_SPARK, spark),)),
    }


def louse_progenitor(ascension : int) -> MoveTable:
    return {
        "WEB_CANNON": Move(frozenset({"attack", "debuff"}), "CURL_AND_GROW", damage=_deadly(ascension, 9, 10), hits=1,
                           player_status=((StatusId.FRAIL, 2),)),
        "CURL_AND_GROW": Move(frozenset({"defend", "buff"}), "POUNCE",
                              block=_tough(ascension, 14, 18), self_status=((StatusId.STRENGTH, 5),)),
        "POUNCE": Move(frozenset({"attack"}), "WEB_CANNON", damage=_deadly(ascension, 14, 16), hits=1),
    }


def _lay_eggs(enemy, combat):
    """Three Tough Eggs, as many as there are free slots (five). They stand in slot order, the newest to the left, and
    every egg's id is its position among the eggs, as the bridge reports it."""
    from sts2_lite.enemy import Enemy
    cs = combat.combat_state
    for _ in range(min(3, EGG_SLOTS - sum(e.enemy_id.startswith("TOUGH_EGG_") for e in cs.enemies))):
        combat.summon(Enemy.spawn("TOUGH_EGG", 0, cs.ascension), front=True)
    for i, egg in enumerate(e for e in cs.enemies if e.enemy_id.startswith("TOUGH_EGG_")):
        egg.enemy_id, egg.slot = f"TOUGH_EGG_{i}", i


def _can_lay(enemy, combat) -> bool:
    return len(combat.combat_state.enemies) <= 3        # every living enemy counts, the Ovicopter too


def _hatch(enemy, combat):
    # the egg becomes a hatchling: new hit points, and every power but Minion is lost
    low, high = HATCHLING_HP[0 if combat.combat_state.ascension < TOUGH_ASCENSION else 1]
    enemy.max_hp = enemy.current_hp = rng.randrange(low, high + 1)
    for status_id in [s for s in enemy.status if s is not StatusId.MINION]:
        del enemy.status[status_id]


def _steal_priority(card) -> int:
    """ThievingHopper._stealPriorities: the index of the first rule that accepts the card (Imbued cards count last)."""
    if card.enchantment == EnchantmentId.IMBUED:
        return 3
    rarity = CARD_RARITY[card.card_id]
    return {CardRarity.Uncommon: 0, CardRarity.Common: 1, CardRarity.Rare: 1, CardRarity.Event: 1,
            CardRarity.Basic: 2, CardRarity.Ancient: 3}.get(rarity, 4)


def _steal_a_card(enemy, combat):
    """Takes a card of the deck (not one made this fight) from the draw or discard pile, the Uncommon ones first."""
    player = combat.combat_state.player
    deck = [c for c in [*player.draw_pile, *player.discard_pile]
            if not c.generated and CARD_RARITY[c.card_id] not in (CardRarity.Status, CardRarity.Token)]
    if not deck:
        return
    best = min(_steal_priority(c) for c in deck)
    pool = [c for c in deck if _steal_priority(c) == best] if best < 4 else deck
    card = rng.choice(pool)
    if any(card is c for c in player.draw_pile):
        player.remove_from_draw_pile(card)
    else:
        player.discard_pile = [c for c in player.discard_pile if c is not card]
    enemy.apply_status(StatusId.SWIPE, 1)


def _escape(enemy, combat):
    combat.combat_state.enemies.remove(enemy)


def tunneler(ascension : int) -> MoveTable:
    # Burrowed keeps the block; breaking it stuns the Tunneler and it bites again (Creature._after_damage)
    return {
        "BITE": Move(frozenset({"attack"}), "BURROW", damage=_deadly(ascension, 13, 15), hits=1),
        "BURROW": Move(frozenset({"buff", "defend"}), "BELOW", block=_tough(ascension, 32, 37),
                       self_status=((StatusId.BURROWED, 1),)),
        "BELOW": Move(frozenset({"attack"}), "BELOW", damage=_deadly(ascension, 23, 26), hits=1),
    }


def slumbering_beetle(ascension : int) -> MoveTable:
    # Slumber ticks at the end of each enemy turn; at zero (or when hit down to it) the Plating goes and it rolls
    return {
        "SNORE": Move(frozenset({"sleep"}), "",
                      choose=lambda e, c: "SNORE" if StatusId.SLUMBER in e.status else "ROLL_OUT"),
        "ROLL_OUT": Move(frozenset({"attack", "buff"}), "ROLL_OUT", damage=_deadly(ascension, 16, 18), hits=1,
                         self_status=((StatusId.STRENGTH, 2),)),
        "STUNNED": Move(frozenset({"stun"}), "", effect=lambda e, c: e.status.pop(StatusId.PLATING, None)),
    }


def ovicopter(ascension : int) -> MoveTable:
    return {
        "LAY_EGGS": Move(frozenset({"summon"}), "SMASH", effect=_lay_eggs),
        "SMASH": Move(frozenset({"attack"}), "TENDERIZER", damage=_deadly(ascension, 16, 17), hits=1),
        "TENDERIZER": Move(frozenset({"attack", "debuff"}), "", damage=_deadly(ascension, 7, 8), hits=1,
                           player_status=((StatusId.VULNERABLE, 2),),
                           choose=lambda e, c: "LAY_EGGS" if _can_lay(e, c) else "NUTRITIONAL_PASTE"),
        "NUTRITIONAL_PASTE": Move(frozenset({"buff"}), "SMASH", self_status=((StatusId.STRENGTH, _deadly(ascension, 3, 4)),)),
    }


def tough_egg(ascension : int) -> MoveTable:
    return {
        "HATCH": Move(frozenset({"summon"}), "NIBBLE", effect=_hatch),
        "NIBBLE": Move(frozenset({"attack"}), "NIBBLE", damage=_deadly(ascension, 4, 5), hits=1),
    }


def thieving_hopper(ascension : int) -> MoveTable:
    return {
        "THIEVERY": Move(frozenset({"attack", "carddebuff"}), "FLUTTER", damage=_deadly(ascension, 17, 19), hits=1,
                         effect=_steal_a_card),
        "FLUTTER": Move(frozenset({"buff"}), "HAT_TRICK", self_status=((StatusId.FLUTTER, 5),)),
        "HAT_TRICK": Move(frozenset({"attack"}), "NAB", damage=_deadly(ascension, 21, 23), hits=1),
        "NAB": Move(frozenset({"attack"}), "ESCAPE", damage=_deadly(ascension, 14, 16), hits=1),
        "ESCAPE": Move(frozenset({"escape"}), "ESCAPE", effect=_escape),
    }


def the_insatiable(ascension : int) -> MoveTable:
    # Sandpit (4) counts down at the start of each enemy turn and kills the player at zero; Frantic Escape adds one
    return {
        "LIQUIFY_GROUND": Move(frozenset({"buff", "statuscard"}), "THRASH", self_status=((StatusId.SANDPIT, 4),),
                               draw_cards=((CardId.FRANTIC_ESCAPE, 3),), cards=((CardId.FRANTIC_ESCAPE, 3),)),
        "THRASH": Move(frozenset({"attack"}), "LUNGING_BITE", damage=_deadly(ascension, 8, 9), hits=2),
        "LUNGING_BITE": Move(frozenset({"attack"}), "SALIVATE", damage=_deadly(ascension, 28, 31), hits=1),
        "SALIVATE": Move(frozenset({"buff"}), "THRASH_2", self_status=((StatusId.STRENGTH, _deadly(ascension, 2, 3)),)),
        "THRASH_2": Move(frozenset({"attack"}), "THRASH", damage=_deadly(ascension, 8, 9), hits=2),
    }


CURSE_SETS = ((CardId.DISINTEGRATION, CardId.MIND_ROT), (CardId.DISINTEGRATION, CardId.SLOTH), (CardId.DISINTEGRATION, CardId.WASTE_AWAY))
CURSE_CASTS = 3
DISINTEGRATION_DAMAGE = (6, 7, 8)       # by cast


def _curse_of_knowledge(enemy, combat):
    # the player picks one of two curses; the pick is applied (and the next player turn begins) when it is made
    from sts2_lite.card import Card
    combat.request_curse([Card.create_knowledge_curse(c) for c in CURSE_SETS[enemy.counter]], DISINTEGRATION_DAMAGE[enemy.counter])
    enemy.counter += 1


def knowledge_demon(ascension : int) -> MoveTable:
    return {
        "CURSE_OF_KNOWLEDGE": Move(frozenset({"debuff"}), "SLAP", effect=_curse_of_knowledge),
        "SLAP": Move(frozenset({"attack"}), "KNOWLEDGE_OVERWHELMING", damage=_deadly(ascension, 17, 18), hits=1),
        "KNOWLEDGE_OVERWHELMING": Move(frozenset({"attack"}), "PONDER", damage=_deadly(ascension, 8, 9), hits=3),
        "PONDER": Move(frozenset({"attack", "heal", "buff"}), "", damage=_deadly(ascension, 11, 13), hits=1, heal=30,
                       self_status=((StatusId.STRENGTH, _deadly(ascension, 2, 3)),),
                       choose=lambda e, c: "CURSE_OF_KNOWLEDGE" if e.counter < CURSE_CASTS else "SLAP"),
    }


def decimillipede_segment(ascension : int) -> MoveTable:
    # CONSTRICT -> BULK -> WRITHE in a ring; a killed segment lies DEAD for a turn, then REATTACHes and picks one of the three at random
    revive = (Branch("WRITHE"), Branch("BULK"), Branch("CONSTRICT"))
    return {
        "WRITHE": Move(frozenset({"attack"}), "CONSTRICT", damage=_deadly(ascension, 5, 6), hits=2),
        "BULK": Move(frozenset({"attack", "buff"}), "WRITHE", damage=_deadly(ascension, 6, 7), hits=1,
                     self_status=((StatusId.STRENGTH, 2),)),
        "CONSTRICT": Move(frozenset({"attack", "debuff"}), "BULK", damage=_deadly(ascension, 8, 9), hits=1,
                          player_status=((StatusId.WEAK, 1),)),
        "DEAD": Move(frozenset(), "REATTACH"),
        "REATTACH": Move(frozenset({"heal"}), "", branches=revive),
    }


SEGMENTS = ("DECIMILLIPEDE_SEGMENT_FRONT", "DECIMILLIPEDE_SEGMENT_MIDDLE", "DECIMILLIPEDE_SEGMENT_BACK")      # left to right


def crusher(ascension : int) -> MoveTable:
    # the Kaiser Crab's left arm; it hits 1.5x while the player faces away from it (Surrounded)
    return {
        "THRASH": Move(frozenset({"attack"}), "ENLARGING_STRIKE", damage=_deadly(ascension, 12, 14), hits=1),
        "ENLARGING_STRIKE": Move(frozenset({"attack"}), "BUG_STING", damage=4, hits=1),
        "BUG_STING": Move(frozenset({"attack", "debuff"}), "ADAPT", damage=_deadly(ascension, 6, 7), hits=2,
                          player_status=((StatusId.WEAK, 2), (StatusId.FRAIL, 2))),
        "ADAPT": Move(frozenset({"buff"}), "GUARDED_STRIKE", self_status=((StatusId.STRENGTH, _deadly(ascension, 2, 3)),)),
        "GUARDED_STRIKE": Move(frozenset({"attack", "defend"}), "THRASH", damage=_deadly(ascension, 12, 14), hits=1, block=18),
    }


def rocket(ascension : int) -> MoveTable:
    # the right arm; RECHARGE is a turn of doing nothing
    return {
        "TARGETING_RETICLE": Move(frozenset({"attack"}), "PRECISION_BEAM", damage=_deadly(ascension, 3, 4), hits=1),
        "PRECISION_BEAM": Move(frozenset({"attack"}), "CHARGE_UP", damage=_deadly(ascension, 18, 20), hits=1),
        "CHARGE_UP": Move(frozenset({"buff"}), "LASER", self_status=((StatusId.STRENGTH, _deadly(ascension, 2, 3)),)),
        "LASER": Move(frozenset({"attack"}), "RECHARGE", damage=_deadly(ascension, 31, 35), hits=1),
        "RECHARGE": Move(frozenset({"sleep"}), "TARGETING_RETICLE"),
    }


# ---------------------------------------------------------------- Act 3: Glory
def axebot(ascension : int) -> MoveTable:
    # Stock (2) brings it back when it dies; each return opens with Boot Up, which grants more Strength the fewer lives are left
    def boot_up(enemy, combat):
        lives_used = 2 - enemy.status_amount(StatusId.STOCK)
        enemy.apply_status(StatusId.STRENGTH, _deadly(ascension, 3, 4) * lives_used)
    return {
        "BOOT_UP": Move(frozenset({"defend", "buff"}), "HAMMER_UPPERCUT", block=_deadly(ascension, 10, 15), effect=boot_up),
        "ONE_TWO": Move(frozenset({"attack"}), "HAMMER_UPPERCUT", damage=_deadly(ascension, 9, 10), hits=2),
        "HAMMER_UPPERCUT": Move(frozenset({"attack", "debuff"}), "ONE_TWO", damage=_deadly(ascension, 12, 14), hits=1,
                                player_status=((StatusId.WEAK, 2), (StatusId.FRAIL, 2))),
    }


def punch_construct(ascension : int) -> MoveTable:
    return {
        "READY": Move(frozenset({"defend"}), "FAST_PUNCH", block=10),
        "FAST_PUNCH": Move(frozenset({"attack", "debuff"}), "STRONG_PUNCH", damage=_deadly(ascension, 5, 6), hits=2,
                           player_status=((StatusId.FRAIL, 1),)),
        "STRONG_PUNCH": Move(frozenset({"attack"}), "READY", damage=_deadly(ascension, 14, 16), hits=1),
    }


def globe_head(ascension : int) -> MoveTable:
    return {
        "SHOCKING_SLAP": Move(frozenset({"attack", "debuff"}), "THUNDER_STRIKE", damage=_deadly(ascension, 13, 14), hits=1,
                              player_status=((StatusId.FRAIL, 2),)),
        "THUNDER_STRIKE": Move(frozenset({"attack"}), "GALVANIC_BURST", damage=_deadly(ascension, 6, 7), hits=3),
        "GALVANIC_BURST": Move(frozenset({"attack", "buff"}), "SHOCKING_SLAP", damage=_deadly(ascension, 16, 17), hits=1,
                               self_status=((StatusId.STRENGTH, 2),)),
    }


def scroll_of_biting(ascension : int) -> MoveTable:
    # Chew can repeat once (CanRepeatXTimes 2); Chomp never twice in a row
    return {
        "CHOMP": Move(frozenset({"attack"}), "MORE_TEETH", damage=_deadly(ascension, 14, 16), hits=1),
        "CHEW": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 5, 6), hits=2,
                     branches=(Branch("CHOMP"), Branch("CHEW", max_streak=2))),
        "MORE_TEETH": Move(frozenset({"buff"}), "CHEW", self_status=((StatusId.STRENGTH, 2),)),
    }


def slimed_berserker(ascension : int) -> MoveTable:
    return {
        "VOMIT_ICHOR": Move(frozenset({"status"}), "FURIOUS_PUMMELING", cards=((CardId.SLIMED, 10),)),
        "FURIOUS_PUMMELING": Move(frozenset({"attack"}), "LEECHING_HUG", damage=_deadly(ascension, 4, 5), hits=4),
        "LEECHING_HUG": Move(frozenset({"debuff", "buff"}), "SMOTHER",
                             player_status=((StatusId.WEAK, 3),), self_status=((StatusId.STRENGTH, 3),)),
        "SMOTHER": Move(frozenset({"attack"}), "VOMIT_ICHOR", damage=_deadly(ascension, 30, 33), hits=1),
    }


def _frog_next(enemy, combat) -> str:
    # HALF_HEALTH: once, below half of its maximum (integer division), it charges instead of lashing
    if "BEETLE_CHARGE" not in enemy.used_moves and enemy.current_hp < enemy.max_hp // 2:
        return "BEETLE_CHARGE"
    return "TONGUE_LASH"


def frog_knight(ascension : int) -> MoveTable:
    return {
        "TONGUE_LASH": Move(frozenset({"attack", "debuff"}), "STRIKE_DOWN_EVIL", damage=_deadly(ascension, 13, 14), hits=1,
                            player_status=((StatusId.FRAIL, 2),)),
        "STRIKE_DOWN_EVIL": Move(frozenset({"attack"}), "FOR_THE_QUEEN", damage=_deadly(ascension, 21, 23), hits=1),
        "FOR_THE_QUEEN": Move(frozenset({"buff"}), "", self_status=((StatusId.STRENGTH, 5),), choose=_frog_next),
        "BEETLE_CHARGE": Move(frozenset({"attack"}), "TONGUE_LASH", damage=_deadly(ascension, 35, 40), hits=1),
    }


def _possess(stat : StatusId, possess : StatusId, amount : int, block : int = 0):
    """Take `amount` of Strength or Dexterity from the player and give it to the mover; the Possess power remembers what was
    taken (Artifact stops it) and hands it back when the mover dies."""
    def effect(enemy, combat):
        player = combat.combat_state.player
        before = player.status_amount(stat)
        player.apply_status(stat, -amount)
        taken = before - player.status_amount(stat)
        if taken > 0 and possess in enemy.status:
            records = enemy.status[possess].records
            if records:
                records[0][0] += taken
            else:
                records.append([taken])
        if block:
            enemy.apply_block(block + enemy.status_amount(StatusId.DEXTERITY))     # Move block is powered: Dexterity counts
        enemy.apply_status(stat, amount)
    return effect


def the_lost(ascension : int) -> MoveTable:
    return {
        "DEBILITATING_SMOG": Move(frozenset({"debuff", "buff"}), "EYE_LASERS",
                                  effect=_possess(StatusId.STRENGTH, StatusId.POSSESS_STRENGTH, 2)),
        "EYE_LASERS": Move(frozenset({"attack"}), "DEBILITATING_SMOG", damage=_deadly(ascension, 4, 5), hits=2),
    }


def the_forgotten(ascension : int) -> MoveTable:
    return {
        "MIASMA": Move(frozenset({"debuff", "defend", "buff"}), "DREAD",
                       effect=_possess(StatusId.DEXTERITY, StatusId.POSSESS_SPEED, 2, block=8)),
        "DREAD": Move(frozenset({"attack"}), "MIASMA", damage=_deadly(ascension, 13, 15), hits=1, dex_damage=True),
    }



def _living_shield_next(enemy, combat) -> str:
    # SHIELD_SLAM_BRANCH: keep slamming while any other enemy lives, then smash forever
    if combat is None or any(e is not enemy and e.current_hp > 0 for e in combat.combat_state.enemies):
        return "SHIELD_SLAM"
    return "SMASH"


def living_shield(ascension : int) -> MoveTable:
    return {
        "SHIELD_SLAM": Move(frozenset({"attack"}), "", damage=6, hits=1, choose=_living_shield_next),
        "SMASH": Move(frozenset({"attack", "buff"}), "SMASH", damage=_deadly(ascension, 16, 18), hits=1,
                      self_status=((StatusId.STRENGTH, 3),)),
    }


def turret_operator(ascension : int) -> MoveTable:
    # two identical unloads, then a reload (the cycle starts on round 1)
    fire = _deadly(ascension, 3, 4)
    return {
        "UNLOAD": Move(frozenset({"attack"}), "UNLOAD_2", damage=fire, hits=5, round_mod=(3, 1)),
        "UNLOAD_2": Move(frozenset({"attack"}), "RELOAD", damage=fire, hits=5, round_mod=(3, 2)),
        "RELOAD": Move(frozenset({"buff"}), "UNLOAD", self_status=((StatusId.STRENGTH, 1),)),
    }


def _incantation(enemy, combat):
    enemy.apply_status(StatusId.RITUAL, 9)
    enemy.status[StatusId.RITUAL].records = [[1]]       # RitualPower.WasJustAppliedByEnemy: no Strength at the end of this turn


def devoted_sculptor(ascension : int) -> MoveTable:
    return {
        "FORBIDDEN_INCANTATION": Move(frozenset({"buff"}), "SAVAGE", effect=_incantation),
        "SAVAGE": Move(frozenset({"attack"}), "SAVAGE", damage=_deadly(ascension, 12, 15), hits=1),
    }


def _take_off(enemy, combat):
    enemy.status.pop(StatusId.SOAR, None)


def owl_magistrate(ascension : int) -> MoveTable:
    return {
        "MAGISTRATE_SCRUTINY": Move(frozenset({"attack"}), "PECK_ASSAULT", damage=_deadly(ascension, 16, 17), hits=1),
        "PECK_ASSAULT": Move(frozenset({"attack"}), "JUDICIAL_FLIGHT", damage=4, hits=6),
        "JUDICIAL_FLIGHT": Move(frozenset({"buff"}), "VERDICT", self_status=((StatusId.SOAR, 1),)),
        "VERDICT": Move(frozenset({"attack", "debuff"}), "MAGISTRATE_SCRUTINY", damage=_deadly(ascension, 33, 36), hits=1,
                        player_status=((StatusId.VULNERABLE, 4),), effect=_take_off),
    }


# Fabricator: bots it can make, as codes in Enemy.counter (the last one made is never made twice in a row from the same list)
BOT_CODES = {"ZAPBOT": 1, "STABBOT": 2, "GUARDBOT": 3, "NOISEBOT": 4}
AGGRO_BOTS, DEFENSE_BOTS = ("ZAPBOT", "STABBOT"), ("GUARDBOT", "NOISEBOT")
FABRICATOR_TEAM = 4


def _make_bot(enemy, combat, options):
    from sts2_lite.enemy import Enemy     # enemy.py imports this module
    last = {code: name for name, code in BOT_CODES.items()}.get(enemy.counter)
    choices = [b for b in options if b != last]
    bot = rng.choice(choices)
    enemy.counter = BOT_CODES[bot]
    enemies = combat.combat_state.enemies
    bot_enemy = Enemy.spawn(bot, 0, combat.combat_state.ascension)
    # GetNextSlot: the encounter's slots run bot1, bot2, fabricator, bot3, bot4 from left to right and a new bot takes the first free one
    home = enemies.index(enemy) if enemy in enemies else len(enemies)
    left, right = home, len(enemies) - home - 1
    if left < 2:
        at = left
    elif right < 2:
        at = home + 1 + right
    else:
        at = len(enemies)
    combat.summon(bot_enemy, at=at)
    same = [e for e in combat.combat_state.enemies if e.enemy_id.rpartition("_")[0] == bot]
    for i, e in enumerate(same):        # the bridge numbers monsters of a kind by their place in the line
        e.enemy_id, e.slot = f"{bot}_{i}", i


def _fabricate(enemy, combat):
    _make_bot(enemy, combat, DEFENSE_BOTS)
    _make_bot(enemy, combat, AGGRO_BOTS)


def _fabricating_strike(enemy, combat):
    _make_bot(enemy, combat, AGGRO_BOTS)


def _fabricator_next(enemy, combat) -> str:
    # fabricateBranch: while fewer than four creatures live on its side it builds (an even pick), then it only disintegrates
    if combat is not None and sum(1 for e in combat.combat_state.enemies if e.current_hp > 0) >= FABRICATOR_TEAM:
        return "DISINTEGRATE"
    return rng.choice(("FABRICATE", "FABRICATING_STRIKE"))


def fabricator(ascension : int) -> MoveTable:
    return {
        "FABRICATE": Move(frozenset({"summon"}), "", effect=_fabricate, choose=_fabricator_next),
        "FABRICATING_STRIKE": Move(frozenset({"attack", "summon"}), "", damage=_deadly(ascension, 18, 21), hits=1,
                                   effect=_fabricating_strike, choose=_fabricator_next),
        "DISINTEGRATE": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 11, 13), hits=1, choose=_fabricator_next),
    }


def zapbot(ascension : int) -> MoveTable:
    return {"ZAP": Move(frozenset({"attack"}), "ZAP", damage=_deadly(ascension, 14, 15), hits=1)}


def stabbot(ascension : int) -> MoveTable:
    return {"STAB": Move(frozenset({"attack", "debuff"}), "STAB", damage=_deadly(ascension, 11, 12), hits=1,
                         player_status=((StatusId.FRAIL, 1),))}


def _guard(enemy, combat):
    for ally in combat.combat_state.enemies:
        if ally.enemy_id.startswith("FABRICATOR") and ally.current_hp > 0:
            ally.apply_block(15)        # unpowered


def guardbot(ascension : int) -> MoveTable:
    return {"GUARD": Move(frozenset({"defend"}), "GUARD", effect=_guard)}


def _noise(enemy, combat):
    player = combat.combat_state.player
    player.discard_pile.append(Card.create(CardId.DAZED))
    player.insert_into_draw_pile(Card.create(CardId.DAZED))


def noisebot(ascension : int) -> MoveTable:
    return {"NOISE": Move(frozenset({"status"}), "NOISE", effect=_noise)}



def soul_nexus(ascension : int) -> MoveTable:
    # the next move is any of the three except the one just used
    follow = (Branch("SOUL_BURN"), Branch("MAELSTROM"), Branch("DRAIN_LIFE"))
    return {
        "SOUL_BURN": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 29, 31), hits=1, branches=follow),
        "MAELSTROM": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 6, 7), hits=4, branches=follow),
        "DRAIN_LIFE": Move(frozenset({"attack", "debuff"}), "", damage=_deadly(ascension, 18, 19), hits=1, branches=follow,
                           player_status=((StatusId.VULNERABLE, 2), (StatusId.WEAK, 2))),
    }


def mecha_knight(ascension : int) -> MoveTable:
    return {
        "CHARGE": Move(frozenset({"attack"}), "FLAMETHROWER", damage=_deadly(ascension, 25, 30), hits=1),
        "FLAMETHROWER": Move(frozenset({"status"}), "WINDUP", hand_cards=((CardId.BURN, 4),)),
        "WINDUP": Move(frozenset({"defend", "buff"}), "HEAVY_CLEAVE", block=15, self_status=((StatusId.STRENGTH, 5),)),
        "HEAVY_CLEAVE": Move(frozenset({"attack"}), "FLAMETHROWER", damage=_deadly(ascension, 35, 40), hits=1),
    }


def flail_knight(ascension : int) -> MoveTable:
    follow = (Branch("WAR_CHANT"), Branch("FLAIL", max_streak=2), Branch("RAM", max_streak=2))
    return {
        "WAR_CHANT": Move(frozenset({"buff"}), "", self_status=((StatusId.STRENGTH, 3),), branches=follow),
        "FLAIL": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 9, 10), hits=2, branches=follow),
        "RAM": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 15, 17), hits=1, branches=follow),
    }


def spectral_knight(ascension : int) -> MoveTable:
    follow = (Branch("SOUL_SLASH", max_streak=2), Branch("SOUL_FLAME"))
    return {
        "HEX": Move(frozenset({"debuff"}), "SOUL_SLASH", player_status=((StatusId.HEX, 2),)),
        "SOUL_SLASH": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 15, 17), hits=1, branches=follow),
        "SOUL_FLAME": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 3, 4), hits=3, branches=follow),
    }


def _dampen(enemy, combat):
    from sts2_lite.status import downgrade_cards, StatusInstance
    player = combat.combat_state.player
    if StatusId.DAMPEN in player.status:
        return
    before = len(player.status)
    player.apply_status(StatusId.DAMPEN, 1)
    if StatusId.DAMPEN in player.status:        # Artifact stops it
        downgrade_cards(player)


def magi_knight(ascension : int) -> MoveTable:
    block = _tough(ascension, 5, 9)
    return {
        "POWER_SHIELD": Move(frozenset({"attack", "defend"}), "DAMPEN", damage=_deadly(ascension, 6, 7), hits=1, block=block),
        "DAMPEN": Move(frozenset({"debuff"}), "RAM", effect=_dampen),
        "RAM": Move(frozenset({"attack"}), "PREP", damage=_deadly(ascension, 10, 11), hits=1),
        "PREP": Move(frozenset({"defend"}), "MAGIC_BOMB", block=block),
        "MAGIC_BOMB": Move(frozenset({"attack"}), "RAM", damage=_deadly(ascension, 35, 40), hits=1),
    }


# ---------------------------------------------------------------- Act 3 bosses

def _queen_next(enemy, combat) -> str:
    """The Queen's branch: Burn Bright For Me while the Torch Head Amalgam lives, Off With Your Head once it has died."""
    return "OFF_WITH_YOUR_HEAD" if enemy.counter else "BURN_BRIGHT_FOR_ME"


def _burn_bright(enemy, combat):
    for ally in combat.combat_state.enemies:
        if ally is not enemy and ally.current_hp > 0:
            ally.apply_status(StatusId.STRENGTH, 1)


def queen(ascension : int) -> MoveTable:
    return {
        "PUPPET_STRINGS": Move(frozenset({"carddebuff"}), "YOU_ARE_MINE", player_status=((StatusId.CHAINS_OF_BINDING, 3),)),
        "YOU_ARE_MINE": Move(frozenset({"debuff"}), "", choose=_queen_next,
                             player_status=((StatusId.FRAIL, 99), (StatusId.WEAK, 99), (StatusId.VULNERABLE, 99))),
        "BURN_BRIGHT_FOR_ME": Move(frozenset({"buff", "defend"}), "", block=20, effect=_burn_bright, choose=_queen_next),
        "OFF_WITH_YOUR_HEAD": Move(frozenset({"attack"}), "EXECUTION", damage=_deadly(ascension, 3, 4), hits=5),
        "EXECUTION": Move(frozenset({"attack"}), "ENRAGE", damage=_deadly(ascension, 15, 18), hits=1),
        "ENRAGE": Move(frozenset({"buff"}), "OFF_WITH_YOUR_HEAD", self_status=((StatusId.STRENGTH, 2),)),
    }


def queen_ally_died(queen_enemy, killed, combat):
    """Queen.AfterDeath: the Torch Head Amalgam falling turns a coming Burn Bright For Me into Enrage."""
    if not killed.enemy_id.startswith("TORCH_HEAD_AMALGAM"):
        return
    queen_enemy.counter = 1
    if queen_enemy.move_id == "BURN_BRIGHT_FOR_ME":
        queen_enemy.move_id, queen_enemy.move_streak = "ENRAGE", 1
        queen_enemy.attack_damage = queen_enemy.num_attacks = 0


ALLY_DEATH_HOOKS = {"QUEEN": queen_ally_died}


def torch_head_amalgam(ascension : int) -> MoveTable:
    tackle, weak = _deadly(ascension, 18, 19), _deadly(ascension, 14, 15)
    return {
        "TACKLE": Move(frozenset({"attack"}), "TACKLE_2", damage=tackle, hits=1),
        "TACKLE_2": Move(frozenset({"attack"}), "BEAM", damage=tackle, hits=1),
        "BEAM": Move(frozenset({"attack"}), "TACKLE_3", damage=8, hits=3),
        "TACKLE_3": Move(frozenset({"attack"}), "TACKLE_4", damage=weak, hits=1),
        "TACKLE_4": Move(frozenset({"attack"}), "BEAM", damage=weak, hits=1),
    }


def subject_respawns(enemy) -> int:
    """Which form the Test Subject is in, read off the powers each one gives it (the game counts its respawns privately)."""
    if StatusId.NEMESIS in enemy.status:
        return 2
    return 1 if StatusId.PAINFUL_STABS in enemy.status else 0


def _respawn(enemy, combat):
    asc = combat.combat_state.ascension
    if subject_respawns(enemy) == 0:
        enemy.max_hp = _tough(asc, 200, 212)
        enemy.apply_status(StatusId.PAINFUL_STABS, 1)
    else:
        enemy.max_hp = _tough(asc, 300, 313)
        enemy.apply_status(StatusId.NEMESIS, 1)
        enemy.status[StatusId.NEMESIS].records = [[0]]
        enemy.status.pop(StatusId.ADAPTABLE, None)
        enemy.status.pop(StatusId.PAINFUL_STABS, None)
    enemy.current_hp = enemy.max_hp


def _after_respawn(enemy, combat) -> str:
    return "MULTI_CLAW" if subject_respawns(enemy) < 2 else "PHASE3_LACERATE"


def _claw(enemy, combat):
    enemy.counter += 1          # ExtraMultiClawCount


def test_subject(ascension : int) -> MoveTable:
    return {
        "BITE": Move(frozenset({"attack"}), "SKULL_BASH", damage=_deadly(ascension, 20, 22), hits=1),
        "SKULL_BASH": Move(frozenset({"attack", "debuff"}), "BITE", damage=_deadly(ascension, 14, 16), hits=1,
                           player_status=((StatusId.VULNERABLE, 1),)),
        "RESPAWN": Move(frozenset({"heal", "buff"}), "", effect=_respawn, choose=_after_respawn),
        "MULTI_CLAW": Move(frozenset({"attack"}), "MULTI_CLAW", damage=_deadly(ascension, 10, 11), hits=3,
                           effect=_claw, extra_hits=lambda enemy: enemy.counter),
        "PHASE3_LACERATE": Move(frozenset({"attack"}), "BIG_POUNCE", damage=_deadly(ascension, 10, 11), hits=3),
        "BIG_POUNCE": Move(frozenset({"attack"}), "BURNING_GROWL", damage=45, hits=1),
        "BURNING_GROWL": Move(frozenset({"status", "buff"}), "PHASE3_LACERATE", cards=((CardId.BURN, _deadly(ascension, 3, 5)),),
                              self_status=((StatusId.STRENGTH, _deadly(ascension, 2, 3)),)),
    }


def _increasing_intensity(enemy, combat):
    """Every Wither in the deck gets one more step, the new ones are made at that step, and the Strength it gains grows each time."""
    asc = combat.combat_state.ascension
    player = combat.combat_state.player
    for pile in (player.hand, player.draw_pile, player.discard_pile, player.exhaust_pile):
        for i, card in enumerate(pile):
            if card.card_id == CardId.WITHER:
                pile[i] = Card.create_wither(card.wither_level + 1)
    strength = _deadly(asc, 3, 4) + enemy.counter
    enemy.counter += 1
    for _ in range(_deadly(asc, 1, 2)):
        player.discard_pile.append(Card.create_wither(enemy.counter))
    enemy.apply_status(StatusId.STRENGTH, strength)


def aeonglass(ascension : int) -> MoveTable:
    return {
        "EBB": Move(frozenset({"attack", "defend"}), "EYE_LASERS", damage=_deadly(ascension, 26, 32), hits=1, block=33),
        "EYE_LASERS": Move(frozenset({"attack"}), "INCREASING_INTENSITY", damage=_deadly(ascension, 11, 12), hits=2),
        "INCREASING_INTENSITY": Move(frozenset({"status", "buff"}), "EBB", effect=_increasing_intensity),
    }


# ---------------------------------------------------------------- Act 1: the Underdocks
def _ritual(amount : int):
    def effect(enemy, combat):
        enemy.apply_status(StatusId.RITUAL, amount)
        enemy.status[StatusId.RITUAL].records = [[1]]       # RitualPower.WasJustAppliedByEnemy
    return effect


def calcified_cultist(ascension : int) -> MoveTable:
    return {
        "INCANTATION": Move(frozenset({"buff"}), "DARK_STRIKE", effect=_ritual(2)),
        "DARK_STRIKE": Move(frozenset({"attack"}), "DARK_STRIKE", damage=_deadly(ascension, 9, 11), hits=1),
    }


def damp_cultist(ascension : int) -> MoveTable:
    return {
        "INCANTATION": Move(frozenset({"buff"}), "DARK_STRIKE", effect=_ritual(_deadly(ascension, 5, 6))),
        "DARK_STRIKE": Move(frozenset({"attack"}), "DARK_STRIKE", damage=_deadly(ascension, 1, 3), hits=1),
    }


def corpse_slug(ascension : int) -> MoveTable:
    # the three moves go round in a fixed order; only where each slug starts differs (and Ravenous stuns it, see status.py)
    return {
        "WHIP_SLAP": Move(frozenset({"attack"}), "GLOMP", damage=3, hits=2),
        "GLOMP": Move(frozenset({"attack"}), "GOOP", damage=_deadly(ascension, 8, 9), hits=1),
        "GOOP": Move(frozenset({"debuff"}), "WHIP_SLAP", player_status=((StatusId.FRAIL, 2),)),
    }


def sewer_clam(ascension : int) -> MoveTable:
    return {
        "JET": Move(frozenset({"attack"}), "PRESSURIZE", damage=_deadly(ascension, 10, 11), hits=1),
        "PRESSURIZE": Move(frozenset({"buff"}), "JET", self_status=((StatusId.STRENGTH, 4),)),
    }


def sludge_spinner(ascension : int) -> MoveTable:
    follow = (Branch("OIL_SPRAY"), Branch("SLAM"), Branch("RAGE"))        # never the move just used
    return {
        "OIL_SPRAY": Move(frozenset({"attack", "debuff"}), "", damage=_deadly(ascension, 8, 9), hits=1,
                          player_status=((StatusId.WEAK, 1),), branches=follow),
        "SLAM": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 11, 12), hits=1, branches=follow),
        "RAGE": Move(frozenset({"attack", "buff"}), "", damage=_deadly(ascension, 6, 7), hits=1,
                     self_status=((StatusId.STRENGTH, 3),), branches=follow),
    }


def seapunk(ascension : int) -> MoveTable:
    return {
        "SEA_KICK": Move(frozenset({"attack"}), "SPINNING_KICK", damage=_deadly(ascension, 11, 13), hits=1),
        "SPINNING_KICK": Move(frozenset({"attack"}), "BUBBLE_BURP", damage=2, hits=4),
        "BUBBLE_BURP": Move(frozenset({"buff", "defend"}), "SEA_KICK", block=_tough(ascension, 7, 8),
                            self_status=((StatusId.STRENGTH, _deadly(ascension, 1, 2)),)),
    }


def fossil_stalker(ascension : int) -> MoveTable:
    follow = (Branch("LATCH", max_streak=2), Branch("TACKLE", max_streak=2), Branch("LASH", max_streak=2))
    return {
        "TACKLE": Move(frozenset({"attack", "debuff"}), "", damage=_deadly(ascension, 9, 11), hits=1,
                       player_status=((StatusId.FRAIL, 1),), branches=follow),
        "LATCH": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 12, 14), hits=1, branches=follow),
        "LASH": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 3, 4), hits=2, branches=follow),
    }


def toadpole(ascension : int) -> MoveTable:
    # the front one starts with SPIKEN, the other with WHIRL; both then go round in the same order
    return {
        "WHIRL": Move(frozenset({"attack"}), "SPIKEN", damage=_deadly(ascension, 7, 8), hits=1),
        "SPIKEN": Move(frozenset({"buff"}), "SPIKE_SPIT", self_status=((StatusId.THORNS, 2),)),
        "SPIKE_SPIT": Move(frozenset({"attack"}), "WHIRL", damage=_deadly(ascension, 3, 4), hits=3,
                           self_status=((StatusId.THORNS, -2),)),
    }


def haunted_ship(ascension : int) -> MoveTable:
    return {
        "HAUNT": Move(frozenset({"debuff", "statuscard"}), "SWIPE", player_status=((StatusId.WEAK, 3),),
                      cards=((CardId.DAZED, 5),)),
        "SWIPE": Move(frozenset({"attack"}), "STOMP", damage=_deadly(ascension, 13, 14), hits=1),
        "STOMP": Move(frozenset({"attack"}), "SWIPE", damage=_deadly(ascension, 4, 5), hits=3),
    }


def skulking_colony(ascension : int) -> MoveTable:
    # two identical Zooms, then Inertia and Piercing Stabs; Hardened Shell (20) comes with the monster
    return {
        "ZOOM": Move(frozenset({"attack"}), "ZOOM_2", damage=_deadly(ascension, 14, 16), hits=1, round_mod=(4, 1)),
        "ZOOM_2": Move(frozenset({"attack"}), "INERTIA", damage=_deadly(ascension, 14, 16), hits=1, round_mod=(4, 2)),
        "INERTIA": Move(frozenset({"attack", "buff"}), "PIERCING_STABS", damage=_deadly(ascension, 9, 11), hits=1,
                        self_status=((StatusId.STRENGTH, _deadly(ascension, 2, 4)),)),
        "PIERCING_STABS": Move(frozenset({"attack"}), "ZOOM", damage=_deadly(ascension, 7, 8), hits=2),
    }


def _steal(enemy, combat):
    """ThieveryPower.Steal: gold off the player, up to the amount, remembered for the gremlin that carries it off."""
    thievery = enemy.status.get(StatusId.THIEVERY)
    player = combat.combat_state.player
    if thievery is None or player.gold <= 0:
        return
    taken = min(thievery.amount, player.gold)
    player.gold -= taken
    if not thievery.records:
        thievery.records = [[thievery.amount, 0]]
    thievery.records[0][1] += taken


def gremlin_merc(ascension : int) -> MoveTable:
    # its damage rises with Tough Enemies (the game's own choice), and Deadly Enemies changes nothing
    return {
        "GIMME": Move(frozenset({"attack"}), "DOUBLE_SMASH", damage=_tough(ascension, 7, 8), hits=2, effect=_steal),
        "DOUBLE_SMASH": Move(frozenset({"attack", "debuff"}), "HEHE", damage=_tough(ascension, 6, 7), hits=2,
                             player_status=((StatusId.WEAK, 2),), effect=_steal),
        "HEHE": Move(frozenset({"attack", "buff"}), "GIMME", damage=_tough(ascension, 8, 9), hits=1,
                     self_status=((StatusId.STRENGTH, 2),), effect=_steal),
    }


def fat_gremlin(ascension : int) -> MoveTable:
    return {
        "SPAWNED": Move(frozenset({"stun"}), "FLEE"),
        "FLEE": Move(frozenset({"escape"}), "FLEE", effect=_escape),
    }


def sneaky_gremlin(ascension : int) -> MoveTable:
    return {
        "SPAWNED": Move(frozenset({"stun"}), "TACKLE"),
        "TACKLE": Move(frozenset({"attack"}), "TACKLE", damage=_deadly(ascension, 9, 10), hits=1),
    }


BOMB_SLOTS = 5


def _bloat(enemy, combat):
    """The Living Fog's Bloat: a Gas Bomb in the first free place (bomb1 to bomb5), left of the fog."""
    from sts2_lite.enemy import Enemy
    cs = combat.combat_state
    bombs = [e for e in cs.enemies if e.enemy_id.startswith("GAS_BOMB")]
    used = {b.slot for b in bombs}
    free = next((s for s in range(BOMB_SLOTS) if s not in used), None)
    if free is None:
        return
    combat.summon(Enemy.spawn("GAS_BOMB", free, cs.ascension), at=sum(1 for b in bombs if b.slot < free))


def living_fog(ascension : int) -> MoveTable:
    return {
        "ADVANCED_GAS": Move(frozenset({"attack", "carddebuff"}), "BLOAT", damage=_deadly(ascension, 8, 9), hits=1,
                             player_status=((StatusId.SMOGGY, 1),)),
        "BLOAT": Move(frozenset({"attack", "summon"}), "SUPER_GAS_BLAST", damage=_deadly(ascension, 5, 6), hits=1, effect=_bloat),
        "SUPER_GAS_BLAST": Move(frozenset({"attack"}), "BLOAT", damage=_deadly(ascension, 8, 9), hits=1),
    }


def _explode(enemy, combat):
    enemy.current_hp = 0        # CreatureCmd.Kill after the blast


def gas_bomb(ascension : int) -> MoveTable:
    return {"EXPLODE": Move(frozenset({"deathblow"}), "EXPLODE", damage=_deadly(ascension, 8, 9), hits=1, effect=_explode)}


RAT_BACKUP_LIMIT = 3
RAT_SLOTS = 5


def _rat_parts(rat) -> tuple[int, int, int]:
    """The rat's memory lives in its counter: moves made so far (up to 2), turns of Screech cooldown left (up to 3),
    and the backups called in this fight (shared by all rats)."""
    return rat.counter % 3, (rat.counter // 3) % 4, rat.counter // 12


def rat_counter(acts : int, cooldown : int, backups : int) -> int:
    return min(acts, 2) + 3 * cooldown + 12 * backups


def _rat_act(rat, screech : bool = False, acted : bool = True):
    acts, cooldown, backups = _rat_parts(rat)
    rat.counter = rat_counter(acts + (1 if acted else 0), 3 if screech else max(0, cooldown - 1), backups)


def _can_call(rat, combat) -> bool:
    acts, _, backups = _rat_parts(rat)
    if acts < 2 or backups >= RAT_BACKUP_LIMIT:
        return False
    if combat is None:
        return True
    rats = [e for e in combat.combat_state.enemies if e.enemy_id.startswith("TWO_TAILED_RAT")]
    return len(rats) < RAT_SLOTS and not any(r is not rat and r.move_id == "CALL_FOR_BACKUP" for r in rats)


def _rat_next(rat, combat) -> str:
    _, cooldown, _ = _rat_parts(rat)
    can = _can_call(rat, combat)
    weight = 1 / 12 if can else 1.0
    options = [(m, weight) for m, ok in (("SCRATCH", rat.move_id != "SCRATCH"), ("DISEASE_BITE", rat.move_id != "DISEASE_BITE"),
                                         ("SCREECH", cooldown == 0)) if ok]
    if can and "CALL_FOR_BACKUP" not in rat.used_moves:
        options.append(("CALL_FOR_BACKUP", 0.75))
    return rng.choices([m for m, _ in options], weights=[w for _, w in options])[0]


def _call_for_backup(rat, combat):
    from sts2_lite.enemy import Enemy
    cs = combat.combat_state
    rats = [e for e in cs.enemies if e.enemy_id.startswith("TWO_TAILED_RAT")]
    if len(rats) < RAT_SLOTS:
        new = Enemy.spawn("TWO_TAILED_RAT", max([r.slot for r in rats], default=-1) + 1, cs.ascension)
        first = rng.choice(["SCRATCH", "DISEASE_BITE", "SCREECH"])      # a new rat rolls its first move like any other turn
        new.move_id = first
        new.attack_damage = new._move_damage(new.moves[first])
        new.num_attacks = new._move_hits(new.moves[first])
        combat.summon(new, at=0)
        rats.append(new)
    backups = max(_rat_parts(r)[2] for r in rats) + 1
    for r in rats:
        acts, cooldown, _ = _rat_parts(r)
        r.counter = rat_counter(acts, cooldown, backups)
    _rat_act(rat, acted=False)


def two_tailed_rat(ascension : int) -> MoveTable:
    return {
        "SCRATCH": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 8, 9), hits=1, choose=_rat_next,
                        effect=lambda rat, combat: _rat_act(rat)),
        "DISEASE_BITE": Move(frozenset({"attack"}), "", damage=_deadly(ascension, 6, 7), hits=1, choose=_rat_next,
                             effect=lambda rat, combat: _rat_act(rat)),
        "SCREECH": Move(frozenset({"debuff"}), "", player_status=((StatusId.FRAIL, 1),), choose=_rat_next,
                        effect=lambda rat, combat: _rat_act(rat, screech=True)),
        "CALL_FOR_BACKUP": Move(frozenset({"summon"}), "", choose=_rat_next, effect=_call_for_backup),
    }


def terror_eel(ascension : int) -> MoveTable:
    # Shriek (70, or 75 on Tough Enemies) stuns it into TERROR the first time a hit leaves it at or below that
    return {
        "CRASH": Move(frozenset({"attack"}), "THRASH", damage=_deadly(ascension, 16, 18), hits=1),
        "THRASH": Move(frozenset({"attack", "buff"}), "CRASH", damage=_deadly(ascension, 3, 4), hits=3,
                       self_status=((StatusId.VIGOR, 6),)),
        "TERROR": Move(frozenset({"debuff"}), "CRASH", player_status=((StatusId.VULNERABLE, 99),)),
    }


def phantasmal_gardener(ascension : int) -> MoveTable:
    # four gardeners start on different moves (by place) and then go round in the same order; Skittish comes with them
    return {
        "BITE": Move(frozenset({"attack"}), "LASH", damage=5, hits=1),
        "LASH": Move(frozenset({"attack"}), "FLAIL", damage=7, hits=1),
        "FLAIL": Move(frozenset({"attack"}), "ENLARGE", damage=1, hits=3),
        "ENLARGE": Move(frozenset({"buff"}), "BITE", self_status=((StatusId.STRENGTH, _deadly(ascension, 2, 3)),)),
    }


def lagavulin_matriarch(ascension : int) -> MoveTable:
    # asleep (Plating 12, Asleep 3) until the sleep runs out or a hit gets through; then it goes round the four attacks
    # the next move is picked before this turn's sleep counts down, so it stops on the turn after the last Asleep tick (captures: 3 SLEEP turns)
    wake = lambda e, c: "SLEEP" if StatusId.ASLEEP in e.status and e.status[StatusId.ASLEEP].amount > 1 else "SLASH"
    return {
        "SLEEP": Move(frozenset({"sleep"}), "", choose=wake),
        "SLASH": Move(frozenset({"attack"}), "DISEMBOWEL", damage=_deadly(ascension, 19, 21), hits=1),
        "DISEMBOWEL": Move(frozenset({"attack"}), "SLASH2", damage=_deadly(ascension, 9, 10), hits=2),
        "SLASH2": Move(frozenset({"attack", "defend"}), "SOUL_SIPHON", damage=_deadly(ascension, 12, 14), hits=1,
                       block=_tough(ascension, 12, 14)),
        "SOUL_SIPHON": Move(frozenset({"debuff", "buff"}), "SLASH", player_status=((StatusId.STRENGTH, -2), (StatusId.DEXTERITY, -2)),
                            self_status=((StatusId.STRENGTH, 2),)),
    }


def soul_fysh(ascension : int) -> MoveTable:
    return {
        "BECKON": Move(frozenset({"statuscard"}), "DE_GAS", draw_cards=((CardId.BECKON, 1),), cards=((CardId.BECKON, 1),)),
        "DE_GAS": Move(frozenset({"attack"}), "GAZE", damage=_deadly(ascension, 16, 17), hits=1),
        "GAZE": Move(frozenset({"attack", "statuscard"}), "FADE", damage=_deadly(ascension, 7, 8), hits=1, cards=((CardId.BECKON, 1),)),
        "FADE": Move(frozenset({"buff"}), "SCREAM", self_status=((StatusId.INTANGIBLE, 2),)),
        "SCREAM": Move(frozenset({"attack", "debuff"}), "BECKON", damage=_deadly(ascension, 13, 15), hits=1,
                       player_status=((StatusId.VULNERABLE, 3),)),
    }


STEAM_PER_MOVE = 3
PRESSURE_GUN_STEP = 5


def _gun_fired(giant, combat):
    giant.counter += 1


def _about_to_blow(giant, combat):
    """AboutToBlowMove: the steam it built is what the eruption will do, and the Steam Eruption power is gone."""
    steam = giant.status.pop(StatusId.STEAM_ERUPTION, None)
    giant.counter = steam.amount if steam is not None else 0


def _blow(giant, combat):
    giant.current_hp = 0


def waterfall_giant(ascension : int) -> MoveTable:
    steam = ((StatusId.STEAM_ERUPTION, STEAM_PER_MOVE),)
    return {
        "PRESSURIZE": Move(frozenset({"buff"}), "STOMP", self_status=((StatusId.STEAM_ERUPTION, _deadly(ascension, 15, 20)),)),
        "STOMP": Move(frozenset({"attack", "debuff", "buff"}), "RAM", damage=_deadly(ascension, 15, 16), hits=1,
                      player_status=((StatusId.WEAK, 1),), self_status=steam),
        "RAM": Move(frozenset({"attack", "buff"}), "SIPHON", damage=_deadly(ascension, 10, 11), hits=1, self_status=steam),
        "SIPHON": Move(frozenset({"heal", "buff"}), "PRESSURE_GUN", heal=_tough(ascension, 10, 15), self_status=steam),
        "PRESSURE_GUN": Move(frozenset({"attack", "buff"}), "PRESSURE_UP", damage=_deadly(ascension, 20, 23), hits=1, self_status=steam,
                             extra_damage=lambda e: PRESSURE_GUN_STEP * e.counter, effect=_gun_fired),
        "PRESSURE_UP": Move(frozenset({"attack", "buff"}), "STOMP", damage=_deadly(ascension, 13, 14), hits=1, self_status=steam),
        "ABOUT_TO_BLOW": Move(frozenset({"stun"}), "EXPLODE", effect=_about_to_blow),
        "EXPLODE": Move(frozenset({"deathblow"}), "EXPLODE", damage=0, hits=1, extra_damage=lambda e: e.counter, effect=_blow),
    }


MOVE_TABLES = {
    "PHANTASMAL_GARDENER": phantasmal_gardener,
    "LAGAVULIN_MATRIARCH": lagavulin_matriarch,
    "SOUL_FYSH": soul_fysh,
    "WATERFALL_GIANT": waterfall_giant,
    "GREMLIN_MERC": gremlin_merc,
    "FAT_GREMLIN": fat_gremlin,
    "SNEAKY_GREMLIN": sneaky_gremlin,
    "LIVING_FOG": living_fog,
    "GAS_BOMB": gas_bomb,
    "TWO_TAILED_RAT": two_tailed_rat,
    "TERROR_EEL": terror_eel,
    "CALCIFIED_CULTIST": calcified_cultist,
    "DAMP_CULTIST": damp_cultist,
    "CORPSE_SLUG": corpse_slug,
    "SEWER_CLAM": sewer_clam,
    "SLUDGE_SPINNER": sludge_spinner,
    "SEAPUNK": seapunk,
    "FOSSIL_STALKER": fossil_stalker,
    "TOADPOLE": toadpole,
    "HAUNTED_SHIP": haunted_ship,
    "SKULKING_COLONY": skulking_colony,
    "KNOWLEDGE_DEMON": knowledge_demon,
    "QUEEN": queen,
    "TORCH_HEAD_AMALGAM": torch_head_amalgam,
    "TEST_SUBJECT": test_subject,
    "AEONGLASS": aeonglass,
    **{segment: decimillipede_segment for segment in SEGMENTS},
    "CRUSHER": crusher,
    "ROCKET": rocket,
    "NIBBIT": nibbit,
    "SHRINKER_BEETLE": shrinker_beetle,
    "FUZZY_WURM_CRAWLER": fuzzy_wurm_crawler,
    "LEAF_SLIME_S": leaf_slime_s,
    "TWIG_SLIME_S": twig_slime_s,
    "LEAF_SLIME_M": leaf_slime_m,
    "TWIG_SLIME_M": twig_slime_m,
    "BYRDONIS": byrdonis,
    "BYGONE_EFFIGY": bygone_effigy,
    "PHROG_PARASITE": phrog_parasite,
    "MAWLER": mawler,
    "VINE_SHAMBLER": vine_shambler,
    "SNAPPING_JAXFRUIT": snapping_jaxfruit,
    "FLYCONID": flyconid,
    "SLITHERING_STRANGLER": slithering_strangler,
    "INKLET": inklet,
    "CUBEX_CONSTRUCT": cubex_construct,
    "ASSASSIN_RUBY_RAIDER": assassin_ruby_raider,
    "AXE_RUBY_RAIDER": axe_ruby_raider,
    "BRUTE_RUBY_RAIDER": brute_ruby_raider,
    "CROSSBOW_RUBY_RAIDER": crossbow_ruby_raider,
    "TRACKER_RUBY_RAIDER": tracker_ruby_raider,
    "FOGMOG": fogmog,
    "EYE_WITH_TEETH": eye_with_teeth,
    "WRIGGLER": wriggler,
    "VANTOM": vantom,
    "CEREMONIAL_BEAST": ceremonial_beast,
    "KIN_FOLLOWER": kin_follower,
    "KIN_PRIEST": kin_priest,
    "BOWLBUG_EGG": bowlbug_egg,
    "BOWLBUG_NECTAR": bowlbug_nectar,
    "BOWLBUG_SILK": bowlbug_silk,
    "BOWLBUG_ROCK": bowlbug_rock,
    "CHOMPER": chomper,
    "SPINY_TOAD": spiny_toad,
    "MYTE": myte,
    "PARAFRIGHT": parafright,
    "THE_OBSCURA": the_obscura,
    "EXOSKELETON": exoskeleton,
    "HUNTER_KILLER": hunter_killer,
    "ENTOMANCER": entomancer,
    "INFESTED_PRISM": infested_prism,
    "LOUSE_PROGENITOR": louse_progenitor,
    "TUNNELER": tunneler,
    "SLUMBERING_BEETLE": slumbering_beetle,
    "OVICOPTER": ovicopter,
    "TOUGH_EGG": tough_egg,
    "THIEVING_HOPPER": thieving_hopper,
    "THE_INSATIABLE": the_insatiable,
    "AXEBOT": axebot,
    "PUNCH_CONSTRUCT": punch_construct,
    "GLOBE_HEAD": globe_head,
    "SCROLL_OF_BITING": scroll_of_biting,
    "SLIMED_BERSERKER": slimed_berserker,
    "FROG_KNIGHT": frog_knight,
    "THE_LOST": the_lost,
    "THE_FORGOTTEN": the_forgotten,
    "LIVING_SHIELD": living_shield,
    "TURRET_OPERATOR": turret_operator,
    "DEVOTED_SCULPTOR": devoted_sculptor,
    "OWL_MAGISTRATE": owl_magistrate,
    "FABRICATOR": fabricator,
    "ZAPBOT": zapbot,
    "STABBOT": stabbot,
    "GUARDBOT": guardbot,
    "NOISEBOT": noisebot,
    "SOUL_NEXUS": soul_nexus,
    "MECHA_KNIGHT": mecha_knight,
    "FLAIL_KNIGHT": flail_knight,
    "SPECTRAL_KNIGHT": spectral_knight,
    "MAGI_KNIGHT": magi_knight,
}


# The game's move state ids differ from the table keys: "<KEY>_MOVE" in most cases, and these exceptions.
# monster -> {game id: table key}
GAME_MOVE_ALIASES = {
    "GREMLIN_MERC": {"DOUBLE_SMASH_MOVE": "DOUBLE_SMASH"},
    "SKULKING_COLONY": {"ZOOM_MOVE_2": "ZOOM_2"},
    "SHRINKER_BEETLE": {"SHRINKER_MOVE": "SHRINK"},
    "FUZZY_WURM_CRAWLER": {"FIRST_ACID_GOOP": "FIRST_GOOP", "ACID_GOOP": "GOOP"},
    "LEAF_SLIME_S": {"TACKLE_MOVE": "BUTT"},
    "TWIG_SLIME_S": {"TACKLE_MOVE": "BUTT"},
    "TWIG_SLIME_M": {"POKEY_POUNCE_MOVE": "CLUMP_SHOT"},
    "BYGONE_EFFIGY": {"SLASHES_MOVE": "SLASH"},
    "WRIGGLER": {"NASTY_BITE_MOVE": "BITE"},
    "CUBEX_CONSTRUCT": {"REPEATER_BLAST_MOVE_2": "REPEATER_BLAST_2"},
    "THE_INSATIABLE": {"THRASH_MOVE_2": "THRASH_2"},
    "THE_OBSCURA": {"SAIL_MOVE": "WAIL"},       # the game's own spelling
    "TURRET_OPERATOR": {"UNLOAD_MOVE_2": "UNLOAD_2"},
    "FLAIL_KNIGHT": {"FLAIL_MOVE": "FLAIL", "RAM_MOVE": "RAM"},
    "MAGI_KNIGHT": {"RAM_MOVE": "RAM"},
}


def table_move_id(monster : str, game_id : str, table : MoveTable) -> str | None:
    """The table key for a move state id from the bridge (`move_id`), or None when the table has no such move."""
    alias = GAME_MOVE_ALIASES.get(monster, {}).get(game_id)
    if alias in table:
        return alias
    if game_id in table:
        return game_id
    if game_id.endswith("_MOVE") and game_id[:-5] in table:
        return game_id[:-5]
    return None
