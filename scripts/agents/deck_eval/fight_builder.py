"""A fresh round-1 fight of a template with the player's own deck, hp and relics (approximation: no combat-start relic effects)."""
from __future__ import annotations
import copy

from sts2_lite import rng
from sts2_lite.combat import CombatState, CombatSimulator

from agents.deck_eval.fight_pool import FightTemplate

BASE_ENERGY = 3
UNPLAYABLE_TYPES = ("Curse", "Status")


def card_dict(card : dict, target_types : dict[str, str]) -> dict:
    ctype = card.get("type", "Skill")
    target = card.get("target_type") or target_types.get(card["id"]) or ("AnyEnemy" if ctype == "Attack" else "Self")
    return {"id": card["id"], "name": card.get("name", card["id"]), "type": ctype, "cost": card.get("cost", 1),
            "star_cost": card.get("star_cost"), "description": card.get("description", ""), "target_type": target,
            "can_play": ctype not in UNPLAYABLE_TYPES, "unplayable_reason": None, "is_upgraded": bool(card.get("is_upgraded")),
            "generated": False, "enchantment": card.get("enchantment"), "keywords": [], "_upgrade": bool(card.get("_upgrade"))}


def build_fight(template : FightTemplate, deck : list[dict], player : dict, target_types : dict[str, str]) -> CombatSimulator:
    """Round 1, player turn started: `deck` (card dicts) shuffled into the draw pile and the opening hand drawn."""
    state = copy.deepcopy(template.state)
    me = state["player"]
    cards = [card_dict(c, target_types) for c in deck]
    me.update(hp=player["hp"], max_hp=player["max_hp"], block=0, status=[], hand=[], draw_pile=cards, discard_pile=[], exhaust_pile=[],
              relics=copy.deepcopy(player.get("relics", [])), potions=[], energy=BASE_ENERGY, max_energy=BASE_ENERGY,
              draw_pile_count=len(cards), discard_pile_count=0, exhaust_pile_count=0)
    state["energy"], state["max_energy"] = BASE_ENERGY, BASE_ENERGY
    state.pop("battle", None)
    cs = CombatState.from_dict(state)
    for i, raw in enumerate(cards):     # a card marked "_upgrade" is the upgraded one: the sim's own upgrade (cost, keywords, name)
        if raw["_upgrade"] and cs.player.draw_pile[i].is_upgradable:
            cs.player.draw_pile[i] = cs.player.draw_pile[i].upgraded_copy()
    cs.player.shuffle_draw_pile()
    sim = CombatSimulator(cs)
    sim._start_player_turn(enemies_start=False)
    return sim
