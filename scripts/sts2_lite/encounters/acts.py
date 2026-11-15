"""The acts: their encounter pools, room counts, ancients and events, and the room list `ActModel.GenerateRooms` builds for a run.

The sandbox draws with its own `rng`, never the game's: the lists have the game's structure (grab bags that refill when empty, no repeated tags
back to back) but not its sequence, so an agent can not predict them from a seed."""
from __future__ import annotations

from dataclasses import dataclass, field

from sts2_lite.encounters.definitions import ENCOUNTERS, Encounter

ELITE_SLOTS = 15        # elite encounters generated per act


@dataclass(frozen=True)
class Act:
    id : str
    encounters : tuple[str, ...]
    base_rooms : int
    weak_rooms : int
    ancients : tuple[str, ...]
    events : tuple[str, ...]

    def _of(self, room : str, weak : bool | None = None) -> tuple[Encounter, ...]:
        found = (ENCOUNTERS[e] for e in self.encounters)
        return tuple(e for e in found if e.room == room and (weak is None or e.weak == weak))

    @property
    def weak(self): return self._of("Monster", True)
    @property
    def regular(self): return self._of("Monster", False)
    @property
    def elites(self): return self._of("Elite")
    @property
    def bosses(self): return self._of("Boss")

    def room_count(self, multiplayer : bool = False) -> int:
        return self.base_rooms - (1 if multiplayer else 0)


# ModelDb.AllSharedEvents: in every act's event pool
SHARED_EVENTS = ("BRAIN_LEECH", "CRYSTAL_SPHERE", "DOLL_ROOM", "FAKE_MERCHANT", "POTION_COURIER", "RANWID_THE_ELDER", "RELIC_TRADER", "ROOM_FULL_OF_CHEESE", "SELF_HELP_BOOK",
                 "SLIPPERY_BRIDGE", "STONE_OF_ALL_TIME", "SYMBIOTE", "TEA_MASTER", "THE_FUTURE_OF_POTIONS", "THE_LEGENDS_WERE_TRUE", "THIS_OR_THAT", "WAR_HISTORIAN_REPY",
                 "WELCOME_TO_WONGOS")


ACTS : dict[str, Act] = {
    "OVERGROWTH": Act("OVERGROWTH", (
        "BYGONE_EFFIGY_ELITE",
        "BYRDONIS_ELITE",
        "CEREMONIAL_BEAST_BOSS",
        "CUBEX_CONSTRUCT_NORMAL",
        "FLYCONID_NORMAL",
        "FOGMOG_NORMAL",
        "FUZZY_WURM_CRAWLER_WEAK",
        "INKLETS_NORMAL",
        "MAWLER_NORMAL",
        "NIBBITS_NORMAL",
        "NIBBITS_WEAK",
        "OVERGROWTH_CRAWLERS",
        "PHROG_PARASITE_ELITE",
        "RUBY_RAIDERS_NORMAL",
        "SHRINKER_BEETLE_WEAK",
        "SLIMES_NORMAL",
        "SLIMES_WEAK",
        "SLITHERING_STRANGLER_NORMAL",
        "SNAPPING_JAXFRUIT_NORMAL",
        "THE_KIN_BOSS",
        "VANTOM_BOSS",
        "VINE_SHAMBLER_NORMAL",
    ), 15, 3, ('NEOW',), ('AROMA_OF_CHAOS', 'BYRDONIS_NEST', 'DENSE_VEGETATION', 'JUNGLE_MAZE_ADVENTURE', 'LUMINOUS_CHOIR', 'MORPHIC_GROVE', 'SAPPHIRE_SEED', 'SUNKEN_STATUE', 'TABLET_OF_TRUTH', 'UNREST_SITE', 'WELLSPRING', 'WHISPERING_HOLLOW', 'WOOD_CARVINGS')),
    "UNDERDOCKS": Act("UNDERDOCKS", (
        "CORPSE_SLUGS_NORMAL",
        "CORPSE_SLUGS_WEAK",
        "CULTISTS_NORMAL",
        "FOSSIL_STALKER_NORMAL",
        "GREMLIN_MERC_NORMAL",
        "HAUNTED_SHIP_NORMAL",
        "LAGAVULIN_MATRIARCH_BOSS",
        "LIVING_FOG_NORMAL",
        "PHANTASMAL_GARDENERS_ELITE",
        "PUNCH_CONSTRUCT_NORMAL",
        "SEAPUNK_NORMAL",
        "SEAPUNK_WEAK",
        "SEWER_CLAM_NORMAL",
        "SKULKING_COLONY_ELITE",
        "SLUDGE_SPINNER_WEAK",
        "SOUL_FYSH_BOSS",
        "TERROR_EEL_ELITE",
        "TOADPOLES_WEAK",
        "TWO_TAILED_RATS_NORMAL",
        "WATERFALL_GIANT_BOSS",
    ), 15, 3, ('NEOW',), ('ABYSSAL_BATHS', 'DROWNING_BEACON', 'ENDLESS_CONVEYOR', 'PUNCH_OFF', 'SPIRALING_WHIRLPOOL', 'SUNKEN_STATUE', 'SUNKEN_TREASURY', 'DOORS_OF_LIGHT_AND_DARK', 'TRASH_HEAP', 'WATERLOGGED_SCRIPTORIUM')),
    "HIVE": Act("HIVE", (
        "BOWLBUGS_NORMAL",
        "BOWLBUGS_WEAK",
        "CHOMPERS_NORMAL",
        "DECIMILLIPEDE_ELITE",
        "ENTOMANCER_ELITE",
        "EXOSKELETONS_NORMAL",
        "EXOSKELETONS_WEAK",
        "HUNTER_KILLER_NORMAL",
        "KAISER_CRAB_BOSS",
        "INFESTED_PRISMS_ELITE",
        "KNOWLEDGE_DEMON_BOSS",
        "LOUSE_PROGENITOR_NORMAL",
        "MYTES_NORMAL",
        "OVICOPTER_NORMAL",
        "SLUMBERING_BEETLE_NORMAL",
        "SPINY_TOAD_NORMAL",
        "THE_INSATIABLE_BOSS",
        "THE_OBSCURA_NORMAL",
        "THIEVING_HOPPER_WEAK",
        "TUNNELER_WEAK",
    ), 14, 2, ('OROBAS', 'PAEL', 'TEZCATARA'), ('AMALGAMATOR', 'BUGSLAYER', 'COLORFUL_PHILOSOPHERS', 'COLOSSAL_FLOWER', 'FIELD_OF_MAN_SIZED_HOLES', 'INFESTED_AUTOMATON', 'LOST_WISP', 'SPIRIT_GRAFTER', 'THE_LANTERN_KEY', 'ZEN_WEAVER')),
    "GLORY": Act("GLORY", (
        "AXEBOTS_NORMAL",
        "CONSTRUCT_MENAGERIE_NORMAL",
        "DEVOTED_SCULPTOR_WEAK",
        "AEONGLASS_BOSS",
        "FABRICATOR_NORMAL",
        "FROG_KNIGHT_NORMAL",
        "GLOBE_HEAD_NORMAL",
        "KNIGHTS_ELITE",
        "MECHA_KNIGHT_ELITE",
        "OWL_MAGISTRATE_NORMAL",
        "QUEEN_BOSS",
        "SCROLLS_OF_BITING_NORMAL",
        "SCROLLS_OF_BITING_WEAK",
        "SLIMED_BERSERKER_NORMAL",
        "SOUL_NEXUS_ELITE",
        "TEST_SUBJECT_BOSS",
        "THE_LOST_AND_FORGOTTEN_NORMAL",
        "TURRET_OPERATOR_WEAK",
    ), 13, 2, ('NONUPEIPE', 'TANX', 'VAKUU'), ('BATTLEWORN_DUMMY', 'GRAVE_OF_THE_FORGOTTEN', 'HUNGRY_FOR_MUSHROOMS', 'REFLECTIONS', 'ROUND_TEA_PARTY', 'TRIAL', 'TINKER_TIME')),
}


@dataclass
class Rooms:
    normal : list[Encounter] = field(default_factory=list)
    elite : list[Encounter] = field(default_factory=list)
    boss : Encounter | None = None
    second_boss : Encounter | None = None      # Ascension 10 (Double Boss), in the last act
    ancient : str | None = None


class GrabBag:
    """The game's GrabBag with equal weights: items come out uniformly and are removed."""
    def __init__(self):
        self.items : list[Encounter] = []

    def refill(self, items):
        self.items = list(items)

    def __bool__(self):
        return bool(self.items)

    def grab(self, rng, allowed=None) -> Encounter | None:
        pool = [e for e in self.items if allowed is None or allowed(e)]
        if not pool:
            return None
        item = rng.choice(pool)
        self.items.remove(item)
        return item


def _add_without_repeating_tags(chosen : list[Encounter], bag : GrabBag, rng):
    last = chosen[-1] if chosen else None
    found = bag.grab(rng, lambda e: not e.shares_tags_with(last) and e is not last)
    if found is None:
        found = bag.grab(rng)       # nothing else fits, so a repeat of tags is allowed
    if found is not None:
        chosen.append(found)


def generate_rooms(act : Act, rng, multiplayer : bool = False, ascension : int = 0, last_act : bool = False, shared_ancients : tuple = ()) -> Rooms:
    """ActModel.GenerateRooms: the weak, regular and elite encounters of the act in the order they will be met, its boss and its ancient."""
    rooms = Rooms()
    bag = GrabBag()
    for _ in range(act.weak_rooms):
        if not bag:
            bag.refill(act.weak)
        _add_without_repeating_tags(rooms.normal, bag, rng)
    bag = GrabBag()
    for _ in range(act.weak_rooms, act.room_count(multiplayer)):
        if not bag:
            bag.refill(act.regular)
        _add_without_repeating_tags(rooms.normal, bag, rng)
    bag = GrabBag()
    for _ in range(ELITE_SLOTS):
        if not bag:
            bag.refill(act.elites)
        _add_without_repeating_tags(rooms.elite, bag, rng)
    rooms.boss = rng.choice(act.bosses)
    if ascension >= 10 and last_act:
        rooms.second_boss = rng.choice([b for b in act.bosses if b is not rooms.boss])
    rooms.ancient = rng.choice(tuple(act.ancients) + tuple(shared_ancients))       # the act's own ancients and the shared ones it was dealt (Darv)
    return rooms
