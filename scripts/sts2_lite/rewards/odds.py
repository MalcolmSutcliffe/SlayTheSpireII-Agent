"""Card rarity odds: `CardRarityOdds` of the game, rolled with the sandbox's own rng (never the game's).

The rarity offset starts at -0.05 and grows by 0.01 for every card rolled with `roll` (0.005 at Scarcity, ascension 7), up to 0.4. It is added to the
rare odds of the roll, and a rare card resets it. Rolls that do not change the future odds (`roll_with_base_odds`, `roll_without_changing_future_odds`)
leave it alone. The numbers below are those of CardRarityOdds.cs."""
from __future__ import annotations

from enum import Enum, auto

SCARCITY_ASCENSION = 7
BASE_RARITY_OFFSET = -0.05
MAX_RARITY_OFFSET = 0.4


class Rarity(Enum):
    NONE = auto()
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()

    def next_highest_with_wrapping(self) -> "Rarity":
        """Common -> Uncommon -> Rare -> Common (CardRarityExtensions.GetNextHighestRarityWithWrapping)."""
        return {Rarity.NONE: Rarity.NONE, Rarity.COMMON: Rarity.UNCOMMON, Rarity.UNCOMMON: Rarity.RARE, Rarity.RARE: Rarity.COMMON}[self]


class OddsType(Enum):
    """CardRarityOddsType."""
    NONE = auto()
    REGULAR_ENCOUNTER = auto()
    ELITE_ENCOUNTER = auto()
    BOSS_ENCOUNTER = auto()
    SHOP = auto()
    UNIFORM = auto()


class Source(Enum):
    """CardCreationSource: where a card reward comes from. Only encounter rewards change the future odds."""
    NONE = auto()
    ENCOUNTER = auto()
    SHOP = auto()
    OTHER = auto()


ENCOUNTER_ODDS = (OddsType.REGULAR_ENCOUNTER, OddsType.ELITE_ENCOUNTER, OddsType.BOSS_ENCOUNTER)


def _scarce(ascension : int, scarce, normal):
    return scarce if ascension >= SCARCITY_ASCENSION else normal


def base_odds(odds_type : OddsType, rarity : Rarity, ascension : int = 0) -> float:
    """CardRarityOdds.GetBaseOdds. The uncommon number is the width of the uncommon band when rolled with the offset, and the end of it when rolled
    with the base odds only (see `roll_with_base_odds`)."""
    if odds_type == OddsType.ELITE_ENCOUNTER:
        return {Rarity.COMMON: _scarce(ascension, 0.549, 0.5), Rarity.UNCOMMON: 0.4, Rarity.RARE: _scarce(ascension, 0.05, 0.1)}[rarity]
    if odds_type == OddsType.BOSS_ENCOUNTER:
        return {Rarity.COMMON: 0.0, Rarity.UNCOMMON: 0.0, Rarity.RARE: 1.0}[rarity]
    if odds_type == OddsType.SHOP:
        return {Rarity.COMMON: _scarce(ascension, 0.585, 0.54), Rarity.UNCOMMON: 0.37, Rarity.RARE: _scarce(ascension, 0.045, 0.09)}[rarity]
    if odds_type == OddsType.REGULAR_ENCOUNTER:
        return {Rarity.COMMON: _scarce(ascension, 0.615, 0.6), Rarity.UNCOMMON: 0.37, Rarity.RARE: _scarce(ascension, 0.0149, 0.03)}[rarity]
    if odds_type == OddsType.UNIFORM:
        return 0.33
    raise ValueError(odds_type)


class CardRarityOdds:
    """The player's card rarity state. `rng` needs only `random()`: a `random.Random` works."""
    def __init__(self, rng, ascension : int = 0, current_value : float = BASE_RARITY_OFFSET):
        self.rng = rng
        self.ascension = ascension
        self.current_value = current_value

    @property
    def growth(self) -> float:
        return _scarce(self.ascension, 0.005, 0.01)

    def roll(self, odds_type : OddsType) -> Rarity:
        """A rarity that moves the future odds (end-of-combat rewards). A boss reward is rolled with no offset, but still moves it."""
        rarity = self._roll(odds_type, 0.0 if odds_type == OddsType.BOSS_ENCOUNTER else self.current_value)
        if rarity == Rarity.RARE:
            self.current_value = BASE_RARITY_OFFSET
        else:
            self.current_value = min(self.current_value + self.growth, MAX_RARITY_OFFSET)
        return rarity

    def roll_without_changing_future_odds(self, odds_type : OddsType, offset : float | None = None) -> Rarity:
        """The shop's cards: the current offset applies, nothing changes."""
        return self._roll(odds_type, self.current_value if offset is None else offset)

    def roll_with_base_odds(self, odds_type : OddsType) -> Rarity:
        """Events and relics: no offset and no change. The uncommon band is [rare, rare + uncommon) (it was [rare, uncommon) before v0.111)."""
        x = self.rng.random()
        rare = base_odds(odds_type, Rarity.RARE, self.ascension)
        if x < rare:
            return Rarity.RARE
        if x < base_odds(odds_type, Rarity.UNCOMMON, self.ascension) + rare:
            return Rarity.UNCOMMON
        return Rarity.COMMON

    def _roll(self, odds_type : OddsType, offset : float) -> Rarity:
        x = self.rng.random()
        rare_edge = base_odds(odds_type, Rarity.RARE, self.ascension) + offset
        if x < rare_edge:
            return Rarity.RARE
        if x < base_odds(odds_type, Rarity.UNCOMMON, self.ascension) + rare_edge:
            return Rarity.UNCOMMON
        return Rarity.COMMON
