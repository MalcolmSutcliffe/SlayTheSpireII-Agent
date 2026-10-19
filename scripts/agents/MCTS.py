import random
import math
import copy

from sts2_env.run.run_manager import RunManager
from sts2_env.core.rng import Rng, INT_MAX

EXPLORATION_CONSTANT = 0.5


class sts2_Node:
    
    parent : sts2_Node
    children : dict[tuple,tuple[dict,sts2_Node]] # dictionary of action (frozendict) pointing to action/child pair (dict,sts2_Node)
    visits : int
    total_reward: float
    is_terminal : bool

    def __init__(self, parent : sts2_Node):
        self.parent = parent
        self.children = {}
        self.visits = 0
        self.total_reward = 0.0
        self.is_terminal = False

    # uct score 
    def get_uct_score(self, num_sims : int):
        if self.visits == 0:
            return 999
        return self.total_reward / self.visits + EXPLORATION_CONSTANT*math.sqrt(math.log(num_sims)/self.visits)

class sts2_MCTS:

    _current_exploration : RunManager = None
    _root_node : sts2_Node = None
    _num_sims: int = 0
    _max_sims: int = 1000

    def __init__(self):
        pass


    def monte_carlo_tree_search(self, mgr : RunManager, max_sims : int) -> dict:
        self._root_node = sts2_Node(None)
        self._num_sims = 0
        self._max_sims = max_sims

        while self._num_sims < self._max_sims:
            # make copy of state
            self._current_exploration = copy.deepcopy(mgr)
            # randomize rng 
            mgr.randomize_rng()
            leaf = self.traverse_node(self._root_node) # find optimal node to simulate from
            sim_result = self._simulate_random_combat() # simulate
            backpropagate(leaf, sim_result)

        best_child = max(self._root_node.children.values(), key=lambda c: c[1].visits)
        return best_child[0]

    # finds the optimal node to simulate from
    def traverse_node(self, node : sts2_Node) -> sts2_Node:
        # if leaf node
        if node.visits == 0:
            return node
        
        # check if terminal node
        if node.is_terminal:
            return node
        if self._current_exploration.get_combat_state() is None:
            node.is_terminal = True
            return node
        if self._current_exploration.get_combat_state().is_over:
            node.is_terminal = True
            return node

        # expand node
        actions = self._current_exploration.get_available_actions()

        # expand node
        for a in actions:
            key = tuple(sorted(a.items()))
            if key not in node.children:
                new_child = sts2_Node(node)
                node.children[key] = (a,new_child)

        # if terminal
        if len(node.children.keys()) == 0:
            node.is_terminal = True
            return node
        
        choice = self._best_uct(node)
        
        # apply choice to sim
        self._current_exploration.take_action(choice[0])
        # traverse this new node
        return self.traverse_node(choice[1])
        
    # simulate combat to end
    def _simulate_random_combat(self) -> float:
        
        while self._current_exploration.get_combat_state():

            actions = self._current_exploration.get_available_actions()

            # remove potion actions (for now)
            actions = [a for a in actions if a["action"] != "use_potion"]

            if len(actions) == 0:
                break
            
            # if only action is end turn:
            if len(actions) <= 1:
                choice = actions[0]
            # choose random non end-turn action
            else:
                choice = random.choice(actions[1::])

            # print(choice)
            self._current_exploration.take_action(choice)

        self._num_sims += 1
        outcome = self._rate_outcome()
        print(outcome)
        return self._rate_outcome()


    def _rate_outcome(self) -> float:
        current_hp = self._current_exploration.run_state.player.current_hp
        max_hp = self._current_exploration.run_state.player.max_hp

        print(current_hp)
        return float(current_hp) / max_hp

    def _best_uct(self,node : sts2_Node) -> tuple[dict, sts2_Node]:
        return max(node.children.values(), key = lambda x: x[1].get_uct_score(self._num_sims))

def backpropagate(node : sts2_Node, result):
    if node is None:
        return
    node.visits += 1
    node.total_reward += result
    backpropagate(node.parent, result)