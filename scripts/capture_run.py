"""Record a run played by hand in the live game, as reference data for the sim.

Polls the bridge mod (the same reader the agent runner uses) and keeps every settled state that differs from the last one:

    data/run_examples/<run_name>/
        states/00001_combat_play_f2.json   the full normalized bridge state, one file per change
        steps.jsonl                        one line per state: index, file, decision, floor, what changed since the previous state
        log.md                             the same, written to be read: each state's essentials and what changed

Usage (from scripts/, with the game running and the bridge mod loaded):

    ../.venv/bin/python capture_run.py silent-a0-1

Play normally; stop with Ctrl+C (it also stops by itself a few seconds after the game-over screen). Running it again with the same name
carries on numbering after the states already there.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from data_paths import RUN_EXAMPLES

POLL_SECONDS = 0.3          # between reads
SETTLE_READS = 2            # identical reads in a row before a state is kept (the game passes through half-finished states while animating)
GAME_OVER_LINGER = 5.0      # seconds the game-over screen is recorded before the capture stops


###
### Reading the game
###

def make_reader():
    """The agent runner's in-process reader, else the CLI (slower: it starts a process each read)."""
    from agent_runner.game_client import GameClient
    return GameClient().get_state


def canonical(state : dict) -> str:
    return json.dumps(state, sort_keys=True)


###
### Summaries
###

def label(x) -> str:
    """A readable name for a card, relic, potion, option or map node."""
    if not isinstance(x, dict):
        return str(x)
    name = next((x[k] for k in ("name", "title", "label", "text", "id", "type") if x.get(k)), "?")
    extra = []
    for k in ("price", "cost_gold", "gold_cost"):
        if x.get(k) is not None:
            extra.append(f"{x[k]}g")
            break
    if x.get("is_upgraded") and not str(name).endswith("+"):
        name = f"{name}+"
    if x.get("enchantment"):
        extra.append(f"ench {x['enchantment']}")
    if x.get("disabled") or x.get("is_locked") or x.get("enabled") is False:
        extra.append("locked")
    return f"{name} ({', '.join(extra)})" if extra else str(name)


def card_text(c : dict) -> str:
    cost = c.get("cost")
    return f"{label(c)} [{cost}]" if cost not in (None, "") else label(c)


def statuses(creature : dict) -> str:
    out = []
    for s in creature.get("status") or []:
        if isinstance(s, dict):
            name = s.get("name") or s.get("id") or "?"
            amount = s.get("amount")
            out.append(f"{name} {amount}" if amount not in (None, "") else str(name))
        else:
            out.append(str(s))
    return ", ".join(out)


def intents(enemy : dict) -> str:
    parts = []
    for i in enemy.get("intents") or []:
        text = i.get("type") or "?"
        if i.get("label"):
            text += f" {i['label']}"
        parts.append(text)
    move = enemy.get("move_id")
    return (" + ".join(parts) or "?") + (f" ({move})" if move else "")


def floor_of(state : dict):
    for src in (state.get("run"), state.get("context")):
        if isinstance(src, dict) and src.get("floor") is not None:
            return src.get("floor")
    return None


def player_of(state : dict) -> dict:
    return state.get("player") or {}


def describe(state : dict) -> list[str]:
    """The essentials of a state, as markdown lines."""
    d = state.get("decision")
    p = player_of(state)
    lines = []
    if p:
        bits = [f"HP {p.get('hp')}/{p.get('max_hp')}"]
        if p.get("block"):
            bits.append(f"Block {p['block']}")
        if d in ("combat_play", "hand_select"):
            bits.append(f"Energy {p.get('energy')}/{p.get('max_energy')}")
        bits.append(f"Gold {p.get('gold')}")
        lines.append(" · ".join(str(b) for b in bits))
        if p.get("status"):
            lines.append(f"Powers: {statuses(p)}")
    if d == "combat_play":
        lines.append(f"Round {state.get('round')} · {state.get('turn')} turn")
        lines.append("Hand: " + (", ".join(card_text(c) for c in state.get("hand") or []) or "(empty)"))
        for pile in ("draw_pile", "discard_pile", "exhaust_pile"):
            cards = p.get(pile)
            if cards:
                counts = Counter(label(c) for c in cards)
                lines.append(f"{pile.replace('_', ' ').title()} ({len(cards)}): " + ", ".join(f"{n}x {k}" if n > 1 else k for k, n in sorted(counts.items())))
        for e in state.get("enemies") or []:
            line = f"- {e.get('name')} {e.get('hp')}/{e.get('max_hp')}"
            if e.get("block"):
                line += f" block {e['block']}"
            if e.get("status"):
                line += f" [{statuses(e)}]"
            line += f" → {intents(e)}"
            lines.append(line)
    elif d == "hand_select" or d == "card_select":
        lines.append(f"Prompt: {state.get('prompt')}")
        lines.append("Cards: " + ", ".join(card_text(c) for c in state.get("cards") or []))
        if state.get("selected_cards"):
            lines.append("Selected: " + ", ".join(card_text(c) for c in state["selected_cards"]))
    elif d == "card_reward":
        lines.append("Cards: " + ", ".join(card_text(c) for c in state.get("cards") or []))
    elif d == "combat_rewards":
        lines.append("Rewards: " + ", ".join(label(i) for i in state.get("items") or []))
    elif d == "map_select":
        pos = state.get("current_position") or {}
        if pos:
            lines.append(f"At: {label(pos)} (row {pos.get('row')}, col {pos.get('col')})")
        lines.append("Next: " + ", ".join(f"{label(c)} (row {c.get('row')}, col {c.get('col')})" for c in state.get("choices") or []))
    elif d == "event_choice":
        lines.append(f"Event: {state.get('event_name')} ({state.get('event_id')})")
        lines.append("Options: " + " | ".join(label(o) for o in state.get("options") or []))
    elif d in ("rest_site", "game_over"):
        lines.append("Options: " + ", ".join(label(o) for o in state.get("options") or []))
    elif d == "shop":
        lines.append("Shop: " + ", ".join(label(i) for i in state.get("items") or []))
    elif d in ("relic_select", "treasure"):
        lines.append("Relics: " + ", ".join(label(r) for r in state.get("relics") or []))
    return lines


def _multiset_diff(before : list, after : list) -> tuple[list, list]:
    a, b = Counter(label(x) for x in before or []), Counter(label(x) for x in after or [])
    return sorted((b - a).elements()), sorted((a - b).elements())


def changes(prev : dict | None, state : dict) -> list[str]:
    """What changed since the previous state kept: what the player did, as far as the states show it."""
    if prev is None:
        return ["capture started"]
    out = []
    p0, p1 = player_of(prev), player_of(state)
    if floor_of(prev) != floor_of(state):
        out.append(f"floor {floor_of(prev)} → {floor_of(state)}")
    if prev.get("decision") != state.get("decision"):
        out.append(f"screen {prev.get('decision')} → {state.get('decision')}")
    for key, name in (("hp", "HP"), ("max_hp", "max HP"), ("gold", "gold"), ("block", "block"), ("energy", "energy")):
        if p0.get(key) is not None and p1.get(key) is not None and p0.get(key) != p1.get(key):
            out.append(f"{name} {p0[key]} → {p1[key]}")
    for key, name in (("deck", "deck"), ("relics", "relics"), ("potions", "potions")):
        if key in p0 and key in p1:
            added, removed = _multiset_diff(p0[key], p1[key])
            if added:
                out.append(f"{name} +{', +'.join(added)}")
            if removed:
                out.append(f"{name} -{', -'.join(removed)}")
    if p0.get("status") is not None and statuses(p0) != statuses(p1):
        out.append(f"powers [{statuses(p0)}] → [{statuses(p1)}]")
    if prev.get("decision") == state.get("decision"):
        if prev.get("selected_cards") != state.get("selected_cards"):
            added, removed = _multiset_diff(prev.get("selected_cards"), state.get("selected_cards"))
            out += [f"selected {c}" for c in added] + [f"unselected {c}" for c in removed]
        if (prev.get("current_position") or {}) != (state.get("current_position") or {}):
            pos = state.get("current_position") or {}
            out.append(f"moved to {label(pos)} (row {pos.get('row')}, col {pos.get('col')})")
        elif prev.get("choices") != state.get("choices"):
            out.append("map options changed")
        if prev.get("cards") != state.get("cards") and prev.get("decision") != "combat_play":
            out.append("cards on screen changed")
        if prev.get("can_confirm") != state.get("can_confirm") and state.get("can_confirm") is not None:
            out.append("confirm " + ("enabled" if state.get("can_confirm") else "disabled"))
    if prev.get("decision") == "combat_play" and state.get("decision") == "combat_play":
        added, removed = _multiset_diff(prev.get("hand"), state.get("hand"))
        if removed:
            out.append(f"left hand: {', '.join(removed)}")
        if added:
            out.append(f"joined hand: {', '.join(added)}")
        for pile in ("draw_pile_count", "discard_pile_count", "exhaust_pile_count"):
            if prev.get(pile) != state.get(pile):
                out.append(f"{pile[:-11]} pile {prev.get(pile)} → {state.get(pile)}")
        if prev.get("turn") != state.get("turn") or prev.get("round") != state.get("round"):
            out.append(f"round {prev.get('round')} {prev.get('turn')} → round {state.get('round')} {state.get('turn')}")
        before = {e.get("entity_id") or e.get("name"): e for e in prev.get("enemies") or []}
        for e in state.get("enemies") or []:
            key = e.get("entity_id") or e.get("name")
            old = before.pop(key, None)
            if old is None:
                out.append(f"{e.get('name')} appeared ({e.get('hp')}/{e.get('max_hp')})")
                continue
            for k in ("hp", "block"):
                if old.get(k) != e.get(k):
                    out.append(f"{e.get('name')} {k} {old.get(k)} → {e.get(k)}")
            if statuses(old) != statuses(e):
                out.append(f"{e.get('name')} powers [{statuses(old)}] → [{statuses(e)}]")
            if old.get("move_id") != e.get("move_id"):
                out.append(f"{e.get('name')} next move {old.get('move_id')} → {e.get('move_id')}")
        for old in before.values():
            out.append(f"{old.get('name')} gone")
    return out or ["(no visible change)"]


###
### The capture
###

class Capture:
    def __init__(self, folder : Path):
        self.folder = folder
        self.states = folder / "states"
        self.states.mkdir(parents=True, exist_ok=True)
        existing = sorted(self.states.glob("*.json"))
        self.index = int(existing[-1].name.split("_")[0]) if existing else 0
        self.prev = json.loads(existing[-1].read_text()) if existing else None
        self.log = (folder / "log.md").open("a")
        self.steps = (folder / "steps.jsonl").open("a")
        if not existing:
            self.log.write(f"# Run capture: {folder.name}\n\nStarted {datetime.now():%Y-%m-%d %H:%M}. "
                           "Each section is one state the game settled on; *Changed* is the difference from the section before.\n")

    def keep(self, state : dict):
        self.index += 1
        d = state.get("decision") or "unknown"
        floor = floor_of(state)
        name = f"{self.index:05d}_{d}" + (f"_f{floor}" if floor is not None else "") + ".json"
        (self.states / name).write_text(json.dumps(state, indent=1, sort_keys=True))
        changed = changes(self.prev, state)
        self.steps.write(json.dumps({"index": self.index, "file": f"states/{name}", "decision": d, "floor": floor,
                                     "time": round(time.time(), 2), "changed": changed}) + "\n")
        self.log.write(f"\n## {self.index:05d} · floor {floor} · {d}\n")
        self.log.write(f"*Changed:* {'; '.join(changed)}\n\n")
        for line in describe(state):
            self.log.write(line + ("\n" if line.startswith("- ") else "  \n"))
        self.log.flush()
        self.steps.flush()
        self.prev = state
        print(f"[{self.index:05d}] f{floor} {d}: {'; '.join(changed)[:150]}", flush=True)


def run(name : str):
    folder = RUN_EXAMPLES / name
    capture = Capture(folder)
    read = make_reader()
    print(f"Capturing to {folder}  (Ctrl+C to stop)", flush=True)
    last_kept = canonical(capture.prev) if capture.prev is not None else None
    candidate, same, bridge_down, game_over_since = None, 0, False, None
    while True:
        try:
            state = read()
        except Exception as e:      # noqa: BLE001  the game is loading, closed, or the bridge is not up yet
            if not bridge_down:
                print(f"waiting for the bridge ({type(e).__name__}: {e})", flush=True)
                bridge_down = True
            time.sleep(1.0)
            continue
        bridge_down = False
        text = canonical(state)
        same = same + 1 if text == candidate else 1
        candidate = text
        if same >= SETTLE_READS and text != last_kept and state.get("decision") not in ("overlay",):
            capture.keep(state)
            last_kept = text
        if state.get("decision") == "game_over":
            game_over_since = game_over_since or time.time()
            if time.time() - game_over_since > GAME_OVER_LINGER and last_kept == text:
                print("game over: capture finished", flush=True)
                return
        else:
            game_over_since = None
        time.sleep(POLL_SECONDS)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", nargs="?", default=None, help="folder name under data/run_examples/ (default: a timestamp)")
    args = parser.parse_args(argv)
    name = args.name or datetime.now().strftime("run-%Y%m%d-%H%M%S")
    try:
        run(name)
    except KeyboardInterrupt:
        print("\nstopped", flush=True)


if __name__ == "__main__":
    sys.exit(main())
