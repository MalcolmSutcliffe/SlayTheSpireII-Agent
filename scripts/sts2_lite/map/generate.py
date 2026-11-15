"""Act map generation (StandardActMap) with its pruning.

Seven paths are walked up a 7-wide grid, merging where they meet (and never crossing); the first row is monsters, the last row rests, a treasure row sits
six rows below it; the other room types are dealt out at random under the placement rules; duplicate stretches are pruned (`pruning`). The game then centres, spreads and straightens the grid
(MapPostProcessing); that only moves nodes between columns, so it is left out: the sandbox does not draw the map, and a map read from the game already has it. The numbers of each type come from `MapPointTypeCounts` and `Act.GetMapPointTypes`.

The sandbox draws with its own `rng`, never the game's, so these maps have the game's shape but not its sequence (the shuffles are plain uniform shuffles)."""
from __future__ import annotations

from dataclasses import dataclass

from sts2_lite.map.points import ActMap, MapPoint, PointType
from sts2_lite.map.pruning import prune_and_repair

WIDTH = 7
PATHS = 7
LOWER_ROWS = 6              # no rest sites or elites below this row
FIRST_TYPE_ROW = 1
TREASURE_ROWS_BELOW_LAST = 6    # the treasure row is the last row minus 6 (GetRowCount() - 7)

LOWER_RESTRICTED = {PointType.REST_SITE, PointType.ELITE}
UPPER_RESTRICTED = {PointType.REST_SITE}
NO_NEIGHBOUR_REPEAT = {PointType.ELITE, PointType.REST_SITE, PointType.TREASURE, PointType.SHOP}
SIBLING_RESTRICTED = {PointType.REST_SITE, PointType.MONSTER, PointType.UNKNOWN, PointType.ELITE, PointType.SHOP}


SWARMING_ELITES_ASCENSION = 1
SWARMING_ELITE_FACTOR = 1.6


@dataclass(frozen=True)
class PointTypeCounts:
    """MapPointTypeCounts: how many of each type are dealt out."""
    unknowns : int
    rests : int
    shops : int = 3
    elites : int = 5
    ignore_rules : frozenset = frozenset()          # PointTypesThatIgnoreRules

    def ignores_rules(self, point_type : PointType) -> bool:
        return point_type in self.ignore_rules


def gaussian_int(rng, mean : int, std : int, low : int, high : int) -> int:
    """Rng.NextGaussianInt: Box-Muller, redrawn until it lands in [low, high]."""
    import math
    while True:
        d, u = 1.0 - rng.random(), 1.0 - rng.random()
        value = round(mean + std * math.sqrt(-2.0 * math.log(d)) * math.sin(2 * math.pi * u))
        if low <= value <= high:
            return value


def standard_unknown_count(rng) -> int:
    return gaussian_int(rng, 12, 1, 10, 14)         # MapPointTypeCounts.StandardRandomUnknownCount


def point_type_counts(act_id : str, rng, ascension : int = 0) -> PointTypeCounts:
    """Act.GetMapPointTypes, with the elite count of MapPointTypeCounts (5, or 8 with Swarming Elites)."""
    if act_id in ("OVERGROWTH", "UNDERDOCKS"):
        rests = gaussian_int(rng, 7, 1, 6, 7)
        unknowns = standard_unknown_count(rng)
    elif act_id == "HIVE":
        rests = gaussian_int(rng, 6, 1, 6, 7)
        unknowns = standard_unknown_count(rng) - 1
    elif act_id == "GLORY":
        rests = rng.randrange(5, 7)         # Rng.NextInt(5, 7): the upper bound is exclusive
        unknowns = standard_unknown_count(rng) - 1
    else:
        raise KeyError(act_id)
    elites = round(5 * (SWARMING_ELITE_FACTOR if ascension >= SWARMING_ELITES_ASCENSION else 1.0))
    return PointTypeCounts(unknowns, rests, elites=elites)


class _Builder:
    def __init__(self, rng, rooms : int, counts : PointTypeCounts, second_boss : bool, treasure_as_elite : bool):
        self.rng = rng
        self.rows = rooms + 1
        self.counts = counts
        self.treasure_as_elite = treasure_as_elite
        self.grid : list[list[MapPoint | None]] = [[None] * self.rows for _ in range(WIDTH)]
        self.boss = MapPoint(WIDTH // 2, self.rows)
        self.start = MapPoint(WIDTH // 2, 0)
        self.second_boss = MapPoint(WIDTH // 2, self.rows + 1) if second_boss else None
        self.start_points : list[MapPoint] = []

    # --- paths
    def point(self, col : int, row : int) -> MapPoint:
        found = self.grid[col][row]
        if found is None:
            found = self.grid[col][row] = MapPoint(col, row)
        return found

    def invalid_crossover(self, current : MapPoint, target : int) -> bool:
        """A path that would cross another one going the opposite way on the same step."""
        step = target - current.col
        if step == 0:
            return False
        beside = self.grid[target][current.row]
        return beside is not None and any(child.col - beside.col == -step for child in beside.children)

    def next_col(self, current : MapPoint) -> int:
        options = [-1, 0, 1]
        self.rng.shuffle(options)
        for option in options:
            target = {-1: max(0, current.col - 1), 0: current.col, 1: min(current.col + 1, WIDTH - 1)}[option]
            if not self.invalid_crossover(current, target):
                return target
        raise RuntimeError("no next node")

    def generate(self):
        for i in range(PATHS):
            first = self.point(self.rng.randrange(WIDTH), 1)
            if i == 1:
                while first in self.start_points:
                    first = self.point(self.rng.randrange(WIDTH), 1)
            self.start_points.append(first)
            current = first
            while current.row < self.rows - 1:
                nxt = self.point(self.next_col(current), current.row + 1)
                current.add_child(nxt)
                current = nxt
        for p in self.row(self.rows - 1):
            p.add_child(self.boss)
        if self.second_boss is not None:
            self.boss.add_child(self.second_boss)
        for p in self.row(1):
            self.start.add_child(p)

    def row(self, row : int) -> list[MapPoint]:
        return [p for col in range(WIDTH) if (p := self.grid[col][row]) is not None]

    def all_points(self) -> list[MapPoint]:
        return [p for row in range(self.rows) for p in self.row(row)]

    def all_points_by_column(self) -> list[MapPoint]:
        """ActMap.GetAllMapPoints: column by column."""
        return [p for col in range(WIDTH) for row in range(self.rows) if (p := self.grid[col][row]) is not None]

    # --- types
    def assign_types(self):
        for p in self.row(self.rows - 1):
            p.type, p.can_be_modified = PointType.REST_SITE, False
        special = PointType.ELITE if self.treasure_as_elite else PointType.TREASURE
        for p in self.row(self.rows - 1 - TREASURE_ROWS_BELOW_LAST):
            p.type, p.can_be_modified = special, False
        for p in self.row(1):
            p.type, p.can_be_modified = PointType.MONSTER, False
        queue = ([PointType.REST_SITE] * self.counts.rests + [PointType.SHOP] * self.counts.shops
                 + [PointType.ELITE] * self.counts.elites + [PointType.UNKNOWN] * self.counts.unknowns)
        for _ in range(3):
            if not queue:
                break
            free = [p for p in self.all_points() if p.type == PointType.UNASSIGNED]
            self.rng.shuffle(free)
            for p in free:
                if not queue:
                    break
                p.type = self.next_valid_type(queue, p)
        for p in self.all_points():
            if p.type == PointType.UNASSIGNED:
                p.type = PointType.MONSTER
        self.boss.type = PointType.BOSS
        self.start.type = PointType.ANCIENT
        if self.second_boss is not None:
            self.second_boss.type = PointType.BOSS

    def next_valid_type(self, queue : list[PointType], point : MapPoint) -> PointType:
        for _ in range(len(queue)):
            candidate = queue.pop(0)
            if self.counts.ignores_rules(candidate) or self.valid(candidate, point):
                return candidate
            queue.append(candidate)
        return PointType.UNASSIGNED

    def valid(self, kind : PointType, p : MapPoint) -> bool:
        if p.row < LOWER_ROWS and kind in LOWER_RESTRICTED:
            return False
        if p.row >= self.rows - 3 and kind in UPPER_RESTRICTED:
            return False
        if kind in NO_NEIGHBOUR_REPEAT and any(n.type == kind for n in p.parents + p.children):
            return False
        if kind in SIBLING_RESTRICTED and any(s.type == kind for parent in p.parents for s in parent.children if s is not p):
            return False
        return True


class _SpoilsBuilder(_Builder):
    """SpoilsActMap: an hourglass. The paths narrow towards one centred treasure room (row GetRowCount() - 7) and widen again after it. Everything else (the type dealing, the
    rules, the pruning) is the standard map's."""
    MAX_PARENTS = 3
    MAX_CHILDREN = 3

    def __init__(self, rng, rooms : int, counts : PointTypeCounts):
        super().__init__(rng, rooms, counts, False, False)
        self.treasure_row = self.rows - 1 - TREASURE_ROWS_BELOW_LAST

    def allowed_columns(self, row : int) -> tuple[int, int]:
        centre = WIDTH // 2
        reach = min(centre, min(abs(row - self.treasure_row), min(centre, max(0, self.rows - 1 - row) + 1)))
        return max(0, centre - reach), min(WIDTH - 1, centre + reach)

    @staticmethod
    def centred_priority(col : int, centre : int) -> list[int]:
        toward = (centre > col) - (centre < col)
        order = ([toward] if toward else []) + [0] + ([-toward] if toward else [])
        return order + [d for d in (-1, 1) if d not in order]

    def next_col(self, current : MapPoint) -> int:
        row = current.row + 1
        low, high = self.allowed_columns(row)
        centre = WIDTH // 2
        options = [-1, 0, 1]
        distance = self.treasure_row - current.row
        if distance > 3 or distance <= 0:
            self.rng.shuffle(options)
        else:
            options = self.centred_priority(current.col, centre)
        for option in options:
            target = {-1: max(0, current.col - 1), 0: current.col, 1: min(current.col + 1, WIDTH - 1)}[option]
            if target < low or target > high or self.invalid_crossover(current, target):
                continue
            there = self.grid[target][row]
            if (there is None or current in there.parents or len(there.parents) < self.MAX_PARENTS) and \
                    (len(current.children) < self.MAX_CHILDREN or (there is not None and there in current.children)):
                return target
        target = min(max(centre, low), high)
        if abs(target - current.col) > 1:
            target = min(max(current.col + ((target > current.col) - (target < current.col)), low), high)
        if self.invalid_crossover(current, target):
            target = min(max(current.col, low), high)
        return target

    def generate(self):
        for i in range(PATHS):
            first = self.point(self.rng.randrange(WIDTH), 1)
            if i == 1:
                while first in self.start_points:
                    first = self.point(self.rng.randrange(WIDTH), 1)
            self.start_points.append(first)
            current = first
            while current.row < self.rows - 1:
                nxt = self.point(self.next_col(current), current.row + 1)
                current.add_child(nxt)
                current = nxt
        treasure = self.point(WIDTH // 2, self.treasure_row)
        treasure.type, treasure.can_be_modified = PointType.TREASURE, False
        for stray in self.row(self.treasure_row):
            if stray is treasure:
                continue
            for parent in list(stray.parents):
                parent.remove_child(stray)
                parent.add_child(treasure)
            for child in list(stray.children):
                stray.remove_child(child)
                treasure.add_child(child)
            self.grid[stray.col][stray.row] = None
        for p in self.row(self.rows - 1):
            p.add_child(self.boss)
        for p in self.row(1):
            self.start.add_child(p)

    def assign_types(self):
        for p in self.row(self.rows - 1):
            p.type, p.can_be_modified = PointType.REST_SITE, False
        for p in self.row(1):
            p.type, p.can_be_modified = PointType.MONSTER, False
        queue = ([PointType.REST_SITE] * self.counts.rests + [PointType.SHOP] * self.counts.shops
                 + [PointType.ELITE] * self.counts.elites + [PointType.UNKNOWN] * self.counts.unknowns)
        for _ in range(3):
            if not queue:
                break
            free = [p for p in self.all_points() if p.type == PointType.UNASSIGNED]
            self.rng.shuffle(free)
            for p in free:
                if not queue:
                    break
                p.type = self.next_valid_type(queue, p)
        for p in self.all_points():
            if p.type == PointType.UNASSIGNED:
                p.type = PointType.MONSTER
        self.boss.type = PointType.BOSS
        self.start.type = PointType.ANCIENT


def generate_spoils_map(act_id : str, rng, rooms : int, ascension : int = 0, counts : PointTypeCounts | None = None, prune : bool = True) -> ActMap:
    """SpoilsActMap (act 2 with the Spoils Map card): the hourglass through one treasure room."""
    chosen = counts or point_type_counts(act_id, rng, ascension)
    b = _SpoilsBuilder(rng, rooms, chosen)
    b.generate()
    b.assign_types()
    if prune:
        prune_and_repair(b.grid, b.start_points, b.start, b.all_points_by_column, chosen, rng, b.valid)
    return ActMap(b.grid, b.start, b.boss, None, b.rows, b.start_points)


def generate_map(act_id : str, rng, rooms : int, ascension : int = 0, second_boss : bool = False, treasure_as_elite : bool = False,
                 counts : PointTypeCounts | None = None, prune : bool = True) -> ActMap:
    """The map of an act with `rooms` rooms (Act.room_count): the rooms are rows 1..rooms, with the ancient below and the boss above."""
    chosen = counts or point_type_counts(act_id, rng, ascension)
    b = _Builder(rng, rooms, chosen, second_boss, treasure_as_elite)
    b.generate()
    b.assign_types()
    if prune:
        prune_and_repair(b.grid, b.start_points, b.start, b.all_points_by_column, chosen, rng, b.valid)
    return ActMap(b.grid, b.start, b.boss, b.second_boss, b.rows, b.start_points)


GOLDEN_PATH = ("MONSTER", "UNKNOWN", "MONSTER", "REST_SITE", "MONSTER", "REST_SITE", "UNKNOWN", "TREASURE", "UNKNOWN", "TREASURE", "UNKNOWN", "SHOP",
               "ELITE", "REST_SITE", "ELITE", "REST_SITE")


def golden_path_map() -> ActMap:
    """GoldenPathActMap (Golden Compass, single player): one column of 16 rooms from the ancient to a single boss, no second boss."""
    rows = len(GOLDEN_PATH) + 1
    grid : list[list[MapPoint | None]] = [[None] * rows for _ in range(WIDTH)]
    start, boss = MapPoint(WIDTH // 2, 0, PointType.ANCIENT), MapPoint(WIDTH // 2, rows, PointType.BOSS)
    previous = start
    for i, name in enumerate(GOLDEN_PATH):
        point = grid[WIDTH // 2][i + 1] = MapPoint(WIDTH // 2, i + 1, PointType[name])
        previous.add_child(point)
        previous = point
    previous.add_child(boss)
    return ActMap(grid, start, boss, None, rows, [grid[WIDTH // 2][1]])
