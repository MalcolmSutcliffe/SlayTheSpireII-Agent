from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.creature import Creature
    from sts2_lite.enemy import Enemy
    from sts2_lite.player import Player

import re
from enum import Enum, auto

from sts2_lite import rng
from sts2_lite.events import EventType
from sts2_lite.status import StatusId, is_debuff, AUTOMATION_CARDS, PANACHE_CARDS
from sts2_lite.relic import block_multiplier, block_gained, debuff_multiplier, x_bonus, before_card_played, snapshot, restore, RelicId, extra_plays, free_by_relic, blocks_play


class CardType(Enum):
    __hash__ = object.__hash__      # members are singletons; Enum.__hash__ is pure Python
    Power = auto()
    Skill = auto()
    Attack = auto()
    Status = auto()
    Curse = auto()

class CardId(Enum):
    __hash__ = object.__hash__      # members are singletons; Enum.__hash__ is pure Python
    STRIKE_IRONCLAD = auto()
    DEFEND_IRONCLAD = auto()
    BASH = auto()
    BLOOD_WALL = auto()
    SLIMED = auto()
    PERFECTED_STRIKE = auto()
    BREAKTHROUGH = auto()
    SHRUG_IT_OFF = auto()
    POMMEL_STRIKE = auto()
    IRON_WAVE = auto()
    THUNDERCLAP = auto()
    INFLAME = auto()
    FIGHT_ME = auto()
    TREMBLE = auto()
    CRIMSON_MANTLE = auto()
    ANGER = auto()
    INFECTION = auto()
    BURN = auto()
    BECKON = auto()
    WITHER = auto()
    BLUDGEON = auto()
    UNRELENTING = auto()
    BODY_SLAM = auto()
    TWIN_STRIKE = auto()
    DAZED = auto()
    WOUND = auto()
    NOT_IMPLEMENTED = auto()    # stand-in for a card the sim does not model: behaves like Wound
    SOOT = auto()
    TOXIC = auto()
    FRANTIC_ESCAPE = auto()
    DISINTEGRATION = auto()    # the four Knowledge Demon curses are only ever offered on its pick screen
    MIND_ROT = auto()
    SLOTH = auto()
    WASTE_AWAY = auto()
    REGRET = auto()
    DECAY = auto()
    SHAME = auto()
    DOUBT = auto()
    NORMALITY = auto()
    INJURY = auto()
    POOR_SLEEP = auto()
    GREED = auto()
    CLUMSY = auto()
    CURSE_OF_THE_BELL = auto()
    WRITHE = auto()
    FOLLY = auto()
    BAD_LUCK = auto()
    DEBT = auto()
    GUILTY = auto()
    SPORE_MIND = auto()
    ASCENDERS_BANE = auto()
    BREAK = auto()
    HEMOKINESIS = auto()
    DISMANTLE = auto()
    BULLY = auto()
    ASHEN_STRIKE = auto()
    MOLTEN_FIST = auto()
    UPPERCUT = auto()
    SWORD_BOOMERANG = auto()
    WHIRLWIND = auto()
    SPITE = auto()
    CINDER = auto()
    IMPERVIOUS = auto()
    EVIL_EYE = auto()
    TAUNT = auto()
    SECOND_WIND = auto()
    BLOODLETTING = auto()
    FEED = auto()
    DOMINATE = auto()
    ARMAMENTS = auto()
    AGGRESSION = auto()
    HEADBUTT = auto()
    NEOWS_FURY = auto()
    # colorless
    FINESSE = auto()
    FLASH_OF_STEEL = auto()
    ULTIMATE_STRIKE = auto()
    ULTIMATE_DEFEND = auto()
    PRODUCTION = auto()
    MASTER_OF_STRATEGY = auto()
    DRAMATIC_ENTRANCE = auto()
    SHOCKWAVE = auto()
    PROWESS = auto()
    IMPATIENCE = auto()
    RESTLESSNESS = auto()
    SCRAWL = auto()
    FISTICUFFS = auto()
    MIND_BLAST = auto()
    GOLD_AXE = auto()
    REND = auto()
    OMNISLICE = auto()
    VOLLEY = auto()
    ETERNAL_ARMOR = auto()
    HAND_OF_GREED = auto()
    PURITY = auto()
    SECRET_TECHNIQUE = auto()
    SECRET_WEAPON = auto()
    SEEKER_STRIKE = auto()
    THINKING_AHEAD = auto()
    EQUILIBRIUM = auto()
    SALVO = auto()
    PANIC_BUTTON = auto()
    PROLONG = auto()
    FASTEN = auto()
    PREP_TIME = auto()
    DARK_SHACKLES = auto()
    AUTOMATION = auto()
    PANACHE = auto()
    ROLLING_BOULDER = auto()
    THE_BOMB = auto()
    THE_GAMBIT = auto()
    MAYHEM = auto()
    NOSTALGIA = auto()
    BOLAS = auto()
    THRUMMING_HATCHET = auto()
    JACKPOT = auto()
    CALAMITY = auto()
    JACK_OF_ALL_TRADES = auto()
    CATASTROPHE = auto()
    BEAT_DOWN = auto()
    ANOINTED = auto()
    DISCOVERY = auto()
    ENTROPY = auto()
    HIDDEN_GEM = auto()
    ALCHEMIZE = auto()
    LUMINESCE = auto()
    TRUE_GRIT = auto()
    BURNING_PACT = auto()
    HAVOC = auto()
    BARRICADE = auto()
    COLOSSUS = auto()
    CORRUPTION = auto()
    CRUELTY = auto()
    DARK_EMBRACE = auto()
    DEMON_FORM = auto()
    FEEL_NO_PAIN = auto()
    FLAME_BARRIER = auto()
    JUGGERNAUT = auto()
    JUGGLING = auto()
    ONE_TWO_PUNCH = auto()
    PYRE = auto()
    RAGE = auto()
    RUPTURE = auto()
    STAMPEDE = auto()
    STONE_ARMOR = auto()
    UNMOVABLE = auto()
    VICIOUS = auto()
    BATTLE_TRANCE = auto()
    CASCADE = auto()
    CONFLAGRATION = auto()
    DRUM_OF_BATTLE = auto()
    EXPECT_A_FIGHT = auto()
    FIEND_FIRE = auto()
    FORGOTTEN_RITUAL = auto()
    HOWL_FROM_BEYOND = auto()
    INFERNAL_BLADE = auto()
    NOT_YET = auto()
    OFFERING = auto()
    PACTS_END = auto()
    BRAND = auto()
    GIANT_ROCK = auto()
    HELLRAISER = auto()
    INFERNO = auto()
    MANGLE = auto()
    PILLAGE = auto()
    PRIMAL_FORCE = auto()
    RAMPAGE = auto()
    SETUP_STRIKE = auto()
    STOKE = auto()
    STOMP = auto()
    TEAR_ASUNDER = auto()
    THRASH = auto()
    # event cards
    BYRD_SWOOP = auto()
    EXTERMINATE = auto()
    PECK = auto()
    SQUASH = auto()
    ENLIGHTENMENT = auto()
    METAMORPHOSIS = auto()
    TORIC_TOUGHNESS = auto()
    ABUNDANCE = auto()
    APOTHEOSIS = auto()
    APPARITION = auto()
    BRIGHTEST_FLAME = auto()
    MAUL = auto()
    RELAX = auto()
    WHISTLE = auto()
    WISH = auto()

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

class CardKeyword(Enum):
    """Entities.Cards.CardKeyword (None omitted). Values are bits: cards store keywords as an int mask (Enum hashing is slow)."""
    EXHAUST = 1
    ETHEREAL = 2
    INNATE = 4
    UNPLAYABLE = 8
    RETAIN = 16
    SLY = 32
    ETERNAL = 64
    REPLAY = 128        # Glam: the card is played one extra time (Replay 1, once per combat)

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

class EnchantmentId(Enum):
    """Models.Enchantments, by the bridge's id (the card's "enchantment": {"id", "amount"}). A card holds at most one."""
    __hash__ = object.__hash__
    ADROIT = auto()             # X Block after the card's own effects, as a separate gain
    CLONE = auto()
    CORRUPTED = auto()          # Attack: +50% damage, lose 2 HP after its effects
    GLAM = auto()               # Replay 1 (placeholder keyword), lost on play
    GOOPY = auto()              # Defend: Exhaust, +1 Block per play (the state carries it)
    IMBUED = auto()
    INKY = auto()
    INSTINCT = auto()           # Attack: +100% damage
    MOMENTUM = auto()           # Attack: +X damage for the rest of the combat each play
    NIMBLE = auto()             # Skill: +X Block
    PERFECT_FIT = auto()        # goes on top of the draw pile when shuffled
    ROYALLY_APPROVED = auto()   # Innate and Retain
    SHARP = auto()              # Attack: +X damage
    SLITHER = auto()            # cost 0-3 whenever drawn
    SWIFT = auto()              # draw X cards on play, then lost
    SOULS_POWER = auto()
    SOWN = auto()               # +1 energy on play, then lost
    SPIRAL = auto()
    STEADY = auto()
    TEZCATARAS_EMBER = auto()   # basic Strike: costs 0 (the state's cost), +3 damage
    VIGOROUS = auto()           # Attack: +X damage on the first play, then lost

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

class TargetType(Enum):
    __hash__ = object.__hash__      # members are singletons; Enum.__hash__ is pure Python
    AnyEnemy = auto()
    AllEnemies = auto()
    Self = auto()
    RandomEnemy = auto()
    NONE = auto()

class Card:
    card_id : CardId
    name : str
    type : CardType
    energy_cost : int | str
    target_type : TargetType
    is_upgraded : bool
    is_unplayable : bool
    restore_cost : int | str | None = None     # set while the cost is changed for this turn: the cost it gets back
    until_played : bool = False                # the temporary cost also ends when the card is played (SetThisTurnOrUntilPlayed)
    replay : int = 0                           # extra plays the card has for good (Hidden Gem); Glam's is the REPLAY keyword
    bonus_damage : int = 0                     # damage Rampage and Thrash have gained this combat
    shown_damage : int | None = None           # the damage printed on the card when it was loaded from the game
    enchantment : EnchantmentId | None = None  # at most one per card
    enchant_amount : int = 0                   # the enchantment's X (Sharp 2, Adroit 3, ...)
    enchant_bonus : int = 0                    # damage Momentum has added this combat
    dampened_from : Card | None = None         # Dampen: the upgraded card this one was downgraded from
    wither_level : int = 0                     # Aeonglass's Increasing Intensity: how often this Wither has been fake-upgraded
    bound : bool = False                       # the Queen's Chains of Binding: only one Bound card can be played a turn
    _keywords : int | None = None              # keyword mask; None: the card's canonical keywords
    generated : bool = False                   # made during this fight (the game's DeckVersion is null); the Thieving Hopper cannot take it

    def __init__(self):
        pass

    @property
    def _mask(self) -> int:
        return self._keywords if self._keywords is not None else self.card_id.keyword_mask

    @property
    def keywords(self) -> frozenset[CardKeyword]:
        mask = self._mask
        return frozenset(k for k in CardKeyword if mask & k.value)

    def with_keyword(self, keyword : CardKeyword) -> Card:
        """A copy with `keyword` added (CardCmd.ApplyKeyword); cards are shared between states, so never in place."""
        mask = self._mask
        if mask & keyword.value:
            return self
        new_card = Card.create_copy(self)
        new_card._keywords = mask | keyword.value
        return new_card

    def with_replay(self, extra : int) -> Card:
        """A copy that plays `extra` more times for good (BaseReplayCount)."""
        new_card = Card.create_copy(self)
        new_card.replay = self.replay + extra
        return new_card

    @property
    def has_glam_replay(self) -> bool:
        return bool(self._mask & _REPLAY)

    @property
    def exhausts(self) -> bool:
        return bool(self._mask & _EXHAUST) or self.enchantment == EnchantmentId.GOOPY

    @property
    def ethereal(self) -> bool:
        return bool(self._mask & _ETHEREAL)

    @property
    def unplayable(self) -> bool:
        return bool(self._mask & _UNPLAYABLE)

    @property
    def retains(self) -> bool:
        return bool(self._mask & _RETAIN)

    @classmethod
    def from_dict(cls, card : dict):
        if card["id"] not in CardId.__members__ or card["id"] == "NOT_IMPLEMENTED":
            if card["id"] not in _unknown_cards:
                _unknown_cards.add(card["id"])
                print(f"card {card['id']} is not implemented in the sim: treated as a Wound")
            placeholder = cls.create_not_implemented(card.get("name") or card["id"])
            placeholder.is_upgraded = bool(card.get("is_upgraded"))
            return placeholder
        new_card = cls()
        new_card.card_id = CardId[card["id"]]
        new_card.type = CardType[card["type"]]
        new_card.name = card["name"]
        # "EnergyCostTooHigh" is only the energy left right now: the simulator decides that itself, so the flag must not follow the card
        # into the discard pile (it made every card the player could not afford at the moment unplayable for the rest of a search)
        new_card.is_unplayable = not card["can_play"] and card.get("unplayable_reason") != "EnergyCostTooHigh"
        if card["cost"] == "X":
            new_card.energy_cost = card["cost"]
        else:
            new_card.energy_cost = int(card["cost"])
        new_card.is_upgraded = card["is_upgraded"]
        new_card.generated = bool(card.get("generated"))
        if card.get("card_keywords") is not None:       # CardModel.Keywords; older bridges only send hover tips
            new_card._keywords = keyword_mask(CardKeyword[k.upper()] for k in card["card_keywords"] if k.upper() in CardKeyword.__members__)
        if card.get("enchantment"):
            new_card._read_enchantment(card["enchantment"])
        new_card.bound = any(k.get("name") == "Bound" for k in card.get("keywords") or ())      # Chains of Binding shows as a keyword
        if new_card.bound and card.get("unplayable_reason") == "BlockedByHook":
            new_card.is_unplayable = False              # only because a Bound card was played this turn: the simulator knows that itself
        if new_card.card_id == CardId.STOMP and new_card.energy_cost < 3:
            new_card.restore_cost = 3           # the shown cost already includes this turn's Attacks
        match = re.search(r"Deals?\s+(\d+)", card.get("description") or "")
        new_card.shown_damage = int(match.group(1)) if match else None
        if new_card.card_id == CardId.WITHER:       # "Wither+2": the damage on it is 3 for every step
            damage = re.search(r"(\d+)\s+damage", card.get("description") or "")
            new_card.wither_level = max(0, int(damage.group(1)) // WITHER_DAMAGE - 1) if damage else 0
        replay = re.search(r"Replay (\d+)\.", card.get("description") or "")       # Hidden Gem (Glam prints "Replay 1." too, but it is the keyword)
        new_card.replay = int(replay.group(1)) if replay and new_card.card_id != CardId.HIDDEN_GEM and new_card.enchantment != EnchantmentId.GLAM else 0
        if card["target_type"] == "None":
            new_card.target_type = TargetType.NONE
        else:
            new_card.target_type = TargetType[card["target_type"]]
        return new_card

    def _read_enchantment(self, raw : dict):
        """The enchantment the bridge reports, with the keywords it grants (they are not in the card's keyword list)."""
        enchantment = EnchantmentId.__members__.get(raw["id"])
        if enchantment is None:
            if raw["id"] not in _unknown_enchantments:
                _unknown_enchantments.add(raw["id"])
                print(f"unknown enchantment {raw['id']} on {self.name}: ignored")
            return
        self.enchantment, self.enchant_amount = enchantment, int(raw.get("amount") or 0)
        if enchantment == EnchantmentId.ROYALLY_APPROVED:
            self._keywords = self._mask | _INNATE | _RETAIN
        elif enchantment == EnchantmentId.GLAM:
            self._keywords = self._mask | _REPLAY
        elif enchantment == EnchantmentId.GOOPY:
            self._keywords = self._mask | CardKeyword.EXHAUST.value

    @classmethod
    def create_slimed(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.SLIMED, "Slimed", CardType.Status
        c.energy_cost, c.target_type = 1, TargetType.NONE
        c.is_upgraded = c.is_unplayable = False
        return c

    @classmethod
    def create_beckon(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.BECKON, "Beckon", CardType.Status
        c.energy_cost, c.target_type = 1, TargetType.NONE
        c.is_upgraded = c.is_unplayable = False
        return c

    @classmethod
    def create_wither(cls, level : int = 0) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.WITHER, "Wither", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        c.wither_level = level
        return c

    def bound_copy(self, bound : bool = True) -> Card:
        c = Card.create_copy(self)
        c.bound = bound
        return c

    @classmethod
    def create_burn(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.BURN, "Burn", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_infection(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.INFECTION, "Infection", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_dazed(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.DAZED, "Dazed", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_wound(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.WOUND, "Wound", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_not_implemented(cls, name : str = "Not implemented") -> Card:
        """A card the sim does not know: a Wound, so that the agent neither plays it nor counts on it."""
        c = cls.create_wound()
        c.card_id, c.name = CardId.NOT_IMPLEMENTED, name
        return c

    @classmethod
    def create_soot(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.SOOT, "Soot", CardType.Status
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_toxic(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.TOXIC, "Toxic", CardType.Status
        c.energy_cost, c.target_type = 1, TargetType.NONE
        c.is_upgraded = c.is_unplayable = False
        return c

    @classmethod
    def create_frantic_escape(cls) -> Card:
        c = cls()
        c.card_id, c.name, c.type = CardId.FRANTIC_ESCAPE, "Frantic Escape", CardType.Status
        c.energy_cost, c.target_type = 1, TargetType.Self
        c.is_upgraded = c.is_unplayable = False
        return c

    @classmethod
    def create_knowledge_curse(cls, card_id : CardId) -> Card:
        """What Knowledge Demon offers: a pick, never played (the chosen one applies its power)."""
        c = cls()
        c.card_id, c.type = card_id, CardType.Status
        c.name = card_id.name.replace("_", " ").title()
        c.energy_cost, c.target_type = 0, TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = True
        return c

    @classmethod
    def create_curse(cls, card_id : CardId) -> Card:
        """A curse: cost 0 and unplayable, except Spore Mind (1 energy, Exhaust)."""
        c = cls()
        c.card_id, c.type = card_id, CardType.Curse
        c.name = CURSE_NAMES.get(card_id) or card_id.name.replace("_", " ").title()
        c.energy_cost, c.target_type = (1 if card_id == CardId.SPORE_MIND else 0), TargetType.NONE
        c.is_upgraded = False
        c.is_unplayable = card_id != CardId.SPORE_MIND
        return c

    @classmethod
    def create(cls, card_id : CardId) -> Card:
        """A fresh copy of a card that enemies add to the player's piles."""
        c = GENERATED_CARDS[card_id]()
        c.generated = True
        return c

    @classmethod
    def create_generated(cls, card_id : CardId, upgraded : bool = False) -> Card:
        """A fresh copy of a card that a card effect adds to the player's piles (Infernal Blade, Stoke)."""
        name, card_type, cost, target = (GENERATABLE_CARDS.get(card_id) or COLORLESS_CARDS.get(card_id) or EVENT_CARDS.get(card_id) or ANCIENT_CARDS.get(card_id)
                                         or TOKEN_CARDS[card_id])
        c = cls()
        c.card_id, c.name, c.type = card_id, name, card_type
        c.energy_cost, c.target_type = cost, target
        c.is_upgraded = c.is_unplayable = False
        c.generated = True
        return c.upgraded_copy() if upgraded else c

    def confused_copy(self, cost : int) -> Card:
        """ConfusedPower.AfterCardDrawn: SetThisCombat(cost), an Absolute modifier over every earlier one."""
        new_card = Card.create_copy(self)
        new_card.energy_cost, new_card.restore_cost, new_card.until_played = cost, None, False
        return new_card

    def cheaper_this_turn(self, amount : int) -> Card:
        """A copy that costs `amount` less until the end of the turn (Stomp)."""
        new_card = Card.create_copy(self)
        if new_card.restore_cost is None:
            new_card.restore_cost = self.energy_cost
        new_card.energy_cost = max(0, self.energy_cost - amount)
        return new_card

    def free_this_combat(self) -> Card:
        """CardModel.SetToFreeThisCombat: SetThisCombat(0). X costs ignore local modifiers (CardEnergyCost.GetWithModifiers)."""
        if self.energy_cost == "X":
            return self
        new_card = Card.create_copy(self)
        new_card.energy_cost, new_card.restore_cost, new_card.until_played = 0, None, False
        return new_card

    def free_this_turn(self) -> Card:
        """CardModel.SetToFreeThisTurn: SetThisTurnOrUntilPlayed(0)."""
        if self.energy_cost == "X":
            return self
        new_card = Card.create_copy(self)
        if new_card.restore_cost is None:
            new_card.restore_cost = self.energy_cost
        new_card.energy_cost, new_card.until_played = 0, True
        return new_card

    def reduced_to(self, cost : int, this_combat : bool) -> Card:
        """A reduce-only Absolute cost modifier (LocalCostModifier.IsReduceOnly): min(current, cost).
        this_combat: SetThisCombat (also caps the cost a this-turn change gives back); else SetThisTurnOrUntilPlayed."""
        if self.energy_cost == "X":
            return self
        restored = self.restore_cost if self.restore_cost is not None else self.energy_cost
        until = self.until_played
        if this_combat:
            new_restore = None if self.restore_cost is None else min(self.restore_cost, cost)
            new_cost = min(self.energy_cost, cost)
        else:
            new_cost = min(self.energy_cost, cost)
            new_restore = restored if new_cost != self.energy_cost or self.restore_cost is not None else None
            until = until or new_cost != self.energy_cost
        if new_cost == self.energy_cost and new_restore == self.restore_cost and until == self.until_played:
            return self
        new_card = Card.create_copy(self)
        new_card.energy_cost, new_card.restore_cost, new_card.until_played = new_cost, new_restore, until
        return new_card

    def cost_after_play(self) -> Card:
        """CardEnergyCost.AfterCardPlayedCleanup: until-played changes end once the play finishes. The sim keeps one
        temporary cost per card, so a Stomp discount stacked on it ends too (both would be gone by the next turn)."""
        if not self.until_played:
            return self
        new_card = Card.create_copy(self)
        new_card.energy_cost, new_card.restore_cost, new_card.until_played = self.restore_cost, None, False
        return new_card

    @property
    def is_strike(self) -> bool:
        return self.card_id in STRIKE_CARDS

    @property
    def is_upgradable(self) -> bool:
        return not self.is_upgraded and self.type != CardType.Status and self.type != CardType.Curse

    def downgraded_copy(self) -> Card:
        """Dampen: the plain version of an upgraded card (what upgraded_copy undid); shared piles stay untouched."""
        new_card = Card.create_copy(self)
        new_card.is_upgraded = False
        if new_card.name.endswith("+"):
            new_card.name = new_card.name[:-1]
        change = UPGRADE_COST_CHANGE.get(self.card_id, 0)
        if change and new_card.energy_cost != "X":
            new_card.energy_cost = max(0, self.energy_cost - change)
            if self.restore_cost is not None:
                new_card.restore_cost = max(0, self.restore_cost - change)
        keyword = UPGRADE_KEYWORD.get(self.card_id)
        if keyword:
            new_card._keywords = new_card._mask & ~keyword
        removed = UPGRADE_REMOVED_KEYWORD.get(self.card_id)
        if removed:
            new_card._keywords = new_card._mask | removed
        return new_card

    def upgraded_copy(self) -> Card:
        """A new, upgraded copy; the original is left alone because piles are shared between simulated states."""
        if not self.is_upgradable:
            raise ValueError(f"{self.name} cannot be upgraded")
        new_card = Card.create_copy(self)
        new_card.is_upgraded = True
        if not new_card.name.endswith("+"):
            new_card.name += "+"
        change = UPGRADE_COST_CHANGE.get(self.card_id, 0)
        if change and new_card.energy_cost != "X":
            # CardEnergyCost.UpgradeBy: base + change, Absolute modifiers (Confused) capped at it; this-turn offsets stay
            kept = self.restore_cost if self.restore_cost is not None else self.energy_cost
            upgraded = min(kept, UPGRADE_BASE_COST[self.card_id] + change)
            new_card.energy_cost = max(0, self.energy_cost - (kept - upgraded))
            if self.restore_cost is not None:
                new_card.restore_cost = upgraded
        keyword = UPGRADE_KEYWORD.get(self.card_id)
        if keyword:
            new_card._keywords = new_card._mask | keyword
        removed = UPGRADE_REMOVED_KEYWORD.get(self.card_id)
        if removed:
            new_card._keywords = new_card._mask & ~removed
        return new_card

    def on_turn_end_in_hand(self, combat : CombatSimulator):
        """End-of-turn effects of cards held in hand (before the Ethereal exhaust)."""
        card_id = self.card_id
        if card_id == CardId.INFECTION:
            combat.combat_state.player.apply_damage(INFECTION_DAMAGE)
        elif card_id == CardId.BURN:
            combat.combat_state.player.apply_damage(BURN_DAMAGE)
        elif card_id == CardId.BECKON:
            combat.combat_state.player.lose_hp(BECKON_HP_LOSS)        # Unblockable | Unpowered
        elif card_id == CardId.WITHER:
            combat.combat_state.player.apply_damage(WITHER_DAMAGE * (1 + self.wither_level))
        elif card_id == CardId.TOXIC:
            combat.combat_state.player.apply_damage(TOXIC_DAMAGE)
        elif card_id in HAND_CURSE_EFFECTS:
            HAND_CURSE_EFFECTS[card_id](combat.combat_state.player)

    @classmethod
    def create_copy(cls, card : Card) -> Card:
        new_card = cls()
        new_card.card_id = card.card_id
        new_card.type = card.type
        new_card.name = card.name
        new_card.energy_cost = card.energy_cost
        new_card.target_type = card.target_type
        new_card.is_upgraded = card.is_upgraded
        new_card.is_unplayable = card.is_unplayable
        new_card.restore_cost = card.restore_cost
        new_card.until_played = card.until_played
        new_card.bonus_damage = card.bonus_damage
        new_card.replay = card.replay
        new_card.enchantment, new_card.enchant_amount, new_card.enchant_bonus = card.enchantment, card.enchant_amount, card.enchant_bonus
        new_card._keywords = card._keywords
        new_card.generated = card.generated
        new_card.dampened_from = card.dampened_from
        new_card.wither_level = card.wither_level
        new_card.bound = card.bound
        return new_card

    def signature(self) -> tuple:
        """Everything that decides how this card plays: two cards with equal signatures are interchangeable
        (the fields create_copy carries over, minus name/type/target which follow from the id)."""
        return (self.card_id, self.is_upgraded, self.energy_cost, self.is_unplayable, self.restore_cost, self.until_played,
                self.bonus_damage, self.replay, self.enchantment, self.enchant_amount, self.enchant_bonus, self._mask, self.generated, self.dampened_from is not None, self.wither_level, self.bound)

    def current_cost(self, player) -> int | str:
        """Energy cost now: the base cost plus Tangled on attacks."""
        if self.energy_cost == "X":
            return self.energy_cost
        if self.type == CardType.Skill and StatusId.CORRUPTION in player.status:
            return 0
        if self.type == CardType.Attack and StatusId.FREE_ATTACK in player.status and player.status[StatusId.FREE_ATTACK].amount > 0:
            return 0                # FreeAttackPower.TryModifyEnergyCostInCombatLate: the game shows these at 0
        cost = self.energy_cost if self.type != CardType.Attack else self.energy_cost + player.status_amount(StatusId.TANGLED)
        if player.relics and _SCARF in player.relics and free_by_relic(player):
            return 0                # Brilliant Scarf (TryModifyEnergyCostInCombatLate)
        return cost

    def play_card(self, combat : CombatSimulator, target_index : int, free : bool = False, x_value : int | None = None):
        """Play the card. Raises ValueError if it cannot be played; state is restored.
        A free play (auto-play) costs nothing but still consumes Free Attack (FreeAttackPower.BeforeCardPlayed)."""
        player = combat.combat_state.player
        if self.bound:
            player.bound_played = True      # BeforeCardPlayed
        energy = combat.combat_state.energy
        cost = 0 if free else self.current_cost(player)
        free_attack = player.status.get(StatusId.FREE_ATTACK)
        free_attack_amount = free_attack.amount if free_attack else 0
        play = GET_CARD_FUNCTION[self.card_id]
        saved = snapshot(player) if player.relics else None
        punch = player.status.get(StatusId.ONE_TWO_PUNCH) if self.type == CardType.Attack else None
        x = None
        counted = self.type == CardType.Attack or self.type == CardType.Skill
        if counted:
            player.plays_started_this_turn += 1         # CardPlayStarted: Nostalgia counts these

        try:
            extra = self._extra_plays(player, punch)
            if self.energy_cost == "X":
                x = energy + x_bonus(player) if player.relics else energy        # Chemical X
                if x_value is not None:
                    x = x_value             # a dupe keeps the X of the card it copies
                combat.card_x = x
                spent = 0 if free else energy
                if saved:
                    before_card_played(combat, self, spent)
                if not free:
                    combat.combat_state.energy = 0
                play(self, combat, target_index, self.is_upgraded, x)
                self._enchantment_on_play(combat)
            else:
                spent = cost
                if self.type == CardType.Attack and free_attack_amount > 0:
                    free_attack.amount -= 1
                    combat.combat_state.energy += cost
                    spent = 0
                if saved:
                    before_card_played(combat, self, spent)
                combat.combat_state.energy -= cost
                play(self, combat, target_index, self.is_upgraded)
                self._enchantment_on_play(combat)
        except ValueError:
            combat.combat_state.energy = energy
            if self.bound:
                player.bound_played = False
            if counted:
                player.plays_started_this_turn -= 1
            if free_attack:
                free_attack.amount = free_attack_amount
            if saved:
                restore(player, saved)
            combat.vigor_pending = None
            if punch is not None:
                punch.amount += 1
                player.status[StatusId.ONE_TWO_PUNCH] = punch
            raise
        combat.finish_vigor()

        for _ in range(extra):
            combat.card_played_hooks(self)          # AfterCardPlayed of the previous play
            if not any(e.current_hp > 0 for e in combat.combat_state.enemies):
                break
            if saved:
                before_card_played(combat, self, spent)
            self._replay(combat, target_index, x)
            combat.finish_vigor()           # each play is its own attack command

    def _enchantment_on_play(self, combat : CombatSimulator):
        """EnchantmentModel.OnPlay: after the card's own effects, once for every play (replays included)."""
        enchantment = self.enchantment
        if enchantment is None:
            return
        player = combat.combat_state.player
        amount = self.enchant_amount
        if enchantment == EnchantmentId.ADROIT:
            _gain_block(combat, amount)
        elif enchantment == EnchantmentId.CORRUPTED:
            player.lose_hp(ENCHANT_CORRUPTED_HP_LOSS)
        elif enchantment == EnchantmentId.MOMENTUM:
            self.enchant_bonus += amount
        elif enchantment == EnchantmentId.GLAM:
            self._keywords = self._mask & ~_REPLAY          # Replay is spent
        elif enchantment == EnchantmentId.GOOPY:
            self.enchant_amount += 1                        # the amount is the card's permanent block gain + 1
        elif enchantment in CONSUMED_ON_PLAY and amount > 0:    # spent: the game keeps the enchantment with amount 0
            if enchantment == EnchantmentId.SWIFT:
                player.draw_cards(amount)
            elif enchantment == EnchantmentId.SOWN:
                combat.gain_energy(ENCHANT_SOWN_ENERGY)
            self.enchant_amount = 0

    def _extra_plays(self, player, punch) -> int:
        """CardModel.GeneratePlayCount: One-Two Punch (decremented), Throwing Axe. Before the first play."""
        extra = 0
        if punch is not None:
            extra += 1
            punch.amount -= 1
            if punch.amount <= 0:
                del player.status[StatusId.ONE_TWO_PUNCH]
        extra += self.replay
        if StatusId.DUPLICATOR in player.status:        # Duplicator Potion: the next card this turn, once
            extra += 1
            del player.status[StatusId.DUPLICATOR]
        if self._mask & _REPLAY:        # Replay 1 (Glam); it is spent after this play, but this count is fixed before it
            extra += 1
        if player.relics and _AXE in player.relics:
            extra += extra_plays(player)
        return extra

    def _replay(self, combat : CombatSimulator, target_index : int, x):
        """A further play (each fires Before/AfterCardPlayed); a dead target's effect is skipped."""
        if self.target_type == TargetType.AnyEnemy and combat.combat_state.enemies[target_index].current_hp <= 0:
            return
        if self.type == CardType.Attack or self.type == CardType.Skill:
            combat.combat_state.player.plays_started_this_turn += 1
        if x is None:
            GET_CARD_FUNCTION[self.card_id](self, combat, target_index, self.is_upgraded)
        else:
            GET_CARD_FUNCTION[self.card_id](self, combat, target_index, self.is_upgraded, x)
        self._enchantment_on_play(combat)

    def can_play_card(self, combat : CombatSimulator, target_index):
        if self.is_unplayable or self.unplayable:
            return False
        if self.type == CardType.Skill and combat.combat_state.player.smogged:
            return False            # Smoggy: afflicted with Smog
        if self.bound and combat.combat_state.player.bound_played:
            return False            # Chains of Binding: one Bound card a turn
        if StatusId.RINGING in combat.combat_state.player.status and combat.combat_state.cards_played >= 1:
            return False
        sloth = combat.combat_state.player.status.get(StatusId.SLOTH)
        if sloth is not None and combat.combat_state.cards_played >= sloth.amount:
            return False            # Sloth: at most this many cards a turn
        if combat.combat_state.cards_played >= NORMALITY_CARD_LIMIT and any(c.card_id == CardId.NORMALITY for c in combat.combat_state.player.hand):
            return False            # Normality: at most 3 cards a turn while it is in hand
        if combat.combat_state.player.relics and _CHOKER in combat.combat_state.player.relics and blocks_play(combat.combat_state.player):
            return False            # Velvet Choker
        if type(self.energy_cost) is str and self.energy_cost == "X":
            return True
        if self.type == CardType.Attack and StatusId.FREE_ATTACK in combat.combat_state.player.status:
            if combat.combat_state.player.status[StatusId.FREE_ATTACK].amount > 0:
                return True
        if self.current_cost(combat.combat_state.player) <= combat.combat_state.energy:
            return True
        return False

_SCARF, _CHOKER, _AXE = RelicId.BRILLIANT_SCARF, RelicId.VELVET_CHOKER, RelicId.THROWING_AXE

###
### Helpers
###

def _enemy(combat : CombatSimulator, target_index : int) -> Enemy:
    if not 0 <= target_index < len(combat.combat_state.enemies):
        raise ValueError(f"Target index {target_index} out of bounds")
    return combat.combat_state.enemies[target_index]

def _living(combat : CombatSimulator) -> list[Enemy]:
    return [e for e in combat.combat_state.enemies if e.current_hp > 0]

def _attack(combat : CombatSimulator, base : int, target : Creature, hits : int = 1):
    owner = combat.combat_state.player
    card = combat.card_in_play
    if card is not None and card.enchantment is not None:
        base = _enchanted_damage(card, base)
    base += combat.vigor_bonus()
    recompute = None
    if hits > 1 and RelicId.HAND_DRILL in owner.relics:     # a broken block makes later hits Vulnerable
        recompute = lambda: combat.calculate_damage(base, owner, target)
    target.apply_attack_damage(combat.calculate_damage(base, owner, target), owner, hits, recompute)

def _enchanted_damage(card : Card, base):
    """A card's damage enchantment, before Strength and the other modifiers (a float: Corrupted halves are kept)."""
    enchantment = card.enchantment
    if enchantment == EnchantmentId.CORRUPTED:
        return base * ENCHANT_CORRUPTED_DAMAGE
    if enchantment == EnchantmentId.INSTINCT:
        return base * ENCHANT_INSTINCT_DAMAGE
    if enchantment == EnchantmentId.SHARP or enchantment == EnchantmentId.VIGOROUS:
        return base + card.enchant_amount
    if enchantment == EnchantmentId.MOMENTUM:
        return base + card.enchant_bonus
    if enchantment == EnchantmentId.TEZCATARAS_EMBER:
        return base + ENCHANT_EMBER_DAMAGE
    return base

def owner_has_fasten(combat : CombatSimulator, card : Card | None) -> bool:
    """FastenPower.ModifyBlockAdditive: only Defends get the extra block."""
    return card is not None and card.card_id in DEFEND_CARDS and StatusId.FASTEN in combat.combat_state.player.status

def _gain_block(combat : CombatSimulator, base : int):
    card = combat.card_in_play
    if card is not None and card.enchantment == EnchantmentId.NIMBLE:      # adds to the card's own Block, before Dexterity and Frail
        base += card.enchant_amount
    elif card is not None and card.enchantment == EnchantmentId.GOOPY:    # printed block + permanent gains
        base += card.enchant_amount - 1
    if owner_has_fasten(combat, card):
        base += combat.combat_state.player.status_amount(StatusId.FASTEN)
    # Unmovable: doubled while gains from *other* plays this turn < amount (UnmovablePower)
    owner = combat.combat_state.player
    play = combat.play_id
    same_play = play is not None and owner.block_play == play
    from_other_plays = owner.card_blocks_this_turn - (owner.block_play_gains if same_play else 0)
    doubled = from_other_plays < owner.status_amount(StatusId.UNMOVABLE)
    owner.card_blocks_this_turn += 1
    if same_play:
        owner.block_play_gains += 1
    else:
        owner.block_play, owner.block_play_gains = play, 1
    multiplier = 2 if doubled else 1
    if card is not None and StatusId.NO_BLOCK in owner.status:      # NoBlockPower: block from cards (not unpowered block) is nothing
        multiplier = 0
    if owner.relics:
        multiplier *= block_multiplier(owner, combat.card_in_play)     # Vambrace
    block = combat.calculate_block(base, owner, multiplier)
    if owner.relics:
        block_gained(owner, combat.card_in_play, block)
    combat.gain_block(owner, block)
    return block

def _vulnerable(combat : CombatSimulator, target : Creature, amount : int):
    player = combat.combat_state.player
    before = target.status_amount(StatusId.VULNERABLE)
    if player.relics:
        amount *= debuff_multiplier(player, combat.card_in_play, target)      # Unsettling Lamp
    target.apply_status(StatusId.VULNERABLE, amount)
    if target.status_amount(StatusId.VULNERABLE) > before:      # Vicious: not if Artifact stopped it
        player.draw_cards(player.status_amount(StatusId.VICIOUS))

def _temp_strength(target : Creature, marker : StatusId, amount : int, sign : int, combat : CombatSimulator | None = None):
    """Strength that is taken back when the target's turn ends (Setup Strike, Mangle). `sign` is -1 for a loss."""
    if sign < 0 and combat is not None and combat.combat_state.player.relics:
        amount *= debuff_multiplier(combat.combat_state.player, combat.card_in_play, target)      # Unsettling Lamp doubles the marker, which doubles the Strength it takes
    before = target.status_amount(marker)
    target.apply_status(marker, amount)
    if target.status_amount(marker) == before:          # Artifact stopped the debuff
        return
    target.apply_status(StatusId.STRENGTH, sign * amount, bypass_artifact=True)

PLAIN_DAMAGE = {        # id : (damage, damage upgraded) of the cards that print one fixed number
    CardId.BYRD_SWOOP : (14, 18), CardId.PECK : (2, 2), CardId.EXTERMINATE : (3, 4), CardId.SQUASH : (10, 12),
    CardId.ANGER : (6, 8), CardId.BASH : (8, 10), CardId.BLUDGEON : (32, 42), CardId.BREAK : (20, 30),
    CardId.BREAKTHROUGH : (9, 13), CardId.CINDER : (18, 24), CardId.CONFLAGRATION : (2, 2),
    CardId.DISMANTLE : (8, 10), CardId.FEED : (10, 12), CardId.FIEND_FIRE : (7, 10), CardId.FIGHT_ME : (5, 6),
    CardId.GIANT_ROCK : (16, 20), CardId.HEADBUTT : (9, 12), CardId.HEMOKINESIS : (15, 20),
    CardId.HOWL_FROM_BEYOND : (16, 21), CardId.IRON_WAVE : (5, 7), CardId.MANGLE : (15, 20),
    CardId.FISTICUFFS : (7, 9), CardId.FLASH_OF_STEEL : (5, 8), CardId.HAND_OF_GREED : (20, 25), CardId.OMNISLICE : (8, 11),
    CardId.ULTIMATE_STRIKE : (14, 20), CardId.SEEKER_STRIKE : (9, 12), CardId.VOLLEY : (10, 14), CardId.DRAMATIC_ENTRANCE : (11, 15),
    CardId.MAUL : (5, 6), CardId.WHISTLE : (33, 44), CardId.MOLTEN_FIST : (10, 14), CardId.NEOWS_FURY : (10, 14), CardId.PACTS_END : (17, 23), CardId.PILLAGE : (6, 9), CardId.POMMEL_STRIKE : (9, 10),
    CardId.BOLAS : (3, 4), CardId.SALVO : (12, 16), CardId.THRUMMING_HATCHET : (11, 14), CardId.JACKPOT : (25, 30),
    CardId.SETUP_STRIKE : (7, 9), CardId.SPITE : (5, 5), CardId.STOMP : (12, 15), CardId.STRIKE_IRONCLAD : (6, 9),
    CardId.SWORD_BOOMERANG : (3, 3), CardId.TEAR_ASUNDER : (5, 7), CardId.THUNDERCLAP : (4, 7),
    CardId.TWIN_STRIKE : (5, 7), CardId.UNRELENTING : (14, 20), CardId.UPPERCUT : (13, 13), CardId.WHIRLWIND : (5, 8),
}

def _strikes(player : Player, in_play : Card | None = None) -> int:
    """Perfected Strike counts every Strike the player has in the fight: hand, draw, discard and exhaust piles
    (so generated and exhausted Strikes count), plus the card being played, which is out of the hand."""
    piles = player.hand + player.draw_pile + player.discard_pile + player.exhaust_pile
    return sum(c.is_strike for c in piles) + (1 if in_play is not None and in_play.is_strike else 0)

def _printed_damage(card : Card, combat : CombatSimulator) -> int:
    """The base damage an Attack in the hand would print right now (Thrash adds this to itself)."""
    player = combat.combat_state.player
    up = 1 if card.is_upgraded else 0
    if card.card_id == CardId.ASHEN_STRIKE:
        return 6 + (4 if up else 3) * len(player.exhaust_pile)
    if card.card_id == CardId.BODY_SLAM:
        return player.block
    if card.card_id == CardId.BULLY:
        return 4
    if card.card_id == CardId.PERFECTED_STRIKE:
        return 6 + (3 if up else 2) * _strikes(player)
    if card.card_id == CardId.RAMPAGE:
        return 9 + card.bonus_damage
    if card.card_id == CardId.MAUL:
        return (6 if up else 5) + card.bonus_damage
    if card.card_id == CardId.THRASH:
        return (6 if up else 4) + card.bonus_damage
    return PLAIN_DAMAGE[card.card_id][up]

###
### Card Functions, in alphabetical order
###

### Ancient cards that are not in the decompiled source: written from the cards' text

def play_abundance(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # three different Powers, Upgraded; the one picked joins the hand for free this turn (the game's own three are adopted)
    powers = [cid for cid, (_, card_type, _, _) in GENERATABLE_CARDS.items() if card_type == CardType.Power]
    combat.request_discovery([Card.create_generated(cid, True) for cid in rng.sample(powers, min(3, len(powers)))])

def play_apotheosis(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    for pile in (player.hand, player.draw_pile, player.discard_pile, player.exhaust_pile):
        for i, c in enumerate(pile):
            if c.is_upgradable:
                pile[i] = c.upgraded_copy()         # in place: a known top card stays where it is

def play_apparition(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.INTANGIBLE, 1)

def play_brightest_flame(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    amount = 3 if is_upgraded else 2
    combat.gain_energy(amount)
    player.draw_cards(amount)
    player.lose_max_hp(1)

def play_maul(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # `card` is this play's own copy; every Maul of the fight grows, in every pile
    target = _enemy(combat, target_index)
    _attack(combat, (6 if is_upgraded else 5) + card.bonus_damage, target, 2)
    step = 3 if is_upgraded else 2
    card.bonus_damage += step
    player = combat.combat_state.player
    for pile in (player.hand, player.draw_pile, player.discard_pile, player.exhaust_pile):
        for c in pile:
            if c.card_id == CardId.MAUL:
                c.bonus_damage += step

def play_relax(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 18 if is_upgraded else 16)
    player = combat.combat_state.player
    player.apply_status(StatusId.ENERGY_NEXT_TURN, 3 if is_upgraded else 2)
    player.apply_status(StatusId.DRAW_CARDS_NEXT_TURN, 3 if is_upgraded else 2)

def play_whistle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
    if target.current_hp > 0:
        target.stun()           # the move it was about to make comes after the stun

def play_wish(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    draw = combat.combat_state.player.draw_pile
    combat.request_choice("draw_to_hand", list(range(len(draw))), pile="draw")


def play_aggression(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.AGGRESSION, 1)

def play_anger(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    combat.combat_state.player.discard_pile.append(Card.create_copy(card))
    _attack(combat, 8 if is_upgraded else 6, target)

def play_armaments(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 5)
    player = combat.combat_state.player
    upgradable = [i for i, c in enumerate(player.hand) if c.is_upgradable]
    if is_upgraded:
        for i in upgradable:
            player.upgrade_card(player.hand[i])
    else:
        combat.request_choice("upgrade", upgradable)

def play_ashen_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    per_exhausted = 4 if is_upgraded else 3
    _attack(combat, 6 + per_exhausted * len(combat.combat_state.player.exhaust_pile), target)

def play_barricade(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if StatusId.BARRICADE not in player.status:
        player.apply_status(StatusId.BARRICADE, 1)

def play_bash(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 10 if is_upgraded else 8, target)
    _vulnerable(combat, target, 3 if is_upgraded else 2)

def play_battle_trance(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.draw_cards(4 if is_upgraded else 3)
    if StatusId.NO_DRAW not in player.status:       # it does not stack
        player.apply_status(StatusId.NO_DRAW, 1)

def play_blood_wall(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 20 if is_upgraded else 16)
    combat.combat_state.player.lose_hp(2)

def play_bloodletting(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.lose_hp(3)
    combat.gain_energy(3 if is_upgraded else 2)

def play_bludgeon(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 42 if is_upgraded else 32, target)

def play_body_slam(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, combat.combat_state.player.block, target)

def play_brand(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.lose_hp(1)
    if player.current_hp > 0:
        player.apply_status(StatusId.STRENGTH, 2 if is_upgraded else 1)     # before the pick; same result
        combat.request_choice("exhaust", list(range(len(player.hand))))

def play_break(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 30 if is_upgraded else 20, target)
    _vulnerable(combat, target, 7 if is_upgraded else 5)

def _lose_hp_first(combat : CombatSimulator, amount : int):
    """HP lost before the card's damage: Red Skull (at half HP) acts before the hit, not after the card."""
    combat.combat_state.player.lose_hp(amount)
    combat._sync_hp()

def play_breakthrough(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _lose_hp_first(combat, 1)
    for target in list(combat.combat_state.enemies):
        _attack(combat, 13 if is_upgraded else 9, target)

def play_bully(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    per_vulnerable = 3 if is_upgraded else 2
    _attack(combat, 4 + per_vulnerable * target.status_amount(StatusId.VULNERABLE), target)

def play_burning_pact(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    hand = combat.combat_state.player.hand
    combat.request_choice("exhaust", list(range(len(hand))), amount=3 if is_upgraded else 2)

def play_cascade(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    combat.auto_play_from_top(x + (1 if is_upgraded else 0))

def play_equilibrium(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 16 if is_upgraded else 13)
    combat.combat_state.player.apply_status(StatusId.RETAIN_HAND, 1)

def play_salvo(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], _enemy(combat, target_index))
    combat.combat_state.player.apply_status(StatusId.RETAIN_HAND, 1)

def play_panic_button(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 40 if is_upgraded else 30)
    combat.combat_state.player.apply_status(StatusId.NO_BLOCK, 2)       # after the block: this and the next turn's cards give none

def play_prolong(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if player.block > 0:
        player.apply_status(StatusId.BLOCK_NEXT_TURN, player.block)

def play_fasten(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.FASTEN, 6 if is_upgraded else 4)

def play_prep_time(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.PREP_TIME, 6 if is_upgraded else 4)

def play_dark_shackles(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _temp_strength(_enemy(combat, target_index), StatusId.DARK_SHACKLES, 15 if is_upgraded else 9, -1, combat)

def play_automation(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.add_instance(StatusId.AUTOMATION, [AUTOMATION_CARDS])

def play_panache(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.add_instance(StatusId.PANACHE, [PANACHE_CARDS, 14 if is_upgraded else 10, 0])

def play_rolling_boulder(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.add_instance(StatusId.ROLLING_BOULDER, [10 if is_upgraded else 5])

def play_the_bomb(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.add_instance(StatusId.THE_BOMB, [3, 50 if is_upgraded else 40])

def play_the_gambit(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 75 if is_upgraded else 50)
    combat.combat_state.player.apply_status(StatusId.THE_GAMBIT, 1)

def play_mayhem(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.MAYHEM, 1)

def play_nostalgia(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.NOSTALGIA, 1)

def play_bolas(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], _enemy(combat, target_index))

def play_thrumming_hatchet(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], _enemy(combat, target_index))

def play_jackpot(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], _enemy(combat, target_index))
    for _ in range(3):      # CardFactory.GetForCombat: with repeats
        combat.combat_state.player.add_to_hand(Card.create_generated(rng.choice(ZERO_COST_POOL), is_upgraded))

def play_calamity(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.CALAMITY, 1)

def play_jack_of_all_trades(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for card_id in rng.sample(JACK_POOL, 2 if is_upgraded else 1):       # distinct
        combat.combat_state.player.add_to_hand(Card.create_generated(card_id))

def play_catastrophe(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.play_random_from_draw_pile(3 if is_upgraded else 2)

def play_beat_down(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    attacks = [c for c in player.discard_pile if c.type == CardType.Attack and not c.unplayable]
    combat._run_autoplay(rng.sample(attacks, min(len(attacks), 4 if is_upgraded else 3)))       # all chosen before the first is played; a card that asks for a pick holds the rest back

def play_anointed(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    rares = [c for c in player.draw_pile if c.card_id in RARE_CARDS]
    for pick in rng.sample(rares, min(len(rares), MAX_HAND_SIZE - len(player.hand))):
        player.remove_from_draw_pile(pick)
        player.hand.append(pick)

def play_discovery(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # CardFactory.GetDistinctForCombat: three different cards; the game shows its own three (see CombatState.adopt_offer)
    combat.request_discovery([Card.create_generated(card_id) for card_id in rng.sample(list(GENERATABLE_CARDS), 3)])

def play_entropy(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.ENTROPY, 1)

def play_alchemize(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Procure a random potion (never Fruit Juice); nothing happens when every potion slot is full."""
    from sts2_lite.potion import procure_random_potion, PotionId
    procure_random_potion(combat.combat_state.player, exclude=(PotionId.FRUIT_JUICE,))

def play_hidden_gem(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    # a playable card without Replay that is not a Curse; Attacks, Skills and Powers first
    candidates = [i for i, c in enumerate(player.draw_pile) if not c.unplayable and c.type != CardType.Curse and c.replay == 0 and not c.has_glam_replay]
    preferred = [i for i in candidates if player.draw_pile[i].type != CardType.Status]
    if not candidates:
        return
    i = rng.choice(preferred or candidates)
    gained = player.draw_pile[i].with_replay(3 if is_upgraded else 2)
    player.draw_pile[i] = gained            # in place: a known top card stays where it is

def play_cinder(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 24 if is_upgraded else 18, target)
    hand = combat.combat_state.player.hand
    if hand:
        victim = hand[0] if len(hand) == 1 else rng.choice(hand)
        combat.combat_state.player.exhaust_card(victim)
        combat.fire(EventType.CARD_EXHAUSTED, victim)

def play_colossus(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)
    combat.combat_state.player.apply_status(StatusId.COLOSSUS, 1)

def play_conflagration(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in _living(combat):
        _attack(combat, 2, target, 5 if is_upgraded else 4)

def play_corruption(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if StatusId.CORRUPTION not in player.status:
        player.apply_status(StatusId.CORRUPTION, 1)

def play_crimson_mantle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.apply_status(StatusId.CRIMSON_MANTLE, 10 if is_upgraded else 8)
    player.crimson_mantle_plays += 1        # self-damage per turn (CrimsonMantlePower.IncrementSelfDamage)

def play_cruelty(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.CRUELTY, 50 if is_upgraded else 25)

def play_dark_embrace(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.DARK_EMBRACE, 1)

def play_defend(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)

def play_demon_form(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.DEMON_FORM, 3 if is_upgraded else 2)

def play_dismantle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    hits = 2 if StatusId.VULNERABLE in target.status else 1
    _attack(combat, 10 if is_upgraded else 8, target, hits)

def play_dominate(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _vulnerable(combat, target, 2 if is_upgraded else 1)
    combat.combat_state.player.apply_status(StatusId.STRENGTH, target.status_amount(StatusId.VULNERABLE))

def play_drum_of_battle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.draw_cards(2)        # the energy comes when the card is exhausted

def play_evil_eye(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    gains = 2 if combat.combat_state.player.cards_exhausted_this_turn > 0 else 1
    for _ in range(gains):
        _gain_block(combat, 11 if is_upgraded else 8)

def play_expect_a_fight(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    combat.gain_energy(sum(1 for c in player.hand if c.type == CardType.Attack))
    player.apply_status(StatusId.NO_ENERGY_GAIN, 1)

def play_feed(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 12 if is_upgraded else 10, target)
    if target.current_hp <= 0 and StatusId.MINION not in target.status:
        gain = 4 if is_upgraded else 3
        player = combat.combat_state.player
        player.max_hp += gain
        player.current_hp += gain

def play_feel_no_pain(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.FEEL_NO_PAIN, 4 if is_upgraded else 3)

def play_fiend_fire(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    player = combat.combat_state.player
    exhausted = list(player.hand)
    for victim in exhausted:
        player.exhaust_card(victim)
        combat.fire(EventType.CARD_EXHAUSTED, victim)
    if exhausted:
        _attack(combat, 10 if is_upgraded else 7, target, len(exhausted))

def play_fight_me(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 6 if is_upgraded else 5, target, 2)
    combat.combat_state.player.apply_status(StatusId.STRENGTH, 4 if is_upgraded else 3)
    target.apply_status(StatusId.STRENGTH, 1)

def play_flame_barrier(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 16 if is_upgraded else 12)
    combat.combat_state.player.apply_status(StatusId.FLAME_BARRIER, 6 if is_upgraded else 4)

def play_forgotten_ritual(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    if combat.combat_state.player.cards_exhausted_this_turn > 0:
        combat.gain_energy(4 if is_upgraded else 3)

def play_giant_rock(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 20 if is_upgraded else 16, target)

def play_havoc(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if not player.draw_pile:
        player.shuffle_discard_into_draw()
    if not player.draw_pile:
        return
    top = player.draw_pile[-1]
    if player.known_top == 0:
        player.unknown_draws += 1   # the top card is unknown to the agent, so this is a chance event
    if top.unplayable:                          # CardCmd.AutoPlay skips only Unplayable
        player.exhaust_card(top)
        combat.fire(EventType.CARD_EXHAUSTED, top)
    else:
        combat.auto_play(top, force_exhaust=True)

def play_headbutt(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 12 if is_upgraded else 9, target)
    combat.request_choice("to_draw_pile", list(range(len(combat.combat_state.player.discard_pile))), pile="discard")

def play_neows_fury(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
    player = combat.combat_state.player
    discard = player.discard_pile
    combat.request_choice("to_hand", list(range(len(discard))), pile="discard", amount=NEOWS_FURY_CARDS[is_upgraded], source=card)

def play_hellraiser(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if StatusId.HELLRAISER not in player.status:
        player.apply_status(StatusId.HELLRAISER, 1)

def play_hemokinesis(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _lose_hp_first(combat, 2)
    _attack(combat, 20 if is_upgraded else 15, target)

def play_howl_from_beyond(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in _living(combat):
        _attack(combat, 21 if is_upgraded else 16, target)

def play_impervious(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 40 if is_upgraded else 30)

def play_infernal_blade(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    new_card = Card.create_generated(rng.choice(INFERNAL_BLADE_POOL)).free_this_turn()     # Whirlwind stays X
    combat.combat_state.player.add_to_hand(new_card)

def play_inferno(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.apply_status(StatusId.INFERNO, 9 if is_upgraded else 6)
    player.inferno_plays += 1

def play_inflame(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.STRENGTH, 3 if is_upgraded else 2)

def play_iron_wave(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _gain_block(combat, 7 if is_upgraded else 5)
    _attack(combat, 7 if is_upgraded else 5, target)

def play_juggernaut(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.JUGGERNAUT, 8 if is_upgraded else 6)

def play_juggling(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.JUGGLING, 1)

def play_luminesce(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_energy(3 if is_upgraded else 2)

def play_mangle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 20 if is_upgraded else 15, target)
    _temp_strength(target, StatusId.MANGLE, 15 if is_upgraded else 10, -1, combat)

def play_molten_fist(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 14 if is_upgraded else 10, target)
    vulnerable = target.status_amount(StatusId.VULNERABLE)
    if target.current_hp > 0 and vulnerable > 0:
        _vulnerable(combat, target, vulnerable)

def play_not_yet(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.current_hp = min(player.max_hp, player.current_hp + (13 if is_upgraded else 10))

def play_offering(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.lose_hp(6)
    if player.current_hp > 0:
        combat.gain_energy(2)
        player.draw_cards(5 if is_upgraded else 3)

def play_one_two_punch(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.ONE_TWO_PUNCH, 2 if is_upgraded else 1)

def play_pacts_end(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    if len(combat.combat_state.player.exhaust_pile) >= 3:
        for target in _living(combat):
            _attack(combat, 23 if is_upgraded else 17, target)

def play_perfected_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    strikes = _strikes(combat.combat_state.player, card)
    _attack(combat, 6 + (3 if is_upgraded else 2) * strikes, target)

def play_pillage(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 9 if is_upgraded else 6, target)
    player = combat.combat_state.player
    while True:                 # draw until something that is not an Attack comes up, or the hand is full
        drawn = player.draw_card()
        if drawn is None or drawn.type != CardType.Attack or len(player.hand) >= 10:
            break

def play_pommel_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 10 if is_upgraded else 9, target)
    combat.combat_state.player.draw_cards(2 if is_upgraded else 1)

def play_primal_force(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    hand = combat.combat_state.player.hand
    for i, c in enumerate(hand):
        if c.type == CardType.Attack:
            hand[i] = Card.create_generated(CardId.GIANT_ROCK, is_upgraded)

def play_pyre(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    energy = 2 if is_upgraded else 1
    combat.combat_state.player.apply_status(StatusId.PYRE, energy)
    combat.combat_state.max_energy += energy

def play_rage(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.RAGE, 5 if is_upgraded else 3)

def play_rampage(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # `card` is this play's own copy (see CombatSimulator.private_copy), so it can remember the growth
    target = _enemy(combat, target_index)
    _attack(combat, 9 + card.bonus_damage, target)
    card.bonus_damage += 9 if is_upgraded else 5

def play_rupture(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.RUPTURE, 2 if is_upgraded else 1)

def play_second_wind(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    for victim in [c for c in player.hand if c.type != CardType.Attack]:
        player.exhaust_card(victim)
        combat.fire(EventType.CARD_EXHAUSTED, victim)
        _gain_block(combat, 7 if is_upgraded else 5)

def play_setup_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 9 if is_upgraded else 7, target)
    _temp_strength(combat.combat_state.player, StatusId.SETUP_STRIKE, 3 if is_upgraded else 2, 1)

def play_shrug_it_off(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 11 if is_upgraded else 8)
    combat.combat_state.player.draw_cards(1)

def play_toxic(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    pass        # only its Exhaust keyword

def play_frantic_escape(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """One more turn before the Sandpit closes; every play costs one more energy for the rest of the fight."""
    for enemy in combat.combat_state.enemies:
        if StatusId.SANDPIT in enemy.status:
            enemy.status[StatusId.SANDPIT].amount += 1
    card.energy_cost += 1

def play_knowledge_curse(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    pass        # unplayable

def play_spore_mind(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    pass        # only its Exhaust keyword

def play_beckon(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    pass        # it does nothing; playing it only gets it out of the hand

def play_slimed(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.draw_card()

def play_spite(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    repeat = 3 if is_upgraded else 2
    _attack(combat, 5, target, repeat if combat.combat_state.player.lost_hp_this_turn else 1)

def play_stampede(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.STAMPEDE, 1)

def play_stoke(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    exhausted = list(player.hand)
    for victim in exhausted:
        player.exhaust_card(victim)
        combat.fire(EventType.CARD_EXHAUSTED, victim)
    for _ in exhausted:         # a random card (repeats allowed) for each one exhausted
        new_card = Card.create_generated(rng.choice(STOKE_POOL), is_upgraded)
        if new_card.type == CardType.Power and RelicId.SPIKED_GAUNTLETS in player.relics:
            new_card.energy_cost += 1       # the bridge shows Spiked Gauntlets' +1; a card made here has to add it
        player.add_to_hand(new_card)

def play_stomp(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in _living(combat):
        _attack(combat, 15 if is_upgraded else 12, target)

def play_stone_armor(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.PLATING, 6 if is_upgraded else 4)

def play_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 9 if is_upgraded else 6, target)

def play_sword_boomerang(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for _ in range(4 if is_upgraded else 3):
        living = _living(combat)
        if not living:
            break
        target = rng.pick_target(living)
        _attack(combat, 3, target)
        combat.resolve_deaths()

def play_taunt(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _gain_block(combat, 8 if is_upgraded else 7)
    _vulnerable(combat, target, 2 if is_upgraded else 1)

def play_tear_asunder(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    # one hit, and one more for every time the player has lost HP in this fight
    _attack(combat, 7 if is_upgraded else 5, target, 1 + combat.combat_state.player.hp_loss_events)

# ---- event cards
TORIC_TOUGHNESS_TURNS = 2
METAMORPHOSIS_CARDS = (3, 5)
ENLIGHTENMENT_COST = 1

def play_byrd_swoop(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], _enemy(combat, target_index))

def play_peck(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], _enemy(combat, target_index), 4 if is_upgraded else 3)

def play_exterminate(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for _ in range(4):                  # each hit goes to every living enemy
        for target in _living(combat):
            _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
        combat.resolve_deaths()

def play_squash(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
    _vulnerable(combat, target, 3 if is_upgraded else 2)

def play_enlightenment(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Cards in hand (this one is in play, not in hand): cost reduced to 1 this turn, or this combat if upgraded."""
    hand = combat.combat_state.player.hand
    for i, c in enumerate(hand):
        hand[i] = c.reduced_to(ENLIGHTENMENT_COST, this_combat=is_upgraded)

def play_metamorphosis(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """CardFactory.GetForCombat (repeats allowed): random Attacks from the pool, free this combat, each at a random place
    in the draw pile."""
    made = [Card.create_generated(rng.choice(INFERNAL_BLADE_POOL)).free_this_combat()
            for _ in range(METAMORPHOSIS_CARDS[is_upgraded])]
    for new_card in made:
        combat.combat_state.player.insert_into_draw_pile(new_card)

def play_toric_toughness(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Block now; the power gains that same (already modified) block, unpowered, after the block is cleared for 2 turns."""
    block = _gain_block(combat, 7 if is_upgraded else 5)
    combat.combat_state.player.add_instance(StatusId.TORIC_TOUGHNESS, [TORIC_TOUGHNESS_TURNS, block])

def play_thrash(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # `card` is this play's own copy (see CombatSimulator.private_copy), so it can remember the growth
    target = _enemy(combat, target_index)
    player = combat.combat_state.player
    _attack(combat, (6 if is_upgraded else 4) + card.bonus_damage, target, 2)
    attacks = [c for c in player.hand if c.type == CardType.Attack]
    if attacks:
        victim = attacks[0] if len(attacks) == 1 else rng.choice(attacks)
        from sts2_lite.creature import Creature      # card.py is imported by creature.py's package
        from sts2_lite.damage import modify_damage
        # relics read the victim, not Thrash (Thrash.OnPlay)
        card.bonus_damage += modify_damage(_printed_damage(victim, combat), player, Creature(), victim, in_play=False)
        player.exhaust_card(victim)
        combat.fire(EventType.CARD_EXHAUSTED, victim)

def play_thunderclap(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in list(combat.combat_state.enemies):
        _attack(combat, 7 if is_upgraded else 4, target)
        _vulnerable(combat, target, 1)

def play_tremble(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _vulnerable(combat, target, 4 if is_upgraded else 3)

def play_true_grit(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 9 if is_upgraded else 7)
    player = combat.combat_state.player
    hand = player.hand
    if is_upgraded:
        combat.request_choice("exhaust", list(range(len(hand))))
    elif hand:
        victim = hand[0] if len(hand) == 1 else rng.choice(hand)
        player.exhaust_card(victim)
        combat.fire(EventType.CARD_EXHAUSTED, victim)

def play_twin_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 7 if is_upgraded else 5, target, 2)

def play_unmovable(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.UNMOVABLE, 1)

def play_unrelenting(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 20 if is_upgraded else 14, target)
    combat.combat_state.player.apply_status(StatusId.FREE_ATTACK, 1)

def play_uppercut(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, 13, target)
    debuff = 2 if is_upgraded else 1
    player = combat.combat_state.player
    target.apply_status(StatusId.WEAK, debuff * debuff_multiplier(player, combat.card_in_play, target) if player.relics else debuff)
    _vulnerable(combat, target, debuff)

def play_vicious(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.VICIOUS, 2 if is_upgraded else 1)

def play_whirlwind(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    for _ in range(x):
        for target in _living(combat):
            _attack(combat, 8 if is_upgraded else 5, target)
        combat.resolve_deaths()

###
### map to get function from card id
###

# ---------------------------------------------------------------- colorless
MAX_HAND_SIZE = 10

def play_finesse(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 7 if is_upgraded else 4)
    combat.combat_state.player.draw_cards(1)

def play_flash_of_steel(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], _enemy(combat, target_index))
    combat.combat_state.player.draw_cards(1)

def play_ultimate_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], _enemy(combat, target_index))

def play_ultimate_defend(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 15 if is_upgraded else 11)

def play_production(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_energy(3 if is_upgraded else 2)

def play_master_of_strategy(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.draw_cards(4 if is_upgraded else 3)

def play_dramatic_entrance(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in list(combat.combat_state.enemies):
        _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)

def play_shockwave(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    amount = 5 if is_upgraded else 3
    for target in _living(combat):
        target.apply_status(StatusId.WEAK, amount * debuff_multiplier(player, combat.card_in_play, target) if player.relics else amount)
        _vulnerable(combat, target, amount)

def play_prowess(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.apply_status(StatusId.STRENGTH, 2 if is_upgraded else 1)
    player.apply_status(StatusId.DEXTERITY, 2 if is_upgraded else 1)

def play_impatience(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if not any(c.type == CardType.Attack for c in player.hand):
        player.draw_cards(3 if is_upgraded else 2)

def play_restlessness(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if not player.hand:         # the card being played has left the hand
        player.draw_cards(3 if is_upgraded else 2)
        combat.gain_energy(3 if is_upgraded else 2)

def play_scrawl(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.draw_cards(MAX_HAND_SIZE - len(player.hand))

def play_fisticuffs(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    before = target.damage_taken
    _attack(combat, 9 if is_upgraded else 7, target)
    dealt = target.damage_taken - before
    if dealt > 0:
        _gain_block(combat, dealt)       # powered block: Dexterity and Frail apply

def play_mind_blast(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, len(combat.combat_state.player.draw_pile), _enemy(combat, target_index))

def play_gold_axe(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, combat.combat_state.player.cards_played_total, _enemy(combat, target_index))

def play_rend(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    debuffs = sum(1 for status_id, inst in target.status.items() if is_debuff(status_id, inst.amount) and status_id not in (StatusId.MANGLE, StatusId.DARK_SHACKLES))
    _attack(combat, (18 if is_upgraded else 15) + (8 if is_upgraded else 5) * debuffs, target)    # temporary debuffs do not count

def play_omnislice(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    before = target.damage_taken
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
    dealt = target.damage_taken - before
    if dealt > 0:       # the rest take what the first hit dealt, unpowered (no Strength or Vulnerable)
        for other in _living(combat):
            if other is not target:
                other.apply_damage(dealt, combat.combat_state.player)

def play_volley(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    for _ in range(x):
        living = _living(combat)
        if not living:
            break
        _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], rng.pick_target(living))
        combat.resolve_deaths()

def play_eternal_armor(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.PLATING, 12 if is_upgraded else 9)

def play_hand_of_greed(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _enemy(combat, target_index)
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
    if target.current_hp <= 0 and StatusId.MINION not in target.status:
        combat.combat_state.player.gold += 25 if is_upgraded else 20

def play_purity(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    hand = combat.combat_state.player.hand
    combat.request_choice("exhaust_any", list(range(len(hand))), amount=5 if is_upgraded else 3)

def _pick_from_draw_pile(combat : CombatSimulator, card_type : CardType):
    """Secret Technique / Secret Weapon: take a Skill / Attack of your choice from the draw pile."""
    draw = combat.combat_state.player.draw_pile
    combat.request_choice("draw_to_hand", [i for i, c in enumerate(draw) if c.type == card_type], pile="draw")

def play_secret_technique(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _pick_from_draw_pile(combat, CardType.Skill)

def play_secret_weapon(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _pick_from_draw_pile(combat, CardType.Attack)

SEEKER_STRIKE_OPTIONS = 3

def play_seeker_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], _enemy(combat, target_index))
    draw = combat.combat_state.player.draw_pile
    if draw:        # three random cards of the draw pile (the game's own three are adopted when its screen appears)
        offered = rng.sample(range(len(draw)), min(SEEKER_STRIKE_OPTIONS, len(draw)))
        combat.request_choice("draw_to_hand", offered, pile="draw", hidden=True)

def play_thinking_ahead(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.draw_cards(2)
    combat.request_choice("to_draw_pile", list(range(len(player.hand))), pile="hand")

GET_CARD_FUNCTION : dict[CardId, function] = {
    CardId.ABUNDANCE : play_abundance,
    CardId.AGGRESSION : play_aggression,
    CardId.ALCHEMIZE : play_alchemize,
    CardId.ANGER : play_anger,
    CardId.ANOINTED : play_anointed,
    CardId.APOTHEOSIS : play_apotheosis,
    CardId.APPARITION : play_apparition,
    CardId.ARMAMENTS : play_armaments,
    CardId.ASHEN_STRIKE : play_ashen_strike,
    CardId.AUTOMATION : play_automation,
    CardId.BARRICADE : play_barricade,
    CardId.BASH : play_bash,
    CardId.BATTLE_TRANCE : play_battle_trance,
    CardId.BEAT_DOWN : play_beat_down,
    CardId.BECKON : play_beckon,
    CardId.BLOODLETTING : play_bloodletting,
    CardId.BLOOD_WALL : play_blood_wall,
    CardId.BLUDGEON : play_bludgeon,
    CardId.BODY_SLAM : play_body_slam,
    CardId.BOLAS : play_bolas,
    CardId.BRAND : play_brand,
    CardId.BREAK : play_break,
    CardId.BREAKTHROUGH : play_breakthrough,
    CardId.BRIGHTEST_FLAME : play_brightest_flame,
    CardId.BULLY : play_bully,
    CardId.BURNING_PACT : play_burning_pact,
    CardId.BYRD_SWOOP : play_byrd_swoop,
    CardId.CALAMITY : play_calamity,
    CardId.CASCADE : play_cascade,
    CardId.CATASTROPHE : play_catastrophe,
    CardId.CINDER : play_cinder,
    CardId.COLOSSUS : play_colossus,
    CardId.CONFLAGRATION : play_conflagration,
    CardId.CORRUPTION : play_corruption,
    CardId.CRIMSON_MANTLE : play_crimson_mantle,
    CardId.CRUELTY : play_cruelty,
    CardId.DARK_EMBRACE : play_dark_embrace,
    CardId.DARK_SHACKLES : play_dark_shackles,
    CardId.DEFEND_IRONCLAD : play_defend,
    CardId.DEMON_FORM : play_demon_form,
    CardId.DISCOVERY : play_discovery,
    CardId.DISINTEGRATION : play_knowledge_curse,
    CardId.DISMANTLE : play_dismantle,
    CardId.DOMINATE : play_dominate,
    CardId.DRAMATIC_ENTRANCE : play_dramatic_entrance,
    CardId.DRUM_OF_BATTLE : play_drum_of_battle,
    CardId.ENLIGHTENMENT : play_enlightenment,
    CardId.ENTROPY : play_entropy,
    CardId.EQUILIBRIUM : play_equilibrium,
    CardId.ETERNAL_ARMOR : play_eternal_armor,
    CardId.EVIL_EYE : play_evil_eye,
    CardId.EXPECT_A_FIGHT : play_expect_a_fight,
    CardId.EXTERMINATE : play_exterminate,
    CardId.FASTEN : play_fasten,
    CardId.FEED : play_feed,
    CardId.FEEL_NO_PAIN : play_feel_no_pain,
    CardId.FIEND_FIRE : play_fiend_fire,
    CardId.FIGHT_ME : play_fight_me,
    CardId.FINESSE : play_finesse,
    CardId.FISTICUFFS : play_fisticuffs,
    CardId.FLAME_BARRIER : play_flame_barrier,
    CardId.FLASH_OF_STEEL : play_flash_of_steel,
    CardId.FORGOTTEN_RITUAL : play_forgotten_ritual,
    CardId.FRANTIC_ESCAPE : play_frantic_escape,
    CardId.GIANT_ROCK : play_giant_rock,
    CardId.GOLD_AXE : play_gold_axe,
    CardId.HAND_OF_GREED : play_hand_of_greed,
    CardId.HAVOC : play_havoc,
    CardId.HEADBUTT : play_headbutt,
    CardId.HELLRAISER : play_hellraiser,
    CardId.HEMOKINESIS : play_hemokinesis,
    CardId.HIDDEN_GEM : play_hidden_gem,
    CardId.HOWL_FROM_BEYOND : play_howl_from_beyond,
    CardId.IMPATIENCE : play_impatience,
    CardId.IMPERVIOUS : play_impervious,
    CardId.INFERNAL_BLADE : play_infernal_blade,
    CardId.INFERNO : play_inferno,
    CardId.INFLAME : play_inflame,
    CardId.IRON_WAVE : play_iron_wave,
    CardId.JACKPOT : play_jackpot,
    CardId.JACK_OF_ALL_TRADES : play_jack_of_all_trades,
    CardId.JUGGERNAUT : play_juggernaut,
    CardId.JUGGLING : play_juggling,
    CardId.LUMINESCE : play_luminesce,
    CardId.MANGLE : play_mangle,
    CardId.MASTER_OF_STRATEGY : play_master_of_strategy,
    CardId.MAUL : play_maul,
    CardId.MAYHEM : play_mayhem,
    CardId.METAMORPHOSIS : play_metamorphosis,
    CardId.MIND_BLAST : play_mind_blast,
    CardId.MIND_ROT : play_knowledge_curse,
    CardId.MOLTEN_FIST : play_molten_fist,
    CardId.NEOWS_FURY : play_neows_fury,
    CardId.NOSTALGIA : play_nostalgia,
    CardId.NOT_YET : play_not_yet,
    CardId.OFFERING : play_offering,
    CardId.OMNISLICE : play_omnislice,
    CardId.ONE_TWO_PUNCH : play_one_two_punch,
    CardId.PACTS_END : play_pacts_end,
    CardId.PANACHE : play_panache,
    CardId.PANIC_BUTTON : play_panic_button,
    CardId.PECK : play_peck,
    CardId.PERFECTED_STRIKE : play_perfected_strike,
    CardId.PILLAGE : play_pillage,
    CardId.POMMEL_STRIKE : play_pommel_strike,
    CardId.PREP_TIME : play_prep_time,
    CardId.PRIMAL_FORCE : play_primal_force,
    CardId.PRODUCTION : play_production,
    CardId.PROLONG : play_prolong,
    CardId.PROWESS : play_prowess,
    CardId.PURITY : play_purity,
    CardId.PYRE : play_pyre,
    CardId.RAGE : play_rage,
    CardId.RAMPAGE : play_rampage,
    CardId.RELAX : play_relax,
    CardId.REND : play_rend,
    CardId.RESTLESSNESS : play_restlessness,
    CardId.ROLLING_BOULDER : play_rolling_boulder,
    CardId.RUPTURE : play_rupture,
    CardId.SALVO : play_salvo,
    CardId.SCRAWL : play_scrawl,
    CardId.SECOND_WIND : play_second_wind,
    CardId.SECRET_TECHNIQUE : play_secret_technique,
    CardId.SECRET_WEAPON : play_secret_weapon,
    CardId.SEEKER_STRIKE : play_seeker_strike,
    CardId.SETUP_STRIKE : play_setup_strike,
    CardId.SHOCKWAVE : play_shockwave,
    CardId.SHRUG_IT_OFF : play_shrug_it_off,
    CardId.SLIMED : play_slimed,
    CardId.SLOTH : play_knowledge_curse,
    CardId.SPITE : play_spite,
    CardId.SPORE_MIND : play_spore_mind,
    CardId.SQUASH : play_squash,
    CardId.STAMPEDE : play_stampede,
    CardId.STOKE : play_stoke,
    CardId.STOMP : play_stomp,
    CardId.STONE_ARMOR : play_stone_armor,
    CardId.STRIKE_IRONCLAD : play_strike,
    CardId.SWORD_BOOMERANG : play_sword_boomerang,
    CardId.TAUNT : play_taunt,
    CardId.TEAR_ASUNDER : play_tear_asunder,
    CardId.THE_BOMB : play_the_bomb,
    CardId.THE_GAMBIT : play_the_gambit,
    CardId.THINKING_AHEAD : play_thinking_ahead,
    CardId.THRASH : play_thrash,
    CardId.THRUMMING_HATCHET : play_thrumming_hatchet,
    CardId.THUNDERCLAP : play_thunderclap,
    CardId.TORIC_TOUGHNESS : play_toric_toughness,
    CardId.TOXIC : play_toxic,
    CardId.TREMBLE : play_tremble,
    CardId.TRUE_GRIT : play_true_grit,
    CardId.TWIN_STRIKE : play_twin_strike,
    CardId.ULTIMATE_DEFEND : play_ultimate_defend,
    CardId.ULTIMATE_STRIKE : play_ultimate_strike,
    CardId.UNMOVABLE : play_unmovable,
    CardId.UNRELENTING : play_unrelenting,
    CardId.UPPERCUT : play_uppercut,
    CardId.VICIOUS : play_vicious,
    CardId.VOLLEY : play_volley,
    CardId.WASTE_AWAY : play_knowledge_curse,
    CardId.WHIRLWIND : play_whirlwind,
    CardId.WHISTLE : play_whistle,
    CardId.WISH : play_wish,
}

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

GENERATED_CARDS = {
    CardId.SLIMED : Card.create_slimed,
    CardId.INFECTION : Card.create_infection,
    CardId.BURN : Card.create_burn,
    CardId.BECKON : Card.create_beckon,
    CardId.WITHER : Card.create_wither,
    CardId.DAZED : Card.create_dazed,
    CardId.WOUND : Card.create_wound,
    CardId.SOOT : Card.create_soot,
    CardId.TOXIC : Card.create_toxic,
    CardId.FRANTIC_ESCAPE : Card.create_frantic_escape,
}
for _curse in (CardId.DISINTEGRATION, CardId.MIND_ROT, CardId.SLOTH, CardId.WASTE_AWAY):
    GENERATED_CARDS[_curse] = lambda _curse=_curse: Card.create_knowledge_curse(_curse)
for _curse in CURSE_CARDS:
    GENERATED_CARDS[_curse] = lambda _curse=_curse: Card.create_curse(_curse)
