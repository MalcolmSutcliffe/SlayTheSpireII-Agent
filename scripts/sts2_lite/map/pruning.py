"""MapPathPruning: after the types are placed, two different stretches of the map with the same endpoints and the same sequence of room types are
duplicates, and one of them is removed (or its link broken); then the types that fell short of their count are put back on monsters.
A port of the decompiled class, step for step (segment keys are the game's strings, since their sorted order decides which duplicate is dealt with first)."""
from __future__ import annotations

from sts2_lite.map.points import MapPoint, PointType

# MapPointType enum values: they are part of the segment key
TYPE_VALUE = {PointType.UNASSIGNED: 0, PointType.UNKNOWN: 1, PointType.SHOP: 2, PointType.TREASURE: 3, PointType.REST_SITE: 4, PointType.MONSTER: 5,
              PointType.ELITE: 6, PointType.BOSS: 7, PointType.ANCIENT: 8}
TYPE_TEXT = {kind: str(value) for kind, value in TYPE_VALUE.items()}
MAX_PRUNE_ROUNDS = 50
REPAIR_ROUNDS = 3


def prune_and_repair(grid, start_points : list[MapPoint], start : MapPoint, all_points, counts, rng, is_valid):
    """`all_points()` lists the grid's points column by column (ActMap.GetAllMapPoints); `is_valid(type, point)` is StandardActMap.IsValidPointType."""
    for _ in range(REPAIR_ROUNDS):
        prune_duplicate_segments(grid, start_points, start, rng)
        if not repair_pruned_types(all_points, counts, rng, is_valid):
            break


def repair_pruned_types(all_points, counts, rng, is_valid) -> bool:
    changed = False
    for kind, target in ((PointType.SHOP, counts.shops), (PointType.ELITE, counts.elites), (PointType.REST_SITE, counts.rests), (PointType.UNKNOWN, counts.unknowns)):
        changed |= repair_type(all_points, kind, target, rng, is_valid)
    return changed


def repair_type(all_points, kind : PointType, target : int, rng, is_valid) -> bool:
    missing = target - sum(p.type == kind for p in all_points())
    if missing <= 0:
        return False
    monsters = [p for p in all_points() if p.type == PointType.MONSTER and p.can_be_modified]
    rng.shuffle(monsters)
    changed = False
    for p in monsters:
        if missing == 0:
            break
        if is_valid(kind, p):
            p.type = kind
            missing -= 1
            changed = True
    return changed


def prune_duplicate_segments(grid, start_points, start : MapPoint, rng):
    rounds = 0
    matching = find_matching_segments(start)
    while prune_paths(grid, start_points, matching, rng):
        rounds += 1
        if rounds > MAX_PRUNE_ROUNDS:
            raise RuntimeError(f"unable to prune matching segments in {rounds} iterations")
        matching = find_matching_segments(start)


def find_matching_segments(start : MapPoint) -> list[list[list[MapPoint]]]:
    """Groups of two or more segments with the same ends and the same room types, in the order of their sorted keys (SortedDictionary, ordinal).

    The game lists every full path from the start and cuts segments out of each (`find_matching_segments_exact`). A map has thousands of paths, so this walks down
    from each point that starts a segment instead and reaches the same segments with far less work; only the order they are found in differs, and the group is
    shuffled before anything is cut anyway."""
    reachable = reachable_from(start)
    can_finish = {}
    segments : dict[str, list[list[MapPoint]]] = {}

    def finishes(p : MapPoint) -> bool:
        found = can_finish.get(p)
        if found is None:
            found = can_finish[p] = p.type == PointType.BOSS or any(finishes(c) for c in p.children)
        return found

    def walk(path : list[MapPoint], codes : list[str], head : str):
        last = path[-1]
        if len(path) >= 3 and len(last.parents) >= 2:
            key = f"{head}{last.col},{last.row}-" + ",".join(codes)
            add_segment(path, segments, key)
        if last.type != PointType.BOSS:
            for child in last.children:
                if finishes(child):
                    path.append(child)
                    codes.append(TYPE_TEXT[child.type])
                    walk(path, codes, head)
                    codes.pop()
                    path.pop()

    for p in sorted(reachable, key=lambda q: (q.row, q.col)):
        if (len(p.children) > 1 or p.row == 0) and finishes(p):
            walk([p], [TYPE_TEXT[p.type]], "0-" if p.row == 0 else f"{p.col},{p.row}-")
    return [segments[key] for key in sorted(segments) if len(segments[key]) > 1]


def reachable_from(start : MapPoint) -> set[MapPoint]:
    seen, stack = {start}, [start]
    while stack:
        for child in stack.pop().children:
            if child not in seen:
                seen.add(child)
                stack.append(child)
    return seen


def add_segment(path : list[MapPoint], segments : dict, key : str | None = None):
    segment = list(path)
    key = key or segment_key(segment)
    if key not in segments:
        segments[key] = [segment]
    elif not any(overlapping(existing, segment) for existing in segments[key]):
        segments[key].append(segment)


def find_matching_segments_exact(start : MapPoint) -> list[list[list[MapPoint]]]:
    """The game's own way (every full path, segments cut out of each in order). Slow; kept to check `find_matching_segments` against."""
    segments : dict[str, list[list[MapPoint]]] = {}
    for path in find_all_paths(start):
        add_segments(path, segments)
    return [segments[key] for key in sorted(segments) if len(segments[key]) > 1]


def find_all_paths(point : MapPoint) -> list[list[MapPoint]]:
    if point.type == PointType.BOSS:
        return [[point]]
    return [[point] + rest for child in point.children for rest in find_all_paths(child)]


def add_segments(path : list[MapPoint], segments : dict):
    for i in range(len(path) - 1):
        if not (len(path[i].children) > 1 or path[i].row == 0):
            continue
        for j in range(2, len(path) - i):
            if len(path[i + j].parents) >= 2:
                add_segment(path[i:i + j + 1], segments)


def segment_key(segment : list[MapPoint]) -> str:
    first, last = segment[0], segment[-1]
    head = f"{first.row}-{last.col},{last.row}-" if first.row == 0 else f"{first.col},{first.row}-{last.col},{last.row}-"
    return head + ",".join(str(TYPE_VALUE[p.type]) for p in segment)


def overlapping(a : list[MapPoint], b : list[MapPoint]) -> bool:
    if len(a) < 3 or len(b) < 3:
        return False
    return any(a[i] is b[i] for i in range(1, len(a) - 1))


def prune_paths(grid, start_points, matching, rng) -> bool:
    for group in matching:
        rng.shuffle(group)
        if prune_all_but_last(grid, start_points, group) != 0:
            return True
        if any(break_a_link(segment) for segment in group):
            return True
    return False


def prune_all_but_last(grid, start_points, matches) -> int:
    pruned = 0
    for segment in matches:
        if pruned == len(matches) - 1:
            return pruned
        if prune_segment(grid, start_points, segment):
            pruned += 1
    return pruned


def in_grid(grid, p : MapPoint) -> bool:
    return p.type in (PointType.ANCIENT, PointType.BOSS) or (0 <= p.col < len(grid) and 0 <= p.row < len(grid[0]) and grid[p.col][p.row] is not None)


def removed(grid, p : MapPoint) -> bool:
    return grid[p.col][p.row] is None


def prune_segment(grid, start_points, segment : list[MapPoint]) -> bool:
    result = False
    for i in range(len(segment) - 1):
        p = segment[i]
        if not in_grid(grid, p):
            return True
        if len(p.children) > 1 or len(p.parents) > 1 or any(len(n.children) == 1 and not removed(grid, n) for n in p.parents):
            continue
        if not any(len(n.children) > 1 and len(n.parents) == 1 for n in segment[i:]):
            if len(segment[-1].parents) == 1:
                return False
            if not any(len(c.parents) == 1 for c in p.children if c not in segment):
                remove_point(grid, start_points, p)
                result = True
    return result


def remove_point(grid, start_points, p : MapPoint):
    grid[p.col][p.row] = None
    while p in start_points:
        start_points.remove(p)
    for child in list(p.children):
        p.remove_child(child)
    for parent in list(p.parents):
        parent.remove_child(p)


def break_a_link(segment : list[MapPoint]) -> bool:
    result = False
    for i in range(len(segment) - 1):
        p = segment[i]
        if len(p.children) >= 2 and len(segment[i + 1].parents) != 1:
            p.remove_child(segment[i + 1])
            result = True
    return result
