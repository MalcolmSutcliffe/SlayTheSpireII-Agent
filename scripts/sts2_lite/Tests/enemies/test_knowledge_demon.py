"""Knowledge Demon: the curse pick and the four curses' powers. Run from scripts/: python -m pytest sts2_lite"""
import json
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.status import StatusId
from sts2_lite.Tests import captures
from sts2_lite.Tests.test_cards import make_card
from sts2_lite.Tests.enemies.test_hive_simple import at, moves_over, turn


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)

def strike():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def defend():
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.Self)

def demon(move="CURSE_OF_KNOWLEDGE", log=None):
    cs = at("KNOWLEDGE_DEMON", move, log=log)
    cs.player.draw_pile = [strike() for _ in range(12)]
    return cs

def end_turn_to_curse(cs):
    sim = CombatSimulator(cs)
    sim.end_turn()
    return sim

def offered(cs):
    return [c.card_id for c in cs.pending_choice.offers]


def test_values():
    t = MOVE_TABLES["KNOWLEDGE_DEMON"](0)
    assert (t["SLAP"].damage, t["KNOWLEDGE_OVERWHELMING"].damage, t["KNOWLEDGE_OVERWHELMING"].hits, t["PONDER"].damage, t["PONDER"].heal) == (17, 8, 3, 11, 30)
    t = MOVE_TABLES["KNOWLEDGE_DEMON"](10)
    assert (t["SLAP"].damage, t["KNOWLEDGE_OVERWHELMING"].damage, t["PONDER"].damage, t["PONDER"].self_status) == (18, 9, 13, ((StatusId.STRENGTH, 3),))

def test_the_cycle_casts_three_curses_then_stops():
    cs = demon()
    sim = CombatSimulator(cs)
    seen = []
    for _ in range(14):
        seen.append(cs.enemies[0].move_id)
        cs.player.current_hp = 500
        cs.player.block = 0
        sim._play_enemy_turn()
        if cs.pending_choice is not None:
            sim.choose_card(0)
    assert seen[:9] == ["CURSE_OF_KNOWLEDGE", "SLAP", "KNOWLEDGE_OVERWHELMING", "PONDER",
                        "CURSE_OF_KNOWLEDGE", "SLAP", "KNOWLEDGE_OVERWHELMING", "PONDER", "CURSE_OF_KNOWLEDGE"]
    assert seen[9:13] == ["SLAP", "KNOWLEDGE_OVERWHELMING", "PONDER", "SLAP"]      # after the third there are no more

def test_ending_the_turn_waits_for_the_pick():
    cs = demon()
    sim = end_turn_to_curse(cs)
    assert cs.pending_choice is not None and cs.pending_choice.kind == "curse"
    assert offered(cs) == [CardId.DISINTEGRATION, CardId.MIND_ROT]
    assert cs.player.hand == []         # the next turn has not started
    with pytest.raises(Exception):
        sim.end_turn()
    sim.choose_card(1)
    assert cs.pending_choice is None
    assert len(cs.player.hand) == 4     # Mind Rot: one card fewer
    assert cs.player.status_amount(StatusId.MIND_ROT) == 1
    assert cs.turn_number == 2

def test_the_counter_picks_the_set_and_disintegration_grows():
    expected = [([CardId.DISINTEGRATION, CardId.MIND_ROT], 6), ([CardId.DISINTEGRATION, CardId.SLOTH], 7), ([CardId.DISINTEGRATION, CardId.WASTE_AWAY], 8)]
    for counter, (cards, damage) in enumerate(expected):
        log = ["CURSE_OF_KNOWLEDGE_MOVE", "SLAP_MOVE", "KNOWLEDGE_OVERWHELMING_MOVE", "PONDER_MOVE"] * counter + ["CURSE_OF_KNOWLEDGE_MOVE"]
        cs = demon(log=log)
        assert cs.enemies[0].counter == counter
        end_turn_to_curse(cs)
        assert offered(cs) == cards
        CombatSimulator(cs).choose_card(0)
        assert cs.player.status_amount(StatusId.DISINTEGRATION) == damage

def test_disintegration_deals_its_amount_at_the_end_of_the_turn():
    cs = demon("SLAP")
    cs.player.status[StatusId.DISINTEGRATION] = __import__("sts2_lite.status", fromlist=["StatusInstance"]).StatusInstance(StatusId.DISINTEGRATION, 6)
    cs.player.block = 0
    hp = cs.player.current_hp
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.player.current_hp == hp - 6 - 17

def test_sloth_allows_three_cards_a_turn():
    cs = demon("SLAP")
    cs.player.hand = [defend() for _ in range(5)]
    cs.energy = cs.max_energy = 5
    cs.player.apply_status(StatusId.SLOTH, 3)
    sim = CombatSimulator(cs)
    for _ in range(3):
        sim.play_card(0, 0)
    assert not cs.player.hand[0].can_play_card(sim, 0)
    assert all(a["action"] == "end_turn" for a in sim.get_available_actions())
    sim.end_turn()
    assert cs.cards_played == 0

def test_waste_away_costs_an_energy_every_turn():
    log = ["CURSE_OF_KNOWLEDGE_MOVE", "SLAP_MOVE", "KNOWLEDGE_OVERWHELMING_MOVE", "PONDER_MOVE"] * 2 + ["CURSE_OF_KNOWLEDGE_MOVE"]
    cs = demon(log=log)
    sim = end_turn_to_curse(cs)
    sim.choose_card(1)
    assert cs.player.status_amount(StatusId.WASTE_AWAY) == 1
    assert (cs.energy, cs.max_energy) == (2, 2)       # the bridge reports the reduced maximum too

def test_sloth_from_the_bridge_is_the_cards_played_not_the_limit():
    from sts2_lite.Tests.enemies.test_bridge_moves import attack, load, raw_enemy
    cs = load(raw_enemy("KNOWLEDGE_DEMON", "SLAP_MOVE", ["SLAP_MOVE"], attack(17)), player_status=[{"id": "SLOTH_POWER", "amount": 2}])
    assert cs.player.status_amount(StatusId.SLOTH) == 3
    assert cs.cards_played == 2

def test_ponder_heals_and_strengthens():
    cs = demon("PONDER", log=["CURSE_OF_KNOWLEDGE_MOVE", "SLAP_MOVE", "KNOWLEDGE_OVERWHELMING_MOVE", "PONDER_MOVE"])
    cs.enemies[0].current_hp = 100
    cs.enemies[0].max_hp = 379
    turn(cs)
    assert cs.enemies[0].current_hp == 130
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2
    assert cs.enemies[0].move_id == "CURSE_OF_KNOWLEDGE"

def test_the_demon_after_the_last_curse_slaps():
    log = ["CURSE_OF_KNOWLEDGE_MOVE", "SLAP_MOVE", "KNOWLEDGE_OVERWHELMING_MOVE", "PONDER_MOVE"] * 3
    cs = demon("PONDER", log=log)
    turn(cs)
    assert cs.enemies[0].move_id == "SLAP"

def test_the_pick_screen_matches_the_first_offer():
    d = json.loads((captures.DATA / captures.HIVE / "knowledge_demon" / "curse_choice_screen.json").read_text()) if hasattr(captures, "DATA") else None
    cs = demon()
    end_turn_to_curse(cs)
    if d is not None:
        shown = [c["id"] for c in d["cards"]]
        assert shown == [c.name for c in offered(cs)]


def test_capture_with_mind_rot_and_sloth():
    cs = captures.load("knowledge_demon", "mind_rot_sloth", captures.HIVE)
    assert cs.enemies[0].counter == 2 and cs.enemies[0].move_id == "SLAP"
    assert cs.player.status_amount(StatusId.MIND_ROT) == 1
    assert cs.player.status_amount(StatusId.SLOTH) == 3 and cs.cards_played == 1
    assert (cs.energy, cs.max_energy) == (2, 3)

def test_waste_away_in_a_loaded_state_is_not_taken_off_twice():
    from sts2_lite.Tests.enemies.test_bridge_moves import attack, load, raw_enemy
    cs = load(raw_enemy("KNOWLEDGE_DEMON", "SLAP_MOVE", ["SLAP_MOVE"], attack(17)), player_status=[{"id": "WASTE_AWAY_POWER", "amount": 1}])
    cs.max_energy = 2
    CombatSimulator(cs).end_turn()
    assert cs.energy == 2
