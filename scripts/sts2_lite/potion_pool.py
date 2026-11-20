"""PotionFactory: the potions a character can be given. Pool = the character's potions + SharedPotionPool (event potions, tokens and specials are never rolled)."""
from __future__ import annotations

from sts2_lite.potion import POTION_INFO, PotionId, PotionRarity

SHARED = ("ATTACK_POTION BEETLE_JUICE BLESSING_OF_THE_FORGE BLOCK_POTION BOTTLED_POTENTIAL CLARITY_EXTRACT COLORLESS_POTION CURE_ALL "
          "DEXTERITY_POTION DISTILLED_CHAOS DROPLET_OF_PRECOGNITION DUPLICATOR ENERGY_POTION ENTROPIC_BREW EXPLOSIVE_AMPOULE FAIRY_IN_A_BOTTLE "
          "FIRE_POTION FLEX_POTION FORTIFIER FRUIT_JUICE FYSH_OIL GAMBLERS_BREW GIGANTIFICATION_POTION HEART_OF_IRON LIQUID_BRONZE LIQUID_MEMORIES "
          "LUCKY_TONIC MAZALETHS_GIFT OROBIC_ACID POTION_OF_BINDING POWDERED_DEMISE POWER_POTION RADIANT_TINCTURE REGEN_POTION SHACKLING_POTION "
          "SHIP_IN_A_BOTTLE SKILL_POTION SNECKO_OIL SPEED_POTION STABLE_SERUM STRENGTH_POTION SWIFT_POTION TOUCH_OF_INSANITY VULNERABLE_POTION WEAK_POTION").split()
CHARACTER = {"IRONCLAD": ("BLOOD_POTION", "SOLDIERS_STEW", "ASHWATER"),      # Ironclad4Epoch.Potions, in its order
             "SILENT": ("POISON_POTION", "GHOST_IN_A_JAR", "CUNNING_POTION"),     # Silent4Epoch.Potions
             "REGENT": ("STAR_POTION", "KINGS_COURAGE", "COSMIC_CONCOCTION"),
             "NECROBINDER": ("POTION_OF_DOOM", "BONE_BREW", "POT_OF_GHOULS"),
             "DEFECT": ("FOCUS_POTION", "ESSENCE_OF_DARKNESS", "POTION_OF_CAPACITY")}
RARE_UP_TO, UNCOMMON_UP_TO = 0.1, 0.35                                      # PotionFactory.RollRarity on NextFloat


def potion_pool(character : str = "IRONCLAD") -> list[PotionId]:
    names = list(CHARACTER.get(character.upper(), ())) + SHARED
    return [PotionId[n] for n in names if n in PotionId.__members__]


def roll_rarity(rng) -> PotionRarity:
    x = rng.random()
    return PotionRarity.RARE if x <= RARE_UP_TO else PotionRarity.UNCOMMON if x <= UNCOMMON_UP_TO else PotionRarity.COMMON


def create_random_potions(rng, count : int = 1, character : str = "IRONCLAD", exclude=()) -> list[PotionId]:
    """`count` distinct potions: a rarity roll each, then a random potion of that rarity, removed from the options."""
    options = [p for p in potion_pool(character) if p not in exclude]
    out = []
    for _ in range(count):
        rarity = roll_rarity(rng)
        of = [p for p in options if POTION_INFO[p].rarity == rarity] or options
        if not of:
            break
        pick = rng.choice(of)
        options.remove(pick)
        out.append(pick)
    return out


def random_potion_id(rng, character : str = "IRONCLAD", exclude=()) -> PotionId:
    return create_random_potions(rng, 1, character, exclude)[0]
