"""The Defect's mechanics that live outside single cards: the powers (Focus, Storm, Loop, ...) and the hooks combat.py calls for them.

Orbs themselves are in orbs.py. The powers below are handlers for the (status, event) pairs of status.STATUS_HANDLERS (merged in at the bottom of
status.py). Where the game works a power out in a hook the simulator has no stage for (BeforeCardPlayed, AfterCardGeneratedForCombat), the closest event
is used and the difference noted."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.hooks import HookType
from sts2_lite.status import StatusId

if TYPE_CHECKING:
    from sts2_lite.card import Card
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.creature import Creature

# the powers that hold temporary Focus: (marker, the sign of the Focus it gave); their Focus goes back when the player's turn ends
FOCUS_MARKERS = ((StatusId.FOCUSED_STRIKE, 1), (StatusId.HOTFIX, 1), (StatusId.SYNCHRONIZE, 1), (StatusId.HYPERBEAM_FOCUS_DOWN, -1))
STORM_CARD_AMOUNT = {"STORM": (1, 2), "SUBROUTINE": (1, 1)}      # what playing the power itself adds to it (it does not react to its own play)

def _player(combat : CombatSimulator):
    return combat.combat_state.player

def _living(combat : CombatSimulator) -> list:
    return [e for e in combat.combat_state.enemies if e.current_hp > 0]

def _own(combat : CombatSimulator, owner : Creature) -> bool:
    return owner is combat.combat_state.player


# ------------------------------------------------------------------ helpers cards use

def temp_focus(combat : CombatSimulator, marker : StatusId, amount : int, sign : int):
    """TemporaryFocusPower: Focus that goes back when the turn ends (Artifact stops the negative kind, marker and all)."""
    player = _player(combat)
    before = player.status_amount(marker)
    player.apply_status(marker, amount)
    if player.status_amount(marker) == before:
        return
    player.apply_status(StatusId.FOCUS, sign * amount, bypass_artifact=True)

def return_temporary_focus(creature):
    """The temporary Focus ends with the player's turn."""
    for marker, sign in FOCUS_MARKERS:
        held = creature.status.pop(marker, None)
        if held is not None:
            creature.apply_status(StatusId.FOCUS, -sign * held.amount, bypass_artifact=True)

def add_status_card(combat : CombatSimulator, card_id, pile : str = "discard") -> Card:
    """CardPileCmd.AddGeneratedCardToCombat of a Status the player's card makes (Wound, Dazed, Slimed, Burn, Void): Smokestack and Trash to Treasure hear of it."""
    from sts2_lite.card import Card
    player = _player(combat)
    card = Card.create(card_id)
    if pile == "hand":
        player.add_to_hand(card)
    else:
        player.discard_pile.append(card)
        player.cards_generated += 1
        combat._card_generated(card)
    return card

def buff_claws(combat : CombatSimulator, increase : int, played : Card):
    """Claw.BuffFromClawPlay on every Claw of the combat, the one being played included."""
    from sts2_lite.card import Card, CardId
    player = _player(combat)
    for pile in (player.hand, player.draw_pile, player.discard_pile, player.exhaust_pile):
        for i, c in enumerate(pile):
            if c.card_id is CardId.CLAW:
                grown = Card.create_copy(c)
                grown.bonus_damage += increase
                pile[i] = grown
    if played.card_id is CardId.CLAW:
        played.bonus_damage += increase


# ------------------------------------------------------------------ hooks combat.py calls

def after_energy_reset(combat : CombatSimulator):
    """AfterEnergyReset: Lightning Rod and Spinner channel; the Plasma orbs give their Energy."""
    from sts2_lite import orbs
    player = _player(combat)
    rod = player.status.get(StatusId.LIGHTNING_ROD)
    if rod is not None:
        orbs.channel(combat, orbs.LIGHTNING)
        rod.amount -= 1
        if rod.amount <= 0:
            del player.status[StatusId.LIGHTNING_ROD]
    spinner = player.status.get(StatusId.SPINNER)
    if spinner is not None:
        orbs.channel(combat, orbs.GLASS, spinner.amount)
    if player.orbs:
        orbs.after_turn_start(combat)
    combat.resolve_deaths()

def before_turn_end(combat : CombatSimulator):
    """BeforeTurnEnd: the orbs' Passives."""
    from sts2_lite import orbs
    if _player(combat).orbs:
        orbs.before_turn_end(combat)
        combat.resolve_deaths()

def card_drawn(combat : CombatSimulator, card : Card):
    """Void costs 1 Energy when drawn; Iteration draws for the first Status drawn each turn."""
    from sts2_lite.card import CardId
    player = _player(combat)
    if card.card_id is CardId.VOID:
        combat.combat_state.energy = max(0, combat.combat_state.energy - 1)
    player.statuses_drawn_this_turn += 1
    iteration = player.status.get(StatusId.ITERATION)
    if iteration is not None and player.statuses_drawn_this_turn <= 1:
        player.draw_cards(iteration.amount)

def status_made(combat : CombatSimulator, card : Card):
    """AfterCardGeneratedForCombat for a Status one of the player's cards made: Smokestack, Trash to Treasure and every Rocket Punch."""
    from sts2_lite import orbs
    from sts2_lite.card import CardId
    if combat.in_enemy_turn or combat.card_in_play is None:
        return
    player = _player(combat)
    smokestack = player.status.get(StatusId.SMOKESTACK)
    if smokestack is not None:
        for enemy in _living(combat):
            enemy.apply_damage(smokestack.amount, player)
    trash = player.status.get(StatusId.TRASH_TO_TREASURE)
    if trash is not None:
        orbs.channel_random(combat, trash.amount)
    for pile in (player.hand, player.draw_pile, player.discard_pile):
        for i, c in enumerate(pile):
            if c.card_id is CardId.ROCKET_PUNCH and c.energy_cost not in ("X", 0):
                pile[i] = c.cheaper_until_played(1)      # AddUntilPlayed(-1)

def card_moved_after_play(combat : CombatSimulator, card : Card, played : bool) -> bool:
    """FeralPower.ModifyCardPlayResultLocation: an Attack that cost nothing returns to the top of the hand (the first few each turn)."""
    player = _player(combat)
    if card.type.name != "Attack" or not played or combat.last_energy_paid > 0:
        return False
    player.zero_cost_attacks_this_turn += 1
    feral = player.status.get(StatusId.FERAL)
    if feral is None or player.zero_cost_attacks_this_turn > feral.amount or len(player.hand) >= 10:
        return False
    player.hand.append(card.cost_after_play())
    return True


# ------------------------------------------------------------------ powers

def _biased_cognition_before_turn(combat, owner, amount):
    """BiasedCognitionPower.AfterSideTurnStart: Focus drains away."""
    if _own(combat, owner):
        owner.apply_status(StatusId.FOCUS, -amount, bypass_artifact=True)

def _consuming_shadow_turn_ended(combat, owner, amount):
    """ConsumingShadowPower.AfterSideTurnEnd: the last orb is evoked."""
    from sts2_lite import orbs
    if _own(combat, owner) and owner.orbs:
        for _ in range(amount):
            orbs.evoke_last(combat)
        combat.resolve_deaths()

def _coolant_turn_start(combat, owner, amount):
    """CoolantPower.AfterSideTurnStart: Block for each kind of orb held (Unpowered)."""
    from sts2_lite import orbs
    if _own(combat, owner) and owner.orbs:
        combat.gain_block(owner, orbs.distinct_kinds(owner) * amount)

def _creative_ai_before_draw(combat, owner, amount):
    """CreativeAiPower.BeforeHandDraw: random Powers of the pool join the hand."""
    if not _own(combat, owner):
        return
    from sts2_lite.card import Card, CardType
    from sts2_lite.card.tables import combat_pool
    pool = combat_pool("DEFECT", CardType.Power)
    for _ in range(amount):
        owner.add_to_hand(Card.create_generated(rng.choice(pool)))

def _hailstorm_turn_end(combat, owner, amount):
    """HailstormPower.BeforeSideTurnEnd: every enemy takes damage while a Frost orb is held."""
    from sts2_lite import orbs
    if _own(combat, owner) and any(o.kind == orbs.FROST for o in owner.orbs):
        for enemy in _living(combat):
            enemy.apply_damage(amount, owner)

def _loop_turn_start(combat, owner, amount):
    """LoopPower.AfterPlayerTurnStart: the first orb's Passive again."""
    from sts2_lite import orbs
    if _own(combat, owner):
        for _ in range(amount):
            if owner.orbs and not combat.is_over:
                orbs.passive(combat, owner.orbs[0])
        combat.resolve_deaths()

def _power_played(combat, owner, amount, card, effect):
    if not _own(combat, owner) or card.type.name != "Power":
        return
    own_gain = STORM_CARD_AMOUNT.get(card.card_id.name)
    if own_gain is not None:
        amount -= own_gain[1] if card.is_upgraded else own_gain[0]      # the amount the power had before this play was applied
    if amount > 0:
        effect(combat, amount)

def _storm_card_played(combat, owner, amount, card):
    """StormPower: a Lightning orb for every Power played (the amount it had before the card)."""
    from sts2_lite import orbs
    _power_played(combat, owner, amount, card, lambda combat, n: orbs.channel(combat, orbs.LIGHTNING, n))

def _subroutine_card_played(combat, owner, amount, card):
    """SubroutinePower: Energy for every Power played."""
    _power_played(combat, owner, amount, card, lambda combat, n: combat.gain_energy(n))


STATUS_HANDLERS = {
    (StatusId.BIASED_COGNITION, HookType.BEFORE_PLAYER_TURN) : _biased_cognition_before_turn,
    (StatusId.CONSUMING_SHADOW, HookType.PLAYER_TURN_ENDED) : _consuming_shadow_turn_ended,
    (StatusId.COOLANT, HookType.PLAYER_TURN_START) : _coolant_turn_start,
    (StatusId.CREATIVE_AI, HookType.BLOCK_CLEARED) : _creative_ai_before_draw,
    (StatusId.HAILSTORM, HookType.END_TURN) : _hailstorm_turn_end,
    (StatusId.LOOP, HookType.PLAYER_TURN_START) : _loop_turn_start,
    (StatusId.STORM, HookType.CARD_PLAYED) : _storm_card_played,
    (StatusId.SUBROUTINE, HookType.CARD_PLAYED) : _subroutine_card_played,
}
