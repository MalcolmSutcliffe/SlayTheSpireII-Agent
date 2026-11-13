"""Act 3 (Glory) monsters, phase 2: Living Shield + Turret Operator, Devoted Sculptor, Owl Magistrate, Fabricator and its bots.
Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite import rng
from sts2_lite.card import CardId
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.status import StatusId
from sts2_lite.Tests.enemies.test_glory_simple import at, moves_over, status, turn
from sts2_lite.Tests.enemies.test_bridge_moves import attack, raw_enemy
from sts2_lite.Tests.enemies.test_hive_simple import make_card, strike


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)

def other(monster, move="STAB_MOVE", slot=0, hp=20, intents=None):
    raw = raw_enemy(monster, move, [move], attack(11) if intents is None else intents, slot=slot)
    raw["hp"] = raw["max_hp"] = hp
    return raw


@pytest.mark.parametrize("monster, move, base, deadly, hits", [
    ("LIVING_SHIELD", "SMASH", 16, 18, 1), ("TURRET_OPERATOR", "UNLOAD", 3, 4, 5),
    ("DEVOTED_SCULPTOR", "SAVAGE", 12, 15, 1),
    ("OWL_MAGISTRATE", "MAGISTRATE_SCRUTINY", 16, 17, 1), ("OWL_MAGISTRATE", "VERDICT", 33, 36, 1),
    ("FABRICATOR", "FABRICATING_STRIKE", 18, 21, 1), ("FABRICATOR", "DISINTEGRATE", 11, 13, 1),
    ("ZAPBOT", "ZAP", 14, 15, 1), ("STABBOT", "STAB", 11, 12, 1),
])
def test_damage_rises_on_deadly_ascension(monster, move, base, deadly, hits):
    for ascension, damage in ((0, base), (9, deadly)):
        m = MOVE_TABLES[monster](ascension)[move]
        assert (m.damage, m.hits) == (damage, hits)


# ---------------------------------------------------------------- Living Shield and Turret Operator
def test_living_shield_slams_while_an_ally_lives_then_smashes_forever():
    cs = at("LIVING_SHIELD", "SHIELD_SLAM", extra=[other("TURRET_OPERATOR", "UNLOAD_MOVE")])
    turn(cs)
    assert cs.enemies[0].move_id == "SHIELD_SLAM"
    cs.enemies[1].current_hp = 0
    cs.enemies = [e for e in cs.enemies if e.current_hp > 0]
    turn(cs)
    assert cs.enemies[0].move_id == "SMASH"
    turn(cs)
    turn(cs)
    assert cs.enemies[0].move_id == "SMASH" and cs.enemies[0].status_amount(StatusId.STRENGTH) == 6

def test_shield_slam_deals_six():
    cs = at("LIVING_SHIELD", "SHIELD_SLAM", extra=[other("TURRET_OPERATOR", "UNLOAD_MOVE", intents=[])])
    turn(cs)
    assert cs.player.current_hp == 74

def test_turret_operator_cycle_and_strength():
    cs = at("TURRET_OPERATOR", "UNLOAD")
    assert moves_over(cs, 4) == ["UNLOAD", "UNLOAD_2", "RELOAD", "UNLOAD", "UNLOAD_2"]
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 1
    assert cs.player.current_hp == 80 - 15 - 15 - 20      # two unloads at 3, then after the Reload one at 4

def test_rampart_gives_the_turret_block_as_every_player_turn_starts():
    cs = at("LIVING_SHIELD", "SHIELD_SLAM", status=[status("RAMPART", 25)], extra=[other("TURRET_OPERATOR", "UNLOAD_MOVE")])
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.enemies[1].block == 25 and cs.enemies[0].block == 0

def test_rampart_ends_with_the_shield():
    cs = at("LIVING_SHIELD", "SHIELD_SLAM", status=[status("RAMPART", 25)], hp=1, extra=[other("TURRET_OPERATOR", "UNLOAD_MOVE")])
    cs.player.hand = [strike()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert [e.enemy_id for e in cs.enemies] == ["TURRET_OPERATOR_0"]
    sim.end_turn()
    assert cs.enemies[0].block == 0


# ---------------------------------------------------------------- Devoted Sculptor
def test_sculptor_incantation_then_savage_forever():
    assert moves_over(at("DEVOTED_SCULPTOR", "FORBIDDEN_INCANTATION"), 3) == ["FORBIDDEN_INCANTATION", "SAVAGE", "SAVAGE", "SAVAGE"]

def test_the_turn_ritual_is_applied_does_not_give_strength():
    cs = at("DEVOTED_SCULPTOR", "FORBIDDEN_INCANTATION")
    e = cs.enemies[0]
    turn(cs)
    assert e.status_amount(StatusId.RITUAL) == 9 and e.status_amount(StatusId.STRENGTH) == 0
    turn(cs)        # Savage for 12, then +9
    assert cs.player.current_hp == 68 and e.status_amount(StatusId.STRENGTH) == 9
    turn(cs)        # Savage for 21, then +9
    assert cs.player.current_hp == 68 - 21 and e.status_amount(StatusId.STRENGTH) == 18

def test_a_ritual_read_from_the_game_gives_strength_every_turn():
    from sts2_lite.Tests.enemies.test_bridge_moves import load
    cs = load(raw_enemy("DEVOTED_SCULPTOR", "SAVAGE_MOVE", ["FORBIDDEN_INCANTATION_MOVE", "SAVAGE_MOVE"], attack(12, damage=21),
                        status=[status("RITUAL", 9), status("STRENGTH", 9)]))
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 18


# ---------------------------------------------------------------- Owl Magistrate
def test_owl_cycle():
    assert moves_over(at("OWL_MAGISTRATE", "MAGISTRATE_SCRUTINY"), 4) == \
        ["MAGISTRATE_SCRUTINY", "PECK_ASSAULT", "JUDICIAL_FLIGHT", "VERDICT", "MAGISTRATE_SCRUTINY"]

def test_peck_assault_is_six_hits_of_four():
    cs = at("OWL_MAGISTRATE", "PECK_ASSAULT")
    turn(cs)
    assert cs.player.current_hp == 80 - 24

def test_judicial_flight_gives_soar_and_verdict_takes_it_away_and_applies_vulnerable():
    cs = at("OWL_MAGISTRATE", "JUDICIAL_FLIGHT")
    e = cs.enemies[0]
    turn(cs)
    assert e.status_amount(StatusId.SOAR) == 1 and e.move_id == "VERDICT"
    turn(cs)
    assert StatusId.SOAR not in e.status
    assert cs.player.current_hp == 80 - 33 and cs.player.status_amount(StatusId.VULNERABLE) == 4

def test_soar_halves_attack_damage_against_the_owl():
    cs = at("OWL_MAGISTRATE", "VERDICT", status=[status("SOAR", 1)])
    cs.player.hand = [strike()]
    CombatSimulator(cs).play_card(0, 0)
    assert cs.enemies[0].current_hp == 40 - 3


# ---------------------------------------------------------------- Fabricator
def minions(cs):
    return [e for e in cs.enemies if not e.enemy_id.startswith("FABRICATOR")]

def bots(cs):
    """Kinds of the bots in the order they were built (the line runs bot1, bot2, Fabricator, bot3, bot4)."""
    return [e.enemy_id.rpartition("_")[0] for e in minions(cs)]

def test_fabricate_adds_a_defensive_and_an_aggressive_minion():
    for seed in range(30):
        rng.seed(seed) if hasattr(rng, "seed") else None
        cs = at("FABRICATOR", "FABRICATE", hp=150, max_hp=150)
        turn(cs)
        first, second = bots(cs)
        assert first in ("GUARDBOT", "NOISEBOT") and second in ("ZAPBOT", "STABBOT")
        assert all(e.is_minion for e in minions(cs))
        assert [e.enemy_id.startswith("FABRICATOR") for e in cs.enemies] == [False, False, True]

def test_zapbot_arrives_with_high_voltage_and_the_bots_have_the_expected_hit_points():
    seen = set()
    for seed in range(60):
        cs = at("FABRICATOR", "FABRICATE", hp=150, max_hp=150)
        turn(cs)
        for bot in minions(cs):
            name = bot.enemy_id.rpartition("_")[0]
            seen.add(name)
            low, high = (16, 20) if name == "GUARDBOT" else (18, 23)
            assert low <= bot.max_hp <= high and bot.current_hp == bot.max_hp
            assert bot.move_id == {"ZAPBOT": "ZAP", "STABBOT": "STAB", "GUARDBOT": "GUARD", "NOISEBOT": "NOISE"}[name]
            assert (StatusId.HIGH_VOLTAGE in bot.status) == (name == "ZAPBOT")
    assert seen == {"ZAPBOT", "STABBOT", "GUARDBOT", "NOISEBOT"}

def test_fabricating_strike_hits_and_adds_one_aggressive_bot():
    cs = at("FABRICATOR", "FABRICATING_STRIKE", hp=150, max_hp=150)
    turn(cs)
    assert cs.player.current_hp == 80 - 18 and len(cs.enemies) == 2 and bots(cs)[0] in ("ZAPBOT", "STABBOT")

def test_the_same_aggressive_bot_is_never_built_twice_in_a_row_by_strikes():
    for seed in range(40):
        cs = at("FABRICATOR", "FABRICATING_STRIKE", hp=150, max_hp=150)
        e = cs.enemies[0]
        built = []
        for _ in range(2):
            e.move_id, e.attack_damage, e.num_attacks = "FABRICATING_STRIKE", 18, 1
            turn(cs)
            built.append(e.counter)        # the code of the last bot it made
        assert built[0] != built[1]

def test_with_four_or_more_alive_it_only_disintegrates():
    cs = at("FABRICATOR", "FABRICATE", hp=150, max_hp=150)
    turn(cs)            # three bots? two bots: the team is three, so it may still build
    assert len(cs.enemies) == 3
    e = next(x for x in cs.enemies if x.enemy_id.startswith("FABRICATOR"))
    e.move_id, e.attack_damage, e.num_attacks = "FABRICATING_STRIKE", 18, 1
    turn(cs)
    assert len(cs.enemies) == 4 and e.move_id == "DISINTEGRATE"
    turn(cs)
    assert e.move_id == "DISINTEGRATE" and len(cs.enemies) == 4

def test_a_dead_bot_lets_it_build_again():
    cs = at("FABRICATOR", "DISINTEGRATE", hp=150, max_hp=150,
            extra=[other("ZAPBOT", "ZAP", 0), other("STABBOT", "STAB_MOVE", 0), other("GUARDBOT", "GUARD_MOVE", 0)])
    turn(cs)
    assert cs.enemies[0].move_id == "DISINTEGRATE"
    cs.enemies.pop()
    turn(cs)
    assert cs.enemies[0].move_id in ("FABRICATE", "FABRICATING_STRIKE")

def test_killing_the_fabricator_ends_the_fight_with_its_minions_alive():
    cs = at("FABRICATOR", "DISINTEGRATE", hp=1, max_hp=150, extra=[other("ZAPBOT", "ZAP", 0)])
    cs.enemies[1].status[StatusId.MINION] = enemy_module.StatusInstance(StatusId.MINION, 1)
    cs.enemies[1].is_minion = True
    cs.player.hand = [strike()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert sim.is_over and cs.won

def test_zapbot_gains_strength_every_enemy_turn_and_stabbot_frails():
    cs = at("ZAPBOT", "ZAP", status=[status("HIGH_VOLTAGE", 2)])
    turn(cs)
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 4
    assert cs.player.current_hp == 80 - 14 - 16
    cs = at("STABBOT", "STAB")
    turn(cs)
    assert cs.player.status_amount(StatusId.FRAIL) == 1

def test_guardbot_blocks_the_fabricator_for_fifteen_and_noisebot_adds_two_dazed():
    cs = at("GUARDBOT", "GUARD", extra=[other("FABRICATOR", "DISINTEGRATE_MOVE", 0, 150, intents=[])])
    cs.enemies[1].max_hp = 150
    turn(cs)
    assert cs.enemies[1].block == 15 and cs.enemies[0].block == 0      # the Guardbot acts first; the Fabricator keeps the block
    cs = at("NOISEBOT", "NOISE")
    turn(cs)
    assert [c.card_id for c in cs.player.discard_pile] == [CardId.DAZED]
    assert [c.card_id for c in cs.player.draw_pile] == [CardId.DAZED]


# ---------------------------------------------------------------- captured from the game (Tests/data/act3_glory)
from agents import verify
from sts2_lite.Tests import captures


def glory(enemy, name):
    return captures.load(enemy, name, captures.GLORY)

def test_the_captured_states_load_with_every_move_and_damage_agreeing():
    for enemy, name in (("axe_bots", "after_kill"), ("fabricator", "after_fabricate"), ("fabricator", "fabricating_strike"),
                        ("fabricator", "after_fabricating_strike"), ("owl_magistrate", "judicial_flight"), ("turret_operator", "turn_2")):
        glory(enemy, name)

def test_a_respawned_axebot_opens_with_boot_up_and_has_one_life_left():
    cs = glory("axe_bots", "after_kill")
    e = cs.enemies[0]
    assert (e.move_id, e.status_amount(StatusId.STOCK)) == ("BOOT_UP", 1)
    turn(cs)
    assert (e.block, e.status_amount(StatusId.STRENGTH), e.move_id) == (10, 3, "HAMMER_UPPERCUT")

def test_the_owl_in_flight_is_read_with_soar_and_about_to_deliver_its_verdict():
    e = glory("owl_magistrate", "judicial_flight").enemies[0]
    assert (e.move_id, e.status_amount(StatusId.SOAR)) == ("VERDICT", 1)
    cs = glory("owl_magistrate", "judicial_flight")
    turn(cs)
    assert StatusId.SOAR not in cs.enemies[0].status and cs.enemies[0].move_id == "MAGISTRATE_SCRUTINY"

def test_the_turret_operator_has_its_rampart_block_on_turn_two():
    cs = glory("turret_operator", "turn_2")
    assert cs.enemies[1].block == 25 and cs.enemies[1].move_id == "UNLOAD_2"
    sim = CombatSimulator(cs)
    sim.end_turn()      # the shield slams, the turret reloads... the block it had is gone, and the next turn's is back
    assert cs.enemies[1].block == 25 and cs.enemies[1].move_id == "RELOAD"

def test_fabricate_builds_its_bots_in_the_game_s_slots_and_the_guardbot_blocks_the_fabricator():
    """After_fabricate (round 2) -> fabricating_strike (round 3): same bots, same order, the same 15 block, and the move afterwards."""
    for seed in range(300):
        rng.seed(seed)
        cs = glory("fabricator", "after_fabricate")
        turn(cs)
        want = glory("fabricator", "fabricating_strike")
        if [e.enemy_id for e in cs.enemies] != [e.enemy_id for e in want.enemies]:
            continue
        break
    else:
        pytest.fail("no seed gave GUARDBOT_1 and ZAPBOT_0 to the right of the Fabricator")
    diffs = [d for d in verify.compare(cs, want) if d.startswith("enemy") and "hp" not in d]
    assert diffs == []
    assert [e.enemy_id for e in cs.enemies] == ["GUARDBOT_0", "STABBOT_0", "FABRICATOR_0", "GUARDBOT_1", "ZAPBOT_0"]
    assert cs.enemies[2].block == 15 and cs.enemies[2].move_id == "DISINTEGRATE"
    assert cs.enemies[4].status_amount(StatusId.STRENGTH) == 2         # High Voltage on the turn it arrived

def test_two_guardbots_and_two_turns_stack_thirty_block_on_the_fabricator():
    cs = glory("fabricator", "fabricating_strike")
    want = glory("fabricator", "after_fabricating_strike")
    turn(cs)
    assert cs.enemies[2].block == want.enemies[2].block == 30
    assert cs.enemies[4].status_amount(StatusId.STRENGTH) == 4
