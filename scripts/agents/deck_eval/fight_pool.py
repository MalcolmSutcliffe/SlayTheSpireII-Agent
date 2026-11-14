"""The fights a deck is tried on: round-1 states captured in the runs (data/runs/<run>/**/f<floor>_r1_<enemies>_<time>.json).

There is no encounter table in the sim, so a captured first round stands in for the fight: its enemies are kept, its player is
replaced by the deck being rated (fight_builder). Each template is tagged "weak" (the act's first combats: 3 in act 1, 2 after),
"normal", "elite" or "boss". The pool grows with every run that captures."""
from __future__ import annotations
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import data_paths

WEAK_FIGHTS = {1: 3, 2: 2, 3: 2}        # Act.NumberOfWeakEncounters: the first combats of an act come from the weak encounters


@dataclass(frozen=True)
class FightTemplate:
    name : str          # "Sludge_Spinner"
    act : int
    kind : str          # "weak" | "normal" | "elite" | "boss"
    state : dict        # the captured combat_play state, round 1
    boss : str | None = None        # a boss fight: its encounter id (VANTOM_BOSS, ...)
    variant : str | None = None     # act 1 only: "OVERGROWTH" or "UNDERDOCKS" (None: not known)

    @property
    def room_type(self) -> str:
        return {"weak": "monster", "normal": "monster"}.get(self.kind, self.kind)


def _is_round_one(state : dict) -> bool:
    return state.get("decision") == "combat_play" and state.get("round") == 1 and state.get("enemies") and "player" in state


def _context(state : dict) -> dict:
    return state.get("context") or state.get("run") or {}


def load_pool(root : Path | None = None) -> list[FightTemplate]:
    root = root or data_paths.RUNS
    per_run = defaultdict(list)       # run folder -> (floor, name, state)
    for path in sorted(root.rglob("f*_r1_*.json")):
        try:
            state = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not _is_round_one(state) or state.get("room_type") not in ("monster", "elite", "boss"):
            continue
        run = path.relative_to(root).parts[0]
        name = path.stem.split("_r1_", 1)[1].rsplit("_", 1)[0]
        per_run[run].append((_context(state).get("floor", 0), name, state))
    from agents.deck_eval.boss_spawner import BOSS_ACTS, boss_of
    # act 1 is Overgrowth or Underdocks, and that run's act 1 boss says which; an enemy met in a run that tells is known for the others
    run_variant = {}
    for run, fights in per_run.items():
        for floor, name, state in fights:
            boss = boss_of([e["entity_id"] for e in state["enemies"]]) if state["room_type"] == "boss" else None
            if boss and BOSS_ACTS[boss][0] == 1:
                run_variant[run] = BOSS_ACTS[boss][1]
    enemy_variant = {}
    for run, fights in per_run.items():
        for floor, name, state in fights:
            if run in run_variant and _context(state).get("act", 1) == 1:
                enemy_variant.setdefault(name, run_variant[run])
    pool, seen = [], set()
    for run, fights in per_run.items():
        combats = defaultdict(int)      # act -> monster fights met so far in this run
        for floor, name, state in sorted(fights, key=lambda f: f[0]):
            act = _context(state).get("act", 1)
            kind = state["room_type"]
            if kind == "monster":
                kind = "weak" if combats[act] < WEAK_FIGHTS.get(act, 2) else "normal"
                combats[act] += 1
            ids = [e["entity_id"] for e in state["enemies"]]
            boss = boss_of(ids) if kind == "boss" else None
            variant = (run_variant.get(run) or enemy_variant.get(name)) if act == 1 else None
            key = (act, kind, tuple(ids), state["enemies"][0].get("max_hp"))
            if key not in seen:     # the same fight met in several runs adds nothing
                seen.add(key)
                pool.append(FightTemplate(name, act, kind, state, boss, variant))
    return pool


def target_types(pool : list[FightTemplate]) -> dict[str, str]:
    """card id -> target_type, read from the cards in the pool's piles (the deck lists carry none)."""
    out = {}
    for t in pool:
        for pile in ("hand", "draw_pile", "discard_pile"):
            for c in t.state["player"].get(pile, ()):
                out.setdefault(c["id"], c["target_type"])
    return out
