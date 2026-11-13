import copy
import json
import math
import time


from sts2_lite import rng
from sts2_lite.combat import CombatState, CombatSimulator

from agents.sts2_MCTS.state_key import state_key
from agents.sts2_MCTS.stats import Z_SCORE, TIE_MARGIN
from agents.sts2_MCTS.order_check import OrderCheck
from agents.sts2_MCTS.paired_check import PairedCheck
from agents.sts2_MCTS import outcome_score
from agents.sts2_MCTS.params import DEFAULT_CONFIG, SearchConfig
from agents.sts2_MCTS.rollout_policy import rollout_policy

CULLABLE_PILES = ("hand", "discard") # draw pile is not neccessarily cullable because of known_top cards

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
    _search_config : SearchConfig = DEFAULT_CONFIG      # the config of the search in progress (the defaults before the first)
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
        """cap * tanh(spread / info_sigma) * the share of sampled outcomes with something left to play.
        spread is the standard deviation, between the outcomes, of their values (weighted by how often each was sampled), with the
        noise of each outcome's own estimate taken off, so outcomes that only look different by chance earn nothing."""
        sampled = [(node.outcomes[k], node.outcome_counts[k]) for k in node.outcomes]
        seen = [(o, c) for o, c in sampled if o.visits >= self._search_config.uct.info_min_visits]
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
        return self._info_cap * math.tanh(spread / self._search_config.uct.info_sigma) * actionable

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
        tie = self._search_config.confidence
        if not self._search_config.prefer_info or top.visits < tie.tie_min_visits:
            return top
        informative = [c for c in children if c.is_chance_node and c.action["action"] != "end_turn"
                       and c.visits >= max(tie.tie_min_visits, tie.tie_visit_fraction * top.visits) and self._tied(c, top)]
        return max(informative, key=lambda c: c.visits) if informative else top

    ### Replaying a line of moves, for the paired comparison (paired_check.py) and the order check (order_check.py)

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
        end_turn = turn + self._search_config.max_rollout_turns
        while not c.is_over and cs.turn_number < end_turn:
            if cs.turn_number != turn:
                turn = cs.turn_number
                rng.seed((seed << 20) + turn)
            actions = c.get_available_actions()
            if len(actions) == 0:
                break
            c.perform_action(rollout_policy(c, actions, self._search_config.rollout, self._search_config.heuristic))
        return self._rate_outcome(cs)

    def _paired_check(self, picked : sts2_Node) -> dict | None:
        """See paired_check.py."""
        return PairedCheck(self).run(picked)

    ### The tree's own line, for the checks that replay it (paired comparison above, order_check.py)

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
        """See order_check.py."""
        return OrderCheck(self).run(picked)

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
        cap = max(1, math.ceil(self._search_config.outcome_c * node.visits ** self._search_config.outcome_alpha))

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
        end_turn = c.combat_state.turn_number + self._search_config.max_rollout_turns
        
        while not c.is_over and c.combat_state.turn_number < end_turn:
            actions = c.get_available_actions()

            if len(actions) == 0:
                break

            action = rollout_policy(c, actions, self._search_config.rollout, self._search_config.heuristic)
            
            c.perform_action(action)

        self._num_sims += 1
        outcome = self._rate_outcome(c.combat_state)
        return outcome

    def _rate_outcome(self, combat_state : CombatState) -> float:
        """See outcome_score.py."""
        return outcome_score.rate_outcome(combat_state, self._search_config.reward, self._starting_hp, self._starting_max_hp, self._expected_total_hp)

    def _enemy_progress_left(self, combat_state : CombatState) -> float:
        return outcome_score.enemy_progress_left(combat_state, self._expected_total_hp)

    # uct score 
    def get_uct_score(self, node : sts2_Node, parent : sts2_Node | None = None):
        # a shared node (transposition) has several parents: use the one the search came through
        if parent is None:
            parent = node.parent
        if node.visits == 0:
            return 0
        return node.total_reward/node.visits + self._search_config.exploration*self._exploration_scale()*math.sqrt(math.log(max(1, parent.visits))/node.visits)

    def _exploration_scale(self) -> float:
        """How wide the rewards are, as UCT's exploration term needs it: a fixed exploration_scale if one is set, else sized from the
        lowest and highest rollout reward seen in this fight's tree."""
        uct = self._search_config.uct
        if uct.exploration_scale is not None:
            return uct.exploration_scale
        span = max(self._reward_hi - self._reward_lo, uct.min_reward_span)
        return (span / 2.0) ** uct.exploration_power

    def _best_uct(self, node : sts2_Node) -> sts2_Node:
        if len(node.children) == 0:
            return node
        return max(node.children, key = lambda x: self.get_uct_score(x, node))

    def _calculate_expected_total_hp(self, combat_state : CombatState):
        return outcome_score.expected_total_hp(combat_state)

    def _check_statistical_exit(self)-> str | None:
        # ensure minimum sims has been reached
        if self._num_sims < max(self._search_config.min_sims, 40* len(self._root_node.children)):
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
        if Z_SCORE*SE_diff < self._search_config.confidence.epsilon:
            best_mean = max(node_a.total_reward/node_a.visits, node_b.total_reward/node_b.visits)
            return "TIE" if best_mean > 0.0 else None # only return TIE if winning line
        
        return None

    def _check_exit(self) -> tuple[bool, str]:
        # check min sims
        min_sims = self._search_config.min_sims
        if self._num_sims < min_sims:
            return False, None
        # check max sims reached
        if self._num_sims >= self._search_config.max_sims:
            return True, "MAX_SIMS"
        # check time limit
        if self._num_sims >= min_sims and self._search_config.time_budget is not None and time.perf_counter() >= (self._start_time + self._search_config.time_budget):
            return True, "TIME_BUDGET"
        # check for statistical confidence (every 50)
        statistical_exit_reason = self._check_statistical_exit()
        if self._search_config.early_exit and self._num_sims >= min_sims and self._num_sims%50 == 0 and statistical_exit_reason is not None:
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

def cull_identical_actions(c : CombatSimulator, actions : list[dict]) -> list[dict]:
    seen = set()
    kept = []
    for a in actions:
        key = _action_key(c,a)
        if key not in seen:
            seen.add(key)
            kept.append(a)
    return kept

