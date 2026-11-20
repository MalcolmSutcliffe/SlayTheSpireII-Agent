"""The part of a run an event can change: hit points, gold, the deck, relics and potions.

`RunSnapshot` is `sts2_lite.run.RunState` (the same card dicts the deck evaluator scores), so an event is played on a copy and the original is untouched.
Card entries are made from the sim's own tables, so a card an event adds has the cost, type and target the combat engine expects."""
from __future__ import annotations
import random

from sts2_lite.card.constants import CARD_ENERGY_COST_AND_TARGET, PLAYABLE_CURSES, STAR_COST
from sts2_lite.card.ids import CardId, CardType
from sts2_lite.card.tables import CARD_RARITY, CHARACTER_CARDS, COLORLESS_CARDS, DEFECT_CARDS, GENERATABLE_CARDS, NECROBINDER_CARDS, REGENT_CARDS, SILENT_CARDS, STRIKE_CARDS, DEFEND_CARDS
from sts2_lite.run.state import RunState

REST_HEAL_SHARE = 0.30          # what a rest site heals, as a share of max HP (the Dense Vegetation and Unrest Site heal match it)
# The cards a transform / reward event draws from: the Ironclad pool only (rarity odds: sts2_lite.rewards)
EXTRA_TYPES = {CardId.FEED : CardType.Attack, CardId.NOT_YET : CardType.Skill, CardId.APPARITION : CardType.Skill, CardId.APOTHEOSIS : CardType.Skill, CardId.MAUL : CardType.Attack, CardId.BREAK : CardType.Attack, CardId.NEOWS_FURY : CardType.Attack, CardId.CORRUPTION : CardType.Power}      # cards GENERATABLE_CARDS lacks (Feed, Not Yet: Ironclad; the rest: relics, ancients)


BASIC_CARDS = {CardId.STRIKE_IRONCLAD : ("Strike", CardType.Attack), CardId.DEFEND_IRONCLAD : ("Defend", CardType.Skill), CardId.BASH : ("Bash", CardType.Attack)}
CURSE_IDS = frozenset(CardId[n] for n in ("DECAY", "NORMALITY", "INJURY", "POOR_SLEEP", "GREED", "CLUMSY", "BAD_LUCK", "DEBT", "GUILTY", "SPORE_MIND",
                                          "CURSE_OF_THE_BELL", "ASCENDERS_BANE", "DOUBT", "REGRET", "SHAME", "WRITHE", "FOLLY", "ENTHRALLED"))


def card_entry(card_id : CardId | str, upgraded : bool = False) -> dict:
    """A deck entry for a card by id, in the shape the bridge and the deck evaluator use (cost and target from the sim's own tables)."""
    from sts2_lite.card.tables import ANCIENT_CARDS, EVENT_CARDS, TOKEN_CARDS
    cid = card_id if isinstance(card_id, CardId) else CardId[card_id]
    if cid in CURSE_IDS:
        cost, target = PLAYABLE_CURSES.get(cid, 0), None       # most curses cannot be played
    elif cid in CARD_ENERGY_COST_AND_TARGET:
        cost, target = CARD_ENERGY_COST_AND_TARGET[cid]
    else:
        cost, target = ANCIENT_CARDS[cid][2:4]
    for table in (GENERATABLE_CARDS, SILENT_CARDS, REGENT_CARDS, NECROBINDER_CARDS, DEFECT_CARDS, COLORLESS_CARDS, EVENT_CARDS, TOKEN_CARDS, ANCIENT_CARDS):
        if cid in table:
            name, ctype = table[cid][0], table[cid][1]
            break
    else:
        if cid in BASIC_CARDS:
            name, ctype = BASIC_CARDS[cid]
        elif cid in CURSE_IDS:
            name, ctype = cid.name.replace("_", " ").title(), CardType.Curse
        elif cid in EXTRA_TYPES:
            name, ctype = cid.name.replace("_", " ").title(), EXTRA_TYPES[cid]
        else:
            raise KeyError(f"no type known for card {cid.name}")
    entry = {"id": cid.name, "name": name, "type": ctype.name, "rarity": "Curse" if ctype == CardType.Curse else CARD_RARITY[cid].name if cid in CARD_RARITY else None,
             "cost": cost, "target_type": target.name if target is not None else None, "is_upgraded": bool(upgraded)}
    if cid in STAR_COST:
        entry["star_cost"] = STAR_COST[cid]         # the Regent's cards also cost Stars
    if upgraded:
        entry["_upgrade"] = True
    return entry


def _pool(table : dict, rarities : tuple[str, ...]) -> dict[str, list[CardId]]:
    pool = {r: [] for r in rarities}
    for cid, rarity in CARD_RARITY.items():
        if rarity.name in pool and (cid in table or cid in EXTRA_TYPES):
            pool[rarity.name].append(cid)
    return pool


CLASS_POOL = _pool(GENERATABLE_CARDS, ("Common", "Uncommon", "Rare"))        # the Ironclad's


def class_pool(character : str = "IRONCLAD") -> dict[str, list[CardId]]:
    """A character's card pool by rarity, as events and relics draw from it."""
    if character.upper() == "IRONCLAD":
        return CLASS_POOL
    from sts2_lite.rewards.cards import card_pool
    return {rarity: list(cids) for rarity, cids in card_pool(character).items()}


def class_pool_ids(character : str = "IRONCLAD") -> list[CardId]:
    return [cid for cids in class_pool(character).values() for cid in cids]
COLORLESS_POOL = [cid for cid in COLORLESS_CARDS if CARD_RARITY.get(cid) is not None and CARD_RARITY[cid].name in ("Uncommon", "Rare")]


def is_basic_strike(card : dict) -> bool:
    cid = CardId.__members__.get(card.get("id"))
    return cid in STRIKE_CARDS and card.get("rarity", "Basic") == "Basic" and CARD_RARITY.get(cid) is not None and CARD_RARITY[cid].name == "Basic"


def is_basic_defend(card : dict) -> bool:
    cid = CardId.__members__.get(card.get("id"))
    return cid in DEFEND_CARDS and CARD_RARITY.get(cid) is not None and CARD_RARITY[cid].name == "Basic"


def is_curse(card : dict) -> bool:
    return card.get("type") == "Curse"


def can_upgrade(card : dict) -> bool:
    return not card.get("is_upgraded") and card.get("can_upgrade", True) and card.get("type") not in ("Curse", "Status")


def random_class_cards(n : int, r : random.Random, exclude : set[str] = frozenset(), ascension : int = 0, character : str = "IRONCLAD") -> list[dict]:
    """n distinct cards of the character's pool as an event or relic offers them (CardCreationOptions.ForNonCombatWithDefaultOdds): the regular-encounter rarity odds
    without the run's rarity offset, and no upgrades."""
    from sts2_lite.rewards import CardRarityOdds, OddsType, Source, create_card_reward
    blacklist = [CardId[name] for name in exclude if name in CardId.__members__]
    offers = create_card_reward(r, CardRarityOdds(r, ascension), 0, n, OddsType.REGULAR_ENCOUNTER, Source.OTHER, no_upgrade_roll=True, blacklist=blacklist, character=character)
    return [card_entry(offer.card_id) for offer in offers]


RunSnapshot = RunState        # the old name: events play on the run's state


# --- enchantments -------------------------------------------------------------------------------------------------------------------------------------
# The card's "enchantment": {"id", "amount"} is what the bridge reports and what the combat sim reads. Rules follow EnchantmentModel.CanEnchant.
ENCHANT_ATTACK_ONLY = frozenset({"CORRUPTED", "SHARP", "INSTINCT", "VIGOROUS"})


def _sim_card(card : dict):
    from sts2_lite.card import Card
    return Card.from_dict({"id": card["id"], "name": card.get("name", card["id"]), "type": card["type"], "cost": card.get("cost", 1), "can_play": True, "target_type": card.get("target_type") or "Self",
                           "is_upgraded": bool(card.get("is_upgraded")), "unplayable_reason": None})


def can_enchant(card : dict, enchantment : str, card_type : str | None = None) -> bool:
    """EnchantmentModel.CanEnchant: not a Curse / Status, not already enchanted, not unplayable, plus the enchantment's own rule. `card_type` is an event's extra filter."""
    if card.get("type") in ("Curse", "Status", "Quest") or card.get("enchantment"):
        return False
    if card_type is not None and card.get("type") != card_type:
        return False
    if enchantment in ENCHANT_ATTACK_ONLY and card.get("type") != "Attack":
        return False
    sim = _sim_card(card)
    if sim.unplayable or sim.is_unplayable:
        return False
    if enchantment == "GOOPY":
        return CardId.__members__.get(card.get("id")) in DEFEND_CARDS          # CardTag.Defend
    if enchantment == "TEZCATARAS_EMBER":
        return is_basic_strike(card)
    if enchantment == "SPIRAL":
        return card.get("rarity", "Basic") == "Basic" and (is_basic_strike(card) or is_basic_defend(card))
    if enchantment == "SOULS_POWER":
        return sim.exhausts                 # the card has Exhaust of its own
    if enchantment == "SLITHER":
        return sim.energy_cost != "X"
    if enchantment == "NIMBLE":
        return "block" in str(card.get("description", "block")).lower() and card.get("type") in ("Skill", "Attack")       # GainsBlock: a printed Block (assumed for a card without text)
    return True


def enchanted(card : dict, enchantment : str, amount : int) -> dict:
    return dict(card, enchantment={"id": enchantment, "amount": amount})


# --- cards the engine has no model for -----------------------------------------------------------------------------------------------------------------
def placeholder_entry(card_id : str, name : str | None = None, card_type : str = "Skill") -> dict:
    """A card the engine cannot play (another character's, or a quest card): it sits in the deck as a dead card, like the combat engine treats an unknown id."""
    return {"id": card_id, "name": name or card_id.replace("_", " ").title(), "type": card_type, "rarity": None, "cost": 1, "target_type": "Self", "is_upgraded": False, "modelled": False}


def mad_science_entry(card_type : str, rider : str) -> dict:
    """Tinker Time's card: 1 energy, the type picked (an Attack aims at one enemy) and the rider it was given."""
    return dict(card_entry("MAD_SCIENCE"), type=card_type, target_type="AnyEnemy" if card_type == "Attack" else "Self", rider=rider)


def random_pool_card(r : random.Random, where, ascension : int = 0, character : str = "IRONCLAD") -> dict | None:
    """One card of the character's pool that satisfies `where(card_entry)`, with the default non-combat odds (CardCreationOptions.ForNonCombatWithDefaultOdds + a filter)."""
    from sts2_lite.rewards import CardRarityOdds, OddsType, Source, create_card_reward
    pool = [cid for cid in class_pool_ids(character) if where(card_entry(cid))]
    if not pool:
        return None
    offers = create_card_reward(r, CardRarityOdds(r, ascension), 0, 1, OddsType.REGULAR_ENCOUNTER, Source.OTHER, pool=pool, no_upgrade_roll=True)
    return card_entry(offers[0].card_id)
