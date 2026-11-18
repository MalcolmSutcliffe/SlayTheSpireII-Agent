"""Walk-labeled self-play: full runs in which every card reward is rated by the walks, the way the live agent's card chooser rates it, and the ratings logged.

  python -m agents.selfplay.label --out walk0 --runs 500 --pilot mcts:100:big --fights 400 --workers 16

Why: a run's outcome is a very noisy label for one card pick (a run's rooms cleared spread ~11 rooms, a card is worth a fraction of a room). The walks compare
every option on the same walks with the same dice, so their gain over skipping is a paired, low-noise label: what pick_model.py learns from.

A labeled run is a self-play run (run.SelfPlayRun) with two changes:
  - the map is chosen by the live agent's node-score planner (pathing.PathPlanner, without the walks), and its planned route is the route the walks follow;
  - at a card reward the walks rate every card (CardRewardChooser.future_rows, a fixed `fights`), and the pick is the chooser's own take-or-skip rule
    (card_reward_chooser.decide), so the decks are the ones the agent itself would build; with chance `epsilon` the pick is uniform instead (a card or the skip).
Each pick logs, per offered card: its walk gain over skipping (`gain`, without the kind bonus), its standard error (`se`) and the kind bonus (`bonus`); the base
deck's mean walk reward and win rate; the teacher's pick (`teacher`, len(offered) = skip) and the gain it had to beat (`needed`). The log has the same shape as the
suite's (rooms, picks, outcome), so value_model.Rows reads it too.

`--out NAME` writes data/selfplay/NAME/runs.jsonl.gz and meta.json; running it again plays the seeds not done yet."""
from __future__ import annotations
import argparse
import functools
import gzip
import json
import os
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agents.deck_eval.advisor import DeckAdvisor
from agents.deck_eval.cards import RARITY_RANK
from agents.deck_eval.card_reward_chooser import CardRewardChooser, decide, kind_bonus
from agents.deck_eval.config import DEFAULT, DeckEvalConfig
from agents.deck_eval.evaluator import WALK_POLICY
from agents.deck_eval.fight_pool import load_pool
from agents.deck_eval.route_sim import WalkAgent
from agents.pathing import PathPlanner
from agents.selfplay.choosers import card_key
from agents.selfplay.run import SelfPlayAgent, SelfPlayRun, parse_pilot, play_run_guarded, reward_snapshot
from agents.selfplay.suite import OUT_ROOT, ascension_of, parse_ascensions, read_runs, summary
from agents.sts2_MCTS.params import SearchConfig

LABEL_TIMEOUT = 3 * 3600        # seconds: a labeled run rates ~15-25 rewards at several seconds each, on top of its fights


@functools.lru_cache(maxsize=1)
def fight_pool():
    """The deck evaluator's fight pool, loaded once per process."""
    return load_pool()


class LabelAgent(SelfPlayAgent):
    """The self-play agent with the live agent's map planner, and card rewards picked by the walks (with chance `epsilon` uniformly)."""
    def __init__(self, sim : "LabelRun", seed : int, fights : int, epsilon : float, config : DeckEvalConfig = DEFAULT):
        WalkAgent.__init__(self, 1.0, seed)
        self.sim, self.fights, self.epsilon, self.config = sim, fights, epsilon, config
        self.planner = PathPlanner()
        advisor = DeckAdvisor(fights, fight_pool(), route_provider=lambda: self.planner.route, log=lambda *a: None, seed=seed, config=config)
        self.chooser = CardRewardChooser(fights=fights, advisor=advisor)
        self.explore = random.Random(f"{seed}/label-explore")

    def _get_map_decision(self, decision):
        return self.planner.choose(decision)

    def _get_card_reward_decision(self, decision):
        options = [o for o in decision.options if "id" in (o.data or {})]
        skip = next((o for o in decision.options if o.action.get("action") == "skip_card_reward"), None)
        if not options:
            return skip or decision.options[0]
        snap = reward_snapshot(self.sim)
        player = decision.player
        deck = player.get("deck") or []
        start = time.perf_counter()
        try:
            future = self.chooser.future_rows(decision, deck, player, self.planner.route, skip, self.fights)
        except Exception as error:          # the engine failed in a walk (outside a fight's actions, which the walks catch): the screen goes unlabeled, the run goes on
            index = max(range(len(options)), key=lambda i: RARITY_RANK.get(options[i].data.get("rarity"), 0))
            chosen = card_key(options[index].data)
            self.sim.picks.append({"act": snap["act"], "floor": snap["floor"], "offered": [card_key(o.data) for o in options], "chosen": chosen, "exploratory": False,
                                   "labels": None, "error": f"{type(error).__name__}: {error}"[:300], "room": len(self.sim.rooms), "snap": snap,
                                   "after": dict(snap, deck=snap["deck"] + [chosen])})
            return options[index]
        rows, base = future["rows"], future["base"]
        early = len(self.sim.picks) < self.config.early_rewards
        best, take, needed = decide(rows, base.win_rate, early, self.config)
        teacher = next(i for i, o in enumerate(options) if o is best[2]) if take else len(options)
        index = teacher
        if self.explore.random() < self.epsilon:
            index = self.explore.randrange(len(options) + 1)
        cards = []
        for (gain, se, opt, _, score), o in zip(rows, options):
            bonus = kind_bonus(o.data, deck, self.config)
            cards.append({"key": card_key(o.data), "type": o.data.get("type"), "rarity": o.data.get("rarity"), "gain": round(gain - bonus, 5), "se": round(se, 5),
                          "bonus": round(bonus, 5), "win_rate": round(score.win_rate, 4)})
        chosen = "SKIP" if index == len(options) else card_key(options[index].data)
        record = {"act": snap["act"], "floor": snap["floor"], "offered": [c["key"] for c in cards], "chosen": chosen, "exploratory": index != teacher,
                  "teacher": teacher, "needed": round(needed, 5), "early": early, "labels": cards, "base": round(base.mean, 4), "base_win_rate": round(base.win_rate, 4),
                  "walks": future["walks"], "fights": len(future["fights"]), "seconds": round(time.perf_counter() - start, 2),
                  "route": list(self.planner.route.kinds) if self.planner.route else None, "room": len(self.sim.rooms), "snap": snap}
        record["after"] = snap if index == len(options) else dict(snap, deck=snap["deck"] + [chosen])
        self.sim.picks.append(record)
        return (skip or options[0]) if index == len(options) else options[index]


class LabelRun(SelfPlayRun):
    """A self-play run with the LabelAgent; the elites it fights are told to the planner (the walks draw the next elite from what the game's bag has left)."""
    def __init__(self, seed : int, config, ascension : int = 0, pilot="rollout", fights : int = 400, epsilon : float = 0.1, scoring : DeckEvalConfig = DEFAULT):
        super().__init__(seed, config, None, ascension, scoring=scoring, pilot=pilot)
        self.agent = LabelAgent(self, seed, fights, epsilon, scoring)

    def fight(self, encounter, room : str, *args, **kwargs) -> bool:
        if room == "Elite":
            self.agent.planner.note_elite(encounter.id)
        return super().fight(encounter, room, *args, **kwargs)


def play_labeled_run(seed : int, ascension : int = 0, pilot="rollout", fights : int = 400, epsilon : float = 0.1) -> dict:
    """The labeled run with this `seed` (the same settings play the same run): {seed, ascension, pilot, labeled, rooms, picks, outcome}."""
    pilot = parse_pilot(pilot)
    sim = LabelRun(seed, SearchConfig().tuned(rollout=WALK_POLICY), ascension, pilot, fights, epsilon)
    outcome = sim.play_run()
    return {"seed": seed, "ascension": ascension, "pilot": pilot.name, "labeled": True, "rooms": sim.rooms, "picks": sim.picks, "outcome": outcome}


def job(args) -> dict:
    seed, levels, pilot, fights, epsilon, timeout = args
    return play_run_guarded(seed, timeout=timeout, play=play_labeled_run, ascension=ascension_of(seed, levels), pilot=pilot, fights=fights, epsilon=epsilon)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, help="the folder name under data/selfplay")
    p.add_argument("--runs", type=int, default=200)
    p.add_argument("--start-seed", type=int, default=1)
    p.add_argument("--pilot", default="mcts:100:big", help="who fights: rollout | mcts:N | mcts:N:big")
    p.add_argument("--fights", type=int, default=400, help="fights each card reward is rated on (the live chooser plays 400 to a few thousand in its time budget)")
    p.add_argument("--epsilon", type=float, default=0.1, help="chance a pick is uniform among the cards and the skip instead of the walks' pick")
    p.add_argument("--ascensions", default="0")
    p.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    p.add_argument("--run-timeout", type=int, default=LABEL_TIMEOUT)
    args = p.parse_args(argv)
    args.pilot = parse_pilot(args.pilot).name

    out = OUT_ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    log = out / "runs.jsonl.gz"
    meta = {"labeled": True, **{k: getattr(args, k) for k in ("pilot", "fights", "epsilon", "ascensions")}}
    meta_file = out / "meta.json"
    if meta_file.exists() and json.loads(meta_file.read_text()) != meta:
        print(f"{meta_file} has other settings ({meta_file.read_text().strip()}): use another --out, or the same settings", file=sys.stderr)
        return 1
    meta_file.write_text(json.dumps(meta))
    levels = parse_ascensions(args.ascensions)
    done = {r["seed"] for r in read_runs(log)}
    todo = [s for s in range(args.start_seed, args.start_seed + args.runs) if s not in done]
    print(f"{out}: {len(done)} runs already labeled, {len(todo)} to play, {args.workers} workers", flush=True)
    start, last, screens = time.perf_counter(), time.perf_counter(), 0
    with Pool(args.workers) as pool:
        jobs = [(s, levels, args.pilot, args.fights, args.epsilon, args.run_timeout) for s in todo]
        for i, run in enumerate(pool.imap_unordered(job, jobs), 1):
            with gzip.open(log, "at", encoding="utf-8") as f:
                f.write(json.dumps(run, separators=(",", ":")) + "\n")
            screens += len(run["picks"])
            if time.perf_counter() - last > 60 or i == len(todo):
                last = time.perf_counter()
                rate = i / (last - start)
                print(f"{len(done) + i}/{len(done) + len(todo)} runs, {screens} screens labeled  {rate * 3600:.0f} runs/h  ~{(len(todo) - i) / rate / 3600:.1f} h left", flush=True)
    print(summary(list(read_runs(log))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
