"""Move tables of the Act 1 Overgrowth enemies."""
from __future__ import annotations

from sts2_lite.card import CardId
from sts2_lite.status import StatusId
from sts2_lite.enemy_moves.core import Branch, Move, MoveTable, deadly, tough


def nibbit(ascension : int) -> MoveTable:
    return {
        "BUTT": Move(frozenset({"attack"}), "SLICE",
                     damage=deadly(ascension, 12, 13), hits=1),
        "SLICE": Move(frozenset({"attack", "defend"}), "HISS",
                      damage=deadly(ascension, 6, 7), hits=1, block=tough(ascension, 5, 6)),
        "HISS": Move(frozenset({"buff"}), "BUTT",
                     self_status=((StatusId.STRENGTH, deadly(ascension, 2, 3)),)),
    }


def shrinker_beetle(ascension : int) -> MoveTable:
    return {
        "SHRINK": Move(frozenset({"debuffstrong"}), "CHOMP",
                       player_status=((StatusId.SHRINK, -1),)),
        "CHOMP": Move(frozenset({"attack"}), "STOMP",
                      damage=deadly(ascension, 7, 8), hits=1),
        "STOMP": Move(frozenset({"attack"}), "CHOMP",
                      damage=deadly(ascension, 13, 14), hits=1),
    }


def fuzzy_wurm_crawler(ascension : int) -> MoveTable:
    # goop, inhale, goop, goop, inhale, ...; both goops look the same, so rounds tell them apart
    return {
        "FIRST_GOOP": Move(frozenset({"attack"}), "INHALE",
                           damage=deadly(ascension, 4, 6), hits=1, round_mod=(3, 1)),
        "INHALE": Move(frozenset({"buff"}), "GOOP",
                       self_status=((StatusId.STRENGTH, 7),)),
        "GOOP": Move(frozenset({"attack"}), "FIRST_GOOP",
                     damage=deadly(ascension, 4, 6), hits=1, round_mod=(3, 0)),
    }


def leaf_slime_s(ascension : int) -> MoveTable:
    return {
        "BUTT": Move(frozenset({"attack"}), "GOOP",
                     damage=deadly(ascension, 3, 4), hits=1),
        "GOOP": Move(frozenset({"statuscard"}), "BUTT", cards=((CardId.SLIMED, 1),)),
    }


def twig_slime_s(ascension : int) -> MoveTable:
    return {
        "BUTT": Move(frozenset({"attack"}), "BUTT",
                     damage=deadly(ascension, 4, 5), hits=1),
    }


def leaf_slime_m(ascension : int) -> MoveTable:
    return {
        "STICKY_SHOT": Move(frozenset({"statuscard"}), "CLUMP_SHOT", cards=((CardId.SLIMED, 2),)),
        "CLUMP_SHOT": Move(frozenset({"attack"}), "STICKY_SHOT",
                           damage=deadly(ascension, 8, 9), hits=1),
    }


def twig_slime_m(ascension : int) -> MoveTable:
    follow = (Branch("CLUMP_SHOT", max_streak=2), Branch("STICKY_SHOT"))
    return {
        "STICKY_SHOT": Move(frozenset({"statuscard"}), "", cards=((CardId.SLIMED, 1),), branches=follow),
        "CLUMP_SHOT": Move(frozenset({"attack"}), "",
                           damage=deadly(ascension, 11, 12), hits=1, branches=follow),
    }


def byrdonis(ascension : int) -> MoveTable:
    return {
        "SWOOP": Move(frozenset({"attack"}), "PECK",
                      damage=deadly(ascension, 17, 19), hits=1),
        "PECK": Move(frozenset({"attack"}), "SWOOP",
                     damage=deadly(ascension, 3, 4), hits=3),
    }


def bygone_effigy(ascension : int) -> MoveTable:
    return {
        "SLEEP": Move(frozenset({"sleep"}), "WAKE"),
        "WAKE": Move(frozenset({"buff"}), "SLASH",
                     self_status=((StatusId.STRENGTH, 10),)),
        "SLASH": Move(frozenset({"attack"}), "SLASH",
                      damage=deadly(ascension, 13, 15), hits=1),
    }


def phrog_parasite(ascension : int) -> MoveTable:
    return {
        "INFECT": Move(frozenset({"statuscard"}), "LASH", cards=((CardId.INFECTION, 3),)),
        "LASH": Move(frozenset({"attack"}), "INFECT",
                     damage=deadly(ascension, 4, 5), hits=4),
    }


def wriggler(ascension : int) -> MoveTable:
    # slots 0 and 2 open with a bite, slots 1 and 3 with a wriggle
    return {
        "SPAWNED": Move(frozenset({"stun"}), "", next_by_slot=("BITE", "WRIGGLE", "BITE", "WRIGGLE")),
        "BITE": Move(frozenset({"attack"}), "WRIGGLE",
                     damage=deadly(ascension, 6, 7), hits=1),
        "WRIGGLE": Move(frozenset({"buff", "statuscard"}), "BITE",
                        cards=((CardId.INFECTION, 1),), self_status=((StatusId.STRENGTH, 2),)),
    }


def mawler(ascension : int) -> MoveTable:
    follow = (Branch("RIP_AND_TEAR"), Branch("ROAR", once=True), Branch("CLAW"))
    return {
        "RIP_AND_TEAR": Move(frozenset({"attack"}), "",
                             damage=deadly(ascension, 14, 16), hits=1, branches=follow),
        "ROAR": Move(frozenset({"debuff"}), "",
                     player_status=((StatusId.VULNERABLE, 3),), branches=follow),
        "CLAW": Move(frozenset({"attack"}), "",
                     damage=deadly(ascension, 4, 5), hits=2, branches=follow),
    }


def vine_shambler(ascension : int) -> MoveTable:
    return {
        "SWIPE": Move(frozenset({"attack"}), "GRASPING_VINES",
                      damage=deadly(ascension, 6, 7), hits=2),
        "GRASPING_VINES": Move(frozenset({"attack", "carddebuff"}), "CHOMP",
                               damage=deadly(ascension, 8, 9), hits=1,
                               player_status=((StatusId.TANGLED, 1),)),
        "CHOMP": Move(frozenset({"attack"}), "SWIPE",
                      damage=deadly(ascension, 16, 18), hits=1),
    }


def snapping_jaxfruit(ascension : int) -> MoveTable:
    return {
        "ENERGY_ORB": Move(frozenset({"attack", "buff"}), "ENERGY_ORB",
                           damage=deadly(ascension, 3, 4), hits=1,
                           self_status=((StatusId.STRENGTH, 2),)),
    }


def flyconid(ascension : int) -> MoveTable:
    follow = (Branch("VULNERABLE_SPORES", weight=3), Branch("FRAIL_SPORES", weight=2), Branch("SMASH"))
    return {
        "VULNERABLE_SPORES": Move(frozenset({"debuff"}), "",
                                  player_status=((StatusId.VULNERABLE, 2),), branches=follow),
        "FRAIL_SPORES": Move(frozenset({"attack", "debuff"}), "",
                             damage=deadly(ascension, 8, 9), hits=1,
                             player_status=((StatusId.FRAIL, 2),), branches=follow),
        "SMASH": Move(frozenset({"attack"}), "",
                      damage=deadly(ascension, 11, 12), hits=1, branches=follow),
    }


def slithering_strangler(ascension : int) -> MoveTable:
    after_constrict = (Branch("THWACK"), Branch("LASH"))
    return {
        "CONSTRICT": Move(frozenset({"debuff"}), "",
                          player_status=((StatusId.CONSTRICT, 3),), branches=after_constrict),
        "THWACK": Move(frozenset({"attack", "defend"}), "CONSTRICT",
                       damage=deadly(ascension, 7, 8), hits=1, block=5),
        "LASH": Move(frozenset({"attack"}), "CONSTRICT",
                     damage=deadly(ascension, 12, 13), hits=1),
    }


def inklet(ascension : int) -> MoveTable:
    # the middle inklet opens with a whirlwind; the bridge shows each one's current move
    return {
        "JAB": Move(frozenset({"attack"}), "",
                    damage=deadly(ascension, 3, 4), hits=1,
                    branches=(Branch("PIERCING_GAZE"), Branch("WHIRLWIND"))),
        "WHIRLWIND": Move(frozenset({"attack"}), "JAB",
                          damage=deadly(ascension, 2, 3), hits=3),
        "PIERCING_GAZE": Move(frozenset({"attack"}), "JAB",
                              damage=deadly(ascension, 10, 11), hits=1),
    }


def cubex_construct(ascension : int) -> MoveTable:
    # charge, blast, blast, expel, then blast, blast, expel...; the two blasts look alike,
    # so the round number tells them apart (the cycle starts on round 1)
    strength = ((StatusId.STRENGTH, 2),)
    return {
        "CHARGE_UP": Move(frozenset({"buff"}), "REPEATER_BLAST", self_status=strength),
        "REPEATER_BLAST": Move(frozenset({"attack", "buff"}), "REPEATER_BLAST_2",
                               damage=deadly(ascension, 7, 8), hits=1,
                               self_status=strength, round_mod=(3, 2)),
        "REPEATER_BLAST_2": Move(frozenset({"attack", "buff"}), "EXPEL",
                                 damage=deadly(ascension, 7, 8), hits=1,
                                 self_status=strength, round_mod=(3, 0)),
        "EXPEL": Move(frozenset({"attack"}), "REPEATER_BLAST",
                      damage=deadly(ascension, 5, 6), hits=2),
    }


def assassin_ruby_raider(ascension : int) -> MoveTable:
    return {
        "KILLSHOT": Move(frozenset({"attack"}), "KILLSHOT",
                         damage=deadly(ascension, 10, 11), hits=1),
    }


def axe_ruby_raider(ascension : int) -> MoveTable:
    # the two swings look alike, so the round number tells them apart (the cycle starts on round 1)
    swing = dict(intents=frozenset({"attack", "defend"}), damage=deadly(ascension, 5, 6), hits=1,
                 block=deadly(ascension, 5, 6))
    return {
        "SWING_1": Move(next_move="SWING_2", round_mod=(3, 1), **swing),
        "SWING_2": Move(next_move="BIG_SWING", round_mod=(3, 2), **swing),
        "BIG_SWING": Move(frozenset({"attack"}), "SWING_1",
                          damage=deadly(ascension, 12, 13), hits=1),
    }


def brute_ruby_raider(ascension : int) -> MoveTable:
    return {
        "BEAT": Move(frozenset({"attack"}), "ROAR",
                     damage=deadly(ascension, 7, 8), hits=1),
        "ROAR": Move(frozenset({"buff"}), "BEAT", self_status=((StatusId.STRENGTH, 3),)),
    }


def crossbow_ruby_raider(ascension : int) -> MoveTable:
    return {
        "RELOAD": Move(frozenset({"defend"}), "FIRE", block=3),
        "FIRE": Move(frozenset({"attack"}), "RELOAD",
                     damage=deadly(ascension, 14, 16), hits=1),
    }


def tracker_ruby_raider(ascension : int) -> MoveTable:
    return {
        "TRACK": Move(frozenset({"debuff"}), "HOUNDS", player_status=((StatusId.FRAIL, 2),)),
        "HOUNDS": Move(frozenset({"attack"}), "HOUNDS",
                       damage=1, hits=deadly(ascension, 8, 9)),
    }


def fogmog(ascension : int) -> MoveTable:
    swipe = dict(intents=frozenset({"attack", "buff"}), damage=deadly(ascension, 8, 9), hits=1,
                 self_status=((StatusId.STRENGTH, 1),))
    return {
        "ILLUSION": Move(frozenset({"summon"}), "SWIPE", summon=("EYE_WITH_TEETH", 0)),
        "SWIPE": Move(next_move="", branches=(Branch("SWIPE_RANDOM", weight=2), Branch("HEADBUTT", weight=3)),
                      **swipe),
        # the same swipe, reached from a random choice; it always leads to a headbutt
        "SWIPE_RANDOM": Move(next_move="HEADBUTT", from_bridge=False, **swipe),
        "HEADBUTT": Move(frozenset({"attack"}), "SWIPE",
                         damage=deadly(ascension, 14, 16), hits=1),
    }


def eye_with_teeth(ascension : int) -> MoveTable:
    return {
        "DISTRACT": Move(frozenset({"statuscard"}), "DISTRACT", cards=((CardId.DAZED, 3),)),
    }


def vantom(ascension : int) -> MoveTable:
    return {
        "INK_BLOT": Move(frozenset({"attack"}), "INKY_LANCE",
                         damage=deadly(ascension, 7, 8), hits=1),
        "INKY_LANCE": Move(frozenset({"attack"}), "DISMEMBER",
                           damage=deadly(ascension, 6, 7), hits=2),
        "DISMEMBER": Move(frozenset({"attack", "statuscard"}), "PREPARE",
                          damage=deadly(ascension, 26, 30), hits=1, cards=((CardId.WOUND, 3),)),
        "PREPARE": Move(frozenset({"buff"}), "INK_BLOT",
                        self_status=((StatusId.STRENGTH, 2),)),
    }


def ceremonial_beast(ascension : int) -> MoveTable:
    # Plow breaks once the beast is hit down to its amount; it is then stunned and starts phase two
    return {
        "STAMP": Move(frozenset({"buff"}), "PLOW",
                      self_status=((StatusId.PLOW, deadly(ascension, 150, 160)),)),
        "PLOW": Move(frozenset({"attack", "buff"}), "PLOW",
                     damage=deadly(ascension, 18, 20), hits=1, self_status=((StatusId.STRENGTH, 2),)),
        "STUN": Move(frozenset({"stun"}), "BEAST_CRY"),
        "BEAST_CRY": Move(frozenset({"debuff"}), "STOMP",
                          player_status=((StatusId.RINGING, 1),)),
        "STOMP": Move(frozenset({"attack"}), "CRUSH",
                      damage=deadly(ascension, 15, 17), hits=1),
        "CRUSH": Move(frozenset({"attack", "buff"}), "BEAST_CRY",
                      damage=deadly(ascension, 17, 19), hits=1,
                      self_status=((StatusId.STRENGTH, deadly(ascension, 3, 4)),)),
    }


def kin_follower(ascension : int) -> MoveTable:
    return {
        "QUICK_SLASH": Move(frozenset({"attack"}), "BOOMERANG", damage=5, hits=1),
        "BOOMERANG": Move(frozenset({"attack"}), "POWER_DANCE", damage=2, hits=2),
        "POWER_DANCE": Move(frozenset({"buff"}), "QUICK_SLASH",
                            self_status=((StatusId.STRENGTH, deadly(ascension, 2, 3)),)),
    }


def kin_priest(ascension : int) -> MoveTable:
    # a four round cycle starting on round 1
    orb = deadly(ascension, 8, 9)
    return {
        "ORB_OF_FRAILTY": Move(frozenset({"attack", "debuff"}), "ORB_OF_WEAKNESS", damage=orb, hits=1,
                               player_status=((StatusId.FRAIL, 1),), round_mod=(4, 1)),
        "ORB_OF_WEAKNESS": Move(frozenset({"attack", "debuff"}), "BEAM", damage=orb, hits=1,
                                player_status=((StatusId.WEAK, 1),), round_mod=(4, 2)),
        "BEAM": Move(frozenset({"attack"}), "RITUAL", damage=3, hits=3),
        "RITUAL": Move(frozenset({"buff"}), "ORB_OF_FRAILTY",
                       self_status=((StatusId.STRENGTH, deadly(ascension, 2, 3)),)),
    }


