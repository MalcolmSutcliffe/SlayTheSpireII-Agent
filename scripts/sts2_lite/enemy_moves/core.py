"""The pieces every enemy's move table is built from: `Move`, `Branch` and the helpers that scale a number by ascension."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sts2_lite.card import CardId
from sts2_lite.status import StatusId

TOUGH_ASCENSION = 8      # more hit points and block
DEADLY_ASCENSION = 9     # more damage and strength


@dataclass(frozen=True)
class Branch:
    """A random follow-up option; max_streak caps how many times in a row this move may be used."""
    move: str
    max_streak: int = 1
    once: bool = False       # may be used only once per fight
    weight: int = 1          # relative chance among the allowed options


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
    cards: tuple[tuple[CardId, int], ...] = ()  # cards added to the player's discard pile
    next_by_slot: tuple[str, ...] = ()         # next move chosen by the enemy's slot, used instead of next_move
    branches: tuple[Branch, ...] = ()          # random follow-up; used instead of next_move when set
    summon: tuple[str, int] | None = None      # (monster, slot) added to the fight when the move is performed
    from_bridge: bool = True                   # False: looks like another move, so never picked when reading the bridge
    hand_cards: tuple[tuple[CardId, int], ...] = ()     # cards added to the player's hand (the discard pile when the hand is full)
    draw_cards: tuple[tuple[CardId, int], ...] = ()     # cards shuffled into the player's draw pile
    summons: tuple[tuple[str, int], ...] = ()  # (monster, slot) pairs added when the move is performed, like `summon`
    team_status: tuple[tuple[StatusId, int], ...] = ()  # applied to every living enemy, the mover included
    heal: int = 0                              # hit points the mover recovers
    choose: Callable | None = None             # (enemy, combat) -> next move key; used instead of next_move and branches
    effect: Callable | None = None             # (enemy, combat) run when the move is performed, for anything above
    extra_hits: Callable | None = None         # (enemy) -> hits added to `hits` (the Test Subject's claws grow)
    extra_damage: Callable | None = None       # (enemy) -> damage added to `damage` (the Waterfall Giant's Pressure Gun grows)
    dex_damage: bool = False                   # the move's damage grows by the mover's Dexterity (The Forgotten's Dread)


MoveTable = dict[str, Move]


def deadly(ascension : int, base : int, deadly : int) -> int:
    return deadly if ascension >= DEADLY_ASCENSION else base


def tough(ascension : int, base : int, tough : int) -> int:
    return tough if ascension >= TOUGH_ASCENSION else base


def escape(enemy, combat):
    combat.combat_state.enemies.remove(enemy)
