"""Synergy experiments: does card A make card B worth more to the MCTS? A factorial design on logged fights.

  python -m agents.strategy.synergy --from fights_m400 --out syn_m100 --sources 600 [--blocks "BARRICADE:BODY_SLAM,SHRUG_IT_OFF,IRON_WAVE,~POMMEL_STRIKE;..."]
  python -m agents.strategy.synergy --report syn_m100

Random deck variants (variants.py) almost never put a card next to the one it combos with, so they cannot show synergy. Here each block is an anchor card A
and partners B1..Bk; each source fight (an elite or boss fight from self-play whose deck holds none of the block's cards) is played with every cell of
{the deck, the deck + A} x {nothing, + B1, ..., + Bk}, all on the same game seed (variants.job: the same monsters and dice). B's interaction with A in that fight:
    (cost[A + B] - cost[A]) - (cost[B] - cost[deck])        (HP of the fight's cost; negative: A makes B better)
and its mean over the sources is the synergy, with a standard error from their spread. The cells without A or B are shared by all of a block's partners, so a
block of k partners costs 2(k + 1) fights per source instead of 4k. A partner written ~B is a control: one not expected to interact, so the report shows how
big an interaction noise alone makes. Rows are variant rows (source, base_deck, changes), so card_model and fight_model can read them too.

One cell's cost varies by ~9-10 HP over replays, so an interaction is good to about 2 * 9.7 / sqrt(sources) HP: 600 sources, ~0.8."""
from __future__ import annotations
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from agents.selfplay.choosers import base_id
from agents.strategy.experiments import REWARD_POOL, read, source_states
from agents.strategy.fight_model import cost

BASICS = {"STRIKE_IRONCLAD", "DEFEND_IRONCLAD"}         # partners that may be in the deck already (every deck holds them): "one more plain card"

BLOCKS = ("BARRICADE:BODY_SLAM,SHRUG_IT_OFF,IRON_WAVE,~POMMEL_STRIKE;"
          "FEEL_NO_PAIN:BURNING_PACT,TRUE_GRIT,SECOND_WIND,~TWIN_STRIKE;"
          "INFLAME:SWORD_BOOMERANG,TWIN_STRIKE,WHIRLWIND,~SHRUG_IT_OFF;"
          "JUGGERNAUT:SHRUG_IT_OFF,IMPERVIOUS,FLAME_BARRIER,~POMMEL_STRIKE;"
          "RUPTURE:BLOODLETTING,OFFERING,HEMOKINESIS,~SHRUG_IT_OFF;"
          "DARK_EMBRACE:BURNING_PACT,TRUE_GRIT,SECOND_WIND,~POMMEL_STRIKE")


def parse_blocks(text : str) -> list[dict]:
    """"A:B1,B2,~C;..." -> [{anchor, partners, controls}] (a ~ marks a control partner)."""
    out = []
    for part in filter(None, (p.strip() for p in text.split(";"))):
        anchor, rest = part.split(":")
        partners = [b.strip() for b in rest.split(",") if b.strip()]
        out.append({"anchor": anchor.strip(), "partners": [b.lstrip("~") for b in partners], "controls": [b.lstrip("~") for b in partners if b.startswith("~")]})
    for b in out:
        for card in [b["anchor"]] + b["partners"]:
            if card not in REWARD_POOL and card not in BASICS:
                raise ValueError(f"{card} is not in the reward pool")
    return out


def cells(block : dict) -> list[tuple[str | None, str | None]]:
    """(a, b) for every cell: a the anchor or None, b a partner or None."""
    return [(a, b) for a in (None, block["anchor"]) for b in [None] + block["partners"]]


def design(states : list[dict], blocks : list[dict], n_sources : int, seed : int, reps : int = 1) -> list[dict]:
    """Every cell of every block on `n_sources` source fights each (fights whose deck holds none of the block's cards but BASICS; drawn without replacement
    while they last), each cell played `reps` times (a unit per rep: unit "block/source/rep"). The same seed gives the same list; `i` numbers the fights."""
    r = random.Random(seed)
    out = []
    for k, block in enumerate(blocks):
        cards = {block["anchor"], *block["partners"]} - BASICS
        ok = [s for s in states if not any(base_id(c) in cards for c in s["before"]["deck"])]
        picks = r.sample(ok, min(n_sources, len(ok))) + [r.choice(ok) for _ in range(max(0, n_sources - len(ok)))]
        for j, s in enumerate(picks):
          for rep in range(reps):
            for a, b in cells(block):
                added = [c for c in (a, b) if c]
                out.append({"i": len(out), "block": k, "anchor": block["anchor"], "unit": f"{k}/{j}" + (f"/{rep}" if reps > 1 else ""), "a": a, "b": b, "source": s["source"], "encounter": s["encounter"],
                            "kind": s["kind"], "before": s["before"], "deck": s["before"]["deck"] + added, "changes": [{"op": "add", "card": c} for c in added]})
    return out


def job(args) -> dict:
    from agents.strategy.variants import job as play_variant
    v, sims = args
    return dict(play_variant((v, sims)), block=v["block"], anchor=v["anchor"], unit=v["unit"], a=v["a"], b=v["b"])


def interactions(rows : list[dict]) -> dict[tuple[str, str], dict]:
    """{(anchor, partner): {n, effect, se, main_a, main_b, by_kind}} from complete units (a source fight of a block with every cell played)."""
    units = defaultdict(dict)
    for r in rows:
        if not r.get("error") and "won" in r:
            units[(r["anchor"], r["unit"])][(r["a"], r["b"])] = r
    out = defaultdict(lambda: {"d": [], "a": [], "b": [], "kind": []})
    for (anchor, _), cell in units.items():
        base, with_a = cell.get((None, None)), cell.get((anchor, None))
        if base is None or with_a is None:
            continue
        for (a, b), r in cell.items():
            if a is None or b is None or (None, b) not in cell:
                continue
            c0, ca, cb, cab = cost(base), cost(with_a), cost(cell[(None, b)]), cost(r)
            o = out[(anchor, b)]
            o["d"].append((cab - ca) - (cb - c0)); o["a"].append(ca - c0); o["b"].append(cb - c0); o["kind"].append(base["kind"])
    res = {}
    for key, o in out.items():
        d = np.array(o["d"])
        se = lambda x: float(np.std(x, ddof=1) / np.sqrt(len(x))) if len(x) > 1 else float("nan")
        kinds = np.array(o["kind"])
        res[key] = {"n": len(d), "effect": float(d.mean()), "se": se(d), "main_a": float(np.mean(o["a"])), "main_b": float(np.mean(o["b"])),
                    "by_kind": {k: (float(d[kinds == k].mean()), se(d[kinds == k]), int((kinds == k).sum())) for k in ("Elite", "Boss") if (kinds == k).any()}}
    return res


def report(rows : list[dict], blocks : list[dict] | None = None):
    res = interactions(rows)
    controls = {(b["anchor"], c) for b in blocks for c in b["controls"]} if blocks else set()
    print("synergy: B's value with A in the deck less without it (HP of the fight's cost; negative: A makes B better)")
    print(f"  {'A':14s} {'B':16s} {'n':>5s} {'interaction':>16s}   {'z':>5s}  | {'+A':>6s} {'+B':>6s} | {'elite':>14s} {'boss':>14s}")
    for (a, b), o in sorted(res.items()):
        kinds = "".join(f"  {o['by_kind'][k][0]:+6.2f} ± {o['by_kind'][k][1]:4.2f}" if k in o["by_kind"] else "%16s" % "-" for k in ("Elite", "Boss"))
        mark = "  (control)" if (a, b) in controls else ""
        print(f"  {a:14s} {b:16s} {o['n']:5d} {o['effect']:+7.2f} ± {o['se']:5.2f}   {o['effect'] / o['se']:+5.1f}  | {o['main_a']:+6.2f} {o['main_b']:+6.2f} |{kinds}{mark}")
    ctl = [res[k]["effect"] / res[k]["se"] for k in controls if k in res and res[k]["se"] > 0]
    if ctl:
        print(f"  controls: z from {min(ctl):+.1f} to {max(ctl):+.1f} (|z| should mostly be under 2 if the noise is as estimated)")


def main(argv=None):
    from agents.selfplay.suite import OUT_ROOT
    from agents.strategy.variants import play_all
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from", dest="sources_from", default="fights_m400", help="comma separated folders of data/selfplay whose fight logs give the fights")
    p.add_argument("--out", help="results file data/selfplay/synergy/NAME.jsonl.gz")
    p.add_argument("--report", help="report on data/selfplay/synergy/NAME.jsonl.gz and stop")
    p.add_argument("--blocks", default=BLOCKS)
    p.add_argument("--sources", type=int, default=600, help="source fights per block")
    p.add_argument("--sims", type=int, default=100)
    p.add_argument("--kinds", default="Elite,Boss")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--reps", type=int, default=1, help="plays of each cell of each source fight (each its own unit)")
    p.add_argument("--workers", type=int, default=15)
    args = p.parse_args(argv)

    name = args.report or args.out
    if not name:
        p.error("--out or --report")
    path = OUT_ROOT / "synergy" / f"{name}.jsonl.gz"
    meta_file = path.with_suffix("").with_suffix(".meta.json")
    if args.report:
        meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
        report(list(read(path)), parse_blocks(meta.get("blocks", args.blocks)))
        return 0
    blocks = parse_blocks(args.blocks)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"from": args.sources_from, "blocks": args.blocks, "sources": args.sources, "sims": args.sims, "kinds": args.kinds, "seed": args.seed, **({"reps": args.reps} if args.reps > 1 else {})}
    if meta_file.exists() and json.loads(meta_file.read_text()) != meta:
        print(f"{meta_file} has other settings ({meta_file.read_text().strip()}): use another --out, or the same settings", file=sys.stderr)
        return 1
    states = source_states(args.sources_from.split(","), tuple(args.kinds.split(",")))
    meta_file.write_text(json.dumps(meta))
    done = {r["i"] for r in read(path) if not r.get("error")}
    plan = design(states, blocks, args.sources, args.seed, args.reps)
    todo = [v for v in plan if v["i"] not in done]
    todo.sort(key=lambda v: (int(v["unit"].split("/")[1]), v["block"]))         # source by source across the blocks, so a partial run has whole units
    print(f"{path}: {len(blocks)} blocks x {args.sources} sources = {len(plan)} fights, {len(done)} done, {len(todo)} to play at {args.sims} sims, {args.workers} workers",
          flush=True)
    play_all(path, [(v, args.sims) for v in todo], job, args.workers, len(done))
    report(list(read(path)), blocks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
