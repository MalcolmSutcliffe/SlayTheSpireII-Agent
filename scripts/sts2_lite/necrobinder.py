"""The Necrobinder's mechanics that live outside single cards: Osty's attacks, Doom, Souls, and the powers that react to them.

Osty itself is in osty.py. Cards call osty_attack / apply_doom / create_souls from card/plays/necrobinder.py; the powers below are handlers for the
(status, event) pairs of status.STATUS_HANDLERS (merged in at the bottom of status.py). Where the game works a power out in a hook the simulator
has no stage for (BeforeCardPlayed, AfterCardEnteredCombat), the closest event is used and the difference noted."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.hooks import HookType
from sts2_lite.status import StatusId

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.creature import Creature

BONE_FLUTE_BLOCK = 2
BOOK_REPAIR_KNIFE_HEAL = 3
FLATTEN_COST_REDUCED = ("FLATTEN",)

def summon(player, amount : int):
    from sts2_lite.osty import summon as _summon      # osty.py needs Creature, which needs the card package, which needs this module
    _summon(player, amount)

def hurt_osty(player, amount : int) -> int:
    from sts2_lite.osty import hurt_osty as _hurt
    return _hurt(player, amount)

def _player(combat : CombatSimulator):
    return combat.combat_state.player

def _living(combat : CombatSimulator) -> list:
    return [e for e in combat.combat_state.enemies if e.current_hp > 0]

def _own(combat : CombatSimulator, owner : Creature) -> bool:
    return owner is combat.combat_state.player

# ------------------------------------------------------------------ Osty

def osty_attack(combat : CombatSimulator, base : int, targets, hits : int = 1, random_targets : bool = False) -> int:
    """DamageCmd.Attack(...).FromOsty: the damage Osty deals (base + Calcify, then the target's Vulnerable and the rest; no Strength) as one attack command.
    `targets`: one creature, or a list (every enemy); `random_targets`: each hit picks a living enemy. Nothing happens without a living Osty.
    Returns the damage dealt (blocked included) to the enemies hit."""
    from sts2_lite.damage import modify_damage
    player = _player(combat)
    osty = player.osty
    if osty is None or osty.current_hp <= 0:
        return 0
    base += player.status_amount(StatusId.CALCIFY)
    card = combat.card_in_play
    dealt = 0
    if random_targets:
        for _ in range(hits):
            living = _living(combat)
            if not living or osty.current_hp <= 0:
                break
            target = rng.pick_target(living)
            before = target.damage_taken
            target.apply_attack_damage(modify_damage(base, osty, target, card, owner=player), osty, 1)
            dealt += target.damage_taken - before
            _sic_em(combat, target, 1)
    else:
        for target in (targets if isinstance(targets, list) else [targets]):
            if target.current_hp <= 0:
                continue
            before = target.damage_taken
            damage = lambda target=target: modify_damage(base, osty, target, card, owner=player)
            target.apply_attack_damage(damage(), osty, hits, damage if hits > 1 else None)
            dealt += target.damage_taken - before
            _sic_em(combat, target, hits)
    player.osty_attacks_this_turn += 1
    if player.relics:
        from sts2_lite.relic import RelicId
        if RelicId.BONE_FLUTE in player.relics:
            combat.gain_block(player, BONE_FLUTE_BLOCK)          # BoneFlute.AfterAttack: unpowered Block for every attack Osty makes
    _flatten_cheaper(player)
    return dealt

def _sic_em(combat : CombatSimulator, target, hits : int):
    """SicEmPower.AfterDamageGiven: every hit of Osty on the marked enemy summons more."""
    sic_em = target.status.get(StatusId.SIC_EM)
    if sic_em is not None:
        summon(_player(combat), sic_em.amount * hits)

def _flatten_cheaper(player):
    """Flatten costs 0 for the rest of the turn once Osty has attacked."""
    from sts2_lite.card.ids import CardId
    for pile in (player.hand, player.draw_pile, player.discard_pile):
        for i, c in enumerate(pile):
            if c.card_id is CardId.FLATTEN and c.energy_cost != 0:
                pile[i] = c.cheaper_this_turn(c.energy_cost)

def osty_hurt(combat : CombatSimulator, lost : int):
    """NecroMasteryPower.AfterCurrentHpChanged: every HP Osty loses is dealt to every enemy (Unblockable, Unpowered)."""
    player = _player(combat)
    mastery = player.status.get(StatusId.NECRO_MASTERY)
    if mastery is not None and lost > 0:
        for enemy in _living(combat):
            enemy.lose_hp(lost * mastery.amount)

def kill_osty(combat : CombatSimulator) -> int:
    """CreatureCmd.Kill(Osty): the HP it had are lost (Necro Mastery hears of it). Returns them."""
    player = _player(combat)
    osty = player.osty
    return hurt_osty(player, osty.current_hp) if osty is not None else 0

# ------------------------------------------------------------------ Doom

def apply_doom(combat : CombatSimulator, target, amount : int):
    """PowerCmd.Apply<DoomPower> from the player (cards, Countdown, Oblivion, the potion): Unsettling Lamp counts, Artifact stops it."""
    if amount <= 0 or target.current_hp <= 0:
        return
    from sts2_lite.card.effects import _debuff
    combat.combat_state.player.doom_applied_this_turn = True
    _debuff(combat, target, StatusId.DOOM, amount)

def after_debuff(combat : CombatSimulator, target, status : StatusId):
    """AfterPowerAmountChanged, for powers the player applied: Shroud (Doom gives Block) and Sleight of Flesh (any debuff on an enemy hurts it)."""
    player = _player(combat)
    if target is player or not player.status:
        return
    if status is StatusId.DOOM:
        shroud = player.status.get(StatusId.SHROUD)
        if shroud is not None:
            combat.gain_block(player, shroud.amount)
    sleight = player.status.get(StatusId.SLEIGHT_OF_FLESH)
    if sleight is not None and target.current_hp > 0 and hasattr(target, "enemy_id"):
        target.apply_damage(sleight.amount, player)         # Unpowered: no Strength, Block still counts

def doom_kill(combat : CombatSimulator, creatures : list):
    """DoomPower.DoomKill: everything doomed dies together, then Book Repair Knife hears of it."""
    killed = [c for c in creatures if c.current_hp > 0]
    player = _player(combat)
    for creature in killed:
        creature.die()
    if killed and player.relics:
        from sts2_lite.relic import RelicId
        if RelicId.BOOK_REPAIR_KNIFE in player.relics:
            count = sum(c is not player for c in killed)
            player.current_hp = min(player.max_hp, player.current_hp + BOOK_REPAIR_KNIFE_HEAL * count)

def doomed(creatures) -> list:
    return [c for c in creatures if c.current_hp > 0 and StatusId.DOOM in c.status and c.current_hp <= c.status[StatusId.DOOM].amount]

def _doom_on_enemy_turn_end(combat : CombatSimulator, owner : Creature, amount : int):
    """DoomPower.BeforeSideTurnEnd: once the enemies have acted, every enemy whose HP is no more than its Doom dies."""
    if _own(combat, owner) or owner.current_hp <= 0 or owner.current_hp > amount:
        return
    doom_kill(combat, doomed(combat.combat_state.enemies))

def _doom_on_player_turn_ended(combat : CombatSimulator, owner : Creature, amount : int):
    """DoomPower.AfterSideTurnEnd: the player's own Doom (Neurosurge) kills at the end of their turn."""
    if _own(combat, owner) and 0 < owner.current_hp <= amount:
        doom_kill(combat, [owner])

# ------------------------------------------------------------------ Souls

def create_souls(combat : CombatSimulator, count : int, upgraded : bool = False, pile : str = "draw") -> list:
    """Soul.Create + AddGeneratedCardsToCombat: into the draw pile at random places, the discard pile, or the hand."""
    from sts2_lite.card import Card, CardId
    player = _player(combat)
    souls = []
    for _ in range(count):
        soul = Card.create_generated(CardId.SOUL, upgraded)
        if pile == "draw":
            player.insert_into_draw_pile(soul)
        elif pile == "discard":
            player.discard_pile.append(soul)
            player.cards_generated += 1
            combat._card_generated(soul)
        else:
            player.add_to_hand(soul)
        souls.append(soul)
    return souls

# ------------------------------------------------------------------ powers

def _borrowed_time_on_turn_ended(combat, owner, amount):
    owner.status.pop(StatusId.BORROWED_TIME, None)

def _call_of_the_void_before_draw(combat, owner, amount):
    """CallOfTheVoidPower.BeforeHandDraw: random cards of the pool (no Basic or Ancient ones), Ethereal, into the hand."""
    if not _own(combat, owner):
        return
    from sts2_lite.card import Card
    from sts2_lite.card.tables import combat_pool
    pool = combat_pool("NECROBINDER")
    for card_id in rng.sample(pool, min(amount, len(pool))):
        owner.add_to_hand(Card.create_generated(card_id).with_keyword(_keyword("ETHEREAL")))

def _keyword(name : str):
    from sts2_lite.card.ids import CardKeyword
    return CardKeyword[name]

def _countdown_on_turn_start(combat, owner, amount):
    if _own(combat, owner):
        living = _living(combat)
        if living:
            apply_doom(combat, rng.pick_target(living), amount)

def _neurosurge_on_turn_start(combat, owner, amount):
    if _own(combat, owner):
        owner.apply_status(StatusId.DOOM, amount)
        shroud = owner.status.get(StatusId.SHROUD)      # ShroudPower: applier == owner, and Neurosurge applies to itself
        if shroud is not None:
            combat.gain_block(owner, shroud.amount)

def _danse_macabre_on_card_played(combat, owner, amount, card):
    """DanseMacabrePower.BeforeCardPlayed: a card that costs 2 or more gives Block (Unpowered)."""
    if _own(combat, owner) and type(card.energy_cost) is int and card.current_cost(owner) >= 2:
        combat.gain_block(owner, amount)

def _devour_life_on_card_played(combat, owner, amount, card):
    from sts2_lite.card.ids import CardId
    if _own(combat, owner) and card.card_id is CardId.SOUL:
        summon(owner, amount)

def _haunt_on_card_played(combat, owner, amount, card):
    from sts2_lite.card.ids import CardId
    living = _living(combat)
    if _own(combat, owner) and card.card_id is CardId.SOUL and living:
        rng.pick_target(living).lose_hp(amount)         # Unblockable | Unpowered

def _oblivion_on_card_played(combat, owner, amount, card):
    """OblivionPower: every card the player plays after it was applied adds its Doom (the play that applied it adds none)."""
    from sts2_lite.status import fresh_amount
    amount -= fresh_amount(owner.status.get(StatusId.OBLIVION))
    if amount > 0 and not _own(combat, owner):
        apply_doom(combat, owner, amount)

def _oblivion_on_player_turn_ended(combat, owner, amount):
    if not _own(combat, owner):
        owner.status.pop(StatusId.OBLIVION, None)

def _sic_em_on_enemy_turn_end(combat, owner, amount):
    owner.status.pop(StatusId.SIC_EM, None)

def _sentry_mode_before_draw(combat, owner, amount):
    """SentryModePower.BeforeHandDraw: Sweeping Gazes into the hand."""
    if _own(combat, owner):
        from sts2_lite.card import Card, CardId
        for _ in range(amount):
            owner.add_to_hand(Card.create_generated(CardId.SWEEPING_GAZE))

def _spirit_of_ash_on_card_played(combat, owner, amount, card):
    if _own(combat, owner) and card.ethereal:
        combat.gain_block(owner, amount)

def _veilpiercer_on_card_played(combat, owner, amount, card):
    """VeilpiercerPower: the next Ethereal cards cost nothing, one use each."""
    if _own(combat, owner) and card.ethereal:
        veil = owner.status[StatusId.VEILPIERCER]
        veil.amount -= 1
        if veil.amount <= 0:
            del owner.status[StatusId.VEILPIERCER]

def _summon_next_turn_on_turn_start(combat, owner, amount):
    if _own(combat, owner):
        summon(owner, amount)
        owner.status.pop(StatusId.SUMMON_NEXT_TURN, None)

def _pagestorm_on_drawn(combat, owner, amount):
    owner.draw_cards(amount)

STATUS_HANDLERS = {
    (StatusId.DOOM, HookType.ENEMY_TURN_END) : _doom_on_enemy_turn_end,
    (StatusId.DOOM, HookType.PLAYER_TURN_ENDED) : _doom_on_player_turn_ended,
    (StatusId.BORROWED_TIME, HookType.PLAYER_TURN_ENDED) : _borrowed_time_on_turn_ended,
    (StatusId.CALL_OF_THE_VOID, HookType.BLOCK_CLEARED) : _call_of_the_void_before_draw,
    (StatusId.COUNTDOWN, HookType.PLAYER_TURN_START) : _countdown_on_turn_start,
    (StatusId.NEUROSURGE, HookType.PLAYER_TURN_START) : _neurosurge_on_turn_start,
    (StatusId.DANSE_MACABRE, HookType.CARD_PLAYED) : _danse_macabre_on_card_played,
    (StatusId.DEVOUR_LIFE, HookType.CARD_PLAYED) : _devour_life_on_card_played,
    (StatusId.HAUNT, HookType.CARD_PLAYED) : _haunt_on_card_played,
    (StatusId.OBLIVION, HookType.CARD_PLAYED) : _oblivion_on_card_played,
    (StatusId.OBLIVION, HookType.PLAYER_TURN_ENDED) : _oblivion_on_player_turn_ended,
    (StatusId.SIC_EM, HookType.ENEMY_TURN_END) : _sic_em_on_enemy_turn_end,
    (StatusId.SENTRY_MODE, HookType.BLOCK_CLEARED) : _sentry_mode_before_draw,
    (StatusId.SPIRIT_OF_ASH, HookType.CARD_PLAYED) : _spirit_of_ash_on_card_played,
    (StatusId.VEILPIERCER, HookType.CARD_PLAYED) : _veilpiercer_on_card_played,
    (StatusId.SUMMON_NEXT_TURN, HookType.PLAYER_TURN_START) : _summon_next_turn_on_turn_start,
}


# ------------------------------------------------------------------ card choices (the picks cards ask for; see CombatSimulator._apply_choice)

def _choose_sculpting(combat, choice, index, card):
    """Sculpting Strike: the picked card gains Ethereal."""
    combat.combat_state.player.hand[index] = card.with_keyword(_keyword("ETHEREAL"))

def _choose_snap(combat, choice, index, card):
    """Snap: the picked card gains Retain."""
    combat.combat_state.player.hand[index] = card.with_keyword(_keyword("RETAIN"))

def _choose_transfigure(combat, choice, index, card):
    """Transfigure: the picked card plays one more time and costs 1 more (X costs and negative costs stay)."""
    player = combat.combat_state.player
    new_card = card.with_replay(1)
    if type(new_card.energy_cost) is int and new_card.energy_cost >= 0:
        new_card.energy_cost += 1
    player.hand[index] = new_card

def _choose_seance(combat, choice, index, card):
    """Seance: picked cards of the draw pile become Souls (in the same place)."""
    from sts2_lite.card import Card, CardId
    player = combat.combat_state.player
    player.draw_pile[index] = Card.create_generated(CardId.SOUL)
    player.cards_generated += 1
    picked = choice.picked + [index]
    rest = [i for i, c in enumerate(player.draw_pile) if i not in picked and c.card_id is not CardId.SOUL]
    if choice.amount > 1 and rest:
        combat.request_choice("seance", rest, "draw", choice.amount - 1, picked=picked)

NECROBINDER_CHOICES = {"sculpting" : _choose_sculpting, "snap" : _choose_snap, "transfigure" : _choose_transfigure, "seance" : _choose_seance}


# ------------------------------------------------------------------ combat hooks

def after_card_played(combat : CombatSimulator, card : Card):
    """Ethereal plays, Banshee's Cry getting cheaper, Right Hand Hand returning from the discard pile (AfterCardPlayed(Late))."""
    from sts2_lite.card import CardId
    player = combat.combat_state.player
    if card.ethereal:
        player.ethereal_plays += 1
        for pile in (player.hand, player.draw_pile, player.discard_pile, player.exhaust_pile):
            for i, c in enumerate(pile):
                if c.card_id is CardId.BANSHEES_CRY and c is not card:
                    pile[i] = c.cheaper_this_combat(2)
    if combat.last_energy_paid >= 2:
        for c in list(player.discard_pile):
            if c.card_id is CardId.RIGHT_HAND_HAND and len(player.hand) < 10:
                player.discard_pile.remove(c)
                player.hand.append(c)

def on_enemy_died(combat : CombatSimulator, count : int):
    """Melancholy: 1 cheaper for every creature that dies, wherever it is in the combat piles."""
    from sts2_lite.card import CardId
    player = combat.combat_state.player
    if player.character != "NECROBINDER":
        return
    for _ in range(count):
        for pile in (player.hand, player.draw_pile, player.discard_pile):
            for i, c in enumerate(pile):
                if c.card_id is CardId.MELANCHOLY:
                    pile[i] = c.cheaper_this_combat(1)
