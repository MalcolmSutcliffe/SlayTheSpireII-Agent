"""Every encounter in the game: its room type, tags, slots, gold and exact monster generation.
Generated from the decompiled EncounterModel classes, then the random ones were written by hand. Gating (unlocks) is ignored.

`rng` is any object with the `random.Random` methods; it is never the game's own generator."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Spawn:
    monster : str                   # SNAKE_CASE class name
    slot : str | None = None
    flags : dict = field(default_factory=dict)       # settable monster flags: screams_first, middle, is_front, is_alone, starts_with_dance, starts_with_fast_punch, starter_idx, starting_hp_reduction


@dataclass(frozen=True)
class Encounter:
    id : str
    room : str                      # "Monster", "Elite" or "Boss"
    weak : bool = False
    tags : tuple[str, ...] = ()
    slots : tuple[str, ...] = ()    # the encounter's slot names (empty: the monsters stand in order)
    gold : tuple[int, int] | None = None        # an encounter's own reward gold, otherwise by room type
    rewards : bool = True
    generate : Callable | None = None           # (rng) -> list[Spawn]; None: `fixed`
    fixed : tuple[Spawn, ...] = ()

    def monsters(self, rng, variant : int | None = None) -> list[Spawn]:
        """`variant` is an event's choice for an encounter that takes one (the Battleworn Dummy's setting)."""
        if self.generate is None:
            return list(self.fixed)
        return self.generate(rng) if variant is None else self.generate(rng, variant)

    def shares_tags_with(self, other : "Encounter | None") -> bool:
        return other is not None and bool(set(self.tags) & set(other.tags))


def S(monster : str, slot : str | None = None, **flags) -> Spawn:
    return Spawn(monster, slot, flags)


def _pick_distinct(rng, items, count):
    """`count` different items, each pick uniform among those left (the encounters' per-kind limit of one)."""
    left, picked = list(items), []
    for _ in range(count):
        item = rng.choice(left)
        left.remove(item)
        picked.append(item)
    return picked


def _consecutive_starts(rng, count, start=None):
    first = rng.randrange(3) if start is None else start
    return [(first + i) % 3 for i in range(count)]




def _battleworn_dummy(rng, setting : int = 1) -> list[Spawn]:
    return [S(f"BATTLE_FRIEND_V{setting}")]


def _bowlbugs_normal(rng) -> list[Spawn]:
    workers = _pick_distinct(rng, ("BOWLBUG_EGG", "BOWLBUG_SILK", "BOWLBUG_NECTAR"), 2)
    return [S("BOWLBUG_ROCK", "first"), S(workers[0], "middle"), S(workers[1], "last")]


def _bowlbugs_weak(rng) -> list[Spawn]:
    return [S("BOWLBUG_ROCK", "odd"), S(rng.choice(("BOWLBUG_EGG", "BOWLBUG_NECTAR")), "even")]


def _chompers(rng) -> list[Spawn]:
    return [S("CHOMPER"), S("CHOMPER", screams_first=True)]


def _corpse_slugs(count : int):
    def generate(rng) -> list[Spawn]:      # EnsureCorpseSlugsStartWithDifferentMoves: consecutive starting moves from a random one
        return [S("CORPSE_SLUG", starter_idx=i) for i in _consecutive_starts(rng, count)]
    return generate


def _decimillipede(rng) -> list[Spawn]:
    first = rng.randrange(3)
    return [S("DECIMILLIPEDE_SEGMENT_FRONT", "segment1", starter_idx=first),
            S("DECIMILLIPEDE_SEGMENT_MIDDLE", "segment2", starter_idx=(first + 1) % 3),
            S("DECIMILLIPEDE_SEGMENT_BACK", "segment3", starter_idx=(first + 2) % 3)]


def _dense_vegetation(rng) -> list[Spawn]:
    return [S("WRIGGLER", f"wriggler{i}", start_stunned=False) for i in range(1, 5)]


def _flyconid(rng) -> list[Spawn]:
    return [S(rng.choice(("LEAF_SLIME_M", "TWIG_SLIME_M"))), S("FLYCONID")]


def _inklets(rng) -> list[Spawn]:
    return [S("INKLET"), S("INKLET", middle=True), S("INKLET")]


def _nibbits_normal(rng) -> list[Spawn]:
    return [S("NIBBIT", "front", is_front=True), S("NIBBIT", "back")]


def _nibbits_weak(rng) -> list[Spawn]:
    return [S("NIBBIT", is_alone=True)]


def _punch_off(rng) -> list[Spawn]:
    return [S("PUNCH_CONSTRUCT", starts_with_fast_punch=True, starting_hp_reduction=rng.randrange(2, 10)),
            S("PUNCH_CONSTRUCT", starting_hp_reduction=rng.randrange(2, 10))]


def _ruby_raiders(rng) -> list[Spawn]:
    kinds = ("AXE_RUBY_RAIDER", "ASSASSIN_RUBY_RAIDER", "BRUTE_RUBY_RAIDER", "CROSSBOW_RUBY_RAIDER", "TRACKER_RUBY_RAIDER")
    return [S(kind) for kind in _pick_distinct(rng, kinds, 3)]


def _scrolls(last_fixed : bool):
    def generate(rng) -> list[Spawn]:
        first = rng.randrange(3)
        spawns = [S("SCROLL_OF_BITING", starter_idx=(first + i) % 3) for i in range(3)]
        if last_fixed:
            spawns.append(S("SCROLL_OF_BITING", starter_idx=2))
        return spawns
    return generate


def _slimes_normal(rng) -> list[Spawn]:
    leaf_first = rng.random() < 0.5
    small = ("LEAF_SLIME_S", "TWIG_SLIME_S") if leaf_first else ("TWIG_SLIME_S", "LEAF_SLIME_S")
    return [S("TWIG_SLIME_M"), S("LEAF_SLIME_M"), S(small[0]), S(small[1])]


def _slimes_weak(rng) -> list[Spawn]:
    first, second = _pick_distinct(rng, ("LEAF_SLIME_S", "TWIG_SLIME_S"), 2)
    return [S(first), S(rng.choice(("LEAF_SLIME_M", "TWIG_SLIME_M"))), S(second)]


def _slithering_strangler(rng) -> list[Spawn]:
    secondary = rng.choice(("SnappingJaxfruit", "MediumSlime", "SmallSlimes"))
    if secondary == "SnappingJaxfruit":
        monsters = ["SNAPPING_JAXFRUIT"]
    elif secondary == "MediumSlime":
        monsters = [rng.choice(("LEAF_SLIME_M", "TWIG_SLIME_M"))]
    else:
        monsters = [rng.choice(("LEAF_SLIME_S", "TWIG_SLIME_S")) for _ in range(2)]        # the two small slimes are drawn independently
    return [S(m) for m in monsters] + [S("SLITHERING_STRANGLER")]


def _the_kin(rng) -> list[Spawn]:
    return [S("KIN_FOLLOWER", "slot1", starts_with_dance=True), S("KIN_FOLLOWER", "slot2"), S("KIN_PRIEST", "leaderSlot")]


def _toadpoles(rng) -> list[Spawn]:
    return [S("TOADPOLE", is_front=True), S("TOADPOLE", is_front=False)]


def _tunneler(rng) -> list[Spawn]:
    return [S("CHOMPER", screams_first=True), S("TUNNELER")]


def _two_tailed_rats(rng) -> list[Spawn]:
    slots = ("third", "fourth", "fifth")
    return [S("TWO_TAILED_RAT", slot, starter_idx=i) for slot, i in zip(slots, _consecutive_starts(rng, 3))]



ENCOUNTERS : dict[str, Encounter] = {
    "AEONGLASS_BOSS": Encounter("AEONGLASS_BOSS", "Boss", fixed=(S("AEONGLASS"),)),
    "AXEBOTS_NORMAL": Encounter("AXEBOTS_NORMAL", "Monster", slots=('front',), fixed=(S("AXEBOT", "front"),)),
    "BATTLEWORN_DUMMY_EVENT_ENCOUNTER": Encounter("BATTLEWORN_DUMMY_EVENT_ENCOUNTER", "Monster", rewards=False, generate=_battleworn_dummy),
    "BOWLBUGS_NORMAL": Encounter("BOWLBUGS_NORMAL", "Monster", tags=('Workers',), generate=_bowlbugs_normal),
    "BOWLBUGS_WEAK": Encounter("BOWLBUGS_WEAK", "Monster", weak=True, tags=('Workers',), generate=_bowlbugs_weak),
    "BYGONE_EFFIGY_ELITE": Encounter("BYGONE_EFFIGY_ELITE", "Elite", fixed=(S("BYGONE_EFFIGY"),)),
    "BYRDONIS_ELITE": Encounter("BYRDONIS_ELITE", "Elite", fixed=(S("BYRDONIS"),)),
    "CEREMONIAL_BEAST_BOSS": Encounter("CEREMONIAL_BEAST_BOSS", "Boss", fixed=(S("CEREMONIAL_BEAST"),)),
    "CHOMPERS_NORMAL": Encounter("CHOMPERS_NORMAL", "Monster", tags=('Chomper',), generate=_chompers),
    "CONSTRUCT_MENAGERIE_NORMAL": Encounter("CONSTRUCT_MENAGERIE_NORMAL", "Monster", fixed=(S("PUNCH_CONSTRUCT"), S("CUBEX_CONSTRUCT"), S("CUBEX_CONSTRUCT"),)),
    "CORPSE_SLUGS_NORMAL": Encounter("CORPSE_SLUGS_NORMAL", "Monster", tags=('Slugs',), generate=_corpse_slugs(3)),
    "CORPSE_SLUGS_WEAK": Encounter("CORPSE_SLUGS_WEAK", "Monster", weak=True, tags=('Slugs',), generate=_corpse_slugs(2)),
    "CUBEX_CONSTRUCT_NORMAL": Encounter("CUBEX_CONSTRUCT_NORMAL", "Monster", fixed=(S("CUBEX_CONSTRUCT"),)),
    "CULTISTS_NORMAL": Encounter("CULTISTS_NORMAL", "Monster", fixed=(S("CALCIFIED_CULTIST"), S("DAMP_CULTIST"),)),
    "DECIMILLIPEDE_ELITE": Encounter("DECIMILLIPEDE_ELITE", "Elite", slots=('segment1', 'segment2', 'segment3'), generate=_decimillipede),
    "DENSE_VEGETATION_EVENT_ENCOUNTER": Encounter("DENSE_VEGETATION_EVENT_ENCOUNTER", "Monster", slots=('wriggler1', 'wriggler2', 'wriggler3', 'wriggler4'), generate=_dense_vegetation),
    "DEVOTED_SCULPTOR_WEAK": Encounter("DEVOTED_SCULPTOR_WEAK", "Monster", weak=True, fixed=(S("DEVOTED_SCULPTOR"),)),
    "ENTOMANCER_ELITE": Encounter("ENTOMANCER_ELITE", "Elite", fixed=(S("ENTOMANCER"),)),
    "EXOSKELETONS_NORMAL": Encounter("EXOSKELETONS_NORMAL", "Monster", tags=('Exoskeletons',), slots=('first', 'second', 'third', 'fourth'), fixed=(S("EXOSKELETON", "first"), S("EXOSKELETON", "second"), S("EXOSKELETON", "third"), S("EXOSKELETON", "fourth"),)),
    "EXOSKELETONS_WEAK": Encounter("EXOSKELETONS_WEAK", "Monster", weak=True, tags=('Exoskeletons',), slots=('first', 'second', 'third'), fixed=(S("EXOSKELETON", "first"), S("EXOSKELETON", "second"), S("EXOSKELETON", "third"),)),
    "FABRICATOR_NORMAL": Encounter("FABRICATOR_NORMAL", "Monster", slots=('bot1', 'bot2', 'fabricator', 'bot3', 'bot4'), fixed=(S("FABRICATOR", "fabricator"),)),
    "FAKE_MERCHANT_EVENT_ENCOUNTER": Encounter("FAKE_MERCHANT_EVENT_ENCOUNTER", "Monster", slots=('merchant',), gold=(300, 300), fixed=(S("FAKE_MERCHANT_MONSTER", "merchant"),)),
    "FLYCONID_NORMAL": Encounter("FLYCONID_NORMAL", "Monster", tags=('Mushroom', 'Slimes'), generate=_flyconid),
    "FOGMOG_NORMAL": Encounter("FOGMOG_NORMAL", "Monster", slots=('illusion', 'fogmog'), fixed=(S("FOGMOG", "fogmog"),)),
    "FOSSIL_STALKER_NORMAL": Encounter("FOSSIL_STALKER_NORMAL", "Monster", fixed=(S("FOSSIL_STALKER"),)),
    "FROG_KNIGHT_NORMAL": Encounter("FROG_KNIGHT_NORMAL", "Monster", fixed=(S("FROG_KNIGHT"),)),
    "FUZZY_WURM_CRAWLER_WEAK": Encounter("FUZZY_WURM_CRAWLER_WEAK", "Monster", weak=True, tags=('Crawler',), fixed=(S("FUZZY_WURM_CRAWLER"),)),
    "GLOBE_HEAD_NORMAL": Encounter("GLOBE_HEAD_NORMAL", "Monster", fixed=(S("GLOBE_HEAD"),)),
    "GREMLIN_MERC_NORMAL": Encounter("GREMLIN_MERC_NORMAL", "Monster", fixed=(S("GREMLIN_MERC", "merc"),)),
    "HAUNTED_SHIP_NORMAL": Encounter("HAUNTED_SHIP_NORMAL", "Monster", fixed=(S("HAUNTED_SHIP"),)),
    "HUNTER_KILLER_NORMAL": Encounter("HUNTER_KILLER_NORMAL", "Monster", fixed=(S("HUNTER_KILLER"),)),
    "INFESTED_PRISMS_ELITE": Encounter("INFESTED_PRISMS_ELITE", "Elite", fixed=(S("INFESTED_PRISM"),)),
    "INKLETS_NORMAL": Encounter("INKLETS_NORMAL", "Monster", generate=_inklets),
    "KAISER_CRAB_BOSS": Encounter("KAISER_CRAB_BOSS", "Boss", slots=('crusher', 'rocket'), fixed=(S("CRUSHER", "crusher"), S("ROCKET", "rocket"),)),
    "KNIGHTS_ELITE": Encounter("KNIGHTS_ELITE", "Elite", tags=('Knights',), fixed=(S("FLAIL_KNIGHT", "first"), S("SPECTRAL_KNIGHT", "second"), S("MAGI_KNIGHT", "third"),)),
    "KNOWLEDGE_DEMON_BOSS": Encounter("KNOWLEDGE_DEMON_BOSS", "Boss", fixed=(S("KNOWLEDGE_DEMON"),)),
    "LAGAVULIN_MATRIARCH_BOSS": Encounter("LAGAVULIN_MATRIARCH_BOSS", "Boss", fixed=(S("LAGAVULIN_MATRIARCH"),)),
    "LIVING_FOG_NORMAL": Encounter("LIVING_FOG_NORMAL", "Monster", slots=('bomb1', 'bomb2', 'bomb3', 'bomb4', 'bomb5', 'livingFog'), fixed=(S("LIVING_FOG", "livingFog"),)),
    "LOUSE_PROGENITOR_NORMAL": Encounter("LOUSE_PROGENITOR_NORMAL", "Monster", fixed=(S("LOUSE_PROGENITOR"),)),
    "MAWLER_NORMAL": Encounter("MAWLER_NORMAL", "Monster", fixed=(S("MAWLER"),)),
    "MECHA_KNIGHT_ELITE": Encounter("MECHA_KNIGHT_ELITE", "Elite", fixed=(S("MECHA_KNIGHT"),)),
    "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER": Encounter("MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER", "Monster", fixed=(S("MYSTERIOUS_KNIGHT"),)),
    "MYTES_NORMAL": Encounter("MYTES_NORMAL", "Monster", slots=('first', 'second'), fixed=(S("MYTE", "first"), S("MYTE", "second"),)),
    "NIBBITS_NORMAL": Encounter("NIBBITS_NORMAL", "Monster", slots=('front', 'back'), generate=_nibbits_normal),
    "NIBBITS_WEAK": Encounter("NIBBITS_WEAK", "Monster", weak=True, tags=('Nibbit',), generate=_nibbits_weak),
    "OVERGROWTH_CRAWLERS": Encounter("OVERGROWTH_CRAWLERS", "Monster", tags=('Shrinker', 'Crawler'), fixed=(S("SHRINKER_BEETLE"), S("FUZZY_WURM_CRAWLER"),)),
    "OVICOPTER_NORMAL": Encounter("OVICOPTER_NORMAL", "Monster", slots=('egg1', 'egg2', 'egg3', 'egg4', 'egg5', 'ovicopter'), fixed=(S("OVICOPTER", "ovicopter"),)),
    "OWL_MAGISTRATE_NORMAL": Encounter("OWL_MAGISTRATE_NORMAL", "Monster", fixed=(S("OWL_MAGISTRATE"),)),
    "PHANTASMAL_GARDENERS_ELITE": Encounter("PHANTASMAL_GARDENERS_ELITE", "Elite", slots=('first', 'second', 'third', 'fourth'), fixed=(S("PHANTASMAL_GARDENER", "first"), S("PHANTASMAL_GARDENER", "second"), S("PHANTASMAL_GARDENER", "third"), S("PHANTASMAL_GARDENER", "fourth"),)),
    "PHROG_PARASITE_ELITE": Encounter("PHROG_PARASITE_ELITE", "Elite", slots=('phrog', 'wriggler1', 'wriggler2', 'wriggler3', 'wriggler4'), fixed=(S("PHROG_PARASITE", "phrog"),)),
    "PUNCH_CONSTRUCT_NORMAL": Encounter("PUNCH_CONSTRUCT_NORMAL", "Monster", fixed=(S("PUNCH_CONSTRUCT"),)),
    "PUNCH_OFF_EVENT_ENCOUNTER": Encounter("PUNCH_OFF_EVENT_ENCOUNTER", "Monster", generate=_punch_off),
    "QUEEN_BOSS": Encounter("QUEEN_BOSS", "Boss", slots=('amalgam', 'queen'), fixed=(S("TORCH_HEAD_AMALGAM", "amalgam"), S("QUEEN", "queen"),)),
    "RUBY_RAIDERS_NORMAL": Encounter("RUBY_RAIDERS_NORMAL", "Monster", generate=_ruby_raiders),
    "SCROLLS_OF_BITING_NORMAL": Encounter("SCROLLS_OF_BITING_NORMAL", "Monster", tags=('Scrolls',), generate=_scrolls(True)),
    "SCROLLS_OF_BITING_WEAK": Encounter("SCROLLS_OF_BITING_WEAK", "Monster", weak=True, tags=('Scrolls',), generate=_scrolls(False)),
    "SEAPUNK_NORMAL": Encounter("SEAPUNK_NORMAL", "Monster", tags=('Seapunk',), fixed=(S("CALCIFIED_CULTIST"), S("SEAPUNK"),)),
    "SEAPUNK_WEAK": Encounter("SEAPUNK_WEAK", "Monster", weak=True, tags=('Seapunk',), fixed=(S("SEAPUNK"),)),
    "SEWER_CLAM_NORMAL": Encounter("SEWER_CLAM_NORMAL", "Monster", fixed=(S("SEWER_CLAM"),)),
    "SHRINKER_BEETLE_WEAK": Encounter("SHRINKER_BEETLE_WEAK", "Monster", weak=True, tags=('Shrinker',), fixed=(S("SHRINKER_BEETLE"),)),
    "SKULKING_COLONY_ELITE": Encounter("SKULKING_COLONY_ELITE", "Elite", fixed=(S("SKULKING_COLONY"),)),
    "SLIMED_BERSERKER_NORMAL": Encounter("SLIMED_BERSERKER_NORMAL", "Monster", fixed=(S("SLIMED_BERSERKER"),)),
    "SLIMES_NORMAL": Encounter("SLIMES_NORMAL", "Monster", tags=('Slimes',), generate=_slimes_normal),
    "SLIMES_WEAK": Encounter("SLIMES_WEAK", "Monster", weak=True, tags=('Slimes',), generate=_slimes_weak),
    "SLITHERING_STRANGLER_NORMAL": Encounter("SLITHERING_STRANGLER_NORMAL", "Monster", tags=('Jaxfruit', 'Slimes'), generate=_slithering_strangler),
    "SLUDGE_SPINNER_WEAK": Encounter("SLUDGE_SPINNER_WEAK", "Monster", weak=True, fixed=(S("SLUDGE_SPINNER"),)),
    "SLUMBERING_BEETLE_NORMAL": Encounter("SLUMBERING_BEETLE_NORMAL", "Monster", tags=('Workers',), fixed=(S("BOWLBUG_ROCK", "first"), S("BOWLBUG_SILK", "second"), S("SLUMBERING_BEETLE", "third"),)),
    "SNAPPING_JAXFRUIT_NORMAL": Encounter("SNAPPING_JAXFRUIT_NORMAL", "Monster", tags=('Jaxfruit', 'Mushroom'), fixed=(S("SNAPPING_JAXFRUIT"), S("FLYCONID"),)),
    "SOUL_FYSH_BOSS": Encounter("SOUL_FYSH_BOSS", "Boss", fixed=(S("SOUL_FYSH"),)),
    "SOUL_NEXUS_ELITE": Encounter("SOUL_NEXUS_ELITE", "Elite", fixed=(S("SOUL_NEXUS"),)),
    "SPINY_TOAD_NORMAL": Encounter("SPINY_TOAD_NORMAL", "Monster", fixed=(S("SPINY_TOAD"),)),
    "TERROR_EEL_ELITE": Encounter("TERROR_EEL_ELITE", "Elite", fixed=(S("TERROR_EEL"),)),
    "TEST_SUBJECT_BOSS": Encounter("TEST_SUBJECT_BOSS", "Boss", fixed=(S("TEST_SUBJECT"),)),
    "THE_ARCHITECT_EVENT_ENCOUNTER": Encounter("THE_ARCHITECT_EVENT_ENCOUNTER", "Monster", fixed=(S("ARCHITECT"),)),
    "THE_INSATIABLE_BOSS": Encounter("THE_INSATIABLE_BOSS", "Boss", fixed=(S("THE_INSATIABLE"),)),
    "THE_KIN_BOSS": Encounter("THE_KIN_BOSS", "Boss", slots=('slot1', 'slot2', 'leaderSlot'), generate=_the_kin),
    "THE_LOST_AND_FORGOTTEN_NORMAL": Encounter("THE_LOST_AND_FORGOTTEN_NORMAL", "Monster", fixed=(S("THE_LOST"), S("THE_FORGOTTEN"),)),
    "THE_OBSCURA_NORMAL": Encounter("THE_OBSCURA_NORMAL", "Monster", slots=('illusion', 'obscura'), fixed=(S("THE_OBSCURA", "obscura"),)),
    "THIEVING_HOPPER_WEAK": Encounter("THIEVING_HOPPER_WEAK", "Monster", weak=True, tags=('Thieves',), fixed=(S("THIEVING_HOPPER"),)),
    "TOADPOLES_WEAK": Encounter("TOADPOLES_WEAK", "Monster", weak=True, generate=_toadpoles),
    "TUNNELER_NORMAL": Encounter("TUNNELER_NORMAL", "Monster", tags=('Burrower', 'Chomper'), generate=_tunneler),
    "TUNNELER_WEAK": Encounter("TUNNELER_WEAK", "Monster", weak=True, tags=('Burrower',), fixed=(S("TUNNELER"),)),
    "TURRET_OPERATOR_WEAK": Encounter("TURRET_OPERATOR_WEAK", "Monster", weak=True, fixed=(S("LIVING_SHIELD"), S("TURRET_OPERATOR"),)),
    "TWO_TAILED_RATS_NORMAL": Encounter("TWO_TAILED_RATS_NORMAL", "Monster", slots=('first', 'second', 'third', 'fourth', 'fifth'), generate=_two_tailed_rats),
    "VANTOM_BOSS": Encounter("VANTOM_BOSS", "Boss", fixed=(S("VANTOM"),)),
    "VINE_SHAMBLER_NORMAL": Encounter("VINE_SHAMBLER_NORMAL", "Monster", fixed=(S("VINE_SHAMBLER"),)),
    "WATERFALL_GIANT_BOSS": Encounter("WATERFALL_GIANT_BOSS", "Boss", fixed=(S("WATERFALL_GIANT"),)),
}
