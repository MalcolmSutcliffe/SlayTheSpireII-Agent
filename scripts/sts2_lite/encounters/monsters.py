"""Per-monster combat setup read from the game's monster classes: hit points, starting powers and how the first move is chosen.
Generated from the decompiled MonsterModel sources, then checked by hand. Monster ids are the game's class names in SNAKE_CASE.

hp:       (min, max, tough_min, tough_max); the game rolls a uniform integer in [min, max], and Tough Enemies (ascension 8) swaps in the tough pair
powers:   (status, who, kind, base, high): applied when the monster joins the room. `kind` is "const", "tough" (high from ascension 8) or "deadly" (high from ascension 9)
          `who` is "self" or "player" (Rocket puts Surrounded on the player)
opening:  how the first move is picked, resolved by `encounters.builder.opening_move`
            ("fixed", move)                        always that move
            ("flag", flag, if_true, if_false)      chosen by a flag the encounter sets on this monster
            ("idx", (a, b, c))                     chosen by the `starter_idx` the encounter gives it
            ("slot", {slot: move}, fallback)       chosen by the encounter slot name; the fallback is an opening of its own
            ("random", ((move, weight), ...))      weighted random branch
            ("nibbit",) ("rat",) ("wriggler",)     the few that need more than one flag
Moves are the game's state ids ("SCRATCH_MOVE"); the move table's own key is found with `table_move_id`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MonsterSetup:
    hp : tuple[int, int, int, int]
    powers : tuple[tuple[str, str, str, int, int], ...]
    opening : tuple


MONSTERS : dict[str, MonsterSetup] = {
    "AEONGLASS": MonsterSetup((512, 512, 535, 535), (('ARTIFACT', 'self', 'const', 3, 3),), ('fixed', 'EBB_MOVE')),
    "ARCHITECT": MonsterSetup((9999, 9999, 9999, 9999), (), ('fixed', 'NOTHING')),
    "ASSASSIN_RUBY_RAIDER": MonsterSetup((18, 23, 19, 24), (), ('fixed', 'KILLSHOT_MOVE')),
    "AXE_RUBY_RAIDER": MonsterSetup((20, 22, 21, 23), (), ('fixed', 'SWING_1')),
    "AXEBOT": MonsterSetup((70, 78, 76, 86), (('STOCK', 'self', 'const', 2, 2),), ('fixed', 'HAMMER_UPPERCUT_MOVE')),
    "BATTLE_FRIEND_V1": MonsterSetup((75, 75, 75, 75), (("BATTLEWORN_DUMMY_TIME_LIMIT", "self", "const", 3, 3),), ('fixed', 'NOTHING_MOVE')),
    "BATTLE_FRIEND_V2": MonsterSetup((150, 150, 150, 150), (("BATTLEWORN_DUMMY_TIME_LIMIT", "self", "const", 3, 3),), ('fixed', 'NOTHING_MOVE')),
    "BATTLE_FRIEND_V3": MonsterSetup((300, 300, 300, 300), (("BATTLEWORN_DUMMY_TIME_LIMIT", "self", "const", 3, 3),), ('fixed', 'NOTHING_MOVE')),
    "BOWLBUG_EGG": MonsterSetup((21, 22, 23, 24), (), ('fixed', 'BITE_MOVE')),
    "BOWLBUG_NECTAR": MonsterSetup((35, 38, 36, 39), (), ('fixed', 'THRASH_MOVE')),
    "BOWLBUG_ROCK": MonsterSetup((45, 48, 46, 49), (('IMBALANCED', 'self', 'const', 1, 1),), ('fixed', 'HEADBUTT_MOVE')),
    "BOWLBUG_SILK": MonsterSetup((40, 43, 41, 44), (), ('fixed', 'TOXIC_SPIT_MOVE')),
    "BRUTE_RUBY_RAIDER": MonsterSetup((30, 33, 31, 34), (), ('fixed', 'BEAT_MOVE')),
    "BYGONE_EFFIGY": MonsterSetup((127, 127, 132, 132), (('SLOW', 'self', 'const', 1, 1),), ('fixed', 'SLEEP_MOVE')),
    "BYRDONIS": MonsterSetup((81, 84, 90, 90), (('TERRITORIAL', 'self', 'const', 1, 1),), ('fixed', 'SWOOP_MOVE')),
    "CALCIFIED_CULTIST": MonsterSetup((38, 41, 39, 42), (), ('fixed', 'INCANTATION_MOVE')),
    "CEREMONIAL_BEAST": MonsterSetup((252, 252, 262, 262), (), ('fixed', 'STAMP_MOVE')),
    "CHOMPER": MonsterSetup((60, 64, 63, 67), (('ARTIFACT', 'self', 'const', 2, 2),), ('flag', 'screams_first', 'SCREECH_MOVE', 'CLAMP_MOVE')),
    "CORPSE_SLUG": MonsterSetup((25, 27, 27, 29), (('RAVENOUS', 'self', 'deadly', 4, 5),), ('idx', ('WHIP_SLAP_MOVE', 'GLOMP_MOVE', 'GOOP_MOVE'))),
    "CROSSBOW_RUBY_RAIDER": MonsterSetup((18, 21, 19, 22), (), ('fixed', 'RELOAD_MOVE')),
    "CRUSHER": MonsterSetup((209, 209, 219, 219), (('BACK_ATTACK_LEFT', 'self', 'const', 1, 1), ('CRAB_RAGE', 'self', 'const', 1, 1)), ('fixed', 'THRASH_MOVE')),
    "CUBEX_CONSTRUCT": MonsterSetup((65, 65, 70, 70), (('ARTIFACT', 'self', 'const', 1, 1),), ('fixed', 'CHARGE_UP_MOVE')),
    "DAMP_CULTIST": MonsterSetup((51, 53, 52, 54), (), ('fixed', 'INCANTATION_MOVE')),
    "DECIMILLIPEDE_SEGMENT_BACK": MonsterSetup((40, 46, 46, 52), (), ('idx', ('WRITHE_MOVE', 'BULK_MOVE', 'CONSTRICT_MOVE'))),
    "DECIMILLIPEDE_SEGMENT_FRONT": MonsterSetup((40, 46, 46, 52), (), ('idx', ('WRITHE_MOVE', 'BULK_MOVE', 'CONSTRICT_MOVE'))),
    "DECIMILLIPEDE_SEGMENT_MIDDLE": MonsterSetup((40, 46, 46, 52), (), ('idx', ('WRITHE_MOVE', 'BULK_MOVE', 'CONSTRICT_MOVE'))),
    "DEVOTED_SCULPTOR": MonsterSetup((162, 162, 172, 172), (), ('fixed', 'FORBIDDEN_INCANTATION_MOVE')),
    "ENTOMANCER": MonsterSetup((145, 145, 165, 165), (('PERSONAL_HIVE', 'self', 'const', 1, 1),), ('fixed', 'BEES_MOVE')),
    "EXOSKELETON": MonsterSetup((24, 28, 26, 30), (('HARD_TO_KILL', 'self', 'const', 9, 9),), ('slot', {'first': 'SKITTER_MOVE', 'second': 'MANDIBLES_MOVE', 'third': 'ENRAGE_MOVE'}, ('random', (('SKITTER_MOVE', 1), ('MANDIBLES_MOVE', 1))))),
    "EYE_WITH_TEETH": MonsterSetup((6, 6, 6, 6), (('ILLUSION', 'self', 'const', 1, 1),), ('fixed', 'DISTRACT_MOVE')),
    "FABRICATOR": MonsterSetup((150, 150, 155, 155), (), ('random', (('FABRICATE_MOVE', 1), ('FABRICATING_STRIKE_MOVE', 1)))),
    "FAKE_MERCHANT_MONSTER": MonsterSetup((165, 165, 175, 175), (), ('fixed', 'SWIPE_MOVE')),
    "FAT_GREMLIN": MonsterSetup((13, 17, 14, 18), (), ('fixed', 'SPAWNED_MOVE')),
    "FLAIL_KNIGHT": MonsterSetup((101, 101, 108, 108), (), ('fixed', 'RAM_MOVE')),
    "FLYCONID": MonsterSetup((47, 49, 51, 53), (), ('random', (('FRAIL_SPORES_MOVE', 1), ('SMASH_MOVE', 1)))),
    "FOGMOG": MonsterSetup((74, 74, 78, 78), (), ('fixed', 'ILLUSION_MOVE')),
    "FOSSIL_STALKER": MonsterSetup((51, 53, 54, 56), (('SUCK', 'self', 'const', 3, 3),), ('fixed', 'LATCH_MOVE')),
    "FROG_KNIGHT": MonsterSetup((191, 191, 199, 199), (('PLATING', 'self', 'tough', 15, 19),), ('fixed', 'TONGUE_LASH')),
    "FUZZY_WURM_CRAWLER": MonsterSetup((55, 57, 58, 59), (), ('fixed', 'FIRST_ACID_GOOP')),
    "GAS_BOMB": MonsterSetup((7, 7, 8, 8), (('MINION', 'self', 'const', 1, 1),), ('fixed', 'EXPLODE_MOVE')),
    "GLOBE_HEAD": MonsterSetup((148, 148, 158, 158), (('GALVANIC', 'self', 'deadly', 6, 8),), ('fixed', 'SHOCKING_SLAP')),
    "GREMLIN_MERC": MonsterSetup((47, 49, 51, 53), (('SURPRISE', 'self', 'const', 1, 1),), ('fixed', 'GIMME_MOVE')),
    "GUARDBOT": MonsterSetup((16, 20, 17, 21), (), ('fixed', 'GUARD_MOVE')),
    "HAUNTED_SHIP": MonsterSetup((63, 63, 67, 67), (), ('fixed', 'HAUNT_MOVE')),
    "HUNTER_KILLER": MonsterSetup((121, 121, 126, 126), (), ('fixed', 'TENDERIZING_GOOP_MOVE')),
    "INFESTED_PRISM": MonsterSetup((161, 161, 171, 171), (('VITAL_SPARK', 'self', 'deadly', 2, 3),), ('fixed', 'JAB_MOVE')),
    "INKLET": MonsterSetup((11, 17, 12, 18), (('SLIPPERY', 'self', 'const', 1, 1),), ('flag', 'middle', 'WHIRLWIND_MOVE', 'JAB_MOVE')),
    "KIN_FOLLOWER": MonsterSetup((58, 59, 62, 63), (('MINION', 'self', 'const', 1, 1),), ('flag', 'starts_with_dance', 'POWER_DANCE_MOVE', 'QUICK_SLASH_MOVE')),
    "KIN_PRIEST": MonsterSetup((190, 190, 199, 199), (), ('fixed', 'ORB_OF_FRAILTY_MOVE')),
    "KNOWLEDGE_DEMON": MonsterSetup((379, 379, 399, 399), (), ('fixed', 'CURSE_OF_KNOWLEDGE_MOVE')),
    "LAGAVULIN_MATRIARCH": MonsterSetup((222, 222, 233, 233), (('PLATING', 'self', 'const', 12, 12), ('ASLEEP', 'self', 'const', 3, 3)), ('fixed', 'SLEEP_MOVE')),
    "LEAF_SLIME_M": MonsterSetup((32, 35, 33, 36), (), ('fixed', 'STICKY_SHOT')),
    "LEAF_SLIME_S": MonsterSetup((11, 15, 12, 16), (), ('random', (('TACKLE_MOVE', 1), ('GOOP_MOVE', 1)))),
    "LIVING_FOG": MonsterSetup((80, 80, 82, 82), (), ('fixed', 'ADVANCED_GAS_MOVE')),
    "LIVING_SHIELD": MonsterSetup((55, 55, 65, 65), (('RAMPART', 'self', 'const', 25, 25),), ('fixed', 'SHIELD_SLAM_MOVE')),
    "LOUSE_PROGENITOR": MonsterSetup((134, 136, 138, 141), (('CURL_UP', 'self', 'tough', 14, 18),), ('fixed', 'WEB_CANNON_MOVE')),
    "MAGI_KNIGHT": MonsterSetup((82, 82, 89, 89), (), ('fixed', 'POWER_SHIELD_MOVE')),
    "MAWLER": MonsterSetup((72, 72, 76, 76), (), ('fixed', 'CLAW_MOVE')),
    "MECHA_KNIGHT": MonsterSetup((300, 300, 320, 320), (('ARTIFACT', 'self', 'const', 3, 3),), ('fixed', 'CHARGE_MOVE')),
    "MYSTERIOUS_KNIGHT": MonsterSetup((101, 101, 108, 108), (('STRENGTH', 'self', 'const', 6, 6), ('PLATING', 'self', 'const', 6, 6)), ('fixed', 'RAM_MOVE')),
    "MYTE": MonsterSetup((61, 67, 64, 69), (), ('slot', {'first': 'TOXIC_MOVE', 'second': 'SUCK_MOVE'}, None)),
    "NIBBIT": MonsterSetup((42, 46, 44, 48), (), ('nibbit',)),
    "NOISEBOT": MonsterSetup((18, 23, 19, 24), (), ('fixed', 'NOISE_MOVE')),
    "OVICOPTER": MonsterSetup((124, 130, 126, 132), (), ('fixed', 'LAY_EGGS_MOVE')),
    "OWL_MAGISTRATE": MonsterSetup((231, 231, 247, 247), (), ('fixed', 'MAGISTRATE_SCRUTINY')),
    "PARAFRIGHT": MonsterSetup((21, 21, 21, 21), (('ILLUSION', 'self', 'const', 1, 1),), ('fixed', 'SLAM_MOVE')),
    "PHANTASMAL_GARDENER": MonsterSetup((26, 31, 27, 32), (('SKITTISH', 'self', 'tough', 6, 7),), ('slot', {'first': 'FLAIL_MOVE', 'second': 'BITE_MOVE', 'third': 'LASH_MOVE', 'fourth': 'ENLARGE_MOVE'}, None)),
    "PHROG_PARASITE": MonsterSetup((61, 64, 66, 68), (('INFESTED', 'self', 'const', 4, 4),), ('fixed', 'INFECT_MOVE')),
    "PUNCH_CONSTRUCT": MonsterSetup((55, 55, 60, 60), (('ARTIFACT', 'self', 'const', 1, 1),), ('flag', 'starts_with_fast_punch', 'FAST_PUNCH_MOVE', 'READY_MOVE')),
    "QUEEN": MonsterSetup((400, 400, 419, 419), (), ('fixed', 'PUPPET_STRINGS_MOVE')),
    "ROCKET": MonsterSetup((199, 199, 209, 209), (('SURROUNDED', 'player', 'const', 1, 1), ('BACK_ATTACK_RIGHT', 'self', 'const', 1, 1), ('CRAB_RAGE', 'self', 'const', 1, 1)), ('fixed', 'TARGETING_RETICLE_MOVE')),
    "SCROLL_OF_BITING": MonsterSetup((30, 37, 33, 39), (('PAPER_CUTS', 'self', 'const', 2, 2),), ('idx', ('CHOMP', 'CHEW', 'MORE_TEETH'))),
    "SEAPUNK": MonsterSetup((44, 46, 47, 49), (), ('fixed', 'SEA_KICK_MOVE')),
    "SEWER_CLAM": MonsterSetup((56, 56, 58, 58), (('PLATING', 'self', 'tough', 8, 9),), ('fixed', 'JET_MOVE')),
    "SHRINKER_BEETLE": MonsterSetup((38, 40, 40, 42), (), ('fixed', 'SHRINKER_MOVE')),
    "SKULKING_COLONY": MonsterSetup((75, 75, 80, 80), (('HARDENED_SHELL', 'self', 'const', 20, 20),), ('fixed', 'ZOOM_MOVE')),
    "SLIMED_BERSERKER": MonsterSetup((261, 261, 281, 281), (), ('fixed', 'VOMIT_ICHOR_MOVE')),
    "SLITHERING_STRANGLER": MonsterSetup((53, 55, 54, 56), (), ('fixed', 'CONSTRICT')),
    "SLUDGE_SPINNER": MonsterSetup((37, 39, 41, 42), (), ('fixed', 'OIL_SPRAY_MOVE')),
    "SLUMBERING_BEETLE": MonsterSetup((86, 86, 89, 89), (('PLATING', 'self', 'tough', 15, 18), ('SLUMBER', 'self', 'const', 3, 3)), ('fixed', 'SNORE_MOVE')),
    "SNAPPING_JAXFRUIT": MonsterSetup((31, 33, 34, 36), (), ('fixed', 'ENERGY_ORB_MOVE')),
    "SNEAKY_GREMLIN": MonsterSetup((10, 14, 11, 15), (), ('fixed', 'SPAWNED_MOVE')),
    "SOUL_FYSH": MonsterSetup((211, 211, 221, 221), (), ('fixed', 'BECKON_MOVE')),
    "SOUL_NEXUS": MonsterSetup((234, 234, 254, 254), (), ('fixed', 'SOUL_BURN_MOVE')),
    "SPECTRAL_KNIGHT": MonsterSetup((93, 93, 97, 97), (), ('fixed', 'HEX')),
    "SPINY_TOAD": MonsterSetup((116, 119, 121, 124), (), ('fixed', 'PROTRUDING_SPIKES_MOVE')),
    "STABBOT": MonsterSetup((18, 23, 19, 24), (), ('fixed', 'STAB_MOVE')),
    "TERROR_EEL": MonsterSetup((140, 140, 150, 150), (('SHRIEK', 'self', 'tough', 70, 75),), ('fixed', 'CRASH_MOVE')),
    "TEST_SUBJECT": MonsterSetup((100, 100, 111, 111), (('ADAPTABLE', 'self', 'const', 1, 1), ('ENRAGE', 'self', 'deadly', 2, 3)), ('fixed', 'BITE_MOVE')),
    "THE_FORGOTTEN": MonsterSetup((106, 106, 111, 111), (('POSSESS_SPEED', 'self', 'const', 1, 1),), ('fixed', 'MIASMA')),
    "THE_INSATIABLE": MonsterSetup((321, 321, 341, 341), (), ('fixed', 'LIQUIFY_GROUND_MOVE')),
    "THE_LOST": MonsterSetup((93, 93, 99, 99), (('POSSESS_STRENGTH', 'self', 'const', 1, 1),), ('fixed', 'DEBILITATING_SMOG')),
    "THE_OBSCURA": MonsterSetup((123, 123, 129, 129), (), ('fixed', 'ILLUSION_MOVE')),
    "THIEVING_HOPPER": MonsterSetup((79, 79, 84, 84), (('ESCAPE_ARTIST', 'self', 'const', 5, 5),), ('fixed', 'THIEVERY_MOVE')),
    "TOADPOLE": MonsterSetup((21, 25, 22, 26), (), ('flag', 'is_front', 'SPIKEN_MOVE', 'WHIRL_MOVE')),
    "TORCH_HEAD_AMALGAM": MonsterSetup((199, 199, 211, 211), (('MINION', 'self', 'const', 1, 1),), ('fixed', 'STRONG_TACKLE_MOVE')),
    "TOUGH_EGG": MonsterSetup((14, 18, 15, 19), (('HATCH', 'self', 'const', 1, 1),), ('fixed', 'HATCH_MOVE')),
    "TRACKER_RUBY_RAIDER": MonsterSetup((21, 25, 22, 26), (), ('fixed', 'TRACK_MOVE')),
    "TUNNELER": MonsterSetup((87, 87, 92, 92), (), ('fixed', 'BITE_MOVE')),
    "TURRET_OPERATOR": MonsterSetup((41, 41, 51, 51), (), ('fixed', 'UNLOAD_MOVE')),
    "TWIG_SLIME_M": MonsterSetup((26, 28, 27, 29), (), ('fixed', 'STICKY_SHOT_MOVE')),
    "TWIG_SLIME_S": MonsterSetup((7, 11, 8, 12), (), ('fixed', 'TACKLE_MOVE')),
    "TWO_TAILED_RAT": MonsterSetup((17, 21, 18, 22), (), ('rat',)),
    "VANTOM": MonsterSetup((173, 173, 183, 183), (('SLIPPERY', 'self', 'tough', 8, 9),), ('fixed', 'INK_BLOT_MOVE')),
    "VINE_SHAMBLER": MonsterSetup((61, 61, 64, 64), (), ('fixed', 'SWIPE_MOVE')),
    "WATERFALL_GIANT": MonsterSetup((240, 240, 250, 250), (), ('fixed', 'PRESSURIZE_MOVE')),
    "WRIGGLER": MonsterSetup((17, 21, 18, 22), (), ('wriggler',)),
    "ZAPBOT": MonsterSetup((18, 23, 19, 24), (('HIGH_VOLTAGE', 'self', 'const', 2, 2),), ('fixed', 'ZAP')),
}
