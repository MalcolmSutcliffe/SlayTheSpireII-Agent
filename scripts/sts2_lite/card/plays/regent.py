"""The Regent's cards (RegentCardPool). Stars are spent by the play itself (Card.play_card -> CombatSimulator.spend_stars) before the effect runs."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite.helpers import enemy_at, living_enemies
from sts2_lite.status import StatusId

from sts2_lite.card.card import Card
from sts2_lite.card.effects import PLAIN_DAMAGE, _attack, _debuff, _gain_block, _vulnerable, _weak, apply_fresh, crescent_spear_damage, temp_strength
from sts2_lite.card.ids import CardId, CardType
from sts2_lite.card.tables import COLORLESS_CARDS
from sts2_lite.card.plays.silent import _hit_all

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator


def _damage(card : Card, is_upgraded : bool) -> int:
    return PLAIN_DAMAGE[card.card_id][is_upgraded]

# ------------------------------------------------------------ Basic

def play_strike_regent(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_defend_regent(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)

def play_falling_star(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    if target.current_hp > 0:
        _weak(combat, target, 1)
        _vulnerable(combat, target, 1)

def play_venerate(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_stars(3 if is_upgraded else 2)

# ------------------------------------------------------------ Token

def play_sovereign_blade(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """10 damage plus everything Forge has added (SeekingEdge hits every enemy, Parry adds Block: later)."""
    if StatusId.SEEKING_EDGE in combat.combat_state.player.status:
        _hit_all(combat, 10 + card.bonus_damage)         # SeekingEdgePower: the Blade hits every enemy
    else:
        _attack(combat, 10 + card.bonus_damage, enemy_at(combat, target_index))
    parry = combat.combat_state.player.status_amount(StatusId.PARRY)
    if parry > 0:
        _gain_block(combat, parry)


def play_minion_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.combat_state.player.draw_cards(1)

def play_debris(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    pass

# ------------------------------------------------------------ Common

def play_astral_pulse(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit_all(combat, _damage(card, is_upgraded), 2)

def play_begone(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """A card of the hand is transformed into a Minion Strike (upgraded when Begone is)."""
    hand = combat.combat_state.player.hand
    combat.request_choice("begone", list(range(len(hand))), "hand", 1 if is_upgraded else 0)

def play_celestial_might(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index), 4 if is_upgraded else 3)

def play_cloak_of_stars(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 10 if is_upgraded else 7)

def play_collision_course(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.combat_state.player.add_to_hand(Card.create(CardId.DEBRIS))

def play_cosmic_indifference(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 9 if is_upgraded else 6)
    combat.request_choice("to_draw_pile", list(range(len(combat.combat_state.player.discard_pile))), pile="discard")

def play_crescent_spear(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """8 plus 2 (3) for every card with a Star cost the player has in the fight, this one included."""
    _attack(combat, crescent_spear_damage(combat.combat_state.player, 1 if is_upgraded else 0, card), enemy_at(combat, target_index))

def play_crush_under(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Every enemy loses Strength until the end of their turn (CrushUnderPower)."""
    enemies = living_enemies(combat)
    _hit_all(combat, _damage(card, is_upgraded))
    for enemy in enemies:
        if enemy.current_hp > 0:
            temp_strength(enemy, StatusId.CRUSH_UNDER, 2 if is_upgraded else 1, -1, combat)

def play_gather_light(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 11 if is_upgraded else 8)
    combat.gain_stars(1)

def play_glitterstream(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """The next turn's Block is worked out now (Hook.ModifyBlock: Dexterity and Frail), then comes as BlockNextTurnPower."""
    player = combat.combat_state.player
    next_turn = combat.calculate_block(7 if is_upgraded else 5, player)
    _gain_block(combat, 13 if is_upgraded else 11)
    if next_turn > 0:
        player.apply_status(StatusId.BLOCK_NEXT_TURN, next_turn)

def play_glow(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    combat.gain_stars(2 if is_upgraded else 1)
    player.draw_cards(1)
    player.apply_status(StatusId.DRAW_CARDS_NEXT_TURN, 1)

def play_guiding_star(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.combat_state.player.apply_status(StatusId.DRAW_CARDS_NEXT_TURN, 3 if is_upgraded else 2)

def play_hidden_cache(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_stars(1)
    combat.combat_state.player.apply_status(StatusId.STAR_NEXT_TURN, 4 if is_upgraded else 3)

def play_know_thy_place(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _weak(combat, target, 1)
    _vulnerable(combat, target, 1)

def play_patter(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 10 if is_upgraded else 8)
    combat.combat_state.player.apply_status(StatusId.VIGOR, 3 if is_upgraded else 2)

def play_photon_cut(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    player.draw_cards(2 if is_upgraded else 1)
    combat.request_choice("to_draw_pile", list(range(len(player.hand))), pile="hand")

def play_refine_blade(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.forge(12 if is_upgraded else 8, card)
    combat.combat_state.player.apply_status(StatusId.ENERGY_NEXT_TURN, 1)

def play_solar_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.gain_stars(2 if is_upgraded else 1)

def play_spoils_of_battle(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.forge(9 if is_upgraded else 6, card)
    combat.combat_state.player.draw_cards(2)

def play_wrought_in_war(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.forge(9 if is_upgraded else 7, card)


# ------------------------------------------------------------ Uncommon

def play_alignment(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_energy(3 if is_upgraded else 2)

def play_black_hole(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.BLACK_HOLE, 4 if is_upgraded else 3)

def play_bulwark(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 15 if is_upgraded else 12)
    combat.forge(13 if is_upgraded else 10, card)

def play_charge(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Two cards of the draw pile become Minion Dive Bombs (upgraded when Charge is)."""
    pile = combat.combat_state.player.draw_pile
    combat.request_choice("charge", list(range(len(pile))), "draw", 2, source=card)

def play_child_of_the_stars(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.CHILD_OF_THE_STARS, 3 if is_upgraded else 2)

def play_conqueror(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _debuff(combat, enemy_at(combat, target_index), StatusId.CONQUEROR, 1)
    combat.forge(5 if is_upgraded else 3, card)

def play_convergence(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.apply_status(StatusId.RETAIN_HAND, 1)
    player.apply_status(StatusId.ENERGY_NEXT_TURN, 1)
    player.apply_status(StatusId.STAR_NEXT_TURN, 2 if is_upgraded else 1)

def play_devastate(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_furnace(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.FURNACE, 7 if is_upgraded else 5)

def play_gamma_blast(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    if target.current_hp > 0:
        _weak(combat, target, 2)
        _vulnerable(combat, target, 2)

def play_glimmer(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.draw_cards(4 if is_upgraded else 3)
    combat.request_choice("to_draw_pile", list(range(len(player.hand))), pile="hand")

def play_hegemony(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.combat_state.player.apply_status(StatusId.ENERGY_NEXT_TURN, 3 if is_upgraded else 2)

def play_kingly_kick(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_kingly_punch(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded) + card.bonus_damage, enemy_at(combat, target_index))

def play_lunar_blast(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """One hit for each Skill played this turn."""
    target = enemy_at(combat, target_index)
    hits = combat.combat_state.player.skills_played_this_turn
    if hits > 0:
        _attack(combat, _damage(card, is_upgraded), target, hits)

def play_manifest_authority(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    from sts2_lite import rng
    from sts2_lite.event.run import COLORLESS_POOL
    _gain_block(combat, 8 if is_upgraded else 7)
    combat.combat_state.player.add_to_hand(Card.create_generated(rng.choice(COLORLESS_POOL), is_upgraded))

def play_monologue(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    apply_fresh(combat, combat.combat_state.player, StatusId.MONOLOGUE, 1)

def play_orbit(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.ORBIT, 1)

def play_pale_blue_dot(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.PALE_BLUE_DOT, 2 if is_upgraded else 1)

def play_parry(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.PARRY, 14 if is_upgraded else 10)

def play_particle_wall(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 12 if is_upgraded else 9)

def play_pillar_of_creation(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.PILLAR_OF_CREATION, 3 if is_upgraded else 2)

def play_prophesize(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.draw_cards(9 if is_upgraded else 6)

def play_quasar(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Choose one of three colorless cards (upgraded when Quasar is); it joins the hand."""
    from sts2_lite import rng
    from sts2_lite.event.run import COLORLESS_POOL
    offers = [Card.create_generated(cid, is_upgraded) for cid in rng.sample(list(COLORLESS_POOL), 3)]
    combat.request_pick_to_hand(offers)

def play_radiate(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Hits every enemy once for each Star gained this turn."""
    hits = combat.combat_state.player.stars_gained_this_turn
    if hits > 0:
        _hit_all(combat, _damage(card, is_upgraded), hits)

def play_reflect(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 20 if is_upgraded else 15)
    combat.combat_state.player.apply_status(StatusId.REFLECT, 1)

def play_resonance(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.STRENGTH, 2 if is_upgraded else 1)
    for enemy in living_enemies(combat):
        _debuff(combat, enemy, StatusId.STRENGTH, -1)

def play_royal_gamble(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_stars(9)

def play_shining_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.gain_stars(2)

def play_spectrum_shift(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.SPECTRUM_SHIFT, 2)

def play_stardust(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """One hit at a random enemy for each Star it was paid with."""
    from sts2_lite import rng
    for _ in range(combat.last_stars_spent):
        living = living_enemies(combat)
        if not living:
            break
        _attack(combat, _damage(card, is_upgraded), rng.pick_target(living))
        combat.resolve_deaths()

def play_summon_forth(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Every Sovereign Blade that is not in the hand joins it (a Blade that was exhausted too), then Forge."""
    player = combat.combat_state.player
    for pile in (player.draw_pile, player.discard_pile, player.exhaust_pile):
        for blade in [c for c in pile if c.card_id is CardId.SOVEREIGN_BLADE]:
            if len(player.hand) >= 10:
                break
            pile[:] = [c for c in pile if c is not blade]
            player.hand.append(blade)
    combat.forge(11 if is_upgraded else 8, card)

def play_supermassive(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """5 plus 3 (4) for every card made up in this fight."""
    _attack(combat, 5 + (4 if is_upgraded else 3) * combat.combat_state.player.cards_generated, enemy_at(combat, target_index))

def play_terraforming(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.VIGOR, 10 if is_upgraded else 7)

def play_minion_dive_bomb(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))


# ------------------------------------------------------------ Rare

def play_knockout_blow(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    if target.current_hp <= 0:
        combat.gain_stars(5)

def play_minion_sacrifice(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 10 if is_upgraded else 7)

def play_arsenal(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.ARSENAL, 1)

def play_beat_into_shape(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Forge 5 (7), plus the same again for each Attack that already hit the enemy this turn."""
    target = enemy_at(combat, target_index)
    earlier = target.status_amount(StatusId.HIT_THIS_TURN)
    _attack(combat, _damage(card, is_upgraded), target)
    step = 7 if is_upgraded else 5
    combat.forge(step + step * earlier, card)

def play_big_bang(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.draw_cards(1)
    combat.gain_stars(1)
    combat.gain_energy(1)
    combat.forge(5, card)

def play_bombardment(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_bundle_of_joy(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    from sts2_lite import rng
    from sts2_lite.event.run import COLORLESS_POOL
    player = combat.combat_state.player
    for card_id in rng.sample(list(COLORLESS_POOL), 4 if is_upgraded else 3):
        player.add_to_hand(Card.create_generated(card_id))

def play_comet(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    if target.current_hp > 0:
        _weak(combat, target, 3)
        _vulnerable(combat, target, 3)

def play_crash_landing(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Hits every enemy, then Debris fills the hand."""
    _hit_all(combat, _damage(card, is_upgraded))
    player = combat.combat_state.player
    for _ in range(10 - len(player.hand)):
        player.add_to_hand(Card.create(CardId.DEBRIS))

def play_decisions_decisions(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Draw 3 (5), then choose a Skill of the hand: it is played three times."""
    player = combat.combat_state.player
    player.draw_cards(5 if is_upgraded else 3)
    skills = [i for i, c in enumerate(player.hand) if c.type == CardType.Skill and not c.unplayable]
    combat.request_choice("decisions", skills, "hand")

def play_dying_star(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Hits every enemy, which then loses Strength until the end of its turn."""
    enemies = living_enemies(combat)
    _hit_all(combat, _damage(card, is_upgraded))
    for enemy in enemies:
        if enemy.current_hp > 0:
            temp_strength(enemy, StatusId.DYING_STAR, 11 if is_upgraded else 9, -1, combat)

def play_foregone_conclusion(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.FOREGONE_CONCLUSION, 3 if is_upgraded else 2)

def play_genesis(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.GENESIS, 3 if is_upgraded else 2)

def play_guards(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Any number of cards of the hand become Minion Sacrifices (upgraded when Guards is)."""
    hand = combat.combat_state.player.hand
    combat.request_choice("guards", list(range(len(hand))), "hand", 0, source=card)

def play_heavenly_drill(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    """X hits (twice as many with 4 or more Energy)."""
    target = enemy_at(combat, target_index)
    hits = x * 2 if x >= 4 else x
    if hits > 0:
        _attack(combat, _damage(card, is_upgraded), target, hits)

def play_heirloom_hammer(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """After the hit, a colorless card of the hand is copied."""
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    hand = combat.combat_state.player.hand
    combat.request_choice("dual_wield", [i for i, c in enumerate(hand) if c.card_id in COLORLESS_CARDS], "hand", 1)

def play_i_am_invincible(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 13 if is_upgraded else 10)

def play_make_it_so(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_monarchs_gaze(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.MONARCHS_GAZE, 1)

def play_neutron_aegis(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.PLATING, 11 if is_upgraded else 8)

def play_royalties(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.ROYALTIES, 40 if is_upgraded else 30)

def play_seeking_edge(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.SEEKING_EDGE, 1)
    combat.forge(11 if is_upgraded else 7, card)

def play_seven_stars(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit_all(combat, _damage(card, is_upgraded), 7)

def play_sword_sage(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.SWORD_SAGE, 1)

def play_the_smith(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.forge(40 if is_upgraded else 30, card)

def play_tyranny(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.TYRANNY, 1)

def play_void_form(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """The first 2 cards of each turn are free; the turn ends once this card is played."""
    combat.combat_state.player.apply_status(StatusId.VOID_FORM, 2)
    combat.end_turn_requested = True


# ------------------------------------------------------------ Ancient

def play_meteor_shower(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    enemies = living_enemies(combat)
    _hit_all(combat, _damage(card, is_upgraded))
    for enemy in enemies:
        if enemy.current_hp > 0:
            _weak(combat, enemy, 2)
            _vulnerable(combat, enemy, 2)

def play_the_sealed_throne(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    apply_fresh(combat, combat.combat_state.player, StatusId.THE_SEALED_THRONE, 1)

REGENT_PLAYS = {
    CardId.METEOR_SHOWER : play_meteor_shower,
    CardId.THE_SEALED_THRONE : play_the_sealed_throne,
    CardId.STRIKE_REGENT : play_strike_regent,
    CardId.DEFEND_REGENT : play_defend_regent,
    CardId.FALLING_STAR : play_falling_star,
    CardId.VENERATE : play_venerate,
    CardId.SOVEREIGN_BLADE : play_sovereign_blade,
    CardId.MINION_STRIKE : play_minion_strike,
    CardId.DEBRIS : play_debris,
    CardId.ASTRAL_PULSE : play_astral_pulse,
    CardId.BEGONE : play_begone,
    CardId.CELESTIAL_MIGHT : play_celestial_might,
    CardId.CLOAK_OF_STARS : play_cloak_of_stars,
    CardId.COLLISION_COURSE : play_collision_course,
    CardId.COSMIC_INDIFFERENCE : play_cosmic_indifference,
    CardId.CRESCENT_SPEAR : play_crescent_spear,
    CardId.CRUSH_UNDER : play_crush_under,
    CardId.GATHER_LIGHT : play_gather_light,
    CardId.GLITTERSTREAM : play_glitterstream,
    CardId.GLOW : play_glow,
    CardId.GUIDING_STAR : play_guiding_star,
    CardId.HIDDEN_CACHE : play_hidden_cache,
    CardId.KNOW_THY_PLACE : play_know_thy_place,
    CardId.PATTER : play_patter,
    CardId.PHOTON_CUT : play_photon_cut,
    CardId.REFINE_BLADE : play_refine_blade,
    CardId.SOLAR_STRIKE : play_solar_strike,
    CardId.SPOILS_OF_BATTLE : play_spoils_of_battle,
    CardId.WROUGHT_IN_WAR : play_wrought_in_war,
    CardId.ALIGNMENT : play_alignment,
    CardId.BLACK_HOLE : play_black_hole,
    CardId.BULWARK : play_bulwark,
    CardId.CHARGE : play_charge,
    CardId.CHILD_OF_THE_STARS : play_child_of_the_stars,
    CardId.CONQUEROR : play_conqueror,
    CardId.CONVERGENCE : play_convergence,
    CardId.DEVASTATE : play_devastate,
    CardId.FURNACE : play_furnace,
    CardId.GAMMA_BLAST : play_gamma_blast,
    CardId.GLIMMER : play_glimmer,
    CardId.HEGEMONY : play_hegemony,
    CardId.KINGLY_KICK : play_kingly_kick,
    CardId.KINGLY_PUNCH : play_kingly_punch,
    CardId.LUNAR_BLAST : play_lunar_blast,
    CardId.MANIFEST_AUTHORITY : play_manifest_authority,
    CardId.MONOLOGUE : play_monologue,
    CardId.ORBIT : play_orbit,
    CardId.PALE_BLUE_DOT : play_pale_blue_dot,
    CardId.PARRY : play_parry,
    CardId.PARTICLE_WALL : play_particle_wall,
    CardId.PILLAR_OF_CREATION : play_pillar_of_creation,
    CardId.PROPHESIZE : play_prophesize,
    CardId.QUASAR : play_quasar,
    CardId.RADIATE : play_radiate,
    CardId.REFLECT : play_reflect,
    CardId.RESONANCE : play_resonance,
    CardId.ROYAL_GAMBLE : play_royal_gamble,
    CardId.SHINING_STRIKE : play_shining_strike,
    CardId.SPECTRUM_SHIFT : play_spectrum_shift,
    CardId.STARDUST : play_stardust,
    CardId.SUMMON_FORTH : play_summon_forth,
    CardId.SUPERMASSIVE : play_supermassive,
    CardId.TERRAFORMING : play_terraforming,
    CardId.MINION_DIVE_BOMB : play_minion_dive_bomb,
    CardId.KNOCKOUT_BLOW : play_knockout_blow,
    CardId.MINION_SACRIFICE : play_minion_sacrifice,
    CardId.ARSENAL : play_arsenal,
    CardId.BEAT_INTO_SHAPE : play_beat_into_shape,
    CardId.BIG_BANG : play_big_bang,
    CardId.BOMBARDMENT : play_bombardment,
    CardId.BUNDLE_OF_JOY : play_bundle_of_joy,
    CardId.COMET : play_comet,
    CardId.CRASH_LANDING : play_crash_landing,
    CardId.DECISIONS_DECISIONS : play_decisions_decisions,
    CardId.DYING_STAR : play_dying_star,
    CardId.FOREGONE_CONCLUSION : play_foregone_conclusion,
    CardId.GENESIS : play_genesis,
    CardId.GUARDS : play_guards,
    CardId.HEAVENLY_DRILL : play_heavenly_drill,
    CardId.HEIRLOOM_HAMMER : play_heirloom_hammer,
    CardId.I_AM_INVINCIBLE : play_i_am_invincible,
    CardId.MAKE_IT_SO : play_make_it_so,
    CardId.MONARCHS_GAZE : play_monarchs_gaze,
    CardId.NEUTRON_AEGIS : play_neutron_aegis,
    CardId.ROYALTIES : play_royalties,
    CardId.SEEKING_EDGE : play_seeking_edge,
    CardId.SEVEN_STARS : play_seven_stars,
    CardId.SWORD_SAGE : play_sword_sage,
    CardId.THE_SMITH : play_the_smith,
    CardId.TYRANNY : play_tyranny,
    CardId.VOID_FORM : play_void_form,
}
