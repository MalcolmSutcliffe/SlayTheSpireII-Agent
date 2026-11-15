"""The fights a deck is tried on: the engine's own encounter pools (sts2_lite.encounters.ACTS).

An act lists the encounters it can deal: its weak ones (the act's first combats: 3 in act 1, 2 after), its regular ones, its elites and its
bosses. Every encounter of every act is a template here, tagged "weak", "normal", "elite" or "boss". A template is only the encounter: the
monsters and their hit points are rolled when a fight is drawn, with the seed the draw stamped on it (`instance`), so two decks tried on the same
drawn fight meet the same monsters.

A template with a captured `state` (agents/verify_opening.py: the live game's own fight) is built from that state instead of the engine."""
from __future__ import annotations
import random
from dataclasses import dataclass, replace

from sts2_lite.card.constants import CARD_ENERGY_COST_AND_TARGET
from sts2_lite.encounters import ACTS

# the engine's act ids -> the act's number (act 1 is Overgrowth or Underdocks, and the act's boss tells which)
ACT_NUMBER = {"OVERGROWTH": 1, "UNDERDOCKS": 1, "HIVE": 2, "GLORY": 3}
WEAK_FIGHTS = {ACT_NUMBER[act.id]: act.weak_rooms for act in ACTS.values()}        # Act.NumberOfWeakEncounters: the first combats of an act come from the weak encounters
SEED_RANGE = 1 << 31


@dataclass(frozen=True)
class FightTemplate:
    name : str          # "SLIMES_WEAK" (the encounter id); "live" for a live game state
    act : int
    kind : str          # "weak" | "normal" | "elite" | "boss"
    state : dict | None = None      # a captured combat_play state, round 1: used instead of the engine when given
    boss : str | None = None        # a boss fight: its encounter id (VANTOM_BOSS, ...)
    variant : str | None = None     # act 1 only: "OVERGROWTH" or "UNDERDOCKS" (None: not known)
    encounter : str | None = None   # the engine's encounter id; None for a captured state
    ascension : int = 0             # stamped on a drawn fight (`instance`)
    seed : int = 0                  # rolls the monsters' hit points and openings of a drawn fight

    @property
    def room_type(self) -> str:
        return {"weak": "monster", "normal": "monster"}.get(self.kind, self.kind)


def instance(template : FightTemplate, ascension : int, r : random.Random) -> FightTemplate:
    """One drawn fight of the template: the run's ascension and a seed from `r` that rolls its monsters."""
    return replace(template, ascension=ascension, seed=r.randrange(SEED_RANGE))


def load_pool() -> list[FightTemplate]:
    """Every encounter of every act the engine knows."""
    pool = []
    for act in ACTS.values():
        number = ACT_NUMBER[act.id]
        variant = act.id if number == 1 else None
        for kind, encounters in (("weak", act.weak), ("normal", act.regular), ("elite", act.elites), ("boss", act.bosses)):
            for encounter in encounters:
                pool.append(FightTemplate(encounter.id, number, kind, boss=encounter.id if kind == "boss" else None, variant=variant, encounter=encounter.id))
    return pool


def target_types(pool : list[FightTemplate] | None = None) -> dict[str, str]:
    """card id -> target_type, from the engine's card table (the deck lists the bridge gives carry none). `pool` is not needed any more."""
    return {card.name: target.name for card, (cost, target) in CARD_ENERGY_COST_AND_TARGET.items() if target is not None}
