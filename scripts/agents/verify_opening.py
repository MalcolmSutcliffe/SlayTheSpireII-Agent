"""Checks the opening of a fight: the sim opens the same fight from the game's own deck, hp and relics (agents.deck_eval.fight_builder,
sts2_lite/relic/combat_start.py) and the result is compared with the first state the game reports. A difference is a start-of-combat
relic or an Innate card the sim gets wrong (or does not know)."""
from __future__ import annotations
import copy
from collections import Counter

from agents.deck_eval.fight_builder import build_fight
from agents.deck_eval.fight_pool import FightTemplate
from agents.verify import compare
from sts2_lite.card.ids import CardKeyword
from sts2_lite.combat import CombatState
from sts2_lite.relic.combat_start import BLOCK, HEAL, PANTOGRAPH_HEAL, ROYAL_POISON_DAMAGE, Opening

TEA_SET_ENERGY = 2
RANDOM_CARD_RELICS = frozenset({"ORANGE_DOUGH", "VEXING_PUZZLEBOX", "BIG_HAT"})     # they add a random card: the sim's pick is not the game's


def deck_of(game_state : dict) -> list[dict]:
    """Every card the player brought into the fight: the piles at round 1 (a card Toasty Mittens exhausted is still the deck's), minus what a relic made."""
    me = game_state["player"]
    return [dict(c) for pile in ("hand", "draw_pile", "discard_pile", "exhaust_pile") for c in me.get(pile) or [] if not c.get("generated")]

def hp_before_opening(game_state : dict, opening : Opening) -> int:
    """The hp the player walked in with: what the opening relics healed or took is taken back off (at full hp the heal is capped, which is the same)."""
    me = game_state["player"]
    net = sum(amount for relic, amount in HEAL.items() if opening.has(relic))
    net -= ROYAL_POISON_DAMAGE if opening.has("ROYAL_POISON") else 0
    net += PANTOGRAPH_HEAL if opening.boss and opening.has("PANTOGRAPH") else 0
    return max(1, me["hp"] - net)

TURN_COUNTED = {"PENDULUM": 3, "POLLINOUS_CORE": 4}      # relic -> turns in its cycle: their counter in the game's first state already counts the first turn

def counters_before_opening(relics : list[dict]) -> list[dict]:
    """The relics as they were before the fight's first turn started: the game's first state shows the counters after it."""
    out = copy.deepcopy(relics)
    for r in out:
        if r["id"] in TURN_COUNTED and r.get("counter") is not None:
            r["counter"] = (r["counter"] - 1) % TURN_COUNTED[r["id"]]
    return out

def simulated_opening(game_state : dict) -> CombatState:
    """The sim's round 1 for the fight of this game state, built from the game's deck, hp and relics."""
    me = game_state["player"]
    room = game_state.get("room_type") or "monster"
    template = FightTemplate("live", (game_state.get("context") or game_state.get("run") or {}).get("act", 1), room, game_state)
    relics = counters_before_opening(me.get("relics") or [])
    opening = Opening(relics, room)
    player = {"hp": hp_before_opening(game_state, opening), "max_hp": me["max_hp"], "relics": relics}
    return build_fight(template, deck_of(game_state), player, {}).combat_state

def _innate_in_hand(cs : CombatState) -> Counter:
    return Counter(c.card_id.name for c in cs.player.hand if CardKeyword.INNATE in c.keywords)

def opening_diffs(game_state : dict) -> tuple[list[str], CombatState, CombatState]:
    """(differences, the sim's opening, the game's state read into the sim)."""
    actual = CombatState.from_dict(game_state)
    predicted = simulated_opening(game_state)
    diffs = [d for d in compare(predicted, actual, random_step=True) if not d.startswith("relic ")]     # counters of relics that count turn-start draws are read after them
    if any(r.get("id") in RANDOM_CARD_RELICS and r.get("status") != "Disabled" for r in game_state["player"].get("relics") or []):
        diffs = [d for d in diffs if not d.startswith("cards owned")]
    owned = {r.get("id") for r in game_state["player"].get("relics") or [] if r.get("status") != "Disabled"}
    if "VENERABLE_TEA_SET" in owned and actual.energy - predicted.energy == TEA_SET_ENERGY:
        diffs = [d for d in diffs if not d.startswith("player energy")]       # its flag (a rest site was just used) is not in the state
    enemy_ids = {str(e.enemy_id) for e in actual.enemies}
    if any(i.startswith("AEONGLASS") for i in enemy_ids):
        diffs = [d for d in diffs if d != "player status NO_DRAW: sim 0, game 1"]      # the boss puts it on you as the fight starts
    if len(predicted.player.hand) != len(actual.player.hand):
        diffs.append(f"opening hand size: sim {len(predicted.player.hand)}, game {len(actual.player.hand)}")
    sim_innate, game_innate = _innate_in_hand(predicted), _innate_in_hand(actual)
    if sim_innate != game_innate:
        diffs.append(f"Innate cards in the opening hand: sim {dict(sim_innate)}, game {dict(game_innate)}")
    return diffs, predicted, actual
