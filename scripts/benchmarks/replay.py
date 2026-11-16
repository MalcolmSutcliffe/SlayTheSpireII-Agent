"""Replays one fight of a calibration chain turn by turn, with the walk's rollout policy and with the MCTS from the same start, to see where they part.

Usage (from scripts/):
  python -m benchmarks.replay --seed 6 --fight 1 [--time-budget 0.1] [--policy ClaudeHeuristic] [--p-random P] [--tries 1]
`--fight N` is the Nth real fight of the chain of that seed (as benchmarks.calibrate numbers them, from 1). The rollout policy is played `--tries` times
(it is random): the first is shown turn by turn, the others as a one-line summary each."""
from __future__ import annotations
import argparse
import contextlib
import io
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmarks.bench import SEARCH_SEED_OFFSET
from sts2_lite import rng
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.status import StatusId
from agents.sts2_MCTS import outcome_score


def card_name(card) -> str:
    return card.card_id.name + ("+" if card.is_upgraded else "")


def describe(sim : CombatSimulator, action : dict) -> str:
    cs = sim.combat_state
    kind = action["action"]
    if kind == "play_card":
        text = card_name(cs.player.hand[action["card_index"]])
        if "target_name" in action:
            text += " -> " + str(action["target_name"])
        return text
    if kind == "choose_card":
        return "choose " + action.get("card_id", "?")
    return kind


def show_state(cs : CombatState) -> str:
    p = cs.player
    enemies = ", ".join("%s %d hp%s hits %dx%d" % (e.enemy_id, e.current_hp, "+%d" % e.block if e.block else "", e.attack_damage, e.num_attacks) for e in cs.enemies if e.current_hp > 0)
    return "turn %d  hp %d/%d block %d energy %d  hand [%s]  | %s" % (cs.turn_number, p.current_hp, p.max_hp, p.block, cs.energy, " ".join(card_name(c) for c in p.hand), enemies)


def play_traced(sim, choose, label : str, verbose : bool = True) -> dict:
    """`choose(sim, actions) -> action`; prints the turn's start and the plays, then the result."""
    cs = sim.combat_state
    hp0, turn0, turn, plays = cs.player.current_hp, cs.turn_number, None, []
    def flush():
        if plays and verbose:
            print("      plays: " + ", ".join(plays))
        plays.clear()
    while not sim.is_over and cs.turn_number < turn0 + 50:
        if cs.turn_number != turn:
            flush()
            turn = cs.turn_number
            if verbose:
                print("    " + show_state(cs))
        actions = sim.get_available_actions()
        if not actions:
            break
        action = actions[0] if len(actions) == 1 else choose(sim, actions)
        plays.append(describe(sim, action))
        sim.perform_action(action)
    flush()
    won = outcome_score.is_win(cs)
    result = {"won": won, "hp_lost": hp0 - max(0, cs.player.current_hp), "turns": cs.turn_number - turn0}
    print("  %-8s %s, %d HP lost, %d turns" % (label, "won" if won else "LOST", result["hp_lost"], result["turns"]))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--fight", type=int, required=True)
    ap.add_argument("--time-budget", type=float, default=0.1)
    ap.add_argument("--policy", default="ClaudeHeuristic")
    ap.add_argument("--p-random", type=float, default=None)
    ap.add_argument("--potions", action="store_true", help="let the MCTS drink the potions (the rollout policy never does)")
    ap.add_argument("--tries", type=int, default=1)
    args = ap.parse_args()

    from agents.sts2_MCTS.MCTS import sts2_MCTS
    from agents.sts2_MCTS.params import RolloutPolicy, SearchConfig
    from agents.sts2_MCTS.rollout_policy import rollout_policy
    from benchmarks.calibrate import make_simulator
    from agents.deck_eval.route_sim import RouteSimulator
    from agents.deck_eval.evaluator import DeckEvaluator
    from agents.deck_eval.fight_pool import load_pool, target_types
    from agents.deck_eval.route_sim import play_walk, sample_walks
    from sts2_lite.run import new_run

    pool = load_pool()
    targets = target_types(pool)
    config = DeckEvaluator(pool, targets, RolloutPolicy[args.policy]).config
    if args.p_random is not None:
        config = config.tuned(p_random_action=args.p_random)
    mcts_config = SearchConfig(time_budget=args.time_budget)
    base, seen, made = make_simulator(args.time_budget), [0], []

    class Replaying(base):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            made.append(self)

        def play(self, sim):
            if self.turn_limit is not None:
                return RouteSimulator.play(self, sim)
            seen[0] += 1
            if seen[0] != args.fight:
                return RouteSimulator.play(self, sim)
            cs = sim.combat_state
            start = CombatState.deepcopy(cs)
            print("fight %d of seed %d: %s in %s, deck %d cards, %d/%d HP" % (args.fight, args.seed, self.room_now[1], self.room_now[0], len(self.run_state.deck), cs.player.current_hp, cs.player.max_hp))
            print("  deck: " + " ".join(sorted(card_name(c) for c in cs.player.draw_pile + cs.player.hand)))
            print("  relics: " + " ".join(r.get("id", "?") if isinstance(r, dict) else str(getattr(r, "relic_id", r)) for r in cs.player.relics))
            for attempt in range(args.tries):
                rng.seed(self.walk.seed * 1000 + attempt)
                trial = CombatSimulator(CombatState.deepcopy(start))
                pick = lambda s, a: rollout_policy(s, a, config.rollout, config.heuristic)
                play_traced(trial, pick, "rollout", verbose=attempt == 0)
            seed = self.walk.seed * 1000 + self.fights
            rng.seed(seed); world = rng.getstate()
            rng.seed(SEARCH_SEED_OFFSET + seed); search = rng.getstate()
            trial = CombatSimulator(CombatState.deepcopy(start))
            if not args.potions:
                trial.combat_state.player.potions = []
            rng.setstate(world)
            trial.combat_state.player.shuffle_draw_pile()
            world = rng.getstate()
            searcher, state = sts2_MCTS(), {"world": world, "search": search}
            def choose(s, actions):
                rng.setstate(state["search"])
                with contextlib.redirect_stdout(io.StringIO()):
                    action, _ = searcher.monte_carlo_tree_search(s.combat_state, mcts_config)
                state["search"] = rng.getstate()
                return action
            # the world's dice go back in around each move, as the benchmarks do
            real_perform = trial.perform_action
            def perform(action):
                rng.setstate(state["world"])
                real_perform(action)
                state["world"] = rng.getstate()
            trial.perform_action = perform
            play_traced(trial, choose, "mcts")
            raise SystemExit(0)

    run = new_run(0)
    player, deck = run.player_dict(), run.deck
    for act in range(1, 4):
        walk = sample_walks(None, act, 0, 1, args.seed * 10 + act)[0]
        result = play_walk(walk, deck, player, config, targets, simulator=Replaying)
        final = made[-1].run_state
        if final.dead or not result.alive:
            break
        player, deck = {**final.player_dict(), "hp": final.max_hp}, final.deck
    print("the chain ended before fight %d" % args.fight)


if __name__ == "__main__":
    main()
