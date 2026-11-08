"""Checks a simulated state against the state the game reports, to find places where the engine drifts from the game."""
from __future__ import annotations
from collections import Counter
from typing import TYPE_CHECKING

import re

from sts2_lite.card import CardId, CardType
from sts2_lite.enemy_moves import SPAWN_HP
from sts2_lite.status import StatusId

if TYPE_CHECKING:
    from sts2_lite.combat import CombatState

# cards whose result depends on something the bridge hides (the draw order) or on the RNG: what they
# generate or play cannot be predicted, so their mismatches are tagged rather than trusted
RANDOM_CARDS = frozenset({CardId.INFERNAL_BLADE, CardId.STOKE, CardId.HAVOC, CardId.SEEKER_STRIKE, CardId.JACKPOT, CardId.JACK_OF_ALL_TRADES,
                          CardId.CATASTROPHE, CardId.BEAT_DOWN, CardId.ANOINTED, CardId.DISCOVERY, CardId.HIDDEN_GEM})


def _statuses(creature) -> dict[str, int]:
    return {s.name: inst.amount for s, inst in creature.status.items()}

def _cards(pile) -> Counter:
    return Counter((c.card_id.name + (f"[{c.enchantment.name}]" if c.enchantment else ""), c.is_upgraded) for c in pile)

def snapshot(cs : CombatState) -> dict:
    """The comparable parts of a state as plain data (also what a log entry stores)."""
    p = cs.player
    return {
        "round": cs.turn_number,
        "energy": cs.energy,
        "player": {"hp": p.current_hp, "max_hp": p.max_hp, "block": p.block, "status": _statuses(p)},
        "relics": {r.name: {"counter": inst.counter, "used": inst.used} for r, inst in p.relics.items()},
        "hand": sorted((c.card_id.name, c.is_upgraded, c.energy_cost, c.enchantment.name if c.enchantment else None) for c in p.hand),
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
            if card is not None and (card.card_id in RANDOM_CARDS or (card.type == CardType.Attack and StatusId.CALAMITY in before.player.status)):
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

def _fresh_spawn_hp_is_random(pe, ae) -> bool:
    """A monster that has just appeared with unhurt, in-range HP (Wriggler 17-21): the game rolled it, the sim sampled its own."""
    spawn = SPAWN_HP.get(re.sub(r"_\d+$", "", str(ae.enemy_id)))
    if spawn is None:
        return False
    low, high = min(spawn), max(spawn)
    return all(e.current_hp == e.max_hp and low <= e.current_hp <= high for e in (pe, ae))

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
        if pe.current_hp != ae.current_hp and not _fresh_spawn_hp_is_random(pe, ae):
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
        sim_costs = Counter((c.card_id.name, c.current_cost(pp)) for c in pp.hand)
        game_costs = Counter((c.card_id.name, c.current_cost(ap)) for c in ap.hand)
        diffs += _multiset_diff("hand costs", sim_costs, game_costs)
    return diffs
