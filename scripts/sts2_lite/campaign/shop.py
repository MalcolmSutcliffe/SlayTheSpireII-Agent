"""The merchant (MerchantInventory and its entries): 5 character cards (one on sale), 2 colorless cards, 3 relics, 3 potions and a card removal."""
from __future__ import annotations

from dataclasses import dataclass

from sts2_lite.card.tables import CARD_RARITY, COLORLESS_CARDS
from sts2_lite.event.run import card_entry
from sts2_lite.potion import POTION_INFO, PotionId, PotionRarity
from sts2_lite.potion_pool import create_random_potions
from sts2_lite.relic import run_hooks
from sts2_lite.relic.bag import MERCHANT_BASE_COST, RELIC_INFO, pull_relic, relic_name, roll_rarity
from sts2_lite.rewards import CardRarityOdds
from sts2_lite.rewards.cards import card_pool_ids, create_for_merchant, roll_for_upgrade, NEVER_UPGRADES

COLORED_TYPES = ("Attack", "Attack", "Skill", "Skill", "Power")
COLORLESS_RARITIES = ("Uncommon", "Rare")
CARD_COST = {"Rare": 150, "Uncommon": 75}          # anything else 50
COLORLESS_MARKUP = 1.15
POTION_COST = {PotionRarity.RARE: 100, PotionRarity.UNCOMMON: 75}
CARD_JITTER, POTION_JITTER, RELIC_JITTER = (0.95, 1.05), (0.95, 1.05), (0.85, 1.15)
INFLATION_ASCENSION = 6
REMOVAL_BASE, REMOVAL_STEP = (75, 100), (25, 50)       # without / with Inflation


def _jitter(rng, low : float, high : float) -> float:
    return low + rng.random() * (high - low)


@dataclass
class Entry:
    kind : str                      # "card" | "relic" | "potion" | "removal"
    item : object = None            # a deck entry, a relic id or a potion id; None when sold out
    cost : int = 0
    colorless : bool = False
    on_sale : bool = False
    slot : object = None            # the card type / colorless rarity a card slot is for
    used : bool = False

    @property
    def stocked(self) -> bool:
        return not self.used if self.kind == "removal" else self.item is not None


class Shop:
    def __init__(self, run, game, relic_rng=None):
        self.run, self.game = run, game
        self.rng = game.stream("shop")
        self.relic_rng = relic_rng or game.stream("relics")
        self.cards : list[Entry] = []
        self.relics : list[Entry] = []
        self.potions : list[Entry] = []
        self.removal = Entry("removal")
        self._populate()

    # --- stock
    @property
    def entries(self) -> list[Entry]:
        return self.cards + self.relics + self.potions + [self.removal]

    def _populate(self):
        r, rng = self.run, self.rng
        sale = rng.randrange(len(COLORED_TYPES))
        for i, card_type in enumerate(COLORED_TYPES):
            entry = Entry("card", slot=card_type)
            self.cards.append(entry)
            self._fill_card(entry)
            if i == sale:
                entry.on_sale = True
                self._cost_card(entry)
        for rarity in COLORLESS_RARITIES:
            entry = Entry("card", colorless=True, slot=rarity)
            self.cards.append(entry)
            self._fill_card(entry)
        for rarity in (roll_rarity(r.hidden.relic_bag.rng), roll_rarity(r.hidden.relic_bag.rng), "Shop"):
            entry = Entry("relic", slot=rarity)
            self.relics.append(entry)
            self._fill_relic(entry, rarity)
        for potion in create_random_potions(rng, 3):
            entry = Entry("potion", item=potion.name)
            self.potions.append(entry)
            self._cost_potion(entry)
        self._cost_removal()

    def _taken(self) -> set:
        return {e.item["id"] for e in self.cards if e.item is not None}

    def _fill_card(self, entry : Entry):
        r, rng = self.run, self.rng
        taken = self._taken()
        odds = CardRarityOdds(self.game.stream("card_rewards"), r.ascension, r.hidden.rarity_offset)
        act = max(0, r.act - 1)
        if entry.colorless:
            options = [c for c in COLORLESS_CARDS if c.name not in taken and CARD_RARITY[c].name == entry.slot]
            card_id = rng.choice(options)
            roll_for_upgrade(rng, card_id, NEVER_UPGRADES, act, r.ascension)
            cid = card_id
        else:
            options = [c for c in card_pool_ids(r.character) if c.name not in taken]
            cid = create_for_merchant(rng, odds, options, entry.slot, lambda c: card_entry(c)["type"], act).card_id
        card = card_entry(cid)
        entry.item = run_hooks.modify_card_offers(r, [card], self.relic_rng, False, is_reward=False)[0]
        entry.item.setdefault("id", cid.name)
        self._cost_card(entry)

    def _cost_card(self, entry : Entry):
        base = CARD_COST.get(CARD_RARITY[_card_id(entry.item)].name, 50)
        if entry.colorless:
            base = round(base * COLORLESS_MARKUP)
        entry.cost = round(base * _jitter(self.rng, *CARD_JITTER))
        if entry.on_sale:
            entry.cost //= 2

    def _fill_relic(self, entry : Entry, rarity : str, blacklist=()):
        r = self.run
        entry.item = pull_relic(r, rarity, from_back=True, accept=lambda x: RELIC_INFO[x]["shops"] and x not in blacklist)
        entry.cost = round(MERCHANT_BASE_COST[RELIC_INFO[entry.item]["rarity"]] * _jitter(self.rng, *RELIC_JITTER))

    def _cost_potion(self, entry : Entry):
        entry.cost = round(POTION_COST.get(POTION_INFO[PotionId[entry.item]].rarity, 50) * _jitter(self.rng, *POTION_JITTER))

    def _cost_removal(self):
        inflated = self.run.ascension >= INFLATION_ASCENSION
        self.removal.cost = REMOVAL_BASE[inflated] + REMOVAL_STEP[inflated] * self.run.hidden.shop_removals

    # --- prices and purchases
    def price(self, entry : Entry) -> int:
        return run_hooks.merchant_price(self.run, entry.cost)

    def can_buy(self, entry : Entry) -> bool:
        return entry.stocked and self.price(entry) <= self.run.gold

    def after(self, entry : Entry, spent : int):
        """Restock (The Courier) or clear the slot, then Maw Bank notes the spending and the other cards refresh (UpdateEntries)."""
        r = self.run
        if entry.kind != "removal":
            if r.has_relic("THE_COURIER"):
                entry.on_sale = False
                if entry.kind == "card":
                    self._fill_card(entry)
                elif entry.kind == "relic":
                    held = {e.item for e in self.relics if e is not entry and e.item}
                    self._fill_relic(entry, roll_rarity(r.hidden.relic_bag.rng), held)
                else:
                    entry.item = create_random_potions(self.rng, 1)[0].name
                    self._cost_potion(entry)
            else:
                entry.item = None
        if spent > 0:
            run_hooks.state(r, "MAW_BANK")["bought"] = True
        for e in self.cards:
            if e.item is not None:
                e.item = run_hooks.modify_card_offers(r, [e.item], self.relic_rng, False, is_reward=False)[0]

    def spend(self, amount : int):
        self.run.gold -= amount


def _card_id(card : dict):
    from sts2_lite.card.tables import CardId
    return CardId[card["id"]]


def name_of(entry : Entry) -> str:
    if entry.kind == "card":
        return entry.item.get("name") or entry.item["id"]
    if entry.kind == "relic":
        return relic_name(entry.item)
    if entry.kind == "potion":
        return POTION_INFO[PotionId[entry.item]].name
    return "Card Removal"


def shop_ids(entry : Entry) -> dict:
    """The id fields the bridge reports for a stocked entry (card_id, relic_id, potion_id, with the card's type and rarity)."""
    if not entry.stocked or entry.kind == "removal":
        return {}
    if entry.kind == "card":
        return {"card_id": entry.item["id"], "card_name": entry.item.get("name"), "card_type": entry.item.get("type"), "card_rarity": entry.item.get("rarity")}
    if entry.kind == "relic":
        return {"relic_id": entry.item, "relic_name": relic_name(entry.item)}
    return {"potion_id": entry.item, "potion_name": POTION_INFO[PotionId[entry.item]].name}
