import random
import math
import copy

from sts2_lite.combat import CombatState, Combat

EXPLORATION_CONSTANT = 0.5


class sts2_Node:
    
    parent : sts2_Node
    children : list[sts2_Node]
    state : CombatState
    action : dict
    visits : int
    total_reward: float
    is_terminal : bool
    is_expanded : bool
    depth :int = 0

    def __init__(self, parent : sts2_Node, combat_state, action=None):
        self.parent = parent
        self.children = []
        self.action = action
        self.state = CombatState.deepcopy(combat_state)
        self.visits = 0
        self.total_reward = 0.0
        self.is_terminal = False
        self.is_expanded = False
        if parent:
            self.depth = parent.depth + 1

    # uct score 
    def get_uct_score(self, num_sims : int):
        if self.visits == 0:
            return 1
        return self.total_reward / self.visits + EXPLORATION_CONSTANT*math.sqrt(math.log(num_sims)/self.visits)

class sts2_MCTS:
    _root_node : sts2_Node = None
    _num_sims: int = 0
    _max_sims: int = 1000

    def __init__(self):
        pass

    def monte_carlo_tree_search(self, combat_state : CombatState, max_sims : int) -> dict:
        self._root_node = sts2_Node(None, combat_state)
        self._num_sims = 0
        self._max_sims = max_sims

        while self._num_sims < self._max_sims:
            leaf = self.traverse_node(self._root_node) # find optimal node to simulate from
            sim_result = self._simulate_random_combat(leaf) # simulate
            backpropagate(leaf, sim_result)

        best_child = max(self._root_node.children, key=lambda c: c.total_reward / c.visits)
        return best_child.action

    # finds the optimal node to simulate from
    def traverse_node(self, node : sts2_Node) -> sts2_Node:
        while node.is_expanded:
            node = self._best_uct(node)
        expand_node(node)
        return self._best_uct(node)
        
    # simulate combat to end
    def _simulate_random_combat(self, node : sts2_Node) -> float:

        c = Combat(copy.deepcopy(node.state))
        while not c.is_over:
            actions = c.get_available_actions()

            if len(actions) == 0:
                break
            
            # if only action is end turn:
            if len(actions) <= 1:
                choice = actions[0]
            # choose random non end-turn action
            else:
                choice = random.choice(actions[::-1])

            # print(choice)
            c.perform_action(choice)

        self._num_sims += 1
        outcome = self._rate_outcome(c.combat_state)
        return outcome


    def _rate_outcome(self, combat_state) -> float:
        current_hp = combat_state.player.current_hp
        max_hp = combat_state.player.max_hp
        return float(current_hp) / max_hp

    def _best_uct(self, node : sts2_Node) -> sts2_Node:
        if len(node.children) == 0:
            return node
        return max(node.children, key = lambda x: x.get_uct_score(self._num_sims))

def expand_node(node : sts2_Node):
    c = Combat(node.state)
    actions = c.get_available_actions()

    # expand node
    for a in actions:
        c_a = Combat(CombatState.deepcopy(node.state))
        c_a.perform_action(a)
        new_child = sts2_Node(node, c.combat_state, a)
        node.children.append(new_child)

    node.is_expanded = True

def backpropagate(node : sts2_Node, result):
    if node is None:
        return
    node.visits += 1
    node.total_reward += result
    backpropagate(node.parent, result)