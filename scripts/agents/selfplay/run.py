"""One full simulated run (three acts, the game's own maps) played by the engine's run simulator: the engine's room handlers, fights played with the walks' rollout
policy (and its correction), and card rewards chosen by an `Explorer`. Everything the run saw is returned as plain data: a snapshot on entering each room, every card
pick, and the outcome.

The stand-in agent's other choices are the walks': rest when hurt else upgrade, a seeded random event option, spend everything in a shop, a random path up the map."""
from __future__ import annotations
from types import SimpleNamespace

from agents.deck_eval.config import DEFAULT, DeckEvalConfig
from agents.deck_eval.evaluator import WALK_POLICY
from agents.deck_eval.route_sim import RouteSimulator, WalkAgent
from agents.sts2_MCTS.params import SearchConfig
from agents.selfplay.choosers import Counts, Explorer, make_chooser, snapshot
from sts2_lite.campaign.simulator import ROOM_OF_POINT, RunOver, RunSimulator, StalledFight


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
        index, record = self.explorer.pick(snapshot(self.sim.run_state), [o.data for o in options])
        record["room"] = len(self.sim.rooms)
        self.sim.picks.append(record)
        if index == len(options):
            return skip or options[0]
        return options[index]


class SelfPlayRun(RouteSimulator):
    """The run simulator with the walks' fights. `rooms`: a snapshot of the run on entering each room; `picks`: every card reward."""
    def __init__(self, seed : int, config, explorer : Explorer, ascension : int = 0, scoring : DeckEvalConfig = DEFAULT):
        RunSimulator.__init__(self, None, seed=seed, ascension=ascension, search_seed=seed, time_budget=None)
        self.walk = SimpleNamespace(seed=seed)          # the walks' fights seed their dice from it
        self.config, self.opening, self.turn_limit, self.scoring = config, None, None, scoring
        self.credits, self.partial, self.in_room, self.continuation = [], 0.0, False, 0.0
        self.agent = SelfPlayAgent(explorer, self, seed)
        self.rooms, self.picks = [], []

    def enter(self, point):
        self.rooms.append({**snapshot(self.run_state), "room": ROOM_OF_POINT[point.type]})
        self.in_room = True
        super().enter(point)
        self.in_room = False

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
                "fights": self.fights, "final_deck": snapshot(r)["deck"], "relics": snapshot(r)["relics"]}


def play_run(seed : int, chooser : str = "rarity", counts : Counts | None = None, c : float = 0.5, epsilon : float = 0.05, ascension : int = 0,
             explorer : Explorer | None = None) -> dict:
    """The run with this `seed`: the same seed and settings play the same run. Returns {seed, rooms, picks, outcome}."""
    config = SearchConfig().tuned(rollout=WALK_POLICY)
    if explorer is None:
        explorer = Explorer(make_chooser(chooser, f"{seed}/chooser"), counts or Counts(), c, epsilon, f"{seed}/explore")
    sim = SelfPlayRun(seed, config, explorer, ascension)
    outcome = sim.play_run()
    return {"seed": seed, "ascension": ascension, "rooms": sim.rooms, "picks": sim.picks, "outcome": outcome}
