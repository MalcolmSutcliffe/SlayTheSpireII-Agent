"""The order of the turn's plain plays.

Plays that leave nothing to chance (a potion, a block card, an attack with no draw) can be made in any order, and the order can
matter: Dexterity before the block, Vulnerable before the attack, a relic that wants less block. The tree cannot see it when
the difference is a point or two of HP, since its rollouts are independent. So the tree's line for this turn, up to its first
random play, is listed in every legal order; orders that end in the same state count once; and the distinct ones are replayed
under the same scenarios as the paired check. An order replaces the tree's only when it is ahead by PAIRED_Z standard errors.

The random play itself (a draw) is also tried first, the rest of the line after it and, when that is not as good, with the rest
left to the rollout policy: seeing the draw first costs nothing unless an order matters (Strength before the card that draws), and
the next search plans with what was drawn. Among the orders tied with the best, the one that draws first is played, as with
prefer_info for the root moves. The replay does not plan for the draw, so its verdict on drawing first is a lower bound.

Usage: OrderCheck(mcts).run(picked_root_child). The tree's line and the replay of a line come from the search (mcts)."""
import json
import time
from dataclasses import dataclass, field

from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState

from agents.sts2_MCTS.state_key import state_key
from agents.sts2_MCTS.stats import PAIRED_Z, TIE_MARGIN, spread

ORDER_MAX_UNITS = 7              # a line with more plays than this keeps the tree's order (the orderings multiply)
ORDER_MAX_STATES = 6             # distinct end states compared with the tree's own
ORDER_MAX_STEPS = 3000           # sim steps spent listing the orderings; past it the tree's order is kept
ORDER_EXTEND_Z = 1.0             # an order ahead by this many standard errors, but not yet by PAIRED_Z, is replayed under more scenarios
ORDER_MAX_ROUNDS = 4             # the scenarios of the order check are repeated at most this many times


def is_end_turn(move_id : tuple) -> bool:
    return move_id[0] == "action" and json.loads(move_id[1]).get("action") == "end_turn"

def is_choice(move_id : tuple) -> bool:
    """A move id of the answer to a pending card choice."""
    if move_id[0] == "choose_card":
        return True
    return move_id[0] == "action" and json.loads(move_id[1]).get("action") in ("choose_card", "confirm_choice")


@dataclass
class Replay:
    """One line to replay: its move ids, whether the draw comes first, and how it did against the tree's line."""
    moves : list
    draws_first : bool
    first : dict | None = None          # the action that starts it
    diffs : list = field(default_factory=list)      # its outcome minus the tree's line's, one per scenario
    gain : float = 0.0
    se : float = 0.0


class OrderCheck:
    def __init__(self, mcts):
        self.mcts = mcts
        self.config = mcts._search_config
        self.root = mcts._root_node.state
        self.steps = 0                          # sim steps spent listing the orderings
        self.found : dict[tuple, list[tuple]] = {}      # end state -> the move ids that lead there (the tree's order first)
        self.memo = set()

    def run(self, picked) -> dict | None:
        """Returns the details (and whether another order replaced the tree's, with its first play in "action"), or None when there
        is nothing to compare: the picked move is itself the random play, the line is too long to list, or no other order exists."""
        scenarios = self.config.paired_scenarios
        if scenarios < 2 or self.root.pending_choice is not None:
            return None
        line, self.tail = self.mcts._principal_line(picked)
        if not line:
            return None                                     # the picked move is the random play: it is already played first
        self.can_draw_first = self.tail is not None and not is_end_turn(self.tail)
        units = self._units(line)
        if len(units) > ORDER_MAX_UNITS or (len(units) < 2 and not self.can_draw_first):
            return None
        orders = self._distinct_orders(units)
        if orders is None:
            return None
        replays = self._replays(orders)
        if len(replays) < 2:
            return None
        total = self._replay_under_scenarios(replays, scenarios)
        chosen = self._choose(replays)
        return {
            "replaced" : chosen is not replays[0],
            "action" : chosen.first,
            "draws_first" : chosen.draws_first,
            "scenarios" : total,
            "plays" : len(units),
            "distinct" : len(orders),
            "compared" : [{"first" : r.first, "draws_first" : r.draws_first, "gain" : r.gain, "se" : r.se} for r in replays[1:]],
        }

    # ---- 1. the orders the line's plays can be made in

    @staticmethod
    def _units(line : list) -> list[tuple]:
        """A play and the choices it asks for (True Grit's card) move together."""
        units : list[tuple] = []
        for move in line:
            if is_choice(move) and units:
                units[-1] = units[-1] + (move,)
            else:
                units.append((move,))
        return units

    def _distinct_orders(self, units : list[tuple]) -> list[list[tuple]] | None:
        """Every order of the units that ends in a different state, the tree's own first. None when the tree's own order cannot be
        played or listing the orders took too many steps."""
        ids = {}
        unit_ids = [ids.setdefault(u, len(ids)) for u in units]
        self.by_id = {i: u for u, i in ids.items()}

        # the tree's own order first: it is what the others are compared with
        state, moves = self.root, []
        for uid in unit_ids:
            state = self._play(state, self.by_id[uid])
            if state is None:
                return None
            moves = moves + list(self.by_id[uid])
        self._finish(state, moves)
        if not self.found:
            return None
        self._explore(self.root, tuple(sorted(unit_ids)), [])
        if self.steps > ORDER_MAX_STEPS:
            return None
        return list(self.found.values())

    def _play(self, state : CombatState, unit : tuple) -> CombatState | None:
        c = CombatSimulator(CombatState.deepcopy(state))
        for move in unit:
            action = self.mcts._find_move(c, move)
            if action is None:
                return None
            c.perform_action(action)
            self.steps += 1
        return c.combat_state

    def _finish(self, state : CombatState, moves : list):
        if self.tail is not None and self.mcts._find_move(CombatSimulator(state), self.tail) is None:
            return
        self.found.setdefault(state_key(state), moves)

    def _explore(self, state : CombatState, remaining : tuple, moves : list):
        if self.steps > ORDER_MAX_STEPS or len(self.found) > ORDER_MAX_STATES:
            return
        if not remaining:
            self._finish(state, moves)
            return
        key = (state_key(state), remaining)
        if key in self.memo:
            return
        self.memo.add(key)
        for uid in dict.fromkeys(remaining):
            rest = list(remaining)
            rest.remove(uid)
            done = self._play(state, self.by_id[uid])
            if done is not None:
                self._explore(done, tuple(rest), moves + list(self.by_id[uid]))

    # ---- 2. the lines to replay

    def _replays(self, orders : list[list[tuple]]) -> list[Replay]:
        """Each order, then each order with the draw first, then the draw alone and the rest left to the policy."""
        tail_move = [self.tail] if self.tail is not None else []
        replays = [Replay(o + tail_move, False) for o in orders]
        if self.can_draw_first and self.mcts._find_move(CombatSimulator(self.root), self.tail) is not None:
            replays += [Replay(tail_move + o, True) for o in orders]
            replays.append(Replay(tail_move, True))
        for r in replays:
            r.first = self.mcts._find_move(CombatSimulator(self.root), r.moves[0])
        return replays

    # ---- 3. the replays under shared scenarios

    def _replay_under_scenarios(self, replays : list[Replay], per_round : int) -> int:
        """Replays every line under the same scenarios, again and again while an order is promising but not yet significant (up to
        ORDER_MAX_ROUNDS times as many in all): the noise of the later turns is large, and a real gain of an HP or two needs more than
        the usual count to show. The extra rounds are held to the search's own time budget, so a decision takes at most about twice
        as long as asked. Returns the number of scenarios used."""
        budget = self.config.time_budget
        started = time.perf_counter()
        total = 0
        for done in range(ORDER_MAX_ROUNDS):
            if done > 0 and budget is not None:
                spent = time.perf_counter() - started
                if spent + spent / done > budget:
                    break
            self._add_scenarios(replays, per_round)
            total += per_round
            for r in replays[1:]:
                r.gain, r.se = spread(r.diffs)
            if any(r.gain > PAIRED_Z * r.se for r in replays[1:]):
                break
            if not any(r.gain > ORDER_EXTEND_Z * r.se for r in replays[1:]):
                break
        replays[0].diffs = [0.0] * total
        replays[0].gain = replays[0].se = 0.0
        return total

    def _add_scenarios(self, replays : list[Replay], count : int):
        seeds = [rng.randrange(1 << 30) for _ in range(count)]      # fresh scenarios every time
        saved = rng.getstate()                                      # the rollouts reseed the shared source: put it back afterwards
        try:
            base = [self.mcts._paired_line_rollout(self.root, replays[0].moves, s) for s in seeds]
            for r in replays[1:]:
                r.diffs += [self.mcts._paired_line_rollout(self.root, r.moves, s) - b for s, b in zip(seeds, base)]
        finally:
            rng.setstate(saved)

    # ---- 4. the choice

    @staticmethod
    def _choose(replays : list[Replay]) -> Replay:
        """The best order, when it is ahead of the tree's by PAIRED_Z standard errors; and among the orders tied with it (not worse
        by more than TIE_MARGIN, nor significantly), the one that draws first."""
        ahead = [r for r in replays[1:] if r.gain > 0 and r.gain > PAIRED_Z * r.se]
        best = max(ahead, key=lambda r: r.gain - PAIRED_Z * r.se) if ahead else replays[0]
        tied = []
        for r in replays:
            if not r.draws_first:
                continue
            gap, se = spread([a - b for a, b in zip(r.diffs, best.diffs)])
            if gap >= -min(TIE_MARGIN, PAIRED_Z * se):
                tied.append(r)
        return max(tied, key=lambda r: r.gain) if tied else best
