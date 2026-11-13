"""Act 1 (Underdocks) monsters, phase 1: the cultists, Corpse Slug, Sewer Clam, Sludge Spinner, Seapunk, Fossil Stalker,
Toadpole, Haunted Ship and Skulking Colony. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite import rng
from sts2_lite.card import Card, CardId
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy import STUNNED
from sts2_lite.enemy_moves import MOVE_TABLES, table_move_id
from sts2_lite.events import EventType
from sts2_lite.status import StatusId
from sts2_lite.Tests.enemies.test_bridge_moves import attack, load, raw_enemy
from sts2_lite.Tests.enemies.test_glory_simple import at, moves_over, status, turn


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)

def ascended(cs, monster, ascension):
    """`at` loads the state at ascension 0; the table of the later moves has to follow the state's ascension."""
    cs.enemies[0].moves = MOVE_TABLES[monster](ascension)
    return cs

def companion(monster, move="DARK_STRIKE_MOVE", hp=40):
    raw = raw_enemy(monster, move, [move], [])
    raw["hp"] = raw["max_hp"] = hp
    return raw


@pytest.mark.parametrize("monster, move, base, deadly, hits", [
    ("CALCIFIED_CULTIST", "DARK_STRIKE", 9, 11, 1), ("DAMP_CULTIST", "DARK_STRIKE", 1, 3, 1),
    ("CORPSE_SLUG", "WHIP_SLAP", 3, 3, 2), ("CORPSE_SLUG", "GLOMP", 8, 9, 1),
    ("SEWER_CLAM", "JET", 10, 11, 1),
    ("SLUDGE_SPINNER", "OIL_SPRAY", 8, 9, 1), ("SLUDGE_SPINNER", "SLAM", 11, 12, 1), ("SLUDGE_SPINNER", "RAGE", 6, 7, 1),
    ("SEAPUNK", "SEA_KICK", 11, 13, 1), ("SEAPUNK", "SPINNING_KICK", 2, 2, 4),
    ("FOSSIL_STALKER", "TACKLE", 9, 11, 1), ("FOSSIL_STALKER", "LATCH", 12, 14, 1), ("FOSSIL_STALKER", "LASH", 3, 4, 2),
    ("TOADPOLE", "SPIKE_SPIT", 3, 4, 3), ("TOADPOLE", "WHIRL", 7, 8, 1),
    ("HAUNTED_SHIP", "SWIPE", 13, 14, 1), ("HAUNTED_SHIP", "STOMP", 4, 5, 3),
    ("SKULKING_COLONY", "ZOOM", 14, 16, 1), ("SKULKING_COLONY", "ZOOM_2", 14, 16, 1), ("SKULKING_COLONY", "INERTIA", 9, 11, 1),
    ("SKULKING_COLONY", "PIERCING_STABS", 7, 8, 2),
])
def test_damage_rises_on_deadly_ascension(monster, move, base, deadly, hits):
    for ascension, damage in ((0, base), (9, deadly)):
        m = MOVE_TABLES[monster](ascension)[move]
        assert (m.damage, m.hits) == (damage, hits)

def follow_ups(monster, move, seeds=150, **kw):
    seen = set()
    for seed in range(seeds):
        rng.seed(seed)
        cs = at(monster, move, **kw)
        turn(cs)
        seen.add(cs.enemies[0].move_id)
    return seen


# ---------------------------------------------------------------- the cultists
@pytest.mark.parametrize("monster, ascension, ritual, strike", [
    ("CALCIFIED_CULTIST", 0, 2, 9), ("CALCIFIED_CULTIST", 9, 2, 11), ("DAMP_CULTIST", 0, 5, 1), ("DAMP_CULTIST", 9, 6, 3),
])
def test_cultists_chant_then_strike_with_growing_strength(monster, ascension, ritual, strike):
    cs = ascended(at(monster, "INCANTATION", ascension), monster, ascension)
    turn(cs)
    e = cs.enemies[0]
    assert e.status_amount(StatusId.RITUAL) == ritual
    assert e.status_amount(StatusId.STRENGTH) == 0 and e.move_id == "DARK_STRIKE"      # nothing on the turn it chanted
    turn(cs)
    assert cs.player.current_hp == 80 - strike
    assert e.status_amount(StatusId.STRENGTH) == ritual
    turn(cs)
    assert cs.player.current_hp == 80 - strike - (strike + ritual)


# ---------------------------------------------------------------- Corpse Slug
def test_corpse_slug_goes_round_whatever_it_starts_with():
    for start, expected in (("WHIP_SLAP", ["WHIP_SLAP", "GLOMP", "GOOP", "WHIP_SLAP"]),
                            ("GLOMP", ["GLOMP", "GOOP", "WHIP_SLAP", "GLOMP"]),
                            ("GOOP", ["GOOP", "WHIP_SLAP", "GLOMP", "GOOP"])):
        assert moves_over(at("CORPSE_SLUG", start), 3) == expected

def test_goop_frails_and_whip_slap_hits_twice():
    cs = at("CORPSE_SLUG", "GOOP")
    turn(cs)
    assert cs.player.status_amount(StatusId.FRAIL) == 2
    turn(cs)
    assert cs.player.current_hp == 80 - 6

@pytest.mark.parametrize("ascension, strength", [(0, 4), (9, 5)])
def test_a_slug_devours_a_fallen_ally_stunned_but_stronger(ascension, strength):
    cs = ascended(at("CORPSE_SLUG", "GLOMP", ascension, status=[status("RAVENOUS", strength)], extra=[companion("DAMP_CULTIST")]),
                  "CORPSE_SLUG", ascension)
    slug, cultist = cs.enemies
    sim = CombatSimulator(cs)
    cultist.current_hp = 0
    sim.resolve_deaths()
    assert slug.move_id == STUNNED and slug.status_amount(StatusId.STRENGTH) == strength
    hp = cs.player.current_hp
    turn(cs)
    assert cs.player.current_hp == hp                  # the stunned turn does nothing
    assert slug.move_id == "GLOMP"                     # and then the interrupted move comes back
    turn(cs)
    assert cs.player.current_hp == hp - (8 if ascension == 0 else 9) - strength

def test_a_slug_that_dies_itself_or_a_dead_slug_gains_nothing():
    cs = at("CORPSE_SLUG", "GLOMP", status=[status("RAVENOUS", 4)], extra=[companion("DAMP_CULTIST")])
    slug, cultist = cs.enemies
    slug.current_hp = 0
    CombatSimulator(cs).resolve_deaths()
    assert StatusId.STRENGTH not in slug.status

def test_two_slugs_dying_together_do_not_devour_each_other():
    cs = at("CORPSE_SLUG", "GLOMP", status=[status("RAVENOUS", 4)],
            extra=[{**companion("CORPSE_SLUG", "GOOP_MOVE"), "entity_id": "CORPSE_SLUG_1", "status": [status("RAVENOUS", 4)]}])
    for e in cs.enemies:
        e.current_hp = 0
    CombatSimulator(cs).resolve_deaths()
    assert cs.enemies == []

def test_each_slug_devours_when_one_of_three_falls():
    cs = at("CORPSE_SLUG", "GLOMP", status=[status("RAVENOUS", 4)], extra=[
        {**companion("CORPSE_SLUG", "GOOP_MOVE"), "entity_id": "CORPSE_SLUG_1", "status": [status("RAVENOUS", 4)]},
        {**companion("CORPSE_SLUG", "WHIP_SLAP_MOVE"), "entity_id": "CORPSE_SLUG_2", "status": [status("RAVENOUS", 4)]}])
    cs.enemies[2].current_hp = 0
    CombatSimulator(cs).resolve_deaths()
    assert [e.move_id for e in cs.enemies] == [STUNNED, STUNNED]
    assert [e.status_amount(StatusId.STRENGTH) for e in cs.enemies] == [4, 4]


# ---------------------------------------------------------------- Sewer Clam
def test_sewer_clam_jets_then_pressurizes_and_its_plating_pays_out():
    cs = at("SEWER_CLAM", "JET", status=[status("PLATING", 8)])
    assert moves_over(cs, 3) == ["JET", "PRESSURIZE", "JET", "PRESSURIZE"]
    cs = at("SEWER_CLAM", "PRESSURIZE")
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 4
    turn(cs)
    assert cs.player.current_hp == 80 - 14

def test_sewer_clam_gets_block_from_plating_when_its_turn_starts():
    cs = at("SEWER_CLAM", "JET", status=[status("PLATING", 8)])
    e = cs.enemies[0]
    e.turn_start()
    assert e.block == 8


# ---------------------------------------------------------------- Sludge Spinner
def test_sludge_spinner_picks_any_move_but_the_one_it_just_used():
    assert follow_ups("SLUDGE_SPINNER", "OIL_SPRAY") == {"SLAM", "RAGE"}
    assert follow_ups("SLUDGE_SPINNER", "SLAM") == {"OIL_SPRAY", "RAGE"}
    assert follow_ups("SLUDGE_SPINNER", "RAGE") == {"OIL_SPRAY", "SLAM"}

def test_oil_spray_weakens_and_rage_adds_strength_after_hitting():
    cs = at("SLUDGE_SPINNER", "OIL_SPRAY")
    turn(cs)
    assert cs.player.current_hp == 80 - 8 and cs.player.status_amount(StatusId.WEAK) == 1
    cs = at("SLUDGE_SPINNER", "RAGE")
    turn(cs)
    assert cs.player.current_hp == 80 - 6 and cs.enemies[0].status_amount(StatusId.STRENGTH) == 3


# ---------------------------------------------------------------- Seapunk
def test_seapunk_kicks_spins_and_burps_in_turn():
    assert moves_over(at("SEAPUNK", "SEA_KICK"), 3) == ["SEA_KICK", "SPINNING_KICK", "BUBBLE_BURP", "SEA_KICK"]

@pytest.mark.parametrize("ascension, block, strength", [(0, 7, 1), (8, 8, 1), (9, 8, 2)])
def test_bubble_burp_blocks_and_adds_strength(ascension, block, strength):
    cs = ascended(at("SEAPUNK", "BUBBLE_BURP", ascension), "SEAPUNK", ascension)
    turn(cs)
    e = cs.enemies[0]
    assert (e.block, e.status_amount(StatusId.STRENGTH)) == (block, strength)

def test_spinning_kick_is_four_hits_of_two():
    cs = at("SEAPUNK", "SPINNING_KICK")
    turn(cs)
    assert cs.player.current_hp == 80 - 8


# ---------------------------------------------------------------- Fossil Stalker
def test_fossil_stalker_uses_any_move_but_never_three_in_a_row():
    assert follow_ups("FOSSIL_STALKER", "LATCH") == {"LATCH", "TACKLE", "LASH"}
    cs = at("FOSSIL_STALKER", "LATCH")
    streak, last, longest = 0, None, 0
    for seed in range(300):
        rng.seed(seed)
        turn(cs)
        e = cs.enemies[0]
        streak = streak + 1 if e.move_id == last else 1
        last, longest = e.move_id, max(longest, streak)
    assert longest <= 2

def test_tackle_frails_after_hitting():
    cs = at("FOSSIL_STALKER", "TACKLE", status=[status("SUCK", 3)])
    turn(cs)
    assert cs.player.current_hp == 80 - 9 and cs.player.status_amount(StatusId.FRAIL) == 1

def test_suck_gives_strength_for_a_hit_that_gets_through():
    cs = at("FOSSIL_STALKER", "LATCH", status=[status("SUCK", 3)])
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 3

def test_suck_gives_nothing_when_block_takes_the_whole_hit():
    cs = at("FOSSIL_STALKER", "LATCH", status=[status("SUCK", 3)])
    cs.player.block = 12
    turn(cs)
    assert StatusId.STRENGTH not in cs.enemies[0].status and cs.player.current_hp == 80

def test_suck_counts_each_hit_of_the_lash_that_gets_through():
    cs = at("FOSSIL_STALKER", "LASH", status=[status("SUCK", 3)])
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 6          # two hits of 3
    cs = at("FOSSIL_STALKER", "LASH", status=[status("SUCK", 3)])
    cs.player.block = 3
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 3          # the first hit is eaten by the block
    assert cs.player.current_hp == 80 - 3


# ---------------------------------------------------------------- Toadpole
def test_toadpole_goes_whirl_spiken_spit_whatever_it_starts_with():
    assert moves_over(at("TOADPOLE", "WHIRL"), 3) == ["WHIRL", "SPIKEN", "SPIKE_SPIT", "WHIRL"]
    assert moves_over(at("TOADPOLE", "SPIKEN"), 3) == ["SPIKEN", "SPIKE_SPIT", "WHIRL", "SPIKEN"]

def test_spiken_raises_thorns_and_spike_spit_takes_them_back():
    cs = at("TOADPOLE", "SPIKEN")
    turn(cs)
    e = cs.enemies[0]
    assert e.status_amount(StatusId.THORNS) == 2
    turn(cs)
    assert cs.player.current_hp == 80 - 9 and StatusId.THORNS not in e.status

def test_thorns_hurt_a_player_who_attacks_the_spiked_toadpole():
    cs = at("TOADPOLE", "SPIKEN")
    turn(cs)
    e = cs.enemies[0]
    hp = cs.player.current_hp
    e.apply_attack_damage(5, cs.player)
    assert cs.player.current_hp == hp - 2


# ---------------------------------------------------------------- Haunted Ship
def test_haunted_ship_haunts_once_then_swipes_and_stomps_in_turn():
    assert moves_over(at("HAUNTED_SHIP", "HAUNT"), 4) == ["HAUNT", "SWIPE", "STOMP", "SWIPE", "STOMP"]

def test_haunt_weakens_and_shuffles_five_dazed_into_the_discard_pile():
    cs = at("HAUNTED_SHIP", "HAUNT")
    turn(cs)
    assert cs.player.status_amount(StatusId.WEAK) == 3
    assert [c.card_id for c in cs.player.discard_pile] == [CardId.DAZED] * 5
    assert cs.player.current_hp == 80


# ---------------------------------------------------------------- Skulking Colony
def colony(**kw):
    return at("SKULKING_COLONY", "ZOOM", hp=80, max_hp=80, status=[status("HARDENED_SHELL", 20)], **kw)

def test_skulking_colony_cycle_with_its_two_identical_zooms():
    assert moves_over(colony(), 5) == ["ZOOM", "ZOOM_2", "INERTIA", "PIERCING_STABS", "ZOOM", "ZOOM_2"]

def test_the_game_names_the_second_zoom_zoom_move_2():
    table = MOVE_TABLES["SKULKING_COLONY"](0)
    assert table_move_id("SKULKING_COLONY", "ZOOM_MOVE_2", table) == "ZOOM_2"
    assert table_move_id("SKULKING_COLONY", "ZOOM_MOVE", table) == "ZOOM"

def test_inertia_hits_then_adds_strength():
    for ascension, strength in ((0, 2), (9, 4)):
        cs = ascended(at("SKULKING_COLONY", "INERTIA", ascension), "SKULKING_COLONY", ascension)
        turn(cs)
        assert cs.enemies[0].status_amount(StatusId.STRENGTH) == strength

def test_hardened_shell_lets_through_at_most_twenty_hit_points_a_turn():
    e = colony().enemies[0]
    player = colony().player
    e.apply_damage(30, player, True)
    assert e.current_hp == 60
    e.apply_damage(30, player, True)
    assert e.current_hp == 60

def test_hardened_shell_counts_every_hit_towards_the_cap():
    e = colony().enemies[0]
    player = colony().player
    for _ in range(3):
        e.apply_damage(8, player, True)
    assert e.current_hp == 80 - 20

def test_hit_points_blocked_do_not_count_towards_the_cap():
    e = colony().enemies[0]
    player = colony().player
    e.block = 10
    e.apply_damage(15, player, True)           # 5 get through
    e.apply_damage(15, player, True)           # 15 more
    assert e.current_hp == 80 - 20
    e.block = 30
    e.apply_damage(15, player, True)
    assert e.current_hp == 60 and e.block == 15

def test_hardened_shell_starts_again_with_each_side_turn():
    cs = colony()
    e, player = cs.enemies[0], cs.player
    sim = CombatSimulator(cs)
    e.apply_damage(50, player, True)
    assert e.current_hp == 60
    sim.fire(EventType.BEFORE_PLAYER_TURN)
    e.apply_damage(50, player, True)
    assert e.current_hp == 40

def test_hardened_shell_does_not_stop_losing_hit_points_directly():
    e = colony().enemies[0]
    e.apply_damage(100, colony().player, True)
    assert e.current_hp == 60 and e.current_hp > 0


# ---------------------------------------------------------------- captured from the game (Tests/data/act1_underdocks)
from agents import verify
from sts2_lite.Tests import captures

def under(enemy, name):
    return captures.load(enemy, name, captures.UNDERDOCKS)

def enemy_diffs(cs, want):
    return [d for d in verify.compare(cs, want) if d.startswith("enemy") and "hp" not in d]

def test_every_underdocks_capture_loads_with_moves_and_damage_agreeing():
    for enemy, name in (("corpse_slugs", "before_ravenous"), ("corpse_slugs", "after_ravenous"), ("fossil_stalker", "after_lash_1"),
                        ("fossil_stalker", "after_lash_2"), ("skulking_colony", "hardened_shell_full"),
                        ("skulking_colony", "hardened_shell_empty")):
        under(enemy, name)

def test_capture_a_slug_devours_the_one_bludgeoned_to_death():
    cs = under("corpse_slugs", "before_ravenous")
    cs.enemies[1].current_hp = 0
    CombatSimulator(cs).resolve_deaths()
    want = under("corpse_slugs", "after_ravenous")
    assert enemy_diffs(cs, want) == []
    assert cs.enemies[0].move_id == STUNNED and cs.enemies[0].after_stun == "GLOMP"

def test_capture_suck_gives_strength_for_both_lash_hits():
    cs = under("fossil_stalker", "after_lash_1")
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 3 and cs.enemies[0].attack_damage == 3
    rng.seed(0)
    turn(cs)
    assert cs.player.current_hp == 73 - 12
    want = under("fossil_stalker", "after_lash_2")
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == want.enemies[0].status_amount(StatusId.STRENGTH) == 9
    assert cs.player.current_hp == want.player.current_hp

def test_capture_hardened_shell_is_read_as_what_is_left_of_the_cap():
    full = under("skulking_colony", "hardened_shell_full").enemies[0]
    empty = under("skulking_colony", "hardened_shell_empty").enemies[0]
    assert (full.status[StatusId.HARDENED_SHELL].amount, full.status[StatusId.HARDENED_SHELL].shown_amount) == (20, 20)
    assert (empty.status[StatusId.HARDENED_SHELL].amount, empty.status[StatusId.HARDENED_SHELL].shown_amount) == (20, 0)
    empty.apply_damage(30, None, True)
    assert empty.current_hp == 55                      # nothing more gets through this turn
    full.apply_damage(30, None, True)
    assert full.current_hp == 55                       # 75 - 20, the same hit points as the other capture

def test_capture_hardened_shell_comes_back_after_the_turn_passes():
    cs = under("skulking_colony", "hardened_shell_empty")
    sim = CombatSimulator(cs)
    sim.fire(EventType.BEFORE_PLAYER_TURN)
    assert cs.enemies[0].status[StatusId.HARDENED_SHELL].shown_amount == 20
