"""Fits the walk's fight policy to the MCTS.

A fixed set of fights (a deck of the starter cards plus a few card rewards, a monster group from the engine's pools, some HP) is played once by the MCTS (the
slow part, cached in a file), and then by any number of variants of the rollout policy (fast). A variant is better the closer its cost per fight is to the
MCTS's: a fight's cost is the HP it took, or all the HP the fight began with if it was lost.

Usage (from scripts/):
  python -m benchmarks.policy_fit mcts --cases 120 --time-budget 0.1 --workers 2      # plays the MCTS on the cases (cached by case and budget)
  ... --stratify                                                                      # on every command: the cases cycle through weak / normal / elite / boss fights (a cache of its own)
  python -m benchmarks.policy_fit collect                                             # the decks of the runs in data/runs -> benchmarks/results/real_decks.json
  ... --decks                                                                         # on every command: play those real decks, each against the kind of fight it would meet (a cache of its own)
  python -m benchmarks.policy_fit cards --cases 60 --reps 3 --time-budget 1.0 --workers N   # does the walk's cheap policy find the same cards good as the MCTS? (implies --decks; --only powers --kinds elite,boss asks about the Powers in the long fights)
  python -m benchmarks.policy_fit moves --cases 40 --time-budget 1.0 --workers N   # at each decision of an MCTS fight: what the cheap policy would have played instead (implies --decks)
  python -m benchmarks.policy_fit tune [--set name=field:value,...]                  # variants of the policy against the turns of those MCTS fights (cheap; needs `moves` first)
  python -m benchmarks.policy_fit sweep [--reps 6] [--set name=field:value,field:value ...]   # variants of the policy against it
Variants (`--set`) change HeuristicParams fields (and `policy` names a RolloutPolicy); with none given a built-in list of single-field sweeps runs."""
from __future__ import annotations
import argparse
import json
import os
import random
import statistics
import time
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmarks.bench import SEARCH_SEED_OFFSET, default_workers, map_jobs, play_fight
from benchmarks.calibrate import spearman

CACHE_DIR = Path(__file__).resolve().parent / "results"
KINDS = ("weak", "normal", "elite", "boss")
ONLY_ENV = "POLICY_FIT_ONLY"                  # set by `cards --only`: the cards a case may ask about (comma separated; "powers": every Power)
KINDS_ENV = "POLICY_FIT_KINDS"                # set by `cards --kinds`: the kinds of fight the cases cycle through
STRATIFY_ENV = "POLICY_FIT_STRATIFY"          # set by --stratify (an environment variable, so the worker processes see it)
DECKS_ENV = "POLICY_FIT_DECKS"                # set by --decks: the file `collect` wrote
DECKS_FILE = CACHE_DIR / "real_decks.json"
ACT_START = {1: 0, 2: 17, 3: 34}              # the floor an act starts after
ROOMS_INTO_ACT = {"weak": (1, 5), "normal": (2, 14), "elite": (5, 14), "boss": (12, 17)}       # how far into its act a deck is when it meets that kind of fight
MAX_HP = 80
EXTRAS = {1: (0, 7), 2: (6, 13), 3: (10, 19)}            # card rewards a deck holds when it meets an act's fights


def make_case(seed : int, i : int):
    """(template, deck, player) of case i: the same for every player."""
    from agents.deck_eval.fight_mix import draw, kind_templates, new_act_mix, pick_fights
    from agents.deck_eval.fight_pool import load_pool, target_types
    from agents.deck_eval.future_cards import extra_cards
    from sts2_lite.run import new_run
    r = random.Random(seed * 100003 + i)
    pool = load_pool()
    if os.environ.get(DECKS_ENV):           # a deck, relics and HP a real run had, against a fight of the kind it would meet there
        kinds = os.environ[KINDS_ENV].split(",") if os.environ.get(KINDS_ENV) else KINDS
        kind = kinds[i % len(kinds)]
        states = real_decks(os.environ[DECKS_ENV])
        lo, hi = ROOMS_INTO_ACT[kind]
        state = r.choice([x for x in states if lo <= x["floor"] - ACT_START[x["act"]] <= hi] or states)
        act, player = state["act"], state["player"]
        template = draw(kind_templates(pool, new_act_mix(act)), kind, state.get("ascension") or 0, r)
        return template, player["deck"], player, target_types(pool), act
    act = r.choice((1, 1, 2, 3))
    if os.environ.get(STRATIFY_ENV):            # every kind of fight in turn, so each row of the table gets as many cases as the others
        template = draw(kind_templates(pool, new_act_mix(act)), KINDS[i % len(KINDS)], 0, r)
    else:
        template = pick_fights(pool, new_act_mix(act), 1, r.randrange(1 << 30))[0]
    run = new_run()
    deck = run.deck + extra_cards(r.randint(*EXTRAS[act]), r)
    hp = r.randint(int(0.55 * MAX_HP), MAX_HP)
    player = {"hp": hp, "max_hp": MAX_HP, "relics": run.relics, "gold": 0}
    return template, deck, player, target_types(pool), act


_DECKS : dict[str, list[dict]] = {}


def real_decks(path : str) -> list[dict]:
    if path not in _DECKS:
        _DECKS[path] = json.loads(Path(path).read_text())
    return _DECKS[path]


def collect(args):
    """The decks, relics and HP the runs in data/runs had at each map screen (one per room of a run), written to `real_decks.json`: what `--decks` plays the fights with.
    Only the player is used, never the old run's outcomes: those came from older versions of the agent and the sim."""
    from data_paths import RUNS
    states = []
    for path in sorted(RUNS.glob("*/run_states.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            state = (json.loads(line) or {}).get("state") or {}
            player, context = state.get("player") or {}, state.get("context") or {}
            if state.get("decision") != "map_select" or not player.get("deck") or context.get("act") not in ACT_START:
                continue
            keep = {k: player[k] for k in ("hp", "max_hp", "gold", "potion_slots", "relics", "deck") if k in player}
            states.append({"run": path.parent.name, "act": context["act"], "floor": context["floor"], "ascension": context.get("ascension", 0), "player": keep})
    CACHE_DIR.mkdir(exist_ok=True)
    DECKS_FILE.write_text(json.dumps(states))
    by_act = {a: sum(1 for x in states if x["act"] == a) for a in ACT_START}
    print(f"{len(states)} deck states from {len({x['run'] for x in states})} runs ({by_act}) in {DECKS_FILE}")


def candidate(seed : int, i : int) -> dict:
    """The card case i asks about: one card drawn like a card reward."""
    from agents.deck_eval.future_cards import CARD_POOL, extra_cards
    if os.environ.get(ONLY_ENV):
        wanted = os.environ[ONLY_ENV].split(",")
        pool = [c for cards in CARD_POOL.values() for c in cards if c["id"] in wanted or ("powers" in wanted and c["type"] == "Power")]
        return dict(random.Random(seed * 31 + i).choice(pool))
    return extra_cards(1, random.Random(seed * 31 + i))[0]


def build(seed : int, i : int, arm : str = "without"):
    from agents.deck_eval.fight_builder import build_fight
    template, deck, player, targets, act = make_case(seed, i)
    if arm == "with":
        deck = deck + [candidate(seed, i)]
    return build_fight(template, deck, player, targets), template, player["hp"], act


def mcts_job(job):
    seed, i, budget = job
    from agents.sts2_MCTS.params import SearchConfig
    sim, template, hp, act = build(seed, i)
    out = play_fight(sim.combat_state, SearchConfig(time_budget=budget), seed * 1000 + i, SEARCH_SEED_OFFSET + seed * 1000 + i)
    return {"i": i, "act": act, "kind": template.kind, "enemy": template.name, "hp": hp, "won": out["won"], "hp_lost": out["hp_lost"], "turns": out["turns"]}


def policy_job(job):
    seed, i, name, spec, rep = job
    from sts2_lite import rng
    from sts2_lite.combat import CombatSimulator
    from agents.deck_eval.playout import play_out
    cfg = variant_config(spec)
    sim, template, hp, act = build(seed, i)
    cs = sim.combat_state
    from agents.sts2_MCTS import outcome_score
    expected = outcome_score.expected_total_hp(cs)
    rng.seed(seed * 7919 + i * 31 + rep)
    play_out(sim, cfg, 25)
    won = outcome_score.is_win(cs)
    left = outcome_score.enemy_progress_left(cs, expected)
    return {"i": i, "name": name, "won": won, "hp_lost": hp - max(0, cs.player.current_hp), "hp": hp, "left": 0.0 if won else left}


def mcts_card_job(job):
    seed, i, arm, rep, budget = job
    from agents.sts2_MCTS.params import SearchConfig
    sim, template, hp, act = build(seed, i, arm)
    world = seed * 1000 + i * 10 + rep            # the same draws and enemy rolls for both arms of a case, until their moves differ
    out = play_fight(sim.combat_state, SearchConfig(time_budget=budget), world, SEARCH_SEED_OFFSET + world)
    return {"i": i, "arm": arm, "rep": rep, "act": act, "kind": template.kind, "enemy": template.name, "card": candidate(seed, i)["id"], "hp": hp,
            "won": out["won"], "hp_lost": out["hp_lost"], "turns": out["turns"]}


def policy_card_job(job):
    seed, i, arm, rep = job
    from sts2_lite import rng
    from agents.sts2_MCTS.params import SearchConfig
    from agents.sts2_MCTS import outcome_score
    from agents.deck_eval.playout import play_out
    sim, template, hp, act = build(seed, i, arm)
    cs = sim.combat_state
    expected = outcome_score.expected_total_hp(cs)
    rng.seed(seed * 7919 + i * 31 + rep)
    play_out(sim, variant_config({}), 25)
    won = outcome_score.is_win(cs)
    left = outcome_score.enemy_progress_left(cs, expected)
    return {"i": i, "arm": arm, "rep": rep, "won": won, "hp_lost": hp - max(0, cs.player.current_hp), "hp": hp, "left": 0.0 if won else left}


def cards(args):
    """Does the walk's cheap policy (with route_sim's correction) find the same cards good as the MCTS?
    Each case is a real deck against a fight, and one card drawn like a card reward: both play the fight without the card and with it, and a card's value is the HP it saves
    (a lost fight costs all the HP the fight began with). The MCTS is the reference, at `--time-budget` per decision, `--reps` fights per arm; the policy plays `--policy-reps`."""
    suffix = ("_only-" + args.only.replace(",", "-") if args.only else "") + ("_kinds-" + args.kinds.replace(",", "-") if args.kinds else "")
    cache = CACHE_DIR / f"policy_fit_cards_s{args.seed}_b{args.time_budget}{suffix}.json"
    CACHE_DIR.mkdir(exist_ok=True)
    cached = json.loads(cache.read_text()) if cache.exists() else []
    have = {(r["i"], r["arm"], r["rep"]) for r in cached}
    todo = [(args.seed, i, arm, rep, args.time_budget) for i in range(args.cases) for arm in ("without", "with") for rep in range(args.reps) if (i, arm, rep) not in have]
    if todo:
        cached += map_jobs(mcts_card_job, todo, args.workers, "mcts fights")
        cache.write_text(json.dumps(cached))
    cached = [r for r in cached if r["i"] < args.cases and r["rep"] < args.reps]
    info = {r["i"]: r for r in cached}
    ids = sorted(info)
    runs = map_jobs(policy_card_job, [(args.seed, i, arm, rep) for i in ids for arm in ("without", "with") for rep in range(args.policy_reps)], args.workers, "policy fights")
    rolls = random.Random(5)
    mean = lambda rows: statistics.fmean(rows)

    def value(rows : list[dict], i : int, rep_filter=lambda rep: True) -> float:
        """HP the card saves in case i: the cost without it minus the cost with it."""
        side = lambda arm: [cost(r) for r in rows if r["i"] == i and r["arm"] == arm and rep_filter(r["rep"])]
        return mean(side("without")) - mean(side("with"))

    fixed = [dict(corrected(r, info[r["i"]], rolls.random()), i=r["i"], arm=r["arm"], rep=r["rep"]) for r in runs]
    mv = {i: value(cached, i) for i in ids}
    pv = {i: value(fixed, i) for i in ids}
    rv = {i: value(runs, i) for i in ids}
    half = lambda k: {i: value(cached, i, lambda rep: rep % 2 == k) for i in ids}
    even, odd = half(0), half(1)

    def report(name, sel):
        part = [i for i in ids if sel(info[i])]
        if len(part) < 3:
            return
        row = lambda d: [d[i] for i in part]
        big = [i for i in part if abs(mv[i]) >= 5]
        agree = lambda d: "%3.0f%% of %2d" % (100 * statistics.fmean((d[i] > 0) == (mv[i] > 0) for i in big), len(big)) if big else "  n/a"
        print("%-8s n=%3d | rank agr: corrected %5.2f  raw %5.2f  (MCTS with itself %5.2f) | same sign where MCTS moves it >= 5 HP: corrected %s  raw %s | mean saved: mcts %+5.1f  policy %+5.1f" % (
            name, len(part), spearman(row(pv), row(mv)), spearman(row(rv), row(mv)), spearman(row(even), row(odd)), agree(pv), agree(rv), mean(row(mv)), mean(row(pv))))
    print("# value of a card = HP it saves in a fight (positive: good).  MCTS with itself = its even reps against its odd reps: what any policy could reach at best")
    report("all", lambda m: True)
    for kind in KINDS:
        report(kind, lambda m, k=kind: m["kind"] == k)
    for act in (1, 2, 3):
        report("act %d" % act, lambda m, a=act: m["act"] == a)
    by_card = {}
    for i in ids:
        by_card.setdefault(info[i]["card"], []).append(i)
    rows = sorted(((mean([mv[i] for i in v]), mean([pv[i] for i in v]), len(v), c) for c, v in by_card.items() if len(v) >= 2), reverse=True)
    if rows:
        print("\n# cards drawn at least twice: mean HP saved (MCTS | policy), by the MCTS's value; a gap of more than 5 HP is marked")
        for m, p, n, c in rows:
            print("  %-22s n=%2d  mcts %+6.1f  policy %+6.1f %s" % (c, n, m, p, "<-- differ" if abs(m - p) > 5 else ""))
    worst = sorted(ids, key=lambda i: -abs(pv[i] - mv[i]))[:8]
    print("\n# the cases the two disagree on most (kind, card, enemy: mcts | policy)")
    for i in worst:
        print("  %-6s %-22s %-26s %+6.1f | %+6.1f" % (info[i]["kind"], info[i]["card"], info[i]["enemy"], mv[i], pv[i]))


def label(sim, action : dict) -> str:
    """What an action is, without its target: the card's id, END_TURN, a potion, or a pick from a pile."""
    kind = action["action"]
    if kind == "end_turn":
        return "END_TURN"
    hand = sim.combat_state.player.hand
    if kind == "play_card" and action.get("card_index") is not None and action["card_index"] < len(hand):
        return hand[action["card_index"]].card_id.name
    return kind.upper() + (":" + str(action.get("card_index")) if kind != "use_potion" else "")


def variant_config(spec : dict):
    """The policy the walks use (evaluator.WALK_POLICY) unless `policy` names another RolloutPolicy; the other fields are HeuristicParams'."""
    from agents.deck_eval.evaluator import WALK_POLICY
    from agents.sts2_MCTS.params import RolloutPolicy, SearchConfig
    return SearchConfig().tuned(rollout=RolloutPolicy[spec["policy"]] if "policy" in spec else WALK_POLICY, **{k: v for k, v in spec.items() if k != "policy"})


def foes_hp(cs) -> int:
    """The enemies' HP, without the Waterfall Giant's 999999999 once it is about to blow."""
    return sum(e.current_hp for e in cs.enemies if 0 < e.current_hp < 100000)


def policy_turn(start_sim, turn : int, config, seed : int) -> dict:
    """The rollout policy plays the rest of `turn` on a copy of `start_sim`, up to its end_turn: the cards it played and what the turn left."""
    from collections import Counter
    from sts2_lite import rng
    from sts2_lite.combat import CombatSimulator, CombatState
    from agents.sts2_MCTS.rollout_policy import rollout_policy
    rng.seed(seed)
    copy_sim = CombatSimulator(CombatState.deepcopy(start_sim.combat_state))
    played = Counter()
    while not copy_sim.is_over and copy_sim.combat_state.turn_number == turn:
        actions = copy_sim.get_available_actions()
        if not actions:
            break
        action = rollout_policy(copy_sim, actions, config.rollout, config.heuristic) if len(actions) > 1 else actions[0]
        if action["action"] == "end_turn":
            break
        if action["action"] == "play_card":
            played[label(copy_sim, action)] += 1
        copy_sim.perform_action(action)
    cs = copy_sim.combat_state
    return {"played": dict(played), "energy": cs.energy, "block": cs.player.block, "foes": foes_hp(cs)}


def moves_job(job):
    """The MCTS plays one fight. At the start of each turn the policy plays that turn from the same state `samples` times (on copies), so the two turns can be compared:
    the cards each played, and what the turn left (energy, block, damage done)."""
    seed, i, budget, samples = job
    from collections import Counter
    import copy
    from sts2_lite import rng
    from sts2_lite.combat import CombatSimulator, CombatState
    from agents.sts2_MCTS.MCTS import sts2_MCTS
    from agents.sts2_MCTS.params import SearchConfig
    from agents.sts2_MCTS.rollout_policy import rollout_policy
    from agents.sts2_MCTS.outcome_score import is_win
    world_seed = seed * 1000 + i
    rng.seed(world_seed)                    # (the opening hand is drawn while the fight is built: seeded, so the fight can be replayed from its actions)
    sim, template, hp, act = build(seed, i)
    config = SearchConfig(time_budget=budget)
    policy_config = variant_config({"p_random_action": 0.0})
    rng.seed(world_seed); world = rng.getstate()
    rng.seed(SEARCH_SEED_OFFSET + world_seed); search = rng.getstate()
    sim = CombatSimulator(CombatState.deepcopy(sim.combat_state))
    rng.setstate(world); sim.combat_state.player.shuffle_draw_pile(); world = rng.getstate()
    searcher = sts2_MCTS()
    foes = foes_hp
    taken = []

    policy_turns = lambda sim, turn: [policy_turn(sim, turn, policy_config, world_seed * 131 + turn * 7 + k) for k in range(samples)]

    turns, current, start_turn = [], None, sim.combat_state.turn_number
    while not sim.is_over and sim.combat_state.turn_number < start_turn + 25:
        cs = sim.combat_state
        if current is None or current["turn"] != cs.turn_number:
            saved = rng.getstate()
            current = {"i": i, "kind": template.kind, "act": act, "turn": cs.turn_number, "hp": cs.player.current_hp, "hand": [c.card_id.name for c in cs.player.hand],
                       "energy_start": cs.energy, "foes_start": foes(cs), "incoming": sum(e.attack_damage * e.num_attacks for e in cs.enemies if e.current_hp > 0 and not e.is_minion),
                       "policy": policy_turns(sim, cs.turn_number), "mcts_played": {}}
            rng.setstate(saved)
            turns.append(current)
        actions = sim.get_available_actions()
        if not actions:
            break
        if len(actions) == 1:
            action = actions[0]
        else:
            rng.setstate(search)
            action, stats = searcher.monte_carlo_tree_search(cs, config)
            search = rng.getstate()
        if action["action"] == "end_turn":
            current["mcts_end"] = {"energy": cs.energy, "block": cs.player.block, "foes": foes(cs)}
        elif action["action"] == "play_card":
            name = label(sim, action)
            current["mcts_played"][name] = current["mcts_played"].get(name, 0) + 1
        taken.append(action)
        rng.setstate(world)
        sim.perform_action(action)
        world = rng.getstate()
    return {"i": i, "kind": template.kind, "won": is_win(sim.combat_state), "turns": [t for t in turns if "mcts_end" in t], "actions": taken}


def moves(args):
    """How the cheap policy plays a turn compared with the MCTS, from the same state: which cards it plays more or less often, and what the turn leaves."""
    cache = CACHE_DIR / f"policy_fit_moves_s{args.seed}_b{args.time_budget}.json"
    CACHE_DIR.mkdir(exist_ok=True)
    cached = [r for r in json.loads(cache.read_text()) if "actions" in r] if cache.exists() else []      # (fights cached before the actions were kept are played again)
    have = {r["i"] for r in cached}
    todo = [(args.seed, i, args.time_budget, args.samples) for i in range(args.cases) if i not in have]
    if todo:
        cached += map_jobs(moves_job, todo, args.workers, "mcts fights")
        cache.write_text(json.dumps(cached))
    turns = [t for f in cached if f["i"] < args.cases for t in f["turns"]]
    from collections import Counter, defaultdict
    mean = statistics.fmean
    print("%d turns in %d fights (%d policy turns each)" % (len(turns), len({t["i"] for t in turns}), args.samples))

    def spent(t):
        return {"mcts": t["energy_start"] - t["mcts_end"]["energy"], "policy": mean(t["energy_start"] - p["energy"] for p in t["policy"])}
    def sane(t):         # a turn an earlier version of this command recorded with the Waterfall Giant's stand-in HP
        return max(t["foes_start"], t["mcts_end"]["foes"], *[p["foes"] for p in t["policy"]]) < 5000
    def damage(t):
        return {"mcts": t["foes_start"] - t["mcts_end"]["foes"], "policy": mean(t["foes_start"] - p["foes"] for p in t["policy"])}
    def block(t):
        return {"mcts": t["mcts_end"]["block"], "policy": mean(p["block"] for p in t["policy"])}
    def same_cards(t):
        return mean(p["played"] == t["mcts_played"] for p in t["policy"])
    print("\n# per turn, MCTS | policy: energy spent, damage to enemies, block at the end of the turn, and how often the policy plays exactly the MCTS's cards")
    groups = [("all", lambda t: True)] + [(k, lambda t, k=k: t["kind"] == k) for k in KINDS] + [("turn 1-2", lambda t: t["turn"] <= 2), ("turn 3+", lambda t: t["turn"] > 2)]
    for name, sel in groups:
        part = [t for t in turns if sel(t)]
        if part:
            print("  %-8s n=%4d | energy %.2f | %.2f   damage %5.1f | %5.1f   block %5.1f | %5.1f   same cards %.2f" % (
                name, len(part), mean(spent(t)["mcts"] for t in part), mean(spent(t)["policy"] for t in part), mean(damage(t)["mcts"] for t in part if sane(t)), mean(damage(t)["policy"] for t in part if sane(t)),
                mean(block(t)["mcts"] for t in part), mean(block(t)["policy"] for t in part), mean(same_cards(t) for t in part)))
    by_card = defaultdict(list)
    for t in turns:
        for name in set(t["hand"]):
            by_card[name].append((t["mcts_played"].get(name, 0), mean(p["played"].get(name, 0) for p in t["policy"]), t["hand"].count(name)))
    print("\n# per card, over the turns it was in the opening hand (at least 10): plays per turn (MCTS | policy) per copy in hand, sorted by the gap")
    rows = [(mean(m / c for m, p, c in v) - mean(p / c for m, p, c in v), name, len(v), mean(m / c for m, p, c in v), mean(p / c for m, p, c in v)) for name, v in by_card.items() if len(v) >= 10]
    for gap, name, n, m, p in sorted(rows):
        print("  %-22s n=%4d   %.2f | %.2f   %+.2f %s" % (name, n, m, p, -gap, "  policy plays it more" if gap < -0.15 else "  policy plays it less" if gap > 0.15 else ""))


def replay_fight(job):
    """The turns of one cached MCTS fight, rebuilt by replaying its actions: (turn, state at its start, the cards the MCTS played, what it left)."""
    seed, i, actions = job
    from collections import Counter
    from sts2_lite import rng
    from sts2_lite.combat import CombatSimulator, CombatState
    world_seed = seed * 1000 + i
    rng.seed(world_seed)
    sim, template, hp, act = build(seed, i)
    rng.seed(world_seed)
    sim = CombatSimulator(CombatState.deepcopy(sim.combat_state))
    sim.combat_state.player.shuffle_draw_pile()
    world = rng.getstate()
    turns, current = [], None
    for action in actions:
        cs = sim.combat_state
        if current is None or current["turn"] != cs.turn_number:
            current = {"i": i, "kind": template.kind, "turn": cs.turn_number, "start": CombatSimulator(CombatState.deepcopy(cs)), "energy_start": cs.energy, "foes_start": foes_hp(cs), "played": Counter()}
            turns.append(current)
        if action["action"] == "end_turn":
            current["end"] = {"energy": cs.energy, "block": cs.player.block, "foes": foes_hp(cs)}
        elif action["action"] == "play_card":
            current["played"][label(sim, action)] += 1
        rng.setstate(world)
        sim.perform_action(action)
        world = rng.getstate()
    return [t for t in turns if "end" in t]


def tune_job(job):
    """One MCTS fight, replayed from its actions (the states cannot be sent between processes, so each worker replays its own), and every variant of the policy on its turns:
    how far the policy's turns are from the MCTS's. A fight that does not replay gives its error."""
    seed, i, actions, variants, samples = job
    try:
        turns = replay_fight((seed, i, actions))
    except Exception as error:
        return {"i": i, "error": "%s: %s" % (type(error).__name__, str(error)[:200]), "rows": [], "turns": 0}
    rows = []
    for name, spec in variants.items():
        config = variant_config(spec)
        for t in turns:
            for k in range(samples):
                clock = time.perf_counter()
                out = policy_turn(t["start"], t["turn"], config, seed * 977 + t["i"] * 131 + t["turn"] * 7 + k)
                took = time.perf_counter() - clock
                mine, theirs = out["played"], t["played"]
                gap = sum(abs(mine.get(c, 0) - theirs.get(c, 0)) for c in set(mine) | set(theirs))
                rows.append({"name": name, "kind": t["kind"], "gap": gap, "same": gap == 0, "ms": 1000 * took,
                             "energy": (t["energy_start"] - out["energy"]) - (t["energy_start"] - t["end"]["energy"]),
                             "damage": out["foes"] * -1 + t["end"]["foes"] if max(t["foes_start"], out["foes"], t["end"]["foes"]) < 5000 else None,
                             "block": out["block"] - t["end"]["block"]})
    return {"i": i, "rows": rows, "turns": len(turns)}


def tune(args):
    """Variants of the policy against the turns of the cached MCTS fights (`moves` first). A turn's gap is the number of cards the policy plays that the MCTS did not
    plus the number it left unplayed that the MCTS played (0: the same cards); energy / damage / block are the policy's minus the MCTS's."""
    cache = CACHE_DIR / f"policy_fit_moves_s{args.seed}_b{args.time_budget}.json"
    fights = [r for r in json.loads(cache.read_text()) if "actions" in r] if cache.exists() else []
    if not fights:
        raise SystemExit("no MCTS fights with their actions: run the `moves` command first")
    variants = dict(parse_variant(t) for t in args.set) or VARIANTS
    variants = {"floor (first action)": {"policy": "FirstAction"}, **variants}          # what a turn costs with no thinking: the engine alone
    results = map_jobs(tune_job, [(args.seed, f["i"], f["actions"], variants, args.samples) for f in fights], args.workers, "replays + policy turns")
    failed = [r for r in results if r.get("error")]
    if failed:
        print("%d of %d fights did not replay, left out:" % (len(failed), len(fights)))
        for r in failed[:5]:
            print("   case %d: %s" % (r["i"], r["error"]))
    rows = [row for r in results for row in r["rows"]]
    if not rows:
        raise SystemExit("no fight replayed")
    print("%d turns of %d MCTS fights; %d samples of the policy each" % (sum(r["turns"] for r in results), len(results) - len(failed), args.samples))
    print("%-22s %6s %7s %8s %8s %8s %8s    %s" % ("variant", "gap", "same", "energy", "damage", "block", "ms/turn", "gap by weak / normal / elite / boss"))
    for name in variants:
        mine = [r for r in rows if r["name"] == name]
        by_kind = " / ".join("%.2f" % statistics.fmean(r["gap"] for r in mine if r["kind"] == k) for k in KINDS if any(r["kind"] == k for r in mine))
        dmg = [r["damage"] for r in mine if r["damage"] is not None]
        print("%-22s %6.2f %6.0f%% %+8.2f %+8.1f %+8.1f %8.2f    %s" % (name, statistics.fmean(r["gap"] for r in mine), 100 * statistics.fmean(r["same"] for r in mine),
              statistics.fmean(r["energy"] for r in mine), statistics.fmean(dmg), statistics.fmean(r["block"] for r in mine), statistics.fmean(r["ms"] for r in mine), by_kind))


def cost(row) -> float:
    return row["hp_lost"] if row["won"] else row["hp"]


VARIANTS = {
    "shipped": {},                                               # the walks' policy (evaluator.WALK_POLICY)
    "old heuristic": {"policy": "ClaudeHeuristic"},
    "block x0": {"block_mult": 0.0},
    "block x3": {"block_mult": 3.0},
    "block x8": {"block_mult": 8.0},
    "cap 25": {"block_cap": 25},
    "attack first": {"block_mult": 0.0, "draw_first": 1.0, "power_first": 1.0},
    "planner": {"policy": "WalkPlanner", "p_random_action": 0.0, "walk_block_value": 4.0, "walk_spare_block": 0.0},
}


def parse_variant(text : str) -> tuple[str, dict]:
    name, _, fields = text.partition("=")
    spec = {}
    for item in filter(None, fields.split(",")):
        key, _, value = item.partition(":")
        spec[key] = value if key == "policy" else json.loads(value)
    return name, spec




def fit(cached : list[dict], args):
    """Per kind of fight: KEEP (the share of the HP a won fight costs that the MCTS also loses) and RESCUE (the chance the MCTS wins a fight the policy lost, by how much
    of the enemy was left, and the HP that win costs as a share of the HP the fight began with)."""
    jobs = [(args.seed, r["i"], "shipped", {}, rep) for r in cached for rep in range(args.reps)]
    runs = map_jobs(policy_job, jobs, args.workers, "policy fights")
    by_case = {r["i"]: r for r in cached}
    groups = {"weak": ("weak", "normal"), "normal": ("weak", "normal"), "elite": ("elite",), "boss": ("boss",)}
    from agents.deck_eval.route_sim import CORRECTION_FILE, LEFT_EDGES          # a lost fight's share of enemy HP left: close / half way / far
    print("# kind: KEEP, RESCUE by (left <= %.2f, <= %.2f, more), RESCUE_COST (n of won pairs / n of lost runs)" % LEFT_EDGES)
    table, kinds = {}, {}
    for kind, members in groups.items():
        rows = [(r, by_case[r["i"]]) for r in runs if by_case[r["i"]]["kind"] in members]
        both = [(r, m) for r, m in rows if r["won"] and m["won"]]
        keep = sum(m["hp_lost"] for r, m in both) / max(1, sum(r["hp_lost"] for r, m in both)) if both else 1.0
        lost = [(r, m) for r, m in rows if not r["won"]]
        rescue = []
        for lo, hi in ((0, LEFT_EDGES[0]), (LEFT_EDGES[0], LEFT_EDGES[1]), (LEFT_EDGES[1], 99)):
            part = [(r, m) for r, m in lost if lo < r["left"] <= hi or (lo == 0 and r["left"] <= hi)]
            rescue.append(round(sum(m["won"] for r, m in part) / len(part), 2) if part else 0.0)
        saved = [m["hp_lost"] / m["hp"] for r, m in lost if m["won"]]
        cost = round(statistics.fmean(saved), 2) if saved else 0.5
        table[kind] = (round(keep, 2), tuple(rescue), cost)
        kinds[kind] = {"keep": round(keep, 2), "rescue": rescue, "rescue_cost": cost, "won_pairs": len(both), "lost_runs": len(lost)}
        print("%-7s keep %.2f  rescue %s  rescue_cost %.2f   (%d / %d)" % (kind, keep, rescue, cost, len(both), len(lost)))
    if args.write:
        data = json.loads(CORRECTION_FILE.read_text())
        data.update(left_edges=list(LEFT_EDGES), kinds=kinds, fitted={"seed": args.seed, "time_budget": args.time_budget, "reps": args.reps, "cases": len(cached)})
        CORRECTION_FILE.write_text(json.dumps(data, indent=2) + "\n")
        print(f"wrote {CORRECTION_FILE}")
    else:
        print("CORRECTION = " + repr(table) + "   (add --write to save it to %s)" % CORRECTION_FILE.name)


def corrected(run : dict, case : dict, roll : float) -> dict:
    """What route_sim.correct makes of one run of the policy on a case (roll: the uniform number that decides a rescue)."""
    from agents.deck_eval import route_sim
    keep, rescue, cost_share = route_sim.CORRECTION.get("weak" if case["kind"] == "normal" else case["kind"], route_sim.CORRECTION["normal"])
    if run["won"]:
        return {"won": True, "hp_lost": round(keep * run["hp_lost"]), "hp": run["hp"]}
    left = run["left"]
    chance = rescue[0 if left <= route_sim.LEFT_EDGES[0] else 1 if left <= route_sim.LEFT_EDGES[1] else 2]
    if roll < chance:
        return {"won": True, "hp_lost": min(run["hp"] - 1, round(cost_share * run["hp"])), "hp": run["hp"]}
    return run


def check(cached : list[dict], args):
    jobs = [(args.seed, r["i"], "shipped", {}, rep) for r in cached for rep in range(args.reps)]
    runs = map_jobs(policy_job, jobs, args.workers, "policy fights")
    by_case = {r["i"]: r for r in cached}
    rolls = random.Random(5)
    out = [(r, by_case[r["i"]], corrected(r, by_case[r["i"]], rolls.random())) for r in runs]
    def line(name, sel):
        part = [(r, m, c) for r, m, c in out if sel(m)]
        if not part:
            return
        ids = sorted({m["i"] for r, m, c in part})
        per = lambda who, f: {i: statistics.fmean(f(x) for x in who if x[1]["i"] == i) for i in ids}
        raw, fixed = per(part, lambda x: cost(x[0])), per(part, lambda x: cost(x[2]))
        mc = {i: cost({"won": by_case[i]["won"], "hp_lost": by_case[i]["hp_lost"], "hp": by_case[i]["hp"]}) for i in ids}
        win = lambda f: 100 * statistics.fmean(f(x) for x in part)
        mw = 100 * statistics.fmean(by_case[i]["won"] for i in ids)
        print("%-8s n=%3d | win raw %3.0f%% fixed %3.0f%% mcts %3.0f%% | cost raw %5.1f fixed %5.1f mcts %5.1f | MAE raw %4.1f fixed %4.1f | rank agr raw %.2f fixed %.2f" % (
            name, len(ids), win(lambda x: x[0]["won"]), win(lambda x: x[2]["won"]), mw, statistics.fmean(raw.values()), statistics.fmean(fixed.values()), statistics.fmean(mc.values()),
            statistics.fmean(abs(raw[i] - mc[i]) for i in ids), statistics.fmean(abs(fixed[i] - mc[i]) for i in ids),
            spearman([raw[i] for i in ids], [mc[i] for i in ids]), spearman([fixed[i] for i in ids], [mc[i] for i in ids])))
    line("all", lambda m: True)
    for kind in ("weak", "normal", "elite", "boss"):
        line(kind, lambda m, k=kind: m["kind"] == k)
    for act in (1, 2, 3):
        line("act %d" % act, lambda m, a=act: m["act"] == a)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mcts")
    m.add_argument("--cases", type=int, default=100)
    m.add_argument("--seed", type=int, default=1)
    m.add_argument("--time-budget", type=float, default=0.1)
    m.add_argument("--workers", type=int, default=default_workers())
    sub.add_parser("collect", help="gather the decks of the runs in data/runs into benchmarks/results/real_decks.json (for --decks)")
    k = sub.add_parser("cards", help="the cards the walk's cheap policy finds good against the MCTS's (implies --decks)")
    k.add_argument("--cases", type=int, default=60)
    k.add_argument("--seed", type=int, default=1)
    k.add_argument("--time-budget", type=float, default=1.0)
    k.add_argument("--reps", type=int, default=3, help="MCTS fights per arm of a case")
    k.add_argument("--policy-reps", type=int, default=30, help="policy fights per arm of a case")
    k.add_argument("--workers", type=int, default=default_workers())
    k.add_argument("--only", help="ask only about these cards (comma separated ids, or `powers`)")
    k.add_argument("--kinds", help="only these kinds of fight (comma separated: weak, normal, elite, boss)")
    mv = sub.add_parser("moves", help="where the cheap policy plays differently from the MCTS, move by move (implies --decks)")
    mv.add_argument("--cases", type=int, default=40)
    mv.add_argument("--seed", type=int, default=1)
    mv.add_argument("--time-budget", type=float, default=1.0)
    mv.add_argument("--samples", type=int, default=20, help="times the policy is asked at each decision")
    mv.add_argument("--workers", type=int, default=default_workers())
    tu = sub.add_parser("tune", help="variants of the policy against the turns of the cached `moves` fights (implies --decks)")
    tu.add_argument("--seed", type=int, default=1)
    tu.add_argument("--time-budget", type=float, default=1.0)
    tu.add_argument("--samples", type=int, default=6)
    tu.add_argument("--workers", type=int, default=default_workers())
    tu.add_argument("--set", action="append", default=[], metavar="NAME=field:value,...")
    s = sub.add_parser("sweep")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--time-budget", type=float, default=0.1)
    s.add_argument("--reps", type=int, default=6)
    s.add_argument("--workers", type=int, default=default_workers())
    c = sub.add_parser("check", help="the shipped policy with route_sim.CORRECTION applied, against the MCTS on these cases (use a seed the fit has not seen)")
    c.add_argument("--seed", type=int, default=2)
    c.add_argument("--time-budget", type=float, default=0.1)
    c.add_argument("--reps", type=int, default=8)
    c.add_argument("--workers", type=int, default=default_workers())
    f = sub.add_parser("fit", help="the numbers of route_sim.CORRECTION: how the shipped policy's fights are turned into the MCTS's")
    f.add_argument("--write", action="store_true", help="save the fitted table to agents/deck_eval/policy_correction.json")
    f.add_argument("--seed", type=int, default=1)
    f.add_argument("--time-budget", type=float, default=0.1)
    f.add_argument("--reps", type=int, default=8)
    f.add_argument("--workers", type=int, default=default_workers())
    s.add_argument("--set", action="append", default=[], metavar="NAME=field:value,...")
    for sub_parser in sub.choices.values():
        if sub_parser.prog.endswith("collect"):
            continue
        sub_parser.add_argument("--stratify", action="store_true", help="cases cycle through the kinds of fight, so the elite and boss rows are fitted on as many as the others")
        sub_parser.add_argument("--decks", nargs="?", const=str(DECKS_FILE), metavar="FILE", help="play real decks (what `collect` wrote) instead of the starter deck and random cards; implies --stratify")
    args = ap.parse_args()
    if args.cmd == "collect":
        return collect(args)
    if args.cmd in ("cards", "moves", "tune") and not args.decks:
        args.decks = str(DECKS_FILE)
    if args.decks:
        args.stratify = True
        os.environ[DECKS_ENV] = args.decks
    if args.stratify:
        os.environ[STRATIFY_ENV] = "1"
    if args.cmd == "cards":
        for env, value in ((ONLY_ENV, args.only), (KINDS_ENV, args.kinds)):
            if value:
                os.environ[env] = value
        return cards(args)
    if args.cmd == "moves":
        return moves(args)
    if args.cmd == "tune":
        return tune(args)
    cache = CACHE_DIR / f"policy_fit_mcts_s{args.seed}_b{args.time_budget}{'_decks' if args.decks else '_strat' if args.stratify else ''}.json"
    CACHE_DIR.mkdir(exist_ok=True)
    cached = json.loads(cache.read_text()) if cache.exists() else []
    if args.cmd == "mcts":
        have = {r["i"] for r in cached}
        todo = [(args.seed, i, args.time_budget) for i in range(args.cases) if i not in have]
        cached += map_jobs(mcts_job, todo, args.workers, "mcts fights")
        cache.write_text(json.dumps(sorted(cached, key=lambda r: r["i"])))
        print(f"{len(cached)} cases in {cache}")
        return
    if not cached:
        raise SystemExit("no MCTS cases: run the `mcts` command first")
    if args.cmd == "fit":
        return fit(cached, args)
    if args.cmd == "check":
        return check(cached, args)
    variants = dict(parse_variant(t) for t in args.set) or VARIANTS
    jobs = [(args.seed, r["i"], name, spec, rep) for name, spec in variants.items() for r in cached for rep in range(args.reps)]
    rows = map_jobs(policy_job, jobs, args.workers, "policy fights")
    by_case = {r["i"]: r for r in cached}
    mc = {i: cost({"won": r["won"], "hp_lost": r["hp_lost"], "hp": r["hp"]}) for i, r in by_case.items()}
    print("MCTS (%d fights, %.2f s/decision): win %.0f%%  mean cost %.1f" % (len(cached), args.time_budget, 100 * statistics.fmean(r["won"] for r in cached), statistics.fmean(mc.values())))
    print("%-14s %6s %9s %8s %6s %9s   %s" % ("variant", "win%", "cost", "bias", "MAE", "rank agr", "win% by act 1/2/3"))
    for name in variants:
        mine = [r for r in rows if r["name"] == name]
        per_case = {i: statistics.fmean(cost(r) for r in mine if r["i"] == i) for i in by_case}
        wins = {i: statistics.fmean(r["won"] for r in mine if r["i"] == i) for i in by_case}
        diffs = [per_case[i] - mc[i] for i in by_case]
        acts = [statistics.fmean(wins[i] for i in by_case if by_case[i]["act"] == a) for a in (1, 2, 3)]
        print("%-14s %5.0f%% %9.1f %+8.1f %6.1f %9.2f   %s" % (name, 100 * statistics.fmean(wins.values()), statistics.fmean(per_case.values()), statistics.fmean(diffs),
              statistics.fmean(abs(d) for d in diffs), spearman([per_case[i] for i in by_case], [mc[i] for i in by_case]), " / ".join("%.0f%%" % (100 * w) for w in acts)))


if __name__ == "__main__":
    main()
