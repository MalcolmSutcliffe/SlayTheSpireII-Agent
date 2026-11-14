"""The part of a run an event can change: hit points, gold, the deck, relics and potions.

`RunSnapshot` is a plain copy of that state (the same card dicts the deck evaluator scores), so an event is played on a copy and the original is untouched.
Card entries are made from the sim's own tables, so a card an event adds has the cost, type and target the combat engine expects."""
from __future__ import annotations
import copy
import random
from dataclasses import dataclass, field

from sts2_lite.card.constants import CARD_ENERGY_COST_AND_TARGET
from sts2_lite.card.ids import CardId, CardType
from sts2_lite.card.tables import CARD_RARITY, COLORLESS_CARDS, GENERATABLE_CARDS, STRIKE_CARDS, DEFEND_CARDS
from sts2_lite.relic import RelicId

REST_HEAL_SHARE = 0.30          # what a rest site heals, as a share of max HP (the Dense Vegetation and Unrest Site heal match it)
# Share of each rarity in a card reward, and the cards a transform / reward event draws from: the Ironclad pool only
REWARD_ODDS = {"Common": 0.60, "Uncommon": 0.25, "Rare": 0.15}
EXTRA_TYPES = {CardId.FEED : CardType.Attack, CardId.NOT_YET : CardType.Skill}      # Ironclad cards GENERATABLE_CARDS lacks


BASIC_CARDS = {CardId.STRIKE_IRONCLAD : ("Strike", CardType.Attack), CardId.DEFEND_IRONCLAD : ("Defend", CardType.Skill), CardId.BASH : ("Bash", CardType.Attack)}
CURSE_IDS = frozenset(CardId[n] for n in ("DECAY", "NORMALITY", "INJURY", "POOR_SLEEP", "GREED", "CLUMSY", "BAD_LUCK", "DEBT", "GUILTY", "SPORE_MIND",
                                          "CURSE_OF_THE_BELL", "ASCENDERS_BANE"))


def card_entry(card_id : CardId | str, upgraded : bool = False) -> dict:
    """A deck entry for a card by id, in the shape the bridge and the deck evaluator use (cost and target from the sim's own tables)."""
    from sts2_lite.card.tables import EVENT_CARDS, TOKEN_CARDS
    cid = card_id if isinstance(card_id, CardId) else CardId[card_id]
    cost, target = CARD_ENERGY_COST_AND_TARGET.get(cid, (0, None)) if cid in CURSE_IDS else CARD_ENERGY_COST_AND_TARGET[cid]       # a curse cannot be played
    for table in (GENERATABLE_CARDS, COLORLESS_CARDS, EVENT_CARDS, TOKEN_CARDS):
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
    if upgraded:
        entry["_upgrade"] = True
    return entry


def _pool(table : dict, rarities : tuple[str, ...]) -> dict[str, list[CardId]]:
    pool = {r: [] for r in rarities}
    for cid, rarity in CARD_RARITY.items():
        if rarity.name in pool and (cid in table or cid in EXTRA_TYPES):
            pool[rarity.name].append(cid)
    return pool


CLASS_POOL = _pool(GENERATABLE_CARDS, tuple(REWARD_ODDS))
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


def random_class_cards(n : int, r : random.Random, exclude : set[str] = frozenset()) -> list[dict]:
    """n distinct Ironclad cards by the odds of a card reward."""
    out, seen = [], set(exclude)
    while len(out) < n:
        x = r.random()
        rarity = "Common" if x < REWARD_ODDS["Common"] else "Uncommon" if x < REWARD_ODDS["Common"] + REWARD_ODDS["Uncommon"] else "Rare"
        cid = r.choice(CLASS_POOL[rarity])
        if cid.name not in seen:
            seen.add(cid.name)
            out.append(card_entry(cid))
    return out


@dataclass
class RunSnapshot:
    hp : int
    max_hp : int
    gold : int
    deck : list[dict]
    relics : list[dict] = field(default_factory=list)       # {"id": ..., "name": ...}; ids the combat sim does not know are kept too
    potions : list[dict] = field(default_factory=list)
    potion_slots : int = 3
    act : int = 1
    floor : int = 1
    pending_relics : int = 0        # relics an event gave whose kind is chosen by the game's relic bag (not modelled): a count, not an id
    pending_fight : str | None = None   # the fight an event option started (not played by the event)
    dead : bool = False

    def copy(self) -> "RunSnapshot":
        return copy.deepcopy(self)

    @classmethod
    def from_player(cls, player : dict, deck : list[dict], act : int = 1, floor : int = 1) -> "RunSnapshot":
        """From a bridge `player` dict plus the deck."""
        return cls(hp=player["hp"], max_hp=player["max_hp"], gold=player.get("gold", 0), deck=copy.deepcopy(deck), relics=copy.deepcopy(player.get("relics", [])),
                   potions=copy.deepcopy([p for p in player.get("potions", []) if p]), potion_slots=player.get("potion_slots", 3), act=act, floor=floor)

    def sim_relics(self) -> list[dict]:
        """The relics the combat sim knows (the rest cannot change a fight it plays)."""
        return [r for r in self.relics if str(r.get("id", "")) in RelicId.__members__]

    def has_relic(self, relic_id : str) -> bool:
        return any(r.get("id") == relic_id for r in self.relics)


# --- enchantments -------------------------------------------------------------------------------------------------------------------------------------
# The card's "enchantment": {"id", "amount"} is what the bridge reports and what the combat sim reads. Rules follow EnchantmentModel.CanEnchant.
ENCHANT_ATTACK_ONLY = frozenset({"CORRUPTED", "SHARP"})


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
