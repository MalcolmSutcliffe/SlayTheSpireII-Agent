"""Act 3 (Glory) elites: Soul Nexus, Mecha Knight, and the Flail, Spectral and Magi Knights.
Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.status import StatusId, StatusInstance
from sts2_lite.Tests.enemies.test_bridge_moves import attack, raw_enemy
from sts2_lite.Tests.enemies.test_glory_simple import at, moves_over, status, turn
from sts2_lite.Tests.enemies.test_hive_simple import defend, make_card, strike


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)

def other(monster, move, intents, hp=100):
    raw = raw_enemy(monster, move, [move], intents)
    raw["hp"] = raw["max_hp"] = hp
    return raw

def upgraded_strike():
    c = strike()
    c.is_upgraded = True
    return c


@pytest.mark.parametrize("monster, move, base, deadly, hits", [
    ("SOUL_NEXUS", "SOUL_BURN", 29, 31, 1), ("SOUL_NEXUS", "MAELSTROM", 6, 7, 4), ("SOUL_NEXUS", "DRAIN_LIFE", 18, 19, 1),
    ("MECHA_KNIGHT", "CHARGE", 25, 30, 1), ("MECHA_KNIGHT", "HEAVY_CLEAVE", 35, 40, 1),
    ("FLAIL_KNIGHT", "FLAIL", 9, 10, 2), ("FLAIL_KNIGHT", "RAM", 15, 17, 1),
    ("SPECTRAL_KNIGHT", "SOUL_SLASH", 15, 17, 1), ("SPECTRAL_KNIGHT", "SOUL_FLAME", 3, 4, 3),
    ("MAGI_KNIGHT", "POWER_SHIELD", 6, 7, 1), ("MAGI_KNIGHT", "RAM", 10, 11, 1), ("MAGI_KNIGHT", "MAGIC_BOMB", 35, 40, 1),
])
def test_damage_rises_on_deadly_ascension(monster, move, base, deadly, hits):
    for ascension, damage in ((0, base), (9, deadly)):
        m = MOVE_TABLES[monster](ascension)[move]
        assert (m.damage, m.hits) == (damage, hits)

def test_magi_knight_block_rises_on_tough_ascension():
    assert MOVE_TABLES["MAGI_KNIGHT"](0)["PREP"].block == 5 and MOVE_TABLES["MAGI_KNIGHT"](8)["PREP"].block == 9


def follow_ups(monster, move, seeds=150):
    seen = set()
    for seed in range(seeds):
        rng.seed(seed)
        cs = at(monster, move)
        turn(cs)
        seen.add(cs.enemies[0].move_id)
    return seen


# ---------------------------------------------------------------- Soul Nexus
def test_soul_nexus_never_repeats_a_move_and_uses_all_three():
    assert follow_ups("SOUL_NEXUS", "SOUL_BURN") == {"MAELSTROM", "DRAIN_LIFE"}
    assert follow_ups("SOUL_NEXUS", "MAELSTROM") == {"SOUL_BURN", "DRAIN_LIFE"}
    assert follow_ups("SOUL_NEXUS", "DRAIN_LIFE") == {"SOUL_BURN", "MAELSTROM"}

def test_drain_life_hits_and_applies_vulnerable_and_weak():
    cs = at("SOUL_NEXUS", "DRAIN_LIFE")
    turn(cs)
    assert cs.player.current_hp == 80 - 18
    assert (cs.player.status_amount(StatusId.VULNERABLE), cs.player.status_amount(StatusId.WEAK)) == (2, 2)


# ---------------------------------------------------------------- Mecha Knight
def test_mecha_knight_opens_with_a_charge_then_loops_flames_windup_cleave():
    assert moves_over(at("MECHA_KNIGHT", "CHARGE", status=[status("ARTIFACT", 3)]), 6) == \
        ["CHARGE", "FLAMETHROWER", "WINDUP", "HEAVY_CLEAVE", "FLAMETHROWER", "WINDUP", "HEAVY_CLEAVE"]

def test_flamethrower_puts_four_burns_in_the_hand():
    cs = at("MECHA_KNIGHT", "FLAMETHROWER")
    turn(cs)
    assert [c.card_id for c in cs.player.hand] == [CardId.BURN] * 4

def test_burns_that_do_not_fit_the_hand_go_to_the_discard_pile():
    cs = at("MECHA_KNIGHT", "FLAMETHROWER")
    cs.player.hand = [defend() for _ in range(8)]
    turn(cs)
    assert [c.card_id for c in cs.player.hand].count(CardId.BURN) == 2 and [c.card_id for c in cs.player.discard_pile] == [CardId.BURN] * 2

def test_each_burn_in_hand_costs_two_hit_points_at_turn_end():
    cs = at("MECHA_KNIGHT", "FLAMETHROWER")
    turn(cs)
    sim = CombatSimulator(cs)
    hp = cs.player.current_hp
    sim.end_turn()
    assert cs.player.current_hp == hp - 8        # four Burns; the Mecha Knight winds up
    cs = at("MECHA_KNIGHT", "WINDUP")
    cs.player.hand = [Card.create(CardId.BURN), Card.create(CardId.BURN)]
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 80 - 4       # the Burns are discarded after they hurt

def test_burn_is_unplayable_and_blocks_absorb_it():
    cs = at("MECHA_KNIGHT", "WINDUP")
    cs.player.hand = [Card.create(CardId.BURN)]
    assert Card.create(CardId.BURN).unplayable
    cs.player.block = 5
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 80        # 2 damage into 5 block

def test_windup_blocks_and_adds_five_strength_and_cleave_hits_hard():
    cs = at("MECHA_KNIGHT", "WINDUP")
    turn(cs)
    e = cs.enemies[0]
    assert (e.block, e.status_amount(StatusId.STRENGTH)) == (15, 5)
    turn(cs)
    assert cs.player.current_hp == 80 - 40

def test_artifact_stops_the_first_debuffs_on_the_mecha_knight():
    e = at("MECHA_KNIGHT", "CHARGE", status=[status("ARTIFACT", 3)]).enemies[0]
    for _ in range(3):
        e.apply_status(StatusId.WEAK, 1)
    assert StatusId.WEAK not in e.status and StatusId.ARTIFACT not in e.status
    e.apply_status(StatusId.WEAK, 1)
    assert e.status_amount(StatusId.WEAK) == 1


# ---------------------------------------------------------------- Flail Knight
def test_flail_knight_follow_ups():
    assert follow_ups("FLAIL_KNIGHT", "RAM") == {"WAR_CHANT", "FLAIL", "RAM"}
    assert follow_ups("FLAIL_KNIGHT", "WAR_CHANT") == {"FLAIL", "RAM"}

def test_flail_knight_repeats_an_attack_at_most_once():
    for seed in range(60):
        rng.seed(seed)
        cs = at("FLAIL_KNIGHT", "RAM")
        e = cs.enemies[0]
        for _ in range(12):
            turn(cs)
            assert e.move_streak <= 2

def test_war_chant_adds_three_strength():
    cs = at("FLAIL_KNIGHT", "WAR_CHANT")
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 3


# ---------------------------------------------------------------- Spectral Knight
def test_spectral_knight_hexes_then_slashes_then_slashes_or_flames():
    cs = at("SPECTRAL_KNIGHT", "HEX")
    assert moves_over(cs, 1) == ["HEX", "SOUL_SLASH"]
    assert follow_ups("SPECTRAL_KNIGHT", "SOUL_SLASH") == {"SOUL_SLASH", "SOUL_FLAME"}
    assert follow_ups("SPECTRAL_KNIGHT", "SOUL_FLAME") == {"SOUL_SLASH"}

def test_the_knight_slashes_at_most_twice_in_a_row():
    for seed in range(60):
        rng.seed(seed)
        cs = at("SPECTRAL_KNIGHT", "SOUL_SLASH")
        for _ in range(12):
            turn(cs)
            assert cs.enemies[0].move_streak <= 2

def test_hex_makes_every_card_in_hand_ethereal_at_the_end_of_the_turn():
    cs = at("SPECTRAL_KNIGHT", "HEX")
    turn(cs)
    assert cs.player.status_amount(StatusId.HEX) == 2        # as the game shows it (knights/after_hex)
    cs.player.hand = [strike(), defend()]
    CombatSimulator(cs).end_turn()
    assert len(cs.player.exhaust_pile) == 2 and cs.player.discard_pile == []

def test_without_hex_cards_are_discarded():
    cs = at("SPECTRAL_KNIGHT", "SOUL_SLASH")
    cs.player.hand = [strike(), defend()]
    CombatSimulator(cs).end_turn()
    assert cs.player.exhaust_pile == []

def test_killing_the_spectral_knight_ends_hex():
    cs = at("SPECTRAL_KNIGHT", "SOUL_SLASH", hp=1, status=[], extra=[other("FLAIL_KNIGHT", "RAM_MOVE", [])])
    cs.player.status[StatusId.HEX] = StatusInstance(StatusId.HEX, 1)
    cs.player.hand = [strike()]
    CombatSimulator(cs).play_card(0, 0)
    assert StatusId.HEX not in cs.player.status

def test_artifact_stops_hex():
    cs = at("SPECTRAL_KNIGHT", "HEX")
    cs.player.status[StatusId.ARTIFACT] = StatusInstance(StatusId.ARTIFACT, 1)
    turn(cs)
    assert StatusId.HEX not in cs.player.status


# ---------------------------------------------------------------- Magi Knight
def test_magi_knight_cycle():
    assert moves_over(at("MAGI_KNIGHT", "POWER_SHIELD"), 7) == \
        ["POWER_SHIELD", "DAMPEN", "RAM", "PREP", "MAGIC_BOMB", "RAM", "PREP", "MAGIC_BOMB"]

def test_power_shield_attacks_and_blocks_and_prep_blocks():
    cs = at("MAGI_KNIGHT", "POWER_SHIELD")
    turn(cs)
    assert (cs.player.current_hp, cs.enemies[0].block) == (74, 5)
    cs = at("MAGI_KNIGHT", "PREP")
    turn(cs)
    assert cs.enemies[0].block == 5 and cs.player.current_hp == 80

def test_dampen_downgrades_every_upgraded_card_in_every_pile():
    cs = at("MAGI_KNIGHT", "DAMPEN")
    cs.player.hand = [upgraded_strike(), defend()]
    cs.player.draw_pile = [upgraded_strike()]
    cs.player.discard_pile = [upgraded_strike()]
    turn(cs)
    assert cs.player.status_amount(StatusId.DAMPEN) == 1
    assert not any(c.is_upgraded for c in cs.player.hand + cs.player.draw_pile + cs.player.discard_pile)

def test_killing_the_magi_knight_restores_the_upgrades():
    cs = at("MAGI_KNIGHT", "DAMPEN", hp=6, extra=[other("FLAIL_KNIGHT", "RAM_MOVE", [])])
    cs.player.hand = [strike(), upgraded_strike(), upgraded_strike()]
    turn(cs)
    assert not any(c.is_upgraded for c in cs.player.hand)
    cs.enemies[0].current_hp = 3
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert StatusId.DAMPEN not in cs.player.status
    assert [c.is_upgraded for c in cs.player.hand] == [True, True]

def test_a_downgraded_card_plays_as_the_plain_card():
    cs = at("MAGI_KNIGHT", "DAMPEN")
    cs.player.hand = [upgraded_strike()]
    turn(cs)
    enemy = cs.enemies[0]
    hp = enemy.current_hp
    CombatSimulator(cs).play_card(0, 0)
    assert hp - enemy.current_hp == 6

def test_artifact_stops_dampen():
    cs = at("MAGI_KNIGHT", "DAMPEN")
    cs.player.hand = [upgraded_strike()]
    cs.player.status[StatusId.ARTIFACT] = StatusInstance(StatusId.ARTIFACT, 1)
    turn(cs)
    assert cs.player.hand[0].is_upgraded and StatusId.DAMPEN not in cs.player.status


# ---------------------------------------------------------------- captured from the game
def test_mecha_knight_after_flamethrower_capture_agrees_with_the_simulator():
    from sts2_lite.Tests import captures
    cs = captures.load("mecha_knight", "after_flamethrower", captures.GLORY)
    e = cs.enemies[0]
    assert e.move_id == "WINDUP"
    assert [c.card_id for c in cs.player.hand].count(CardId.BURN) == 4 and len(cs.player.hand) == 9
    assert len(cs.player.draw_pile) == 5 and cs.player.discard_pile == []
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.player.current_hp == 55 - 8            # four Burns
