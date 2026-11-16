"""Map points and the act map's shape (MapPoint, ActMap)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class PointType(Enum):
    UNASSIGNED = auto()
    MONSTER = auto()
    ELITE = auto()
    REST_SITE = auto()
    SHOP = auto()
    TREASURE = auto()
    UNKNOWN = auto()
    BOSS = auto()
    ANCIENT = auto()

    @property
    def bridge_name(self) -> str:
        """The name the bridge reports for the point (`agents.route.node_kind` reads it)."""
        return {"REST_SITE": "RestSite"}.get(self.name, self.name.title())


@dataclass(eq=False)
class MapPoint:
    col : int
    row : int
    type : PointType = PointType.UNASSIGNED
    parents : list["MapPoint"] = field(default_factory=list)
    children : list["MapPoint"] = field(default_factory=list)
    can_be_modified : bool = True

    @property
    def coord(self) -> tuple[int, int]:
        return self.col, self.row

    def add_child(self, child : "MapPoint"):
        """MapPoint.AddChildPoint: a path that reaches a point another path already reaches joins it (no duplicate edge). Kept in the order they were added."""
        if child not in self.children:
            self.children.append(child)
        if self not in child.parents:
            child.parents.append(self)

    def remove_child(self, child : "MapPoint"):
        if child in self.children:
            self.children.remove(child)
        if self in child.parents:
            child.parents.remove(self)

    def __repr__(self):
        return f"MapPoint({self.col},{self.row},{self.type.name})"


@dataclass
class ActMap:
    """The grid of an act (columns 0..6, rows 1..rooms), the start (the ancient) below it and the boss above it."""
    grid : list[list[MapPoint | None]]        # grid[col][row]
    start : MapPoint
    boss : MapPoint
    second_boss : MapPoint | None = None
    rows : int = 0                  # map length: rooms + 1; the boss is on this row
    start_points : list[MapPoint] = field(default_factory=list)

    def points(self) -> list[MapPoint]:
        """Every point of the grid, row by row, left to right (the start and the bosses are not in it)."""
        return [p for row in range(self.rows) for col in range(len(self.grid)) if (p := self.grid[col][row]) is not None]

    def at(self, col : int, row : int) -> MapPoint | None:
        if row == self.rows:
            return self.boss
        if self.second_boss is not None and row == self.rows + 1:
            return self.second_boss
        if row == 0:
            return self.start
        return self.grid[col][row] if 0 <= col < len(self.grid) and 0 <= row < self.rows else None

    def to_bridge(self, visited : list[tuple[int, int]] = (), current : tuple[int, int] | None = None) -> dict:
        """The map in the shape the agent reads: `nodes` with their children, the `visited` path and `current_position`."""
        every = [self.start] + self.points() + [self.boss] + ([self.second_boss] if self.second_boss else [])
        nodes = [{"col": p.col, "row": p.row, "type": p.type.bridge_name, "children": [list(c.coord) for c in p.children]} for p in every]
        by_coord = {(n["col"], n["row"]): n for n in nodes}
        return {"nodes": nodes, "visited": [{"col": c, "row": r, "type": by_coord[(c, r)]["type"]} for c, r in visited],
                "current_position": {"col": current[0], "row": current[1]} if current else None}
