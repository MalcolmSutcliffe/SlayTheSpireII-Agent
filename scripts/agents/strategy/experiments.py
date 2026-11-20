"""Paired fight experiments: what one card does to a fight the MCTS plays.

  python -m agents.strategy.experiments --from fights_m400 --out exp_m100 --n 20000 --sims 100 --reps 2 --workers 15

Self-play logs show which decks did well, but not why: a deck's cards go with where the run is (later decks have more cards and meet harder fights), so a
model fitted on them learns those links, not what a card does. Here the card is assigned at random instead. Each experiment takes a fight from the self-play logs
(the run going into it and the encounter: `--from`), changes the deck by one card, and plays the fight with the MCTS twice per rep: with the deck as it was
(`base`) and with the change (`alt`), on the same seed (the same monsters and their moves; the MCTS's own draws seeded alike). The draw pile is shuffled in an
aligned order (Player.aligned_shuffle): the cards both decks hold come in the same order, the added card slotted in among them, so the two fights start from
the same hands and part only where the card shows up (with a random shuffle, one card more reshuffles everything and the pair is little better than two fights). The change is
  add      a card of the Ironclad's reward pool, every card as likely (so a rare card is seen as often as a common one), upgraded with chance UPGRADE_SHARE;
  remove   a card of the deck, each as likely (what a removal is worth: Strikes, Defends, curses).
A fight's result is its `cost` in HP (fight_model.cost: all the HP it began with when it is lost), so `alt cost - base cost` is the change's effect on this fight.

The reps of an experiment are independent replays (other seeds): how well one rep's effect predicts the other's is how much of an effect a fight shows
over its own luck (effect_model.py reports it). The run going into a fight is rebuilt from the log's snapshot: card, relic and potion ids, HP, act, ascension
(a relic's counters are not in the snapshot, so they start fresh).

Results go to data/selfplay/experiments/NAME.jsonl.gz as each experiment finishes; running the same command again plays only the experiments not done yet
(and plays again the ones that failed)."""
from __future__ import annotations
import argparse
import gzip
import json
import os
import random
import sys
import time
import zlib
from multiprocessing import Pool
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sts2_lite.campaign.combat import start_fight
from sts2_lite.card.constants import QUEST_CARDS
from sts2_lite.event.run import card_entry, placeholder_entry
from sts2_lite.run import RunState
from sts2_lite.run.streams import GameRng

from agents.deck_eval.config import DEFAULT
from agents.deck_eval.future_cards import CARD_POOL
from agents.selfplay.choosers import base_id
from agents.selfplay.run import Pilot, mcts_fight
from agents.sts2_MCTS import outcome_score
from agents.strategy.fight_model import fight_rows

ADD_SHARE = 0.7             # the rest of the experiments remove a card
UPGRADE_SHARE = 0.2         # an added card is upgraded this often
REWARD_POOL = sorted({c["id"] for cards in CARD_POOL.values() for c in cards})


def deck_entry(key : str) -> dict:
    """A deck entry from a card key; a card the engine has no model for (a quest card: Spoils Map, Dowsing, ...) is a placeholder, a dead card in a fight, as in a run."""
    try:
        return card_entry(base_id(key), key.endswith("+"))
    except KeyError:
        cid = base_id(key)
        return placeholder_entry(cid, None, "Quest" if cid in QUEST_CARDS else "Skill")


def run_of(before : dict, deck_keys : list[str]) -> RunState:
    """The run going into a fight, from a self-play snapshot, with `deck_keys` as its deck."""
    deck = [deck_entry(k) for k in deck_keys]
    player = {"hp": before["hp"], "max_hp": before["max_hp"], "gold": before.get("gold", 0), "relics": [{"id": r} for r in before["relics"]],
              "potions": [{"id": p} for p in before["potions"]]}
    return RunState.from_player(player, deck, act=before.get("act", 1), floor=before.get("floor", 1), ascension=before.get("ascension") or 0)


def play(before : dict, deck_keys : list[str], encounter : str, kind : str, seed : int, sims : int, label : str, aligned : bool = True) -> dict:
    """The fight with this deck, played by the MCTS at `sims` simulations: {won, hp_after, turns, progress, cost}. `aligned`: the draw pile is shuffled in the
    aligned order (Player.aligned_shuffle, seeded by `seed`), so the decks of an experiment draw their common cards in the same order."""
    run = run_of(before, deck_keys)
    game = GameRng(seed)
    sim = start_fight(run, encounter, kind.lower(), game, final_fight=kind == "Boss" and run.act == 3, aligned_shuffle=seed if aligned else None)
    cs = sim.combat_state
    expected, hp0 = outcome_score.expected_total_hp(cs), cs.player.current_hp
    mcts_fight(sim, Pilot(sims).search_config(), label, DEFAULT.max_turns, lambda: game.scope("combat"))
    won = outcome_score.is_win(cs)
    hp = max(0, cs.player.current_hp)
    return {"won": won, "hp_after": hp, "turns": cs.turn_number, "progress": None if won else round(max(0.0, 1.0 - outcome_score.enemy_progress_left(cs, expected)), 4),
            "cost": float(hp0 - hp) if won else float(hp0)}


def design(states : list[dict], n : int, seed : int) -> list[dict]:
    """`n` experiments over `states` (the same seed gives the same list, so a stopped batch resumes where it was)."""
    r = random.Random(seed)
    out = []
    for i in range(n):
        s = r.choice(states)
        deck = s["before"]["deck"]
        if r.random() < ADD_SHARE or not deck:
            card = r.choice(REWARD_POOL) + ("+" if r.random() < UPGRADE_SHARE else "")
            change = {"op": "add", "card": card}
        else:
            change = {"op": "remove", "card": deck[r.randrange(len(deck))]}
        out.append({"i": i, "source": s["source"], "encounter": s["encounter"], "kind": s["kind"], "before": s["before"], "change": change})
    return out


def apply(deck : list[str], change : dict) -> list[str]:
    if change["op"] == "add":
        return deck + [change["card"]]
    out = list(deck)
    out.remove(change["card"])
    return out


def job(args) -> dict:
    exp, reps, sims, aligned = args if len(args) == 4 else (*args, True)
    base_deck = exp["before"]["deck"]
    alt_deck = apply(base_deck, exp["change"])
    results = []
    for rep in range(reps):
        seed = zlib.crc32(f"{exp['source']}/{exp['i']}/{rep}".encode())
        label = f"exp/{exp['i']}/{rep}"
        try:
            base = play(exp["before"], base_deck, exp["encounter"], exp["kind"], seed, sims, label, aligned)
            alt = play(exp["before"], alt_deck, exp["encounter"], exp["kind"], seed, sims, label, aligned)
        except Exception as error:          # the engine failed (or could not rebuild the run): the experiment is logged as failed
            return dict(exp, sims=sims, aligned=aligned, reps=[], error=f"{type(error).__name__}: {error}"[:300])
        results.append({"seed": seed, "base": base, "alt": alt})
    return dict(exp, sims=sims, aligned=aligned, reps=results)


def source_states(folders : list[str], kinds=("Monster", "Elite", "Boss")) -> list[dict]:
    """The fights of self-play logs an experiment can start from: every fight of `kinds` the engine did not fail in, whoever played it."""
    from agents.selfplay.fit import load_runs
    out = []
    for f in fight_rows(load_runs(folders), mcts_only=False):
        if f["kind"] not in kinds:
            continue
        out.append({"source": f"{f['seed']}/{f.get('room_index')}/{f['encounter']}", "encounter": f["encounter"], "kind": f["kind"], "before": f["before"]})
    return out


def read(path : Path):
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def main(argv=None):
    from agents.selfplay.suite import OUT_ROOT
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from", dest="sources", required=True, help="comma separated folders of data/selfplay whose fight logs give the fights to start from")
    p.add_argument("--out", required=True, help="results file data/selfplay/experiments/NAME.jsonl.gz")
    p.add_argument("--n", type=int, default=10000, help="experiments in all")
    p.add_argument("--sims", type=int, default=100, help="MCTS simulations per decision")
    p.add_argument("--reps", type=int, default=2, help="independent replays of each experiment (each plays the fight with and without the change)")
    p.add_argument("--seed", type=int, default=0, help="seeds the design (which fights, which changes)")
    p.add_argument("--kinds", default="Monster,Elite,Boss", help="the kinds of fight to start from (comma separated)")
    p.add_argument("--unaligned", action="store_true", help="shuffle at random instead of in the aligned order (Player.aligned_shuffle)")
    p.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = p.parse_args(argv)

    path = OUT_ROOT / "experiments" / f"{args.out}.jsonl.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta_file = path.with_suffix("").with_suffix(".meta.json")
    meta = {"from": args.sources, "sims": args.sims, "reps": args.reps, "seed": args.seed, "kinds": args.kinds, "aligned": not args.unaligned}
    if meta_file.exists() and {"kinds": "Monster,Elite,Boss", "aligned": False, **json.loads(meta_file.read_text())} != meta:          # files from before these settings
        print(f"{meta_file} has other settings ({meta_file.read_text().strip()}): use another --out, or the same settings", file=sys.stderr)
        return 1
    states = source_states(args.sources.split(","), tuple(args.kinds.split(",")))
    if not states:
        print("no fights to start from in those logs", file=sys.stderr)
        return 1
    meta_file.write_text(json.dumps(meta))
    done = {e["i"] for e in read(path) if not e.get("error")}          # a failed experiment is played again (effect_model reads the ones that played)
    todo = [e for e in design(states, args.n, args.seed) if e["i"] not in done]
    print(f"{path}: {len(states)} fights to start from, {len(done)} experiments done, {len(todo)} to play ({args.reps} reps x 2 fights at {args.sims} sims), {args.workers} workers", flush=True)
    start, last, failed = time.perf_counter(), time.perf_counter(), 0
    with Pool(args.workers) as pool:
        for k, exp in enumerate(pool.imap_unordered(job, [(e, args.reps, args.sims, not args.unaligned) for e in todo], chunksize=1), 1):
            with gzip.open(path, "at", encoding="utf-8") as f:
                f.write(json.dumps(exp, separators=(",", ":")) + "\n")
            failed += bool(exp.get("error"))
            if time.perf_counter() - last > 60 or k == len(todo):
                last = time.perf_counter()
                rate = k / (last - start)
                print(f"{len(done) + k}/{len(done) + len(todo)} experiments ({failed} failed)  {rate * 3600:.0f}/h  ~{(len(todo) - k) / rate / 3600:.1f} h left", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
