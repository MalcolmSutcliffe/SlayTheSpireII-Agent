"""Playing a fight out with the rollout policy: the one loop the deck evaluator's single fights and the route walks (route_sim) share."""
from __future__ import annotations
import contextlib

from agents.sts2_MCTS.rollout_policy import rollout_policy


class RolloutError(Exception):
    """The engine failed while a rollout played `action` (None: before an action was chosen). The engine's own error is the __cause__."""
    def __init__(self, action):
        super().__init__("engine error in a rollout (last action %r)" % (action,))
        self.action = action


def play_out(sim, config, max_turns : int, new_turn=None, scope=contextlib.nullcontext) -> None:
    """Plays `sim` with `config`'s rollout policy until the fight is over, no action is left, or `max_turns` more turns have begun.
    `new_turn(turn)` is called as each later turn begins (to reseed the dice, so every deck meets each turn with the same ones);
    `scope()` wraps choosing and performing each action (route_sim uses the run's combat stream). An error of the engine is raised as RolloutError."""
    cs = sim.combat_state
    end_turn = cs.turn_number + max_turns
    turn = cs.turn_number
    while not sim.is_over and cs.turn_number < end_turn:
        if cs.turn_number != turn:
            turn = cs.turn_number
            if new_turn is not None:
                new_turn(turn)
        action = None
        try:
            actions = sim.get_available_actions()
            if not actions:
                return
            with scope():
                action = rollout_policy(sim, actions, config.rollout, config.heuristic)
                sim.perform_action(action)
        except Exception as error:
            raise RolloutError(action) from error
