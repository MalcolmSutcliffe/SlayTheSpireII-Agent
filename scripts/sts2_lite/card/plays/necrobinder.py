"""The Necrobinder's cards (NecrobinderCardPool). Osty's Attacks go through necrobinder.osty_attack (nothing happens without a living Osty); Doom through
necrobinder.apply_doom. The other powers are in necrobinder.py."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.helpers import enemy_at, living_enemies
from sts2_lite.necrobinder import apply_doom, create_souls, doom_kill, doomed, kill_osty, osty_attack, summon
from sts2_lite.osty import heal_osty, osty_alive
from sts2_lite.status import StatusId, is_debuff

from sts2_lite.card.card import Card
from sts2_lite.card.effects import PLAIN_DAMAGE, _attack, _debuff, _gain_block, _vulnerable, _weak, apply_fresh, temp_strength
from sts2_lite.card.ids import CardId
from sts2_lite.card.plays.silent import _hit_all

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator

def _damage(card : Card, is_upgraded : bool) -> int:
    return PLAIN_DAMAGE[card.card_id][is_upgraded]

def _player(combat : CombatSimulator):
    return combat.combat_state.player

def _osty_hp(combat : CombatSimulator, maximum : bool = False) -> int:
    player = _player(combat)
    return (player.osty.max_hp if maximum else player.osty.current_hp) if osty_alive(player) else 0

# ------------------------------------------------------------ Basic

def play_strike_necrobinder(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_defend_necrobinder(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)

def play_bodyguard(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    summon(_player(combat), 7 if is_upgraded else 5)

def play_unleash(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """6 (9) plus 1 for every HP Osty has."""
    osty_attack(combat, (9 if is_upgraded else 6) + _osty_hp(combat), enemy_at(combat, target_index))

# ------------------------------------------------------------ Token

def play_soul(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).draw_cards(3 if is_upgraded else 2)

def play_sweeping_gaze(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    osty_attack(combat, _damage(card, is_upgraded), None, random_targets=True)

# ------------------------------------------------------------ Common

def play_afterlife(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    summon(_player(combat), 9 if is_upgraded else 6)

def play_blight_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Doom as much as the damage dealt (Block counts)."""
    target = enemy_at(combat, target_index)
    before = target.damage_taken
    _attack(combat, _damage(card, is_upgraded), target)
    if target.current_hp > 0:
        apply_doom(combat, target, target.damage_taken - before)

def play_defile(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_defy(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 9 if is_upgraded else 6)
    _weak(combat, enemy_at(combat, target_index), 1)

def play_drain_power(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Upgrades random cards of the discard pile."""
    player = _player(combat)
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    upgradable = [c for c in player.discard_pile if c.is_upgradable]
    for c in rng.sample(upgradable, min(3 if is_upgraded else 2, len(upgradable))):
        player.upgrade_card(c)

def play_fear(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    if target.current_hp > 0:
        _vulnerable(combat, target, 2 if is_upgraded else 1)

def play_flatten(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    osty_attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_grave_warden(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 11 if is_upgraded else 8)
    create_souls(combat, 1)

def play_graveblast(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    discard = _player(combat).discard_pile
    combat.request_choice("to_hand", list(range(len(discard))), "discard", 1, card)

def play_invoke(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = _player(combat)
    player.apply_status(StatusId.SUMMON_NEXT_TURN, 3 if is_upgraded else 2)
    player.apply_status(StatusId.ENERGY_NEXT_TURN, 3 if is_upgraded else 2)

def play_negative_pulse(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 6 if is_upgraded else 5)
    for enemy in living_enemies(combat):
        apply_doom(combat, enemy, 11 if is_upgraded else 7)

def play_poke(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    osty_attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_pull_aggro(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    summon(_player(combat), 5 if is_upgraded else 4)
    _gain_block(combat, 9 if is_upgraded else 7)

def play_reap(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_reave(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    create_souls(combat, 1, upgraded=is_upgraded)

def play_scourge(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    apply_doom(combat, enemy_at(combat, target_index), 16 if is_upgraded else 13)
    _player(combat).draw_cards(2 if is_upgraded else 1)

def play_sculpting_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """After the hit, a card of the hand that is not Ethereal becomes Ethereal."""
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    hand = _player(combat).hand
    combat.request_choice("sculpting", [i for i, c in enumerate(hand) if not c.ethereal], "hand", 1, card)

def play_snap(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    osty_attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    hand = _player(combat).hand
    combat.request_choice("snap", [i for i, c in enumerate(hand) if not c.retains], "hand", 1, card)

def play_sow(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit_all(combat, _damage(card, is_upgraded))

def play_wisp(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_energy(1)

# ------------------------------------------------------------ Uncommon

def play_bone_shards(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Osty hits every enemy, the player gets Block, and Osty dies."""
    osty_attack(combat, _damage(card, is_upgraded), living_enemies(combat))
    combat.resolve_deaths()
    _gain_block(combat, 12 if is_upgraded else 9)
    if osty_alive(_player(combat)):
        kill_osty(combat)

def play_borrowed_time(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = _player(combat)
    combat.gain_energy(6 if is_upgraded else 4)
    player.apply_status(StatusId.BORROWED_TIME, 1)

def play_bury(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_calcify(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.CALCIFY, 6 if is_upgraded else 4)

def play_capture_spirit(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """The enemy loses HP (Unblockable, Unpowered), and Souls join the draw pile."""
    enemy_at(combat, target_index).lose_hp(4 if is_upgraded else 3)
    create_souls(combat, 4 if is_upgraded else 3)

def play_cleanse(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Summon, then a card of the draw pile of your choice is exhausted."""
    summon(_player(combat), 5 if is_upgraded else 3)
    draw = _player(combat).draw_pile
    combat.request_choice("exhaust", list(range(len(draw))), "draw", 0, card)

def play_countdown(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.COUNTDOWN, 9 if is_upgraded else 6)

def play_danse_macabre(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.DANSE_MACABRE, 6 if is_upgraded else 4)

def play_death_march(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """8 (9) plus 4 (6) for every card drawn this turn outside the hand draw."""
    drawn = _player(combat).extra_draws_this_turn
    _attack(combat, (9 + 6 * drawn) if is_upgraded else (8 + 4 * drawn), enemy_at(combat, target_index))

def play_deathbringer(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for enemy in living_enemies(combat):
        apply_doom(combat, enemy, 26 if is_upgraded else 21)
    for enemy in living_enemies(combat):
        _weak(combat, enemy, 1)

def play_deaths_door(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Block once, and twice more if the player has applied Doom this turn."""
    gains = 3 if _player(combat).doom_applied_this_turn else 1
    for _ in range(gains):
        _gain_block(combat, 7 if is_upgraded else 6)

def play_debilitate(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    if target.current_hp > 0:
        _debuff(combat, target, StatusId.DEBILITATE, 3 if is_upgraded else 2)

def play_delay(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 13 if is_upgraded else 11)
    _player(combat).apply_status(StatusId.ENERGY_NEXT_TURN, 2 if is_upgraded else 1)

def play_dirge(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    """X times: Summon 3 (4); X Souls (upgraded ones when Dirge is) join the draw pile."""
    player = _player(combat)
    for _ in range(x):
        summon(player, 4 if is_upgraded else 3)
    create_souls(combat, x, upgraded=is_upgraded)

def play_dredge(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Up to 3 cards of the discard pile return to the hand."""
    player = _player(combat)
    discard = player.discard_pile
    count = min(3, 10 - len(player.hand), len(discard))
    if count > 0:
        combat.request_choice("to_hand", list(range(len(discard))), "discard", count, card)

def play_enfeebling_touch(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    temp_strength(enemy_at(combat, target_index), StatusId.ENFEEBLING_TOUCH, 11 if is_upgraded else 8, -1, combat)

def play_fetch(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Osty attacks; the first play of this card in a turn draws a card. `card` is this play's own copy (CombatSimulator.private_copy)."""
    player = _player(combat)
    first = card.last_played_turn != combat.combat_state.player_turn
    osty_attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    if first:
        player.draw_cards(1)
    card.last_played_turn = combat.combat_state.player_turn

def play_friendship(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = _player(combat)
    player.apply_status(StatusId.STRENGTH, -1 if is_upgraded else -2)
    player.apply_status(StatusId.FRIENDSHIP, 1)

def play_haunt(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.HAUNT, 9 if is_upgraded else 7)

def play_high_five(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    osty_attack(combat, _damage(card, is_upgraded), living_enemies(combat))
    for enemy in living_enemies(combat):
        _vulnerable(combat, enemy, 3 if is_upgraded else 2)

def play_lethality(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.LETHALITY, 75 if is_upgraded else 50)

def play_melancholy(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 17 if is_upgraded else 13)

def play_no_escape(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """10 (15) Doom, and 5 more for every 10 Doom the enemy already has."""
    target = enemy_at(combat, target_index)
    apply_doom(combat, target, (15 if is_upgraded else 10) + 5 * (target.status_amount(StatusId.DOOM) // 10))

def play_pagestorm(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.PAGESTORM, 1)

def play_parse(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).draw_cards(4 if is_upgraded else 3)

def play_pull_from_below(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """One hit for every Ethereal card played this combat."""
    target = enemy_at(combat, target_index)
    hits = _player(combat).ethereal_plays
    if hits > 0:
        _attack(combat, _damage(card, is_upgraded), target, hits)

def play_putrefy(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _weak(combat, target, 3 if is_upgraded else 2)
    _vulnerable(combat, target, 3 if is_upgraded else 2)

def play_rattle(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Osty hits once, and once more for every attack it has made this turn."""
    hits = 1 + _player(combat).osty_attacks_this_turn
    osty_attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index), hits)

def play_right_hand_hand(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    osty_attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_severance(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """A Soul to the draw pile, the discard pile and the hand."""
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    create_souls(combat, 1, pile="draw")
    create_souls(combat, 1, pile="discard")
    create_souls(combat, 1, pile="hand")

def play_shroud(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.SHROUD, 4 if is_upgraded else 3)

def play_sic_em(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    osty_attack(combat, _damage(card, is_upgraded), target)
    if target.current_hp > 0:
        _debuff(combat, target, StatusId.SIC_EM, 4 if is_upgraded else 3)

def play_sleight_of_flesh(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.SLEIGHT_OF_FLESH, 13 if is_upgraded else 9)

def play_spur(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = _player(combat)
    summon(player, 5 if is_upgraded else 3)
    heal_osty(player, 7 if is_upgraded else 5)

def play_veilpiercer(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    _player(combat).apply_status(StatusId.VEILPIERCER, 1)

# ------------------------------------------------------------ Rare

def play_banshees_cry(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit_all(combat, _damage(card, is_upgraded))

def play_call_of_the_void(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.CALL_OF_THE_VOID, 1)

def play_demesne(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.DEMESNE, 1)

def play_devour_life(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.DEVOUR_LIFE, 2 if is_upgraded else 1)

def play_eidolon(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Plays every Ethereal card of the exhaust pile."""
    for c in [c for c in _player(combat).exhaust_pile if c.ethereal and not c.is_unplayable]:
        combat.auto_play(c)

def play_end_of_days(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Doom on every enemy, and what is doomed dies now."""
    for enemy in living_enemies(combat):
        apply_doom(combat, enemy, 37 if is_upgraded else 29)
    doom_kill(combat, doomed(combat.combat_state.enemies))

def play_eradicate(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    target = enemy_at(combat, target_index)
    if x > 0:
        _attack(combat, _damage(card, is_upgraded), target, x)

def play_hang(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """The damage is multiplied by the Hang the enemy has (damage.modify_damage); then its Hang doubles (2 at first)."""
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    if target.current_hp > 0:
        target.apply_status(StatusId.HANG, max(2, target.status_amount(StatusId.HANG)))

def play_misery(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Every other enemy gets the debuffs the target had before the hit."""
    target = enemy_at(combat, target_index)
    debuffs = {sid: s.amount for sid, s in target.status.items() if is_debuff(sid, s.amount) and s.amount != 0}
    _attack(combat, _damage(card, is_upgraded), target)
    for enemy in living_enemies(combat):
        if enemy is not target:
            for status_id, amount in debuffs.items():
                enemy.apply_status(status_id, amount)

def play_necro_mastery(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = _player(combat)
    summon(player, 8 if is_upgraded else 5)
    player.apply_status(StatusId.NECRO_MASTERY, 1)

def play_neurosurge(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = _player(combat)
    combat.gain_energy(4 if is_upgraded else 3)
    player.draw_cards(2)
    player.apply_status(StatusId.NEUROSURGE, 3)

def play_oblivion(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    apply_fresh(combat, enemy_at(combat, target_index), StatusId.OBLIVION, 4 if is_upgraded else 3, debuff=True)

def play_reanimate(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    summon(_player(combat), 25 if is_upgraded else 20)

def play_reaper_form(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.REAPER_FORM, 1)

def play_sacrifice(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Osty dies; Block is three times its Max HP."""
    block = 3 * _osty_hp(combat, maximum=True)
    kill_osty(combat)
    _gain_block(combat, block)

def play_seance(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    draw = _player(combat).draw_pile
    combat.request_choice("seance", list(range(len(draw))), "draw", 1, card)

def play_sentry_mode(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.SENTRY_MODE, 1)

def play_shared_fate(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    from sts2_lite.necrobinder import after_debuff
    player = _player(combat)
    target = enemy_at(combat, target_index)
    player.apply_status(StatusId.STRENGTH, -2)
    before = target.status_amount(StatusId.STRENGTH)
    target.apply_status(StatusId.STRENGTH, -3 if is_upgraded else -2)
    if target.status_amount(StatusId.STRENGTH) < before:
        after_debuff(combat, target, StatusId.STRENGTH)

def play_soul_storm(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """9 plus 4 (6) for every Soul in the exhaust pile."""
    souls = sum(c.card_id is CardId.SOUL for c in _player(combat).exhaust_pile)
    _attack(combat, 9 + (6 if is_upgraded else 4) * souls, enemy_at(combat, target_index))

def play_spirit_of_ash(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.SPIRIT_OF_ASH, 5 if is_upgraded else 4)

def play_squeeze(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """25 (30) plus 5 (6) for every other Osty Attack card in the fight."""
    from sts2_lite.card.constants import OSTY_ATTACK_CARDS
    player = _player(combat)
    others = sum(c.card_id in OSTY_ATTACK_CARDS for c in player.hand + player.draw_pile + player.discard_pile + player.exhaust_pile)
    osty_attack(combat, (30 + 6 * others) if is_upgraded else (25 + 5 * others), enemy_at(combat, target_index))

def play_the_scythe(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """13 plus what it has grown by; each play adds 5 (7). `card` is this play's own copy, so it can remember the growth."""
    _attack(combat, 13 + card.bonus_damage, enemy_at(combat, target_index))
    card.bonus_damage += 7 if is_upgraded else 5

def play_times_up(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, target.status_amount(StatusId.DOOM), target)

def play_transfigure(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    hand = _player(combat).hand
    combat.request_choice("transfigure", list(range(len(hand))), "hand", 1, card)

def play_undeath(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Block, and a copy of itself joins the discard pile."""
    player = _player(combat)
    _gain_block(combat, 9 if is_upgraded else 7)
    clone = Card.create_generated(CardId.UNDEATH, is_upgraded)
    player.discard_pile.append(clone)
    player.cards_generated += 1
    combat._card_generated(clone)

# ------------------------------------------------------------ Ancient

def play_forbidden_grimoire(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.FORBIDDEN_GRIMOIRE, 1)

def play_protector(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """10 (15) plus 1 for every Max HP Osty has."""
    osty_attack(combat, (15 if is_upgraded else 10) + _osty_hp(combat, maximum=True), enemy_at(combat, target_index))

PLAIN_DAMAGE.update({       # id : (damage, damage upgraded): what the cards print (Osty's damage included; the Attacks that count something start from their base)
    CardId.STRIKE_NECROBINDER : (6, 9), CardId.UNLEASH : (6, 9), CardId.SWEEPING_GAZE : (10, 15),
    CardId.BLIGHT_STRIKE : (8, 10), CardId.DEFILE : (13, 17), CardId.DRAIN_POWER : (10, 12), CardId.FEAR : (7, 8), CardId.FLATTEN : (12, 16),
    CardId.GRAVEBLAST : (4, 6), CardId.POKE : (6, 9), CardId.REAP : (27, 33), CardId.REAVE : (10, 13), CardId.SCULPTING_STRIKE : (9, 12),
    CardId.SNAP : (7, 10), CardId.SOW : (8, 11), CardId.BONE_SHARDS : (9, 12), CardId.BURY : (52, 63), CardId.DEATH_MARCH : (8, 9),
    CardId.DEBILITATE : (10, 12), CardId.FETCH : (3, 6), CardId.HIGH_FIVE : (11, 13), CardId.PULL_FROM_BELOW : (5, 7), CardId.RATTLE : (7, 9),
    CardId.RIGHT_HAND_HAND : (4, 6), CardId.SEVERANCE : (13, 18), CardId.SIC_EM : (5, 6), CardId.VEILPIERCER : (10, 13),
    CardId.BANSHEES_CRY : (33, 33), CardId.ERADICATE : (11, 14), CardId.HANG : (10, 13), CardId.MISERY : (7, 9), CardId.SOUL_STORM : (9, 9),
    CardId.SQUEEZE : (25, 30), CardId.THE_SCYTHE : (13, 13), CardId.TIMES_UP : (0, 0), CardId.PROTECTOR : (10, 15),
})

NECROBINDER_PLAYS = {
    CardId.STRIKE_NECROBINDER : play_strike_necrobinder, CardId.DEFEND_NECROBINDER : play_defend_necrobinder, CardId.BODYGUARD : play_bodyguard, CardId.UNLEASH : play_unleash,
    CardId.SOUL : play_soul, CardId.SWEEPING_GAZE : play_sweeping_gaze,
    CardId.AFTERLIFE : play_afterlife, CardId.BLIGHT_STRIKE : play_blight_strike, CardId.DEFILE : play_defile, CardId.DEFY : play_defy, CardId.DRAIN_POWER : play_drain_power,
    CardId.FEAR : play_fear, CardId.FLATTEN : play_flatten, CardId.GRAVE_WARDEN : play_grave_warden, CardId.GRAVEBLAST : play_graveblast, CardId.INVOKE : play_invoke,
    CardId.NEGATIVE_PULSE : play_negative_pulse, CardId.POKE : play_poke, CardId.PULL_AGGRO : play_pull_aggro, CardId.REAP : play_reap, CardId.REAVE : play_reave,
    CardId.SCOURGE : play_scourge, CardId.SCULPTING_STRIKE : play_sculpting_strike, CardId.SNAP : play_snap, CardId.SOW : play_sow, CardId.WISP : play_wisp,
    CardId.BONE_SHARDS : play_bone_shards, CardId.BORROWED_TIME : play_borrowed_time, CardId.BURY : play_bury, CardId.CALCIFY : play_calcify,
    CardId.CAPTURE_SPIRIT : play_capture_spirit, CardId.CLEANSE : play_cleanse, CardId.COUNTDOWN : play_countdown, CardId.DANSE_MACABRE : play_danse_macabre,
    CardId.DEATH_MARCH : play_death_march, CardId.DEATHBRINGER : play_deathbringer, CardId.DEATHS_DOOR : play_deaths_door, CardId.DEBILITATE : play_debilitate,
    CardId.DELAY : play_delay, CardId.DIRGE : play_dirge, CardId.DREDGE : play_dredge, CardId.ENFEEBLING_TOUCH : play_enfeebling_touch, CardId.FETCH : play_fetch,
    CardId.FRIENDSHIP : play_friendship, CardId.HAUNT : play_haunt, CardId.HIGH_FIVE : play_high_five, CardId.LETHALITY : play_lethality, CardId.MELANCHOLY : play_melancholy,
    CardId.NO_ESCAPE : play_no_escape, CardId.PAGESTORM : play_pagestorm, CardId.PARSE : play_parse, CardId.PULL_FROM_BELOW : play_pull_from_below, CardId.PUTREFY : play_putrefy,
    CardId.RATTLE : play_rattle, CardId.RIGHT_HAND_HAND : play_right_hand_hand, CardId.SEVERANCE : play_severance, CardId.SHROUD : play_shroud, CardId.SIC_EM : play_sic_em,
    CardId.SLEIGHT_OF_FLESH : play_sleight_of_flesh, CardId.SPUR : play_spur, CardId.VEILPIERCER : play_veilpiercer,
    CardId.BANSHEES_CRY : play_banshees_cry, CardId.CALL_OF_THE_VOID : play_call_of_the_void, CardId.DEMESNE : play_demesne, CardId.DEVOUR_LIFE : play_devour_life,
    CardId.EIDOLON : play_eidolon, CardId.END_OF_DAYS : play_end_of_days, CardId.ERADICATE : play_eradicate, CardId.HANG : play_hang, CardId.MISERY : play_misery,
    CardId.NECRO_MASTERY : play_necro_mastery, CardId.NEUROSURGE : play_neurosurge, CardId.OBLIVION : play_oblivion, CardId.REANIMATE : play_reanimate,
    CardId.REAPER_FORM : play_reaper_form, CardId.SACRIFICE : play_sacrifice, CardId.SEANCE : play_seance, CardId.SENTRY_MODE : play_sentry_mode,
    CardId.SHARED_FATE : play_shared_fate, CardId.SOUL_STORM : play_soul_storm, CardId.SPIRIT_OF_ASH : play_spirit_of_ash, CardId.SQUEEZE : play_squeeze,
    CardId.THE_SCYTHE : play_the_scythe, CardId.TIMES_UP : play_times_up, CardId.TRANSFIGURE : play_transfigure, CardId.UNDEATH : play_undeath,
    CardId.FORBIDDEN_GRIMOIRE : play_forbidden_grimoire, CardId.PROTECTOR : play_protector,
}
