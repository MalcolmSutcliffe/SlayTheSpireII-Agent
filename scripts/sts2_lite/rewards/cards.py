"""Card rewards: `CardFactory.CreateForReward` and the merchant's card creation, with the sandbox's own rng.

What is not modelled yet: relics and events that change a reward (extra or fewer cards, upgraded cards, a different pool, rerolls), and the
multiplayer-only cards (Tank and Demonic Shield are not in the engine). Unlocks are ignored: every card is available."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from sts2_lite.card.ids import CardId
from sts2_lite.card.tables import CARD_RARITY, DEFECT_CARDS, GENERATABLE_CARDS, NECROBINDER_CARDS, REGENT_CARDS, SILENT_CARDS
from sts2_lite.rewards.odds import ENCOUNTER_ODDS, CardRarityOdds, OddsType, Rarity, Source, SCARCITY_ASCENSION

REWARD_RARITIES = ("Common", "Uncommon", "Rare")
NEVER_UPGRADES = -999999999.0       # the merchant rolls an upgrade, and never gets one


def _ironclad_pool() -> dict[str, tuple[CardId, ...]]:
    """The Ironclad pool minus Basic and Ancient cards: what GENERATABLE_CARDS holds, plus Feed and Not Yet (rare; a card effect never generates them)."""
    pool = {rarity: [] for rarity in REWARD_RARITIES}
    for card_id, rarity in CARD_RARITY.items():
        if rarity.name in pool and (card_id in GENERATABLE_CARDS or card_id in (CardId.FEED, CardId.NOT_YET)):
            pool[rarity.name].append(card_id)
    return {rarity: tuple(cards) for rarity, cards in pool.items()}


IRONCLAD_POOL = _ironclad_pool()


def _table_pool(table) -> dict[str, tuple[CardId, ...]]:
    return {rarity: tuple(cid for cid in table if CARD_RARITY[cid].name == rarity) for rarity in REWARD_RARITIES}


CHARACTER_POOLS = {"IRONCLAD": IRONCLAD_POOL, "SILENT": _table_pool(SILENT_CARDS), "REGENT": _table_pool(REGENT_CARDS), "NECROBINDER": _table_pool(NECROBINDER_CARDS), "DEFECT": _table_pool(DEFECT_CARDS)}


def card_pool(character : str = "IRONCLAD") -> dict[str, tuple[CardId, ...]]:
    """A character's reward pool by rarity (Common, Uncommon, Rare)."""
    pool = CHARACTER_POOLS.get(character.upper())
    if pool is None or not any(pool.values()):
        raise NotImplementedError(f"{character}: no reward cards are modelled yet")
    return pool


def card_pool_ids(character : str = "IRONCLAD") -> list[CardId]:
    return [cid for cards in card_pool(character).values() for cid in cards]


@dataclass(frozen=True)
class CardOffer:
    card_id : CardId
    upgraded : bool = False


ROOM_ODDS = {"Monster": (Source.ENCOUNTER, OddsType.REGULAR_ENCOUNTER), "Elite": (Source.ENCOUNTER, OddsType.ELITE_ENCOUNTER),
             "Boss": (Source.ENCOUNTER, OddsType.BOSS_ENCOUNTER), "Shop": (Source.SHOP, OddsType.SHOP)}      # CardCreationOptions.ForRoom


_RARITY_OF : dict[CardId, Rarity] = {}        # rarity_of, filled as cards are asked about


def rarity_of(card_id : CardId) -> Rarity:
    rarity = _RARITY_OF.get(card_id)
    if rarity is None:
        rarity = _RARITY_OF[card_id] = Rarity[CARD_RARITY[card_id].name.upper()]
    return rarity


def next_allowed_rarity(rarity : Rarity, is_allowed : Callable[[Rarity], bool]) -> Rarity:
    """CardFactory.GetNextAllowedRarity: the rolled rarity, or the next one up (wrapping) that the pool has; NONE when it has none of the three."""
    tried = [rarity]
    while not is_allowed(rarity) and rarity != Rarity.NONE:
        rarity = rarity.next_highest_with_wrapping()
        if rarity in tried:
            return Rarity.NONE
    return rarity


def roll_for_rarity(odds : CardRarityOdds, odds_type : OddsType, source : Source, allowed : set[Rarity], force_odds_change : bool = False) -> Rarity:
    """CardFactory.RollForRarity: only an encounter's reward (or a forced one) moves the odds; any other source rolls with the base odds."""
    moves_odds = force_odds_change or (source == Source.ENCOUNTER and odds_type in ENCOUNTER_ODDS)
    rolled = odds.roll(odds_type) if moves_odds else odds.roll_with_base_odds(odds_type)
    return next_allowed_rarity(rolled, allowed.__contains__)


def roll_for_upgrade(rng, card_id : CardId, base_chance : float, act_index : int, ascension : int = 0, upgradable : bool = True):
    """CardFactory.RollForUpgrade: the roll is drawn whether or not the card can be upgraded. Non-rare cards gain 0.25 (0.125 at Scarcity) per act."""
    x = rng.random()
    if not upgradable:
        return False
    chance = base_chance
    if rarity_of(card_id) != Rarity.RARE:
        chance += act_index * (0.125 if ascension >= SCARCITY_ASCENSION else 0.25)
    return x <= chance


def create_card_reward(rng, odds : CardRarityOdds, act_index : int, count : int = 3, odds_type : OddsType = OddsType.REGULAR_ENCOUNTER,
                       source : Source = Source.ENCOUNTER, pool : Iterable[CardId] | None = None, no_upgrade_roll : bool = False,
                       force_odds_change : bool = False, blacklist : Iterable[CardId] = (), character : str = "IRONCLAD") -> list[CardOffer]:
    """`count` different cards for one reward screen. `act_index` is 0 in the first act. A pool with a single rarity needs OddsType.UNIFORM."""
    if pool is None:
        pool = card_pool_ids(character)
    pool = list(pool)
    chosen : list[CardId] = list(blacklist)
    offers = []
    for _ in range(count):
        options = [cid for cid in pool if cid not in chosen]
        if odds_type == OddsType.UNIFORM:
            items = [cid for cid in options if CARD_RARITY[cid].name not in ("Basic", "Ancient")]
        else:
            rarities = [_RARITY_OF.get(cid) or rarity_of(cid) for cid in options]
            distinct = []              # the few rarities among the options (a list: compared by identity, no enum hashing per card)
            for r in rarities:
                if r not in distinct:
                    distinct.append(r)
            allowed = set(distinct)
            rarity = roll_for_rarity(odds, odds_type, source, allowed, force_odds_change)
            if rarity == Rarity.NONE:
                raise ValueError("no valid rarity for this card pool")
            items = [cid for cid, r in zip(options, rarities) if r is rarity]
        if not items:
            raise ValueError("no card left to offer")
        card_id = rng.choice(items)
        chosen.append(card_id)
        upgraded = False if no_upgrade_roll else roll_for_upgrade(rng, card_id, 0.0, act_index, odds.ascension)
        offers.append(CardOffer(card_id, upgraded))
    return offers


def create_reward_for_room(rng, odds : CardRarityOdds, room_type : str, act_index : int, count : int = 3, **kwargs) -> list[CardOffer]:
    """A card reward as the room type gives it (CardCreationOptions.ForRoom): end-of-combat for Monster, Elite and Boss, the shop's odds for a Shop."""
    source, odds_type = ROOM_ODDS[room_type]
    return create_card_reward(rng, odds, act_index, count, odds_type, source, **kwargs)


def create_for_merchant(rng, odds : CardRarityOdds, options : Iterable[CardId], card_type, type_of : Callable[[CardId], object], act_index : int = 0) -> CardOffer:
    """A shop card of a given type (CardFactory.CreateForMerchant): the rarity is rolled with the shop odds and the current offset, without moving it.
    `options` are the cards the shop may sell (no Basic cards); `type_of` gives a card's type. The upgrade roll is drawn and never succeeds."""
    options = [cid for cid in options if CARD_RARITY[cid].name != "Basic"]
    allowed = {rarity_of(cid) for cid in options if type_of(cid) == card_type}
    rarity = next_allowed_rarity(odds.roll_without_changing_future_odds(OddsType.SHOP), allowed.__contains__)
    if rarity == Rarity.NONE:
        raise ValueError(f"no card of type {card_type} for the merchant")
    card_id = rng.choice([cid for cid in options if rarity_of(cid) == rarity and type_of(cid) == card_type])
    roll_for_upgrade(rng, card_id, NEVER_UPGRADES, act_index, odds.ascension)
    return CardOffer(card_id, False)
