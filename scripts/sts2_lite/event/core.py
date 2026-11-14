"""An event is a few pages; each page offers options; an option changes the run and leads to another page or ends the event.

    session = EventSession(EVENTS["ABYSSAL_BATHS"], run, rng, picker)
    while not session.finished: session.choose(session.options[0].key)

Random numbers an event rolls when it starts (the gold of a chest, the cost of a tribute) come from `rng` and are fixed for the session, as in the game.
Choices inside an option (which card to remove, which reward card to take) go to the `picker`; the default picker is random."""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Callable

from sts2_lite.event.run import RunSnapshot, can_enchant, can_upgrade, card_entry, enchanted, random_class_cards, is_curse, CLASS_POOL, REWARD_ODDS


class CardPicker:
    """Decides the card choices inside an event option. Every method returns indexes into the list it is given (distinct, at most `n`)."""
    def __init__(self, rng : random.Random | None = None):
        self.rng = rng or random.Random(0)

    def remove(self, deck : list[dict], n : int, allowed : list[int]) -> list[int]:
        return self.rng.sample(allowed, min(n, len(allowed)))

    def upgrade(self, deck : list[dict], n : int, allowed : list[int]) -> list[int]:
        return self.rng.sample(allowed, min(n, len(allowed)))

    def transform(self, deck : list[dict], n : int, allowed : list[int]) -> list[int]:
        return self.rng.sample(allowed, min(n, len(allowed)))

    def enchant(self, deck : list[dict], allowed : list[int]) -> list[int]:
        return self.rng.sample(allowed, min(1, len(allowed)))

    def take(self, offered : list[dict], n : int) -> list[int]:
        """Cards of a reward screen to add to the deck."""
        return self.rng.sample(range(len(offered)), min(n, len(offered)))


@dataclass
class Option:
    key : str
    apply : Callable[["Ctx"], "Page | None"]
    locked : bool = False           # shown but cannot be chosen (not enough gold)
    hp_cost : int = 0               # hit points the option takes (for a quick look, not used by the rules)
    lethal : bool = False


Page = list[Option]


@dataclass
class Ctx:
    run : RunSnapshot
    rng : random.Random
    picker : CardPicker
    vars : dict = field(default_factory=dict)       # rolled at the start, plus counters the event keeps between pages

    # --- hit points
    def lose_hp(self, n : int):
        self.run.hp = max(0, self.run.hp - n)
        self.run.dead = self.run.hp <= 0

    def heal(self, n : int):
        self.run.hp = min(self.run.max_hp, self.run.hp + n)

    def heal_to_full(self):
        self.run.hp = self.run.max_hp

    def gain_max_hp(self, n : int):
        self.run.max_hp += n
        self.run.hp += n

    def lose_max_hp(self, n : int):
        self.run.max_hp = max(1, self.run.max_hp - n)
        self.run.hp = min(self.run.hp, self.run.max_hp)

    # --- gold
    def gain_gold(self, n : int):
        self.run.gold += max(0, n)

    def lose_gold(self, n : int):
        self.run.gold = max(0, self.run.gold - n)

    # --- cards
    def add_card(self, card_id : str, upgraded : bool = False):
        self.run.deck.append(card_entry(card_id, upgraded))

    def removable(self, pred : Callable[[dict], bool] = lambda c: True) -> list[int]:
        return [i for i, c in enumerate(self.run.deck) if c.get("removable") is not False and pred(c)]

    def remove_cards(self, n : int, pred : Callable[[dict], bool] = lambda c: True) -> list[dict]:
        allowed = self.removable(pred)
        picks = sorted(set(self.picker.remove(self.run.deck, n, allowed)) & set(allowed), reverse=True)[:n]
        return [self.run.deck.pop(i) for i in picks]

    def upgrade_picked(self, n : int):
        allowed = [i for i, c in enumerate(self.run.deck) if can_upgrade(c)]
        for i in self.picker.upgrade(self.run.deck, n, allowed):
            if i in allowed:
                self.upgrade_at(i)

    def upgrade_random(self, n : int):
        allowed = [i for i, c in enumerate(self.run.deck) if can_upgrade(c)]
        self.rng.shuffle(allowed)
        for i in allowed[:n]:
            self.upgrade_at(i)

    def upgrade_at(self, i : int):
        self.run.deck[i] = dict(self.run.deck[i], is_upgraded=True, _upgrade=True)

    def transform(self, n : int, pred : Callable[[dict], bool] = lambda c: not is_curse(c)):
        """Replace n picked cards by Ironclad cards drawn uniformly from the pool (never the same card)."""
        allowed = [i for i, c in enumerate(self.run.deck) if c.get("removable") is not False and pred(c)]
        for i in sorted(set(self.picker.transform(self.run.deck, n, allowed)) & set(allowed)):
            old = self.run.deck[i]
            new = card_entry(self.rng.choice([cid for cids in CLASS_POOL.values() for cid in cids if cid.name != old["id"]]))      # uniform over the pool, not by rarity
            self.run.deck[i] = new

    def enchantable(self, enchantment : str, card_type : str | None = None) -> list[int]:
        return [i for i, x in enumerate(self.run.deck) if can_enchant(x, enchantment, card_type)]

    def enchant(self, enchantment : str, amount : int, card_type : str | None = None):
        allowed = self.enchantable(enchantment, card_type)
        for i in self.picker.enchant(self.run.deck, allowed)[:1]:
            if i in allowed:
                self.run.deck[i] = enchanted(self.run.deck[i], enchantment, amount)

    def transform_into(self, card_id : str, pred : Callable[[dict], bool]):
        """Replace one picked card (matching `pred`) by a fixed card."""
        allowed = [i for i, x in enumerate(self.run.deck) if x.get("removable") is not False and pred(x) and not is_curse(x)]
        for i in self.picker.transform(self.run.deck, 1, allowed)[:1]:
            if i in allowed:
                self.run.deck[i] = card_entry(card_id)

    def pick_from_offer(self, offered : list[dict], n : int):
        for i in sorted(set(self.picker.take(offered, n))):
            self.run.deck.append(offered[i])

    def reward_cards(self, n : int, colorless : bool = False) -> list[dict]:
        from sts2_lite.event.run import COLORLESS_POOL
        if colorless:
            return [card_entry(c) for c in self.rng.sample(COLORLESS_POOL, n)]
        return random_class_cards(n, self.rng)

    # --- relics and potions
    def gain_relic(self, relic_id : str | None = None, name : str | None = None):
        """A named relic, or (id None) a relic the game draws from its bag: counted in `pending_relics`."""
        if relic_id is None:
            self.run.pending_relics += 1
        else:
            self.run.relics.append({"id": relic_id, "name": name or relic_id.replace("_", " ").title()})

    def gain_potion(self, potion_id : str | None = None):
        if len(self.run.potions) < self.run.potion_slots:
            self.run.potions.append({"id": potion_id or "RANDOM_POTION", "name": (potion_id or "random potion").replace("_", " ").title()})

    def start_fight(self, name : str):
        self.run.pending_fight = name


@dataclass
class EventDef:
    id : str
    start : Callable[[Ctx], Page]       # rolls the event's variables into ctx.vars and returns the first page
    allowed : Callable[[RunSnapshot], bool] = lambda run: True
    acts : tuple[int, ...] = (1, 2, 3)  # acts the event can appear in (for the sim's own event draw)


class EventSession:
    """One visit to an event: `options` is the page the player sees; `choose(key)` plays an option and moves to the next page."""
    def __init__(self, event : EventDef, run : RunSnapshot, rng : random.Random, picker : CardPicker | None = None):
        self.event, self.run = event, run
        self.ctx = Ctx(run, rng, picker or CardPicker(rng))
        self.options : Page = event.start(self.ctx)
        self.finished = not self.options
        self.log : list[str] = []

    def available(self) -> list[Option]:
        return [o for o in self.options if not o.locked]

    def choose(self, key : str | int):
        option = self.options[key] if isinstance(key, int) else next(o for o in self.options if o.key == key)
        if option.locked:
            raise ValueError(f"option {option.key!r} is locked")
        self.log.append(option.key)
        page = option.apply(self.ctx)
        self.options = page if page and all(isinstance(o, Option) for o in page) else []      # an option that returns anything but a page ends the event
        self.finished = not self.options or self.run.dead or self.run.pending_fight is not None
        return self

    def play(self, keys : list[str]) -> RunSnapshot:
        for key in keys:
            self.choose(key)
        return self.run
