"""The Defect's orbs (Models.Orbs, OrbQueue, OrbCmd): slots that hold Lightning, Frost, Dark, Plasma and Glass orbs.

An orb has a Passive that fires at the end of the player's turn (Plasma: at the start of the next one) and an Evoke that fires when it is pushed out by a new
orb, or by a card. Focus (and Infused Core, for Lightning) changes the values; Gold Plated Cables makes the first orb's Passive fire twice. Orb damage is
Unpowered (no Strength, no Vulnerable) and Orb Block is too (no Dexterity, no Frail). The queue is `Player.orbs` (the first orb is the next one evoked),
`Player.orb_slots` its capacity."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.status import StatusId

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.player import Player

LIGHTNING, FROST, DARK, PLASMA, GLASS = "LIGHTNING", "FROST", "DARK", "PLASMA", "GLASS"
RANDOM_ORBS = (LIGHTNING, FROST, DARK, PLASMA, GLASS)       # OrbModel._validOrbs, in the game's order
MAX_SLOTS = 10
DEFECT_SLOTS = 3

LIGHTNING_PASSIVE, LIGHTNING_EVOKE = 3, 8
FROST_PASSIVE, FROST_EVOKE = 2, 5
DARK_PASSIVE, DARK_EVOKE = 6, 6
PLASMA_PASSIVE, PLASMA_EVOKE = 1, 2
GLASS_PASSIVE = 4
INFUSED_CORE_BONUS = 1
METRONOME_ORBS, METRONOME_DAMAGE = 7, 30


class Orb:
    """One orb. `passive` is what its Passive is worth before Focus (Glass loses 1 each time it fires); `evoke` is what a Dark orb has stored up."""
    __slots__ = ("kind", "passive", "evoke")

    def __init__(self, kind : str, passive : int | None = None, evoke : int | None = None):
        self.kind = kind
        self.passive = passive if passive is not None else {LIGHTNING: LIGHTNING_PASSIVE, FROST: FROST_PASSIVE, DARK: DARK_PASSIVE, PLASMA: PLASMA_PASSIVE, GLASS: GLASS_PASSIVE}[kind]
        self.evoke = evoke if evoke is not None else DARK_EVOKE

    def copy(self) -> Orb:
        return Orb(self.kind, self.passive, self.evoke)

    def key(self) -> tuple:
        return (self.kind, self.passive, self.evoke if self.kind == DARK else 0)

    def __repr__(self) -> str:
        return f"Orb({self.kind}, {self.passive}, {self.evoke})"


def orb_kind_of(game_id : str | None) -> str | None:
    """The kind of the bridge's orb id ("LIGHTNING_ORB")."""
    kind = (game_id or "").removesuffix("_ORB")
    return kind if kind in RANDOM_ORBS else None


# ------------------------------------------------------------------ values

def focus(player : Player) -> int:
    return player.status_amount(StatusId.FOCUS) if player.status else 0

def _modified(player : Player, base : int, lightning : bool = False) -> int:
    """OrbModel.ModifyOrbValue: Focus (never below 0), and Infused Core's extra Lightning damage."""
    value = max(base + focus(player), 0)
    if lightning and player.relics:
        from sts2_lite.relic import RelicId
        if RelicId.INFUSED_CORE in player.relics:
            value += INFUSED_CORE_BONUS
    return value

def passive_value(player : Player, orb : Orb) -> int:
    kind = orb.kind
    if kind == PLASMA:
        return PLASMA_PASSIVE
    return _modified(player, orb.passive, kind == LIGHTNING)

def evoke_value(player : Player, orb : Orb) -> int:
    kind = orb.kind
    if kind == LIGHTNING:
        return _modified(player, LIGHTNING_EVOKE, True)
    if kind == FROST:
        return _modified(player, FROST_EVOKE)
    if kind == DARK:
        return orb.evoke            # what its Passives stored; Focus does not change it
    if kind == PLASMA:
        return PLASMA_EVOKE
    return passive_value(player, orb) * 2       # Glass

def orb_from_state(player : Player, raw : dict) -> Orb | None:
    """An orb the bridge reports (`passive_val` and `evoke_val` have Focus in them)."""
    kind = orb_kind_of(raw.get("id"))
    if kind is None:
        return None
    shown = int(raw.get("passive_val") or 0)
    if kind in (PLASMA,):
        return Orb(kind)
    base = shown - focus(player)
    if kind == LIGHTNING and player.relics:
        from sts2_lite.relic import RelicId
        if RelicId.INFUSED_CORE in player.relics:
            base -= INFUSED_CORE_BONUS
    base = max(base, 0)
    orb = Orb(kind, base)
    if kind == DARK:
        orb.evoke = int(raw.get("evoke_val") or DARK_EVOKE)
    return orb


# ------------------------------------------------------------------ queue

def add_slots(player : Player, amount : int):
    """OrbCmd.AddSlots."""
    player.orb_slots += max(0, min(MAX_SLOTS - player.orb_slots, amount))

def remove_slots(player : Player, amount : int):
    """OrbCmd.RemoveSlots / OrbQueue.RemoveCapacity: the orbs at the back go with their slots."""
    player.orb_slots = max(0, player.orb_slots - min(player.orb_slots, amount))
    del player.orbs[player.orb_slots:]

def distinct_kinds(player : Player) -> int:
    return len({o.kind for o in player.orbs})

def living_enemies(combat : CombatSimulator) -> list:
    return [e for e in combat.combat_state.enemies if e.current_hp > 0]

def channel(combat : CombatSimulator, kind : str, count : int = 1):
    """OrbCmd.Channel: a full queue evokes its first orb to make room; no slots at all means the orb is lost (a character without orb slots gets one)."""
    player = combat.combat_state.player
    for _ in range(count):
        if combat.is_over:
            return
        if player.orb_slots == 0 and player.character != "DEFECT":
            add_slots(player, 1)        # Character.BaseOrbSlotCount == 0 and no capacity yet
        if len(player.orbs) >= player.orb_slots and player.orbs:
            evoke_next(combat)
        if player.orb_slots == 0 or len(player.orbs) >= player.orb_slots:
            continue
        player.orbs.append(Orb(kind))
        _after_channel(combat, kind)

def channel_random(combat : CombatSimulator, count : int = 1):
    for _ in range(count):
        channel(combat, rng.choice(RANDOM_ORBS))

def _after_channel(combat : CombatSimulator, kind : str):
    """Hook.AfterOrbChanneled: the count Voltaic reads, and Metronome."""
    player = combat.combat_state.player
    if kind == LIGHTNING:
        player.lightning_channeled += 1
    if player.relics:
        from sts2_lite.relic import RelicId
        metronome = player.relics.get(RelicId.METRONOME)
        if metronome is not None:
            metronome.counter = (metronome.counter or 0) + 1
            if metronome.counter == METRONOME_ORBS:
                for enemy in living_enemies(combat):
                    enemy.apply_damage(METRONOME_DAMAGE, player)

def evoke_next(combat : CombatSimulator, dequeue : bool = True):
    """OrbCmd.EvokeNext."""
    player = combat.combat_state.player
    if player.orbs:
        _evoke(combat, player.orbs[0], dequeue)

def evoke_last(combat : CombatSimulator, dequeue : bool = True):
    player = combat.combat_state.player
    if player.orbs:
        _evoke(combat, player.orbs[-1], dequeue)

def _evoke(combat : CombatSimulator, orb : Orb, dequeue : bool):
    player = combat.combat_state.player
    if dequeue:
        player.orbs.remove(orb)
    targets = _evoke_effect(combat, orb)
    thunder = player.status.get(StatusId.THUNDER)       # ThunderPower.AfterOrbEvoked
    if thunder is not None and orb.kind == LIGHTNING:
        for target in targets:
            if target.current_hp > 0:
                target.apply_damage(thunder.amount, player)

def _evoke_effect(combat : CombatSimulator, orb : Orb) -> list:
    """Orb.Evoke: the creatures it hit (only enemies matter to Thunder)."""
    player = combat.combat_state.player
    value = evoke_value(player, orb)
    kind = orb.kind
    if kind == FROST:
        combat.gain_block(player, value)
        return []
    if kind == PLASMA:
        combat.gain_energy(value)
        return []
    living = living_enemies(combat)
    if not living or value <= 0 and kind == GLASS:
        return []
    if kind == LIGHTNING:
        target = rng.pick_target(living)
        target.apply_damage(value, player)
        return [target]
    if kind == DARK:
        target = min(living, key=lambda e: e.current_hp)
        target.apply_damage(value, player)
        return [target]
    for enemy in living:        # Glass: every enemy
        enemy.apply_damage(value, player)
    return living


def passive(combat : CombatSimulator, orb : Orb, target=None, counted : bool = False):
    """OrbCmd.Passive: one trigger (`counted`: the number of triggers goes through the hooks, as at a turn's end, which is how Gold Plated Cables doubles it)."""
    player = combat.combat_state.player
    count = 1
    if counted and player.relics and orb is player.orbs[0] and _has_cables(player):
        count += 1
    for _ in range(count):
        _passive_once(combat, orb, target)

def _has_cables(player : Player) -> bool:
    from sts2_lite.relic import RelicId
    return RelicId.GOLD_PLATED_CABLES in player.relics

def _passive_once(combat : CombatSimulator, orb : Orb, target):
    player = combat.combat_state.player
    value = passive_value(player, orb)
    kind = orb.kind
    if kind == FROST:
        combat.gain_block(player, value)
    elif kind == PLASMA:
        combat.gain_energy(PLASMA_PASSIVE)
    elif kind == DARK:
        orb.evoke += value
    elif kind == LIGHTNING:
        living = living_enemies(combat)
        if living:
            hit = target if target is not None and target.current_hp > 0 else rng.pick_target(living)
            hit.apply_damage(value, player)
    elif kind == GLASS and value > 0:
        orb.passive = max(0, orb.passive - 1)
        for enemy in living_enemies(combat):
            enemy.apply_damage(value, player)


# ------------------------------------------------------------------ the turn

def before_turn_end(combat : CombatSimulator):
    """OrbQueue.BeforeTurnEnd: Lightning, Frost, Dark and Glass fire."""
    player = combat.combat_state.player
    for orb in list(player.orbs):
        if combat.is_over:
            return
        if orb.kind != PLASMA and orb in player.orbs:
            passive(combat, orb, counted=True)

def after_turn_start(combat : CombatSimulator):
    """OrbQueue.AfterTurnStart: Plasma gives its Energy."""
    player = combat.combat_state.player
    for orb in list(player.orbs):
        if orb.kind == PLASMA and orb in player.orbs:
            passive(combat, orb, counted=True)

def trigger_all_passives(combat : CombatSimulator):
    """Emotion Chip: every orb's Passive once more, through the hooks."""
    player = combat.combat_state.player
    for orb in list(player.orbs):
        passive(combat, orb, counted=True)
