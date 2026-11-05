"""Enemy move tables. A move table maps move id -> Move; each move names its follow-up."""
from __future__ import annotations

from dataclasses import dataclass

from sts2_lite.card import CardId
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


# monsters that appear mid-fight: (min hp, max hp, tough min hp, tough max hp)
SPAWN_HP = {
    "WRIGGLER": (17, 21, 18, 22),
    "EYE_WITH_TEETH": (6, 6, 6, 6),
}

# the move a summoned monster starts on (default SPAWNED) and the statuses it starts with
SPAWN_MOVE = {"EYE_WITH_TEETH": "DISTRACT"}
SPAWN_STATUS = {"EYE_WITH_TEETH": ((StatusId.ILLUSION, 1), (StatusId.MINION, 1))}

# summoner -> (summoning move, summoned monster, slot): the monster is missing from a bridge
# state when it has been killed, and returns at the end of the enemy turn
SUMMONS = {"FOGMOG": ("ILLUSION", "EYE_WITH_TEETH", 0)}


MOVE_TABLES = {
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
}
