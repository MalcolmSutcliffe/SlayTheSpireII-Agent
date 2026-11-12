from __future__ import annotations
"""Floor 29, Ovicopter (12 HP) with two Strikes in hand and 2 energy: Strike, Strike kills it, which ends the fight.
Blood Wall is safe but takes HP and gives the hatchlings a turn. The paired check once replayed the first Strike followed by the rollout
policy, which need not play the second Strike, and swapped it for Blood Wall; each move is now replayed along the line the tree found."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from sts2_lite import rng
from sts2_lite.combat import CombatState
from agents.sts2_MCTS.MCTS import sts2_MCTS, SearchConfig

STATE = os.path.join(os.path.dirname(__file__), "fixtures", "ovicopter_lethal.json")


def search(seed, **config):
    rng.seed(seed)
    state = CombatState.from_dict(json.load(open(STATE)))
    move, stats = sts2_MCTS().monte_carlo_tree_search(state, SearchConfig(max_sims=2000, time_budget=None, **config))
    return state, move, stats


def test_the_lethal_strike_is_kept_when_the_tree_prefers_it():
    for seed in (2, 3):             # the old paired check replaced the Strike with Blood Wall on these
        state, move, stats = search(seed)
        card = state.player.hand[move["card_index"]].card_id.name if move["action"] == "play_card" else move["action"]
        assert card == "STRIKE_IRONCLAD" and move["target_name"] == "OVICOPTER_0", seed
        assert not stats["paired"]["replaced"], seed
