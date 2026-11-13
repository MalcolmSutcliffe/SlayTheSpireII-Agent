from __future__ import annotations

from sts2_lite.relic import RelicId

from sts2_lite.card.ids import CardId, EnchantmentId

INFECTION_DAMAGE = 3

BURN_DAMAGE = 2

BECKON_HP_LOSS = 6      # Soul Fysh's Beckon: a status that can be played for 1 Energy, else costs this at the end of the turn

WITHER_DAMAGE = 3       # and 3 more for each time Aeonglass has upgraded it

TOXIC_DAMAGE = 5

# energy cost change when upgraded (the rest of an upgrade is read from is_upgraded when the card is played)
UPGRADE_COST_CHANGE = {
    CardId.BARRICADE : -1, CardId.CORRUPTION : -1, CardId.DARK_EMBRACE : -1, CardId.STAMPEDE : -1,
    CardId.UNMOVABLE : -1, CardId.HAVOC : -1, CardId.EXPECT_A_FIGHT : -1, CardId.INFERNAL_BLADE : -1,
    CardId.BODY_SLAM : -1, CardId.HELLRAISER : -1, CardId.MIND_BLAST : -1,
    CardId.AUTOMATION : -1, CardId.MAYHEM : -1, CardId.NOSTALGIA : -1, CardId.CALAMITY : -1,
    CardId.APOTHEOSIS : -1, CardId.ABUNDANCE : -1, CardId.ALCHEMIZE : -1,
}

# CardModel base cost of the cards above (an upgrade caps a rolled Confused cost at base + change)
UPGRADE_BASE_COST = {
    CardId.BARRICADE : 3, CardId.CORRUPTION : 3, CardId.DARK_EMBRACE : 2, CardId.STAMPEDE : 2,
    CardId.UNMOVABLE : 2, CardId.HAVOC : 1, CardId.EXPECT_A_FIGHT : 2, CardId.INFERNAL_BLADE : 1,
    CardId.BODY_SLAM : 1, CardId.HELLRAISER : 2, CardId.MIND_BLAST : 1,
    CardId.AUTOMATION : 1, CardId.MAYHEM : 2, CardId.NOSTALGIA : 1, CardId.CALAMITY : 3,
    CardId.APOTHEOSIS : 2, CardId.ABUNDANCE : 1, CardId.ALCHEMIZE : 1,
}

# keyword an upgrade removes (Exhaust)
UPGRADE_REMOVED_KEYWORD = {CardId.SECRET_TECHNIQUE : 1, CardId.SECRET_WEAPON : 1, CardId.THINKING_AHEAD : 1, CardId.PROLONG : 1, CardId.DISCOVERY : 1, CardId.APPARITION : 2}      # Exhaust x5, Ethereal for Apparition

# keyword an upgrade adds
UPGRADE_KEYWORD = {CardId.SCRAWL : 16, CardId.GOLD_AXE : 16, CardId.ANOINTED : 16, CardId.ENTROPY : 4, CardId.WISH : 16}       # Retain, Retain, Retain, Innate

CONFUSED_MAX_COST = 3

_EXHAUST, _ETHEREAL, _INNATE, _UNPLAYABLE, _RETAIN, _ETERNAL, _REPLAY = 1, 2, 4, 8, 16, 64, 128

# cards with the Exhaust keyword
EXHAUSTING_CARDS = frozenset({CardId.SLIMED, CardId.TREMBLE, CardId.IMPERVIOUS, CardId.MOLTEN_FIST,
                              CardId.TOXIC, CardId.FEED, CardId.DOMINATE, CardId.FIEND_FIRE, CardId.FORGOTTEN_RITUAL,
                              CardId.INFERNAL_BLADE, CardId.NOT_YET, CardId.OFFERING, CardId.SPORE_MIND,
                              CardId.PRODUCTION, CardId.MASTER_OF_STRATEGY, CardId.DRAMATIC_ENTRANCE, CardId.SHOCKWAVE,
                              CardId.SCRAWL, CardId.PURITY, CardId.SECRET_TECHNIQUE, CardId.SECRET_WEAPON, CardId.THINKING_AHEAD,
                              CardId.PANIC_BUTTON, CardId.PROLONG, CardId.DARK_SHACKLES, CardId.JACK_OF_ALL_TRADES, CardId.ANOINTED, CardId.DISCOVERY, CardId.ALCHEMIZE, CardId.LUMINESCE,
                              CardId.ENLIGHTENMENT, CardId.METAMORPHOSIS, CardId.NEOWS_FURY,
                              CardId.ABUNDANCE, CardId.APOTHEOSIS, CardId.APPARITION, CardId.RELAX, CardId.WHISTLE, CardId.WISH})

# curses (Enthralled is not modelled; Debt's gold loss is not either: the sim does not track gold)
CURSE_CARDS = frozenset({CardId.BAD_LUCK, CardId.DEBT, CardId.REGRET, CardId.DECAY, CardId.SHAME, CardId.DOUBT, CardId.NORMALITY, CardId.INJURY,
                         CardId.POOR_SLEEP, CardId.GREED, CardId.CLUMSY, CardId.CURSE_OF_THE_BELL, CardId.WRITHE,
                         CardId.FOLLY, CardId.GUILTY, CardId.SPORE_MIND, CardId.ASCENDERS_BANE})

# cards with the Unplayable keyword
UNPLAYABLE_CARDS = frozenset({CardId.DAZED, CardId.WOUND, CardId.NOT_IMPLEMENTED, CardId.INFECTION, CardId.BURN, CardId.WITHER, CardId.SOOT,
                              CardId.DISINTEGRATION, CardId.MIND_ROT, CardId.SLOTH, CardId.WASTE_AWAY}
                             | (CURSE_CARDS - {CardId.SPORE_MIND}))

# cards with the Ethereal keyword: exhausted instead of discarded if still in hand at end of turn
ETHEREAL_CARDS = frozenset({CardId.APPARITION, CardId.DAZED, CardId.CLUMSY, CardId.FOLLY, CardId.ASCENDERS_BANE})

# Retain / Innate / Eternal: only Retain acts in combat (Innate and Eternal are deck-level)
RETAINING_CARDS = frozenset({CardId.POOR_SLEEP, CardId.RESTLESSNESS, CardId.PURITY, CardId.LUMINESCE})

INNATE_CARDS = frozenset({CardId.APOTHEOSIS, CardId.WRITHE, CardId.FOLLY, CardId.DRAMATIC_ENTRANCE, CardId.MIND_BLAST})

ETERNAL_CARDS = frozenset({CardId.BAD_LUCK, CardId.ASCENDERS_BANE, CardId.CURSE_OF_THE_BELL, CardId.GREED, CardId.FOLLY})

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
                                | (_INNATE if card_id in INNATE_CARDS else 0) | (_ETERNAL if card_id in ETERNAL_CARDS else 0))

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
