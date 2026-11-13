"""Act 1 (Underdocks) monsters, phase 3: Phantasmal Gardener, Lagavulin Matriarch, Soul Fysh, Waterfall Giant, and the Beckon card.
Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite.card import Card, CardId
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.status import StatusId
from sts2_lite.Tests.enemies.test_glory_simple import at, moves_over, status, turn
from sts2_lite.Tests.card.test_curses import end_turn


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)


@pytest.mark.parametrize("monster, move, base, deadly, hits", [
    ("LAGAVULIN_MATRIARCH", "SLASH", 19, 21, 1), ("LAGAVULIN_MATRIARCH", "DISEMBOWEL", 9, 10, 2), ("LAGAVULIN_MATRIARCH", "SLASH2", 12, 14, 1),
    ("SOUL_FYSH", "DE_GAS", 16, 17, 1), ("SOUL_FYSH", "GAZE", 7, 8, 1), ("SOUL_FYSH", "SCREAM", 13, 15, 1),
    ("WATERFALL_GIANT", "STOMP", 15, 16, 1), ("WATERFALL_GIANT", "RAM", 10, 11, 1),
    ("WATERFALL_GIANT", "PRESSURE_GUN", 20, 23, 1), ("WATERFALL_GIANT", "PRESSURE_UP", 13, 14, 1),
])
def test_damage_rises_on_deadly_ascension(monster, move, base, deadly, hits):
    for ascension, damage in ((0, base), (9, deadly)):
        m = MOVE_TABLES[monster](ascension)[move]
        assert (m.damage, m.hits) == (damage, hits)


# ---------------------------------------------------------------- Phantasmal Gardener
def test_gardener_goes_round_its_four_moves():
    cs = at("PHANTASMAL_GARDENER", "BITE", hp=30, max_hp=30)
    assert moves_over(cs, 4) == ["BITE", "LASH", "FLAIL", "ENLARGE", "BITE"]

def test_gardener_hits_and_enlarges():
    cs = at("PHANTASMAL_GARDENER", "FLAIL", hp=30, max_hp=30)
    hp = cs.player.current_hp
    turn(cs)
    assert cs.player.current_hp == hp - 3
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2

def test_enlarge_gives_three_strength_on_deadly_ascension():
    cs = at("PHANTASMAL_GARDENER", "ENLARGE", hp=30, max_hp=30)
    cs.enemies[0].moves = MOVE_TABLES["PHANTASMAL_GARDENER"](9)
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 3


# ---------------------------------------------------------------- Lagavulin Matriarch
def matriarch(move="SLEEP", asleep=3, plating=12):
    st = []
    if asleep:
        st += [status("ASLEEP", asleep), status("PLATING", plating)]
    return at("LAGAVULIN_MATRIARCH", move, status=st, hp=200, max_hp=200)

def test_matriarch_sleeps_while_asleep_then_wakes_up_to_slash():
    cs = matriarch()
    seen = moves_over(cs, 5)
    assert seen == ["SLEEP"] * 3 + ["SLASH", "DISEMBOWEL", "SLASH2"]
    assert StatusId.ASLEEP not in cs.enemies[0].status

def test_a_sleeping_matriarch_does_not_attack():
    cs = matriarch()
    hp = cs.player.current_hp
    turn(cs)
    assert cs.player.current_hp == hp

def test_sleep_counts_down_each_enemy_turn_and_takes_the_plating_with_it():
    cs = matriarch(asleep=1)
    turn(cs)
    assert StatusId.ASLEEP not in cs.enemies[0].status
    assert StatusId.PLATING not in cs.enemies[0].status
    assert cs.enemies[0].move_id == "SLASH"

def test_an_unblocked_hit_wakes_it_up_and_stuns_it():
    cs = matriarch()
    e = cs.enemies[0]
    e.apply_damage(5)
    assert StatusId.ASLEEP not in e.status and StatusId.PLATING not in e.status
    assert e.move_id == "STUNNED"
    turn(cs)
    assert e.move_id == "SLASH"

def test_a_hit_that_plating_soaks_up_does_not_wake_it():
    cs = matriarch()
    cs.enemies[0].block = 50
    cs.enemies[0].apply_damage(5)
    assert StatusId.ASLEEP in cs.enemies[0].status

def test_matriarch_cycle_and_soul_siphon():
    cs = matriarch("SLASH", asleep=0)
    assert moves_over(cs, 4) == ["SLASH", "DISEMBOWEL", "SLASH2", "SOUL_SIPHON", "SLASH"]

def test_awake_matriarch_attacks_with_block_on_slash2():
    cs = matriarch("SLASH2", asleep=0)
    hp = cs.player.current_hp
    turn(cs)
    assert cs.player.current_hp == hp - 12 and cs.enemies[0].block == 12

def test_soul_siphon_saps_strength_and_dexterity_and_feeds_the_matriarch():
    cs = matriarch("SOUL_SIPHON", asleep=0)
    turn(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == -2 and cs.player.status_amount(StatusId.DEXTERITY) == -2
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2


# ---------------------------------------------------------------- Soul Fysh and Beckon
def count(pile, cid):
    return sum(1 for c in pile if c.card_id == cid)

def test_soul_fysh_cycle():
    cs = at("SOUL_FYSH", "BECKON", hp=80, max_hp=80)
    assert moves_over(cs, 5) == ["BECKON", "DE_GAS", "GAZE", "FADE", "SCREAM", "BECKON"]

def test_beckon_adds_one_to_the_draw_pile_and_one_to_the_discard_pile():
    cs = at("SOUL_FYSH", "BECKON", hp=80, max_hp=80)
    turn(cs)
    assert count(cs.player.draw_pile, CardId.BECKON) == 1 and count(cs.player.discard_pile, CardId.BECKON) == 1

def test_gaze_hits_and_adds_a_beckon_to_the_discard_pile():
    cs = at("SOUL_FYSH", "GAZE", hp=80, max_hp=80)
    hp = cs.player.current_hp
    turn(cs)
    assert cs.player.current_hp == hp - 7 and count(cs.player.discard_pile, CardId.BECKON) == 1

def test_fade_gives_intangible_and_scream_makes_the_player_vulnerable():
    cs = at("SOUL_FYSH", "FADE", hp=80, max_hp=80)
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.INTANGIBLE) == 2
    turn(cs)
    assert cs.player.status_amount(StatusId.VULNERABLE) == 3

def test_a_beckon_left_in_hand_costs_six_hp_at_the_end_of_the_turn():
    b = Card.create_beckon()
    cs = end_turn([b])
    assert cs.player.current_hp == cs.player.max_hp - 6

def test_two_beckons_cost_twelve_and_block_does_not_help():
    cs = end_turn([Card.create_beckon(), Card.create_beckon()])
    assert cs.player.current_hp == cs.player.max_hp - 12

def test_beckon_can_be_played_for_one_energy_and_does_nothing():
    b = Card.create_beckon()
    assert b.energy_cost == 1 and not b.is_unplayable


# ---------------------------------------------------------------- Waterfall Giant
def giant(move="PRESSURIZE", steam=0, counter=0, **kw):
    st = [status("STEAM_ERUPTION", steam)] if steam else []
    cs = at("WATERFALL_GIANT", move, status=st, hp=250, max_hp=250, **kw)
    cs.enemies[0].counter = counter
    return cs

def test_giant_cycle():
    cs = giant()
    assert moves_over(cs, 7) == ["PRESSURIZE", "STOMP", "RAM", "SIPHON", "PRESSURE_GUN", "PRESSURE_UP", "STOMP", "RAM"]

@pytest.mark.parametrize("ascension, steam", [(0, 15), (9, 20)])
def test_pressurize_builds_the_first_steam(ascension, steam):
    cs = giant()
    cs.enemies[0].moves = MOVE_TABLES["WATERFALL_GIANT"](ascension)
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STEAM_ERUPTION) == steam

def test_each_attack_adds_three_steam():
    cs = giant("STOMP", steam=15)
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STEAM_ERUPTION) == 18
    assert cs.player.status_amount(StatusId.WEAK) == 1

def test_siphon_heals():
    cs = giant("SIPHON", steam=15)
    cs.enemies[0].current_hp = 100
    turn(cs)
    assert cs.enemies[0].current_hp == 110

def test_pressure_gun_hits_harder_every_time_it_is_fired():
    cs = giant("PRESSURE_GUN", steam=15)
    hp = cs.player.current_hp
    turn(cs)
    assert cs.player.current_hp == hp - 20
    cs = giant("PRESSURE_GUN", steam=15)
    cs.player.max_hp = cs.player.current_hp = 999
    assert moves_over(cs, 5)[-1] == "PRESSURE_GUN"
    assert cs.enemies[0].attack_damage == 25
    hp = cs.player.current_hp
    turn(cs)
    assert cs.player.current_hp == hp - 25

def test_dying_with_steam_does_not_end_the_fight_it_is_about_to_blow():
    cs = giant("STOMP", steam=21)
    e = cs.enemies[0]
    e.current_hp = 0
    sim = CombatSimulator(cs)
    sim.resolve_deaths()
    assert not sim.is_over
    assert e in cs.enemies and e.move_id == "ABOUT_TO_BLOW"

def test_about_to_blow_then_explodes_for_the_steam_it_built():
    cs = giant("STOMP", steam=21)
    e = cs.enemies[0]
    e.current_hp = 0
    sim = CombatSimulator(cs)
    sim.resolve_deaths()
    hp = cs.player.current_hp
    turn(cs)
    assert cs.player.current_hp == hp and e.move_id == "EXPLODE"
    turn(cs)
    assert cs.player.current_hp == hp - 21
    sim.resolve_deaths()
    assert sim.is_over or e not in cs.enemies


# ---------------------------------------------------------------- captures
from sts2_lite.Tests import captures

def cap(enemy, name):
    return captures.load(enemy, name, captures.UNDERDOCKS)

def seen(cs):
    return [(e.move_id, e.attack_damage, {k: v.amount for k, v in e.status.items()}, e.block) for e in cs.enemies]

def next_turn(cs):
    CombatSimulator(cs).end_turn()

def test_matriarch_sleeps_three_turns_with_its_plating_then_wakes_to_slash():
    cs = cap("lagavulin_matriarch", "turn_1")
    for name in ("turn_2", "turn_3", "turn_4_awake"):
        next_turn(cs)
        assert seen(cs) == seen(cap("lagavulin_matriarch", name)), name

def test_matriarch_woken_by_a_hit_is_stunned_and_then_slashes():
    cs = cap("lagavulin_matriarch", "awake_from_hit")
    e = cs.enemies[0]
    assert e.move_id == "STUNNED" and StatusId.ASLEEP not in e.status and StatusId.PLATING not in e.status
    CombatSimulator(cs)._play_enemy_turn()
    assert e.move_id == "SLASH"

def test_waterfall_giant_steam_builds_by_three_a_move():
    cs = cap("waterfall_giant", "turn_1")
    for name in ("turn_2", "turn_3", "turn_4"):
        CombatSimulator(cs)._play_enemy_turn()
        assert seen(cs) == seen(cap("waterfall_giant", name)), name

def test_waterfall_giant_about_to_blow_then_explodes_for_its_steam():
    cs = cap("waterfall_giant", "after_kill")
    assert cs.enemies[0].status_amount(StatusId.STEAM_ERUPTION) == 21
    CombatSimulator(cs)._play_enemy_turn()
    assert seen(cs) == seen(cap("waterfall_giant", "before_explosion"))
    hp = cs.player.current_hp
    CombatSimulator(cs)._play_enemy_turn()
    assert cs.player.current_hp == hp - 21

def test_soul_fysh_turns_match_the_captures():
    cs = cap("soul_fysh", "turn_1")
    for _ in range(4):
        next_turn(cs)
    assert seen(cs) == seen(cap("soul_fysh", "intangible"))

def test_soul_fysh_beckon_cards_load_and_cost_hp_in_hand():
    cs = cap("soul_fysh", "beckon_in_hand")
    assert [c.card_id for c in cs.player.hand].count(CardId.BECKON) == 2
    assert all(not c.is_unplayable for c in cs.player.hand if c.card_id == CardId.BECKON)
    cs = cap("soul_fysh", "intangible")
    assert count(cs.player.draw_pile, CardId.BECKON) == 3

def test_gardeners_open_on_different_moves_and_start_skittish():
    cs = cap("phantasmal_gardeners", "turn_1")
    assert [e.move_id for e in cs.enemies] == ["FLAIL", "BITE", "LASH", "ENLARGE"]
    assert all(e.status_amount(StatusId.SKITTISH) == 6 for e in cs.enemies)
    CombatSimulator(cs)._play_enemy_turn()
    assert [e.move_id for e in cs.enemies] == ["ENLARGE", "LASH", "FLAIL", "BITE"]

def test_the_beckon_move_leaves_one_beckon_in_the_discard_pile_and_one_to_draw():
    cs = cap("soul_fysh", "after_beckon")
    p = cs.player
    assert count(p.discard_pile, CardId.BECKON) == 1 and count(p.hand, CardId.BECKON) + count(p.draw_pile, CardId.BECKON) == 1
    cs = cap("soul_fysh", "turn_1")
    next_turn(cs)
    p = cs.player
    assert count(p.discard_pile, CardId.BECKON) == 1 and count(p.hand, CardId.BECKON) + count(p.draw_pile, CardId.BECKON) == 1

def test_two_beckons_and_a_defend_played_cost_what_the_game_showed():
    cs = cap("soul_fysh", "beckon_in_hand")
    defend = next(c for c in cs.player.hand if c.card_id == CardId.DEFEND_IRONCLAD)
    cs.player.hand.remove(defend)
    cs.player.block = 5
    next_turn(cs)
    assert cs.player.current_hp == 64 - 12 - 2        # 2 Beckons at 6, and Gaze's 7 less 5 block
