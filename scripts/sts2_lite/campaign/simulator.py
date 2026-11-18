"""The loop of a run: acts, maps, rooms, rewards, and the agent's decisions in between.

Not modelled yet (each is marked in unimplemented_features.md and works as a stand-in): the Neow / ancient screens (each act's relic choice), pickup effects of
some relics (`relic.pickup.NOT_MODELLED`) and rest-site options that come from relics.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agent_runner.decision_builders import build_decision
from agents.decision import Option

from sts2_lite.campaign import ancients, screens
from sts2_lite.campaign.combat import StalledFight, carry_back, play_fight, start_fight
from sts2_lite.campaign.pickers import AgentPicker
from sts2_lite.campaign.rewards import Reward, generate_rewards, random_potion, treasure_gold_range
from sts2_lite.encounters import ACTS, ENCOUNTERS, generate_rooms
from sts2_lite.encounters.acts import SHARED_EVENTS
from sts2_lite.event import EVENTS, EventSession, available, card_entry
from sts2_lite.event.run import can_upgrade
from sts2_lite.map import generate_map, generate_spoils_map
from sts2_lite.map.points import PointType
from sts2_lite.relic.bag import RelicGrabBag, pull_relic, relic_name
from sts2_lite.relic.pickup import obtain_relic
from sts2_lite.relic import run_hooks
from sts2_lite.event.core import Ctx
from sts2_lite.status import StatusId
from sts2_lite.run import GameRng, SearchRng, Visit, new_run
from sts2_lite.run.state import WEARY_TRAVELER_ASCENSION, WEARY_TRAVELER_SHARE

ACT_ORDER = (("OVERGROWTH", "UNDERDOCKS"), ("HIVE",), ("GLORY",))
DEFAULT_TIME_BUDGET = 0.5
ROOM_OF_POINT = {PointType.MONSTER: "Monster", PointType.ELITE: "Elite", PointType.REST_SITE: "RestSite", PointType.SHOP: "Shop", PointType.TREASURE: "Treasure",
                 PointType.UNKNOWN: "Unknown", PointType.BOSS: "Boss"}


class RunOver(Exception):
    pass


@dataclass
class RunResult:
    won : bool
    act : int
    floor : int
    hp : int
    max_hp : int
    ascension : int
    seed : int
    cause : str | None              # the encounter that killed the player, or why the run was stopped
    deck : list[str]
    relics : list[str]
    pending_relics : int
    fights : int
    illegal_choices : int           # times the agent chose something that was not on the screen
    history : list[Visit] = field(default_factory=list)


class RunSimulator:
    def __init__(self, agent, seed : int | None = None, ascension : int = 0, search_seed : int | None = None, time_budget : float | None = DEFAULT_TIME_BUDGET):
        self.agent, self.ascension, self.time_budget = agent, ascension, time_budget
        self.game = GameRng(seed)
        self.search = SearchRng(search_seed)
        self.run_state = new_run(ascension)
        self.run_state.hidden.relic_bag = RelicGrabBag(self.game.stream("relics"))
        self.run_state.hidden.relic_bag.remove(self.run_state.relics[0]["id"])
        self.fights = 0
        self.took_damage = True         # the last fight cost hit points (Lava Lamp)
        self.illegal = 0
        self.shared_ancients : dict[int, tuple] = {}
        self.cause : str | None = None
        self.won = False

    # --- asking the agent
    def ask(self, state : dict) -> Option:
        decision = build_decision(state)
        if decision is None or not decision.options:
            raise RuntimeError(f"nothing to decide on a {state.get('decision')} screen")
        with self.search.scope():
            option = self.agent.get_decision(decision)
        if option not in decision.options:
            self.illegal += 1
            option = decision.options[0]
        return option

    # --- the run
    def run(self) -> RunResult:
        try:
            for act_index in range(3):
                self.start_act(act_index)
                self.travel()
            self.won = True
        except RunOver:
            pass
        except StalledFight as error:
            self.cause = f"stalled: {error}"
        return self.result()

    def result(self) -> RunResult:
        r = self.run_state
        return RunResult(self.won, r.act, r.floor, r.hp, r.max_hp, self.ascension, self.game.seed, self.cause, [c["id"] for c in r.deck], [x["id"] for x in r.relics],
                         r.pending_relics, self.fights, self.illegal, list(r.history))

    def start_act(self, act_index : int):
        r = self.run_state
        names = ACT_ORDER[act_index]
        act_id = names[0] if len(names) == 1 else self.game.stream("up_front").choice(names)        # act 1 is Overgrowth or Underdocks, evenly
        act = ACTS[act_id]
        last = act_index == 2
        r.act, r.act_id = act_index + 1, act_id
        if act_index == 0:
            self.deal_shared_ancients()
        rooms = generate_rooms(act, self.game.stream("up_front"), ascension=self.ascension, last_act=last, shared_ancients=self.shared_ancients.get(act_index, ()))
        r.hidden.rooms, r.hidden.normal_fought, r.hidden.elite_fought = rooms, 0, 0
        r.hidden.unknown_odds.reset()
        r.hidden.events, r.hidden.events_visited = list(act.events + SHARED_EVENTS), 0
        self.game.stream("up_front").shuffle(r.hidden.events)
        double = self.ascension >= 10 and last
        if act_index == 1 and self.has_card("SPOILS_MAP"):          # SpoilsMap.ModifyGeneratedMap: the hourglass through one treasure room
            r.map = generate_spoils_map(act_id, self.game.stream("map"), act.room_count(), self.ascension)
        else:
            r.map = generate_map(act_id, self.game.stream("map"), act.room_count(), self.ascension, second_boss=double)
        r.position = r.map.start.coord
        r.hidden.spoils_point = self.spoils_point()
        r.boss = rooms.boss.id
        self.visited : list[tuple[int, int]] = []
        self.ancient(rooms.ancient)

    def has_card(self, card_id : str) -> bool:
        return any(c["id"] == card_id for c in self.run_state.deck)

    def spoils_point(self):
        """SpoilsMap.AfterMapGenerated: with the card in the deck when act 2's map is made, its first treasure room (rows from the start up) carries the quest.
        (The act 2 map should become a SpoilsActMap, an hourglass through one treasure room; the standard map is kept for now.)"""
        r = self.run_state
        if r.act != 2 or not self.has_card("SPOILS_MAP"):
            return None
        treasures = sorted((p.row, p.col) for col in r.map.grid for p in col if p is not None and p.type == PointType.TREASURE)
        return (treasures[0][1], treasures[0][0]) if treasures else None

    def deal_shared_ancients(self):
        """RunManager.GenerateRooms: the shared ancients (Darv) are shuffled and a random number of them goes to each act after the first."""
        rng = self.game.stream("up_front")
        left = list(ancients.SHARED)
        rng.shuffle(left)
        self.shared_ancients = {}
        for act_index in (1, 2):
            count = rng.randrange(len(left) + 1)
            self.shared_ancients[act_index] = tuple(left[:count])
            left = left[count:]

    def ancient(self, ancient_id : str):
        """The act's first room: the ancient heals (to full; 80% of what is missing from Ascension 2) and offers three relics, one of which is taken."""
        r = self.run_state
        r.visit("Ancient", ancient_id)
        if ancient_id != "NEOW":            # Neow's heal is already in the starting hit points
            missing = r.max_hp - r.hp
            r.hp += int(missing * WEARY_TRAVELER_SHARE) if self.ascension >= WEARY_TRAVELER_ASCENSION else missing
        options = ancients.generate(ancient_id, r, self.game.stream("ancients"))
        option = self.ask(screens.event_choice(r, ancient_id, options))
        chosen = options[option.action["index"]]
        if chosen.relic:
            self.take_ancient_relic(chosen)

    def take_ancient_relic(self, option):
        r = self.run_state
        if option.setup:
            run_hooks.state(r, option.relic).update(option.setup)
        self.gain_relic(option.relic)

    def travel(self):
        """From the ancient's room up the map to the boss (and the second boss), asking the agent for the next room each time."""
        r = self.run_state
        point = r.map.start
        while point.type != PointType.BOSS:
            free = run_hooks.free_travel(r)
            nearest = [p for p in ([r.map.boss] if point.row + 1 == r.map.rows else [r.map.grid[c][point.row + 1] for c in range(len(r.map.grid))]) if p is not None] if free else point.children
            choices = sorted(nearest, key=lambda p: (p.col, p.row))
            option = self.ask(screens.map_select(r, r.map, choices, self.visited, r.boss))
            chosen = choices[option.action["index"]]
            run_hooks.traveled(r, chosen in point.children)
            point = chosen
            r.position = point.coord
            self.visited.append(point.coord)
            r.floor += 1
            self.enter(point)

    # --- rooms
    def _dowse(self, r):
        from sts2_lite.card.constants import DOWSING_ROOMS
        from sts2_lite.event.run import card_entry
        for i, c in enumerate(r.deck):
            if c["id"] == "DOWSING":
                c["rooms_entered"] = c.get("rooms_entered", 0) + 1
                if c["rooms_entered"] >= DOWSING_ROOMS:
                    r.deck[i] = card_entry("ABUNDANCE")        # TransformTo<Abundance>: a fixed transform, not upgraded

    def enter(self, point):
        r = self.run_state
        kind = ROOM_OF_POINT[point.type]
        from_unknown = kind == "Unknown"
        if from_unknown:
            kind = r.hidden.unknown_odds.roll(self.game.stream("unknown_room"), run_hooks.unknown_room_blacklist(r))
            if run_hooks.golden_path_act(r) or (r.act == 3 and self.has_card("LANTERN_KEY")):         # LanternKey.ModifyUnknownMapPointRoomTypes
                kind = "Event"
        self.fur_coat = run_hooks.fur_coat_marked(r, point.coord)
        if from_unknown:        # Dowsing.BeforeRoomEntered: counts ? map points (whatever room they turn into)
            self._dowse(r)
        if r.hidden.spoils_point is not None and tuple(point.coord) == tuple(r.hidden.spoils_point) and self.has_card("SPOILS_MAP"):       # SpoilsMap.OnQuestComplete
            run_hooks.gain_gold(r, 600)
            r.deck.pop(next(i for i, c in enumerate(r.deck) if c["id"] == "SPOILS_MAP"))
            r.hidden.spoils_point = None
        run_hooks.room_entered(r, kind, from_unknown)
        if kind == "Boss" and point is r.map.boss and r.map.second_boss is not None:
            self.fight_room("Boss", r.hidden.rooms.boss, first_of_two=True)
            r.floor += 1
            self.fight_room("Boss", r.hidden.rooms.second_boss, last_boss=True)
            return
        {"Monster": lambda: self.fight_room("Monster", self.next_fight("Monster")),
         "Elite": lambda: self.fight_room("Elite", self.next_fight("Elite")),
         "Boss": lambda: self.fight_room("Boss", r.hidden.rooms.boss),
         "RestSite": self.rest_site, "Shop": self.shop, "Treasure": self.treasure, "Event": self.event}[kind]()

    def next_fight(self, room : str):
        r = self.run_state
        h = r.hidden
        if room == "Elite":
            enc = h.rooms.elite[h.elite_fought % len(h.rooms.elite)]
            h.elite_fought += 1
        else:
            enc = h.rooms.normal[h.normal_fought % len(h.rooms.normal)]
            h.normal_fought += 1
        return enc

    def fight_room(self, room : str, encounter, first_of_two : bool = False, last_boss : bool = False):
        r = self.run_state
        r.visit(room, encounter.id)
        final = room == "Boss" and r.act == 3 and (r.map.second_boss is None or last_boss)
        self.fight(encounter, room, final)
        run_hooks.combat_finished(r, room, self.game.stream("relics"))
        if first_of_two:
            return
        self.rewards(encounter)

    def fight(self, encounter, room : str, final : bool = False, variant : int | None = None, turn_limit : int | None = None) -> bool:
        """Plays the fight; True when every enemy is dead (False: the turn limit of an event fight ran out)."""
        r = self.run_state
        hp_before = r.hp
        sim = start_fight(r, encounter.id, room.lower(), self.game, final_fight=final, one_hp=getattr(self, "fur_coat", False), variant=variant)
        self.fights += 1
        play_fight(sim, self.agent, self.game, self.search, self.time_budget, turn_limit)
        carry_back(r, sim)
        improvement = sim.combat_state.player.status.get(StatusId.IMPROVEMENT)
        if improvement is not None and not r.dead:       # Mad Science (Improvement): upgrades a random card of the deck as the combat ends
            self.ctx().upgrade_random(improvement.amount)
        self.took_damage = r.hp < hp_before or r.dead
        if r.dead:
            self.cause = encounter.id
            raise RunOver
        return not any(e.current_hp > 0 for e in sim.combat_state.enemies)

    def rewards(self, encounter, extra=()):
        """The reward screen of a won fight; `extra` are an event's own rewards on top of the encounter's (("relic",), ("potion",))."""
        r = self.run_state
        last_boss = encounter.room == "Boss" and r.act == 3
        items = generate_rewards(r, encounter, last_boss, self.game)
        for kind, *_ in extra:
            if kind == "relic":
                items.append(Reward("relic", relic=pull_relic(r) if r.hidden.relic_bag else None))
            elif kind == "potion":
                items.append(Reward("potion", potion=random_potion(self.game.stream("potion_rewards"))))
        while items:
            option = self.ask(screens.combat_rewards(r, items))
            if option.action["action"] == "proceed":
                return
            item = items[option.action["index"]]
            if item.kind == "gold":
                run_hooks.gain_gold(r, item.amount)
            elif item.kind == "potion":
                self.add_potion(item.potion)
            elif item.kind == "relic":
                self.gain_relic(item.relic)
            elif item.kind == "card":
                picked = self.card_reward(item.cards, in_combat=True, room=item.room)
                if not picked:
                    items.remove(item)         # skipped: the reward is gone
                    continue
                run_hooks.add_to_deck(r, picked)
            items.remove(item)

    def ctx(self) -> Ctx:
        return Ctx(self.run_state, self.game.stream("relics"), AgentPicker(self))

    def gain_relic(self, relic_id : str | None = None):
        """Take a relic (a bag draw when no id is given), play its pickup effect and put any reward screens it queued to the agent."""
        obtain_relic(self.ctx(), relic_id)
        self.take_offers()

    def add_potion(self, potion : str):
        r = self.run_state
        if len(r.potions) < r.potion_slots:
            r.potions.append({"id": potion, "name": potion.replace("_", " ").title()})

    def take_offers(self):
        """The reward screens a relic, an event or a rest site queued in `run.offers`."""
        r = self.run_state
        while r.offers:
            offer = r.offers.pop(0)
            if offer["kind"] == "cards":
                entries = offer.get("cards") or self.make_cards(offer["room"])
                picked = self.card_reward_entries(entries, in_combat=False, room=offer.get("room"))
                if picked:
                    run_hooks.add_to_deck(r, picked)
            elif offer["kind"] == "potion":
                from sts2_lite.campaign.rewards import random_potion
                self.add_potion(random_potion(self.game.stream("potion_rewards")))
            elif offer["kind"] == "relic":
                self.gain_relic(offer.get("relic"))
                if offer.get("wax"):
                    r.relics[-1]["wax"] = True
            elif offer["kind"] == "bundle":
                self.pick_bundle(offer["bundles"])

    def pick_bundle(self, bundles : list[list[dict]]):
        """Scroll Boxes: one bundle of cards is kept whole."""
        r = self.run_state
        options = [ancients.AncientOption("", " + ".join(c["name"] for c in bundle)) for bundle in bundles]
        option = self.ask(screens.event_choice(r, "SCROLL_BOXES", options))
        for card in bundles[option.action["index"]]:
            run_hooks.add_to_deck(r, card)

    def make_cards(self, room : str) -> list[dict]:
        """A card reward of `room`'s odds, as deck entries."""
        from sts2_lite.campaign.rewards import _pool_options
        from sts2_lite.rewards import CardRarityOdds, create_reward_for_room
        r = self.run_state
        rng = self.game.stream("card_rewards")
        odds = CardRarityOdds(rng, r.ascension, r.hidden.rarity_offset)
        offers = create_reward_for_room(rng, odds, room, max(0, r.act - 1), **_pool_options(r))
        r.hidden.rarity_offset = odds.current_value
        return [card_entry(o.card_id, o.upgraded) for o in offers]

    def card_reward_entries(self, cards : list[dict], in_combat : bool = False, room : str | None = None) -> dict | None:
        """One card reward screen: a card (returned), a skip or a Pael's Wing sacrifice (None), or a Driftwood reroll (once: `room` says which odds make the new cards)."""
        r = self.run_state
        can_reroll = r.has_relic("DRIFTWOOD") and room is not None
        while True:
            shown = run_hooks.modify_card_offers(r, cards, self.game.stream("relics"), in_combat, self.took_damage)
            alternatives = (["REROLL"] if can_reroll else []) + (["SACRIFICE"] if r.has_relic("PAELS_WING") else [])
            option = self.ask(screens.card_reward(r, shown, alternatives))
            action = option.action
            if action["action"] == "select_card_reward":
                return shown[action["card_index"]]
            if action["action"] == "card_reward_alternative" and action.get("option_id") == "REROLL" and can_reroll:
                cards, can_reroll = self.make_cards(room), False
                continue
            if action["action"] == "card_reward_alternative" and action.get("option_id") == "SACRIFICE" and r.has_relic("PAELS_WING"):
                run_hooks.sacrificed(r)
                if run_hooks.state(r, "PAELS_WING")["sacrificed"] % 2 == 0:
                    self.gain_relic()
            return None

    def card_reward(self, offers, in_combat : bool = False, room : str | None = None) -> dict | None:
        return self.card_reward_entries([card_entry(o.card_id, o.upgraded) for o in offers], in_combat, room)

    def rest_site(self):
        """HEAL, SMITH and what relics add (DIG). One option is used and the site is done, unless Miniature Tent keeps the rest open."""
        r = self.run_state
        r.visit("RestSite")
        names = ["HEAL", "SMITH"] + run_hooks.rest_extra_options(r)
        tent = r.has_relic("MINIATURE_TENT")
        smith_ok, cook_ok, used = True, True, False
        while names:
            upgradable = [i for i, c in enumerate(r.deck) if can_upgrade(c)]
            removable = [i for i, c in enumerate(r.deck) if c.get("removable") is not False]
            option = self.ask(screens.rest_site(r, names, bool(upgradable) and smith_ok, used, () if len(removable) >= 2 and cook_ok else ("COOK",)))
            if option.action["action"] == "proceed":
                break
            choice = option.data.get("id")
            if choice == "HEAL":
                r.hp = min(r.max_hp, r.hp + run_hooks.rest_heal(r))
                run_hooks.rest_healed(r)
                r.offers += run_hooks.rest_heal_offers(r)
            elif choice == "DIG":
                self.gain_relic()
            elif choice == "HATCH":
                self.gain_relic("BYRDPIP")
            elif choice == "COOK":
                removable = [i for i, c in enumerate(r.deck) if c.get("removable") is not False]
                if len(removable) < 2:
                    continue
                picks = AgentPicker(self).remove(r.deck, 2, removable, cancel=True)
                if not picks:           # a cancelled Cook goes back to the other options
                    cook_ok = False
                    continue
                for i in sorted(set(picks), reverse=True):
                    r.deck.pop(i)
                r.max_hp += 5        # CookRestSiteOption: +5 Max HP
                r.hp += 5
            elif choice == "CLONE":
                for card in [c for c in r.deck if (c.get("enchantment") or {}).get("id") == "CLONE"]:
                    run_hooks.add_to_deck(r, dict(card))
            else:
                picks = AgentPicker(self).upgrade(r.deck, 1, upgradable, cancel=True)
                if not picks:           # a cancelled upgrade goes back to the other options
                    smith_ok = False
                    continue
                r.deck[picks[0]] = dict(r.deck[picks[0]], is_upgraded=True, _upgrade=True)
            names.remove(choice)
            used = True
            if not tent:
                break
        self.take_offers()
        self.ask(screens.rest_site(r, [], False, True))

    def treasure(self):
        r = self.run_state
        r.visit("Treasure")
        low, high = treasure_gold_range(r.ascension)
        run_hooks.gain_gold(r, self.game.stream("treasure").randint(low, high))      # the chest pays on arrival
        if not run_hooks.treasure_gives_relic(r):
            self.ask(screens.treasure(r, [], True))
            return
        relic = pull_relic(r)
        self.ask(screens.treasure(r, [{"id": relic, "name": relic_name(relic)}], False))
        self.gain_relic(relic)
        self.ask(screens.treasure(r, [], True))

    def shop(self):
        """A merchant: buy until the agent leaves (or nothing is left to want). Card removal asks which card; The Courier restocks what is bought."""
        from sts2_lite.campaign.shop import Shop, name_of, shop_ids
        r = self.run_state
        r.visit("Shop")
        shop = Shop(r, self.game, self.game.stream("relics"))
        if r.has_relic("LORDS_PARASOL"):          # AfterRoomEntered: everything in the shop is taken for free, the removal last
            for entry in sorted(shop.entries, key=lambda e: e.kind == "removal"):
                if entry.stocked:
                    self.buy(shop, entry, 0)
        while True:
            items = []
            for i, e in enumerate(shop.entries):
                price = shop.price(e) if e.stocked else 0
                items.append({"index": i, "category": e.kind if e.kind != "removal" else "card_removal", "is_stocked": e.stocked, "cost": price,
                              "can_afford": e.stocked and price <= r.gold, "name": name_of(e) if e.stocked else None, "on_sale": e.on_sale,
                              **shop_ids(e)})
            option = self.ask(screens.shop(r, items))
            if option.action["action"] != "shop_purchase":
                return
            entry = shop.entries[option.action["index"]]
            if not shop.can_buy(entry):
                continue
            self.buy(shop, entry, shop.price(entry))

    def fake_merchant(self):
        """FakeMerchant: six of nine fake relics at 50 gold rolled like a shop relic's price (x0.85-1.15, captured), bought until the agent leaves.
        No cards, potions or removal; Membership Card and the other shop discounts do not apply (captured)."""
        from sts2_lite.event.events import FAKE_MERCHANT_PRICE, FAKE_MERCHANT_RELICS, FAKE_MERCHANT_STOCK
        r = self.run_state
        stock = list(FAKE_MERCHANT_RELICS)
        self.game.stream("events").shuffle(stock)
        stock = stock[:FAKE_MERCHANT_STOCK]
        from sts2_lite.campaign.shop import RELIC_JITTER, _jitter
        prices = [round(FAKE_MERCHANT_PRICE * _jitter(self.game.stream("events"), *RELIC_JITTER)) for _ in stock]
        while True:
            items = [{"index": i, "category": "relic", "is_stocked": relic is not None, "cost": prices[i] if relic else 0,
                      "can_afford": relic is not None and r.gold >= prices[i], "name": relic_name(relic) if relic else None, "on_sale": False,
                      **({"relic_id": relic, "relic_name": relic_name(relic)} if relic else {})}
                     for i, relic in enumerate(stock)]
            option = self.ask(screens.shop(r, items, fake_merchant=True))
            if option.action["action"] != "shop_purchase":
                return
            i = option.action["index"]
            if stock[i] is None or r.gold < prices[i]:
                continue
            r.gold -= prices[i]
            relic, stock[i] = stock[i], None
            self.gain_relic(relic)

    def buy(self, shop, entry, price : int) -> bool:
        """One purchase at `price` (0 for Lord's Parasol): what the slot holds goes to the run; False when it cannot be done (potion belt full, removal cancelled)."""
        r = self.run_state
        if entry.kind == "card":
            shop.spend(price)
            run_hooks.add_to_deck(r, entry.item)
        elif entry.kind == "relic":
            shop.spend(price)
            self.gain_relic(entry.item)
        elif entry.kind == "potion":
            if len(r.potions) >= r.potion_slots:
                return False
            shop.spend(price)
            self.add_potion(entry.item)
        else:
            if not self.ctx().remove_cards(1):
                return False
            shop.spend(price)
            entry.used = True
            r.hidden.shop_removals += 1
        shop.after(entry, price)
        return True

    def next_event(self):
        """ActModel.PullNextEvent / RoomSet.EnsureNextEventIsValid: the pool is a shuffled ring; events that are not allowed now or were met before are stepped over, and the
        event found is marked visited. Returns (id, EventDef or None for an event the sim does not model: it happens as an empty visit). When every event has been
        met the ring repeats."""
        r = self.run_state
        pool, seen = r.hidden.events, set(r.seen_events)
        if not pool:
            return None, None
        for _ in range(len(pool)):
            name = pool[r.hidden.events_visited % len(pool)]
            event = EVENTS.get(name)
            if name not in seen and (event is None or (r.act in event.acts and event.allowed(r))):
                break
            r.hidden.events_visited += 1
        else:
            name = pool[r.hidden.events_visited % len(pool)]
            event = EVENTS.get(name)
        r.hidden.events_visited += 1
        if r.act == 3 and self.has_card("LANTERN_KEY"):         # LanternKey.ModifyNextEvent: whatever the pool had is replaced
            name = "WAR_HISTORIAN_REPY"
            event = EVENTS[name]
        return name, event

    def event(self):
        r = self.run_state
        name, event = self.next_event()
        r.visit("Event", name)
        if event is None:            # not modelled (or no pool): nothing happens
            return
        if event.id == "FAKE_MERCHANT":
            self.fake_merchant()
            return
        session = EventSession(event, r, self.game.stream("events"), AgentPicker(self))
        while not session.finished:
            if not session.available():
                break
            option = self.ask(screens.event_choice(r, event.id, session.options))
            session.choose(option.action["index"])
            self.take_offers()
        if r.dead:
            self.cause = event.id
            raise RunOver
        if r.pending_fight is not None:
            name, args = r.pending_fight, r.pending_fight_args
            r.pending_fight, r.pending_fight_args = None, {}
            if name in ENCOUNTERS:
                self.event_fight(ENCOUNTERS[name], **args)

    def event_fight(self, encounter, variant : int | None = None, turn_limit : int | None = None, extra=(), on_win : str | None = None):
        """A fight an event started: the event's visit is the room (no second visit), its rewards come on top of the usual ones."""
        r = self.run_state
        won = self.fight(encounter, "Monster", variant=variant, turn_limit=turn_limit)
        run_hooks.combat_finished(r, "Monster", self.game.stream("relics"))
        if not won:         # the Battleworn Dummy's time ran out: nothing
            return
        if on_win == "upgrade_two":
            self.ctx().upgrade_random(2)
        elif on_win == "relic":
            self.gain_relic()
        elif on_win == "lantern_key":
            self.ctx().add_placeholder("LANTERN_KEY", "Lantern Key", "Quest")         # the fight's SpecialCardReward
        self.rewards(encounter, extra=[e if isinstance(e, tuple) else (e,) for e in extra] + ([("potion",)] if on_win == "potion" else []))
