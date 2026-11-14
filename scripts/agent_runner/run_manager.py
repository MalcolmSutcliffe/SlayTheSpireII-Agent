"""One run of the agent against the live game, from the first floor to the end.
RunManager polls the game and routes each state: a fight goes to the CombatSession, a screen the agent decides on (map, rewards, rest site,
shop, event, card or relic pick, treasure) becomes a Decision with its legal options, the agent picks one, and the executor sends it.
Anything else (loading, the main menu, game over) is only waited out."""
import time
from pathlib import Path
from collections import Counter
from dataclasses import dataclass, field

from .combat_session import CombatSession
from .decision_builders import build_decision, reward_key
from .executors import execute
from agents.decision import CARD_REWARD, REWARDS
from .game_client import POLL_SECONDS, GameClient, dump

DEFAULT_LOG = "engine_mismatches.jsonl"     # where differences go when no run is named
SETTLE_BEFORE_DECIDING = True               # read a screen until it stops changing before deciding on it (it animates in)


@dataclass
class RunState:
    """What the manager knows about the run so far. The deck, relics, potions, hp and gold are not kept here: every state carries them in "player"."""
    act : int | None = None
    floor : int | None = None
    history : list[dict] = field(default_factory=list)      # every non-combat decision, in order

    def update(self, game_state : dict):
        context = game_state.get("context") or game_state.get("run") or {}
        self.act = context.get("act", self.act)
        self.floor = context.get("floor", self.floor)


class RunManager:
    """`tick` is one pass of the loop; `run` repeats it until Ctrl-C."""

    def __init__(self, agent, step : bool = False, verify : bool = True, log_path : str = DEFAULT_LOG, capture_dir : str | None = None,
                 decision_log : str | None = None, state_dir : str | None = None, fight_log : str | None = None, first_decision : int = 0,
                 client : GameClient | None = None):
        self.agent = agent
        self.single_step = step
        self.client = client or GameClient()
        self.combat = CombatSession(agent, self.client, step, verify, log_path, capture_dir, decision_log, state_dir, fight_log, first_decision)
        self.run_state = RunState()
        self.waiting_for = None     # what the loop last said it was waiting on, so it says so once
        self.tried : dict[str, set[str]] = {}       # screen (as the game showed it) -> actions sent on it that changed nothing
        self.declined = Counter()       # reward items the agent skipped: the game keeps listing them, so they are not claimed again
        self.opened = None              # the reward item whose card screen is open, to know what a Skip declines

    def run(self):
        try:
            while True:
                self.tick()
        except KeyboardInterrupt:
            combat = self.combat
            print(f"\nstopped. {combat.checked} step(s) checked, {combat.mismatched} with differences" + (f" (see {combat.log_path})" if combat.mismatched else ""))

    def tick(self):
        """One pass: read the game and, when it is the agent's turn to act, decide and act. Returns early to read the game again."""
        game_state = self.client.get_state()
        kind = self.combat.kind_of(game_state)
        if kind == "away":
            self.away(game_state)
            return
        self.waiting_for = None
        self.forget_rewards()           # a fight is on: the rewards of the last one are gone
        self.combat.handle(kind, game_state)

    def away(self, game_state : dict):
        """The game is not in a fight: close the one that was, then decide on the screen if it is one the agent decides on."""
        self.combat.leave(game_state)
        self.run_state.update(game_state)
        decision = build_decision(game_state, self.declined)
        if decision is not None and decision.kind not in (REWARDS, CARD_REWARD):
            self.forget_rewards()       # on to the next screen: the skipped rewards are left behind
        if decision is None or not decision.options:
            self.wait(game_state)
            return
        if SETTLE_BEFORE_DECIDING:
            game_state = self.client.settled(game_state)
            self.run_state.update(game_state)
            decision = build_decision(game_state, self.declined)
            if decision is None or not decision.options:
                return              # the screen moved on while it settled: read it again
        self.decide(game_state, decision)

    def forget_rewards(self):
        self.declined.clear()
        self.opened = None

    def track_rewards(self, decision, option):
        """Remember which reward a card screen belongs to, so that skipping its cards declines that reward and picking one uses it up."""
        action = option.action["action"]
        if decision.kind == REWARDS and action == "claim_reward":
            self.opened = option.data
        elif decision.kind == CARD_REWARD and action == "skip_card_reward" and self.opened is not None:
            self.declined[reward_key(self.opened)] += 1
            self.opened = None
        elif decision.kind == CARD_REWARD and action == "select_card_reward":
            self.opened = None

    def wait(self, game_state : dict):
        what = game_state.get("decision", game_state.get("type"))
        raw = game_state.get("raw") or {}
        if what == "unknown":
            what = f"unknown: state_type={game_state.get('raw_state_type')!r} room_type={raw.get('room_type')!r}"
        message = f"not in combat ({what}) - waiting for the next fight"
        if message != self.waiting_for:
            print(message)
            if game_state.get("decision") == "unknown":
                self.save_unknown(game_state)
            self.waiting_for = message
        time.sleep(1.0)

    def save_unknown(self, game_state : dict):
        """A screen the bridge could not name: keep it, so what the game was showing can be read afterwards."""
        try:
            path = Path(self.combat.state_dir or ".") / f"unknown_state_{int(time.time())}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(dump(game_state))
            print(f"saved the unrecognised state to {path}")
        except OSError as error:
            print(f"could not save the unrecognised state: {error}")

    def decide(self, game_state : dict, decision):
        screen = dump(game_state)
        tried = self.tried.setdefault(screen, set())
        self.tried = {screen: tried}                    # only the screen the game is on now is remembered
        options = [o for o in decision.options if dump(o.action) not in tried]
        if not options:
            print(f"every option on this {decision.kind} screen was tried and nothing changed - act in the game")
            time.sleep(1.0)
            return
        decision.options = options
        option = self.agent.get_decision(decision)
        if option not in options:
            print(f"the agent chose something that is not on the {decision.kind} screen ({option!r}); taking {options[0].label!r} instead")
            option = options[0]
        self.waiting_for = None
        if self.single_step:
            input(f"{decision.kind}: {option.label} - press Enter to send ... \n")
        print(f"floor {self.run_state.floor} {decision.kind}: {option.label}")
        self.run_state.history.append({"floor": self.run_state.floor, "act": self.run_state.act, "kind": decision.kind,
                                       "label": option.label, "action": option.action})
        self.track_rewards(decision, option)
        execute(self.client, option.action)
        if not self.client.wait_for_change(screen):
            tried.add(dump(option.action))
            print(f"the game did not react to {option.label!r}")
