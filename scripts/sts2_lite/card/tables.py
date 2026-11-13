from __future__ import annotations
from typing import TYPE_CHECKING

from enum import Enum, auto
from sts2_lite.status import StatusId

from sts2_lite.card.constants import BAD_LUCK_HP_LOSS, CURSE_STATUS_AMOUNT, DECAY_DAMAGE
from sts2_lite.card.ids import CardId, CardType, TargetType

if TYPE_CHECKING:
    from sts2_lite.card.card import Card

# the Ironclad cards that card effects can add to the player's piles (no Basic or Ancient cards, Feed and Not Yet
# can't be generated, Tank and Demonic Shield are multiplayer only): (name, type, cost, target)
S, A, ALL, RAND = TargetType.Self, TargetType.AnyEnemy, TargetType.AllEnemies, TargetType.RandomEnemy

GENERATABLE_CARDS = {
    CardId.AGGRESSION : ("Aggression", CardType.Power, 1, S),
    CardId.ANGER : ("Anger", CardType.Attack, 0, A),
    CardId.ARMAMENTS : ("Armaments", CardType.Skill, 1, S),
    CardId.ASHEN_STRIKE : ("Ashen Strike", CardType.Attack, 1, A),
    CardId.BARRICADE : ("Barricade", CardType.Power, 3, S),
    CardId.BATTLE_TRANCE : ("Battle Trance", CardType.Skill, 0, S),
    CardId.BLOOD_WALL : ("Blood Wall", CardType.Skill, 2, S),
    CardId.BLOODLETTING : ("Bloodletting", CardType.Skill, 0, S),
    CardId.BLUDGEON : ("Bludgeon", CardType.Attack, 3, A),
    CardId.BODY_SLAM : ("Body Slam", CardType.Attack, 1, A),
    CardId.BRAND : ("Brand", CardType.Skill, 0, S),
    CardId.BREAKTHROUGH : ("Breakthrough", CardType.Attack, 1, ALL),
    CardId.BULLY : ("Bully", CardType.Attack, 0, A),
    CardId.BURNING_PACT : ("Burning Pact", CardType.Skill, 1, S),
    CardId.CASCADE : ("Cascade", CardType.Skill, "X", S),
    CardId.CINDER : ("Cinder", CardType.Attack, 2, A),
    CardId.COLOSSUS : ("Colossus", CardType.Skill, 1, S),
    CardId.CONFLAGRATION : ("Conflagration", CardType.Attack, 1, ALL),
    CardId.CRIMSON_MANTLE : ("Crimson Mantle", CardType.Power, 1, S),
    CardId.CRUELTY : ("Cruelty", CardType.Power, 1, S),
    CardId.DARK_EMBRACE : ("Dark Embrace", CardType.Power, 2, S),
    CardId.DEMON_FORM : ("Demon Form", CardType.Power, 3, S),
    CardId.DISMANTLE : ("Dismantle", CardType.Attack, 1, A),
    CardId.DOMINATE : ("Dominate", CardType.Skill, 1, A),
    CardId.DRUM_OF_BATTLE : ("Drum of Battle", CardType.Skill, 1, S),
    CardId.EVIL_EYE : ("Evil Eye", CardType.Skill, 1, S),
    CardId.EXPECT_A_FIGHT : ("Expect a Fight", CardType.Skill, 2, S),
    CardId.FEEL_NO_PAIN : ("Feel No Pain", CardType.Power, 1, S),
    CardId.FIEND_FIRE : ("Fiend Fire", CardType.Attack, 2, A),
    CardId.FIGHT_ME : ("Fight Me", CardType.Attack, 2, A),
    CardId.FLAME_BARRIER : ("Flame Barrier", CardType.Skill, 2, S),
    CardId.FORGOTTEN_RITUAL : ("Forgotten Ritual", CardType.Skill, 1, S),
    CardId.HAVOC : ("Havoc", CardType.Skill, 1, S),
    CardId.HEADBUTT : ("Headbutt", CardType.Attack, 1, A),
    CardId.HELLRAISER : ("Hellraiser", CardType.Power, 2, S),
    CardId.HEMOKINESIS : ("Hemokinesis", CardType.Attack, 1, A),
    CardId.HOWL_FROM_BEYOND : ("Howl from Beyond", CardType.Attack, 3, ALL),
    CardId.IMPERVIOUS : ("Impervious", CardType.Skill, 2, S),
    CardId.INFERNAL_BLADE : ("Infernal Blade", CardType.Skill, 1, S),
    CardId.INFERNO : ("Inferno", CardType.Power, 1, S),
    CardId.INFLAME : ("Inflame", CardType.Power, 1, S),
    CardId.IRON_WAVE : ("Iron Wave", CardType.Attack, 1, A),
    CardId.JUGGERNAUT : ("Juggernaut", CardType.Power, 2, S),
    CardId.JUGGLING : ("Juggling", CardType.Power, 1, S),
    CardId.MANGLE : ("Mangle", CardType.Attack, 3, A),
    CardId.MOLTEN_FIST : ("Molten Fist", CardType.Attack, 1, A),
    CardId.OFFERING : ("Offering", CardType.Skill, 0, S),
    CardId.ONE_TWO_PUNCH : ("One-Two Punch", CardType.Skill, 1, S),
    CardId.PACTS_END : ("Pact's End", CardType.Attack, 0, ALL),
    CardId.PERFECTED_STRIKE : ("Perfected Strike", CardType.Attack, 2, A),
    CardId.PILLAGE : ("Pillage", CardType.Attack, 1, A),
    CardId.POMMEL_STRIKE : ("Pommel Strike", CardType.Attack, 1, A),
    CardId.PRIMAL_FORCE : ("Primal Force", CardType.Skill, 0, S),
    CardId.PYRE : ("Pyre", CardType.Power, 2, S),
    CardId.RAGE : ("Rage", CardType.Skill, 0, S),
    CardId.RAMPAGE : ("Rampage", CardType.Attack, 1, A),
    CardId.RUPTURE : ("Rupture", CardType.Power, 1, S),
    CardId.SECOND_WIND : ("Second Wind", CardType.Skill, 1, S),
    CardId.SETUP_STRIKE : ("Setup Strike", CardType.Attack, 1, A),
    CardId.SHRUG_IT_OFF : ("Shrug It Off", CardType.Skill, 1, S),
    CardId.SPITE : ("Spite", CardType.Attack, 0, A),
    CardId.STAMPEDE : ("Stampede", CardType.Power, 2, S),
    CardId.STOKE : ("Stoke", CardType.Skill, 1, S),
    CardId.STOMP : ("Stomp", CardType.Attack, 3, ALL),
    CardId.STONE_ARMOR : ("Stone Armor", CardType.Power, 1, S),
    CardId.SWORD_BOOMERANG : ("Sword Boomerang", CardType.Attack, 1, RAND),
    CardId.TAUNT : ("Taunt", CardType.Skill, 1, A),
    CardId.TEAR_ASUNDER : ("Tear Asunder", CardType.Attack, 2, A),
    CardId.THRASH : ("Thrash", CardType.Attack, 1, A),
    CardId.THUNDERCLAP : ("Thunderclap", CardType.Attack, 1, ALL),
    CardId.TREMBLE : ("Tremble", CardType.Skill, 1, A),
    CardId.TRUE_GRIT : ("True Grit", CardType.Skill, 1, S),
    CardId.TWIN_STRIKE : ("Twin Strike", CardType.Attack, 1, A),
    CardId.UNMOVABLE : ("Unmovable", CardType.Power, 2, S),
    CardId.UNRELENTING : ("Unrelenting", CardType.Attack, 2, A),
    CardId.UPPERCUT : ("Uppercut", CardType.Attack, 2, A),
    CardId.VICIOUS : ("Vicious", CardType.Power, 1, S),
    CardId.WHIRLWIND : ("Whirlwind", CardType.Attack, "X", ALL),
}

TOKEN_CARDS = {CardId.GIANT_ROCK : ("Giant Rock", CardType.Attack, 1, A),      # made by Primal Force
               CardId.LUMINESCE : ("Luminesce", CardType.Skill, 0, S)}          # Radiant Pearl: Retain. Gain 2 Energy (3 upgraded). Exhaust.

# event cards (CardRarity.Event): never generated in combat; listed so tests and transforms can build them
EVENT_CARDS = {
    CardId.BYRD_SWOOP : ("Swoop", CardType.Attack, 0, A), CardId.PECK : ("Peck", CardType.Attack, 1, A),
    CardId.EXTERMINATE : ("Exterminate", CardType.Attack, 1, ALL), CardId.SQUASH : ("Squash", CardType.Attack, 1, A),
    CardId.ENLIGHTENMENT : ("Enlightenment", CardType.Skill, 0, S), CardId.METAMORPHOSIS : ("Metamorphosis", CardType.Skill, 2, S),
    CardId.TORIC_TOUGHNESS : ("Toric Toughness", CardType.Skill, 2, S),
}

# colorless cards that card effects can add (Jack of All Trades, Toolbox): (name, type, cost, target). Multiplayer-only
# cards are left out; Splash is not modelled; Alchemize, Hand of Greed and Hidden Gem are never generated in combat.
COLORLESS_CARDS = {
    CardId.FINESSE : ("Finesse", CardType.Skill, 0, S), CardId.FLASH_OF_STEEL : ("Flash of Steel", CardType.Attack, 0, A),
    CardId.ULTIMATE_STRIKE : ("Ultimate Strike", CardType.Attack, 1, A), CardId.ULTIMATE_DEFEND : ("Ultimate Defend", CardType.Skill, 1, S),
    CardId.PRODUCTION : ("Production", CardType.Skill, 0, S), CardId.MASTER_OF_STRATEGY : ("Master of Strategy", CardType.Skill, 0, S),
    CardId.DRAMATIC_ENTRANCE : ("Dramatic Entrance", CardType.Attack, 0, ALL), CardId.SHOCKWAVE : ("Shockwave", CardType.Skill, 2, ALL),
    CardId.PROWESS : ("Prowess", CardType.Power, 1, S), CardId.IMPATIENCE : ("Impatience", CardType.Skill, 0, S),
    CardId.RESTLESSNESS : ("Restlessness", CardType.Skill, 0, S), CardId.SCRAWL : ("Scrawl", CardType.Skill, 1, S),
    CardId.FISTICUFFS : ("Fisticuffs", CardType.Attack, 1, A), CardId.MIND_BLAST : ("Mind Blast", CardType.Attack, 1, A),
    CardId.GOLD_AXE : ("Gold Axe", CardType.Attack, 1, A), CardId.REND : ("Rend", CardType.Attack, 2, A),
    CardId.OMNISLICE : ("Omnislice", CardType.Attack, 0, A), CardId.VOLLEY : ("Volley", CardType.Attack, "X", RAND),
    CardId.ETERNAL_ARMOR : ("Eternal Armor", CardType.Power, 3, S), CardId.HAND_OF_GREED : ("Hand of Greed", CardType.Attack, 2, A),
    CardId.PURITY : ("Purity", CardType.Skill, 0, S),
    CardId.SECRET_TECHNIQUE : ("Secret Technique", CardType.Skill, 0, S), CardId.SECRET_WEAPON : ("Secret Weapon", CardType.Skill, 0, S),
    CardId.SEEKER_STRIKE : ("Seeker Strike", CardType.Attack, 1, A), CardId.THINKING_AHEAD : ("Thinking Ahead", CardType.Skill, 0, S),
    CardId.EQUILIBRIUM : ("Equilibrium", CardType.Skill, 2, S), CardId.SALVO : ("Salvo", CardType.Attack, 1, A),
    CardId.PANIC_BUTTON : ("Panic Button", CardType.Skill, 0, S), CardId.PROLONG : ("Prolong", CardType.Skill, 0, S),
    CardId.FASTEN : ("Fasten", CardType.Power, 1, S), CardId.PREP_TIME : ("Prep Time", CardType.Power, 1, S),
    CardId.DARK_SHACKLES : ("Dark Shackles", CardType.Skill, 0, A), CardId.AUTOMATION : ("Automation", CardType.Power, 1, S),
    CardId.PANACHE : ("Panache", CardType.Power, 0, S), CardId.ROLLING_BOULDER : ("Rolling Boulder", CardType.Power, 3, S),
    CardId.THE_BOMB : ("The Bomb", CardType.Skill, 2, S), CardId.THE_GAMBIT : ("The Gambit", CardType.Skill, 0, S),
    CardId.MAYHEM : ("Mayhem", CardType.Power, 2, S), CardId.NOSTALGIA : ("Nostalgia", CardType.Power, 1, S),
    CardId.BOLAS : ("Bolas", CardType.Attack, 0, A), CardId.THRUMMING_HATCHET : ("Thrumming Hatchet", CardType.Attack, 1, A),
    CardId.JACKPOT : ("Jackpot", CardType.Attack, 3, A), CardId.CALAMITY : ("Calamity", CardType.Power, 3, S),
    CardId.JACK_OF_ALL_TRADES : ("Jack of All Trades", CardType.Skill, 0, S), CardId.CATASTROPHE : ("Catastrophe", CardType.Skill, 2, S),
    CardId.BEAT_DOWN : ("Beat Down", CardType.Skill, 3, RAND), CardId.ANOINTED : ("Anointed", CardType.Skill, 1, S),
    CardId.DISCOVERY : ("Discovery", CardType.Skill, 1, S), CardId.ENTROPY : ("Entropy", CardType.Power, 1, S),
    CardId.HIDDEN_GEM : ("Hidden Gem", CardType.Skill, 1, S), CardId.ALCHEMIZE : ("Alchemize", CardType.Skill, 1, S),
}

# Ancient cards the sim could not read from the decompiled source (name, type, cost, target)
ANCIENT_CARDS = {
    CardId.ABUNDANCE : ("Abundance", CardType.Skill, 1, S), CardId.APOTHEOSIS : ("Apotheosis", CardType.Skill, 2, S),
    CardId.APPARITION : ("Apparition", CardType.Skill, 1, S), CardId.BRIGHTEST_FLAME : ("Brightest Flame", CardType.Skill, 0, S),
    CardId.MAUL : ("Maul", CardType.Attack, 1, A), CardId.RELAX : ("Relax", CardType.Skill, 3, S),
    CardId.WHISTLE : ("Whistle", CardType.Attack, 2, A), CardId.WISH : ("Wish", CardType.Skill, 0, S),
}

# what Jack of All Trades can make: Hand of Greed (and Alchemize and Hidden Gem) cannot be generated in combat, and it makes no Jack of All Trades
NOT_GENERATED_COLORLESS = frozenset({CardId.HAND_OF_GREED, CardId.HIDDEN_GEM, CardId.JACK_OF_ALL_TRADES, CardId.ALCHEMIZE})

JACK_POOL = [cid for cid in COLORLESS_CARDS if cid not in NOT_GENERATED_COLORLESS]

# what a card can be transformed into: generatable colorless cards (Jack of All Trades included), or generatable Ironclad cards
TRANSFORM_COLORLESS = [cid for cid in COLORLESS_CARDS if cid not in (CardId.HAND_OF_GREED, CardId.HIDDEN_GEM, CardId.ALCHEMIZE)]

def transform_options(card : Card) -> list[CardId]:
    """CardFactory.GetFilteredTransformationOptions: Common to Rare cards of the card's own pool (Neow's Fury is colorless), never the same card.
    Empty for Statuses and Curses, which cannot be transformed here."""
    if card.type in (CardType.Status, CardType.Curse):
        return []
    colorless = card.card_id in COLORLESS_CARDS or card.card_id == CardId.NEOWS_FURY or card.card_id in ANCIENT_CARDS
    return [cid for cid in (TRANSFORM_COLORLESS if colorless else GENERATABLE_CARDS) if cid != card.card_id]

class CardRarity(Enum):
    """CardRarity of the game. Basic / Ancient / Event / Token / Status / Curse cards are never in a card reward pool."""
    Basic = auto()
    Common = auto()
    Uncommon = auto()
    Rare = auto()
    Ancient = auto()
    Event = auto()
    Token = auto()
    Status = auto()
    Curse = auto()

# The rarity of every card, read from the `CardRarity` of each class in the decompiled Models.Cards (test_card_rarity checks the
# table is complete). The true game rarity is stored: a policy that treats Bash like a Common does that itself.
_RARITY_NAMES = {
    CardRarity.Basic : (
        "STRIKE_IRONCLAD DEFEND_IRONCLAD BASH"
    ),
    CardRarity.Common : (
        "BLOOD_WALL PERFECTED_STRIKE BREAKTHROUGH SHRUG_IT_OFF POMMEL_STRIKE IRON_WAVE THUNDERCLAP TREMBLE ANGER BODY_SLAM TWIN_STRIKE "
        "MOLTEN_FIST SWORD_BOOMERANG CINDER BLOODLETTING ARMAMENTS HEADBUTT TRUE_GRIT HAVOC SETUP_STRIKE"
    ),
    CardRarity.Uncommon : (
        "INFLAME FIGHT_ME BLUDGEON UNRELENTING HEMOKINESIS DISMANTLE BULLY ASHEN_STRIKE UPPERCUT WHIRLWIND SPITE EVIL_EYE TAUNT SECOND_WIND "
        "DOMINATE FINESSE FLASH_OF_STEEL ULTIMATE_STRIKE ULTIMATE_DEFEND PRODUCTION DRAMATIC_ENTRANCE SHOCKWAVE PROWESS IMPATIENCE "
        "RESTLESSNESS FISTICUFFS MIND_BLAST OMNISLICE VOLLEY PURITY SEEKER_STRIKE THINKING_AHEAD EQUILIBRIUM PANIC_BUTTON PROLONG FASTEN "
        "PREP_TIME DARK_SHACKLES AUTOMATION PANACHE THE_BOMB THRUMMING_HATCHET JACK_OF_ALL_TRADES CATASTROPHE DISCOVERY BURNING_PACT "
        "COLOSSUS FEEL_NO_PAIN FLAME_BARRIER JUGGLING RAGE RUPTURE STAMPEDE STONE_ARMOR VICIOUS BATTLE_TRANCE DRUM_OF_BATTLE EXPECT_A_FIGHT "
        "FORGOTTEN_RITUAL HOWL_FROM_BEYOND INFERNAL_BLADE INFERNO PILLAGE RAMPAGE STOMP"
    ),
    CardRarity.Rare : (
        "CRIMSON_MANTLE IMPERVIOUS FEED AGGRESSION MASTER_OF_STRATEGY SCRAWL GOLD_AXE REND ETERNAL_ARMOR HAND_OF_GREED SECRET_TECHNIQUE "
        "SECRET_WEAPON SALVO ROLLING_BOULDER THE_GAMBIT MAYHEM NOSTALGIA BOLAS JACKPOT CALAMITY BEAT_DOWN ANOINTED ENTROPY HIDDEN_GEM ALCHEMIZE "
        "BARRICADE CRUELTY DARK_EMBRACE DEMON_FORM JUGGERNAUT ONE_TWO_PUNCH PYRE UNMOVABLE CASCADE CONFLAGRATION FIEND_FIRE NOT_YET "
        "OFFERING PACTS_END BRAND HELLRAISER MANGLE PRIMAL_FORCE STOKE TEAR_ASUNDER THRASH"
    ),
    CardRarity.Ancient : (
        "BREAK NEOWS_FURY CORRUPTION ABUNDANCE APOTHEOSIS APPARITION BRIGHTEST_FLAME MAUL RELAX WHISTLE WISH"
    ),
    CardRarity.Event : (
        "BYRD_SWOOP EXTERMINATE PECK SQUASH ENLIGHTENMENT METAMORPHOSIS TORIC_TOUGHNESS"
    ),
    CardRarity.Token : (
        "GIANT_ROCK LUMINESCE"
    ),
    CardRarity.Status : (
        "SLIMED INFECTION BURN BECKON WITHER DAZED WOUND SOOT TOXIC FRANTIC_ESCAPE DISINTEGRATION MIND_ROT SLOTH WASTE_AWAY"
    ),
    CardRarity.Curse : (
        "REGRET DECAY SHAME DOUBT NORMALITY INJURY POOR_SLEEP GREED CLUMSY CURSE_OF_THE_BELL WRITHE FOLLY BAD_LUCK DEBT GUILTY SPORE_MIND "
        "ASCENDERS_BANE"
    ),
}

CARD_RARITY : dict[CardId, CardRarity] = {CardId[name] : rarity for rarity, names in _RARITY_NAMES.items() for name in names.split()}

CARD_RARITY[CardId.NOT_IMPLEMENTED] = CardRarity.Status       # placeholder, not a real card

# Rare cards (Anointed takes them from the draw pile)
RARE_CARDS = frozenset(cid for cid, rarity in CARD_RARITY.items() if rarity == CardRarity.Rare)

INFERNAL_BLADE_POOL = [cid for cid, (_, card_type, _, _) in GENERATABLE_CARDS.items() if card_type == CardType.Attack]

STOKE_POOL = list(GENERATABLE_CARDS)

ZERO_COST_POOL = [cid for cid, (_, _, cost, _) in GENERATABLE_CARDS.items() if cost == 0]       # Jackpot: canonical cost 0, not X

# cards that return to the hand at the start of the next turn if they were played this one (BeforeHandDraw)
RETURNING_CARDS = frozenset({CardId.BOLAS, CardId.THRUMMING_HATCHET})

# cards with the Defend tag (Fasten)
DEFEND_CARDS = frozenset({CardId.DEFEND_IRONCLAD, CardId.ULTIMATE_DEFEND})

# cards with the Strike tag (Hellraiser plays them when they are drawn)
STRIKE_CARDS = frozenset({CardId.ULTIMATE_STRIKE, CardId.SEEKER_STRIKE, CardId.STRIKE_IRONCLAD, CardId.PERFECTED_STRIKE, CardId.POMMEL_STRIKE, CardId.TWIN_STRIKE,
                          CardId.ASHEN_STRIKE, CardId.SETUP_STRIKE})

def _curse_debuff(player, status : StatusId):
    """Shame and Doubt: 2 stacks if the player lacks the debuff, else 1. Hack: the sim ticks it at the end of the enemy turn,
    so a single stack would never reach the next player turn."""
    player.apply_status(status, CURSE_STATUS_AMOUNT if status in player.status else CURSE_STATUS_AMOUNT + 1)

HAND_CURSE_EFFECTS = {
    CardId.REGRET : lambda player: player.lose_hp(len(player.hand)),        # 1 HP per card in hand, itself included
    CardId.DECAY : lambda player: player.apply_damage(DECAY_DAMAGE),
    CardId.BAD_LUCK : lambda player: player.lose_hp(BAD_LUCK_HP_LOSS),     # Unblockable | Unpowered
    CardId.SHAME : lambda player: _curse_debuff(player, StatusId.FRAIL),
    CardId.DOUBT : lambda player: _curse_debuff(player, StatusId.WEAK),
}
