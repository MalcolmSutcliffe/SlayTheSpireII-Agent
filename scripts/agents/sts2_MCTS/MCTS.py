import math
import time

from enum import Enum, auto
from dataclasses import dataclass

from sts2_lite import rng
from sts2_lite.combat import CombatState, CombatSimulator

from sts2_lite.enemy import Enemy
from sts2_lite.state_key import state_key

class RolloutPolicy(Enum):
    FirstAction = auto()            # just play first action
    RandomAction = auto()                 # random choice from all abailable actions
    RandomPlayble = auto()          # random choice that prefers playable cards first, then end turn
    RandomPlayblePEndTurn = auto()  # random playable, with P_End_TURN

## constants
MAX_ROLLOUT_TURNS = 50
MIN_SIMS = 100                  # always searches at least 100 simulations
DEFAULT_TIME_BUDGET = 5.0
DEFAULT_MAX_SIMS = 20000

# uct constants
EXPLORATION_CONSTANT = 2.0

# random sampling constants
DEFAULT_OUTCOME_C = 2.0
OUTCOME_ALPHA = 0.5

# outcome rating constants
WIN_BONUS = 1.0
HP_SCALE = 1.0
GAMMA = 0.999

# move confidence constants
EPSILON = 0.005
Z_SCORE = 2.33
TIE_MARGIN = 0.01                # root moves this close to the best (and not significantly worse) are tied
TIE_MIN_VISITS = 30              # the top move needs this many visits before a tie is considered
TIE_VISIT_FRACTION = 0.5         # a tied move needs this share of the top move's visits: a thin estimate is within the margin by luck

# rollout policy constants
ROLLOUT_POLICY = RolloutPolicy.RandomPlayblePEndTurn
P_END_TURN = 0.05

CULLABLE_PILES = ("hand", "discard") # draw pile is not neccessarily cullable because of known_top cards

@dataclass(frozen=True)
class SearchConfig:
    max_sims: int = DEFAULT_MAX_SIMS
    time_budget: float | None = None     # None = sim-count mode
    exploration: float = 2.0
    outcome_c: float = 2.0
    early_exit : bool = True             # allows the sim to exit early
    prefer_info : bool = True            # among tied root moves, play the one whose outcome is not yet known (a draw) first
    rollout: RolloutPolicy = RolloutPolicy.RandomPlayblePEndTurn

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
    _search_config : SearchConfig
    _num_sims: int = 0
    _start_time : float

    def __init__(self):
        pass

    def monte_carlo_tree_search(self, 
                                combat_state : CombatState, 
                                config : SearchConfig = SearchConfig()
                                ) -> tuple[dict, dict]:
        
        self._table = {}
        self._root_node = sts2_DeterministicNode(None, CombatState.deepcopy(combat_state), None)
        self._expected_total_hp = self._calculate_expected_total_hp(combat_state)
        self._starting_hp = combat_state.player.current_hp
        self._num_sims = 0
        self._search_config = config
        self._start_time = time.perf_counter()

        exit_reason = None

        while True:
            # check exit conditions
            do_exit, reason = self._check_exit()
            if do_exit:
                exit_reason = reason
                break
            # traverse and sim
            path = self.traverse_node(self._root_node) # root to the leaf to simulate from (a shared node has several parents, so the path is tracked)
            sim_result = self._simulate_random_combat(path[-1]) # simulate
            backpropagate(path, sim_result)

        stats = { 
            "children": [{"action": c.action, "visits": c.visits, "q": c.total_reward / c.visits} for c in self._root_node.children],
            "num_sims" : self._num_sims,
            "time_taken" : time.perf_counter() - self._start_time,
            "exit_reason" : exit_reason
                }
        best_child = self._pick_root_child()
        
        return best_child.action, stats

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
    def _simulate_random_combat(self, node : sts2_Node) -> float:

        c = CombatSimulator(CombatState.deepcopy(node.state))
        # shuffle draw pile to inject randomness into rollout
        c.combat_state.player.shuffle_draw_pile()
        end_turn = c.combat_state.turn_number + MAX_ROLLOUT_TURNS
        
        while not c.is_over and c.combat_state.turn_number < end_turn:
            actions = c.get_available_actions()

            if len(actions) == 0:
                break

            action = rollout_policy(actions, self._search_config.rollout)
            
            c.perform_action(action)

        self._num_sims += 1
        outcome = self._rate_outcome(c.combat_state)
        return outcome

    def _rate_outcome(self, combat_state : CombatState) -> float:
        current_hp = combat_state.player.current_hp
        num_turns = combat_state.turn_number
        won = current_hp > 0 and all(e.is_minion or e.current_hp <= 0 for e in combat_state.enemies)
        # if won fight: outcome is best max hp with slight bias towards less turns
        if won:
            hp_ratio = current_hp/self._starting_hp
            outcome = (WIN_BONUS - HP_SCALE*(1.0-math.sqrt(hp_ratio)))*(GAMMA**num_turns)
        # lost or unfinished: minimize enemy effective HP
        else:
            total_enemy_effective_hp = 0
            for enemy in combat_state.enemies:
                total_enemy_effective_hp += _effective_hp(enemy)
            if total_enemy_effective_hp == 0:     # every enemy died and so did the player: no better than a plain loss
                return -1.0
            outcome  = -float(total_enemy_effective_hp)/max(1,self._expected_total_hp)
        return outcome

    # uct score 
    def get_uct_score(self, node : sts2_Node, parent : sts2_Node | None = None):
        # a shared node (transposition) has several parents: use the one the search came through
        if parent is None:
            parent = node.parent
        if node.visits == 0:
            return 0
        return node.total_reward/node.visits + self._search_config.exploration*math.sqrt(math.log(max(1, parent.visits))/node.visits)

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

    def _check_statistical_exit(self)-> bool:
        # ensure minimum sims has been reached
        if self._num_sims < MIN_SIMS:
            return False

        # if only one child (can also exit)
        if len(self._root_node.children) < 2:
            return True

        # get the top two scoring children
        children_sorted = sorted(self._root_node.children, key=lambda c: c.visits)
        node_a = children_sorted[-1]
        node_b = children_sorted[-2]

        # ensure enough visits have been made
        if node_a.visits <= 30 or node_b.visits <= 30:
            return False

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
            return True

        # if difference is small enough
        if Z_SCORE*SE_diff < EPSILON:
            return True
        
        return False

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
        if self._search_config.early_exit and self._num_sims >= MIN_SIMS and self._num_sims%50 == 0 and self._check_statistical_exit():
            return True, "STATISTICAL_CONFIDENCE"
        
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
                new_child = table.setdefault(state_key(new_child.state), new_child)
        if not any(new_child is c for c in node.children):
            node.children.append(new_child)

    node.is_expanded = True

def backpropagate(path : list[sts2_Node], result : float):
    """Adds the result to every node on the path from the root to the simulated leaf."""
    for node in path:
        node.total_reward += result
        node.total_reward_squared += result*result
        node.visits += 1

def rollout_policy(actions, policy : RolloutPolicy):
    if len(actions) == 0:
        return None
    if len(actions) == 1:   
        return actions[0]
    return ROLLOUT_POLICY_DICT[policy](actions)

def _effective_hp(enemy : Enemy):
    if enemy.is_minion:
        return 0
    effective_hp = enemy.current_hp
    # edge cases
    if enemy.enemy_id.startswith("PHROG_PARASITE"):
        effective_hp += 4 * (17 + 21) / 2
    return effective_hp

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
### Rollout Policy functions
###

def first_action(actions : list[dict]) -> dict:
    return actions[0]

def random_action(actions : list[dict]) -> dict:
    return rng.choice(actions)

def random_playable(actions : list[dict]) -> dict:
    playable_actions = [a for a in actions if a["action"] != "end_turn"] or actions
    return rng.choice(playable_actions)

def random_playable_p_end_turn(actions : list[dict]) -> dict:
    end_turn = next((a for a in actions if a["action"] == "end_turn"), None)
    if end_turn is not None and rng.random_float() < P_END_TURN:
        return end_turn
    return random_playable(actions)

ROLLOUT_POLICY_DICT = {
    RolloutPolicy.FirstAction : first_action,
    RolloutPolicy.RandomAction : random_action,
    RolloutPolicy.RandomPlayble : random_playable,
    RolloutPolicy.RandomPlayblePEndTurn : random_playable_p_end_turn
}
