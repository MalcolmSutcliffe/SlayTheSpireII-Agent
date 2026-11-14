"""The fight in progress: the sim that shadows the live game, the agent's decisions in it, and the checks of the sim against the game.
A CombatSession lives for a whole run. It is handed every state the game is in a fight for (and the first one after), reads each into the
sim, compares the sim's last prediction with it, lets the agent decide, sends the action, and keeps the fight's logs.
`CombatSimulator` (sts2_lite) is the rules; this is the code that keeps the rules lined up with the real game."""
import time

from agents.verify import compare, game_order_matches, is_random_step, is_unpredictable_step, some_target_roll_matches
from .combat_logs import (capture_turn_start, fight_end, fight_start, fight_update, install_search_hook, log_decision, log_mismatch,
                          potions_of, report_unimplemented, save_decision_state, write_fight)
from .game_client import POLL_SECONDS, GameClient, dump
from sts2_lite import rng
from sts2_lite.card import CardType
from sts2_lite.combat import CombatState, CombatSimulator

TURN_CHANGE_TIMEOUT = 10.0      # seconds to wait for the round number to advance after End Turn
LOCKED_READS = 8                # reads of locked-looking cards (about 3 s) before the agent acts anyway
NEW_FIGHT_TIMEOUT = 30.0        # seconds a new fight may show no hand before the agent acts anyway (a fight that starts with no cards drawn)
TIME_BUDGET_SECONDS = 10.0      # Max time allocated for agent to think

###
### Reading the game
###

def is_final_fight(game_state : dict, seen_floors : set[int]) -> bool:
    """True in the fight after which the run is won. Act 3's boss is the last fight; from Ascension 10 there is a second final boss,
    so the last fight is the Act 3 boss fight that comes after another one (a floor not seen before). `seen_floors` is filled here.
    Restarting the agent in the middle of the second boss fight reads it as the first: potions stay priced, which is the safe side."""
    context = game_state.get("context") or game_state.get("run") or {}
    if game_state.get("room_type") != "boss" or context.get("act", 0) < 3:
        return False
    floor = context.get("floor")
    others = {f for f in seen_floors if f != floor}
    seen_floors.add(floor)
    return context.get("ascension", 0) < 10 or bool(others)

def in_subject_fight(combat_state : CombatState | None) -> bool:
    """The fight the simulated state belongs to has the Test Subject in it, alive or lying dead."""
    return combat_state is not None and any(e.enemy_id.startswith("TEST_SUBJECT") for e in combat_state.enemies + combat_state.dormant)

def kind_of(game_state : dict, expecting_choice : bool = False, subject_fight : bool = False) -> str:
    """What the loop should do with a state: "play" (agent's turn), "pick" (a card choice during combat),
    "busy" (combat, but the game is animating or it is the enemies' turn) or "away" (not in combat).
    `subject_fight`: the fight is against the Test Subject, which is not listed while it lies dead between its forms: an empty enemy list
    in the player's turn is then a turn to play (the cards that need a target cannot be played, so it ends the turn), not a fight being set up."""
    if game_state.get("type") != "decision":
        return "busy"
    decision = game_state.get("decision")
    if decision == "combat_play":
        if game_state.get("turn") != "player" or game_state.get("is_play_phase") is False:
            return "busy"
        if game_state.get("enemies") == [] and not subject_fight:
            return "busy"       # the killed enemy is gone but its spawns (Phrog Parasite's Wrigglers) are not there yet, or the fight is ending
        if not all(key in (game_state.get("player") or {}) for key in ("hp", "max_hp", "block", "status", "hand")):
            return "busy"       # the player's data is gone as the last enemy dies and the fight is torn down
        return "play"
    if decision == "hand_select":
        return "pick"
    if decision == "card_select" and game_state.get("screen_type") == "NCombatPileCardSelectScreen":
        return "pick"
    if decision == "card_select" and game_state.get("screen_type") == "choose" and expecting_choice:     # Discovery's offer
        return "pick"
    return "away"

def floor_of(game_state : dict) -> int | None:
    context = game_state.get("context") or game_state.get("run") or {}
    return context.get("floor")

def first_state_ready(game_state : dict) -> bool:
    """The first turn of a fight has been set up: the hand is drawn and the energy given (before that the game reports an empty hand,
    and the only thing to do is End Turn)."""
    return bool(game_state.get("hand")) and (game_state.get("energy") or 0) > 0

def turn_is_changing(game_state : dict, ended : dict | None) -> bool:
    """The bridge never reports the play phase. After End Turn it still says "player" while the enemies act, then the
    round number advances before the next hand is drawn and the energy refilled (hand empty, energy 0).
    `ended`: the round the agent ended (and when). Wait for a started turn, but not forever: an extra turn
    (Pael's Eye) keeps the round number."""
    if ended is None or time.time() - ended["time"] >= TURN_CHANGE_TIMEOUT:
        return False
    if game_state.get("round") == ended["round"]:
        return True
    return not game_state.get("hand") and game_state.get("energy") == 0

def cards_look_locked(combat_state : CombatState) -> bool:
    """Affordable cards that the game shows as unplayable although nothing in the rules explains it: the game is not
    in its play phase (the sim already clears the flag for Ringing and Normality)."""
    energy = combat_state.energy
    affordable = [c for c in combat_state.player.hand
                  if not c.unplayable and c.type not in (CardType.Status, CardType.Curse) and (c.energy_cost == "X" or c.energy_cost <= energy)]
    return bool(affordable) and all(c.is_unplayable for c in affordable)

###
### Checking the sim against the game
###

def verify_step(batch : dict, game_state : dict, actual : CombatState, log_path : str) -> bool:
    """Compare the state the sim predicted after the batch of actions with the one the game now reports."""
    drank = any(a["action"] == "use_potion" for a in batch["actions"])
    if potions_of(batch["before"]) != potions_of(game_state) and not drank:
        print("a potion changed during this step without the agent using one (Fairy in a Bottle?): not compared")
        return True
    if batch.get("unpredictable"):
        print("a card played a random card from the draw pile that the agent could not see (Havoc): not compared")
        return True
    diffs = compare(batch["predicted"], actual, random_step=batch["random_step"], random_target=batch.get("random_target", False))
    if diffs and batch.get("random_target") and some_target_roll_matches(batch["before_sim"], batch["actions"], actual, batch["random_step"]):
        diffs = []          # the game hit other enemies than the sim did, and the damage differs because the enemies do
    if diffs and game_order_matches(batch["before_sim"], batch["actions"], batch["before"], actual):
        diffs = []          # the sim does not know the draw order; with the game's order the outcome is exactly the game's
    if diffs:
        log_mismatch(log_path, batch, game_state, diffs, batch["predicted"], actual)
    return not diffs

def chained_into_new_fight(batch : dict | None, game_state : dict) -> bool:
    """The sim ended the combat with the last action and the game is in a play state with other enemies: the first boss of a double-boss
    act fell and the next one follows at once (no screen in between), so there is nothing to compare."""
    if batch is None or not batch.get("predicted_over"):
        return False
    before = {e.get("entity_id") for e in (batch["before"].get("enemies") or [])}
    now = {e.get("entity_id") for e in (game_state.get("enemies") or [])}
    return bool(now) and not (before & now)

def verify_combat_end(batch : dict, game_state : dict, log_path : str):
    """The game left combat after the batch: the sim must have ended it too."""
    if not batch["predicted_over"]:
        log_mismatch(log_path, batch, game_state, ["the game ended the combat but the sim did not"], batch["predicted"], None)

###
### The session
###

class CombatSession:
    """Plays the fights of one run: the sim's last state, the actions awaiting comparison, and the fight in progress live on the object."""

    def __init__(self, agent, client : GameClient, step : bool = False, verify : bool = True, log_path : str = "engine_mismatches.jsonl",
                 capture_dir : str | None = None, decision_log : str | None = None, state_dir : str | None = None,
                 fight_log : str | None = None, first_decision : int = 0):
        self.agent, self.client, self.single_step, self.verify, self.log_path = agent, client, step, verify, log_path
        self.capture_dir, self.decision_log, self.state_dir, self.fight_log = capture_dir, decision_log, state_dir, fight_log
        self.search = install_search_hook() if (decision_log or fight_log) else None
        self.previous = None        # state after the last action: the bridge reports no per-turn history
        self.batch = None           # actions since the last point the sim and the game could be compared
        self.fight_floor = None     # floor of the fight in progress: a play state on another floor is a new fight, whose first state is awaited
        self.arrived = None         # when the first state of that new fight was first read
        self.ended = None           # {"round", "time"} of the last End Turn, until the next round starts
        self.captured_round = None  # round whose first state was saved to capture_dir
        self.fight = None           # summary of the fight in progress (--fight-log)
        self.decisions = first_decision     # numbers the decision log and the saved states
        self.just_mismatched = False
        self.locked_reads = 0
        self.checked = self.mismatched = 0
        self.reported_cards = set()     # NOT_IMPLEMENTED card ids already logged this run
        self.cards_owed = None      # how many cards the hand and piles must hold once the last action has finished
        self.act3_boss_floors : set[int] = set()     # floors of the Act 3 boss fights seen in this run

    def kind_of(self, game_state : dict) -> str:
        return kind_of(game_state, self.previous is not None and self.previous.pending_choice is not None, in_subject_fight(self.previous))

    def handle(self, kind : str, game_state : dict):
        """One pass over a state that is not "away": wait out a busy game, or read the state into the sim and act on it. Returns early to read the game again."""
        if kind == "play" and (self.entering_new_fight(game_state) or turn_is_changing(game_state, self.ended)):
            kind = "busy"
        if kind == "busy":
            time.sleep(POLL_SECONDS)
            return
        if kind == "play":
            self.ended = None

        game_state = self.client.settled(game_state, self.cards_owed)
        self.cards_owed = None
        if self.kind_of(game_state) != kind:
            return              # the game moved on while the state settled (the last enemy died and the fight is torn down): read it again
        combat_state = self.read_state(kind, game_state)
        if combat_state is None:
            return
        self.track_fight(kind, game_state)
        self.capture_round(kind, game_state)
        if self.single_step:
            input("waiting for input ... \n")
        self.decide_and_act(game_state, combat_state)

    def entering_new_fight(self, game_state : dict) -> bool:
        """A play state on a floor the agent has not fought on yet: wait until the first turn has been dealt (hand and energy), however long it
        takes (up to NEW_FIGHT_TIMEOUT), instead of acting on the state of a turn that has not started."""
        floor = floor_of(game_state)
        if floor is None or floor == self.fight_floor:
            return False
        if self.arrived is None:
            self.arrived = time.time()
        if first_state_ready(game_state):
            pass
        elif time.time() - self.arrived < NEW_FIGHT_TIMEOUT:
            return True
        else:
            print("the new fight shows no hand - acting anyway")
        self.fight_floor, self.arrived = floor, None
        return False

    def finish_fight(self, game_state : dict):
        if self.fight is not None and self.fight_log:
            write_fight(self.fight_log, fight_end(self.fight, game_state))

    def forget_fight(self):
        """Nothing carries from one fight to the next."""
        self.fight = self.previous = self.batch = None
        self.captured_round = None
        self.client.picked_on_screen.clear()

    # ---- the game is not in a fight

    def leave(self, game_state : dict):
        """The game is not in a fight (any more): close the one that was, and expect the next to be set up in stages like any turn."""
        self.finish_fight(game_state)
        if self.batch is not None and self.verify and self.batch["predicted"] is not None:
            verify_combat_end(self.batch, game_state, self.log_path)
            self.checked += 1
        self.forget_fight()
        self.fight_floor = self.arrived = None      # the next fight's first turn is set up in stages: its first state is awaited (entering_new_fight)
        self.ended = None

    # ---- reading the game into the sim

    def read_state(self, kind : str, game_state : dict) -> CombatState | None:
        """The sim's state for the game's, or None when this pass has nothing to decide (a confirmation or automatic pick was sent,
        the screen cannot be read, the cards are still locked)."""
        previous = self.previous
        choosing_optionally = previous is not None and previous.pending_choice is not None and previous.pending_choice.optional
        if kind == "pick" and game_state.get("can_confirm") and not choosing_optionally:
            self.client.picked_on_screen.clear()
            self.client.confirm_if_ready()      # a card is already picked; only the confirmation is missing
            return None             # (an "up to N" screen can be confirmed from the start: the agent decides)

        if kind == "pick" and previous is not None and previous.pending_choice is None and self.batch is not None \
                and self.batch["predicted"] is not None and game_state.get("cards"):
            before = dump(game_state)
            self.client.auto_pick(game_state)
            if not self.client.wait_for_change(before):
                print("the game did not react to the automatic pick - pick it in the game")
                input("press Enter when done ... \n")
            return None

        if kind == "pick" and previous is not None and previous.pending_choice is not None:
            # the sim knows what this pick is for; a pile screen has no fight data to load
            combat_state = CombatState.deepcopy(previous)
            combat_state.adopt_offer(game_state.get("cards") or [])     # options the sim drew at random (Seeker Strike)
            return combat_state
        if kind == "pick" and game_state["decision"] != "hand_select":
            print("cannot read this card selection - pick it in the game")
            time.sleep(1.0)
            return None
        return self.read_play_state(kind, game_state)

    def read_play_state(self, kind : str, game_state : dict) -> CombatState | None:
        if kind == "play" and chained_into_new_fight(self.batch, game_state):
            self.finish_fight(game_state)
            self.forget_fight()
        combat_state = CombatState.from_dict(game_state)
        combat_state.final_fight = is_final_fight(game_state, self.act3_boss_floors)
        report_unimplemented(game_state, self.log_path, self.reported_cards)
        combat_state.carry_turn_counters(self.previous)
        combat_state.carry_card_costs(self.previous)    # true costs under Brilliant Scarf's all-zero display
        combat_state.carry_known_top(self.previous)    # cards the agent put on top (Headbutt)
        combat_state.carry_boss_state(self.previous)         # the form of a dead Test Subject
        combat_state.carry_combat_counters(self.previous)    # HP-loss events (Tear Asunder), Inferno plays
        if cards_look_locked(combat_state):
            self.locked_reads += 1
            if self.locked_reads < LOCKED_READS:
                time.sleep(POLL_SECONDS)        # not the play phase yet: neither act nor compare
                return None
            print("cards stay locked although they are affordable - acting anyway")
        self.locked_reads = 0
        if self.batch is not None and self.batch["predicted"] is not None:
            if self.verify:
                self.checked += 1
                if not verify_step(self.batch, game_state, combat_state, self.log_path):
                    self.mismatched += 1
                    self.just_mismatched = True
            self.batch = None
        return combat_state

    # ---- bookkeeping per pass

    def track_fight(self, kind : str, game_state : dict):
        if self.fight_log and kind == "play":
            if self.fight is None:
                self.fight = fight_start(game_state)
            fight_update(self.fight, game_state, mismatched=self.just_mismatched)
        self.just_mismatched = False

    def capture_round(self, kind : str, game_state : dict):
        if self.capture_dir and kind == "play" and game_state.get("round") != self.captured_round:
            self.captured_round = game_state.get("round")
            print("captured", capture_turn_start(game_state, self.capture_dir))

    # ---- deciding, predicting and acting

    def decide_and_act(self, game_state : dict, combat_state : CombatState):
        started = time.perf_counter()
        action = self.agent.get_combat_action(combat_state, TIME_BUDGET_SECONDS)
        self.decisions += 1
        if self.state_dir:
            save_decision_state(self.state_dir, self.decisions, game_state)
        if self.decision_log or self.fight_log:
            record = log_decision(self.decision_log, game_state, combat_state, action, time.perf_counter() - started, self.search, self.decisions,
                                  TIME_BUDGET_SECONDS)
            if self.fight is not None:
                fight_update(self.fight, game_state, record)
        picking_more = self.predict(game_state, combat_state, action)
        self.send(action, game_state, picking_more)

    def predict(self, game_state : dict, combat_state : CombatState, action : dict) -> bool:
        """Play the action in the sim and add it to the batch awaiting comparison. Returns whether the sim waits for a further pick."""
        batch = self.batch
        if batch is None:
            batch = self.batch = {"before": game_state, "actions": [], "before_sim": CombatState.deepcopy(combat_state)}
        batch["actions"].append(action)
        self.previous = CombatState.deepcopy(combat_state)
        simulator = CombatSimulator(self.previous)
        rolls = rng.target_rolls
        simulator.perform_action(action)
        batch["random_target"] = batch.get("random_target", False) or rng.target_rolls != rolls     # the game may have hit another enemy
        picking_more = self.previous.pending_choice is not None
        batch["predicted"] = None if picking_more else self.previous
        batch["predicted_over"] = simulator.is_over
        batch["random_step"] = is_random_step(batch["before_sim"], self.previous, batch["actions"])
        batch["unpredictable"] = batch.get("unpredictable", False) or is_unpredictable_step(batch["before_sim"], batch["actions"])
        if batch["predicted"] is not None:
            p = batch["predicted"].player
            self.cards_owed = len(p.hand) + len(p.draw_pile) + len(p.discard_pile) + len(p.exhaust_pile)     # wait for every card to land
        return picking_more

    def send(self, action : dict, game_state : dict, picking_more : bool):
        before = dump(game_state)
        if action["action"] == "end_turn":
            self.ended = {"round": game_state.get("round"), "time": time.time()}
        self.client.act(action, game_state, picking_more)
        if action["action"] in ("play_card", "end_turn", "use_potion") and not self.client.wait_for_change(before):
            print("the game did not react to", action)
            log_mismatch(self.log_path, self.batch, self.client.get_state(), [f"the game ignored {action}, which the sim treats as legal"],
                         self.previous, None)
            input("fix it in the game, then press Enter ... \n")
            self.previous = self.batch = None
