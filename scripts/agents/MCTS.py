import random
import math
import sys

from sts2_lite.combat import CombatState, Combat

EXPLORATION_CONSTANT = 0.5
TURN_DECAY_CONSTANT = 0.05


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
        self.is_fully_expanded = False
        if parent:
            self.depth = parent.depth + 1

class sts2_MCTS:
    _root_node : sts2_Node = None
    _num_sims: int = 0
    _max_sims: int = 1000

    def __init__(self):
        pass

    def monte_carlo_tree_search(self, combat_state : CombatState, max_sims : int) -> dict:
        sys.setrecursionlimit(max_sims)
        self._root_node = sts2_Node(None, CombatState.deepcopy(combat_state))
        self._num_sims = 0
        self._max_sims = max_sims

        while self._num_sims < self._max_sims:
            leaf = self.traverse_node(self._root_node) # find optimal node to simulate from
            sim_result = self._simulate_random_combat(leaf) # simulate
            backpropagate(leaf, sim_result)

        for node in self._root_node.children:
            print(str(node.action) + ": " + str(node.total_reward/node.visits) + ", " + str(node.visits))

        best_child = max(self._root_node.children, key=lambda c: c.visits)
        sys.setrecursionlimit(1000)
        return best_child.action

    # finds the optimal node to simulate from
    def traverse_node(self, node : sts2_Node) -> sts2_Node:
        while node.is_fully_expanded:
            node = self._best_uct(node)
        if not node.is_expanded:
            expand_node(node)
        if node.is_terminal:
            return node
        leaf = get_unvisited_child(node)
        return leaf or node
        
    # simulate combat to end
    def _simulate_random_combat(self, node : sts2_Node) -> float:

        c = Combat(CombatState.deepcopy(node.state))
        while not c.is_over:
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
        # if won fight: outcome is best max hp with slight bias towars less turns
        if current_hp > 0:
            outcome = (float(current_hp) / max_hp) - TURN_DECAY_CONSTANT*num_turns
        # otherwise: minimize enemy HP
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
    node.is_fully_expanded = True
    return None

def expand_node(node : sts2_Node):
    c = Combat(node.state)
    actions = c.get_available_actions()

    # expand node
    for a in actions:
        c_a = Combat(CombatState.deepcopy(node.state))
        c_a.perform_action(a)
        new_child = sts2_Node(node, c_a.combat_state, a)
        node.children.append(new_child)

    node.is_expanded = True

def backpropagate(node : sts2_Node, result):
    if node is None:
        return
    node.total_reward += result
    node.visits += 1
    backpropagate(node.parent, result)