import math

from sts2_lite import rng
from sts2_lite.combat import CombatState, CombatSimulator

EXPLORATION_CONSTANT = 0.5
TURN_DECAY_CONSTANT = 0.01
WIN_BONUS = 1.0     # keeps every win above every loss
MAX_ROLLOUT_TURNS = 50

OUTCOME_C = 2.0
OUTCOME_ALPHA = 0.5

class sts2_Node:
    parent : sts2_Node
    action : dict
    visits : int
    total_reward: float
    depth :int = 0
    is_chance_node : bool

    def __init__(self, parent : sts2_Node, action=None):
        self.parent = parent
        self.action = action
        self.visits = 0
        self.total_reward = 0.0
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
    _root_node : sts2_Node = None
    _num_sims: int = 0
    _max_sims: int = 1000

    def __init__(self):
        pass

    def monte_carlo_tree_search(self, combat_state : CombatState, max_sims : int) -> dict:
        max_sims = max(100, max_sims)
        self._root_node = sts2_DeterministicNode(None, CombatState.deepcopy(combat_state), None)
        self._num_sims = 0
        self._max_sims = max_sims

        while self._num_sims < self._max_sims:
            leaf = self.traverse_node(self._root_node) # find optimal leaf node to simulate from
            sim_result = self._simulate_random_combat(leaf) # simulate
            backpropagate(leaf, sim_result)

        for node in self._root_node.children:
            print(str(node.action) + ": " + str(node.total_reward/node.visits) + ", " + str(node.visits))

        best_child = max(self._root_node.children, key=lambda c: c.visits)
        return best_child.action

    # finds the optimal node to simulate from
    def traverse_node(self, node : sts2_Node) -> sts2_Node:
        while True:
            # chance node
            if node.is_chance_node:
                node, is_new = self._sample_outcome(node)
                if is_new:
                    return node # roll out from here
            # deterministic node
            else:
                # if terminal node, return
                if node.is_terminal:
                    return node
                # if node has not yet been expanded, expand it
                if not node.is_expanded:
                    expand_node(node)
                # if node has unvisited child, return that
                leaf = get_unvisited_child(node)
                if leaf is not None:
                    if leaf.is_chance_node:
                        node = leaf # resolve it into an outcome
                        continue
                    return leaf
                # otherwise, get best utc and keep traversing
                node = self._best_uct(node)


    # resolve a chance node
    def _sample_outcome(self, node: sts2_Node) -> tuple[sts2_Node, bool]:
        cap = max(1, math.ceil(OUTCOME_C * node.visits ** OUTCOME_ALPHA))

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
            
            c.perform_action(actions[0])

        self._num_sims += 1
        outcome = self._rate_outcome(c.combat_state)
        return outcome


    def _rate_outcome(self, combat_state : CombatState) -> float:
        current_hp = combat_state.player.current_hp
        max_hp = combat_state.player.max_hp
        num_turns = combat_state.turn_number
        won = current_hp > 0 and all(e.is_minion or e.current_hp <= 0 for e in combat_state.enemies)
        # if won fight: outcome is best max hp with slight bias towars less turns
        if won:
            turn_penalty = min(TURN_DECAY_CONSTANT*num_turns, WIN_BONUS)
            outcome = WIN_BONUS + (float(current_hp) / max_hp) - turn_penalty
        # lost or unfinished: minimize enemy HP
        else:
            total_enemy_hp = 0
            total_enemy_max_hp = 0
            for enemy in combat_state.enemies:
                total_enemy_max_hp += enemy.max_hp
                total_enemy_hp += enemy.current_hp
            outcome  = -float(total_enemy_hp)/total_enemy_max_hp
        return outcome

    # uct score 
    def get_uct_score(self, node : sts2_Node):
        if node.visits == 0:
            return 0
        return node.total_reward/node.visits + EXPLORATION_CONSTANT*math.sqrt(math.log(self._num_sims)/node.visits)

    def _best_uct(self, node : sts2_Node) -> sts2_Node:
        if len(node.children) == 0:
            return node
        return max(node.children, key = lambda x: self.get_uct_score(x))

def get_unvisited_child(node : sts2_Node):
    for child in node.children:
        if child.visits == 0:
            return child
    return None

def expand_node(node : sts2_Node):
    c = CombatSimulator(node.state)
    actions = c.get_available_actions()

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
        node.children.append(new_child)

    node.is_expanded = True

def backpropagate(node, result):
    while node is not None:
        node.total_reward += result
        node.visits += 1
        node = node.parent

def outcome_key(state):
    """Canonical key: hand and draw pile contents (order ignored), who is on the field and their next moves."""
    p = state.player
    ids = lambda cards: tuple(sorted((c.card_id.value, c.is_upgraded) for c in cards))
    n = p.known_top
    known = tuple((c.card_id.value, c.is_upgraded) for c in p.draw_pile[len(p.draw_pile) - n:]) if n else ()
    return ids(p.hand), ids(p.draw_pile), known, tuple((e.enemy_id, e.move_id) for e in state.enemies)
