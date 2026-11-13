"""Move tables of the Act 1 Underdocks enemies."""
from __future__ import annotations

from sts2_lite import rng
from sts2_lite.card import CardId
from sts2_lite.status import StatusId
from sts2_lite.enemy_moves.core import Branch, Move, MoveTable, deadly, tough, escape


# ---------------------------------------------------------------- Act 1: the Underdocks
def _ritual(amount : int):
    def effect(enemy, combat):
        enemy.apply_status(StatusId.RITUAL, amount)
        enemy.status[StatusId.RITUAL].records = [[1]]       # RitualPower.WasJustAppliedByEnemy
    return effect


def calcified_cultist(ascension : int) -> MoveTable:
    return {
        "INCANTATION": Move(frozenset({"buff"}), "DARK_STRIKE", effect=_ritual(2)),
        "DARK_STRIKE": Move(frozenset({"attack"}), "DARK_STRIKE", damage=deadly(ascension, 9, 11), hits=1),
    }


def damp_cultist(ascension : int) -> MoveTable:
    return {
        "INCANTATION": Move(frozenset({"buff"}), "DARK_STRIKE", effect=_ritual(deadly(ascension, 5, 6))),
        "DARK_STRIKE": Move(frozenset({"attack"}), "DARK_STRIKE", damage=deadly(ascension, 1, 3), hits=1),
    }


def corpse_slug(ascension : int) -> MoveTable:
    # the three moves go round in a fixed order; only where each slug starts differs (and Ravenous stuns it, see status.py)
    return {
        "WHIP_SLAP": Move(frozenset({"attack"}), "GLOMP", damage=3, hits=2),
        "GLOMP": Move(frozenset({"attack"}), "GOOP", damage=deadly(ascension, 8, 9), hits=1),
        "GOOP": Move(frozenset({"debuff"}), "WHIP_SLAP", player_status=((StatusId.FRAIL, 2),)),
    }


def sewer_clam(ascension : int) -> MoveTable:
    return {
        "JET": Move(frozenset({"attack"}), "PRESSURIZE", damage=deadly(ascension, 10, 11), hits=1),
        "PRESSURIZE": Move(frozenset({"buff"}), "JET", self_status=((StatusId.STRENGTH, 4),)),
    }


def sludge_spinner(ascension : int) -> MoveTable:
    follow = (Branch("OIL_SPRAY"), Branch("SLAM"), Branch("RAGE"))        # never the move just used
    return {
        "OIL_SPRAY": Move(frozenset({"attack", "debuff"}), "", damage=deadly(ascension, 8, 9), hits=1,
                          player_status=((StatusId.WEAK, 1),), branches=follow),
        "SLAM": Move(frozenset({"attack"}), "", damage=deadly(ascension, 11, 12), hits=1, branches=follow),
        "RAGE": Move(frozenset({"attack", "buff"}), "", damage=deadly(ascension, 6, 7), hits=1,
                     self_status=((StatusId.STRENGTH, 3),), branches=follow),
    }


def seapunk(ascension : int) -> MoveTable:
    return {
        "SEA_KICK": Move(frozenset({"attack"}), "SPINNING_KICK", damage=deadly(ascension, 11, 13), hits=1),
        "SPINNING_KICK": Move(frozenset({"attack"}), "BUBBLE_BURP", damage=2, hits=4),
        "BUBBLE_BURP": Move(frozenset({"buff", "defend"}), "SEA_KICK", block=tough(ascension, 7, 8),
                            self_status=((StatusId.STRENGTH, deadly(ascension, 1, 2)),)),
    }


def fossil_stalker(ascension : int) -> MoveTable:
    follow = (Branch("LATCH", max_streak=2), Branch("TACKLE", max_streak=2), Branch("LASH", max_streak=2))
    return {
        "TACKLE": Move(frozenset({"attack", "debuff"}), "", damage=deadly(ascension, 9, 11), hits=1,
                       player_status=((StatusId.FRAIL, 1),), branches=follow),
        "LATCH": Move(frozenset({"attack"}), "", damage=deadly(ascension, 12, 14), hits=1, branches=follow),
        "LASH": Move(frozenset({"attack"}), "", damage=deadly(ascension, 3, 4), hits=2, branches=follow),
    }


def toadpole(ascension : int) -> MoveTable:
    # the front one starts with SPIKEN, the other with WHIRL; both then go round in the same order
    return {
        "WHIRL": Move(frozenset({"attack"}), "SPIKEN", damage=deadly(ascension, 7, 8), hits=1),
        "SPIKEN": Move(frozenset({"buff"}), "SPIKE_SPIT", self_status=((StatusId.THORNS, 2),)),
        "SPIKE_SPIT": Move(frozenset({"attack"}), "WHIRL", damage=deadly(ascension, 3, 4), hits=3,
                           self_status=((StatusId.THORNS, -2),)),
    }


def haunted_ship(ascension : int) -> MoveTable:
    return {
        "HAUNT": Move(frozenset({"debuff", "statuscard"}), "SWIPE", player_status=((StatusId.WEAK, 3),),
                      cards=((CardId.DAZED, 5),)),
        "SWIPE": Move(frozenset({"attack"}), "STOMP", damage=deadly(ascension, 13, 14), hits=1),
        "STOMP": Move(frozenset({"attack"}), "SWIPE", damage=deadly(ascension, 4, 5), hits=3),
    }


def skulking_colony(ascension : int) -> MoveTable:
    # two identical Zooms, then Inertia and Piercing Stabs; Hardened Shell (20) comes with the monster
    return {
        "ZOOM": Move(frozenset({"attack"}), "ZOOM_2", damage=deadly(ascension, 14, 16), hits=1, round_mod=(4, 1)),
        "ZOOM_2": Move(frozenset({"attack"}), "INERTIA", damage=deadly(ascension, 14, 16), hits=1, round_mod=(4, 2)),
        "INERTIA": Move(frozenset({"attack", "buff"}), "PIERCING_STABS", damage=deadly(ascension, 9, 11), hits=1,
                        self_status=((StatusId.STRENGTH, deadly(ascension, 2, 4)),)),
        "PIERCING_STABS": Move(frozenset({"attack"}), "ZOOM", damage=deadly(ascension, 7, 8), hits=2),
    }


def _steal(enemy, combat):
    """ThieveryPower.Steal: gold off the player, up to the amount, remembered for the gremlin that carries it off."""
    thievery = enemy.status.get(StatusId.THIEVERY)
    player = combat.combat_state.player
    if thievery is None or player.gold <= 0:
        return
    taken = min(thievery.amount, player.gold)
    player.gold -= taken
    if not thievery.records:
        thievery.records = [[thievery.amount, 0]]
    thievery.records[0][1] += taken


def gremlin_merc(ascension : int) -> MoveTable:
    # its damage rises with Tough Enemies (the game's own choice), and Deadly Enemies changes nothing
    return {
        "GIMME": Move(frozenset({"attack"}), "DOUBLE_SMASH", damage=tough(ascension, 7, 8), hits=2, effect=_steal),
        "DOUBLE_SMASH": Move(frozenset({"attack", "debuff"}), "HEHE", damage=tough(ascension, 6, 7), hits=2,
                             player_status=((StatusId.WEAK, 2),), effect=_steal),
        "HEHE": Move(frozenset({"attack", "buff"}), "GIMME", damage=tough(ascension, 8, 9), hits=1,
                     self_status=((StatusId.STRENGTH, 2),), effect=_steal),
    }


def fat_gremlin(ascension : int) -> MoveTable:
    return {
        "SPAWNED": Move(frozenset({"stun"}), "FLEE"),
        "FLEE": Move(frozenset({"escape"}), "FLEE", effect=escape),
    }


def sneaky_gremlin(ascension : int) -> MoveTable:
    return {
        "SPAWNED": Move(frozenset({"stun"}), "TACKLE"),
        "TACKLE": Move(frozenset({"attack"}), "TACKLE", damage=deadly(ascension, 9, 10), hits=1),
    }


BOMB_SLOTS = 5


def _bloat(enemy, combat):
    """The Living Fog's Bloat: a Gas Bomb in the first free place (bomb1 to bomb5), left of the fog."""
    from sts2_lite.enemy import Enemy
    cs = combat.combat_state
    bombs = [e for e in cs.enemies if e.enemy_id.startswith("GAS_BOMB")]
    used = {b.slot for b in bombs}
    free = next((s for s in range(BOMB_SLOTS) if s not in used), None)
    if free is None:
        return
    combat.summon(Enemy.spawn("GAS_BOMB", free, cs.ascension), at=sum(1 for b in bombs if b.slot < free))


def living_fog(ascension : int) -> MoveTable:
    return {
        "ADVANCED_GAS": Move(frozenset({"attack", "carddebuff"}), "BLOAT", damage=deadly(ascension, 8, 9), hits=1,
                             player_status=((StatusId.SMOGGY, 1),)),
        "BLOAT": Move(frozenset({"attack", "summon"}), "SUPER_GAS_BLAST", damage=deadly(ascension, 5, 6), hits=1, effect=_bloat),
        "SUPER_GAS_BLAST": Move(frozenset({"attack"}), "BLOAT", damage=deadly(ascension, 8, 9), hits=1),
    }


def _explode(enemy, combat):
    enemy.current_hp = 0        # CreatureCmd.Kill after the blast


def gas_bomb(ascension : int) -> MoveTable:
    return {"EXPLODE": Move(frozenset({"deathblow"}), "EXPLODE", damage=deadly(ascension, 8, 9), hits=1, effect=_explode)}


RAT_BACKUP_LIMIT = 3
RAT_SLOTS = 5


def _rat_parts(rat) -> tuple[int, int, int]:
    """The rat's memory lives in its counter: moves made so far (up to 2), turns of Screech cooldown left (up to 3),
    and the backups called in this fight (shared by all rats)."""
    return rat.counter % 3, (rat.counter // 3) % 4, rat.counter // 12


def rat_counter(acts : int, cooldown : int, backups : int) -> int:
    return min(acts, 2) + 3 * cooldown + 12 * backups


def _rat_act(rat, screech : bool = False, acted : bool = True):
    acts, cooldown, backups = _rat_parts(rat)
    rat.counter = rat_counter(acts + (1 if acted else 0), 3 if screech else max(0, cooldown - 1), backups)


def _can_call(rat, combat) -> bool:
    acts, _, backups = _rat_parts(rat)
    if acts < 2 or backups >= RAT_BACKUP_LIMIT:
        return False
    if combat is None:
        return True
    rats = [e for e in combat.combat_state.enemies if e.enemy_id.startswith("TWO_TAILED_RAT")]
    return len(rats) < RAT_SLOTS and not any(r is not rat and r.move_id == "CALL_FOR_BACKUP" for r in rats)


def _rat_next(rat, combat) -> str:
    _, cooldown, _ = _rat_parts(rat)
    can = _can_call(rat, combat)
    weight = 1 / 12 if can else 1.0
    options = [(m, weight) for m, ok in (("SCRATCH", rat.move_id != "SCRATCH"), ("DISEASE_BITE", rat.move_id != "DISEASE_BITE"),
                                         ("SCREECH", cooldown == 0)) if ok]
    if can and "CALL_FOR_BACKUP" not in rat.used_moves:
        options.append(("CALL_FOR_BACKUP", 0.75))
    return rng.choices([m for m, _ in options], weights=[w for _, w in options])[0]


def _call_for_backup(rat, combat):
    from sts2_lite.enemy import Enemy
    cs = combat.combat_state
    rats = [e for e in cs.enemies if e.enemy_id.startswith("TWO_TAILED_RAT")]
    if len(rats) < RAT_SLOTS:
        new = Enemy.spawn("TWO_TAILED_RAT", max([r.slot for r in rats], default=-1) + 1, cs.ascension)
        first = rng.choice(["SCRATCH", "DISEASE_BITE", "SCREECH"])      # a new rat rolls its first move like any other turn
        new.move_id = first
        new.attack_damage = new._move_damage(new.moves[first])
        new.num_attacks = new._move_hits(new.moves[first])
        combat.summon(new, at=0)
        rats.append(new)
    backups = max(_rat_parts(r)[2] for r in rats) + 1
    for r in rats:
        acts, cooldown, _ = _rat_parts(r)
        r.counter = rat_counter(acts, cooldown, backups)
    _rat_act(rat, acted=False)


def two_tailed_rat(ascension : int) -> MoveTable:
    return {
        "SCRATCH": Move(frozenset({"attack"}), "", damage=deadly(ascension, 8, 9), hits=1, choose=_rat_next,
                        effect=lambda rat, combat: _rat_act(rat)),
        "DISEASE_BITE": Move(frozenset({"attack"}), "", damage=deadly(ascension, 6, 7), hits=1, choose=_rat_next,
                             effect=lambda rat, combat: _rat_act(rat)),
        "SCREECH": Move(frozenset({"debuff"}), "", player_status=((StatusId.FRAIL, 1),), choose=_rat_next,
                        effect=lambda rat, combat: _rat_act(rat, screech=True)),
        "CALL_FOR_BACKUP": Move(frozenset({"summon"}), "", choose=_rat_next, effect=_call_for_backup),
    }


def terror_eel(ascension : int) -> MoveTable:
    # Shriek (70, or 75 on Tough Enemies) stuns it into TERROR the first time a hit leaves it at or below that
    return {
        "CRASH": Move(frozenset({"attack"}), "THRASH", damage=deadly(ascension, 16, 18), hits=1),
        "THRASH": Move(frozenset({"attack", "buff"}), "CRASH", damage=deadly(ascension, 3, 4), hits=3,
                       self_status=((StatusId.VIGOR, 6),)),
        "TERROR": Move(frozenset({"debuff"}), "CRASH", player_status=((StatusId.VULNERABLE, 99),)),
    }


def phantasmal_gardener(ascension : int) -> MoveTable:
    # four gardeners start on different moves (by place) and then go round in the same order; Skittish comes with them
    return {
        "BITE": Move(frozenset({"attack"}), "LASH", damage=5, hits=1),
        "LASH": Move(frozenset({"attack"}), "FLAIL", damage=7, hits=1),
        "FLAIL": Move(frozenset({"attack"}), "ENLARGE", damage=1, hits=3),
        "ENLARGE": Move(frozenset({"buff"}), "BITE", self_status=((StatusId.STRENGTH, deadly(ascension, 2, 3)),)),
    }


def lagavulin_matriarch(ascension : int) -> MoveTable:
    # asleep (Plating 12, Asleep 3) until the sleep runs out or a hit gets through; then it goes round the four attacks
    # the next move is picked before this turn's sleep counts down, so it stops on the turn after the last Asleep tick (captures: 3 SLEEP turns)
    wake = lambda e, c: "SLEEP" if StatusId.ASLEEP in e.status and e.status[StatusId.ASLEEP].amount > 1 else "SLASH"
    return {
        "SLEEP": Move(frozenset({"sleep"}), "", choose=wake),
        "SLASH": Move(frozenset({"attack"}), "DISEMBOWEL", damage=deadly(ascension, 19, 21), hits=1),
        "DISEMBOWEL": Move(frozenset({"attack"}), "SLASH2", damage=deadly(ascension, 9, 10), hits=2),
        "SLASH2": Move(frozenset({"attack", "defend"}), "SOUL_SIPHON", damage=deadly(ascension, 12, 14), hits=1,
                       block=tough(ascension, 12, 14)),
        "SOUL_SIPHON": Move(frozenset({"debuff", "buff"}), "SLASH", player_status=((StatusId.STRENGTH, -2), (StatusId.DEXTERITY, -2)),
                            self_status=((StatusId.STRENGTH, 2),)),
    }


def soul_fysh(ascension : int) -> MoveTable:
    return {
        "BECKON": Move(frozenset({"statuscard"}), "DE_GAS", draw_cards=((CardId.BECKON, 1),), cards=((CardId.BECKON, 1),)),
        "DE_GAS": Move(frozenset({"attack"}), "GAZE", damage=deadly(ascension, 16, 17), hits=1),
        "GAZE": Move(frozenset({"attack", "statuscard"}), "FADE", damage=deadly(ascension, 7, 8), hits=1, cards=((CardId.BECKON, 1),)),
        "FADE": Move(frozenset({"buff"}), "SCREAM", self_status=((StatusId.INTANGIBLE, 2),)),
        "SCREAM": Move(frozenset({"attack", "debuff"}), "BECKON", damage=deadly(ascension, 13, 15), hits=1,
                       player_status=((StatusId.VULNERABLE, 3),)),
    }


STEAM_PER_MOVE = 3
PRESSURE_GUN_STEP = 5


def _gun_fired(giant, combat):
    giant.counter += 1


def _about_to_blow(giant, combat):
    """AboutToBlowMove: the steam it built is what the eruption will do, and the Steam Eruption power is gone."""
    steam = giant.status.pop(StatusId.STEAM_ERUPTION, None)
    giant.counter = steam.amount if steam is not None else 0


def _blow(giant, combat):
    giant.current_hp = 0


def waterfall_giant(ascension : int) -> MoveTable:
    steam = ((StatusId.STEAM_ERUPTION, STEAM_PER_MOVE),)
    return {
        "PRESSURIZE": Move(frozenset({"buff"}), "STOMP", self_status=((StatusId.STEAM_ERUPTION, deadly(ascension, 15, 20)),)),
        "STOMP": Move(frozenset({"attack", "debuff", "buff"}), "RAM", damage=deadly(ascension, 15, 16), hits=1,
                      player_status=((StatusId.WEAK, 1),), self_status=steam),
        "RAM": Move(frozenset({"attack", "buff"}), "SIPHON", damage=deadly(ascension, 10, 11), hits=1, self_status=steam),
        "SIPHON": Move(frozenset({"heal", "buff"}), "PRESSURE_GUN", heal=tough(ascension, 10, 15), self_status=steam),
        "PRESSURE_GUN": Move(frozenset({"attack", "buff"}), "PRESSURE_UP", damage=deadly(ascension, 20, 23), hits=1, self_status=steam,
                             extra_damage=lambda e: PRESSURE_GUN_STEP * e.counter, effect=_gun_fired),
        "PRESSURE_UP": Move(frozenset({"attack", "buff"}), "STOMP", damage=deadly(ascension, 13, 14), hits=1, self_status=steam),
        "ABOUT_TO_BLOW": Move(frozenset({"stun"}), "EXPLODE", effect=_about_to_blow),
        "EXPLODE": Move(frozenset({"deathblow"}), "EXPLODE", damage=0, hits=1, extra_damage=lambda e: e.counter, effect=_blow),
    }


