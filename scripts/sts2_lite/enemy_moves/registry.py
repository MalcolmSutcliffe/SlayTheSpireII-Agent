"""Which move table belongs to which monster, and how a move state id from the game finds its table key."""
from __future__ import annotations

from sts2_lite.enemy_moves.core import MoveTable
from sts2_lite.enemy_moves.act1_overgrowth import assassin_ruby_raider, axe_ruby_raider, brute_ruby_raider, bygone_effigy, byrdonis, ceremonial_beast, crossbow_ruby_raider, cubex_construct, eye_with_teeth, flyconid, fogmog, fuzzy_wurm_crawler, inklet, kin_follower, kin_priest, leaf_slime_m, leaf_slime_s, mawler, nibbit, phrog_parasite, shrinker_beetle, slithering_strangler, snapping_jaxfruit, tracker_ruby_raider, twig_slime_m, twig_slime_s, vantom, vine_shambler, wriggler
from sts2_lite.enemy_moves.act2_hive import SEGMENTS, bowlbug_egg, bowlbug_nectar, bowlbug_rock, bowlbug_silk, chomper, crusher, decimillipede_segment, entomancer, exoskeleton, hunter_killer, infested_prism, knowledge_demon, louse_progenitor, myte, ovicopter, parafright, rocket, slumbering_beetle, spiny_toad, the_insatiable, the_obscura, thieving_hopper, tough_egg, tunneler
from sts2_lite.enemy_moves.act3_glory import aeonglass, axebot, devoted_sculptor, fabricator, flail_knight, frog_knight, globe_head, guardbot, living_shield, magi_knight, mecha_knight, noisebot, owl_magistrate, punch_construct, queen, scroll_of_biting, slimed_berserker, soul_nexus, spectral_knight, stabbot, test_subject, the_forgotten, the_lost, torch_head_amalgam, turret_operator, zapbot
from sts2_lite.enemy_moves.act1_underdocks import calcified_cultist, corpse_slug, damp_cultist, fat_gremlin, fossil_stalker, gas_bomb, gremlin_merc, haunted_ship, lagavulin_matriarch, living_fog, phantasmal_gardener, seapunk, sewer_clam, skulking_colony, sludge_spinner, sneaky_gremlin, soul_fysh, terror_eel, toadpole, two_tailed_rat, waterfall_giant


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

