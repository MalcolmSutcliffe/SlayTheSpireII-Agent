from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.hooks import HookType
from sts2_lite.helpers import enemy_at, living_enemies
from sts2_lite.relic import RelicId, debuff_multiplier
from sts2_lite.status import StatusId

from sts2_lite.card.card import Card
from sts2_lite.card.constants import NEOWS_FURY_CARDS
from sts2_lite.card.effects import PLAIN_DAMAGE, _attack, _gain_block, _printed_damage, _strikes, _vulnerable, temp_strength
from sts2_lite.card.ids import CardId, CardType
from sts2_lite.card.tables import INFERNAL_BLADE_POOL, STOKE_POOL

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator
    from sts2_lite.creature import Creature

def play_aggression(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.AGGRESSION, 1)

def play_anger(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    combat.combat_state.player.discard_pile.append(Card.create_copy(card))
    _attack(combat, 8 if is_upgraded else 6, target)

def play_armaments(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 5)
    player = combat.combat_state.player
    upgradable = [i for i, c in enumerate(player.hand) if c.is_upgradable]
    if is_upgraded:
        for i in upgradable:
            player.upgrade_card(player.hand[i])
    else:
        combat.request_choice("upgrade", upgradable)

def play_ashen_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    per_exhausted = 4 if is_upgraded else 3
    _attack(combat, 6 + per_exhausted * len(combat.combat_state.player.exhaust_pile), target)

def play_barricade(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if StatusId.BARRICADE not in player.status:
        player.apply_status(StatusId.BARRICADE, 1)

def play_bash(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 10 if is_upgraded else 8, target)
    _vulnerable(combat, target, 3 if is_upgraded else 2)

def play_battle_trance(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.draw_cards(4 if is_upgraded else 3)
    if StatusId.NO_DRAW not in player.status:       # it does not stack
        player.apply_status(StatusId.NO_DRAW, 1)

def play_blood_wall(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 20 if is_upgraded else 16)
    combat.combat_state.player.lose_hp(2)

def play_bloodletting(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.lose_hp(3)
    combat.gain_energy(3 if is_upgraded else 2)

def play_bludgeon(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 42 if is_upgraded else 32, target)

def play_body_slam(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, combat.combat_state.player.block, target)

def play_brand(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.lose_hp(1)
    if player.current_hp > 0:
        player.apply_status(StatusId.STRENGTH, 2 if is_upgraded else 1)     # before the pick; same result
        combat.request_choice("exhaust", list(range(len(player.hand))))

def play_break(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 30 if is_upgraded else 20, target)
    _vulnerable(combat, target, 7 if is_upgraded else 5)

def _lose_hp_first(combat : CombatSimulator, amount : int):
    """HP lost before the card's damage: Red Skull (at half HP) acts before the hit, not after the card."""
    combat.combat_state.player.lose_hp(amount)
    combat._sync_hp()

def play_breakthrough(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _lose_hp_first(combat, 1)
    for target in list(combat.combat_state.enemies):
        _attack(combat, 13 if is_upgraded else 9, target)

def play_bully(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    per_vulnerable = 3 if is_upgraded else 2
    _attack(combat, 4 + per_vulnerable * target.status_amount(StatusId.VULNERABLE), target)

def play_burning_pact(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    hand = combat.combat_state.player.hand
    combat.request_choice("exhaust", list(range(len(hand))), amount=3 if is_upgraded else 2)

def play_cascade(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    combat.auto_play_from_top(x + (1 if is_upgraded else 0))

def play_cinder(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 24 if is_upgraded else 18, target)
    hand = combat.combat_state.player.hand
    if hand:
        victim = hand[0] if len(hand) == 1 else rng.choice(hand)
        combat.combat_state.player.exhaust_card(victim)
        combat.fire(HookType.CARD_EXHAUSTED, victim)

def play_colossus(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)
    combat.combat_state.player.apply_status(StatusId.COLOSSUS, 1)

def play_conflagration(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in living_enemies(combat):
        _attack(combat, 2, target, 5 if is_upgraded else 4)

def play_corruption(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if StatusId.CORRUPTION not in player.status:
        player.apply_status(StatusId.CORRUPTION, 1)

def play_crimson_mantle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.apply_status(StatusId.CRIMSON_MANTLE, 10 if is_upgraded else 8)
    player.crimson_mantle_plays += 1        # self-damage per turn (CrimsonMantlePower.IncrementSelfDamage)

def play_cruelty(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.CRUELTY, 50 if is_upgraded else 25)

def play_dark_embrace(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.DARK_EMBRACE, 1)

def play_defend(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)

def play_demon_form(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.DEMON_FORM, 3 if is_upgraded else 2)

def play_dismantle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    hits = 2 if StatusId.VULNERABLE in target.status else 1
    _attack(combat, 10 if is_upgraded else 8, target, hits)

def play_dominate(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _vulnerable(combat, target, 2 if is_upgraded else 1)
    combat.combat_state.player.apply_status(StatusId.STRENGTH, target.status_amount(StatusId.VULNERABLE))

def play_drum_of_battle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.draw_cards(2)        # the energy comes when the card is exhausted

def play_evil_eye(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    gains = 2 if combat.combat_state.player.cards_exhausted_this_turn > 0 else 1
    for _ in range(gains):
        _gain_block(combat, 11 if is_upgraded else 8)

def play_expect_a_fight(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    combat.gain_energy(sum(1 for c in player.hand if c.type == CardType.Attack))
    player.apply_status(StatusId.NO_ENERGY_GAIN, 1)

def play_feed(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 12 if is_upgraded else 10, target)
    if target.current_hp <= 0 and StatusId.MINION not in target.status:
        gain = 4 if is_upgraded else 3
        player = combat.combat_state.player
        player.max_hp += gain
        player.current_hp += gain

def play_feel_no_pain(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.FEEL_NO_PAIN, 4 if is_upgraded else 3)

def play_fiend_fire(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    player = combat.combat_state.player
    exhausted = list(player.hand)
    for victim in exhausted:
        player.exhaust_card(victim)
        combat.fire(HookType.CARD_EXHAUSTED, victim)
    if exhausted:
        _attack(combat, 10 if is_upgraded else 7, target, len(exhausted))

def play_fight_me(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 6 if is_upgraded else 5, target, 2)
    combat.combat_state.player.apply_status(StatusId.STRENGTH, 4 if is_upgraded else 3)
    target.apply_status(StatusId.STRENGTH, 1)

def play_flame_barrier(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 16 if is_upgraded else 12)
    combat.combat_state.player.apply_status(StatusId.FLAME_BARRIER, 6 if is_upgraded else 4)

def play_forgotten_ritual(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    if combat.combat_state.player.cards_exhausted_this_turn > 0:
        combat.gain_energy(4 if is_upgraded else 3)

def play_havoc(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if not player.draw_pile:
        player.shuffle_discard_into_draw()
    if not player.draw_pile:
        return
    top = player.draw_pile[-1]
    if player.known_top == 0:
        player.unknown_draws += 1   # the top card is unknown to the agent, so this is a chance event
    if top.unplayable:                          # CardCmd.AutoPlay skips only Unplayable
        player.exhaust_card(top)
        combat.fire(HookType.CARD_EXHAUSTED, top)
    else:
        combat.auto_play(top, force_exhaust=True)

def play_headbutt(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 12 if is_upgraded else 9, target)
    combat.resolve_deaths()     # a kill's effects (Gremlin Horn's draw) come before the pick, which may then see another discard pile
    combat.request_choice("to_draw_pile", list(range(len(combat.combat_state.player.discard_pile))), pile="discard")

def play_neows_fury(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
    combat.resolve_deaths()
    player = combat.combat_state.player
    discard = player.discard_pile
    combat.request_choice("to_hand", list(range(len(discard))), pile="discard", amount=NEOWS_FURY_CARDS[is_upgraded], source=card)

def play_hellraiser(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if StatusId.HELLRAISER not in player.status:
        player.apply_status(StatusId.HELLRAISER, 1)

def play_hemokinesis(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _lose_hp_first(combat, 2)
    _attack(combat, 20 if is_upgraded else 15, target)

def play_howl_from_beyond(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in living_enemies(combat):
        _attack(combat, 21 if is_upgraded else 16, target)

def play_impervious(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 40 if is_upgraded else 30)

def play_infernal_blade(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    new_card = Card.create_generated(rng.choice(INFERNAL_BLADE_POOL)).free_this_turn()     # Whirlwind stays X
    combat.combat_state.player.add_to_hand(new_card)

def play_inferno(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.apply_status(StatusId.INFERNO, 9 if is_upgraded else 6)
    player.inferno_plays += 1

def play_inflame(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.STRENGTH, 3 if is_upgraded else 2)

def play_iron_wave(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _gain_block(combat, 7 if is_upgraded else 5)
    _attack(combat, 7 if is_upgraded else 5, target)

def play_juggernaut(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.JUGGERNAUT, 8 if is_upgraded else 6)

def play_juggling(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.JUGGLING, 1)

def play_mangle(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 20 if is_upgraded else 15, target)
    temp_strength(target, StatusId.MANGLE, 15 if is_upgraded else 10, -1, combat)

def play_molten_fist(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 14 if is_upgraded else 10, target)
    vulnerable = target.status_amount(StatusId.VULNERABLE)
    if target.current_hp > 0 and vulnerable > 0:
        _vulnerable(combat, target, vulnerable)

def play_not_yet(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.current_hp = min(player.max_hp, player.current_hp + (13 if is_upgraded else 10))

def play_offering(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.lose_hp(6)
    if player.current_hp > 0:
        combat.gain_energy(2)
        player.draw_cards(5 if is_upgraded else 3)

def play_one_two_punch(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.ONE_TWO_PUNCH, 2 if is_upgraded else 1)

def play_pacts_end(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    if len(combat.combat_state.player.exhaust_pile) >= 3:
        for target in living_enemies(combat):
            _attack(combat, 23 if is_upgraded else 17, target)

def play_perfected_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    strikes = _strikes(combat.combat_state.player, card)
    _attack(combat, 6 + (3 if is_upgraded else 2) * strikes, target)

def play_pillage(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 9 if is_upgraded else 6, target)
    player = combat.combat_state.player
    while True:                 # draw until something that is not an Attack comes up, or the hand is full
        drawn = player.draw_card()
        if drawn is None or drawn.type != CardType.Attack or len(player.hand) >= 10:
            break

def play_pommel_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 10 if is_upgraded else 9, target)
    combat.combat_state.player.draw_cards(2 if is_upgraded else 1)

def play_primal_force(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    hand = combat.combat_state.player.hand
    for i, c in enumerate(hand):
        if c.type == CardType.Attack:
            hand[i] = Card.create_generated(CardId.GIANT_ROCK, is_upgraded)

def play_pyre(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    energy = 2 if is_upgraded else 1
    combat.combat_state.player.apply_status(StatusId.PYRE, energy)
    combat.combat_state.max_energy += energy

def play_rage(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.RAGE, 5 if is_upgraded else 3)

def play_rampage(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # `card` is this play's own copy (see CombatSimulator.private_copy), so it can remember the growth
    target = enemy_at(combat, target_index)
    _attack(combat, 9 + card.bonus_damage, target)
    card.bonus_damage += 9 if is_upgraded else 5

def play_rupture(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.RUPTURE, 2 if is_upgraded else 1)

def play_second_wind(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    for victim in [c for c in player.hand if c.type != CardType.Attack]:
        player.exhaust_card(victim)
        combat.fire(HookType.CARD_EXHAUSTED, victim)
        _gain_block(combat, 7 if is_upgraded else 5)

def play_setup_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 9 if is_upgraded else 7, target)
    temp_strength(combat.combat_state.player, StatusId.SETUP_STRIKE, 3 if is_upgraded else 2, 1)

def play_shrug_it_off(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 11 if is_upgraded else 8)
    combat.combat_state.player.draw_cards(1)

def play_spite(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    repeat = 3 if is_upgraded else 2
    _attack(combat, 5, target, repeat if combat.combat_state.player.lost_hp_this_turn else 1)

def play_stampede(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.STAMPEDE, 1)

def play_stoke(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    exhausted = list(player.hand)
    for victim in exhausted:
        player.exhaust_card(victim)
        combat.fire(HookType.CARD_EXHAUSTED, victim)
    for _ in exhausted:         # a random card (repeats allowed) for each one exhausted
        new_card = Card.create_generated(rng.choice(STOKE_POOL), is_upgraded)
        if new_card.type == CardType.Power and RelicId.SPIKED_GAUNTLETS in player.relics:
            new_card.energy_cost += 1       # the bridge shows Spiked Gauntlets' +1; a card made here has to add it
        player.add_to_hand(new_card)

def play_stomp(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in living_enemies(combat):
        _attack(combat, 15 if is_upgraded else 12, target)

def play_stone_armor(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.PLATING, 6 if is_upgraded else 4)

def play_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 9 if is_upgraded else 6, target)

def play_sword_boomerang(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for _ in range(4 if is_upgraded else 3):
        living = living_enemies(combat)
        if not living:
            break
        target = rng.pick_target(living)
        _attack(combat, 3, target)
        combat.resolve_deaths()

def play_taunt(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _gain_block(combat, 8 if is_upgraded else 7)
    _vulnerable(combat, target, 2 if is_upgraded else 1)

def play_tear_asunder(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    # one hit, and one more for every time the player has lost HP in this fight
    _attack(combat, 7 if is_upgraded else 5, target, 1 + combat.combat_state.player.hp_loss_events)

def play_thrash(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # `card` is this play's own copy (see CombatSimulator.private_copy), so it can remember the growth
    target = enemy_at(combat, target_index)
    player = combat.combat_state.player
    _attack(combat, (6 if is_upgraded else 4) + card.bonus_damage, target, 2)
    attacks = [c for c in player.hand if c.type == CardType.Attack]
    if attacks:
        victim = attacks[0] if len(attacks) == 1 else rng.choice(attacks)
        from sts2_lite.creature import Creature      # card.py is imported by creature.py's package
        from sts2_lite.damage import modify_damage
        # relics read the victim, not Thrash (Thrash.OnPlay)
        card.bonus_damage += modify_damage(_printed_damage(victim, combat), player, Creature(), victim, in_play=False)
        player.exhaust_card(victim)
        combat.fire(HookType.CARD_EXHAUSTED, victim)

def play_thunderclap(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in list(combat.combat_state.enemies):
        _attack(combat, 7 if is_upgraded else 4, target)
        _vulnerable(combat, target, 1)

def play_tremble(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _vulnerable(combat, target, 4 if is_upgraded else 3)

def play_true_grit(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 9 if is_upgraded else 7)
    player = combat.combat_state.player
    hand = player.hand
    if is_upgraded:
        combat.request_choice("exhaust", list(range(len(hand))))
    elif hand:
        victim = hand[0] if len(hand) == 1 else rng.choice(hand)
        player.exhaust_card(victim)
        combat.fire(HookType.CARD_EXHAUSTED, victim)

def play_twin_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 7 if is_upgraded else 5, target, 2)

def play_unmovable(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.UNMOVABLE, 1)

def play_unrelenting(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 20 if is_upgraded else 14, target)
    combat.combat_state.player.apply_status(StatusId.FREE_ATTACK, 1)

def play_uppercut(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 13, target)
    debuff = 2 if is_upgraded else 1
    player = combat.combat_state.player
    target.apply_status(StatusId.WEAK, debuff * debuff_multiplier(player, combat.card_in_play, target) if player.relics else debuff)
    _vulnerable(combat, target, debuff)

def play_vicious(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.VICIOUS, 2 if is_upgraded else 1)

def play_whirlwind(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    for _ in range(x):
        for target in living_enemies(combat):
            _attack(combat, 8 if is_upgraded else 5, target)
        combat.resolve_deaths()


IRONCLAD_PLAYS = {
    CardId.AGGRESSION : play_aggression,
    CardId.ANGER : play_anger,
    CardId.ARMAMENTS : play_armaments,
    CardId.ASHEN_STRIKE : play_ashen_strike,
    CardId.BARRICADE : play_barricade,
    CardId.BASH : play_bash,
    CardId.BATTLE_TRANCE : play_battle_trance,
    CardId.BLOODLETTING : play_bloodletting,
    CardId.BLOOD_WALL : play_blood_wall,
    CardId.BLUDGEON : play_bludgeon,
    CardId.BODY_SLAM : play_body_slam,
    CardId.BRAND : play_brand,
    CardId.BREAK : play_break,
    CardId.BREAKTHROUGH : play_breakthrough,
    CardId.BULLY : play_bully,
    CardId.BURNING_PACT : play_burning_pact,
    CardId.CASCADE : play_cascade,
    CardId.CINDER : play_cinder,
    CardId.COLOSSUS : play_colossus,
    CardId.CONFLAGRATION : play_conflagration,
    CardId.CORRUPTION : play_corruption,
    CardId.CRIMSON_MANTLE : play_crimson_mantle,
    CardId.CRUELTY : play_cruelty,
    CardId.DARK_EMBRACE : play_dark_embrace,
    CardId.DEFEND_IRONCLAD : play_defend,
    CardId.DEMON_FORM : play_demon_form,
    CardId.DISMANTLE : play_dismantle,
    CardId.DOMINATE : play_dominate,
    CardId.DRUM_OF_BATTLE : play_drum_of_battle,
    CardId.EVIL_EYE : play_evil_eye,
    CardId.EXPECT_A_FIGHT : play_expect_a_fight,
    CardId.FEED : play_feed,
    CardId.FEEL_NO_PAIN : play_feel_no_pain,
    CardId.FIEND_FIRE : play_fiend_fire,
    CardId.FIGHT_ME : play_fight_me,
    CardId.FLAME_BARRIER : play_flame_barrier,
    CardId.FORGOTTEN_RITUAL : play_forgotten_ritual,
    CardId.HAVOC : play_havoc,
    CardId.HEADBUTT : play_headbutt,
    CardId.HELLRAISER : play_hellraiser,
    CardId.HEMOKINESIS : play_hemokinesis,
    CardId.HOWL_FROM_BEYOND : play_howl_from_beyond,
    CardId.IMPERVIOUS : play_impervious,
    CardId.INFERNAL_BLADE : play_infernal_blade,
    CardId.INFERNO : play_inferno,
    CardId.INFLAME : play_inflame,
    CardId.IRON_WAVE : play_iron_wave,
    CardId.JUGGERNAUT : play_juggernaut,
    CardId.JUGGLING : play_juggling,
    CardId.MANGLE : play_mangle,
    CardId.MOLTEN_FIST : play_molten_fist,
    CardId.NEOWS_FURY : play_neows_fury,
    CardId.NOT_YET : play_not_yet,
    CardId.OFFERING : play_offering,
    CardId.ONE_TWO_PUNCH : play_one_two_punch,
    CardId.PACTS_END : play_pacts_end,
    CardId.PERFECTED_STRIKE : play_perfected_strike,
    CardId.PILLAGE : play_pillage,
    CardId.POMMEL_STRIKE : play_pommel_strike,
    CardId.PRIMAL_FORCE : play_primal_force,
    CardId.PYRE : play_pyre,
    CardId.RAGE : play_rage,
    CardId.RAMPAGE : play_rampage,
    CardId.RUPTURE : play_rupture,
    CardId.SECOND_WIND : play_second_wind,
    CardId.SETUP_STRIKE : play_setup_strike,
    CardId.SHRUG_IT_OFF : play_shrug_it_off,
    CardId.SPITE : play_spite,
    CardId.STAMPEDE : play_stampede,
    CardId.STOKE : play_stoke,
    CardId.STOMP : play_stomp,
    CardId.STONE_ARMOR : play_stone_armor,
    CardId.STRIKE_IRONCLAD : play_strike,
    CardId.SWORD_BOOMERANG : play_sword_boomerang,
    CardId.TAUNT : play_taunt,
    CardId.TEAR_ASUNDER : play_tear_asunder,
    CardId.THRASH : play_thrash,
    CardId.THUNDERCLAP : play_thunderclap,
    CardId.TREMBLE : play_tremble,
    CardId.TRUE_GRIT : play_true_grit,
    CardId.TWIN_STRIKE : play_twin_strike,
    CardId.UNMOVABLE : play_unmovable,
    CardId.UNRELENTING : play_unrelenting,
    CardId.UPPERCUT : play_uppercut,
    CardId.VICIOUS : play_vicious,
    CardId.WHIRLWIND : play_whirlwind,
}
