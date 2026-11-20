"""One full simulated run (three acts, the game's own maps) played by the engine's run simulator: the engine's room handlers, fights played by a `Pilot`, and
card rewards chosen by an `Explorer`. Everything the run saw is returned as plain data: a snapshot on entering each room, every card pick, and the outcome.

The pilot is who fights (`parse_pilot`):
  rollout        the walks' rollout policy, corrected towards what the MCTS would get (route_sim.CORRECTION): fast, but it plays Powers and setup badly
  mcts:N         the MCTS at N simulations for every fight (no paired or order checks); the correction is not applied to its fights
  mcts:N:big     the MCTS at N simulations for the elites and bosses, the corrected rollout policy for the other fights
The MCTS's own random draws are seeded from the run's seed, the fight and the decision, so a run with an MCTS pilot plays the same way twice.

The stand-in agent's other choices are the walks': rest when hurt else upgrade, a seeded random event option, spend everything in a shop, a random path up the map."""
from __future__ import annotations
import signal
from dataclasses import dataclass
from types import SimpleNamespace

from agents.deck_eval.config import DEFAULT, DeckEvalConfig
from agents.deck_eval.evaluator import WALK_POLICY
from agents.deck_eval.route_sim import RouteSimulator, WalkAgent, note_engine_error
from agents.sts2_MCTS.params import SearchConfig
from agents.pathing import PathPlanner
from agents.selfplay.choosers import Counts, Explorer, card_key, make_chooser, snapshot
from sts2_lite import rng
from sts2_lite.campaign.simulator import ROOM_OF_POINT, RunOver, RunSimulator, StalledFight

BIG_ROOMS = ("Elite", "Boss")
PATHS = ("random", "score")           # who picks the path up the map (SelfPlayAgent)
ENGINE_ERROR = "engine error"         # a run's `cause` when the engine failed in a fight: not a death of the deck (value_model.Rows leaves it out)
RUN_TIMEOUT = 900                     # seconds: a run still going after this is stuck (an endless loop in the engine), not slow; an MCTS-piloted run takes ~0.1-150 s


@dataclass(frozen=True)
class Pilot:
    """Who plays a run's fights: the rollout policy, or the MCTS at `sims` simulations (for every fight, or with `big_only` for the elites and bosses alone)."""
    sims : int = 0
    big_only : bool = False

    @property
    def name(self) -> str:
        return "rollout" if not self.sims else f"mcts:{self.sims}" + (":big" if self.big_only else "")

    def mcts_plays(self, room : str | None) -> bool:
        return self.sims > 0 and (not self.big_only or room in BIG_ROOMS)

    def search_config(self) -> SearchConfig:
        """The MCTS of the live agent, at a fixed number of simulations (no clock: the run is repeatable) and without the paired and order checks (they cost
        about as much again as the search)."""
        return SearchConfig().tuned(max_sims=self.sims, min_sims=min(100, self.sims), time_budget=None, paired_scenarios=0, order_check=False, check_workers=1)


def parse_pilot(text : str | Pilot) -> Pilot:
    """"rollout" | "mcts:N" | "mcts:N:big"."""
    if isinstance(text, Pilot):
        return text
    parts = text.split(":")
    if parts == ["rollout"]:
        return Pilot()
    if parts[0] == "mcts" and len(parts) in (2, 3) and parts[1].isdigit() and int(parts[1]) > 0 and (len(parts) == 2 or parts[2] == "big"):
        return Pilot(int(parts[1]), len(parts) == 3)
    raise ValueError(f"unknown pilot {text!r}: rollout, mcts:N or mcts:N:big")


def reward_snapshot(sim : "SelfPlayRun") -> dict:
    """The run as a card reward screen sees it: the room it was won in (`room`) and `reward` set, so the value model can tell it from a room just entered.
    The chooser scores the offered cards on this snapshot, and the snapshot with the pick added (`after` in the log) is a training row: the same kind of state."""
    return {**snapshot(sim.run_state), "room": sim.rooms[-1]["room"] if sim.rooms else None, "reward": True}


class SelfPlayAgent(WalkAgent):
    """The walks' stand-in agent, except that card rewards go to the explorer and the path up the map is `path`: "random", or "score" (the live agent's
    node-score planner, pathing.PathPlanner, without the walks: the route to the boss with the highest total node score)."""
    def __init__(self, explorer : Explorer, sim : "SelfPlayRun", seed : int, path : str = "random"):
        super().__init__(1.0, seed)
        self.explorer, self.sim = explorer, sim
        if path not in PATHS:
            raise ValueError(f"unknown path {path!r}: {PATHS}")
        self.planner = PathPlanner() if path == "score" else None

    def _get_map_decision(self, decision):
        return self.planner.choose(decision) if self.planner else self._rng_choice(decision.options)

    def _get_card_reward_decision(self, decision):
        options = [o for o in decision.options if "id" in (o.data or {})]
        skip = next((o for o in decision.options if o.action.get("action") == "skip_card_reward"), None)
        if not options:
            return skip or decision.options[0]
        snap = reward_snapshot(self.sim)
        index, record = self.explorer.pick(snap, [o.data for o in options])
        record["room"] = len(self.sim.rooms)
        record["after"] = snap if index == len(options) else dict(snap, deck=snap["deck"] + [card_key(options[index].data)])
        self.sim.picks.append(record)
        if index == len(options):
            return skip or options[0]
        return options[index]


def mcts_fight(sim, config : SearchConfig, label : str, max_turns : int, scope, tally : list | None = None) -> None:
    """Plays `sim` with the MCTS (`config`) until the fight is over, no action is left, or `max_turns` more turns have begun. The search's own draws are seeded
    from `label` and the decision's number (not the game's streams), so the same fight plays the same way twice; `scope()` wraps performing each action (the
    game's combat stream). `tally`, when given, is kept as [MCTS decisions made, the last action] (also when the engine fails: the caller reports the action)."""
    from agents.sts2_MCTS.MCTS import sts2_MCTS          # the MCTS only when a fight needs it
    mcts, cs = sts2_MCTS(), sim.combat_state
    tally = tally if tally is not None else [0, None]
    end_turn = cs.turn_number + max_turns
    while not sim.is_over and cs.turn_number < end_turn:
        actions = sim.get_available_actions()
        if not actions:
            return
        if len(actions) == 1:
            tally[1] = actions[0]
        else:
            rng.seed(f"{label}/{tally[0]}")
            tally[1], _ = mcts.monte_carlo_tree_search(cs, config)
            tally[0] += 1
        with scope():
            sim.perform_action(tally[1])


class SelfPlayRun(RouteSimulator):
    """The run simulator with the pilot's fights. `rooms`: a snapshot of the run on entering each room; `picks`: every card reward, with `after`, the run
    right after the pick (see reward_snapshot)."""
    def __init__(self, seed : int, config, explorer : Explorer, ascension : int = 0, scoring : DeckEvalConfig = DEFAULT, pilot : Pilot | str = Pilot(), path : str = "random"):
        RunSimulator.__init__(self, None, seed=seed, ascension=ascension, search_seed=seed, time_budget=None)
        self.walk = SimpleNamespace(seed=seed)          # the walks' fights seed their dice from it
        self.config, self.opening, self.turn_limit, self.scoring = config, None, None, scoring
        self.credits, self.partial, self.in_room, self.continuation = [], 0.0, False, 0.0
        self.agent = SelfPlayAgent(explorer, self, seed, path)
        self.rooms, self.picks = [], []
        self.pilot = parse_pilot(pilot)
        self.fight_kind = None          # the room of the fight being played (Monster, Elite, Boss)
        self.fight_state = None         # its combat state
        self.fight_log = []             # every fight of the run (fight_record)
        self.mcts_decisions = 0

    def enter(self, point):
        self.rooms.append({**snapshot(self.run_state), "room": ROOM_OF_POINT[point.type]})
        self.in_room = True
        super().enter(point)
        self.in_room = False

    def fight(self, encounter, room : str, *args, **kwargs) -> bool:
        """The fight, logged in `fight_log` however it ends (see fight_record)."""
        self.fight_kind = room
        before, self.fight_state = {**snapshot(self.run_state), "room": room}, None
        won = False
        try:
            won = super().fight(encounter, room, *args, **kwargs)
            return won
        finally:
            self.fight_log.append(self.fight_record(encounter, room, before, won))

    def fight_record(self, encounter, room : str, before : dict, won : bool) -> dict:
        """What a fight was and how it went, for a fight model: the run going in (`before`: a snapshot, its `room` the fight's kind), the encounter, who played it
        (`mcts`: the MCTS, else the rollout policy, whose result route_sim's correction then changed when `corrected`), and the result: `won`, `dead`, the HP and max HP
        after it (before the relics that heal after a fight), the turns it took, the potions it drank, and for a fight not won the share of the enemies' HP taken off
        (`progress`). `error`: the engine failed in it (not a result of the deck)."""
        r, cs = self.run_state, self.fight_state
        mcts = self.pilot.mcts_plays(room)
        return {"room_index": len(self.rooms) - 1, "encounter": encounter.id, "kind": room, "mcts": mcts, "corrected": not mcts and self.scoring.correct,
                "before": before, "won": bool(won), "dead": bool(r.dead or r.hp <= 0), "hp_after": max(0, r.hp), "max_hp_after": r.max_hp,
                "turns": cs.turn_number if cs is not None else None, "potions_used": max(0, len(before["potions"]) - len(snapshot(r)["potions"])),
                "progress": None if won else round(self.partial, 4), "error": str(self.cause).startswith(ENGINE_ERROR)}

    def play(self, sim):
        self.fight_state = sim.combat_state
        if not self.pilot.mcts_plays(self.fight_kind):
            try:
                return super().play(sim)            # raises RunOver only when the engine failed in the fight
            except RunOver:
                self.cause = ENGINE_ERROR
                raise
        tally = [0, None]
        try:
            mcts_fight(sim, self.pilot.search_config(), f"{self.walk.seed}/mcts/{self.fights}", self.turn_limit or self.scoring.max_turns, lambda: self.game.scope("combat"), tally)
        except Exception as error:
            note_engine_error(error, sim, tally[1])
            self.partial, self.cause = 0.0, ENGINE_ERROR
            raise RunOver
        finally:
            self.mcts_decisions += tally[0]

    def correct(self, sim, room : str, expected : float, hp0 : int):
        """The correction stands in for the MCTS: a fight the MCTS played is not corrected."""
        if not self.pilot.mcts_plays(room):
            super().correct(sim, room, expected, hp0)

    def play_run(self) -> dict:
        try:
            for act_index in range(3):
                self.start_act(act_index)
                self.travel()
            self.won = True
        except RunOver:
            pass
        except StalledFight as error:
            self.cause = f"stalled: {error}"
        r = self.run_state
        cleared = len(self.rooms) - (0 if self.won else 1)
        return {"rooms_cleared": max(0, cleared), "won": self.won, "act": r.act, "floor": r.floor, "hp": max(0, r.hp), "max_hp": r.max_hp, "cause": self.cause,
                "fights": self.fights, "mcts_decisions": self.mcts_decisions, "final_deck": snapshot(r)["deck"], "relics": snapshot(r)["relics"]}


def play_run(seed : int, chooser : str = "rarity", counts : Counts | None = None, c : float = 0.5, epsilon : float = 0.05, ascension : int = 0,
             explorer : Explorer | None = None, pilot : str | Pilot = "rollout", path : str = "random") -> dict:
    """The run with this `seed`: the same seed and settings play the same run. Returns {seed, ascension, pilot, rooms, picks, fight_log, outcome}."""
    config = SearchConfig().tuned(rollout=WALK_POLICY)
    pilot = parse_pilot(pilot)
    if explorer is None:
        explorer = Explorer(make_chooser(chooser, f"{seed}/chooser"), counts or Counts(), c, epsilon, f"{seed}/explore")
    sim = SelfPlayRun(seed, config, explorer, ascension, pilot=pilot, path=path)
    outcome = sim.play_run()
    return {"seed": seed, "ascension": ascension, "pilot": pilot.name, "rooms": sim.rooms, "picks": sim.picks, "fight_log": sim.fight_log, "outcome": outcome}


class RunTimedOut(BaseException):
    """Not an Exception: the engine's and the fights' `except Exception` (an engine error ends the run there) must let it through to play_run_guarded."""


def _timed_out(signum, frame):
    raise RunTimedOut


def play_run_guarded(seed : int, *args, timeout : int = RUN_TIMEOUT, play=None, **kwargs) -> dict:
    """play_run, given up after `timeout` seconds (0: never): an endless loop in the engine costs one run instead of stalling the suite. A run given up is
    logged with no rooms and picks and cause "engine error: timed out after N s", which value_model.Rows leaves out and evaluate.report does not compare.
    Uses SIGALRM: call it from the main thread of a process (a suite worker is one). `play`: the function that plays the run (default play_run; label.py's labeled runs)."""
    play = play or play_run
    if not timeout:
        return play(seed, *args, **kwargs)
    previous = signal.signal(signal.SIGALRM, _timed_out)
    signal.alarm(timeout)
    try:
        return play(seed, *args, **kwargs)
    except RunTimedOut:
        pilot = parse_pilot(kwargs.get("pilot", "rollout"))
        ascension = kwargs.get("ascension", args[4] if len(args) > 4 else 0)          # play_run(seed, chooser, counts, c, epsilon, ascension, ...)
        print(f"run {seed} timed out after {timeout} s (an endless loop in the engine?): logged as an engine error, replay it with play_run({seed}, ...) to find it", flush=True)
        return {"seed": seed, "ascension": ascension, "pilot": pilot.name, "rooms": [], "picks": [],
                "outcome": {"rooms_cleared": 0, "won": False, "act": 0, "floor": 0, "hp": 0, "max_hp": 0, "cause": f"{ENGINE_ERROR}: timed out after {timeout} s",
                            "fights": 0, "mcts_decisions": 0, "final_deck": [], "relics": []}}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
