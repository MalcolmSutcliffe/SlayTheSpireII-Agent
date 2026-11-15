"""Act map generation and the "?" room odds."""
import random

import pytest

from sts2_lite.encounters import ACTS
from sts2_lite.map import PointType, UnknownRoomOdds, generate_map, point_type_counts
from sts2_lite.map.generate import PointTypeCounts, gaussian_int
from sts2_lite.map.points import MapPoint
from sts2_lite.map.pruning import find_matching_segments, find_matching_segments_exact, prune_duplicate_segments

ACT_IDS = ["OVERGROWTH", "UNDERDOCKS", "HIVE", "GLORY"]
ROOMS = {a: ACTS[a].room_count() for a in ACT_IDS}


def maps(n=60):
    for seed in range(n):
        act = ACT_IDS[seed % 4]
        yield act, generate_map(act, random.Random(seed), ROOMS[act], second_boss=seed % 7 == 0)


def test_rows_and_edges_of_the_map():
    for act, m in maps():
        rooms = ROOMS[act]
        assert m.rows == rooms + 1 and m.boss.coord == (3, rooms + 1) and m.start.coord == (3, 0)
        assert [p.row for p in m.start.children] == [1] * len(m.start.children) and 1 <= len(m.start.children) <= 7
        for p in m.points():
            assert 1 <= p.row <= rooms and p.parents
            assert p.children and all(c.row == p.row + 1 and abs(c.col - p.col) <= 1 for c in p.children if c is not m.boss)
            assert all(len(set(map(id, p.children))) == len(p.children) for _ in [0])


def test_every_path_runs_the_whole_height():
    for act, m in maps():
        stack = [(m.start, 0)]
        seen = set()
        while stack:
            p, depth = stack.pop()
            if p is m.boss:
                assert depth == m.rows
                continue
            for c in p.children:
                if (id(p), id(c)) not in seen:
                    seen.add((id(p), id(c)))
                    stack.append((c, depth + 1))


def test_paths_never_cross():
    for act, m in maps():
        for p in m.points():
            for c in p.children:
                beside = m.grid[c.col][p.row] if c.col != p.col else None
                if beside is not None:
                    assert all(o.col - beside.col != -(c.col - p.col) for o in beside.children)


def test_the_fixed_rows():
    for act, m in maps():
        last = m.rows - 1
        assert {p.type for p in m.points() if p.row == 1} == {PointType.MONSTER}
        assert {p.type for p in m.points() if p.row == last} == {PointType.REST_SITE}
        assert {p.type for p in m.points() if p.row == last - 6} == {PointType.TREASURE}
        assert m.boss.type == PointType.BOSS and m.start.type == PointType.ANCIENT


def test_placement_rules():
    for act, m in maps(120):
        last = m.rows - 1
        for p in m.points():
            assert p.type != PointType.UNASSIGNED
            if p.row < 6 and p.row > 0:
                assert p.type not in (PointType.REST_SITE, PointType.ELITE)
            if last - 2 <= p.row < last:
                assert p.type != PointType.REST_SITE
            if p.can_be_modified and p.type in (PointType.ELITE, PointType.REST_SITE, PointType.SHOP, PointType.TREASURE):        # the fixed rows are exempt
                assert all(n.type != p.type for n in p.parents + p.children if n is not m.start and n is not m.boss)
                assert all(s.type != p.type for q in p.parents for s in q.children if s is not p)


def test_type_totals_do_not_exceed_what_was_asked_for():
    for seed in range(30):
        counts = PointTypeCounts(unknowns=10, rests=6, shops=2, elites=4)
        m = generate_map("OVERGROWTH", random.Random(seed), 15, counts=counts)
        types = [p.type for p in m.points() if 1 < p.row < m.rows - 1]
        assert types.count(PointType.SHOP) <= 2 and types.count(PointType.ELITE) <= 4 and types.count(PointType.UNKNOWN) <= 10
        assert sum(p.type == PointType.REST_SITE for p in m.points() if p.row < m.rows - 1) <= 6


def test_a_second_boss_sits_above_the_first():
    m = generate_map("GLORY", random.Random(1), 13, second_boss=True)
    assert m.second_boss.coord == (3, 15) and m.boss.children == [m.second_boss] and m.second_boss.type == PointType.BOSS
    assert generate_map("GLORY", random.Random(1), 13).second_boss is None


def test_treasure_can_be_swapped_for_elites():
    m = generate_map("GLORY", random.Random(2), 13, treasure_as_elite=True)
    assert {p.type for p in m.points() if p.row == m.rows - 7} == {PointType.ELITE}


def test_point_counts_follow_the_acts():
    for seed in range(100):
        r = random.Random(seed)
        assert 6 <= point_type_counts("OVERGROWTH", r).rests <= 7 and 6 <= point_type_counts("HIVE", r).rests <= 7 and point_type_counts("GLORY", r).rests in (5, 6)
        assert 10 <= point_type_counts("UNDERDOCKS", r).unknowns <= 14 and 9 <= point_type_counts("HIVE", r).unknowns <= 13
    assert point_type_counts("OVERGROWTH", random.Random(1)).elites == 5 and point_type_counts("OVERGROWTH", random.Random(1), ascension=1).elites == 8
    assert point_type_counts("OVERGROWTH", random.Random(1)).shops == 3


def test_most_maps_get_every_type_they_asked_for():
    short = 0
    for seed in range(60):
        m = generate_map("OVERGROWTH", random.Random(seed), 15)
        types = [p.type for p in m.points()]
        short += types.count(PointType.SHOP) < 3 or types.count(PointType.ELITE) < 5
    assert short <= 6


def test_columns_and_the_grid_agree():
    for act, m in maps(80):
        for p in m.points():
            assert m.grid[p.col][p.row] is p and 0 <= p.col < 7
            assert all(abs(c.col - p.col) <= 1 for c in p.children if c is not m.boss and c is not m.second_boss)
            assert all(abs(q.col - p.col) <= 1 for q in p.parents if q is not m.start)


def _grid(rows=4):
    return [[None] * rows for _ in range(7)]


def test_two_identical_stretches_are_cut_down_to_one():
    grid = _grid()
    start, a, b, m, boss = MapPoint(3, 0), MapPoint(2, 1), MapPoint(4, 1), MapPoint(3, 2), MapPoint(3, 3)
    for p in (a, b, m):
        grid[p.col][p.row] = p
    start.type, boss.type = PointType.ANCIENT, PointType.BOSS
    a.type = b.type = PointType.MONSTER
    m.type = PointType.MONSTER
    start.add_child(a); start.add_child(b); a.add_child(m); b.add_child(m); m.add_child(boss)
    assert len(find_matching_segments(start)) == 1
    prune_duplicate_segments(grid, [a, b], start, random.Random(1))
    assert len(start.children) == 1 and len(m.parents) == 1 and find_matching_segments(start) == []
    assert sum(cell is not None for col in grid for cell in col) == 2


def test_stretches_with_different_rooms_are_kept():
    grid = _grid()
    start, a, b, m, boss = MapPoint(3, 0), MapPoint(2, 1), MapPoint(4, 1), MapPoint(3, 2), MapPoint(3, 3)
    for p in (a, b, m):
        grid[p.col][p.row] = p
    start.type, boss.type, a.type, b.type, m.type = PointType.ANCIENT, PointType.BOSS, PointType.MONSTER, PointType.UNKNOWN, PointType.MONSTER
    start.add_child(a); start.add_child(b); a.add_child(m); b.add_child(m); m.add_child(boss)
    assert find_matching_segments(start) == []


# --- "?" rooms ----------------------------------------------------------------------------------------------------------------------------------------
class Fixed:
    def __init__(self, *numbers):
        self.numbers = list(numbers)

    def random(self):
        return self.numbers.pop(0)


def test_unknown_room_bands_start_with_mostly_events():
    odds = UnknownRoomOdds()
    assert odds.event_odds == pytest.approx(0.85)
    assert [UnknownRoomOdds().roll(Fixed(x)) for x in (0.0, 0.1, 0.11, 0.12, 0.121, 0.15, 0.151, 0.9)] == ["Monster", "Monster", "Treasure", "Treasure", "Shop", "Shop", "Event", "Event"]


def test_a_type_not_rolled_grows_and_a_rolled_type_resets():
    odds = UnknownRoomOdds()
    assert odds.roll(Fixed(0.5)) == "Event"
    assert odds.current["Monster"] == pytest.approx(0.2) and odds.current["Treasure"] == pytest.approx(0.04) and odds.current["Shop"] == pytest.approx(0.06)
    assert odds.current["Elite"] == -1.0 and odds.event_odds < 0.85
    assert odds.roll(Fixed(0.0)) == "Monster" and odds.current["Monster"] == 0.1 and odds.current["Shop"] == pytest.approx(0.09)
    odds.reset()
    assert odds.current == odds.base


def test_blacklisted_rooms_are_not_rolled_and_do_not_grow():
    odds = UnknownRoomOdds()
    assert odds.roll(Fixed(0.0), blacklist={"Monster"}) == "Treasure"
    odds = UnknownRoomOdds()
    odds.roll(Fixed(0.9), blacklist={"Shop"})
    assert odds.current["Shop"] == 0.03 and odds.current["Monster"] == pytest.approx(0.2)


def test_long_run_shares_of_unknown_rooms():
    r = random.Random(8)
    odds = UnknownRoomOdds()
    counts = {}
    for _ in range(20000):
        room = odds.roll(r)
        counts[room] = counts.get(room, 0) + 1
    assert "Elite" not in counts and counts["Event"] > counts["Monster"] > counts["Treasure"] > 0


def test_the_fast_segment_search_finds_what_the_game_search_finds():
    agree = 0
    for seed in range(12):
        m = generate_map("OVERGROWTH", random.Random(seed), 15, prune=False)
        fast = {tuple(map(id, g[0])) for g in find_matching_segments(m.start)}
        exact = {tuple(map(id, g[0])) for g in find_matching_segments_exact(m.start)}
        keys = lambda groups: sorted(sorted(map(lambda s: tuple(p.coord for p in s), g)) for g in groups)
        agree += keys(find_matching_segments(m.start)) == keys(find_matching_segments_exact(m.start))
    assert agree >= 10      # the order segments are found in can change which of two overlapping ones is kept


def test_the_spoils_map_is_an_hourglass_through_one_centred_treasure_room():
    import random
    from sts2_lite.map import PointType, generate_spoils_map
    for seed in range(60):
        m = generate_spoils_map("HIVE", random.Random(seed), 14)
        treasure_row = m.rows - 7
        treasures = [p for p in m.points() if p.type == PointType.TREASURE]
        assert len(treasures) == 1 and treasures[0].coord == (3, treasure_row)
        assert [p.coord for p in m.points() if p.row == treasure_row] == [(3, treasure_row)]
        for p in m.points():                        # the paths narrow towards the treasure and widen after it, and every room can be reached
            reach = min(3, abs(p.row - treasure_row), m.rows - p.row)
            assert 3 - reach <= p.col <= 3 + reach or p.row == 1
            assert p.row == 1 or p.parents
        assert all(c.type in (PointType.REST_SITE,) for p in m.points() if p.row == m.rows - 1 for c in [p])
        assert sum(p.type == PointType.SHOP for p in m.points()) <= 3
