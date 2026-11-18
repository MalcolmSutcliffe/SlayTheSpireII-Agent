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
from agents.selfplay.choosers import Counts, Explorer, card_key, make_chooser, snapshot
from sts2_lite import rng
from sts2_lite.campaign.simulator import ROOM_OF_POINT, RunOver, RunSimulator, StalledFight

BIG_ROOMS = ("Elite", "Boss")
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
    """The walks' stand-in agent, except that card rewards go to the explorer and the path up the map is random."""
    def __init__(self, explorer : Explorer, sim : "SelfPlayRun", seed : int):
        super().__init__(1.0, seed)
        self.explorer, self.sim = explorer, sim

    def _get_map_decision(self, decision):
        return self._rng_choice(decision.options)

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


class SelfPlayRun(RouteSimulator):
    """The run simulator with the pilot's fights. `rooms`: a snapshot of the run on entering each room; `picks`: every card reward, with `after`, the run
    right after the pick (see reward_snapshot)."""
    def __init__(self, seed : int, config, explorer : Explorer, ascension : int = 0, scoring : DeckEvalConfig = DEFAULT, pilot : Pilot | str = Pilot()):
        RunSimulator.__init__(self, None, seed=seed, ascension=ascension, search_seed=seed, time_budget=None)
        self.walk = SimpleNamespace(seed=seed)          # the walks' fights seed their dice from it
        self.config, self.opening, self.turn_limit, self.scoring = config, None, None, scoring
        self.credits, self.partial, self.in_room, self.continuation = [], 0.0, False, 0.0
        self.agent = SelfPlayAgent(explorer, self, seed)
        self.rooms, self.picks = [], []
        self.pilot = parse_pilot(pilot)
        self.fight_kind = None          # the room of the fight being played (Monster, Elite, Boss)
        self.mcts_decisions = 0

    def enter(self, point):
        self.rooms.append({**snapshot(self.run_state), "room": ROOM_OF_POINT[point.type]})
        self.in_room = True
        super().enter(point)
        self.in_room = False

    def fight(self, encounter, room : str, *args, **kwargs) -> bool:
        self.fight_kind = room
        return super().fight(encounter, room, *args, **kwargs)

    def play(self, sim):
        if not self.pilot.mcts_plays(self.fight_kind):
            try:
                return super().play(sim)            # raises RunOver only when the engine failed in the fight
            except RunOver:
                self.cause = ENGINE_ERROR
                raise
        from agents.sts2_MCTS.MCTS import sts2_MCTS          # the MCTS only when a pilot needs it
        mcts, config = sts2_MCTS(), self.pilot.search_config()
        cs = sim.combat_state
        end_turn = cs.turn_number + (self.turn_limit or self.scoring.max_turns)
        decision, action = 0, None
        try:
            while not sim.is_over and cs.turn_number < end_turn:
                actions = sim.get_available_actions()
                if not actions:
                    return
                if len(actions) == 1:
                    action = actions[0]
                else:
                    rng.seed(f"{self.walk.seed}/mcts/{self.fights}/{decision}")         # the search's own draws (not the game's streams)
                    action, _ = mcts.monte_carlo_tree_search(cs, config)
                    decision += 1
                with self.game.scope("combat"):
                    sim.perform_action(action)
        except Exception as error:
            note_engine_error(error, sim, action)
            self.partial, self.cause = 0.0, ENGINE_ERROR
            raise RunOver
        finally:
            self.mcts_decisions += decision

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
             explorer : Explorer | None = None, pilot : str | Pilot = "rollout") -> dict:
    """The run with this `seed`: the same seed and settings play the same run. Returns {seed, ascension, pilot, rooms, picks, outcome}."""
    config = SearchConfig().tuned(rollout=WALK_POLICY)
    pilot = parse_pilot(pilot)
    if explorer is None:
        explorer = Explorer(make_chooser(chooser, f"{seed}/chooser"), counts or Counts(), c, epsilon, f"{seed}/explore")
    sim = SelfPlayRun(seed, config, explorer, ascension, pilot=pilot)
    outcome = sim.play_run()
    return {"seed": seed, "ascension": ascension, "pilot": pilot.name, "rooms": sim.rooms, "picks": sim.picks, "outcome": outcome}


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
