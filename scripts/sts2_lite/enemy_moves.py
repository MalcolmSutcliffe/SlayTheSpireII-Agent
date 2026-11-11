"""Enemy move tables. A move table maps move id -> Move; each move names its follow-up."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sts2_lite import rng
from sts2_lite.card import CARD_RARITY, CardId, CardRarity, EnchantmentId
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
    "WRIGGLER": (17, 21, 18, 22),
    "EYE_WITH_TEETH": (6, 6, 6, 6),
    "PARAFRIGHT": (21, 21, 21, 21),
    "TOUGH_EGG": (14, 18, 15, 19),
}

# the move a summoned monster starts on (default SPAWNED) and the statuses it starts with
SPAWN_MOVE = {"EYE_WITH_TEETH": "DISTRACT", "PARAFRIGHT": "SLAM", "TOUGH_EGG": "HATCH"}
SPAWN_STATUS = {"EYE_WITH_TEETH": ((StatusId.ILLUSION, 1), (StatusId.MINION, 1)),
                "PARAFRIGHT": ((StatusId.ILLUSION, 1), (StatusId.MINION, 1)),
                "TOUGH_EGG": ((StatusId.HATCH, 2), (StatusId.MINION, 1))}      # laid during the enemy turn, so it counts down from 2

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


MOVE_TABLES = {
    "KNOWLEDGE_DEMON": knowledge_demon,
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
}


# The game's move state ids differ from the table keys: "<KEY>_MOVE" in most cases, and these exceptions.
# monster -> {game id: table key}
GAME_MOVE_ALIASES = {
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
