import copy
import json
import math
import time

from enum import Enum, auto
from dataclasses import dataclass

from sts2_lite import rng
from sts2_lite.combat import CombatState, CombatSimulator

from sts2_lite.card import (CARD_RARITY, CardId, CardRarity, CardType, MAX_HAND_SIZE, ETHEREAL_CARDS, UPGRADE_COST_CHANGE, UPGRADE_KEYWORD,
                            UPGRADE_REMOVED_KEYWORD)

from sts2_lite.enemy import Enemy
from sts2_lite.potion import PotionId

from sts2_lite.status import StatusId
from sts2_lite.state_key import state_key

class RolloutPolicy(Enum):
    FirstAction = auto()            # just play first action (works surprisingly well)
    RandomAction = auto()           # random choice from all abailable actions
    RandomPlayble = auto()          # random choice that prefers playable cards first, then end turn
    RandomPlayblePEndTurn = auto()  # random playable, with P_END_TURN
    
    # Bias towards playing higher rarity cards first. 
    # Prefer block when being attacked. 
    # Exceptions for certain cards that perform better when played later (i.e. body slam)
    RarityPreference = auto()
    
    # Situation-aware weighted choice (Powers and draw first, Vulnerable before attacks, block only while damage is unblocked)
    ClaudeHeuristic = auto()

    # ClaudeHeuristic with the dice taken out: always plays the highest-weighted card (ties go to the first in hand), never rolls the random
    # action. The same position plays out the same way every rollout, so moves are compared on the draws and not on the policy's luck.
    ClaudeHeuristicGreedy = auto()

## constants
MAX_ROLLOUT_TURNS = 50
MIN_SIMS = 100                  # always searches at least 100 simulations
DEFAULT_TIME_BUDGET = 5.0
DEFAULT_MAX_SIMS = 20000

# random sampling constants
DEFAULT_OUTCOME_C = 2.0
OUTCOME_ALPHA = 0.5

# outcome rating constants
WIN_BASE = 20.0
TURN_COST = 0.1                 # a win loses this much HP of score per turn it took
LOSS_TURN_BONUS = 0.02          # a loss gains this much (a share of the enemies' HP) per turn lasted: dying later leaves more chances to find a win
MAX_HP_SCALING = 2.0
DEFAULT_POTION_BONUS = 16
POTION_BONUS : dict[PotionId, int] = {
    PotionId.BLOOD_POTION : 18,
    PotionId.FORTIFIER : 15,
    PotionId.HEART_OF_IRON : 15,
    PotionId.FRUIT_JUICE : 16,
    PotionId.LUCKY_TONIC : 18,
    PotionId.OROBIC_ACID : 20,
    PotionId.SHACKLING_POTION : 18,
    PotionId.SHIP_IN_A_BOTTLE : 20,
    PotionId.GIGANTIFICATION_POTION : 20,
    PotionId.SOLDIERS_STEW : 15,
    PotionId.AMBERGRIS : 45,
    PotionId.POTION_SHAPED_ROCK : 2
    }

# uct constants
# The exploration term is sized by the spread of the rewards the search has seen (the lowest to the highest rollout): half that spread,
# to the EXPLORATION_POWER. Before any win it is a fraction of a point (losses are -1..0), so the search can tell moves apart by their
# enemy HP; once a win has been found it is ~21 points wide and the scale is what a fixed one of that size gave. Fully scaling made the
# search over-explore on short budgets, none made it miss rare wins (tested on whole fights).
EXPLORATION_POWER = 0.75
MIN_REWARD_SPAN = 0.2           # the span is never taken smaller than this (the first rollouts have seen almost nothing)
EXPLORATION_SCALE = None        # a number fixes the scale (the benchmark's reference searches set one); None sizes it from the rewards seen
EXPLORATION_CONSTANT = 1.0

# information bonus: see sts2_MCTS._information_value
INFO_SIGMA = 0.05               # spread of the outcomes' values (reward units) at which a chance node earns 76% of the largest bonus (tanh(1))
INFO_MIN_VISITS = 2             # a sampled outcome's value counts once it has been visited this often

# move confidence constants
EPSILON = 0.005
Z_SCORE = 2.33
TIE_MARGIN = 0.01                # root moves this close to the best (and not significantly worse) are tied
TIE_MIN_VISITS = 30              # the top move needs this many visits before a tie is considered
TIE_VISIT_FRACTION = 0.5         # a tied move needs this share of the top move's visits: a thin estimate is within the margin by luck

# paired comparison of the root moves (see sts2_MCTS._paired_check)
PAIRED_SCENARIOS = 300           # scenarios each contender is replayed under (0 = off)
PAIRED_VISIT_FRACTION = 0.05     # a root move needs this share of the picked move's visits to be a contender
PAIRED_MAX_CONTENDERS = 4        # contenders besides the picked move
PAIRED_Z = Z_SCORE               # a contender replaces the picked move only when it is ahead by this many standard errors

# the order of the turn's plain plays (see sts2_MCTS._order_check)
ORDER_MAX_UNITS = 7              # a line with more plays than this keeps the tree's order (the orderings multiply)
ORDER_MAX_STATES = 6             # distinct end states compared with the tree's own
ORDER_MAX_STEPS = 3000           # sim steps spent listing the orderings; past it the tree's order is kept
ORDER_EXTEND_Z = 1.0             # an order ahead by this many standard errors, but not yet by PAIRED_Z, is replayed under more scenarios
ORDER_MAX_ROUNDS = 4             # the scenarios of the order check are repeated at most this many times

# rollout policy constants
ROLLOUT_POLICY = RolloutPolicy.ClaudeHeuristic
P_END_TURN = 0.02

# rarity preference
RARITY_WEIGHTS = {
    CardRarity.Ancient : 4,        # Note: usually ancient cards are very good. Right now we only have neow's fury, which is about an uncommn.
    CardRarity.Rare : 8,
    CardRarity.Uncommon : 4,
    CardRarity.Token : 4,           # Note : Token and event cards seem to be about the same as uncommon, in terms of strength.
    CardRarity.Event : 4,
    CardRarity.Common : 2,
    CardRarity.Basic : 1,           # baseline: a basic card is value 1. Model other weights around that value
    CardRarity.Status : 0.1,        # only playable status is slimed
    CardRarity.Curse : 0.01,
}

P_RANDOM_ACTION = 0.05          # chance a heuristic rollout plays a uniformly random action (end_turn included)
BLOCK_MULT = 24.0                # a block card's weight grows to (1 + BLOCK_MULT)x as the unblocked incoming damage reaches BLOCK_CAP
BLOCK_CAP = 15
DRAW_FIRST = 4.0                # draw / energy cards
NO_ROOM = 0.1                   # ... when the hand has no room for what they draw
DRAW_ROOM = 3                   # needs len(hand) <= MAX_HAND_SIZE - DRAW_ROOM
VULN_FIRST = 4.0                # a card that applies Vulnerable, while some enemy lacks it
ATTACK_BEFORE_VULN = 0.1        # an attack on a non-vulnerable target while a Vulnerable card can be played
POWER_FIRST = 3.0               # Heuristic policy only
UPGRADE_WEIGHT = 1.5             # Heuristic policy only: an upgraded card is worth about half as much again (Strike 6 -> 9), and was likely upgraded because the deck wants it played
# ... except when the upgrade only lowers the cost (the energy saved already lets the policy play more) or only adds / removes a keyword (no number goes up)
UPGRADE_UNSCALED = frozenset(UPGRADE_COST_CHANGE) | frozenset(UPGRADE_KEYWORD) | frozenset(UPGRADE_REMOVED_KEYWORD)

# Which enemy the targeted cards of the weighted policies go at, so damage is not spread over several:
#   "none" any enemy | "first" the first living one | "lowest_hp" the lowest HP | "lowest_hp_block" the lowest HP + block (minions last)
FOCUS = "lowest_hp"


DRAW_ENERGY_CARDS = frozenset(CardId[n] for n in (
    "BATTLE_TRANCE BURNING_PACT DRUM_OF_BATTLE FINESSE FLASH_OF_STEEL IMPATIENCE MASTER_OF_STRATEGY OFFERING PILLAGE POMMEL_STRIKE "
    "RESTLESSNESS SCRAWL SHRUG_IT_OFF THINKING_AHEAD BLOODLETTING EXPECT_A_FIGHT FORGOTTEN_RITUAL PRODUCTION").split())
VULNERABLE_CARDS = frozenset(CardId[n] for n in "BASH BREAK SHOCKWAVE SQUASH TAUNT THUNDERCLAP TREMBLE UPPERCUT".split())
BLOCK_CARDS = frozenset(CardId[n] for n in (
    "DEFEND_IRONCLAD SHRUG_IT_OFF BLOOD_WALL IRON_WAVE TRUE_GRIT FLAME_BARRIER IMPERVIOUS SECOND_WIND ULTIMATE_DEFEND EQUILIBRIUM "
    "ARMAMENTS EVIL_EYE PANIC_BUTTON TAUNT FINESSE TORIC_TOUGHNESS").split())

CULLABLE_PILES = ("hand", "discard") # draw pile is not neccessarily cullable because of known_top cards

@dataclass(frozen=True)
class SearchConfig:
    max_sims: int = DEFAULT_MAX_SIMS
    time_budget: float | None = None     # None = sim-count mode
    exploration: float = EXPLORATION_CONSTANT
    outcome_c: float = 2.0
    early_exit : bool = True             # allows the sim to exit early
    prefer_info : bool = True            # among tied root moves, play the one whose outcome is not yet known (a draw) first
    rollout: RolloutPolicy = ROLLOUT_POLICY
    info_bonus : float = 0.0             # largest bonus for resolving a draw / random effect early, in HP of the final score (0 = off; the idea is <= 0.5)
    reuse_tree : bool = True             # keep the part of the previous search the game actually went into (needs the same sts2_MCTS object)
    paired_scenarios : int = PAIRED_SCENARIOS   # after the search, replay the picked move and its close rivals under the same random scenarios and keep the picked move unless a rival is significantly ahead (0 = off)
    order_check : bool = True            # after the search, try the turn's plain plays (no random outcome) in every order under the same scenarios and play first what the best order starts with (needs paired_scenarios > 0)

class sts2_Node:
    parent : sts2_Node
    action : dict
    visits : int
    total_reward: float
    total_reward_squared : float
    depth :int = 0
    is_chance_node : bool

    def __init__(self, parent : sts2_Node, action=None):
        self.parent = parent
        self.action = action
        self.visits = 0
        self.total_reward = 0.0
        self.total_reward_squared = 0.0
        if parent:
            self.depth = parent.depth + 1

class sts2_DeterministicNode(sts2_Node):
    is_terminal : bool
    is_expanded : bool
    state : CombatState
    children : list[sts2_Node]
    key : tuple | None = None      # state_key(state), kept when the node went through the transposition table
    actionable : bool = True       # something other than End Turn can be done in this state (set for sampled outcomes when info_bonus is on)

    def __init__(self, parent : sts2_Node, state: CombatState, action):
        super().__init__(parent, action)
        self.is_chance_node = False
        self.is_terminal = False
        self.is_expanded = False
        self.state = state
        self.children = []

class sts2_ChanceNode(sts2_Node):
    pre_state : CombatState
    outcomes : dict[tuple, sts2_Node]
    outcome_counts : dict[tuple, int]   # times each outcome was sampled

    def __init__(self, parent, pre_state : CombatState, action):
        super().__init__(parent, action)
        self.is_chance_node = True
        self.pre_state = pre_state
        self.outcomes = {}
        self.outcome_counts = {}

class sts2_MCTS:
    _root_node : sts2_DeterministicNode = None
    _table : dict      # transposition table: state_key -> node, one per search
    _expected_total_hp : int
    _starting_hp : int
    _starting_max_hp : int
    _search_config : SearchConfig
    _num_sims: int = 0
    _info_cap : float = 0.0      # largest information bonus, in reward units
    _start_time : float
    _reward_lo : float = math.inf       # the lowest and highest rollout reward of this fight's tree: they size the exploration term
    _reward_hi : float = -math.inf

    def __init__(self):
        pass

    def monte_carlo_tree_search(self, 
                                combat_state : CombatState, 
                                config : SearchConfig = SearchConfig()
                                ) -> tuple[dict, dict]:

        # check if can reroot tree at a saved state
        reused = config.reuse_tree and self._reroot(combat_state)

        # new tree, reset table
        if not reused:
            self._table = {}
            self._root_node = sts2_DeterministicNode(None, CombatState.deepcopy(combat_state), None)
            # re-calculate expected fight hp
            self._expected_total_hp = self._calculate_expected_total_hp(combat_state)
            self._starting_hp = combat_state.player.current_hp
            self._starting_max_hp = combat_state.player.max_hp
            self._reward_lo, self._reward_hi = math.inf, -math.inf

        inherited = self._root_node.visits

        # largest bonus in reward units: `info_bonus` HP, and a win's reward is linear in HP (1 / starting HP a point)
        self._info_cap = config.info_bonus / max(1, self._starting_hp)

        self._num_sims = 0
        self._search_config = config
        self._start_time = time.perf_counter()

        exit_reason = None

        # tree search loop
        while True:
            # check exit conditions
            do_exit, reason = self._check_exit()
            if do_exit:
                exit_reason = reason
                break
            # traverse and sim
            path = self.traverse_node(self._root_node) # root to the leaf to simulate from (a shared node has several parents, so the path is tracked)
            sim_result = self._simulate_combat_rollout(path[-1]) # simulate
            self._reward_lo = min(self._reward_lo, sim_result)
            self._reward_hi = max(self._reward_hi, sim_result)
            backpropagate(path, sim_result, self._information_bonuses(path))

        best_child = self._pick_root_child()
        paired = self._paired_check(best_child) if config.paired_scenarios > 0 else None
        if paired is not None and paired["replaced"]:
            best_child = paired["child"]
        move = best_child.action
        order = None
        if config.order_check and config.paired_scenarios > 0:
            try:
                order = self._order_check(best_child)
            except Exception as error:      # a live run keeps the tree's pick rather than stopping over an ordering it could not list
                order = {"replaced" : False, "error" : f"{type(error).__name__}: {error}"}
            if order is not None and order["replaced"]:
                move = order["action"]

        stats = { 
            "children": [{"action": c.action, "visits": c.visits, "q": c.total_reward / c.visits} for c in self._root_node.children],
            "num_sims" : self._num_sims,
            "time_taken" : time.perf_counter() - self._start_time,
            "exit_reason" : exit_reason,
            "reused" : reused,
            "inherited_visits" : inherited,       # visits the root already had from earlier searches
            "paired" : None if paired is None else {k: v for k, v in paired.items() if k != "child"},
            "order" : None if order is None else {k: v for k, v in order.items() if k != "action"},
                }
        stats["time_taken"] = time.perf_counter() - self._start_time
        return move, stats

    ### Tree reuse
    ### The agent searches again after every action. The state it is given is one the last search already looked at (the node the
    ### played move led to, or one of the sampled outcomes of a draw), so that node becomes the new root with everything below it.

    def _find_node(self, key : tuple) -> sts2_Node | None:
        """The node of the previous search whose state is `key`: the old root, one of its moves or sampled outcomes, or anything deeper."""
        root = self._root_node
        if state_key(root.state) == key:
            return root
        for child in root.children:
            if child.is_chance_node:
                for outcome in child.outcomes.values():
                    if state_key(outcome.state) == key:
                        return outcome
            elif state_key(child.state) == key:
                return child
        return self._table.get(key)

    def _reroot(self, observed : CombatState) -> bool:
        """Makes the node for `observed` the root of the next search; False (nothing changed) when the last search never reached it.
        The reward scale (`_starting_hp`, `_expected_total_hp`) stays that of the first search of the fight, as the inherited
        rewards were rated with it."""
        if self._root_node is None:
            return False
        match = self._find_node(state_key(observed))
        if match is None:
            return False
        root = sts2_DeterministicNode(None, CombatState.deepcopy(observed), None)
        root.visits, root.total_reward, root.total_reward_squared = match.visits, match.total_reward, match.total_reward_squared
        root.is_terminal = match.is_terminal
        expand_node(root)       # the moves in the observed state's own card positions: these are what the agent returns
        if match.is_expanded:
            # A move that leads to a fixed state is found by that state: a shared child keeps the action (card position) of the
            # parent that created it, which is wrong for any other. A random move is a node of its own, so its action is right.
            old_sim = CombatSimulator(match.state)
            by_state = {(c.key or state_key(c.state)): c for c in match.children if not c.is_chance_node}
            by_move = {_move_id(old_sim, c.action): c for c in match.children if c.is_chance_node}
            new_sim = CombatSimulator(root.state)
            for i, fresh in enumerate(root.children):
                old = by_move.get(_move_id(new_sim, fresh.action)) if fresh.is_chance_node else by_state.get(state_key(fresh.state))
                if old is not None:
                    root.children[i] = self._carry_over(old, root, fresh.action)
        self._root_node = root
        self._table = self._adopt(root)
        return True

    def _carry_over(self, old : sts2_Node, root : sts2_DeterministicNode, action : dict) -> sts2_Node:
        """A copy of a move of the matched node, with the action indexed for the observed state, which is root's.
        (A root child is never shared, as the returned action comes from it.)"""
        node = copy.copy(old)
        node.parent, node.action = root, action
        if node.is_chance_node:
            node.pre_state = root.state
            node.outcomes, node.outcome_counts = dict(old.outcomes), dict(old.outcome_counts)
        else:
            node.children = list(old.children)
        return node

    def _adopt(self, root : sts2_DeterministicNode) -> dict:
        """Points every node below `root` at a parent inside the kept tree (so the old tree can be freed) and rebuilds the
        transposition table from it."""
        table, seen, stack = {}, {id(root)}, [root]
        while stack:
            node = stack.pop()
            for child in (node.outcomes.values() if node.is_chance_node else node.children):
                if id(child) in seen:
                    continue
                seen.add(id(child))
                child.parent = node
                if not child.is_chance_node and not node.is_chance_node and node is not root:
                    if child.key is None:
                        child.key = state_key(child.state)
                    table.setdefault(child.key, child)
                stack.append(child)
        return table

    ### Information bonus
    ### Resolving a draw (or a random effect) before the turn's remaining plays are chosen lets the agent choose them knowing the result.
    ### Rollouts play on at random and the sampled outcomes are visited rarely, so the search undervalues that. A chance node whose
    ### outcomes differ in value, and with something left to play afterwards, earns a bonus. It is one-sided on purpose (a potential-based
    ### term would cancel along the path): it does not charge anything back, and it only goes to the chance node and its ancestors, so
    ### the outcomes' own values, which the bonus is measured from, stay clean.

    def _information_value(self, node : sts2_ChanceNode) -> float:
        """cap * tanh(spread / INFO_SIGMA) * the share of sampled outcomes with something left to play.
        spread is the standard deviation, between the outcomes, of their values (weighted by how often each was sampled), with the
        noise of each outcome's own estimate taken off, so outcomes that only look different by chance earn nothing."""
        sampled = [(node.outcomes[k], node.outcome_counts[k]) for k in node.outcomes]
        seen = [(o, c) for o, c in sampled if o.visits >= INFO_MIN_VISITS]
        if len(seen) < 2:
            return 0.0
        total = sum(c for _, c in seen)
        values = [o.total_reward / o.visits for o, _ in seen]
        mean = sum(c * q for (_, c), q in zip(seen, values)) / total
        between = sum(c * (q - mean) ** 2 for (_, c), q in zip(seen, values)) / total
        noise = sum(c * max(0.0, (o.total_reward_squared - o.total_reward ** 2 / o.visits) / (o.visits - 1)) / o.visits
                    for o, c in seen) / total
        spread = math.sqrt(max(0.0, between - noise))
        if spread == 0.0:
            return 0.0
        actionable = sum(c for o, c in sampled if o.actionable) / sum(c for _, c in sampled)
        return self._info_cap * math.tanh(spread / INFO_SIGMA) * actionable

    def _information_bonuses(self, path : list[sts2_Node]) -> list[float] | None:
        """The bonus each node of `path` receives on top of the simulation result, or None when there is none. A node gets the bonuses
        of the chance nodes at or below it, together at most the cap. End Turn is left out: its outcomes (the next hand, the enemies'
        moves) arrive when nothing more can be done about them."""
        if self._info_cap <= 0.0:
            return None
        own = [self._information_value(n) if n.is_chance_node and n.action["action"] != "end_turn" else 0.0 for n in path]
        if not any(own):
            return None
        bonuses, running = [0.0] * len(path), 0.0
        for i in range(len(path) - 1, -1, -1):
            running = min(self._info_cap, running + own[i])
            bonuses[i] = running
        return bonuses

    def _pick_root_child(self) -> sts2_Node:
        """The most visited move; with prefer_info, a tied move that reveals information (a draw or random effect) goes first.
        The agent searches again after every action, so seeing the result early is free, and a tied move gives up nothing."""
        children = self._root_node.children
        top = max(children, key=lambda c: c.visits)
        if not self._search_config.prefer_info or top.visits < TIE_MIN_VISITS:
            return top
        informative = [c for c in children if c.is_chance_node and c.action["action"] != "end_turn"
                       and c.visits >= max(TIE_MIN_VISITS, TIE_VISIT_FRACTION * top.visits) and self._tied(c, top)]
        return max(informative, key=lambda c: c.visits) if informative else top

    ### Paired comparison of the root moves
    ### The tree compares moves with independent noise: a move that is only a little better (Defend+ over Defend) is lost in the
    ### draws and enemy rolls, and the visits settle on whichever got ahead early. Here the picked move and its close rivals are
    ### replayed under the SAME scenarios (shuffle, random rolls) so that noise cancels in the difference. A rival replaces the
    ### picked move only when it is ahead by PAIRED_Z standard errors of that paired difference.

    def _paired_rollout(self, state : CombatState, action : dict, seed : int) -> float:
        """Play `action` from `state`, then the rollout policy to the end, with the random source seeded from `seed`."""
        return self._paired_line_rollout(state, [action], seed)

    def _paired_line_rollout(self, state : CombatState, line : list, seed : int) -> float:
        """Play `line` from `state`, then the rollout policy to the end, with the random source seeded from `seed`.
        An item of the line is an action, or a move id (see _move_id) found among the actions of the state it is played in: the indices
        of the hand move once a draw has happened. A move that cannot be played there is passed over.
        The source is reseeded at the start of every turn, so the rolls of a later turn do not shift when the two lines drew a different
        number of random numbers earlier."""
        rng.seed(seed << 20)
        cs = CombatState.deepcopy(state)
        cs.player.shuffle_draw_pile()
        c = CombatSimulator(cs)
        for item in line:
            action = item if isinstance(item, dict) else self._find_move(c, item)
            if action is not None and not c.is_over:
                c.perform_action(action)
        turn = cs.turn_number
        end_turn = turn + MAX_ROLLOUT_TURNS
        while not c.is_over and cs.turn_number < end_turn:
            if cs.turn_number != turn:
                turn = cs.turn_number
                rng.seed((seed << 20) + turn)
            actions = c.get_available_actions()
            if len(actions) == 0:
                break
            c.perform_action(rollout_policy(c, actions, self._search_config.rollout))
        return self._rate_outcome(cs)

    def _contender_line(self, node : sts2_Node) -> list:
        """The root move `node` and the line the tree follows after it (see _principal_line), for the paired replay."""
        line, tail = self._principal_line(node)
        if not line:
            return [node.action]            # a random play: the move itself
        return line + ([tail] if tail is not None else [])

    def _paired_check(self, picked : sts2_Node) -> dict | None:
        """Compare `picked` with the root moves close to it in visits. Returns the details (and whether a rival `replaced` it),
        or None when there is nothing to compare."""
        n = self._search_config.paired_scenarios
        state = self._root_node.state
        rivals = sorted((c for c in self._root_node.children
                         if c is not picked and c.visits >= max(1, PAIRED_VISIT_FRACTION * picked.visits)),
                        key=lambda c: -c.visits)[:PAIRED_MAX_CONTENDERS]
        if n < 2 or not rivals:
            return None

        seeds = [rng.randrange(1 << 30) for _ in range(n)]      # fresh scenarios every time
        saved = rng.getstate()                                  # the rollouts reseed the shared source: put it back afterwards
        try:
            # each move is replayed along the line the tree found after it (the second Strike that is lethal), not as its first play
            # followed by the rollout policy, which need not find that line and then rates the move below one that is merely safe
            base = [self._paired_line_rollout(state, self._contender_line(picked), s) for s in seeds]
            results = []
            for rival in rivals:
                line = self._contender_line(rival)
                diffs = [self._paired_line_rollout(state, line, s) - b for s, b in zip(seeds, base)]
                mean = sum(diffs) / n
                var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
                results.append((rival, mean, math.sqrt(var / n)))
        finally:
            rng.setstate(saved)

        # a rival is significantly ahead of the picked move (a zero spread with a positive gap is a sure improvement)
        ahead = [r for r in results if r[1] > 0 and r[1] > PAIRED_Z * r[2]]
        best = max(ahead, key=lambda r: r[1] - PAIRED_Z * r[2]) if ahead else None
        return {
            "replaced" : best is not None,
            "child" : best[0] if best else picked,
            "scenarios" : n,
            "compared" : [{"action" : r[0].action, "visits" : r[0].visits, "gain" : r[1], "se" : r[2]} for r in results],
        }

    ### The order of the turn's plain plays
    ### Plays that leave nothing to chance (a potion, a block card, an attack with no draw) can be made in any order, and the order can
    ### matter: Dexterity before the block, Vulnerable before the attack, a relic that wants less block. The tree cannot see it when
    ### the difference is a point or two of HP, since its rollouts are independent. So the tree's line for this turn, up to its first
    ### random play, is listed in every legal order; orders that end in the same state count once; and the distinct ones are replayed
    ### under the same scenarios as the paired check. An order replaces the tree's only when it is ahead by PAIRED_Z standard errors.
    ###
    ### The random play itself (a draw) is also tried first, the rest of the line after it and, when that is not as good, with the rest
    ### left to the rollout policy: seeing the draw first costs nothing unless an order matters (Strength before the card that draws), and
    ### the next search plans with what was drawn. Among the orders tied with the best, the one that draws first is played, as with
    ### prefer_info for the root moves. The replay does not plan for the draw, so its verdict on drawing first is a lower bound.

    def _principal_line(self, first : sts2_Node) -> tuple[list[tuple], tuple | None]:
        """The tree's line from the picked root move, as move ids (see _move_id): the plain plays up to the first play with a random
        outcome or the end of the turn, and that play. The line stops where the tree stops looking."""
        if first.is_chance_node:
            return [], _move_id(CombatSimulator(self._root_node.state), first.action)
        line = [_move_id(CombatSimulator(self._root_node.state), first.action)]
        node = first
        while not node.is_terminal:
            seen = [k for k in node.children if k.visits > 0]
            if not seen:
                break
            nxt = max(seen, key=lambda k: k.visits)
            sim = CombatSimulator(node.state)
            if nxt.is_chance_node:
                return line, _move_id(sim, nxt.action)
            target = state_key(nxt.state)
            step = None
            for a in cull_identical_actions(sim, sim.get_available_actions()):
                c = CombatSimulator(CombatState.deepcopy(node.state))
                c.perform_action(a)
                if state_key(c.combat_state) == target:
                    step = _move_id(sim, a)
                    break
            if step is None:
                break
            line.append(step)
            node = nxt
        return line, None

    @staticmethod
    def _find_move(c : CombatSimulator, move_id : tuple) -> dict | None:
        return next((a for a in c.get_available_actions() if _move_id(c, a) == move_id), None)

    def _order_check(self, picked : sts2_Node) -> dict | None:
        """Returns the details (and whether another order replaced the tree's, with its first play in "action"), or None when there
        is nothing to compare: the picked move is itself the random play, the line is too long to list, or no other order exists."""
        n = self._search_config.paired_scenarios
        root = self._root_node.state
        if n < 2 or root.pending_choice is not None:
            return None
        line, tail = self._principal_line(picked)
        if not line:
            return None                                     # the picked move is the random play: it is already played first
        can_draw_first = tail is not None and not _is_end_turn(tail)

        # a play and the choices it asks for (True Grit's card) move together
        units : list[tuple] = []
        for move in line:
            if _is_choice(move) and units:
                units[-1] = units[-1] + (move,)
            else:
                units.append((move,))
        if len(units) > ORDER_MAX_UNITS or (len(units) < 2 and not can_draw_first):
            return None
        ids = {}
        unit_ids = [ids.setdefault(u, len(ids)) for u in units]
        by_id = {i: u for u, i in ids.items()}

        steps = 0
        found : dict[tuple, list[tuple]] = {}           # end state -> the move ids that lead there (the tree's order first)
        memo = set()

        def play(state, unit):
            nonlocal steps
            c = CombatSimulator(CombatState.deepcopy(state))
            for move in unit:
                a = self._find_move(c, move)
                if a is None:
                    return None
                c.perform_action(a)
                steps += 1
            return c.combat_state

        def finish(state, moves):
            if tail is not None and self._find_move(CombatSimulator(state), tail) is None:
                return
            found.setdefault(state_key(state), moves)

        def go(state, remaining, moves):
            if steps > ORDER_MAX_STEPS or len(found) > ORDER_MAX_STATES:
                return
            if not remaining:
                finish(state, moves)
                return
            key = (state_key(state), remaining)
            if key in memo:
                return
            memo.add(key)
            for uid in dict.fromkeys(remaining):
                rest = list(remaining)
                rest.remove(uid)
                done = play(state, by_id[uid])
                if done is not None:
                    go(done, tuple(rest), moves + list(by_id[uid]))

        # the tree's own order first: it is what the others are compared with
        state, moves = root, []
        for uid in unit_ids:
            state = play(state, by_id[uid])
            if state is None:
                return None
            moves = moves + list(by_id[uid])
        finish(state, moves)
        if not found:
            return None
        go(root, tuple(sorted(unit_ids)), [])
        if steps > ORDER_MAX_STEPS:
            return None
        orders = list(found.values())

        # the lines to replay: each order, then each order with the draw first, then the draw alone and the rest left to the policy
        tail_move = [tail] if tail is not None else []
        lines = [{"moves" : o + tail_move, "draws_first" : False} for o in orders]
        if can_draw_first and self._find_move(CombatSimulator(root), tail) is not None:
            lines += [{"moves" : tail_move + o, "draws_first" : True} for o in orders]
            lines.append({"moves" : tail_move, "draws_first" : True})
        if len(lines) < 2:
            return None
        for ln in lines:
            ln["first"] = self._find_move(CombatSimulator(root), ln["moves"][0])

        for ln in lines:
            ln["diffs"] = []
        lines[0]["diffs"] = None

        def spread(diffs):
            count = len(diffs)
            mean = sum(diffs) / count
            var = sum((d - mean) ** 2 for d in diffs) / (count - 1)
            return mean, math.sqrt(var / count)

        def add_scenarios(count):
            seeds = [rng.randrange(1 << 30) for _ in range(count)]      # fresh scenarios every time
            saved = rng.getstate()                                      # the rollouts reseed the shared source: put it back afterwards
            try:
                base = [self._paired_line_rollout(root, lines[0]["moves"], s) for s in seeds]
                for ln in lines[1:]:
                    ln["diffs"] += [self._paired_line_rollout(root, ln["moves"], s) - b for s, b in zip(seeds, base)]
            finally:
                rng.setstate(saved)

        # an order that is promising but not yet significant gets more scenarios (up to ORDER_MAX_ROUNDS times as many in all):
        # the noise of the later turns is large, and a real gain of an HP or two needs more than the usual count to show
        # (the extra rounds are held to the search's own time budget, so a decision takes at most about twice as long as asked)
        budget = self._search_config.time_budget
        started = time.perf_counter()
        total = 0
        for done in range(ORDER_MAX_ROUNDS):
            if done > 0 and budget is not None:
                spent = time.perf_counter() - started
                if spent + spent / done > budget:
                    break
            add_scenarios(n)
            total += n
            for ln in lines[1:]:
                ln["gain"], ln["se"] = spread(ln["diffs"])
            if any(ln["gain"] > PAIRED_Z * ln["se"] for ln in lines[1:]):
                break
            if not any(ln["gain"] > ORDER_EXTEND_Z * ln["se"] for ln in lines[1:]):
                break
        n = total
        lines[0]["diffs"] = [0.0] * n
        lines[0]["gain"], lines[0]["se"] = 0.0, 0.0

        # the best order, when it is ahead of the tree's by PAIRED_Z standard errors
        ahead = [ln for ln in lines[1:] if ln["gain"] > 0 and ln["gain"] > PAIRED_Z * ln["se"]]
        best = max(ahead, key=lambda ln: ln["gain"] - PAIRED_Z * ln["se"]) if ahead else lines[0]
        chosen = best
        # ... and among the orders tied with it (not worse by more than TIE_MARGIN, nor significantly), the one that draws first
        tied = []
        for ln in lines:
            if not ln["draws_first"]:
                continue
            gap, se = spread([a - b for a, b in zip(ln["diffs"], best["diffs"])])
            if gap >= -min(TIE_MARGIN, PAIRED_Z * se):
                tied.append(ln)
        if tied:
            chosen = max(tied, key=lambda ln: ln["gain"])
        return {
            "replaced" : chosen is not lines[0],
            "action" : chosen["first"],
            "draws_first" : chosen["draws_first"],
            "scenarios" : n,
            "plays" : len(units),
            "distinct" : len(orders),
            "compared" : [{"first" : ln["first"], "draws_first" : ln["draws_first"], "gain" : ln["gain"], "se" : ln["se"]} for ln in lines[1:]],
        }

    def _tied(self, node : sts2_Node, top : sts2_Node) -> bool:
        """`node` is within TIE_MARGIN of `top` and not significantly worse at Z_SCORE (the test the early exit uses)."""
        if node is top:
            return True
        gap = top.total_reward/top.visits - node.total_reward/node.visits
        if gap <= 0:
            return True
        if gap > TIE_MARGIN:
            return False
        var = lambda n: max(0.0, (n.total_reward_squared - n.total_reward**2/n.visits) / (n.visits - 1))
        return gap <= Z_SCORE * math.sqrt(var(node)/node.visits + var(top)/top.visits)

    # finds the optimal node to simulate from
    def traverse_node(self, node : sts2_Node) -> list[sts2_Node]:
        path = [node]
        while True:
            # chance node
            if node.is_chance_node:
                node, is_new = self._sample_outcome(node)
                path.append(node)
                if is_new:
                    return path # roll out from the last node
            # deterministic node
            else:
                # if terminal node, return
                if node.is_terminal:
                    return path
                # if node has not yet been expanded, expand it
                if not node.is_expanded:
                    expand_node(node, self._table)
                # if node has unvisited child, return that
                leaf = get_unvisited_child(node)
                if leaf is not None:
                    path.append(leaf)
                    if leaf.is_chance_node:
                        node = leaf # resolve it into an outcome
                        continue
                    return path
                # otherwise, get best utc and keep traversing
                node = self._best_uct(node)
                path.append(node)

    # resolve a chance node
    def _sample_outcome(self, node: sts2_Node) -> tuple[sts2_Node, bool]:
        cap = max(1, math.ceil(self._search_config.outcome_c * node.visits ** OUTCOME_ALPHA))

        # sample from the true distribution: randomize the draw pile, then act
        state = CombatState.deepcopy(node.pre_state)
        state.player.shuffle_draw_pile()           # known top cards stay where they are
        sim = CombatSimulator(state)
        sim.perform_action(node.action)
        key = outcome_key(state)

        child = node.outcomes.get(key)
        
        if child is None:
            if len(node.outcomes) < cap:
                child = sts2_DeterministicNode(node, state, node.action)
                child.is_terminal = sim.is_over
                if self._info_cap > 0.0:
                    child.actionable = not sim.is_over and any(a["action"] != "end_turn" for a in sim.get_available_actions())
                node.outcomes[key] = child
                node.outcome_counts[key] = 1
                return child, True
            # at the cap: reuse an existing outcome, weighted by how often it was seen
            keys = list(node.outcomes)
            key = rng.choices(keys, weights=[node.outcome_counts[k] for k in keys])[0]
            child = node.outcomes[key]
        
        node.outcome_counts[key] += 1
        return child, False
        
    # simulate combat to end
    def _simulate_combat_rollout(self, node : sts2_Node) -> float:

        c = CombatSimulator(CombatState.deepcopy(node.state))
        # shuffle draw pile to inject randomness into rollout
        c.combat_state.player.shuffle_draw_pile()
        end_turn = c.combat_state.turn_number + MAX_ROLLOUT_TURNS
        
        while not c.is_over and c.combat_state.turn_number < end_turn:
            actions = c.get_available_actions()

            if len(actions) == 0:
                break

            action = rollout_policy(c, actions, self._search_config.rollout)
            
            c.perform_action(action)

        self._num_sims += 1
        outcome = self._rate_outcome(c.combat_state)
        return outcome

    def _rate_outcome(self, combat_state : CombatState) -> float:
        current_hp = combat_state.player.current_hp
        max_hp = combat_state.player.max_hp
        num_turns = combat_state.turn_number
        won = current_hp > 0 and all(e.is_minion or e.current_hp <= 0 for e in combat_state.enemies)
        max_hp_delta = combat_state.player.max_hp - self._starting_max_hp
        # if won fight: outcome is best max hp with slight bias towards less turns
        if won:
            hp_score = current_hp
            if not combat_state.final_fight:        # in the last fight a kept potion is of no use later: drinking one costs nothing
                hp_score += sum(POTION_BONUS.get(p.potion_id, DEFAULT_POTION_BONUS) for p in combat_state.player.potions)
                hp_score += MAX_HP_SCALING * max_hp_delta
            hp_score += -TURN_COST * num_turns                     
            return WIN_BASE + hp_score / self._starting_hp         # linear in HP
        
        # lost or unfinished: minimize the enemy HP that is left, with a small preference for lasting longer
        else:
            progress_left = self._enemy_progress_left(combat_state)
            if progress_left == 0:     # every enemy died and so did the player: no better than a plain loss
                return -1.0
            return -progress_left + LOSS_TURN_BONUS * num_turns

    def _enemy_progress_left(self, combat_state : CombatState) -> float:
        """The share of the fight's enemy HP that is still to be removed: 1.0 at the start of the fight, 0.0 when nothing is left.

        Counts what the living enemies still carry (`_effective_hp`: a Phrog Parasite counts the Wrigglers it will release) and what
        the dead will bring back (`_dormant_hp`: a killed Decimillipede segment is not progress, it is back at 25 HP in two turns)."""
        remaining = sum(_effective_hp(e) for e in combat_state.enemies) + _dormant_hp(combat_state)
        return remaining / max(1, self._expected_total_hp)

    # uct score 
    def get_uct_score(self, node : sts2_Node, parent : sts2_Node | None = None):
        # a shared node (transposition) has several parents: use the one the search came through
        if parent is None:
            parent = node.parent
        if node.visits == 0:
            return 0
        return node.total_reward/node.visits + self._search_config.exploration*self._exploration_scale()*math.sqrt(math.log(max(1, parent.visits))/node.visits)

    def _exploration_scale(self) -> float:
        """How wide the rewards are, as UCT's exploration term needs it: a fixed EXPLORATION_SCALE if one is set, else sized from the
        lowest and highest rollout reward seen in this fight's tree."""
        if EXPLORATION_SCALE is not None:
            return EXPLORATION_SCALE
        span = max(self._reward_hi - self._reward_lo, MIN_REWARD_SPAN)
        return (span / 2.0) ** EXPLORATION_POWER

    def _best_uct(self, node : sts2_Node) -> sts2_Node:
        if len(node.children) == 0:
            return node
        return max(node.children, key = lambda x: self.get_uct_score(x, node))

    def _calculate_expected_total_hp(self, combat_state : CombatState):
        expected_total_hp = 0
        for e in combat_state.enemies:
            if e.is_minion:
                continue
            expected_total_hp += e.max_hp
            # edge cases, should probably implement better way to do this in future
            if e.enemy_id.startswith("PHROG_PARASITE"):
                expected_total_hp += 4*(17+21)/2
        return expected_total_hp

    def _check_statistical_exit(self)-> str | None:
        # ensure minimum sims has been reached
        if self._num_sims < max(MIN_SIMS, 40* len(self._root_node.children)):
            return None

        # if only one child (can also exit)
        if len(self._root_node.children) < 2:
            return "ONE_CHILD"

        # get the top two scoring children
        children_sorted = sorted(self._root_node.children, key=lambda c: c.visits)
        node_a = children_sorted[-1]
        node_b = children_sorted[-2]

        # ensure enough visits have been made
        if node_a.visits <= 30 or node_b.visits <= 30:
            return None

        # calculate variance (sample variance)
        n_a = node_a.visits
        n_b = node_b.visits

        S_a = node_a.total_reward
        S_b = node_b.total_reward

        Q_a = node_a.total_reward_squared
        Q_b = node_b.total_reward_squared

        s_a = max(0.0, (Q_a - S_a**2/ n_a) / (n_a - 1))
        s_b = max(0.0, (Q_b - S_b**2/ n_b) / (n_b - 1))
        
        # calculate standard error
        SE_diff = math.sqrt(s_a/n_a + s_b/n_b)

        # if difference is large enough:
        if (S_a/n_a - S_b/n_b) > Z_SCORE * SE_diff:
            return "BEST"

        # if difference is small enough
        if Z_SCORE*SE_diff < EPSILON:
            best_mean = max(node_a.total_reward/node_a.visits, node_b.total_reward/node_b.visits)
            return "TIE" if best_mean > 0.0 else None # only return TIE if winning line
        
        return None

    def _check_exit(self) -> tuple[bool, str]:
        # check min sims
        if self._num_sims < MIN_SIMS:
            return False, None
        # check max sims reached
        if self._num_sims >= self._search_config.max_sims:
            return True, "MAX_SIMS"
        # check time limit
        if self._num_sims >= MIN_SIMS and self._search_config.time_budget is not None and time.perf_counter() >= (self._start_time + self._search_config.time_budget):
            return True, "TIME_BUDGET"
        # check for statistical confidence (every 50)
        statistical_exit_reason = self._check_statistical_exit()
        if self._search_config.early_exit and self._num_sims >= MIN_SIMS and self._num_sims%50 == 0 and statistical_exit_reason is not None:
            return True, "STATISTICAL_CONFIDENCE" + ": " + statistical_exit_reason
        
        return False, None

def get_unvisited_child(node : sts2_Node):
    for child in node.children:
        if child.visits == 0:
            return child
    return None

def expand_node(node : sts2_Node, table : dict | None = None):
    c = CombatSimulator(node.state)
    actions = c.get_available_actions()
    actions = cull_identical_actions(c, actions)

    # expand node
    for a in actions:
        c_a = CombatSimulator(CombatState.deepcopy(node.state))
        player = c_a.combat_state.player
        rng_calls, unknown_draws = rng.calls, player.unknown_draws
        c_a.perform_action(a)
        # an unforeseeable draw or any rng use means the outcome is not fixed
        is_random = rng.calls != rng_calls or player.unknown_draws != unknown_draws
        if is_random:
            new_child = sts2_ChanceNode(node, node.state, a)
        else:
            new_child = sts2_DeterministicNode(node, c_a.combat_state, a)
            new_child.is_terminal = c_a.is_over
            # same state reached by another order of plays: share the node (the root's children keep their own action)
            if table is not None and node.parent is not None:
                key = state_key(new_child.state)
                new_child = table.setdefault(key, new_child)
                new_child.key = key
        if not any(new_child is c for c in node.children):
            node.children.append(new_child)

    node.is_expanded = True

def backpropagate(path : list[sts2_Node], result : float, bonuses : list[float] | None = None):
    """Adds the result to every node on the path from the root to the simulated leaf (plus its bonus, if there are any)."""
    for i, node in enumerate(path):
        r = result if bonuses is None else result + bonuses[i]
        node.total_reward += r
        node.total_reward_squared += r*r
        node.visits += 1

def rollout_policy(c : CombatSimulator, actions, policy : RolloutPolicy):
    # rollouts never drink potions (every policy): a potion is only used by a move the tree chose, so a kept one keeps its bonus
    actions = [a for a in actions if a["action"] != "use_potion"] or actions
    if len(actions) == 0:
        return None
    if len(actions) == 1:   
        return actions[0]
    return ROLLOUT_POLICY_DICT[policy](c, actions)

def _effective_hp(enemy : Enemy):
    if enemy.is_minion:
        return 0
    effective_hp = enemy.current_hp
    # edge cases
    if enemy.enemy_id.startswith("PHROG_PARASITE"):
        effective_hp += 4 * (17 + 21) / 2
    return effective_hp

def _dormant_hp(combat_state : CombatState) -> float:
    """The HP that enemies lying dead (`combat_state.dormant`) will bring back with them.

    A killed Decimillipede segment (ReattachPower) revives with its Reattach amount, but only while another segment is still alive:
    once the last living one is killed the fight is over and the dormant ones count for nothing."""
    if not any(not e.is_minion and e.current_hp > 0 for e in combat_state.enemies):
        return 0
    return sum(min(d.max_hp, d.status[StatusId.REATTACH].amount) for d in combat_state.dormant if StatusId.REATTACH in d.status)

def _action_key(c : CombatSimulator, action : dict) -> tuple:
    if action["action"] == "play_card":
        return ("play_card", c.combat_state.player.hand[action["card_index"]].signature(), action["target"])
    if action["action"] == "choose_card" and action["pile"] in CULLABLE_PILES:
        return ("choose_card", action["pile"], c._pile(action["pile"])[action["card_index"]].signature())
    return (id(action),)

def outcome_key(state):
    """outcome key: hand and draw pile contents (order ignored), enemies and their next moves."""
    p = state.player
    ids = lambda cards: tuple(sorted((c.card_id.value, c.is_upgraded) for c in cards))
    n = p.known_top
    known = tuple((c.card_id.value, c.is_upgraded) for c in p.draw_pile[len(p.draw_pile) - n:]) if n else ()
    return ids(p.hand), ids(p.draw_pile), known, tuple((e.enemy_id, e.move_id) for e in state.enemies)

def _move_id(c : CombatSimulator, action : dict) -> tuple:
    """Identifies a move across two states that differ only in card order (the indices in `action` do not carry over)."""
    key = _action_key(c, action)
    return key if key != (id(action),) else ("action", json.dumps(action, sort_keys=True))

def _is_end_turn(move_id : tuple) -> bool:
    return move_id[0] == "action" and json.loads(move_id[1]).get("action") == "end_turn"

def _is_choice(move_id : tuple) -> bool:
    """A move id of the answer to a pending card choice."""
    if move_id[0] == "choose_card":
        return True
    return move_id[0] == "action" and json.loads(move_id[1]).get("action") in ("choose_card", "confirm_choice")

def cull_identical_actions(c : CombatSimulator, actions : list[dict]) -> list[dict]:
    seen = set()
    kept = []
    for a in actions:
        key = _action_key(c,a)
        if key not in seen:
            seen.add(key)
            kept.append(a)
    return kept

###
### Rollout Poliocy helpers
###

def _incoming_damage(cs : CombatState) -> int:
    """Damage the enemies' next moves deal before block (no Strength, Weak or Vulnerable applied)."""
    return sum(e.attack_damage * e.num_attacks for e in cs.enemies if e.current_hp > 0 and not e.is_minion)

def _rarity_weight(card) -> float:
    rarity = CardRarity.Common if card.card_id == CardId.BASH else CARD_RARITY[card.card_id]     # Bash plays like a Common
    return RARITY_WEIGHTS[rarity]

def _focus_fire(c : CombatSimulator, plays : list[dict]) -> list[dict]:
    """Restricts the targeted plays to the focus enemy; plays that take no target are untouched."""
    if FOCUS == "none":
        return plays
    enemies = c.combat_state.enemies
    targeted = [a for a in plays if "target_name" in a]
    candidates = list(dict.fromkeys(a["target"] for a in targeted))
    if len(candidates) < 2:
        return plays
    pool = [i for i in candidates if not enemies[i].is_minion] or candidates
    if FOCUS == "first":
        focus = pool[0]
    elif FOCUS == "lowest_hp":
        focus = min(pool, key=lambda i: enemies[i].current_hp)
    else:
        focus = min(pool, key=lambda i: enemies[i].current_hp + enemies[i].block)
    return [a for a in plays if "target_name" not in a or a["target"] == focus]

def _weighted_play(c : CombatSimulator, actions : list[dict], weight, greedy : bool = False) -> dict:
    """P_RANDOM_ACTION: any action. Otherwise a card play drawn with weight(card, action); end_turn only when nothing else can be done.
    greedy: no random action, and the heaviest play every time (the first of equals). Pending choices (choose_card etc.) are uniform."""
    plays = [a for a in actions if a["action"] == "play_card"]
    if not plays or (not greedy and rng.random_float() < P_RANDOM_ACTION):
        return rng.choice(actions)
    plays = _focus_fire(c, plays)
    hand = c.combat_state.player.hand
    weights = [weight(hand[a["card_index"]], a) for a in plays]
    if greedy:
        return plays[max(range(len(plays)), key=weights.__getitem__)]
    return rng.choices(plays, weights=weights)[0]

def _situation(c : CombatSimulator, actions : list[dict]):
    """(unblocked incoming damage, can a Vulnerable card be played, hand has room to draw)"""
    cs = c.combat_state
    hand = cs.player.hand
    can_vuln = any(a["action"] == "play_card" and hand[a["card_index"]].card_id in VULNERABLE_CARDS for a in actions) \
        and any(e.current_hp > 0 and not e.is_minion and e.status_amount(StatusId.VULNERABLE) == 0 for e in cs.enemies)
    return max(0, _incoming_damage(cs) - cs.player.block), can_vuln, len(hand) <= MAX_HAND_SIZE - DRAW_ROOM

def _common_factors(c : CombatSimulator, card, action : dict, unblocked : int, can_vuln : bool, room : bool) -> float:
    """Draw / Vulnerable / block factors shared by both weighted policies."""
    w = 1.0
    if card.card_id in DRAW_ENERGY_CARDS:
        w *= DRAW_FIRST if room else NO_ROOM
    if card.card_id in VULNERABLE_CARDS and can_vuln:
        w *= VULN_FIRST
    if card.type == CardType.Attack and can_vuln and card.card_id not in VULNERABLE_CARDS:
        enemies = c.combat_state.enemies
        target = enemies[action["target"]] if action["target"] < len(enemies) else None
        if target is None or target.status_amount(StatusId.VULNERABLE) == 0:       # (an attack on all enemies counts as unvulnerable too)
            w *= ATTACK_BEFORE_VULN
    if card.card_id in BLOCK_CARDS and unblocked > 0:
        w *= 1.0 + BLOCK_MULT * min(1.0, unblocked / BLOCK_CAP)
    return w


### 
### Rollout Policy functions
###

def first_action(c : CombatSimulator, actions : list[dict]) -> dict:
    return actions[0]

def random_action(c : CombatSimulator, actions : list[dict]) -> dict:
    return rng.choice(actions)

def random_playable(c : CombatSimulator, actions : list[dict]) -> dict:
    playable_actions = [a for a in actions if a["action"] != "end_turn"] or actions
    return rng.choice(playable_actions)

def random_playable_p_end_turn(c : CombatSimulator, actions : list[dict]) -> dict:
    end_turn = next((a for a in actions if a["action"] == "end_turn"), None)
    if end_turn is not None and rng.random_float() < P_END_TURN:
        return end_turn
    return random_playable(c, actions)

def rarity_preference(c : CombatSimulator, actions : list[dict]) -> dict:
    """Weighted by rarity of card"""
    unblocked, can_vuln, room = _situation(c, actions)
    return _weighted_play(c, actions, lambda card, a: _rarity_weight(card) * _common_factors(c, card, a, unblocked, can_vuln, room))

def _claude_weight(c : CombatSimulator, actions : list[dict]):
    unblocked, can_vuln, room = _situation(c, actions)
    def weight(card, a):
        w = _common_factors(c, card, a, unblocked, can_vuln, room)
        if card.type == CardType.Power:
            w *= POWER_FIRST
        elif card.card_id in BLOCK_CARDS and unblocked == 0:
            w *= 0.25                                                                # already safe: spend the energy on offence
        if card.is_upgraded and card.card_id not in UPGRADE_UNSCALED:
            w *= UPGRADE_WEIGHT
        return w
    return weight

### The pick of a pending card choice (True Grit's card, Armaments' card, Ashwater's cards)
REMOVING_CHOICES = ("exhaust", "exhaust_any", "discard_any")      # a card leaves the hand: the least wanted one goes

def _pick_for_choice(c : CombatSimulator, actions : list[dict], greedy : bool) -> dict:
    """The heuristic's answer to a pending card choice, with the weights it plays cards by (as if each card of the hand were playable now):
      - a card leaves the hand (exhaust, discard): unplayable cards first (those that stay in the deck, then ethereal ones), then the rest with
        probability proportional to 1 / weight, so the card the policy would play most is the one least likely to go.
        A choice of "any number" takes the unplayable cards only, and then stops.
      - Armaments: probability proportional to the weight of playing the card; an unplayable card is not upgraded while another can be.
      - anything else: uniform."""
    pending = c.combat_state.pending_choice
    kind = pending.kind if pending is not None else None
    picks = [a for a in actions if a["action"] == "choose_card"]
    if kind not in REMOVING_CHOICES + ("upgrade",) or not picks:
        return rng.choice(actions)
    cs = c.combat_state
    hand = cs.player.hand
    focus = next((i for i, e in enumerate(cs.enemies) if e.current_hp > 0 and not e.is_minion), 0)
    as_plays = [{"action" : "play_card", "card_index" : i, "target" : focus} for i, card in enumerate(hand) if not card.is_unplayable]
    weight = _claude_weight(c, as_plays)
    cards = [c._pile(a["pile"])[a["card_index"]] for a in picks]
    w = [max(1e-9, weight(card, {"action" : "play_card", "target" : focus})) for card in cards]
    def choose(indices, wanted):
        if greedy:
            return picks[max(indices, key=lambda i: wanted[i])]
        return rng.choices([picks[i] for i in indices], weights=[wanted[i] for i in indices])[0]

    if kind == "upgrade":
        playable = [i for i, card in enumerate(cards) if not card.is_unplayable]
        return choose(playable or list(range(len(picks))), w)

    inverse = [1.0 / x for x in w]
    stays = [i for i, card in enumerate(cards) if card.is_unplayable and card.card_id not in ETHEREAL_CARDS]
    fades = [i for i, card in enumerate(cards) if card.is_unplayable and card.card_id in ETHEREAL_CARDS]
    confirm = next((a for a in actions if a["action"] == "confirm_choice"), None)
    if pending.optional and confirm is not None:
        junk = stays + fades
        return choose(junk, inverse) if junk else confirm
    for group in (stays, fades, list(range(len(picks)))):
        if group:
            return choose(group, inverse)
    return rng.choice(actions)

def _claude_pick(c : CombatSimulator, actions : list[dict], greedy : bool) -> dict:
    if c.combat_state.pending_choice is not None:
        return _pick_for_choice(c, actions, greedy)
    return _weighted_play(c, actions, _claude_weight(c, actions), greedy=greedy)

def claude_heuristic(c : CombatSimulator, actions : list[dict]) -> dict:
    """Same shape as rarity_preference, but rarity is replaced by what the card does: Powers first (they pay off for the rest of
    the fight, which the rollout plays out), then draw/energy, Vulnerable, other Skills and Attacks equal, block only while damage
    is unblocked."""
    return _claude_pick(c, actions, greedy=False)

def claude_heuristic_greedy(c : CombatSimulator, actions : list[dict]) -> dict:
    """claude_heuristic, taking the heaviest play instead of drawing one, and without the random action."""
    return _claude_pick(c, actions, greedy=True)

ROLLOUT_POLICY_DICT = {
    RolloutPolicy.FirstAction : first_action,
    RolloutPolicy.RandomAction : random_action,
    RolloutPolicy.RandomPlayble : random_playable,
    RolloutPolicy.RandomPlayblePEndTurn : random_playable_p_end_turn,
    RolloutPolicy.RarityPreference : rarity_preference,
    RolloutPolicy.ClaudeHeuristic : claude_heuristic,
    RolloutPolicy.ClaudeHeuristicGreedy : claude_heuristic_greedy,
}
