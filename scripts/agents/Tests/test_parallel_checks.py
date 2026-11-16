"""The paired and order checks replay their scenarios on several processes (SearchConfig.check_workers, parallel.py). A replay depends only on
the state, the line and the seed, so the decision must not depend on the number of processes. Run from scripts/: python -m pytest agents/Tests/test_parallel_checks.py"""
from agents.sts2_MCTS.parallel import Rollouts
from agents.sts2_MCTS.params import SearchConfig, RolloutPolicy
from sts2_lite import rng
from sts2_lite.card import CardId
from test_order import tree_with_line, dexterity_turn
from test_paired import block_choice, root_with_visits, child_for


def paired(workers, batch=50):
    mcts, root = root_with_visits(block_choice(), SearchConfig(paired_scenarios=300, paired_batch=batch, check_workers=workers))
    rng.seed(11)
    return mcts._paired_check(child_for(root, "play_card", 0))

def test_the_paired_check_gives_the_same_result_on_any_number_of_processes():
    serial, parallel = paired(1), paired(4)
    assert serial["replaced"] == parallel["replaced"] and serial["scenarios_run"] == parallel["scenarios_run"]
    assert [c["gain"] for c in serial["compared"]] == [c["gain"] for c in parallel["compared"]]

def test_the_paired_check_without_batches_gives_the_same_result_on_any_number_of_processes():
    serial, parallel = paired(1, batch=0), paired(6, batch=0)
    assert [c["gain"] for c in serial["compared"]] == [c["gain"] for c in parallel["compared"]]

def order(workers):
    config = SearchConfig(paired_scenarios=300, check_workers=workers, rollout=RolloutPolicy.ClaudeHeuristicGreedy)
    mcts, first = tree_with_line(dexterity_turn(), [CardId.DEFEND_IRONCLAD, "potion", "end_turn"], config)
    rng.seed(5)
    return mcts._order_check(first)

def test_the_order_check_gives_the_same_result_on_any_number_of_processes():
    serial, parallel = order(1), order(4)
    assert serial["replaced"] == parallel["replaced"] and serial["action"] == parallel["action"] and serial["scenarios"] == parallel["scenarios"]
    assert [c["gain"] for c in serial["compared"]] == [c["gain"] for c in parallel["compared"]]

def test_one_worker_replays_in_this_process():
    mcts, root = root_with_visits(block_choice(), SearchConfig(check_workers=1))
    with Rollouts(mcts, root.state, 1) as r:
        assert r.pool is None

def test_the_processes_are_gone_after_the_check():
    mcts, root = root_with_visits(block_choice(), SearchConfig())
    with Rollouts(mcts, root.state, 3) as r:
        assert r.pool is not None
    assert r.pool is None
