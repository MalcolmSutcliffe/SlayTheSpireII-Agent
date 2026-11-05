"""Enemy move tables. A move table maps move id -> Move; each move names its follow-up."""
from __future__ import annotations

from dataclasses import dataclass

from sts2_lite.status import StatusId

DEADLY_ASCENSION = 9


@dataclass(frozen=True)
class Move:
    intents: frozenset[str]                    # lowercase bridge intent types
    next_move: str
    damage: int = 0
    hits: int = 0
    block: int = 0
    self_status: tuple[tuple[StatusId, int], ...] = ()
    player_status: tuple[tuple[StatusId, int], ...] = ()
    round_mod: tuple[int, int] | None = None   # (period, remainder): tells apart moves with the same intent


MoveTable = dict[str, Move]


def _deadly(ascension : int, base : int, deadly : int) -> int:
    return deadly if ascension >= DEADLY_ASCENSION else base


def nibbit(ascension : int) -> MoveTable:
    return {
        "BUTT": Move(frozenset({"attack"}), "SLICE",
                     damage=_deadly(ascension, 12, 13), hits=1),
        "SLICE": Move(frozenset({"attack", "defend"}), "HISS",
                      damage=6, hits=1, block=5),
        "HISS": Move(frozenset({"buff"}), "BUTT",
                     self_status=((StatusId.STRENGTH, 2),)),
    }


def shrinker_beetle(ascension : int) -> MoveTable:
    return {
        "SHRINK": Move(frozenset({"debuffstrong"}), "CHOMP",
                       player_status=((StatusId.SHRINK, -1),)),
        "CHOMP": Move(frozenset({"attack"}), "STOMP",
                      damage=_deadly(ascension, 7, 8), hits=1),
        "STOMP": Move(frozenset({"attack"}), "CHOMP",
                      damage=_deadly(ascension, 13, 14), hits=1),
    }


def fuzzy_wurm_crawler(ascension : int) -> MoveTable:
    # goop, inhale, goop, goop, inhale, ...; both goops look the same, so rounds tell them apart
    return {
        "FIRST_GOOP": Move(frozenset({"attack"}), "INHALE",
                           damage=_deadly(ascension, 4, 6), hits=1, round_mod=(3, 1)),
        "INHALE": Move(frozenset({"buff"}), "GOOP",
                       self_status=((StatusId.STRENGTH, 7),)),
        "GOOP": Move(frozenset({"attack"}), "FIRST_GOOP",
                     damage=_deadly(ascension, 4, 6), hits=1, round_mod=(3, 0)),
    }


MOVE_TABLES = {
    "NIBBIT": nibbit,
    "SHRINKER_BEETLE": shrinker_beetle,
    "FUZZY_WURM_CRAWLER": fuzzy_wurm_crawler,
}
