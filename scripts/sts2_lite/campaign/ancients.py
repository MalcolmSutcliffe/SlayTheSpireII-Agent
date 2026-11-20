"""The ancients (Neow, Orobas, Pael, Tezcatara, Nonupeipe, Tanx, Vakuu, Darv): the three relics each one offers, as `GenerateInitialOptions` rolls them.

Each ancient draws from the "ancients" stream (the game seeds one Rng per event; the campaign shares one). `NextItem` is `choice`, `NextBool` a coin flip,
`NextFloat` a `random()`, `UnstableShuffle` a shuffle."""
from __future__ import annotations

from dataclasses import dataclass, field

from sts2_lite.event.run import can_enchant, is_basic_strike
from sts2_lite.relic.ancient_data import NEOW_CURSES, NEOW_POSITIVE, NOT_AT_NEOW
from sts2_lite.relic.bag import relic_name

CHARACTERS = ("IRONCLAD", "SILENT", "DEFECT", "NECROBINDER", "REGENT")      # every character is assumed unlocked
PRISMATIC_ODDS = 1 / 3

NEOW_PAIRED = {"CURSED_PEARL": "GOLDEN_PEARL", "HEFTY_TABLET": "ARCANE_SCROLL", "LEAFY_POULTICE": "NEW_LEAF", "PRECARIOUS_SHEARS": "PRECISE_SCISSORS"}
OROBAS_1 = ("ELECTRIC_SHRYMP", "GLASS_EYE")
OROBAS_2 = ("ALCHEMICAL_COFFER", "DRIFTWOOD", "RADIANT_PEARL", "SAND_CASTLE")
PAEL_1 = ("PAELS_FLESH", "PAELS_HORN", "PAELS_TEARS")
PAEL_3 = ("PAELS_EYE", "PAELS_BLOOD")
TEZCATARA_1 = ("VERY_HOT_COCOA", "YUMMY_COOKIE")
TEZCATARA_2 = ("BIIIG_HUG", "STORYBOOK", "TOASTY_MITTENS")
TEZCATARA_3 = ("GOLDEN_COMPASS", "PUMPKIN_CANDLE", "TOY_BOX", "SEAL_OF_GOLD")
NONUPEIPE = ("BLESSED_ANTLER", "BRILLIANT_SCARF", "DELICATE_FROND", "DIAMOND_DIADEM", "FUR_COAT", "GLITTER", "JEWELRY_BOX", "LOOMING_FRUIT", "SIGNET_RING")
TANX = ("CLAWS", "CROSSBOW", "IRON_CLUB", "MEAT_CLEAVER", "SAI", "SPIKED_GAUNTLETS", "TANXS_WHISTLE", "THROWING_AXE", "WAR_HAMMER")
VAKUU = (("BLOOD_SOAKED_ROSE", "WHISPERING_EARRING", "FIDDLE"), ("PRESERVED_FOG", "SERE_TALON", "DISTINGUISHED_CAPE"), ("CHOICES_PARADOX", "MUSIC_BOX", "LORDS_PARASOL", "JEWELED_MASK"))
DARV_ANY = (("ASTROLABE",), ("BLACK_STAR",), ("CALLING_BELL",), ("EMPTY_CAGE",), ("PANDORAS_BOX",), ("RUNIC_PYRAMID",), ("SNECKO_EYE",))
DARV_ACT_2, DARV_ACT_2_ON = (("ECTOPLASM",), ("SOZU",)), (("PHILOSOPHERS_STONE",), ("VELVET_CHOKER",))      # act 2 only / act 2 and later
TRANSCENDENCE = {"BASH": "BREAK", "FALLING_STAR": "METEOR_SHOWER", "NEUTRALIZE": "SUPPRESS", "UNLEASH": "PROTECTOR", "DUALCAST": "QUADCAST"}                 # the starter cards Archaic Tooth turns into an Ancient card (the Ironclad's)
STARTER_RELIC_UPGRADE = {"BURNING_BLOOD": "BLACK_BLOOD", "RING_OF_THE_SNAKE": "RING_OF_THE_DRAKE", "BOUND_PHYLACTERY": "PHYLACTERY_UNBOUND", "CRACKED_CORE": "INFUSED_CORE"}
SHARED = ("DARV",)
ACT_ANCIENTS = {"OROBAS", "PAEL", "TEZCATARA", "NONUPEIPE", "TANX", "VAKUU"}

# relics that show their name with extras (the option's title for the agent)
TITLES = {"SEA_GLASS": "Sea Glass"}


@dataclass
class AncientOption:
    relic : str
    key : str = ""                  # what the agent reads
    locked : bool = False
    setup : dict = field(default_factory=dict)      # state the relic keeps from the moment it is offered (Sea Glass' character, Dusty Tome's card, ...)

    def __post_init__(self):
        if not self.key:
            self.key = relic_name(self.relic) if self.relic else "locked"


def _opt(relic : str, **setup) -> AncientOption:
    key = relic_name(relic) + (f" ({setup['character'].title()})" if setup.get("character") else "")
    return AncientOption(relic, key, False, setup)


def _count(run, enchantment : str) -> int:
    return sum(can_enchant(c, enchantment) for c in run.deck)


def _removable(run) -> int:
    return sum(c.get("removable") is not False for c in run.deck)


def _has_pet(run) -> bool:
    return run.has_relic("BYRDPIP") or any(c["id"] == "BYRDONIS_EGG" for c in run.deck)


def _starter_relic(run) -> str | None:
    return next((r["id"] for r in run.relics if r["id"] in STARTER_RELIC_UPGRADE), None)


def _transcend_card(run) -> str | None:
    return next((c["id"] for c in run.deck if c["id"] in TRANSCENDENCE), None)


ANCIENT_CARDS_OF = {"IRONCLAD": ("BREAK", "CORRUPTION"), "REGENT": ("METEOR_SHOWER", "THE_SEALED_THRONE"), "SILENT": ("SUPPRESS", "WRAITH_FORM"), "NECROBINDER": ("PROTECTOR", "FORBIDDEN_GRIMOIRE"), "DEFECT": ("QUADCAST", "BIASED_COGNITION")}        # the Ancient cards of each pool
IRONCLAD_ANCIENT_CARDS = ANCIENT_CARDS_OF["IRONCLAD"]


def _dusty_tome_card(run, rng) -> str:
    """DustyTome.SetupForPlayer: a random Ancient card of the character's pool that is not a Transcendence card (for the Ironclad: Corruption)."""
    return rng.choice([c for c in ANCIENT_CARDS_OF.get(run.character, IRONCLAD_ANCIENT_CARDS) if c not in TRANSCENDENCE.values()])


def neow(run, rng) -> list[AncientOption]:
    curse = rng.choice([c for c in NEOW_CURSES])
    positive = [p for p in NEOW_POSITIVE if p != NEOW_PAIRED.get(curse) and not (curse == "NEOWS_SACRIFICE" and p in ("PHIAL_HOLSTER", "LOST_COFFER"))]
    if curse != "LARGE_CAPSULE":
        positive.append("LAVA_ROCK" if rng.random() < 0.5 else "SMALL_CAPSULE")
    positive.append("NUTRITIOUS_OYSTER" if rng.random() < 0.5 else "STONE_HUMIDIFIER")
    positive.append("NEOWS_TALISMAN" if rng.random() < 0.5 else "POMANDER")
    positive = [p for p in positive if p not in NOT_AT_NEOW]
    rng.shuffle(positive)
    return [_opt(r) for r in positive[:2]] + [_opt(curse)]


def orobas(run, rng) -> list[AncientOption]:
    others = [c for c in CHARACTERS if c != run.character]
    character = rng.choice(others) if others else run.character
    first = [("PLAIN", r) for r in OROBAS_1]
    first.append(("PLAIN", "PRISMATIC_GEM") if rng.random() < PRISMATIC_ODDS else ("SEA_GLASS", character))
    a = rng.choice(first)
    b = rng.choice(OROBAS_2)
    third = []
    if _starter_relic(run):
        third.append("TOUCH_OF_OROBAS")
    if _transcend_card(run):
        third.append("ARCHAIC_TOOTH")
    c = rng.choice(third) if third else None
    out = [_opt("SEA_GLASS", character=a[1]) if a[0] == "SEA_GLASS" else _opt(a[1]), _opt(b)]
    out.append(_opt(c) if c else AncientOption("", "Locked", True))
    return out


def pael(run, rng) -> list[AncientOption]:
    one = rng.choice(PAEL_1)
    pool2 = ["PAELS_WING"]
    if _count(run, "GOOPY") >= 3:
        pool2.append("PAELS_CLAW")
    if _removable(run) >= 5:
        pool2.append("PAELS_TOOTH")
    pool2 = pool2 + pool2                       # the list is added to itself, so these are twice as likely as Paels Growth
    pool2.append("PAELS_GROWTH")
    two = rng.choice(pool2)
    pool3 = list(PAEL_3) + ([] if _has_pet(run) else ["PAELS_LEGION"])
    return [_opt(one), _opt(two), _opt(rng.choice(pool3))]


def tezcatara(run, rng) -> list[AncientOption]:
    pool1 = list(TEZCATARA_1)
    if any(is_basic_strike(c) for c in run.deck):
        pool1.append("NUTRITIOUS_SOUP")
    return [_opt(rng.choice(pool1)), _opt(rng.choice(TEZCATARA_2)), _opt(rng.choice(TEZCATARA_3))]


def nonupeipe(run, rng) -> list[AncientOption]:
    pool = list(NONUPEIPE)
    if _count(run, "SWIFT") >= 4:
        pool.append("BEAUTIFUL_BRACELET")
    rng.shuffle(pool)
    return [_opt(r) for r in pool[:3]]


def tanx(run, rng) -> list[AncientOption]:
    pool = list(TANX)
    if _count(run, "INSTINCT") >= 3:
        pool.append("TRI_BOOMERANG")
    rng.shuffle(pool)
    return [_opt(r) for r in pool[:3]]


def vakuu(run, rng) -> list[AncientOption]:
    pools = [list(p) for p in VAKUU]
    for p in pools:
        rng.shuffle(p)
    return [_opt(p[0]) for p in pools]


def darv(run, rng) -> list[AncientOption]:
    sets = list(DARV_ANY)
    if run.act == 2:
        sets += DARV_ACT_2
    if run.act >= 2:
        sets += DARV_ACT_2_ON
    picks = [_opt(rng.choice(s)) for s in sets]
    rng.shuffle(picks)
    if rng.random() < 0.5:
        return picks[:2] + [_opt("DUSTY_TOME", card=_dusty_tome_card(run, rng))]
    return picks[:3]


GENERATORS = {"NEOW": neow, "OROBAS": orobas, "PAEL": pael, "TEZCATARA": tezcatara, "NONUPEIPE": nonupeipe, "TANX": tanx, "VAKUU": vakuu, "DARV": darv}


def generate(ancient_id : str, run, rng) -> list[AncientOption]:
    return GENERATORS[ancient_id](run, rng)
