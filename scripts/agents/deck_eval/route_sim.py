"""Walks through the rest of the act on the engine's own run simulator.

A walk is the rooms the planned route still has (its fights, rest sites, shops, "?" rooms and treasure room) played by `RunSimulator`'s own room
handlers from the run as it stands: the deck, relics, potions, gold and HP of the decision. So everything the game does on the way is done by the engine, not
modelled here: the rewards of a fight (gold, potions, card rewards with their rarity odds, the relic an elite drops from the relic bag and its pickup effect),
rest-site relics, the treasure room's relic, the hooks relics run after a fight, the second boss of ascension 10.

What the agent cannot see is drawn for each walk, consistent with what it knows: the act's boss when the map showed it, the elites already fought (the next one
comes from what the game's bag has left: elite_odds), the act's normal encounters, the relic bag without the relics the player owns.

Decisions inside a walk are made by `WalkAgent`, a cheap stand-in: rest when hurt, else upgrade; a "?" room turns into what the game's odds make of it (a fight, an event, a shop, a treasure room) and an event option is chosen at random; in a shop spend all the gold (the shop's 3rd relic is never bought): relics first, then a card removal (a curse, else a Strike,
else a Defend), then cards, the rarest first, then potions; a card reward takes the rarest card with the chance the future-deck
model gives (future_cards.EXTRA_CARD_SHARE: 0.8 per fight in act 1, 0.5, 0.3) and skips otherwise; fights are played with the rollout policy.

A walk is scored in rooms of progress, what the run gets through: each room survived is worth 1, a fight died in is worth the share of the enemies' HP the deck had taken off by then
(under 1), rooms never reached are worth 0, so a death costs everything that was still ahead. A walk that clears its act goes on to play the first LOOKAHEAD_ROOMS rooms of the next
act (healed as the ancient does; the same rooms are scored the same way), so a deck, relics, potions and max HP that carry forward show in how those go; a cleared last act is worth
CLEAR_BONUS more. Potions held and max HP gained at the end count once (POTION_CREDIT, MAX_HP_CREDIT). HP, gold and the rest count only through what they do to the rooms that follow.

Every deck of a decision plays the same walks, and each room reseeds every random stream of the run from the walk's seed, so what a deck meets (the monsters, their
dice, the rewards) does not depend on what an earlier room did to the deck."""
from __future__ import annotations
import random
from dataclasses import dataclass

from sts2_lite.campaign.ancients import AncientOption
from sts2_lite.campaign.combat import carry_back, start_fight
from sts2_lite.campaign.simulator import RunOver, RunSimulator
from sts2_lite.encounters import ACTS, ENCOUNTERS, generate_rooms
from sts2_lite.encounters.acts import SHARED_EVENTS
from sts2_lite.run.state import WEARY_TRAVELER_ASCENSION, WEARY_TRAVELER_SHARE
from sts2_lite.event import CardPicker, EVENTS, EventSession
from sts2_lite.relic import run_hooks
from sts2_lite.relic.bag import RelicGrabBag
from sts2_lite.run import Hidden, RunState, SearchRng
from sts2_lite.run.streams import STREAMS, GameRng
from sts2_lite.status import StatusId

from agents.base_agent import BaseAgent
from agents.deck_eval.boss_spawner import BOSS_ACTS, normalize_boss_id
from agents.deck_eval.elite_odds import ACT_IDS, elite_sequence
from agents.deck_eval.future_cards import EXTRA_CARD_SHARE, fight_act, route_steps
from agents.sts2_MCTS import outcome_score
from agents.sts2_MCTS.rollout_policy import rollout_policy

MAX_TURNS = 25
LOOKAHEAD_ROOMS = 3         # rooms of the next act a walk that clears its act goes on to play
CLEAR_BONUS = 3.0           # a cleared last act: the run is won, worth as much as the lookahead's rooms
POTION_CREDIT = 0.1         # rooms' worth of progress each potion held at the end of the walk (counted once, not at every fight)
MAX_HP_CREDIT = 0.02        # rooms' worth for each point of max HP gained during the walk
RARITY_RANK = {"Rare": 3, "Uncommon": 2, "Common": 1}
ROOM_OF_STEP = {"weak": "Monster", "normal": "Monster", "elite": "Elite", "boss": "Boss", "rest": "RestSite", "treasure": "Treasure", "shop": "Shop", "unknown": "Unknown"}


ENGINE_ERRORS : dict[str, int] = {}         # what went wrong inside a rollout (message -> times): a walk meeting one ends there instead of ending the run


def note_engine_error(error : Exception, sim, action) -> None:
    """A rollout hit a bug of the engine: the first time each kind comes up it is printed with what the fight looked like, so the bug can be found."""
    cs = sim.combat_state
    key = "%s: %s" % (type(error).__name__, error)
    ENGINE_ERRORS[key] = ENGINE_ERRORS.get(key, 0) + 1
    if ENGINE_ERRORS[key] == 1:
        import traceback
        where = traceback.extract_tb(error.__traceback__)[-1]
        print("engine error in a rollout (the walk ends there): %s at %s:%d | enemies %s | hand %s | last action %s" % (
            key, where.filename.split("sts2_lite")[-1], where.lineno, [e.enemy_id for e in cs.enemies], [getattr(c, "card_id", c).name for c in cs.player.hand], action))


@dataclass
class Walk:
    """What a walk's rooms hold, the same for every deck: built by `sample_walks`."""
    seed : int
    steps : list[str]           # "weak" | "normal" | "elite" | "boss" | "rest" | "treasure" | "shop" | "unknown"
    act : int
    act_id : str
    rooms : object              # encounters.Rooms: the encounters of the act in the order they come (the first `*_fought` are behind the agent)
    normal_fought : int
    elite_fought : int
    floor : int
    take_rate : float           # chance WalkAgent takes the card of a card reward
    ascension : int = 0

    @property
    def fights(self) -> int:
        """The fights of the walk (the second boss of ascension 10 counts)."""
        return sum(ROOM_OF_STEP[s] in ("Monster", "Elite", "Boss") for s in self.steps) + (self.rooms.second_boss is not None and "boss" in self.steps)


@dataclass
class EventPlan:
    """An event option to play before a walk: the event's id, the keys already chosen on its earlier pages, and the key of the option to try."""
    event_id : str
    path : list[str]
    option : str


@dataclass
class AncientPlan:
    """The relic to take from an ancient's offer before a walk (the engine's own pickup: its effect, its setup, the screens it queues)."""
    ancient_id : str
    relic : str
    setup : dict

    def option(self) -> AncientOption:
        return AncientOption(self.relic, setup=dict(self.setup))


class EventMismatch(Exception):
    """The event the game shows does not match the engine's model of it (an unknown option key): the agent leaves the choice to its fallback."""


class PlanPicker(CardPicker):
    """The card choices inside an event option, as the agent would make them: a curse, a Strike, a Defend go first (removal, transform), the rarest card is upgraded or taken."""
    @staticmethod
    def _rank(card : dict) -> int:
        from agents.deck_eval.shop_chooser import removal_rank
        r = removal_rank(card)
        return 9 if r is None else r

    def remove(self, deck, n, allowed):
        return sorted(allowed, key=lambda i: (self._rank(deck[i]), i))[:n]

    def transform(self, deck, n, allowed):
        return sorted(allowed, key=lambda i: (self._rank(deck[i]), i))[:n]

    def upgrade(self, deck, n, allowed):
        return sorted(allowed, key=lambda i: (str(deck[i].get("id", "")).startswith(("STRIKE", "DEFEND")), -RARITY_RANK.get(deck[i].get("rarity"), 0), i))[:n]

    def enchant(self, deck, allowed, n=1):
        return sorted(allowed, key=lambda i: (-RARITY_RANK.get(deck[i].get("rarity"), 0), i))[:n]

    def take(self, offered, n):
        return sorted(range(len(offered)), key=lambda i: (-RARITY_RANK.get(offered[i].get("rarity"), 0), i))[:n]


@dataclass
class WalkResult:
    reward : float              # rooms of progress (see the module docstring)
    alive : bool                # cleared the act's route (the lookahead into the next act is only in the reward)
    hp : int                    # HP at the end
    fights : int                # rooms cleared, the lookahead's included


class WalkAgent(BaseAgent):
    """The decisions inside a walk. Rest, upgrades, rewards and relics are BaseAgent's; a card reward takes the rarest card by chance `take_rate`."""
    name = "walk"

    def __init__(self, take_rate : float, seed : int):
        super().__init__()
        self.take_rate, self.seed = take_rate, seed
        self._rng = random.Random(seed)

    def _get_card_reward_decision(self, decision):
        cards = [o for o in decision.options if "id" in (o.data or {})]
        skip = next((o for o in decision.options if o.action.get("action") == "skip_card_reward"), None)
        if not cards or self._rng.random() >= self.take_rate:
            return skip or decision.options[0]
        best = max(RARITY_RANK.get(o.data.get("rarity"), 0) for o in cards)
        return self._rng.choice([o for o in cards if RARITY_RANK.get(o.data.get("rarity"), 0) == best])


    def _get_event_decision(self, decision):
        """A random option, drawn from the walk's seed and the screen alone: whatever the deck did before, every deck meets the same choice."""
        key = "%s/event/%s/%s" % (self.seed, decision.state.get("event_id"), "|".join(o.label for o in decision.options))
        return random.Random(key).choice(decision.options)

    def _get_shop_decision(self, decision):
        """Spend everything: the cheapest relic that can be paid, else the removal of a curse or a Strike, else the rarest card (the cheaper of equals), else a potion; then leave."""
        from agents.deck_eval.shop_chooser import SHOP_RELIC_POSITION, removal_rank
        relic_items = [i for i in decision.state.get("items") or [] if i.get("category") == "relic"]
        shop_relic = relic_items[SHOP_RELIC_POSITION]["index"] if len(relic_items) > SHOP_RELIC_POSITION else None         # the shop's own relic (the 3rd listed) is never bought
        buys = [o for o in decision.options if o.name == "shop_purchase" and not ((o.data or {}).get("category") == "relic" and (o.data or {}).get("index") == shop_relic)]
        leave = next((o for o in decision.options if o.name == "proceed"), decision.options[-1])
        by = lambda category: [o for o in buys if (o.data or {}).get("category") == category]
        if by("relic"):
            return min(by("relic"), key=lambda o: o.data.get("cost", 0))          # the cheapest: the dear ones are overpriced
        deck = decision.player.get("deck") or []
        if by("card_removal") and any(removal_rank(c) in (0, 1) for c in deck):
            return by("card_removal")[0]
        if by("card"):
            return max(by("card"), key=lambda o: (RARITY_RANK.get(o.data.get("card_rarity"), 0), -o.data.get("cost", 0)))
        if by("potion"):
            return min(by("potion"), key=lambda o: o.data.get("cost", 0))
        return leave

    def _get_card_select_decision(self, decision):
        """A card to remove: a curse, else a Strike, else a Defend; any other card screen is BaseAgent's."""
        from agents.deck_eval.shop_chooser import removal_rank
        picks = decision.options_named("select_card")
        confirm = decision.options_named("confirm_selection")
        if picks and not confirm and "remove" in str(decision.state.get("screen_type", "")).lower():
            ranked = [(removal_rank(o.data), i, o) for i, o in enumerate(picks) if removal_rank(o.data) is not None]
            if ranked:
                return min(ranked, key=lambda r: (r[0], r[1]))[2]
        return super()._get_card_select_decision(decision)


class RouteSimulator(RunSimulator):
    """`RunSimulator`'s rooms for a run that is already under way, along a list of rooms instead of a map. Fights are played with the rollout policy."""

    def __init__(self, run : RunState, walk : Walk, config, event : EventPlan | AncientPlan | None = None):
        self.walk, self.config, self.opening, self.turn_limit = walk, config, event, None
        self.agent = WalkAgent(walk.take_rate, walk.seed)
        self.ascension, self.time_budget = run.ascension, None
        self.game, self.search = GameRng(walk.seed), SearchRng(walk.seed)
        self.run_state = run
        self.fights, self.took_damage, self.illegal = 0, True, 0
        self.shared_ancients, self.cause, self.won, self.visited = {}, None, False, []
        self.credits : list[float] = []         # the progress of each room cleared
        self.partial, self.in_room = 0.0, False

    def reseed(self, label):
        """Every stream of the run starts again from the walk's seed and `label`: a room does not depend on how many draws an earlier one made."""
        for name in STREAMS:
            self.game.stream(name).seed(f"{self.walk.seed}/{name}/{label}")

    def play(self, sim):
        """The fight to its end (or MAX_TURNS) with the rollout policy; every deck meets each turn with the same dice."""
        cs, cfg = sim.combat_state, self.config
        end_turn = cs.turn_number + (self.turn_limit or MAX_TURNS)
        turn = cs.turn_number
        while not sim.is_over and cs.turn_number < end_turn:
            if cs.turn_number != turn:
                turn = cs.turn_number
                self.game.stream("combat").seed(f"{self.walk.seed}/turn/{self.fights}/{turn}")
            action = None
            try:
                actions = sim.get_available_actions()
                if not actions:
                    break
                with self.game.scope("combat"):
                    action = rollout_policy(sim, actions, cfg.rollout, cfg.heuristic)
                    sim.perform_action(action)
            except Exception as error:         # an engine bug met by this rollout: the walk ends here, scored as a death in this room
                note_engine_error(error, sim, action)
                self.partial = 0.0
                raise RunOver

    def fight_room(self, room : str, encounter, first_of_two : bool = False, last_boss : bool = False):
        r = self.run_state
        r.visit(room, encounter.id)
        final = room == "Boss" and r.act == 3 and (r.hidden.rooms.second_boss is None or last_boss)
        self.fight(encounter, room, final)
        run_hooks.combat_finished(r, room, self.game.stream("relics"))
        if not first_of_two:
            self.rewards(encounter)

    def fight(self, encounter, room : str, final : bool = False, variant=None, turn_limit=None) -> bool:
        r = self.run_state
        hp_before = r.hp
        sim = start_fight(r, encounter.id, room.lower(), self.game, final_fight=final)
        self.fights += 1
        cs = sim.combat_state
        expected, hp0, max0 = outcome_score.expected_total_hp(cs), cs.player.current_hp, cs.player.max_hp
        self.turn_limit = turn_limit
        self.play(sim)
        won = cs.player.current_hp > 0 and all(e.is_minion or e.current_hp <= 0 for e in cs.enemies)
        if not won:
            self.partial = max(0.0, min(0.99, 1.0 - outcome_score.enemy_progress_left(cs, expected)))         # how far the deck got before it died
        carry_back(r, sim)
        improvement = cs.player.status.get(StatusId.IMPROVEMENT)
        if improvement is not None and not r.dead:
            self.ctx().upgrade_random(improvement.amount)
        self.took_damage = r.hp < hp_before or r.dead
        if r.dead or (not won and turn_limit is None):
            self.cause = encounter.id
            raise RunOver
        return won

    def event_fight(self, *args, **kwargs):
        """A fight an event started: not a room of its own (the event's room is scored when it is over); the rewards it pays and the HP it costs show in the rooms after it, and losing it ends the walk."""
        fights = self.fights
        self.fights = 1000 + fights             # the fight's dice have a label of their own: the fights after it are dealt the same dice as without it
        try:
            super().event_fight(*args, **kwargs)
        finally:
            self.fights = fights

    def unknown_room(self):
        """A "?": the room the game's odds turn it into (RunSimulator.enter). A fight there is the room's own (its rewards and HP count)."""
        r = self.run_state
        kind = r.hidden.unknown_odds.roll(self.game.stream("unknown_room"), run_hooks.unknown_room_blacklist(r))
        if run_hooks.golden_path_act(r):
            kind = "Event"
        run_hooks.room_entered(r, kind, True)
        if kind == "Monster":
            fights = self.fights
            self.fights = 1000 + fights             # its dice are its own: the rooms after it are dealt the same dice whatever this "?" turned into
            try:
                self.fight_room("Monster", self.next_fight("Monster"))
            finally:
                self.fights = fights
        else:
            {"Event": self.event, "Shop": self.shop, "Treasure": self.treasure}.get(kind, lambda: None)()

    def play_event(self, plan : EventPlan):
        """The event option `plan` names, played by the engine's EventSession on this run (the pages already chosen are replayed first; the numbers the event rolls
        come from the walk's own seed, the same for every option). A page with one option left is taken. What the option starts (a fight, a relic from the bag,
        card and potion rewards) happens as in the game."""
        r = self.run_state
        event = EVENTS.get(plan.event_id)
        if event is None:
            raise EventMismatch(plan.event_id)
        stream = self.game.stream("events")
        session = EventSession(event, r, stream, PlanPicker(stream))
        for key in plan.path + [plan.option]:
            if session.finished or key not in [o.key for o in session.available()]:
                raise EventMismatch("%s has no option %r" % (plan.event_id, key))
            session.choose(key)
            self.take_offers()
        while not session.finished and len(session.available()) == 1:
            session.choose(session.available()[0].key)
            self.take_offers()
        if r.dead:
            self.cause = event.id
            raise RunOver
        if r.pending_fight is not None:
            name, args = r.pending_fight, r.pending_fight_args
            r.pending_fight, r.pending_fight_args = None, {}
            if name in ENCOUNTERS:
                self.event_fight(ENCOUNTERS[name], **args)

    def play_room(self, step : str, label):
        """One room of the walk; the progress it is worth is credited when it is over (a death in it credits what the fight got through)."""
        r = self.run_state
        self.reseed(label)
        self.partial, self.in_room = 0.0, True
        r.floor += 1
        room = ROOM_OF_STEP[step]
        if step == "unknown":
            self.unknown_room()
        else:
            run_hooks.room_entered(r, room, False)
            if step in ("weak", "normal"):
                self.fight_room("Monster", self.next_fight("Monster"))
            elif step == "elite":
                self.fight_room("Elite", self.next_fight("Elite"))
            elif step == "boss":
                rooms = r.hidden.rooms
                if rooms.second_boss is not None:
                    self.fight_room("Boss", rooms.boss, first_of_two=True)
                    self.credits.append(1.0)
                    r.floor += 1
                    self.fight_room("Boss", rooms.second_boss, last_boss=True)
                else:
                    self.fight_room("Boss", rooms.boss)
            elif step == "rest":
                self.rest_site()
            elif step == "shop":
                self.shop()
            else:
                self.treasure()
        self.credits.append(1.0)
        self.in_room = False

    def next_act(self):
        """The ancient's room between acts: the heal (all of what is missing; 80% of it from the ascension that tires the traveler), the next act's rooms and events."""
        r, walk = self.run_state, self.walk
        act = r.act + 1
        act_id = ACT_IDS[act]
        rooms = generate_rooms(ACTS[act_id], random.Random(walk.seed + 7), ascension=r.ascension, last_act=act == 3)
        missing = r.max_hp - r.hp
        r.hp += int(missing * WEARY_TRAVELER_SHARE) if r.ascension >= WEARY_TRAVELER_ASCENSION else missing
        r.act, r.act_id, r.boss = act, act_id, rooms.boss.id
        r.hidden.rooms, r.hidden.normal_fought, r.hidden.elite_fought = rooms, 0, 0
        r.hidden.unknown_odds.reset()
        r.hidden.events, r.hidden.events_visited = list(ACTS[act_id].events + SHARED_EVENTS), 0
        random.Random(walk.seed + 8).shuffle(r.hidden.events)
        return route_steps(None, act)[:LOOKAHEAD_ROOMS]

    def walk_route(self) -> WalkResult:
        r, walk = self.run_state, self.walk
        max_hp0, alive = r.max_hp, False
        try:
            if isinstance(self.opening, AncientPlan):
                self.reseed("ancient")
                self.take_ancient_relic(self.opening.option())
            elif self.opening is not None:
                self.reseed("event")
                self.play_event(self.opening)
            for i, step in enumerate(walk.steps):
                self.play_room(step, i)
            alive = True
            if r.act < 3:
                for i, step in enumerate(self.next_act()):
                    self.play_room(step, "next%d" % i)
            else:
                self.credits.append(CLEAR_BONUS)
        except RunOver:
            if self.in_room:
                self.credits.append(self.partial)
        reward = sum(self.credits)
        survived = r.hp > 0 and not r.dead
        if survived:
            reward += POTION_CREDIT * len(r.potions) + MAX_HP_CREDIT * (r.max_hp - max_hp0)
        return WalkResult(reward, alive, max(0, r.hp), sum(c == 1.0 for c in self.credits))


def _normalized(deck : list[dict], target_types : dict[str, str]) -> list[dict]:
    """The deck as the fight builder reads it: a card the screen showed without its target gets the one of the card tables."""
    return [c if c.get("target_type") else dict(c, target_type=target_types.get(c["id"])) for c in deck]


def play_walk(walk : Walk, deck : list[dict], player : dict, config, target_types : dict[str, str], event : EventPlan | AncientPlan | None = None, simulator=None) -> WalkResult:
    """One walk with `deck`, from the run as `player` (hp, max hp, gold, relics, potions) has it; with `event`, that event option is played first.
    `simulator`: a RouteSimulator subclass to play it with (benchmarks/calibrate.py)."""
    run = RunState.from_player(player, _normalized(deck, target_types), act=walk.act, floor=walk.floor, ascension=walk.ascension)
    run.act_id, run.boss = walk.act_id, walk.rooms.boss.id
    hidden = Hidden()
    hidden.rooms, hidden.normal_fought, hidden.elite_fought = walk.rooms, walk.normal_fought, walk.elite_fought
    rng = random.Random(walk.seed)
    hidden.relic_bag = RelicGrabBag(rng)
    for relic in run.relics:
        hidden.relic_bag.remove(relic.get("id"))
    hidden.events, hidden.events_visited = list(ACTS[walk.act_id].events + SHARED_EVENTS), 0         # the events a "?" can turn into, in the order the act deals them
    random.Random(walk.seed + 1).shuffle(hidden.events)
    run.hidden = hidden
    return (simulator or RouteSimulator)(run, walk, config, event).walk_route()


def sample_walks(route, act : int, ascension : int, n : int, seed : int, floor : int = 1) -> list[Walk]:
    """`n` walks through the rooms of the route ahead, each with the hidden parts of the act drawn anew (same seed -> same walks).
    A route that ends in the boss reward (or no route) looks at an act as it will be: the next act's rooms, nothing behind the agent yet."""
    steps = route_steps(route, act)
    if not any(ROOM_OF_STEP[s] in ("Monster", "Elite", "Boss") for s in steps):
        steps = steps + ["normal"]
    in_act = route is not None and bool(route.kinds) and route.kinds[0] != "boss"
    played_in = fight_act(route, act)
    boss = normalize_boss_id(getattr(route, "boss", None)) if in_act else None
    variant = None
    if played_in == 1:
        variant = BOSS_ACTS[boss][1] if boss in BOSS_ACTS else (getattr(route, "act_model", None) if in_act else None)
    fought = list(route.elites_seen) if in_act else []
    normals = route.combats_before + (route.kinds[0] == "combat") if in_act else 0
    walks = []
    for i in range(n):
        wseed = seed * 100003 + i
        r = random.Random(wseed)
        act_id = variant or ACT_IDS.get(played_in) or r.choice(("OVERGROWTH", "UNDERDOCKS"))
        rooms = generate_rooms(ACTS[act_id], r, ascension=ascension, last_act=played_in == 3)
        if boss in ENCOUNTERS and BOSS_ACTS.get(boss, (0, act_id))[1] == act_id:
            rooms.boss = ENCOUNTERS[boss]
            if rooms.second_boss is rooms.boss:
                rooms.second_boss = r.choice([b for b in ACTS[act_id].bosses if b is not rooms.boss])
        rooms.elite = elite_sequence(act_id, fought, r)
        walks.append(Walk(wseed, steps, played_in, act_id, rooms, normals, len(fought), floor, EXTRA_CARD_SHARE.get(played_in, 0.3), ascension))
    return walks
