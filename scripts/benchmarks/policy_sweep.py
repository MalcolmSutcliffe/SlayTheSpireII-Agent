"""Rollout-policy-only benchmark: the policy itself plays whole fights from the benchmark states (no search), so a weight's effect
on the policy shows up without search noise. Score and pairing are the fights suite's (lower is better, paired by file and seed).

Usage (from scripts/):
  python -m benchmarks.policy_sweep eval  --policy RarityPreference [--w BLOCK_MULT=6 --w RARITY.Rare=12] [--seeds 100]
  python -m benchmarks.policy_sweep sweep --policy RarityPreference [--seeds 100]      # one-at-a-time grids around the defaults
A --w name is a module constant of agents.sts2_MCTS.MCTS, or RARITY.<CardRarity> for an entry of RARITY_WEIGHTS."""
from __future__ import annotations

import argparse
import contextlib
import json
import statistics
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agents.sts2_MCTS import MCTS as M
from agents.sts2_MCTS.MCTS import RolloutPolicy, rollout_policy
from benchmarks.bench import (DEATH_PENALTY, FIGHT_TURN_CAP, RESULTS_DIR, default_workers, fmt, is_won, load_index, load_state,
                              map_jobs, paired_diff)
from sts2_lite import rng
from sts2_lite.card import CardRarity
from sts2_lite.combat import CombatSimulator, CombatState

AGENT_SEED_OFFSET = 1_000_000

GRIDS = {
    "RARITY.Rare": [4, 8, 16, 32], "RARITY.Uncommon": [2, 4, 8], "RARITY.Common": [1, 2, 3, 4],
    "BLOCK_MULT": [0, 1.5, 3, 6, 12], "BLOCK_CAP": [8, 15, 25], "DRAW_FIRST": [1, 2, 4, 8], "VULN_FIRST": [1, 2, 4, 8],
    "ATTACK_BEFORE_VULN": [1, 0.3, 0.1, 0.02], "P_RANDOM_ACTION": [0, 0.02, 0.05, 0.1, 0.2], "POWER_FIRST": [1, 3, 6],
}

def parse_weights(pairs : list[str]) -> dict[str, float]:
    out = {}
    for pair in pairs or []:
        name, _, raw = pair.partition("=")
        if name not in GRIDS:
            raise SystemExit(f"unknown weight {name!r}; choose from {', '.join(GRIDS)}")
        out[name] = float(raw)
    return out

@contextlib.contextmanager
def weights_applied(weights : dict[str, float]):
    saved = []
    try:
        for name, value in weights.items():
            if name.startswith("RARITY."):
                key = CardRarity[name.split(".", 1)[1]]
                saved.append((M.RARITY_WEIGHTS, key, M.RARITY_WEIGHTS[key]))
                M.RARITY_WEIGHTS[key] = value
            else:
                saved.append((vars(M), name, getattr(M, name)))
                setattr(M, name, value)
        yield
    finally:
        for target, key, old in reversed(saved):
            target[key] = old

def play_policy_fight(start : CombatState, policy : RolloutPolicy, seed : int) -> dict:
    """World (draws, enemy rolls) and policy use separate rng streams, as in bench.play_fight."""
    rng.seed(seed);                       world = rng.getstate()
    rng.seed(AGENT_SEED_OFFSET + seed);   agent = rng.getstate()
    sim = CombatSimulator(CombatState.deepcopy(start))
    state = sim.combat_state
    rng.setstate(world)
    state.player.shuffle_draw_pile()
    world = rng.getstate()
    start_hp, start_turn = state.player.current_hp, state.turn_number
    while not sim.is_over and sim.combat_state.turn_number < start_turn + FIGHT_TURN_CAP:
        actions = sim.get_available_actions()
        if not actions:
            break
        rng.setstate(agent)
        action = rollout_policy(sim, actions, policy)
        agent = rng.getstate()
        rng.setstate(world)
        sim.perform_action(action)
        world = rng.getstate()
    state = sim.combat_state
    won = is_won(state)
    hp_lost = start_hp - max(state.player.current_hp, 0)
    return {"won": won, "hp_lost": hp_lost, "score": hp_lost if won else start_hp + DEATH_PENALTY, "finished": sim.is_over}

def _job(job : tuple) -> dict:
    file, seed, policy, weights = job
    with weights_applied(weights):
        return {"file": file, "seed": seed, **play_policy_fight(load_state(file, "act1"), RolloutPolicy[policy], seed)}

def evaluate(policy : str, weights : dict, seeds : int, workers : int, smoke : bool = False) -> list[dict]:
    jobs = [(e["file"], s, policy, weights) for e in load_index(smoke, suite="act1") for s in range(seeds)]
    return map_jobs(_job, jobs, workers, f"{policy} {weights or ''}")

def summary(rows : list[dict]) -> dict:
    return {"win_rate": statistics.fmean(r["won"] for r in rows), "mean_score": statistics.fmean(r["score"] for r in rows),
            "hp_lost_won": statistics.fmean([r["hp_lost"] for r in rows if r["won"]] or [float("nan")]), "unfinished": sum(not r["finished"] for r in rows)}

def sweep(policy : str, seeds : int, workers : int, params : list[str] | None = None) -> list[dict]:
    base = evaluate(policy, {}, seeds, workers)
    table = [{"param": "(defaults)", "value": None, **summary(base), "delta": 0.0, "ci95": 0.0, "significant": False}]
    for name in params or GRIDS:
        for value in GRIDS[name]:
            rows = evaluate(policy, {name: value}, seeds, workers)
            d = paired_diff(base, rows, "score")
            table.append({"param": name, "value": value, **summary(rows), "delta": d["mean"], "ci95": d["ci95"], "significant": d["significant"]})
    return table

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("eval", "sweep"):
        s = sub.add_parser(name)
        s.add_argument("--policy", default="RarityPreference", choices=[x.name for x in RolloutPolicy])
        s.add_argument("--seeds", type=int, default=100)
        s.add_argument("--workers", type=int, default=default_workers())
        s.add_argument("--smoke", action="store_true")
        if name == "eval":
            s.add_argument("--w", action="append", default=[], metavar="NAME=VALUE")
        else:
            s.add_argument("--only", action="append", default=None, metavar="NAME", help="sweep just these weights")
    a = p.parse_args(argv)
    if a.cmd == "eval":
        rows = evaluate(a.policy, parse_weights(a.w), a.seeds, a.workers, a.smoke)
        print(a.policy, a.w, "  ".join(f"{k}={fmt(v)}" for k, v in summary(rows).items()))
    else:
        table = sweep(a.policy, a.seeds, a.workers, a.only)
        RESULTS_DIR.mkdir(exist_ok=True)
        path = RESULTS_DIR / f"sweep_{a.policy}_{a.seeds}seeds.json"
        path.write_text(json.dumps(table, indent=1))
        for r in table:
            flag = "  *" if r["significant"] else ""
            print(f"{r['param']:20s} {str(r['value']):>6s}  win={r['win_rate']:.3f}  score={r['mean_score']:6.2f}  Δ={r['delta']:+.2f}±{r['ci95']:.2f}{flag}")
        print("wrote", path)

if __name__ == "__main__":
    main()
