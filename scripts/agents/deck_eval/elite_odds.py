"""Which elite the next one can be. The game deals an act's elites from a grab bag that refills when it is empty (encounters.acts.generate_rooms):
each round of as many fights as the act has elites holds every elite once, and an elite never shares a tag with the one before it. So once two of
an act's three elites were fought, the third is known; after the third, the bag is full again and any elite that does not repeat the last one can come.

`identify` tells which elite a fight was from its monsters, so the agent can keep the list of the elites it met."""
from __future__ import annotations
import random

from sts2_lite.encounters import ACTS, ENCOUNTERS

ACT_IDS = {1: None, 2: "HIVE", 3: "GLORY"}      # act 1 is Overgrowth or Underdocks: the boss (or the map) tells which


def act_id(act : int, variant : str | None = None) -> str | None:
    return variant if act == 1 else ACT_IDS.get(act)


def _lead(encounter) -> str:
    """The monster that stands for the encounter: the first one it spawns."""
    return encounter.monsters(random.Random(0))[0].monster


def identify(act : str | None, enemy_ids) -> str | None:
    """The elite encounter of the act whose lead monster is among the fight's enemies (`enemy_ids` like "ENTOMANCER_0"); None when none is."""
    if act not in ACTS:
        return None
    names = {str(e).rpartition("_")[0] for e in enemy_ids}
    return next((e.id for e in ACTS[act].elites if _lead(e) in names), None)


def elites_left(act : str | None, fought : list) -> tuple[str, ...] | None:
    """The elite encounters the next elite of the act can be, given the ones met so far in order (None for one that was not recognized).
    None when the act is not known (act 1 before the map showed its boss)."""
    if act not in ACTS:
        return None
    elites = ACTS[act].elites
    size = len(elites)
    this_round = [e for e in fought[(len(fought) // size) * size:] if e is not None]
    left = [e for e in elites if e.id not in this_round]
    last = ENCOUNTERS.get(fought[-1]) if fought and fought[-1] else None
    apart = [e for e in left if e is not last and not e.shares_tags_with(last)]
    return tuple(e.id for e in (apart or left))


def elite_sequence(act : str, fought : list, rng, slots : int | None = None) -> list:
    """The act's elite encounters in the order they will be met (the sequence `generate_rooms` makes), continuing from the ones already fought:
    the first `len(fought)` entries are those (an elite that was not recognized is a random one of the act), the rest is drawn from the bag the game has left."""
    from sts2_lite.encounters.acts import ELITE_SLOTS, GrabBag, _add_without_repeating_tags
    elites = ACTS[act].elites
    chosen = [ENCOUNTERS[e] if e in ENCOUNTERS else rng.choice(elites) for e in fought]
    bag = GrabBag()
    size = len(elites)
    bag.refill([e for e in elites if e not in chosen[(len(chosen) // size) * size:]])
    while len(chosen) < (slots or max(ELITE_SLOTS, len(fought) + size)):
        if not bag:
            bag.refill(elites)
        _add_without_repeating_tags(chosen, bag, rng)
    return chosen
