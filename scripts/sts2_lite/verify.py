"""Checks a simulated state against the state the game reports, to find places where the engine drifts from the game."""
from __future__ import annotations
from collections import Counter
from typing import TYPE_CHECKING

from sts2_lite.card import CardId

if TYPE_CHECKING:
    from sts2_lite.combat import CombatState

# cards whose result depends on something the bridge hides (the draw order) or on the RNG: what they
# generate or play cannot be predicted, so their mismatches are tagged rather than trusted
RANDOM_CARDS = frozenset({CardId.INFERNAL_BLADE, CardId.STOKE, CardId.HAVOC})


def _statuses(creature) -> dict[str, int]:
    return {s.name: inst.amount for s, inst in creature.status.items()}

def _cards(pile) -> Counter:
    return Counter((c.card_id.name, c.is_upgraded) for c in pile)

def snapshot(cs : CombatState) -> dict:
    """The comparable parts of a state as plain data (also what a log entry stores)."""
    p = cs.player
    return {
        "round": cs.turn_number,
        "energy": cs.energy,
        "player": {"hp": p.current_hp, "max_hp": p.max_hp, "block": p.block, "status": _statuses(p)},
        "relics": {r.name: {"counter": inst.counter, "used": inst.used} for r, inst in p.relics.items()},
        "hand": sorted((c.card_id.name, c.is_upgraded, c.energy_cost) for c in p.hand),
        "draw": sorted(f"{i}{'+' if u else ''}" for (i, u) in _cards(p.draw_pile).elements()),
        "discard": sorted(f"{i}{'+' if u else ''}" for (i, u) in _cards(p.discard_pile).elements()),
        "exhaust": sorted(f"{i}{'+' if u else ''}" for (i, u) in _cards(p.exhaust_pile).elements()),
        "enemies": [{"id": str(e.enemy_id), "hp": e.current_hp, "block": e.block, "status": _statuses(e)} for e in cs.enemies],
    }

def is_random_step(before : CombatState, predicted : CombatState, actions : list[dict]) -> bool:
    """True when the simulated step involved a draw, a shuffle, an enemy turn or a random card, so hand
    contents (and what follows from them) legitimately differ from the real game."""
    if any(a["action"] == "end_turn" for a in actions):
        return True
    if len(before.player.draw_pile) != len(predicted.player.draw_pile):
        return True
    for a in actions:
        if a["action"] == "play_card":
            card = before.player.hand[a["card_index"]] if a["card_index"] < len(before.player.hand) else None
            if card is not None and card.card_id in RANDOM_CARDS:
                return True
    return False

def _multiset_diff(name : str, expected : Counter, actual : Counter) -> list[str]:
    out = []
    missing, extra = expected - actual, actual - expected
    if missing or extra:
        out.append(f"{name}: sim has {dict(missing) or '-'} that the game lacks; game has {dict(extra) or '-'} that the sim lacks")
    return out

def _dict_diff(name : str, expected : dict, actual : dict) -> list[str]:
    out = []
    for key in sorted(set(expected) | set(actual)):
        if expected.get(key, 0) != actual.get(key, 0):
            out.append(f"{name} {key}: sim {expected.get(key, 0)}, game {actual.get(key, 0)}")
    return out

def compare(predicted : CombatState, actual : CombatState, random_step : bool = False) -> list[str]:
    """Differences between the simulated state and the game's. With `random_step` only what no draw
    or shuffle can change is checked as exact: the cards the player owns in total and the exhaust pile."""
    diffs : list[str] = []
    pp, ap = predicted.player, actual.player
    for field, a, b in (("hp", pp.current_hp, ap.current_hp), ("max hp", pp.max_hp, ap.max_hp),
                        ("block", pp.block, ap.block), ("energy", predicted.energy, actual.energy),
                        ("round", predicted.turn_number, actual.turn_number)):
        if a != b:
            diffs.append(f"player {field}: sim {a}, game {b}")
    diffs += _dict_diff("player status", _statuses(pp), _statuses(ap))

    if len(predicted.enemies) != len(actual.enemies):
        diffs.append(f"enemy count: sim {len(predicted.enemies)}, game {len(actual.enemies)}")
    for i, (pe, ae) in enumerate(zip(predicted.enemies, actual.enemies)):
        label = f"enemy {i} ({ae.enemy_id})"
        if pe.current_hp != ae.current_hp:
            diffs.append(f"{label} hp: sim {pe.current_hp}, game {ae.current_hp}")
        if pe.block != ae.block:
            diffs.append(f"{label} block: sim {pe.block}, game {ae.block}")
        diffs += _dict_diff(f"{label} status", _statuses(pe), _statuses(ae))

    for relic, inst in pp.relics.items():
        other = ap.relics.get(relic)
        if other is None:
            diffs.append(f"relic {relic.name}: in the sim but not loaded from the game")
        elif inst.counter != other.counter or inst.used != other.used:
            diffs.append(f"relic {relic.name}: sim counter {inst.counter} used {inst.used}, game counter {other.counter} used {other.used}")

    everything = lambda p: _cards(p.hand) + _cards(p.draw_pile) + _cards(p.discard_pile)
    diffs += _multiset_diff("cards owned (hand+draw+discard)", everything(pp), everything(ap))
    diffs += _multiset_diff("exhaust pile", _cards(pp.exhaust_pile), _cards(ap.exhaust_pile))
    if len(pp.hand) != len(ap.hand) and not random_step:
        diffs.append(f"hand size: sim {len(pp.hand)}, game {len(ap.hand)}")
    if not random_step:
        diffs += _multiset_diff("hand", _cards(pp.hand), _cards(ap.hand))
        diffs += _multiset_diff("discard pile", _cards(pp.discard_pile), _cards(ap.discard_pile))
        diffs += _multiset_diff("draw pile", _cards(pp.draw_pile), _cards(ap.draw_pile))
        sim_costs = Counter((c.card_id.name, c.energy_cost) for c in pp.hand)
        game_costs = Counter((c.card_id.name, c.energy_cost) for c in ap.hand)
        diffs += _multiset_diff("hand costs", sim_costs, game_costs)
    return diffs
