"""What each Ironclad card does when it is played, measured on the engine itself: written to agents/deck_eval/card_profile.json, which the walk's rollout policy weighs cards by.

Each card is played once from a standard hand (the card, two Strikes, two Defends; ten more in the draw pile) against three 300 HP enemies with nothing on them, with 3 energy:
  damage   HP taken off the first enemy;  all   the same summed over every enemy (an attack on all enemies);  block   the player's block;  draw   cards the play put in the hand
  energy   energy gained;  vuln / weak   Vulnerable / Weak put on the first enemy;  strength   Strength the player gained;  hp   HP the player lost;  power   a Power
  cost     its energy cost (X-cost cards: 3, what a play of them spends)   target   its target type
Usage (from scripts/):  python -m benchmarks.profile_cards"""
from __future__ import annotations
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

OUT = SCRIPTS_DIR / "agents" / "deck_eval" / "card_profile.json"


def profile(entry : dict, upgraded : bool) -> dict | None:
    from sts2_lite.card import Card, CardId, CardType, TargetType
    from sts2_lite.combat import CombatSimulator, CombatState
    from sts2_lite.Tests.card.test_card import make_card, make_enemy
    from sts2_lite.player import Player
    from sts2_lite.status import StatusId
    try:
        from agents.deck_eval.fight_builder import card_dict
        card = Card.from_dict(card_dict(entry, {}))
        if upgraded:
            if not card.is_upgradable:
                return None
            card = card.upgraded_copy()
        strike = lambda: make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)
        defend = lambda: make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.NONE)
        player = Player()
        player.max_hp = player.current_hp = 50
        player.hand = [card, strike(), strike(), defend(), defend()]
        player.draw_pile = [strike() if i % 2 else defend() for i in range(10)]
        cs = CombatState()
        cs.player = player
        cs.enemies = [make_enemy(300, f"E{i}") for i in range(3)]
        cs.energy = cs.max_energy = 3
        cs.turn_number = 1
        sim = CombatSimulator(cs)
        if card.unplayable or card.is_unplayable or not card.can_play_card(sim, 0):
            return {"playable": False}
        cost = 3 if card.energy_cost == "X" else card.energy_cost
        before_hand = len(player.hand)
        sim.play_card(0, 0)
        foes = cs.enemies
        status = lambda who, sid: who.status_amount(sid) if who.status_amount(sid) else 0
        return {"playable": True, "cost": cost, "damage": 300 - foes[0].current_hp, "all": sum(300 - e.current_hp for e in foes),
                "block": player.block, "draw": max(0, len(player.hand) - (before_hand - 1)), "energy": max(0, cs.energy - (3 - cost)),
                "vuln": status(foes[0], StatusId.VULNERABLE), "weak": status(foes[0], StatusId.WEAK), "strength": status(player, StatusId.STRENGTH),
                "hp": 50 - player.current_hp, "power": card.type == CardType.Power, "target": card.target_type.name}
    except Exception as error:
        return {"playable": False, "error": "%s: %s" % (type(error).__name__, str(error)[:80])}


def main():
    from sts2_lite.card import CardId
    from agents.deck_eval.future_cards import CARD_POOL
    basics = [{"id": "STRIKE_IRONCLAD", "name": "Strike", "type": "Attack", "cost": 1, "target_type": "AnyEnemy"},
              {"id": "DEFEND_IRONCLAD", "name": "Defend", "type": "Skill", "cost": 1, "target_type": "Self"},
              {"id": "BASH", "name": "Bash", "type": "Attack", "cost": 2, "target_type": "AnyEnemy"}]
    entries = {c["id"]: c for cards in CARD_POOL.values() for c in cards} | {c["id"]: c for c in basics}
    table = {}
    for name in sorted(entries):
        for upgraded in (False, True):
            p = profile(entries[name], upgraded)
            if p is not None:
                table[f"{name}{'+' if upgraded else ''}"] = p
    OUT.write_text(json.dumps(table, indent=1, sort_keys=True) + "\n")
    bad = [k for k, v in table.items() if "error" in v]
    print(f"{len(table)} cards profiled into {OUT}; {len(bad)} failed: {bad}")


if __name__ == "__main__":
    main()
