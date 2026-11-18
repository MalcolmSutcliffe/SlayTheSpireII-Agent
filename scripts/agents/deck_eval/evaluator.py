"""Plays a deck through N fights from the pool with a cheap rollout policy and scores them like the MCTS does."""
from __future__ import annotations
import time
from dataclasses import dataclass

from sts2_lite import rng

from agents.sts2_MCTS import outcome_score
from agents.sts2_MCTS.params import SearchConfig, RolloutPolicy
from agents.deck_eval.config import DEFAULT, DeckEvalConfig
from agents.deck_eval.fight_builder import build_fight
from agents.deck_eval.playout import play_out
from agents.deck_eval.fight_pool import FightTemplate
from agents.deck_eval.route_sim import play_walk


@dataclass
class DeckScore:
    mean : float
    win_rate : float
    mean_hp_left : float
    seconds : float
    rewards : list[float]       # one per fight, in the order of the fights: two decks on the same fights can be compared pair by pair


# The walks' rollout policy: the heuristic with the dice taken out. It is closer to the MCTS's turns than the drawn one (benchmarks/policy_fit.py `tune`: 1.31 cards apart
# per turn against 1.57; the MCTS against itself: 0.76) and its fights come out nearer to the MCTS's (win rate and HP lost). The MCTS's own rollouts keep ClaudeHeuristic.
WALK_POLICY = RolloutPolicy.ClaudeHeuristicGreedy


class DeckEvaluator:
    def __init__(self, pool : list[FightTemplate], target_types : dict[str, str], policy = WALK_POLICY, config : DeckEvalConfig = DEFAULT):
        """`config`: how walks are scored and how long a fight may last (deck_eval/config.py); the rollouts play with `policy`."""
        self.pool, self.target_types, self.deck_config = pool, target_types, config
        self.config = SearchConfig().tuned(rollout=policy)

    def score_walks(self, deck : list[dict], player : dict, walks : list, event=None, card_walk : bool = False, focus : str | None = None) -> DeckScore:
        """Every walk through the route ahead played with `deck` (route_sim: the engine's run simulator from the run as `player` has it): a DeckScore with one
        reward per walk, `win_rate` the share of walks that came through every fight, `mean_hp_left` the HP at the end of them. Two decks on the same walks can
        be compared walk by walk. `event`: an EventPlan played before each walk. `card_walk`, `focus`: see route_sim.play_walk (the card reward chooser's walks)."""
        start, rewards, alive, hp_left = time.perf_counter(), [], 0, 0.0
        for walk in walks:
            result = play_walk(walk, deck, player, self.config, self.target_types, event, scoring=self.deck_config, card_walk=card_walk, focus=focus)
            rewards.append(result.reward)
            alive += result.alive
            hp_left += result.hp if result.alive else 0
        n = max(1, len(walks))
        return DeckScore(sum(rewards) / n, alive / n, hp_left / n, time.perf_counter() - start, rewards)

    def score(self, deck : list[dict], player : dict, fights : list[FightTemplate], seed : int) -> DeckScore:
        """`deck` played through each of `fights` on its own, from the HP `player` has (a timing pilot for the card reward chooser, and the benchmarks)."""
        start, rewards, wins, hp_left = time.perf_counter(), [], 0, 0.0
        cfg = self.config
        for i, template in enumerate(fights):
            rng.seed((seed << 10) + i)
            sim = build_fight(template, deck, player, self.target_types)
            cs = sim.combat_state
            expected, hp0, max0 = outcome_score.expected_total_hp(cs), cs.player.current_hp, cs.player.max_hp
            # every deck meets each turn with the same dice: the policy's luck cancels out between decks
            play_out(sim, cfg, self.deck_config.max_turns, new_turn=lambda turn, i=i: rng.seed(((seed << 10) + i << 10) + turn))
            rewards.append(outcome_score.rate_outcome(cs, cfg.reward, hp0, max0, expected))
            won = outcome_score.is_win(cs)
            wins += won
            hp_left += max(0, cs.player.current_hp) if won else 0
        n = max(1, len(fights))
        return DeckScore(sum(rewards) / n, wins / n, hp_left / n, time.perf_counter() - start, rewards)
