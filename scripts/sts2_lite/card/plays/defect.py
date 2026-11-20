"""The Defect's cards (DefectCardPool). Orbs are channeled and evoked through orbs.py; the powers the cards apply are in defect.py."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import orbs, rng
from sts2_lite.defect import add_status_card, buff_claws, temp_focus
from sts2_lite.helpers import enemy_at, living_enemies
from sts2_lite.hooks import HookType
from sts2_lite.status import StatusId

from sts2_lite.card.card import Card
from sts2_lite.card.effects import PLAIN_DAMAGE, _attack, _gain_block, _vulnerable, _weak
from sts2_lite.card.ids import CardId, CardType
from sts2_lite.card.plays.silent import _hit_all

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator

def _damage(card : Card, is_upgraded : bool) -> int:
    return PLAIN_DAMAGE[card.card_id][is_upgraded]

def _player(combat : CombatSimulator):
    return combat.combat_state.player

def _hit(card : Card, combat : CombatSimulator, target_index : int, is_upgraded : bool):
    """The card's single hit on its target; returns the target."""
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    return target

def _channel(combat : CombatSimulator, kind : str, count : int = 1):
    orbs.channel(combat, kind, count)

def _intends_attack(enemy) -> bool:
    """Monster.IntendsToAttack."""
    if enemy.attack_damage > 0:
        return True
    moves = enemy.moves
    return bool(moves) and enemy.move_id in moves and "attack" in moves[enemy.move_id].intents

# ------------------------------------------------------------ Basic

def play_strike_defect(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit(card, combat, target_index, is_upgraded)

def play_defend_defect(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)

def play_zap(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _channel(combat, orbs.LIGHTNING)

def _evoke_front(combat : CombatSimulator, times : int):
    """The first orb is evoked `times` times and leaves the queue with the last one (Dualcast, Multi-Cast, Quadcast)."""
    for i in range(times):
        if combat.is_over:
            return
        orbs.evoke_next(combat, dequeue=i == times - 1)

def play_dualcast(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    if _player(combat).orbs:
        _evoke_front(combat, 2)

# ------------------------------------------------------------ Common

def play_ball_lightning(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit(card, combat, target_index, is_upgraded)
    _channel(combat, orbs.LIGHTNING)

def play_barrage(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """One hit for every orb."""
    target = enemy_at(combat, target_index)
    hits = len(_player(combat).orbs)
    if hits:
        _attack(combat, _damage(card, is_upgraded), target, hits)

def play_beam_cell(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _hit(card, combat, target_index, is_upgraded)
    if target.current_hp > 0:
        _vulnerable(combat, target, 2 if is_upgraded else 1)

def play_boost_away(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 9 if is_upgraded else 6)
    add_status_card(combat, CardId.DAZED)

def play_charge_battery(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 10 if is_upgraded else 7)
    _player(combat).apply_status(StatusId.ENERGY_NEXT_TURN, 1)

def play_claw(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """3 (4) plus what the Claws played so far have added; every Claw of the combat grows by 2 (3)."""
    _attack(combat, _damage(card, is_upgraded) + card.bonus_damage, enemy_at(combat, target_index))
    buff_claws(combat, 3 if is_upgraded else 2, card)

def play_cold_snap(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit(card, combat, target_index, is_upgraded)
    _channel(combat, orbs.FROST)

def play_compile_driver(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Draws a card for every kind of orb."""
    _hit(card, combat, target_index, is_upgraded)
    _player(combat).draw_cards(orbs.distinct_kinds(_player(combat)))

def play_coolheaded(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _channel(combat, orbs.FROST)
    _player(combat).draw_cards(2 if is_upgraded else 1)

def play_focused_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Temporary Focus."""
    _hit(card, combat, target_index, is_upgraded)
    temp_focus(combat, StatusId.FOCUSED_STRIKE, 2 if is_upgraded else 1, 1)

def play_go_for_the_eyes(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Weak, if the enemy is about to attack."""
    target = _hit(card, combat, target_index, is_upgraded)
    if target.current_hp > 0 and _intends_attack(target):
        _weak(combat, target, 2 if is_upgraded else 1)

def play_gunk_up(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index), 3)
    add_status_card(combat, CardId.SLIMED)

def play_hologram(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 5 if is_upgraded else 3)
    discard = _player(combat).discard_pile
    combat.request_choice("hologram", list(range(len(discard))), "discard", 1, card)

def play_hotfix(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    temp_focus(combat, StatusId.HOTFIX, 2, 1)

def play_leap(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 12 if is_upgraded else 9)

def play_lightning_rod(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 7 if is_upgraded else 4)
    _player(combat).apply_status(StatusId.LIGHTNING_ROD, 2)

def play_momentum_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Costs nothing for the rest of the combat once played (`card` is this play's own copy)."""
    _hit(card, combat, target_index, is_upgraded)
    card.energy_cost, card.restore_cost, card.until_played = 0, None, False

def play_sweeping_beam(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit_all(combat, _damage(card, is_upgraded))
    _player(combat).draw_cards(1)

def play_turbo(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_energy(3 if is_upgraded else 2)
    add_status_card(combat, CardId.VOID)

def play_uproar(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Two hits, then a random Attack of the draw pile (a playable one if there is one) is played for free."""
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index), 2)
    combat.resolve_deaths()
    attacks = [c for c in _player(combat).draw_pile if c.type is CardType.Attack]
    playable = [c for c in attacks if not c.unplayable and not c.is_unplayable]
    pool = playable or attacks
    if pool and not combat.is_over:
        combat.auto_play(rng.choice(pool))

# ------------------------------------------------------------ Uncommon

def play_boot_sequence(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 13 if is_upgraded else 10)

def play_bulk_up(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = _player(combat)
    orbs.remove_slots(player, 1)
    player.apply_status(StatusId.STRENGTH, 3 if is_upgraded else 2)
    player.apply_status(StatusId.DEXTERITY, 3 if is_upgraded else 2)

def play_capacitor(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    orbs.add_slots(_player(combat), 3 if is_upgraded else 2)

def play_chaos(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    orbs.channel_random(combat, 2 if is_upgraded else 1)

def play_chill(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _channel(combat, orbs.FROST)

def play_compact(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Block, and every Status of the hand turns into a Fuel."""
    player = _player(combat)
    _gain_block(combat, 7 if is_upgraded else 6)
    for i, c in enumerate(player.hand):
        if c.type is CardType.Status:
            player.hand[i] = Card.create_generated(CardId.FUEL, is_upgraded)

def play_darkness(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """A Dark orb, then every Dark orb's Passive (twice upgraded)."""
    player = _player(combat)
    _channel(combat, orbs.DARK)
    for orb in [o for o in player.orbs if o.kind == orbs.DARK]:
        for _ in range(2 if is_upgraded else 1):
            if orb in player.orbs:
                orbs.passive(combat, orb)

def play_double_energy(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_energy(combat.combat_state.energy)

def play_feral(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.FERAL, 1)

def play_fight_through(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 17 if is_upgraded else 13)
    add_status_card(combat, CardId.WOUND)
    add_status_card(combat, CardId.WOUND)

def play_ftl(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Draws a card while fewer than 3 (4) cards were played this turn before it."""
    _hit(card, combat, target_index, is_upgraded)
    player = _player(combat)
    played_before = player.series_this_turn         # the plays of this turn that finished (this one counts after its effects)
    if played_before < (4 if is_upgraded else 3):
        player.draw_cards(1)

def play_fusion(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _channel(combat, orbs.PLASMA)

def play_glacier(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 9 if is_upgraded else 6)
    _channel(combat, orbs.FROST, 2)

def play_glasswork(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)
    _channel(combat, orbs.GLASS)

def play_hailstorm(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.HAILSTORM, 8 if is_upgraded else 6)

def play_iteration(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.ITERATION, 3 if is_upgraded else 2)

def play_loop(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.LOOP, 2 if is_upgraded else 1)

def play_null(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = _hit(card, combat, target_index, is_upgraded)
    if target.current_hp > 0:
        _weak(combat, target, 2 if is_upgraded else 1)
    _channel(combat, orbs.DARK)

def play_overclock(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).draw_cards(3 if is_upgraded else 2)
    add_status_card(combat, CardId.BURN)

def play_rainbow(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for kind in (orbs.LIGHTNING, orbs.FROST, orbs.DARK):
        _channel(combat, kind)

def play_refract(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index), 2)
    _channel(combat, orbs.GLASS, 2)

def play_rocket_punch(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit(card, combat, target_index, is_upgraded)
    _player(combat).draw_cards(2 if is_upgraded else 1)

def play_scavenge(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Exhausts a card of the hand; Energy next turn."""
    player = _player(combat)
    player.apply_status(StatusId.ENERGY_NEXT_TURN, 3 if is_upgraded else 2)
    combat.request_choice("exhaust", list(range(len(player.hand))), "hand", 0, card)

def play_scrape(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Draws cards and discards the ones that cost Energy."""
    player = _player(combat)
    _hit(card, combat, target_index, is_upgraded)
    before = list(player.hand)
    player.draw_cards(5 if is_upgraded else 4)
    drawn = [c for c in player.hand if not any(c is b for b in before)]
    costly = [c for c in drawn if c.energy_cost == "X" or c.current_cost(player) != 0]
    if costly:
        combat.discard_cards(costly)

def play_shadow_shield(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 15 if is_upgraded else 11)
    _channel(combat, orbs.DARK)

def play_skim(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).draw_cards(4 if is_upgraded else 3)

def play_smokestack(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.SMOKESTACK, 7 if is_upgraded else 5)

def play_storm(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.STORM, 2 if is_upgraded else 1)

def play_subroutine(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.SUBROUTINE, 1)

def play_sunder(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Energy if the Attack kills."""
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    if target.current_hp <= 0:
        combat.gain_energy(3)

def play_synchronize(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Temporary Focus for every kind of orb."""
    amount = orbs.distinct_kinds(_player(combat)) * (2 if is_upgraded else 1)
    if amount > 0:
        temp_focus(combat, StatusId.SYNCHRONIZE, amount, 1)

def play_synthesis(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit(card, combat, target_index, is_upgraded)
    _player(combat).apply_status(StatusId.FREE_POWER, 1)

def play_tempest(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    _channel(combat, orbs.LIGHTNING, x + (1 if is_upgraded else 0))

def play_tesla_coil(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Every Lightning orb's Passive fires at the target."""
    target = _hit(card, combat, target_index, is_upgraded)
    player = _player(combat)
    for orb in [o for o in player.orbs if o.kind == orbs.LIGHTNING]:
        for _ in range(2 if is_upgraded else 1):
            orbs.passive(combat, orb, target)

def play_thunder(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.THUNDER, 11 if is_upgraded else 8)

def play_white_noise(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """A random Power of the pool joins the hand for free this turn."""
    from sts2_lite.card.tables import combat_pool
    pool = combat_pool("DEFECT", CardType.Power)
    if pool:
        _player(combat).add_to_hand(Card.create_generated(rng.choice(pool)).free_this_turn())

# ------------------------------------------------------------ Rare

def play_adaptive_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """A free copy joins the discard pile."""
    _hit(card, combat, target_index, is_upgraded)
    player = _player(combat)
    clone = card.free_this_combat()
    clone = Card.create_copy(clone) if clone is card else clone
    clone.generated = True
    player.discard_pile.append(clone)
    player.cards_generated += 1

def play_all_for_one(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Every free Attack, Skill and Power of the discard pile returns to the hand."""
    player = _player(combat)
    _hit(card, combat, target_index, is_upgraded)
    for c in [c for c in player.discard_pile if c.energy_cost != "X" and c.type in (CardType.Attack, CardType.Skill, CardType.Power) and c.current_cost(player) == 0]:
        if len(player.hand) >= 10:
            break
        player.discard_pile.remove(c)
        player.hand.append(c)

def play_biased_cognition(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = _player(combat)
    player.apply_status(StatusId.FOCUS, 6 if is_upgraded else 5)
    player.apply_status(StatusId.BIASED_COGNITION, 1)

def play_buffer(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.BUFFER, 2 if is_upgraded else 1)

def play_consuming_shadow(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _channel(combat, orbs.DARK, 3 if is_upgraded else 2)
    _player(combat).apply_status(StatusId.CONSUMING_SHADOW, 1)

def play_coolant(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.COOLANT, 3 if is_upgraded else 2)

def play_creative_ai(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.CREATIVE_AI, 1)

def play_defragment(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.FOCUS, 2 if is_upgraded else 1)

def play_echo_form(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.ECHO_FORM, 1)

def play_flak_cannon(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Exhausts every Status of the hand and piles (the exhaust pile's stay), then one hit on a random enemy for each."""
    player = _player(combat)
    statuses = [c for pile in (player.hand, player.draw_pile, player.discard_pile) for c in pile if c.type is CardType.Status]
    for c in statuses:
        player.exhaust_card(c)
        combat.fire(HookType.CARD_EXHAUSTED, c)
    damage = _damage(card, is_upgraded)
    for _ in range(len(statuses)):
        living = living_enemies(combat)
        if not living:
            break
        _attack(combat, damage, rng.pick_target(living))

def play_fuel(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_energy(2 if is_upgraded else 1)

def play_genetic_algorithm(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """1 Block plus what it has grown by; each play adds 3 (4), which the deck's version keeps (`card` is this play's own copy)."""
    _gain_block(combat, 1 + card.bonus_damage)
    card.bonus_damage += 4 if is_upgraded else 3
    if card.deck_index is not None:
        _player(combat).deck_buffs[card.deck_index] = card.bonus_damage

def play_helix_drill(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """One hit for every Energy spent this turn (not counting this card)."""
    target = enemy_at(combat, target_index)
    hits = _player(combat).energy_spent_this_turn
    if hits > 0:
        _attack(combat, _damage(card, is_upgraded), target, hits)

def play_hyperbeam(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Every enemy; 3 Focus lost until the end of the turn."""
    _hit_all(combat, _damage(card, is_upgraded))
    player = _player(combat)
    before = player.status_amount(StatusId.HYPERBEAM_FOCUS_DOWN)
    player.apply_status(StatusId.HYPERBEAM_FOCUS_DOWN, 3)
    if player.status_amount(StatusId.HYPERBEAM_FOCUS_DOWN) != before:
        player.apply_status(StatusId.FOCUS, -3, bypass_artifact=True)

def play_ice_lance(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit(card, combat, target_index, is_upgraded)
    _channel(combat, orbs.FROST, 3)

def play_machine_learning(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.MACHINE_LEARNING, 1)

def play_meteor_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit(card, combat, target_index, is_upgraded)
    _channel(combat, orbs.PLASMA, 3)

def play_modded(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """A slot, cards, and the card costs 1 more for the rest of the combat (`card` is this play's own copy)."""
    player = _player(combat)
    orbs.add_slots(player, 1)
    player.draw_cards(2 if is_upgraded else 1)
    if card.energy_cost != "X":
        card.energy_cost += 1
        card.restore_cost, card.until_played = None, False

def play_multi_cast(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    if _player(combat).orbs:
        _evoke_front(combat, x + (1 if is_upgraded else 0))

def play_quadcast(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    if _player(combat).orbs:
        _evoke_front(combat, 4)

def play_reboot(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """The hand and the discard pile are shuffled into the draw pile, then cards are drawn."""
    player = _player(combat)
    player.draw_pile.extend(player.hand)
    player.hand.clear()
    player.known_top = 0
    if player.discard_pile:
        player.shuffle_discard_into_draw()
    else:
        player.shuffle_draw_pile()
    player.draw_cards(6 if is_upgraded else 4)

def play_shatter(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Every enemy, then the first orb is evoked once for each orb held and once more as it leaves."""
    _hit_all(combat, _damage(card, is_upgraded))
    player = _player(combat)
    count = len(player.orbs)
    for _ in range(count):
        if combat.is_over:
            return
        orbs.evoke_next(combat, dequeue=False)
    orbs.evoke_next(combat)

def play_signal_boost(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.SIGNAL_BOOST, 1)

def play_spinner(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    if is_upgraded:
        _channel(combat, orbs.GLASS)
    _player(combat).apply_status(StatusId.SPINNER, 1)

def play_supercritical(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_energy(6 if is_upgraded else 4)

def play_trash_to_treasure(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _player(combat).apply_status(StatusId.TRASH_TO_TREASURE, 1)

def play_voltaic(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """A Lightning orb for every Lightning orb channeled this combat."""
    _channel(combat, orbs.LIGHTNING, _player(combat).lightning_channeled)

DEFECT_PLAYS = {
    CardId.ADAPTIVE_STRIKE : play_adaptive_strike, CardId.ALL_FOR_ONE : play_all_for_one, CardId.BALL_LIGHTNING : play_ball_lightning, CardId.BARRAGE : play_barrage,
    CardId.BEAM_CELL : play_beam_cell, CardId.BIASED_COGNITION : play_biased_cognition, CardId.BOOST_AWAY : play_boost_away, CardId.BOOT_SEQUENCE : play_boot_sequence,
    CardId.BUFFER : play_buffer, CardId.BULK_UP : play_bulk_up, CardId.CAPACITOR : play_capacitor, CardId.CHAOS : play_chaos, CardId.CHARGE_BATTERY : play_charge_battery,
    CardId.CHILL : play_chill, CardId.CLAW : play_claw, CardId.COLD_SNAP : play_cold_snap, CardId.COMPACT : play_compact, CardId.COMPILE_DRIVER : play_compile_driver,
    CardId.CONSUMING_SHADOW : play_consuming_shadow, CardId.COOLANT : play_coolant, CardId.COOLHEADED : play_coolheaded, CardId.CREATIVE_AI : play_creative_ai,
    CardId.DARKNESS : play_darkness, CardId.DEFEND_DEFECT : play_defend_defect, CardId.DEFRAGMENT : play_defragment, CardId.DOUBLE_ENERGY : play_double_energy,
    CardId.DUALCAST : play_dualcast, CardId.ECHO_FORM : play_echo_form, CardId.FERAL : play_feral, CardId.FIGHT_THROUGH : play_fight_through,
    CardId.FLAK_CANNON : play_flak_cannon, CardId.FOCUSED_STRIKE : play_focused_strike, CardId.FTL : play_ftl, CardId.FUEL : play_fuel, CardId.FUSION : play_fusion,
    CardId.GENETIC_ALGORITHM : play_genetic_algorithm, CardId.GLACIER : play_glacier, CardId.GLASSWORK : play_glasswork, CardId.GO_FOR_THE_EYES : play_go_for_the_eyes,
    CardId.GUNK_UP : play_gunk_up, CardId.HAILSTORM : play_hailstorm, CardId.HELIX_DRILL : play_helix_drill, CardId.HOLOGRAM : play_hologram, CardId.HOTFIX : play_hotfix,
    CardId.HYPERBEAM : play_hyperbeam, CardId.ICE_LANCE : play_ice_lance, CardId.ITERATION : play_iteration, CardId.LEAP : play_leap,
    CardId.LIGHTNING_ROD : play_lightning_rod, CardId.LOOP : play_loop, CardId.MACHINE_LEARNING : play_machine_learning, CardId.METEOR_STRIKE : play_meteor_strike,
    CardId.MODDED : play_modded, CardId.MOMENTUM_STRIKE : play_momentum_strike, CardId.MULTI_CAST : play_multi_cast, CardId.NULL : play_null, CardId.OVERCLOCK : play_overclock,
    CardId.QUADCAST : play_quadcast, CardId.RAINBOW : play_rainbow, CardId.REBOOT : play_reboot, CardId.REFRACT : play_refract, CardId.ROCKET_PUNCH : play_rocket_punch,
    CardId.SCAVENGE : play_scavenge, CardId.SCRAPE : play_scrape, CardId.SHADOW_SHIELD : play_shadow_shield, CardId.SHATTER : play_shatter,
    CardId.SIGNAL_BOOST : play_signal_boost, CardId.SKIM : play_skim, CardId.SMOKESTACK : play_smokestack, CardId.SPINNER : play_spinner, CardId.STORM : play_storm,
    CardId.STRIKE_DEFECT : play_strike_defect, CardId.SUBROUTINE : play_subroutine, CardId.SUNDER : play_sunder, CardId.SUPERCRITICAL : play_supercritical,
    CardId.SWEEPING_BEAM : play_sweeping_beam, CardId.SYNCHRONIZE : play_synchronize, CardId.SYNTHESIS : play_synthesis, CardId.TEMPEST : play_tempest,
    CardId.TESLA_COIL : play_tesla_coil, CardId.THUNDER : play_thunder, CardId.TRASH_TO_TREASURE : play_trash_to_treasure, CardId.TURBO : play_turbo,
    CardId.UPROAR : play_uproar, CardId.VOLTAIC : play_voltaic, CardId.WHITE_NOISE : play_white_noise, CardId.ZAP : play_zap,
}
