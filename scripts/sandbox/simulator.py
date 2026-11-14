"""The loop of a run: acts, maps, rooms, rewards, and the agent's decisions in between.

Not modelled yet (each is marked in unimplemented_features.md and works as a stand-in): the Neow / ancient screens, shops (the shop is empty), relic
generation of boss relics (counted in `run.pending_relics`), pickup effects of some relics (`relic.pickup.NOT_MODELLED`), rest-site options that come from relics, and potion reward tables."""
from __future__ import annotations

from dataclasses import dataclass, field

from agent_runner.decision_builders import build_decision
from agents.decision import Option

from sandbox import screens
from sandbox.combat import StalledFight, carry_back, play_fight, start_fight
from sandbox.pickers import AgentPicker
from sandbox.rewards import Reward, generate_rewards
from sts2_lite.encounters import ACTS, ENCOUNTERS, generate_rooms
from sts2_lite.event import EVENTS, EventSession, available, card_entry
from sts2_lite.event.run import can_upgrade
from sts2_lite.map import generate_map
from sts2_lite.map.points import PointType
from sts2_lite.relic.bag import RelicGrabBag, pull_relic, relic_name
from sts2_lite.relic.pickup import obtain_relic
from sts2_lite.relic import run_hooks
from sts2_lite.event.core import Ctx
from sts2_lite.run import GameRng, SearchRng, Visit, new_run

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
        rooms = generate_rooms(act, self.game.stream("up_front"), ascension=self.ascension, last_act=last)
        r.hidden.rooms, r.hidden.normal_fought, r.hidden.elite_fought = rooms, 0, 0
        r.hidden.unknown_odds.reset()
        double = self.ascension >= 10 and last
        r.map = generate_map(act_id, self.game.stream("map"), act.room_count(), self.ascension, second_boss=double)
        r.position = r.map.start.coord
        r.boss = rooms.boss.id
        self.visited : list[tuple[int, int]] = []
        self.ancient(rooms.ancient)

    def ancient(self, ancient_id : str | None):
        """Neow / the act's ancient: not modelled yet (no offer is made)."""
        self.run_state.visit("Ancient", ancient_id)

    def travel(self):
        """From the ancient's room up the map to the boss (and the second boss), asking the agent for the next room each time."""
        r = self.run_state
        point = r.map.start
        while point.type != PointType.BOSS:
            choices = sorted(point.children, key=lambda p: (p.col, p.row))
            option = self.ask(screens.map_select(r, r.map, choices, self.visited, r.boss))
            point = choices[option.action["index"]]
            r.position = point.coord
            self.visited.append(point.coord)
            r.floor += 1
            self.enter(point)

    # --- rooms
    def enter(self, point):
        r = self.run_state
        kind = ROOM_OF_POINT[point.type]
        from_unknown = kind == "Unknown"
        if from_unknown:
            kind = r.hidden.unknown_odds.roll(self.game.stream("unknown_room"), run_hooks.unknown_room_blacklist(r))
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
        if room == "Boss" and r.act < 3:
            r.pending_relics += 1         # the boss relic: not modelled yet

    def fight(self, encounter, room : str, final : bool = False):
        r = self.run_state
        hp_before = r.hp
        sim = start_fight(r, encounter.id, room.lower(), self.game, final_fight=final)
        self.fights += 1
        play_fight(sim, self.agent, self.game, self.search, self.time_budget)
        carry_back(r, sim)
        self.took_damage = r.hp < hp_before or r.dead
        if r.dead:
            self.cause = encounter.id
            raise RunOver

    def rewards(self, encounter):
        r = self.run_state
        last_boss = encounter.room == "Boss" and r.act == 3
        items = generate_rewards(r, encounter, last_boss, self.game)
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
                picked = self.card_reward(item.cards, in_combat=True)
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
                picked = self.card_reward_entries(entries, in_combat=False)
                if picked:
                    run_hooks.add_to_deck(r, picked)
            elif offer["kind"] == "potion":
                from sandbox.rewards import random_potion
                self.add_potion(random_potion(self.game.stream("potion_rewards")))
            elif offer["kind"] == "relic":
                self.gain_relic()

    def make_cards(self, room : str) -> list[dict]:
        """A card reward of `room`'s odds, as deck entries."""
        from sandbox.rewards import _pool_options
        from sts2_lite.rewards import CardRarityOdds, create_reward_for_room
        r = self.run_state
        rng = self.game.stream("card_rewards")
        odds = CardRarityOdds(rng, r.ascension, r.hidden.rarity_offset)
        offers = create_reward_for_room(rng, odds, room, max(0, r.act - 1), **_pool_options(r))
        r.hidden.rarity_offset = odds.current_value
        return [card_entry(o.card_id, o.upgraded) for o in offers]

    def card_reward_entries(self, cards : list[dict], in_combat : bool = False) -> dict | None:
        r = self.run_state
        cards = run_hooks.modify_card_offers(r, cards, self.game.stream("relics"), in_combat, self.took_damage)
        option = self.ask(screens.card_reward(r, cards))
        return cards[option.action["card_index"]] if option.action["action"] == "select_card_reward" else None

    def card_reward(self, offers, in_combat : bool = False) -> dict | None:
        return self.card_reward_entries([card_entry(o.card_id, o.upgraded) for o in offers], in_combat)

    def rest_site(self):
        """HEAL, SMITH and what relics add (DIG). One option is used and the site is done, unless Miniature Tent keeps the rest open."""
        r = self.run_state
        r.visit("RestSite")
        names = ["HEAL", "SMITH"] + run_hooks.rest_extra_options(r)
        tent = r.has_relic("MINIATURE_TENT")
        smith_ok, used = True, False
        while names:
            upgradable = [i for i, c in enumerate(r.deck) if can_upgrade(c)]
            option = self.ask(screens.rest_site(r, names, bool(upgradable) and smith_ok, used))
            if option.action["action"] == "proceed":
                break
            choice = option.data.get("id")
            if choice == "HEAL":
                r.hp = min(r.max_hp, r.hp + run_hooks.rest_heal(r))
                run_hooks.rest_healed(r)
                r.offers += run_hooks.rest_heal_offers(r)
            elif choice == "DIG":
                self.gain_relic()
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
        relic = pull_relic(r)
        self.ask(screens.treasure(r, [{"id": relic, "name": relic_name(relic)}], False))
        self.gain_relic(relic)
        self.ask(screens.treasure(r, [], True))

    def shop(self):
        """An empty shop: the merchant's stock is not modelled yet."""
        self.run_state.visit("Shop")
        self.ask(screens.shop(self.run_state, []))

    def event(self):
        r = self.run_state
        seen = set(r.seen_events)
        pool = [e for e in available(r) if e.id not in seen]
        if not pool:
            r.visit("Event", None)
            return
        event = self.game.stream("events").choice(pool)
        r.visit("Event", event.id)
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
            name, r.pending_fight = r.pending_fight, None
            if name in ENCOUNTERS:
                self.fight_room(ENCOUNTERS[name].room, ENCOUNTERS[name])
