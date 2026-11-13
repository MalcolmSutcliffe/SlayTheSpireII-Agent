from __future__ import annotations
from typing import TYPE_CHECKING

from enum import Enum, auto

if TYPE_CHECKING:
    from sts2_lite.card import Card

class RelicId(Enum):
    __hash__ = object.__hash__      # members are singletons; Enum.__hash__ is pure Python
    STRIKE_DUMMY = auto()
    MINIATURE_CANNON = auto()
    PAPER_PHROG = auto()
    PAPER_KRANE = auto()
    VAMBRACE = auto()
    TUNGSTEN_ROD = auto()
    BEATING_REMNANT = auto()
    RUINED_HELMET = auto()
    UNSETTLING_LAMP = auto()
    CHEMICAL_X = auto()
    ICE_CREAM = auto()
    RINGING_TRIANGLE = auto()
    STURDY_CLAMP = auto()
    LIZARD_TAIL = auto()
    PEN_NIB = auto()
    NUNCHAKU = auto()
    KUNAI = auto()
    SHURIKEN = auto()
    KUSARIGAMA = auto()
    LETTER_OPENER = auto()
    ORNAMENTAL_FAN = auto()
    TUNING_FORK = auto()
    RAINBOW_RING = auto()
    POCKETWATCH = auto()
    ART_OF_WAR = auto()
    RIPPLE_BASIN = auto()
    PERMAFROST = auto()
    GAME_PIECE = auto()
    MUMMIFIED_HAND = auto()
    RAZOR_TOOTH = auto()
    DAUGHTER_OF_THE_WIND = auto()
    INTIMIDATING_HELMET = auto()
    JOSS_PAPER = auto()
    BURNING_STICKS = auto()
    CHARONS_ASHES = auto()
    CANDELABRA = auto()
    CHANDELIER = auto()
    HAPPY_FLOWER = auto()
    CAPTAINS_WHEEL = auto()
    HORN_CLEAT = auto()
    SPARKLING_ROUGE = auto()
    MERCURY_HOURGLASS = auto()
    STONE_CALENDAR = auto()
    BRIMSTONE = auto()
    ORICHALCUM = auto()
    CLOAK_CLASP = auto()
    SCREAMING_FLAGON = auto()
    PARRYING_SHIELD = auto()
    CENTENNIAL_PUZZLE = auto()
    GREMLIN_HORN = auto()
    PENDULUM = auto()
    THE_ABACUS = auto()
    UNCEASING_TOP = auto()
    DEMON_TONGUE = auto()
    RED_SKULL = auto()
    SELF_FORMING_CLAY = auto()
    BREAD = auto()
    MEAT_ON_THE_BONE = auto()
    BURNING_BLOOD = auto()
    BLACK_BLOOD = auto()
    GHOST_SEED = auto()
    SAI = auto()
    MR_STRUGGLES = auto()
    PAELS_TEARS = auto()
    PAELS_FLESH = auto()
    LOST_WISP = auto()
    FORGOTTEN_SOUL = auto()
    IRON_CLUB = auto()
    HAND_DRILL = auto()
    THE_BOOT = auto()
    FAKE_ORICHALCUM = auto()
    FAKE_STRIKE_DUMMY = auto()
    FAKE_HAPPY_FLOWER = auto()
    PAELS_BLOOD = auto()
    RING_OF_THE_DRAKE = auto()
    POLLINOUS_CORE = auto()
    FIDDLE = auto()
    SNECKO_EYE = auto()
    BRILLIANT_SCARF = auto()
    VELVET_CHOKER = auto()
    THROWING_AXE = auto()
    MUSIC_BOX = auto()
    DIAMOND_DIADEM = auto()
    CROSSBOW = auto()
    BIIIG_HUG = auto()
    RUNIC_PYRAMID = auto()
    TOASTY_MITTENS = auto()
    HISTORY_COURSE = auto()
    SPIKED_GAUNTLETS = auto()
    PHILOSOPHERS_STONE = auto()
    SEAL_OF_GOLD = auto()
    PAELS_EYE = auto()
    PAELS_LEGION = auto()
    REPTILE_TRINKET = auto()
    BELT_BUCKLE = auto()

# What the bridge calls a relic's state (if it reports one) when `used` is true.
# The game marks Vambrace, Unsettling Lamp and Burning Sticks "Active" until they trigger, and a spent Lizard Tail "Disabled".
# Art of War and Ripple Basin are "Active" until an Attack is played in the turn; Rainbow Ring is "Active" once it has triggered.
# (Checked against the game source and saved states. A relic added by console in the middle of a fight stays "Normal" until its next reset.)
# Rainbow Ring also reports `types_played`, the bits of what it has seen this turn (see SEEN_ATTACK below).
USED_STATUS : dict[RelicId, frozenset[str]] = {
    RelicId.VAMBRACE : frozenset({"Normal"}),
    RelicId.UNSETTLING_LAMP : frozenset({"Normal"}),
    RelicId.LIZARD_TAIL : frozenset({"Disabled"}),
    RelicId.BURNING_STICKS : frozenset({"Normal"}),
    RelicId.ART_OF_WAR : frozenset({"Normal"}),
    RelicId.RIPPLE_BASIN : frozenset({"Normal"}),
    RelicId.RAINBOW_RING : frozenset({"Active"}),
    RelicId.RED_SKULL : frozenset({"Active"}),       # the Strength is on
    RelicId.THROWING_AXE : frozenset({"Normal"}),    # Active until the first card is played twice
}

# `used` of these means "this turn" (it is cleared when the next turn starts), so it is only carried within a turn.
PER_TURN_FLAG = frozenset({RelicId.ART_OF_WAR, RelicId.RIPPLE_BASIN, RelicId.RAINBOW_RING, RelicId.DEMON_TONGUE,
                           RelicId.MUSIC_BOX})

# The bridge reports these every time, so a state that was read is never overruled by one the simulator remembers.
ALWAYS_REPORTED = frozenset({RelicId.RED_SKULL})

class RelicInstance:
    relic_id : RelicId
    counter : int | None        # the number the game shows on the relic, for relics that count something
    used : bool                 # the effect that works once has been spent (Vambrace, Ruined Helmet, Unsettling Lamp, Lizard Tail)
    value : int                 # a total kept for the turn (damage taken so far, for Beating Remnant)
    triggering : Card | None    # the card whose effects the relic is still working on (Vambrace, Unsettling Lamp)

    def __init__(self, relic_id : RelicId, counter : int | None = None, used : bool = False, value : int = 0):
        self.relic_id = relic_id
        self.counter = counter
        self.used = used
        self.value = value
        self.triggering = None

    @classmethod
    def from_dict(cls, relic : dict) -> RelicInstance | None:
        """None for a relic that has no effect in combat (or is not modelled yet)."""
        relic_id = RelicId.__members__.get(relic["id"])
        if relic_id is None:
            return None
        used = relic.get("status") in USED_STATUS.get(relic_id, ()) or bool(relic.get("spent"))
        counter = relic.get("counter")
        if relic_id is RelicId.BRILLIANT_SCARF and counter is None:
            counter = BRILLIANT_SCARF_CARDS         # ShowCounter is false once 5 cards are played
        if counter is not None and counter == FLASHES_AT_FULL_COUNT.get(relic_id):
            counter = 0         # these relics show their full count while they flash, which is a reset to 0 (Letter Opener: until the next card is played)
        return cls(relic_id, counter, used, relic.get("types_played") or 0)

    @classmethod
    def deepcopy(cls, relic : RelicInstance) -> RelicInstance:
        new = cls(relic.relic_id, relic.counter, relic.used, relic.value)
        new.triggering = relic.triggering
        return new

# ---
# Card play rules.
# ---
BRILLIANT_SCARF_CARDS = 5

# every few Attacks
NUNCHAKU_EVERY, KUNAI_EVERY, SHURIKEN_EVERY, KUSARIGAMA_EVERY, FAN_EVERY = 10, 3, 3, 3, 3

# every few Skills
LETTER_OPENER_EVERY, LETTER_OPENER_DAMAGE = 3, 5

HAPPY_FLOWER_TURNS = {RelicId.HAPPY_FLOWER : 3, RelicId.FAKE_HAPPY_FLOWER : 5}

FLASHES_AT_FULL_COUNT = {**HAPPY_FLOWER_TURNS, RelicId.LETTER_OPENER : LETTER_OPENER_EVERY, RelicId.PENDULUM : 3, RelicId.NUNCHAKU : NUNCHAKU_EVERY}    # Pendulum: DisplayAmount is Turns while it activates; Nunchaku shows 10 after the tenth Attack, which has already paid out
