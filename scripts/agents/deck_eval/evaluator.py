"""Plays a deck through N fights from the pool with a cheap rollout policy and scores them like the MCTS does."""
from __future__ import annotations
import time
from dataclasses import dataclass

from sts2_lite import rng
from sts2_lite.combat import CombatState

from agents.sts2_MCTS import outcome_score
from agents.sts2_MCTS.params import SearchConfig, RolloutPolicy
from agents.sts2_MCTS.rollout_policy import rollout_policy
from agents.deck_eval.fight_builder import build_fight
from agents.deck_eval.fight_pool import FightTemplate

MAX_TURNS = 25


@dataclass
class DeckScore:
    mean : float
    win_rate : float
    mean_hp_left : float
    seconds : float
    rewards : list[float]       # one per fight, in the order of the fights: two decks on the same fights can be compared pair by pair


class DeckEvaluator:
    def __init__(self, pool : list[FightTemplate], target_types : dict[str, str], policy = RolloutPolicy.ClaudeHeuristic):
        self.pool, self.target_types = pool, target_types
        self.config = SearchConfig().tuned(rollout=policy)

    def play_chain(self, deck : list[dict], player : dict, fights : list[FightTemplate], seed : int) -> tuple[bool, int]:
        """The fights one after the other with the HP carried over (the combat's own heal after a win included): (alive at the end, HP left)."""
        cfg, hp = self.config, player["hp"]
        for i, template in enumerate(fights):
            rng.seed((seed << 10) + i)
            sim = build_fight(template, deck, {**player, "hp": hp}, self.target_types)
            cs = sim.combat_state
            end_turn = cs.turn_number + MAX_TURNS
            turn = cs.turn_number
            while not sim.is_over and cs.turn_number < end_turn:
                if cs.turn_number != turn:
                    turn = cs.turn_number
                    rng.seed(((seed << 10) + i << 10) + turn)
                actions = sim.get_available_actions()
                if not actions:
                    break
                sim.perform_action(rollout_policy(sim, actions, cfg.rollout, cfg.heuristic))
            if not (cs.player.current_hp > 0 and all(e.is_minion or e.current_hp <= 0 for e in cs.enemies)):
                return False, 0
            hp = cs.player.current_hp
        return True, hp

    def score(self, deck : list[dict], player : dict, fights : list[FightTemplate], seed : int, extras : list[list[dict]] | None = None) -> DeckScore:
        """`extras`: cards added to the deck for one fight each (the cards the deck is expected to have gained by then); None: the deck as it is."""
        start, rewards, wins, hp_left = time.perf_counter(), [], 0, 0.0
        cfg = self.config
        for i, template in enumerate(fights):
            rng.seed((seed << 10) + i)
            sim = build_fight(template, deck + extras[i] if extras else deck, player, self.target_types)
            cs = sim.combat_state
            expected, hp0, max0 = outcome_score.expected_total_hp(cs), cs.player.current_hp, cs.player.max_hp
            end_turn = cs.turn_number + MAX_TURNS
            turn = cs.turn_number
            while not sim.is_over and cs.turn_number < end_turn:
                if cs.turn_number != turn:      # every deck meets each turn with the same dice: the policy's luck cancels out between decks
                    turn = cs.turn_number
                    rng.seed(((seed << 10) + i << 10) + turn)
                actions = sim.get_available_actions()
                if not actions:
                    break
                sim.perform_action(rollout_policy(sim, actions, cfg.rollout, cfg.heuristic))
            rewards.append(outcome_score.rate_outcome(cs, cfg.reward, hp0, max0, expected))
            won = cs.player.current_hp > 0 and all(e.is_minion or e.current_hp <= 0 for e in cs.enemies)
            wins += won
            hp_left += max(0, cs.player.current_hp) if won else 0
        n = max(1, len(fights))
        return DeckScore(sum(rewards) / n, wins / n, hp_left / n, time.perf_counter() - start, rewards)
