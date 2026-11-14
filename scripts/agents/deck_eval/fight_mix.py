"""Which fights lie ahead: how many of each kind, from the route the pathing agent planned, and how to draw a sample of them."""
from __future__ import annotations
import random
from dataclasses import dataclass

from agents.deck_eval.boss_spawner import BOSS_ACTS, bosses_of_act, normalize_boss_id
from agents.deck_eval.fight_pool import FightTemplate, WEAK_FIGHTS

NEW_ACT_NORMALS = 3         # what an act is expected to hold, for the fights ahead when no route is known (a boss reward starts a new act)
NEW_ACT_ELITES = 2
FIGHTS_IN_AN_ACT = 8        # boss emphasis reaches its peak when no fight is left before the boss
BOSS_BOOST = 2.0            # at the end of the act the boss counts 1 + BOSS_BOOST times a single fight

FALLBACK = {"weak": ("normal",), "normal": ("weak",), "elite": ("normal", "weak"), "boss": ("elite", "normal", "weak")}


@dataclass(frozen=True)
class FightMix:
    act : int
    weak : float
    normal : float
    elite : float
    boss : float        # weight of the act's boss among the single fights above
    variant : str | None = None     # act 1: "OVERGROWTH" or "UNDERDOCKS", once the map showed the boss
    boss_id : str | None = None     # the boss the map showed (None: any boss of the act)

    def weights(self) -> dict[str, float]:
        return {"weak": self.weak, "normal": self.normal, "elite": self.elite, "boss": self.boss}


def new_act_mix(act : int) -> FightMix:
    return _with_boss(act, WEAK_FIGHTS.get(act, 2), NEW_ACT_NORMALS, NEW_ACT_ELITES)


def _with_boss(act : int, weak : float, normal : float, elite : float, route=None) -> FightMix:
    progress = min(1.0, max(0.0, 1 - (weak + normal + elite) / FIGHTS_IN_AN_ACT))
    boss = normalize_boss_id(getattr(route, "boss", None))
    variant = BOSS_ACTS[boss][1] if boss in BOSS_ACTS and act == 1 else getattr(route, "act_model", None) if act == 1 else None
    return FightMix(act, weak, normal, elite, 1 + BOSS_BOOST * progress, variant, boss)


def mix_ahead(act : int, route, max_act : int = 3) -> FightMix:
    """The fights after the room the agent is in now. `route` is the pathing agent's PlannedRoute (None: unknown).
    A boss reward comes from the last node of the route: the fights ahead are those of the next act."""
    if route is None or not route.kinds:
        return new_act_mix(act)
    if route.kinds[0] == "boss":
        return new_act_mix(min(max_act, act + 1))
    combats = route.combats_before + (route.kinds[0] == "combat")      # combats of the act fought including the room in progress
    weak_left = max(0, WEAK_FIGHTS.get(act, 2) - combats)
    ahead = route.kinds[1:]
    n_combat, n_elite = sum(k == "combat" for k in ahead), sum(k == "elite" for k in ahead)
    weak = min(weak_left, n_combat)
    return _with_boss(act, weak, n_combat - weak, n_elite, route)


def pick_fights(pool : list[FightTemplate], mix : FightMix, n : int, seed : int, ascension : int = 0) -> list[FightTemplate]:
    """`n` fights drawn from the pool of the mix's act. Same `seed` -> same fights, so every candidate deck faces the same ones.
    Bosses without a capture are spawned (boss_spawner); in act 1 only the fights of the act's version (Overgrowth / Underdocks) are used."""
    r = random.Random(seed)
    in_act = [t for t in pool if t.act == mix.act] or pool
    if mix.variant:
        in_act = [t for t in in_act if t.variant in (mix.variant, None)] or in_act
    by_kind = {k: [t for t in in_act if t.kind == k] for k in ("weak", "normal", "elite", "boss")}
    by_kind["boss"] = bosses_of_act(pool, mix.act, ascension, mix.boss_id, mix.variant) or by_kind["boss"]

    def templates(kind):
        for k in (kind, *FALLBACK[kind]):
            if by_kind[k]:
                return by_kind[k]
        return in_act
    kinds = [k for k, w in mix.weights().items() if w > 0] or ["normal"]
    weights = [mix.weights().get(k, 1) for k in kinds]
    return [r.choice(templates(r.choices(kinds, weights)[0])) for _ in range(n)]
