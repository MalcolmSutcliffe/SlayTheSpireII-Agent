"""Sweep of random decks against random fights, each played by the MCTS and by the walk's policy: the data a deck model (agents/deck_eval/deck_model.py) is fitted on.

A case is one fight (an encounter of the engine's pools, drawn by kind and act) and one deck (the Ironclad's starter deck plus random cards, as many as an act's deck holds) with some HP.
The MCTS plays it once and the walk's rollout policy REPS times, from the same opening. A row of the data file holds the deck, the fight and both outcomes. The cost of a fight is the
share of its starting HP it took (a lost fight costs all of it): `mcts_cost`, `policy_cost` (the mean of the reps) and their difference `residual` = policy - mcts, which is
what the MCTS knows that the walk's policy does not and what the card chooser needs the model for (the walks already see the rest).

Usage (from scripts/):
  python -m benchmarks.deck_sweep run --cases 400 --seed 1 --time-budget 0.1 --reps 3 --workers 2 [--file name]   # appends rows to benchmarks/results/deck_sweep_<name>.jsonl, stops and resumes at any time
  python -m benchmarks.deck_sweep fit benchmarks/results/deck_sweep_a.jsonl [--target residual|mcts|policy] [--lam-base 4 --lam-pair 40] [--holdout 0.25] [--save model.json]
  python -m benchmarks.deck_sweep show benchmarks/results/deck_sweep_a.jsonl                                         # what the data holds

Cards are drawn uniformly from the reward pool (`--odds`: by the reward rarity odds instead) so every card and pair is seen. Decks are not upgraded and hold no relics but Burning Blood."""
from __future__ import annotations
import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmarks.bench import SEARCH_SEED_OFFSET, map_jobs, play_fight

RESULTS_DIR = Path(__file__).resolve().parent / "results"
MAX_HP = 80
CARDS_BY_ACT = {1: (2, 9), 2: (7, 15), 3: (11, 22)}        # card rewards a deck holds when it meets an act's fights
KIND_WEIGHTS = {"weak": 2, "normal": 3, "elite": 2, "boss": 1}
ACT_WEIGHTS = {1: 4, 2: 3, 3: 3}
ACT_MAX_HP = {1: 80, 2: 88, 3: 96}                          # what a run's max HP has grown to
UPGRADED = {1: 0.1, 2: 0.35, 3: 0.55}                       # the share of a deck's cards that are upgraded (the model does not see it: it is noise it has to live with)
CHUNK = 24                                                  # cases played between writes to the data file


def make_case(seed : int, i : int, odds : bool = False) -> dict:
    """The case i of the sweep: the same for every player. Returns the deck (card dicts), the fight template, the player's HP."""
    from agents.deck_eval.fight_pool import load_pool, instance
    from agents.deck_eval.future_cards import extra_cards, CARD_POOL
    from sts2_lite.run import new_run
    r = random.Random(seed * 100003 + i)
    act = r.choices(list(ACT_WEIGHTS), list(ACT_WEIGHTS.values()))[0]
    kind = r.choices(list(KIND_WEIGHTS), list(KIND_WEIGHTS.values()))[0]
    pool = [t for t in load_pool() if t.act == act and t.kind == kind]
    template = instance(r.choice(pool), 0, r)
    run = new_run()
    n = r.randint(*CARDS_BY_ACT[act])
    if odds:
        extra = extra_cards(n, r)
    else:
        every = [c for cards in CARD_POOL.values() for c in cards]
        extra = [dict(r.choice(every)) for _ in range(n)]
    max_hp = ACT_MAX_HP[act]
    hp = r.randint(int(0.6 * max_hp), max_hp)
    deck = [dict(c, _upgrade=True) if r.random() < UPGRADED[act] else c for c in run.deck + extra]
    return {"deck": deck, "relics": run.relics, "template": template, "hp": hp, "max_hp": max_hp, "act": act, "kind": kind}


def play_policy(start, seed : int):
    """The walk's rollout policy on a copy of the opening: (won, hp lost)."""
    from sts2_lite import rng
    from sts2_lite.combat import CombatSimulator, CombatState
    from agents.sts2_MCTS.params import SearchConfig
    from agents.deck_eval.playout import play_out
    from agents.sts2_MCTS.outcome_score import is_win
    cfg = SearchConfig()
    sim = CombatSimulator(CombatState.deepcopy(start))
    cs = sim.combat_state
    rng.seed(seed)
    hp = cs.player.current_hp
    play_out(sim, cfg, 25)
    won = is_win(cs)
    return won, hp - max(0, cs.player.current_hp)


def cost(won : bool, hp_lost : float, hp : float) -> float:
    """A fight's cost as a share of its starting HP: all of it for a lost fight."""
    return 1.0 if not won else max(0.0, min(1.0, hp_lost / hp))


def case_job(job) -> dict:
    seed, i, budget, reps, odds = job
    from agents.deck_eval.fight_builder import build_fight
    from agents.deck_eval.fight_pool import target_types
    from agents.sts2_MCTS.params import SearchConfig
    case = make_case(seed, i, odds)
    player = {"hp": case["hp"], "max_hp": case["max_hp"], "relics": case["relics"], "gold": 0}
    start = build_fight(case["template"], case["deck"], player, target_types()).combat_state
    clock = time.perf_counter()
    out = play_fight(start, SearchConfig(time_budget=budget), seed * 1000 + i, SEARCH_SEED_OFFSET + seed * 1000 + i)
    mcts_seconds = time.perf_counter() - clock
    mcts = cost(out["won"], out["hp_lost"], case["hp"])
    policy = [cost(*play_policy(start, seed * 7919 + i * 31 + rep), case["hp"]) for rep in range(reps)]
    return {"seed": seed, "i": i, "act": case["act"], "kind": case["kind"], "enemy": case["template"].name, "hp": case["hp"], "max_hp": case["max_hp"],
            "deck": [c["id"] for c in case["deck"]], "relics": [r.get("id") for r in case["relics"]],
            "mcts_won": out["won"], "mcts_cost": mcts, "policy_costs": policy, "policy_cost": statistics.fmean(policy), "residual": statistics.fmean(policy) - mcts,
            "turns": out["turns"], "mcts_seconds": round(mcts_seconds, 1)}


def load(paths) -> list[dict]:
    rows = []
    for p in paths:
        rows += [json.loads(l) for l in open(p) if l.strip()]
    return rows


def run(args):
    path = RESULTS_DIR / ("deck_sweep_%s.jsonl" % (args.file or "s%d_b%s" % (args.seed, args.time_budget)))
    path.parent.mkdir(exist_ok=True)
    done = {(r["seed"], r["i"]) for r in load([path])} if path.exists() else set()
    todo = [(args.seed, i, args.time_budget, args.reps, args.odds) for i in range(args.first, args.first + args.cases) if (args.seed, i) not in done]
    print("%d cases to play, %d done: %s" % (len(todo), len(done), path))
    for start in range(0, len(todo), CHUNK):
        rows = map_jobs(case_job, todo[start:start + CHUNK], args.workers, "cases %d-%d" % (start, min(len(todo), start + CHUNK)))
        with open(path, "a") as f:
            for r in sorted(rows, key=lambda r: r["i"]):
                f.write(json.dumps(r) + "\n")
    print("wrote", path)


def show(args):
    rows = load(args.files)
    print("%d fights" % len(rows))
    for kind in ("weak", "normal", "elite", "boss"):
        part = [r for r in rows if r["kind"] == kind]
        if part:
            print("%-7s n=%4d  mcts cost %.3f  policy cost %.3f  residual %+.3f  mcts won %3.0f%%  %.1fs/fight" % (kind, len(part), statistics.fmean(r["mcts_cost"] for r in part),
                  statistics.fmean(r["policy_cost"] for r in part), statistics.fmean(r["residual"] for r in part), 100 * statistics.fmean(r["mcts_won"] for r in part), statistics.fmean(r["mcts_seconds"] for r in part)))
    cards = {c for r in rows for c in r["deck"]}
    print("%d different cards seen" % len(cards))


def split(rows : list[dict], holdout : float, seed : int = 0) -> tuple[list[dict], list[dict]]:
    r = random.Random(seed)
    rows = sorted(rows, key=lambda x: (x["seed"], x["i"]))
    test_ids = set(r.sample(range(len(rows)), int(holdout * len(rows))))
    return [x for k, x in enumerate(rows) if k not in test_ids], [x for k, x in enumerate(rows) if k in test_ids]


def inputs(rows):
    return [([{"id": c} for c in r["deck"]], r["relics"], r["kind"], r["hp"] / r["max_hp"]) for r in rows]


def fit(args):
    import numpy as np
    from agents.deck_eval.deck_model import PairRegression
    rows = load(args.files)
    train, test = split(rows, args.holdout)
    y = lambda r: r["residual"] if args.target == "residual" else r["mcts_cost"] if args.target == "mcts" else r["policy_cost"]
    model = PairRegression(args.lam_base, args.lam_pair).fit(inputs(train), [y(r) for r in train])
    print("%d fights: %d to fit, %d held out; %d cards, %d pairs seen" % (len(rows), len(train), len(test), len(model.cards), len(model.pairs)))
    def mse(pairs): return statistics.fmean((a - b) ** 2 for a, b in pairs)
    pred = [model.predict(*x) for x in inputs(test)]
    truth = [y(r) for r in test]
    mean = statistics.fmean(y(r) for r in train)
    print("target %s on held-out fights: MSE %.4f (predicting the training mean: %.4f), correlation %.2f" % (args.target, mse(zip(pred, truth)), mse((mean, t) for t in truth), float(np.corrcoef(pred, truth)[0, 1])))
    if args.target == "residual":
        mcts = [r["mcts_cost"] for r in test]
        raw = [r["policy_cost"] for r in test]
        corrected = [r["policy_cost"] - p for r, p in zip(test, pred)]
        print("predicting the MCTS's cost of a fight: policy alone MSE %.4f | policy minus the model MSE %.4f | rank correlation policy %.2f, with model %.2f" % (
              mse(zip(raw, mcts)), mse(zip(corrected, mcts)), spearman(raw, mcts), spearman(corrected, mcts)))
    print(model.card_table())
    if args.save:
        model.save(Path(args.save))
        print("saved", args.save)


def spearman(a, b) -> float:
    """Rank correlation (ties get their average rank)."""
    import numpy as np
    def ranks(v):
        v = np.asarray(v, float)
        order = np.argsort(v, kind="stable")
        r = np.empty(len(v))
        r[order] = np.arange(len(v))
        for value in np.unique(v):                  # ties: the mean of their ranks
            mask = v == value
            r[mask] = r[mask].mean()
        return r
    return float(np.corrcoef(ranks(a), ranks(b))[0, 1])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--cases", type=int, default=100)
    r.add_argument("--first", type=int, default=0)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--time-budget", type=float, default=0.1)
    r.add_argument("--reps", type=int, default=3)
    r.add_argument("--workers", type=int, default=1)
    r.add_argument("--file", default=None)
    r.add_argument("--odds", action="store_true", help="draw the deck's cards by the reward rarity odds instead of uniformly")
    s = sub.add_parser("show")
    s.add_argument("files", nargs="+", type=Path)
    f = sub.add_parser("fit")
    f.add_argument("files", nargs="+", type=Path)
    f.add_argument("--target", choices=("residual", "mcts", "policy"), default="residual")
    f.add_argument("--lam-base", type=float, default=4.0)
    f.add_argument("--lam-pair", type=float, default=40.0)
    f.add_argument("--holdout", type=float, default=0.25)
    f.add_argument("--save", default=None)
    args = p.parse_args(argv)
    {"run": run, "show": show, "fit": fit}[args.cmd](args)


if __name__ == "__main__":
    main()
