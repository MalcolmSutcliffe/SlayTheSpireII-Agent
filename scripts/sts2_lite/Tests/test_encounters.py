"""Encounters: exact monster generation, the acts' room lists and fights built from an encounter id. Run from scripts/: python -m pytest sts2_lite/Tests"""
import random

import pytest

from sts2_lite.Tests import captures
from sts2_lite.encounters import ACTS, ENCOUNTERS, MONSTERS, build_combat, build_enemies, generate_rooms
from sts2_lite.encounters.builder import power_amount
from sts2_lite.enemy_moves import MOVE_TABLES, table_move_id
from sts2_lite.status import StatusId

ASCENSIONS = (0, 1, 8, 9, 10)


def possible(opening) -> set[str]:
    kind = opening[0]
    if kind == "fixed":
        return {opening[1]}
    if kind == "flag":
        return {opening[2], opening[3]}
    if kind == "idx":
        return set(opening[1])
    if kind == "slot":
        return set(opening[1].values()) | (possible(opening[2]) if opening[2] else set())
    if kind == "random":
        return {m for m, _ in opening[1]}
    if kind == "nibbit":
        return {"BUTT_MOVE", "SLICE_MOVE", "HISS_MOVE"}
    if kind == "rat":
        return {"SCRATCH_MOVE", "DISEASE_BITE_MOVE", "SCREECH_MOVE"}
    return {"NASTY_BITE_MOVE", "WRIGGLE_MOVE", "SPAWNED_MOVE"}


def test_every_encounter_builds_at_every_ascension():
    rng = random.Random(0)
    for encounter_id, encounter in ENCOUNTERS.items():
        if encounter_id == "FAKE_MERCHANT_EVENT_ENCOUNTER":
            continue            # the Fake Merchant has no move table yet
        for ascension in ASCENSIONS:
            for _ in range(20):
                enemies = build_enemies(encounter_id, ascension, rng)
                assert enemies and all(e.moves is not None and e.move_id in e.moves for e in enemies)
                assert all(0 < e.current_hp <= e.max_hp for e in enemies)


def test_every_monster_with_a_table_has_openings_that_are_in_its_table():
    for monster, setup in MONSTERS.items():
        table = MOVE_TABLES.get(monster)
        if table is None:
            continue
        moves = table(0)
        for game_move in possible(setup.opening):
            assert table_move_id(monster, game_move, moves) is not None, (monster, game_move)


def test_hit_points_are_rolled_inside_the_range_and_tough_enemies_have_more():
    rng = random.Random(1)
    seen = set()
    for _ in range(200):
        seen.add(build_enemies("NIBBITS_WEAK", 0, rng)[0].max_hp)
    assert seen == set(range(42, 47))
    seen = {build_enemies("NIBBITS_WEAK", 8, rng)[0].max_hp for _ in range(200)}
    assert seen == set(range(44, 49))


def test_decimillipede_segments_never_share_maximum_hit_points():
    rng = random.Random(2)
    for ascension in (0, 8):
        for _ in range(200):
            hps = [e.max_hp for e in build_enemies("DECIMILLIPEDE_ELITE", ascension, rng)]
            assert len(set(hps)) == 3 and all(hp % 2 == 0 for hp in hps)


def test_corpse_slugs_start_on_different_moves():
    rng = random.Random(3)
    for _ in range(50):
        moves = [e.move_id for e in build_enemies("CORPSE_SLUGS_NORMAL", 0, rng)]
        assert len(set(moves)) == 3
        assert len({e.move_id for e in build_enemies("CORPSE_SLUGS_WEAK", 0, rng)}) == 2


def test_ruby_raiders_are_three_different_kinds():
    rng = random.Random(4)
    for _ in range(100):
        kinds = [e.enemy_id for e in build_enemies("RUBY_RAIDERS_NORMAL", 0, rng)]
        assert len(set(kinds)) == 3 and all(k.endswith("_0") for k in kinds)


def test_encounters_with_two_of_a_kind_number_them_in_order():
    ids = [e.enemy_id for e in build_enemies("INKLETS_NORMAL", 0, random.Random(5))]
    assert ids == ["INKLET_0", "INKLET_1", "INKLET_2"]
    assert [e.move_id for e in build_enemies("INKLETS_NORMAL", 0, random.Random(5))] == ["JAB", "WHIRLWIND", "JAB"]


def test_openings_that_depend_on_the_encounter():
    rng = random.Random(6)
    assert [e.move_id for e in build_enemies("NIBBITS_NORMAL", 0, rng)] == ["SLICE", "HISS"]
    assert [e.move_id for e in build_enemies("NIBBITS_WEAK", 0, rng)] == ["BUTT"]
    assert [e.move_id for e in build_enemies("TOADPOLES_WEAK", 0, rng)] == ["SPIKEN", "WHIRL"]
    assert [e.move_id for e in build_enemies("PHANTASMAL_GARDENERS_ELITE", 0, rng)] == ["FLAIL", "BITE", "LASH", "ENLARGE"]
    assert [e.move_id for e in build_enemies("CHOMPERS_NORMAL", 0, rng)] == ["CLAMP", "SCREECH"]
    assert [e.move_id for e in build_enemies("THE_KIN_BOSS", 0, rng)][:2] == ["POWER_DANCE", "QUICK_SLASH"]
    assert [e.move_id for e in build_enemies("DENSE_VEGETATION_EVENT_ENCOUNTER", 0, rng)] == ["BITE", "WRIGGLE", "BITE", "WRIGGLE"]


def test_starting_powers_follow_the_ascension():
    rng = random.Random(7)
    assert build_enemies("VANTOM_BOSS", 0, rng)[0].status[StatusId.SLIPPERY].amount == 8
    assert build_enemies("VANTOM_BOSS", 8, rng)[0].status[StatusId.SLIPPERY].amount == 9
    assert build_enemies("CORPSE_SLUGS_WEAK", 9, rng)[0].status[StatusId.RAVENOUS].amount == 5
    assert power_amount("deadly", 4, 5, 8) == 4


def test_punch_off_starts_with_less_hit_points():
    rng = random.Random(8)
    for _ in range(50):
        for e in build_enemies("PUNCH_OFF_EVENT_ENCOUNTER", 0, rng):
            assert 2 <= e.max_hp - e.current_hp <= 9 or e.current_hp == 1


@pytest.mark.parametrize("act", ACTS)
def test_room_lists_follow_the_game_rules(act):
    a = ACTS[act]
    for seed in range(100):
        rooms = generate_rooms(a, random.Random(seed))
        assert len(rooms.normal) == a.base_rooms and len(rooms.elite) == 15
        assert all(e.weak for e in rooms.normal[:a.weak_rooms]) and not any(e.weak for e in rooms.normal[a.weak_rooms:])
        assert all(e.room == "Elite" for e in rooms.elite) and rooms.boss.room == "Boss" and rooms.ancient in a.ancients
        for pair in zip(rooms.normal, rooms.normal[1:]):
            if pair[0].id == pair[1].id:
                assert len(a.weak) == 1 or len(a.regular) == 1       # only possible when the pool has nothing else
        assert rooms.second_boss is None


def test_a_single_weak_pool_entry_can_only_repeat_when_refilled():
    rooms = generate_rooms(ACTS["GLORY"], random.Random(0))
    assert [e.weak for e in rooms.normal[:2]] == [True, True]


def test_double_boss_picks_two_different_bosses_in_the_last_act():
    for seed in range(50):
        rooms = generate_rooms(ACTS["GLORY"], random.Random(seed), ascension=10, last_act=True)
        assert rooms.second_boss is not None and rooms.second_boss is not rooms.boss
        assert generate_rooms(ACTS["GLORY"], random.Random(seed), ascension=10).second_boss is None


def test_every_act_encounter_is_defined_and_every_event_only_encounter_is_outside_the_acts():
    listed = {e for act in ACTS.values() for e in act.encounters}
    assert listed <= set(ENCOUNTERS)
    assert {e for e in ENCOUNTERS if e.endswith("EVENT_ENCOUNTER")}.isdisjoint(listed)


TURN_ONE = [("living_fog", "turn_1", captures.UNDERDOCKS), ("lagavulin_matriarch", "turn_1", captures.UNDERDOCKS),
            ("phantasmal_gardeners", "turn_1", captures.UNDERDOCKS), ("soul_fysh", "turn_1", captures.UNDERDOCKS),
            ("two_tailed_rats", "turn_1", captures.UNDERDOCKS), ("waterfall_giant", "turn_1", captures.UNDERDOCKS),
            ("skulking_colony", "hardened_shell_full", captures.UNDERDOCKS), ("corpse_slugs", "before_ravenous", captures.UNDERDOCKS),
            ("queen", "turn_1", captures.GLORY), ("test_subject", "phase_1", captures.GLORY), ("globe_head", "before_power", captures.GLORY),
            ("kaiser_crab", "surrounded_from_left", captures.HIVE), ("vantom", "ink_blot", captures.ACT1), ("cubex_construct", "charge_up", captures.ACT1),
            ("raiders", "crossbow_assassin_tracker_1", captures.ACT1), ("slimes", "weak_fight", captures.ACT1)]


@pytest.mark.parametrize("enemy,name,act", TURN_ONE)
def test_a_first_turn_capture_agrees_with_the_monster_data(enemy, name, act):
    state = captures.raw(enemy, name, act)
    ascension = state.get("context", {}).get("ascension", 0)
    for raw in state["enemies"]:
        monster = raw["entity_id"].rpartition("_")[0]
        setup = MONSTERS[monster]
        low, high, tough_low, tough_high = setup.hp
        if ascension >= 8:
            low, high = tough_low, tough_high
        assert low <= raw["max_hp"] <= high
        mine = {StatusId[s].name: power_amount(k, b, h, ascension) for s, who, k, b, h in setup.powers if who == "self"}
        assert {s["id"][:-6]: s["amount"] for s in raw["status"]} == mine
        if "move_id" in raw:
            assert raw["move_id"] in possible(setup.opening)
