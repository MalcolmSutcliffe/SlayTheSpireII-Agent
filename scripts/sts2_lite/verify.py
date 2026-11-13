"""Checks a simulated state against the state the game reports, to find places where the engine drifts from the game."""
from __future__ import annotations
from collections import Counter
from typing import TYPE_CHECKING

import re

from sts2_lite.card import CardId, CardType, COLORLESS_CARDS, ZERO_COST_POOL, STOKE_POOL
from sts2_lite.enemy_moves import HATCHLING_HP, SPAWN_HP, TOUGH_ASCENSION
from sts2_lite.status import StatusId

if TYPE_CHECKING:
    from sts2_lite.combat import CombatState

# cards whose result depends on something the bridge hides (the draw order) or on the RNG: what they
# generate or play cannot be predicted, so their mismatches are tagged rather than trusted
RANDOM_CARDS = frozenset({CardId.INFERNAL_BLADE, CardId.STOKE, CardId.HAVOC, CardId.SEEKER_STRIKE, CardId.JACKPOT, CardId.JACK_OF_ALL_TRADES,
                          CardId.CATASTROPHE, CardId.BEAT_DOWN, CardId.ANOINTED, CardId.DISCOVERY, CardId.HIDDEN_GEM, CardId.ALCHEMIZE,
                          CardId.CINDER, CardId.THRASH, CardId.METAMORPHOSIS})       # Cinder / Thrash exhaust a random card
# random only when not upgraded: the upgrade lets the player choose the card to exhaust
RANDOM_UNLESS_UPGRADED = frozenset({CardId.TRUE_GRIT})


def _statuses(creature) -> dict[str, int]:
    return {s.name: inst.shown_amount for s, inst in creature.status.items()}

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
            if card is not None and (card.card_id in RANDOM_CARDS or (card.card_id in RANDOM_UNLESS_UPGRADED and not card.is_upgraded)
                                     or (card.type == CardType.Attack and StatusId.CALAMITY in before.player.status)):
                return True
    return False

def is_unpredictable_step(before : CombatState, actions : list[dict]) -> bool:
    """True when the step played a card whose result the sim cannot know: Havoc plays the top card of the draw pile, and unless
    the agent knows that card (`known_top`) the game's choice is a different one than the sim's guess; Stampede picks a random Attack."""
    for a in actions:
        if a["action"] == "play_card" and a["card_index"] < len(before.player.hand):
            if before.player.hand[a["card_index"]].card_id == CardId.HAVOC and before.player.known_top == 0:
                return True
        if a["action"] == "end_turn" and StatusId.STAMPEDE in before.player.status:
            # Stampede plays a random Attack of the hand as the turn ends: with more than one kind in hand the game's pick is not the sim's
            attacks = {c.card_id for c in before.player.hand if c.type == CardType.Attack and not c.unplayable}
            if len(attacks) > 1:
                return True
    return False

def some_target_roll_matches(before : CombatState, actions : list[dict], actual : CombatState, random_step : bool, tries : int = 300) -> bool:
    """Random targets change how much damage is done when the enemies differ (Vulnerable on one of them), so the totals alone are not
    enough: replay the actions with fresh random targets until one outcome matches the game exactly."""
    from sts2_lite.combat import CombatState, CombatSimulator
    for _ in range(tries):
        replay = CombatState.deepcopy(before)
        simulator = CombatSimulator(replay)
        for action in actions:
            simulator.perform_action(action)
        if not compare(replay, actual, random_step=random_step):
            return True
    return False

def _summed_enemy_diffs(predicted : CombatState, actual : CombatState) -> list[str]:
    out = []
    for field, get in (("hp", lambda e: e.current_hp), ("block", lambda e: e.block)):
        a, b = sum(get(e) for e in predicted.enemies), sum(get(e) for e in actual.enemies)
        if a != b:
            out.append(f"enemies' total {field}: sim {a}, game {b}")
    def total(cs):
        sums : dict[str, int] = {}
        for e in cs.enemies:
            for name, amount in _statuses(e).items():
                sums[name] = sums.get(name, 0) + amount
        return sums
    out += _dict_diff("enemies' total status", total(predicted), total(actual))
    return out

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

def _fresh_spawn_hp_is_random(pe, ae, ascension : int = 0) -> bool:
    """A monster that has just appeared with unhurt, in-range HP (Wriggler 17-21, 18-22 from Ascension 8): the game rolled it, the sim sampled its own."""
    spawn = SPAWN_HP.get(re.sub(r"_\d+$", "", str(ae.enemy_id)))
    if spawn is None:
        return False
    low, high = spawn[2:] if ascension >= TOUGH_ASCENSION else spawn[:2]
    if str(ae.enemy_id).startswith("TOUGH_EGG"):
        hatchling = HATCHLING_HP[1 if ascension >= TOUGH_ASCENSION else 0]
        low, high = min(low, *hatchling), max(high, *hatchling)     # a hatched egg keeps its id, with a hatchling's HP
    # the rolled max HP differs, the damage taken since the spawn (max - current) must not
    # (a Wriggler hit by the rest of a Whirlwind on the turn it appeared)
    return all(low <= e.max_hp <= high for e in (pe, ae)) and pe.max_hp - pe.current_hp == ae.max_hp - ae.current_hp

def compare(predicted : CombatState, actual : CombatState, random_step : bool = False, random_target : bool = False) -> list[str]:
    """Differences between the simulated state and the game's. With `random_step` only what no draw
    or shuffle can change is checked as exact: the cards the player owns in total and the exhaust pile
    (a random exhaust that took another card of the same deck is not a difference). With `random_target` and several enemies the sim
    and the game hit different ones: hit points, block and statuses are compared summed over the enemies instead of one by one."""
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
    if random_target and len(predicted.enemies) > 1 and len(predicted.enemies) == len(actual.enemies):
        diffs += _summed_enemy_diffs(predicted, actual)
    for i, (pe, ae) in enumerate(zip(predicted.enemies, actual.enemies)):
        if random_target and len(predicted.enemies) > 1 and len(predicted.enemies) == len(actual.enemies):
            break
        label = f"enemy {i} ({ae.enemy_id})"
        if pe.current_hp != ae.current_hp and not _fresh_spawn_hp_is_random(pe, ae, predicted.ascension):
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
    if random_step and any(d.startswith("cards owned") for d in diffs) and any(d.startswith("exhaust pile") for d in diffs) \
            and everything(pp) + _cards(pp.exhaust_pile) == everything(ap) + _cards(ap.exhaust_pile):
        # a random exhaust (Cinder, Havoc, True Grit) took a different card: the same deck, split differently between the piles
        diffs = [d for d in diffs if not d.startswith(("cards owned", "exhaust pile"))]
    if random_step and any(d.startswith("cards owned") for d in diffs):
        # Jack of All Trades / Jackpot generate random colorless cards, Stoke random Ironclad ones: the same number of cards, but a different pick
        sim_owned, game_owned = everything(pp), everything(ap)
        extra_cards = (sim_owned - game_owned) + (game_owned - sim_owned)
        pool = set(COLORLESS_CARDS) | set(ZERO_COST_POOL) | set(STOKE_POOL)
        if sum(sim_owned.values()) == sum(game_owned.values()) and all(CardId[name.split("[")[0]] in pool for name, _ in extra_cards):
            diffs = [d for d in diffs if not d.startswith("cards owned")]
    if random_step and predicted.energy != actual.energy:
        # Drum of Battle gives energy when it is exhausted: a random exhaust (Toasty Mittens off a reshuffled pile) that took it in the
        # sim but another card in the game (or the reverse) moves the energy by what the Drum gives
        drum = lambda p: sum((3 if c.is_upgraded else 2) for c in p.exhaust_pile if c.card_id == CardId.DRUM_OF_BATTLE)
        if predicted.energy - actual.energy == drum(pp) - drum(ap) != 0:
            diffs = [d for d in diffs if not d.startswith("player energy")]
    if random_step and StatusId.HELLRAISER in {**pp.status, **ap.status} and _cards(pp.hand) != _cards(ap.hand):
        # Hellraiser plays every Strike the moment it is drawn: a different random draw means different Strikes were played,
        # so the damage dealt, what the enemies then did and the counters of the relics that count plays all diverge
        diffs = [d for d in diffs if not d.startswith(("player hp", "player block", "player energy", "enemy", "relic"))]
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
