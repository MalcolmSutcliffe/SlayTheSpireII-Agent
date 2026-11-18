from __future__ import annotations

from sts2_lite.relic import RelicId

from sts2_lite.card.ids import CardId, EnchantmentId, TargetType

# Energy cost and target of every Ironclad, colorless, ancient, event and token card, read from the base() call of each class in the
# decompiled Models.Cards (cost "X" is a card that spends all its energy). The shop lists only the gold price, so this is where a
# card's energy cost comes from before it is in the deck. tables.py builds from the same numbers: test_card_constants keeps them equal.
_S, _A, _ALL, _RAND, _NONE = TargetType.Self, TargetType.AnyEnemy, TargetType.AllEnemies, TargetType.RandomEnemy, TargetType.NONE
CARD_ENERGY_COST_AND_TARGET : dict[CardId, tuple[int | str, TargetType]] = {
    CardId.ABUNDANCE : (1, _S),
    CardId.BREAK : (1, _A),
    CardId.CORRUPTION : (3, _S),
    CardId.NEOWS_FURY : (1, _A),
    CardId.AGGRESSION : (1, _S),
    CardId.ALCHEMIZE : (1, _S),
    CardId.ANGER : (0, _A),
    CardId.ANOINTED : (1, _S),
    CardId.APOTHEOSIS : (2, _S),
    CardId.APPARITION : (1, _S),
    CardId.ARMAMENTS : (1, _S),
    CardId.ASHEN_STRIKE : (1, _A),
    CardId.AUTOMATION : (1, _S),
    CardId.BARRICADE : (3, _S),
    CardId.BASH : (2, _A),
    CardId.BATTLE_TRANCE : (0, _S),
    CardId.BEAT_DOWN : (3, _RAND),
    CardId.BLOODLETTING : (0, _S),
    CardId.BLOOD_WALL : (2, _S),
    CardId.BLUDGEON : (3, _A),
    CardId.BODY_SLAM : (1, _A),
    CardId.BOLAS : (0, _A),
    CardId.BRAND : (0, _S),
    CardId.BREAKTHROUGH : (1, _ALL),
    CardId.BRIGHTEST_FLAME : (0, _S),
    CardId.BULLY : (0, _A),
    CardId.BURNING_PACT : (1, _S),
    CardId.BYRD_SWOOP : (0, _A),
    CardId.CALAMITY : (3, _S),
    CardId.CASCADE : ('X', _S),
    CardId.CATASTROPHE : (2, _S),
    CardId.CINDER : (2, _A),
    CardId.COLOSSUS : (1, _S),
    CardId.CONFLAGRATION : (1, _ALL),
    CardId.CRIMSON_MANTLE : (1, _S),
    CardId.CRUELTY : (1, _S),
    CardId.DARK_EMBRACE : (2, _S),
    CardId.DARK_SHACKLES : (0, _A),
    CardId.DEFEND_IRONCLAD : (1, _S),
    CardId.DEFEND_SILENT : (1, _S),
    CardId.NEUTRALIZE : (0, _A),
    CardId.SHIV : (0, _A),
    CardId.STRIKE_SILENT : (1, _A),
    CardId.SURVIVOR : (1, _S),
    CardId.ANTICIPATE : (0, _S),
    CardId.BACKFLIP : (1, _S),
    CardId.BLADE_DANCE : (1, _S),
    CardId.CLOAK_AND_DAGGER : (1, _S),
    CardId.DAGGER_SPRAY : (1, _ALL),
    CardId.DAGGER_THROW : (1, _A),
    CardId.DEADLY_POISON : (1, _A),
    CardId.DEFLECT : (0, _S),
    CardId.DODGE_AND_ROLL : (1, _S),
    CardId.FLICK_FLACK : (1, _ALL),
    CardId.LEADING_STRIKE : (1, _A),
    CardId.PIERCING_WAIL : (1, _ALL),
    CardId.POISONED_STAB : (1, _A),
    CardId.PREDATOR : (2, _A),
    CardId.PREPARED : (0, _S),
    CardId.RICOCHET : (2, _RAND),
    CardId.SLICE : (0, _A),
    CardId.SNAKEBITE : (2, _A),
    CardId.SUCKER_PUNCH : (1, _A),
    CardId.UNTOUCHABLE : (2, _S),
    CardId.DEMON_FORM : (3, _S),
    CardId.DISCOVERY : (1, _S),
    CardId.DISMANTLE : (1, _A),
    CardId.DOMINATE : (1, _A),
    CardId.DRAMATIC_ENTRANCE : (0, _ALL),
    CardId.DRUM_OF_BATTLE : (1, _S),
    CardId.ENLIGHTENMENT : (0, _S),
    CardId.ENTROPY : (1, _S),
    CardId.EQUILIBRIUM : (2, _S),
    CardId.ETERNAL_ARMOR : (3, _S),
    CardId.EVIL_EYE : (1, _S),
    CardId.EXPECT_A_FIGHT : (3, _S),
    CardId.EXTERMINATE : (1, _ALL),
    CardId.FASTEN : (1, _S),
    CardId.FEED : (1, _A),
    CardId.FEEL_NO_PAIN : (1, _S),
    CardId.FIEND_FIRE : (2, _A),
    CardId.FIGHT_ME : (2, _A),
    CardId.FINESSE : (0, _S),
    CardId.FISTICUFFS : (1, _A),
    CardId.FLAME_BARRIER : (2, _S),
    CardId.FLASH_OF_STEEL : (0, _A),
    CardId.FORGOTTEN_RITUAL : (1, _S),
    CardId.GIANT_ROCK : (1, _A),
    CardId.GOLD_AXE : (1, _A),
    CardId.HAND_OF_GREED : (2, _A),
    CardId.HAVOC : (1, _S),
    CardId.HEADBUTT : (1, _A),
    CardId.HELLRAISER : (2, _S),
    CardId.HEMOKINESIS : (1, _A),
    CardId.HIDDEN_GEM : (1, _S),
    CardId.HOWL_FROM_BEYOND : (3, _ALL),
    CardId.IMPATIENCE : (0, _S),
    CardId.IMPERVIOUS : (2, _S),
    CardId.INFERNAL_BLADE : (1, _S),
    CardId.INFERNO : (1, _S),
    CardId.INFLAME : (1, _S),
    CardId.IRON_WAVE : (1, _A),
    CardId.JACKPOT : (3, _A),
    CardId.JACK_OF_ALL_TRADES : (0, _S),
    CardId.JUGGERNAUT : (2, _S),
    CardId.JUGGLING : (1, _S),
    CardId.LUMINESCE : (0, _S),
    CardId.MANGLE : (3, _A),
    CardId.MASTER_OF_STRATEGY : (0, _S),
    CardId.MAUL : (1, _A),
    CardId.MAYHEM : (2, _S),
    CardId.STRATAGEM : (1, _S),
    CardId.METAMORPHOSIS : (2, _S),
    CardId.MIND_BLAST : (1, _A),
    CardId.MOLTEN_FIST : (1, _A),
    CardId.NOSTALGIA : (1, _S),
    CardId.NOT_YET : (2, _S),
    CardId.OFFERING : (0, _S),
    CardId.OMNISLICE : (0, _A),
    CardId.ONE_TWO_PUNCH : (1, _S),
    CardId.PACTS_END : (0, _ALL),
    CardId.PANACHE : (0, _S),
    CardId.PANIC_BUTTON : (0, _S),
    CardId.PECK : (1, _A),
    CardId.PERFECTED_STRIKE : (2, _A),
    CardId.PILLAGE : (1, _A),
    CardId.POMMEL_STRIKE : (1, _A),
    CardId.PREP_TIME : (1, _S),
    CardId.PRIMAL_FORCE : (0, _S),
    CardId.PRODUCTION : (0, _S),
    CardId.PROLONG : (0, _S),
    CardId.PROWESS : (1, _S),
    CardId.PURITY : (0, _S),
    CardId.PYRE : (2, _S),
    CardId.RAGE : (0, _S),
    CardId.RAMPAGE : (1, _A),
    CardId.RELAX : (3, _S),
    CardId.REND : (1, _A),
    CardId.RESTLESSNESS : (0, _S),
    CardId.ROLLING_BOULDER : (3, _S),
    CardId.RUPTURE : (1, _S),
    CardId.SALVO : (1, _A),
    CardId.SCRAWL : (1, _S),
    CardId.SECOND_WIND : (1, _S),
    CardId.SECRET_TECHNIQUE : (0, _S),
    CardId.SECRET_WEAPON : (0, _S),
    CardId.SEEKER_STRIKE : (1, _A),
    CardId.SETUP_STRIKE : (1, _A),
    CardId.SHOCKWAVE : (2, _ALL),
    CardId.SHRUG_IT_OFF : (1, _S),
    CardId.SPITE : (0, _A),
    CardId.SQUASH : (1, _A),
    CardId.STAMPEDE : (2, _S),
    CardId.STOKE : (1, _S),
    CardId.STOMP : (3, _ALL),
    CardId.STONE_ARMOR : (1, _S),
    CardId.STRIKE_IRONCLAD : (1, _A),
    CardId.SWORD_BOOMERANG : (1, _RAND),
    CardId.TAUNT : (1, _A),
    CardId.TEAR_ASUNDER : (2, _A),
    CardId.THE_BOMB : (2, _S),
    CardId.THE_GAMBIT : (0, _S),
    CardId.THINKING_AHEAD : (0, _S),
    CardId.THRASH : (1, _A),
    CardId.THRUMMING_HATCHET : (1, _A),
    CardId.THUNDERCLAP : (1, _ALL),
    CardId.TORIC_TOUGHNESS : (2, _S),
    CardId.FEEDING_FRENZY : (0, _S),
    CardId.MAD_SCIENCE : (1, _A),
    CardId.CLASH : (0, _A), CardId.DUAL_WIELD : (1, _S), CardId.ENTRENCH : (2, _S), CardId.CALTROPS : (1, _S), CardId.DISTRACTION : (1, _S),
    CardId.OUTMANEUVER : (1, _S), CardId.HELLO_WORLD : (1, _S), CardId.REBOUND : (1, _A), CardId.RIP_AND_TEAR : (1, _RAND), CardId.STACK : (1, _S),
    CardId.TREMBLE : (1, _A),
    CardId.TRUE_GRIT : (1, _S),
    CardId.TWIN_STRIKE : (1, _A),
    CardId.ULTIMATE_DEFEND : (1, _S),
    CardId.ULTIMATE_STRIKE : (1, _A),
    CardId.UNMOVABLE : (2, _S),
    CardId.UNRELENTING : (2, _A),
    CardId.UPPERCUT : (2, _A),
    CardId.VICIOUS : (1, _S),
    CardId.VOLLEY : ('X', _RAND),
    CardId.WHIRLWIND : ('X', _ALL),
    CardId.WHISTLE : (2, _A),
    CardId.WISH : (0, _S),
}

INFECTION_DAMAGE = 3

BURN_DAMAGE = 2

BECKON_HP_LOSS = 6      # Soul Fysh's Beckon: a status that can be played for 1 Energy, else costs this at the end of the turn

WITHER_DAMAGE = 3       # and 3 more for each time Aeonglass has upgraded it

TOXIC_DAMAGE = 5

# energy cost change when upgraded (the rest of an upgrade is read from is_upgraded when the card is played)
UPGRADE_COST_CHANGE = {
    CardId.BARRICADE : -1, CardId.CORRUPTION : -1, CardId.DARK_EMBRACE : -1, CardId.STAMPEDE : -1,
    CardId.UNMOVABLE : -1, CardId.HAVOC : -1, CardId.INFERNAL_BLADE : -1,
    CardId.BODY_SLAM : -1, CardId.HELLRAISER : -1, CardId.MIND_BLAST : -1,
    CardId.AUTOMATION : -1, CardId.MAYHEM : -1, CardId.NOSTALGIA : -1, CardId.CALAMITY : -1,
    CardId.APOTHEOSIS : -1, CardId.ABUNDANCE : -1, CardId.ALCHEMIZE : -1, CardId.ENTRENCH : -1, CardId.DISTRACTION : -1,
    CardId.STRATAGEM : -1,
}

# CardModel base cost of the cards above (an upgrade caps a rolled Confused cost at base + change)
UPGRADE_BASE_COST = {
    CardId.BARRICADE : 3, CardId.CORRUPTION : 3, CardId.DARK_EMBRACE : 2, CardId.STAMPEDE : 2,
    CardId.UNMOVABLE : 2, CardId.HAVOC : 1, CardId.INFERNAL_BLADE : 1,
    CardId.BODY_SLAM : 1, CardId.HELLRAISER : 2, CardId.MIND_BLAST : 1,
    CardId.AUTOMATION : 1, CardId.MAYHEM : 2, CardId.NOSTALGIA : 1, CardId.CALAMITY : 3,
    CardId.APOTHEOSIS : 2, CardId.ABUNDANCE : 1, CardId.ALCHEMIZE : 1, CardId.ENTRENCH : 2, CardId.DISTRACTION : 1,
    CardId.STRATAGEM : 1,
}

# keyword an upgrade removes (Exhaust)
UPGRADE_REMOVED_KEYWORD = {CardId.SECRET_TECHNIQUE : 1, CardId.SECRET_WEAPON : 1, CardId.THINKING_AHEAD : 1, CardId.PROLONG : 1, CardId.DISCOVERY : 1, CardId.APPARITION : 2}      # Exhaust x5, Ethereal for Apparition

# keyword an upgrade adds
UPGRADE_KEYWORD = {CardId.HELLO_WORLD : 4, CardId.MAD_SCIENCE : 4, CardId.SCRAWL : 16, CardId.GOLD_AXE : 16, CardId.ANOINTED : 16, CardId.ENTROPY : 4, CardId.WISH : 16, CardId.AGGRESSION : 4, CardId.JUGGLING : 4}       # Retain, Retain, Retain, Innate (Entropy, Aggression, Juggling), Retain

CONFUSED_MAX_COST = 3

_EXHAUST, _ETHEREAL, _INNATE, _UNPLAYABLE, _RETAIN, _SLY, _ETERNAL, _REPLAY = 1, 2, 4, 8, 16, 32, 64, 128

# cards with the Exhaust keyword
EXHAUSTING_CARDS = frozenset({CardId.SLIMED, CardId.TREMBLE, CardId.IMPERVIOUS, CardId.MOLTEN_FIST,
                              CardId.TOXIC, CardId.FEED, CardId.DOMINATE, CardId.FIEND_FIRE, CardId.FORGOTTEN_RITUAL,
                              CardId.INFERNAL_BLADE, CardId.NOT_YET, CardId.OFFERING, CardId.SPORE_MIND,
                              CardId.PRODUCTION, CardId.MASTER_OF_STRATEGY, CardId.DRAMATIC_ENTRANCE, CardId.SHOCKWAVE,
                              CardId.SCRAWL, CardId.PURITY, CardId.SECRET_TECHNIQUE, CardId.SECRET_WEAPON, CardId.THINKING_AHEAD,
                              CardId.PANIC_BUTTON, CardId.PROLONG, CardId.DARK_SHACKLES, CardId.JACK_OF_ALL_TRADES, CardId.ANOINTED, CardId.DISCOVERY, CardId.ALCHEMIZE, CardId.LUMINESCE,
                              CardId.ENLIGHTENMENT, CardId.METAMORPHOSIS, CardId.DISTRACTION, CardId.NEOWS_FURY,
                              CardId.ABUNDANCE, CardId.APOTHEOSIS, CardId.APPARITION, CardId.RELAX, CardId.WHISTLE, CardId.WISH, CardId.SHIV,
                              CardId.BLADE_DANCE, CardId.PIERCING_WAIL})

# curses (Debt's gold loss is not modelled: the sim does not track gold)
CURSE_CARDS = frozenset({CardId.BAD_LUCK, CardId.DEBT, CardId.REGRET, CardId.DECAY, CardId.SHAME, CardId.DOUBT, CardId.NORMALITY, CardId.INJURY,
                         CardId.POOR_SLEEP, CardId.GREED, CardId.CLUMSY, CardId.CURSE_OF_THE_BELL, CardId.WRITHE,
                         CardId.FOLLY, CardId.GUILTY, CardId.SPORE_MIND, CardId.ASCENDERS_BANE, CardId.ENTHRALLED})

PLAYABLE_CURSES = {CardId.SPORE_MIND : 1, CardId.ENTHRALLED : 2}      # energy cost of the curses that can be played

# cards with the Unplayable keyword
UNPLAYABLE_CARDS = frozenset({CardId.SPOILS_MAP, CardId.LANTERN_KEY, CardId.BYRDONIS_EGG, CardId.DOWSING, CardId.DAZED, CardId.WOUND, CardId.NOT_IMPLEMENTED, CardId.INFECTION, CardId.BURN, CardId.WITHER, CardId.SOOT,
                              CardId.DISINTEGRATION, CardId.MIND_ROT, CardId.SLOTH, CardId.WASTE_AWAY}
                             | (CURSE_CARDS - PLAYABLE_CURSES.keys()))

# cards with the Ethereal keyword: exhausted instead of discarded if still in hand at end of turn
ETHEREAL_CARDS = frozenset({CardId.APPARITION, CardId.DAZED, CardId.CLUMSY, CardId.FOLLY, CardId.ASCENDERS_BANE})

# Retain / Innate / Eternal: only Retain acts in combat (Innate and Eternal are deck-level)
RETAINING_CARDS = frozenset({CardId.POOR_SLEEP, CardId.RESTLESSNESS, CardId.PURITY, CardId.LUMINESCE, CardId.SNAKEBITE})

# cards with the Sly keyword: discarded by an effect, they play themselves for free (CardCmd.DiscardAndDraw)
SLY_CARDS = frozenset({CardId.FLICK_FLACK, CardId.RICOCHET, CardId.UNTOUCHABLE})

INNATE_CARDS = frozenset({CardId.APOTHEOSIS, CardId.WRITHE, CardId.FOLLY, CardId.DRAMATIC_ENTRANCE, CardId.MIND_BLAST})

ETERNAL_CARDS = frozenset({CardId.BAD_LUCK, CardId.ASCENDERS_BANE, CardId.CURSE_OF_THE_BELL, CardId.GREED, CardId.FOLLY, CardId.ENTHRALLED})

NORMALITY_CARD_LIMIT = 3

NEOWS_FURY_CARDS = (2, 3)       # cards returned to the hand, by upgrade

DECAY_DAMAGE = 2

BAD_LUCK_HP_LOSS = 13

CURSE_STATUS_AMOUNT = 1         # Shame (Frail), Doubt (Weak)

def _set_canonical_keywords():
    """CardModel.CanonicalKeywords, stored as a mask on each CardId member."""
    for card_id in CardId:
        card_id.keyword_mask = ((_EXHAUST if card_id in EXHAUSTING_CARDS else 0) | (_ETHEREAL if card_id in ETHEREAL_CARDS else 0)
                                | (_UNPLAYABLE if card_id in UNPLAYABLE_CARDS else 0) | (_RETAIN if card_id in RETAINING_CARDS else 0)
                                | (_INNATE if card_id in INNATE_CARDS else 0) | (_ETERNAL if card_id in ETERNAL_CARDS else 0)
                                | (_SLY if card_id in SLY_CARDS else 0))

_set_canonical_keywords()

ENCHANT_CORRUPTED_DAMAGE = 1.5

ENCHANT_INSTINCT_DAMAGE = 2.0

ENCHANT_CORRUPTED_HP_LOSS = 2

ENCHANT_SOWN_ENERGY = 1

ENCHANT_EMBER_DAMAGE = 3

SLITHER_MAX_COST = 3

# enchantments a play changes on the card: the card is played as a private copy (Card.create_copy shares nothing mutable)
CONSUMED_ON_PLAY = frozenset({EnchantmentId.SWIFT, EnchantmentId.SOWN, EnchantmentId.VIGOROUS})

CHANGED_ON_PLAY = CONSUMED_ON_PLAY | {EnchantmentId.MOMENTUM, EnchantmentId.GLAM, EnchantmentId.GOOPY}

_unknown_enchantments : set[str] = set()

_unknown_cards : set[str] = set()

# Quest cards (CardType.Quest, cost -1, Unplayable, MaxUpgradeLevel 0): in combat they do nothing, like a Wound (Spoils Map, Lantern Key, Byrdonis Egg
# and Dowsing act on the map, at events and at rest sites, which the campaign simulator models). They load as themselves (Card.create_quest).
QUEST_NAMES = {CardId.SPOILS_MAP: "Spoils Map", CardId.LANTERN_KEY: "Lantern Key", CardId.BYRDONIS_EGG: "Byrdonis Egg", CardId.DOWSING: "Dowsing"}
QUEST_CARDS = frozenset(cid.name for cid in QUEST_NAMES)
DOWSING_ROOMS = 5         # Dowsing.maxRooms: ? rooms entered with it in the deck before it becomes Abundance

# Mad Science: the riders Tinker Time offers for each card type, and (damage / block, rider numbers) the sim plays them with
MAD_SCIENCE_RIDERS = {"Attack": ("SAPPING", "VIOLENCE", "CHOKING"), "Skill": ("ENERGIZED", "WISDOM", "CHAOS"), "Power": ("EXPERTISE", "CURIOUS", "IMPROVEMENT")}
MAD_SCIENCE_DAMAGE, MAD_SCIENCE_BLOCK = 12, 8
MAD_SCIENCE_TEXT = (("weak", "SAPPING"), ("times", "VIOLENCE"), ("lose", "CHOKING"), ("strangle", "CHOKING"), ("energy", "ENERGIZED"), ("draw", "WISDOM"),
                    ("random", "CHAOS"), ("strength", "EXPERTISE"), ("dexterity", "EXPERTISE"), ("upgrade", "IMPROVEMENT"), ("cost", "CURIOUS"))


def mad_science_rider(description : str) -> str | None:
    """The rider of a Mad Science card the bridge showed, read from its text (the bridge has no field for it)."""
    text = description.lower()
    return next((rider for word, rider in MAD_SCIENCE_TEXT if word in text), None)


def keyword_mask(keywords) -> int:
    mask = 0
    for k in keywords:
        mask |= k.value
    return mask

CURSE_NAMES = {CardId.CURSE_OF_THE_BELL: "Curse of the Bell", CardId.ASCENDERS_BANE: "Ascender's Bane", CardId.POOR_SLEEP: "Poor Sleep",
               CardId.SPORE_MIND: "Spore Mind"}

_SCARF, _CHOKER, _AXE = RelicId.BRILLIANT_SCARF, RelicId.VELVET_CHOKER, RelicId.THROWING_AXE

###
### Helpers
###
