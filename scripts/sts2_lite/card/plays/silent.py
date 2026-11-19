"""The Silent's cards (SilentCardPool)."""
from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.helpers import enemy_at, living_enemies
from sts2_lite.status import StatusId

from sts2_lite.card.card import Card
from sts2_lite.card.effects import PLAIN_DAMAGE, _attack, _debuff, _gain_block, _weak, apply_fresh, apply_strangle, temp_strength
from sts2_lite.card.ids import CardId, CardKeyword, CardType, EnchantmentId, TargetType

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator


def _plain_attack(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index))

def play_defend_silent(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)

def play_neutralize(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
    if target.current_hp > 0:
        _weak(combat, target, 2 if is_upgraded else 1)

def play_survivor(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 11 if is_upgraded else 8)
    combat.request_discard(1)


def _damage(card : Card, is_upgraded : bool) -> int:
    return PLAIN_DAMAGE[card.card_id][is_upgraded]

def _hit_all(combat : CombatSimulator, damage : int, times : int = 1):
    """TargetingAllOpponents, WithHitCount(times): every living enemy, once per hit."""
    for _ in range(times):
        for target in living_enemies(combat):
            _attack(combat, damage, target)
        combat.resolve_deaths()

# ------------------------------------------------------------ Common

def play_anticipate(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """AnticipatePower (TemporaryDexterityPower): Dexterity until the end of the turn."""
    player = combat.combat_state.player
    amount = 4 if is_upgraded else 2
    player.apply_status(StatusId.ANTICIPATE, amount)
    player.apply_status(StatusId.DEXTERITY, amount)

def play_backflip(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)
    combat.combat_state.player.draw_cards(2)

def play_blade_dance(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.create_shivs(4 if is_upgraded else 3)

def play_cloak_and_dagger(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 6)
    combat.create_shivs(2 if is_upgraded else 1)

def play_dagger_spray(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit_all(combat, _damage(card, is_upgraded), 2)

def play_dagger_throw(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.resolve_deaths()
    combat.combat_state.player.draw_cards(1)
    combat.request_discard(1)

def play_deadly_poison(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _debuff(combat, enemy_at(combat, target_index), StatusId.POISON, 7 if is_upgraded else 5)

def play_deflect(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 7 if is_upgraded else 4)

def play_dodge_and_roll(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """The block actually gained comes again next turn (BlockNextTurnPower)."""
    gained = _gain_block(combat, 6 if is_upgraded else 4)
    if gained > 0:
        combat.combat_state.player.apply_status(StatusId.BLOCK_NEXT_TURN, gained)

def play_flick_flack(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit_all(combat, _damage(card, is_upgraded))

def play_leading_strike(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.create_shivs(2)

def play_piercing_wail(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """PiercingWailPower (TemporaryStrengthPower, negative): every enemy loses Strength until the end of its turn."""
    for target in living_enemies(combat):
        temp_strength(target, StatusId.PIERCING_WAIL, 8 if is_upgraded else 6, -1, combat)

def play_poisoned_stab(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    _debuff(combat, target, StatusId.POISON, 4 if is_upgraded else 3)

def play_predator(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))
    combat.combat_state.player.apply_status(StatusId.DRAW_CARDS_NEXT_TURN, 2)

def play_prepared(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    count = 2 if is_upgraded else 1
    combat.combat_state.player.draw_cards(count)
    combat.request_discard(count)

def play_ricochet(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """TargetingRandomOpponents: each hit picks a living enemy at random."""
    for _ in range(5 if is_upgraded else 4):
        living = living_enemies(combat)
        if not living:
            break
        _attack(combat, _damage(card, is_upgraded), rng.pick_target(living))
        combat.resolve_deaths()

def play_snakebite(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _debuff(combat, enemy_at(combat, target_index), StatusId.POISON, 10 if is_upgraded else 7)

def play_sucker_punch(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    _weak(combat, target, 2 if is_upgraded else 1)

def play_untouchable(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 9 if is_upgraded else 6)

# ------------------------------------------------------------ Uncommon

def _power(status : StatusId, base : int, upgraded_amount : int):
    def play(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
        combat.combat_state.player.apply_status(status, upgraded_amount if is_upgraded else base)
    return play

def _single_hit(card : Card, combat : CombatSimulator, target_index : int, is_upgraded : bool, hits : int = 1, damage : int | None = None):
    target = enemy_at(combat, target_index)        # a bad target is refused even with no hits
    if hits > 0:
        _attack(combat, _damage(card, is_upgraded) if damage is None else damage, target, hits)

def play_acrobatics(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.draw_cards(4 if is_upgraded else 3)
    combat.request_discard(1)

def play_blur(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 8 if is_upgraded else 5)
    combat.combat_state.player.apply_status(StatusId.BLUR, 1)

def play_bouncing_flask(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """3 Poison on a random enemy, 3 (4) times (Rng.CombatTargets)."""
    for _ in range(4 if is_upgraded else 3):
        living = living_enemies(combat)
        if not living:
            break
        _debuff(combat, rng.pick_target(living), StatusId.POISON, 3)

def play_bubble_bubble(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    if StatusId.POISON in target.status:
        _debuff(combat, target, StatusId.POISON, 12 if is_upgraded else 9)

def play_calculated_gamble(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """CardCmd.DiscardAndDraw: the whole hand is discarded and as many cards drawn, then the Sly ones among the discarded play."""
    hand = list(combat.combat_state.player.hand)
    if hand:
        combat.discard_cards(hand, draw=len(hand))

def play_dash(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 13 if is_upgraded else 10)
    _single_hit(card, combat, target_index, is_upgraded)

def play_echoing_slash(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Every enemy is hit; each one it kills makes it hit every enemy again."""
    damage, pending = _damage(card, is_upgraded), 1
    while pending > 0:
        pending -= 1
        targets = living_enemies(combat)
        if not targets:
            break
        for target in targets:
            _attack(combat, damage, target)
        pending += sum(1 for target in targets if target.current_hp <= 0)
        combat.resolve_deaths()

def play_escape_plan(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    drawn = combat.combat_state.player.draw_card()
    if drawn is not None and drawn.type == CardType.Skill:
        _gain_block(combat, 5 if is_upgraded else 3)

def play_expertise(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """The cards drawn are retained this turn (CardCmd.ApplySingleTurnRetain)."""
    player = combat.combat_state.player
    count = 3 if is_upgraded else 2
    for i in range(count):
        drawn = player.draw_card()
        if drawn is not None:
            for j, c in enumerate(player.hand):
                if c is drawn:
                    player.hand[j] = drawn.with_turn_keyword(CardKeyword.RETAIN)
        if combat.combat_state.pending_choice is not None:
            combat._pause_draw(count - i - 1, False)
            return

def play_expose(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """The target loses all its block and its Artifact, then is Vulnerable."""
    target = enemy_at(combat, target_index)
    target.block = 0
    target.status.pop(StatusId.ARTIFACT, None)
    _debuff(combat, target, StatusId.VULNERABLE, 3 if is_upgraded else 2)

def play_finisher(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """A hit for every Attack played this turn."""
    _single_hit(card, combat, target_index, is_upgraded, combat.combat_state.player.attacks_played_this_turn)

def play_flechettes(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """A hit for every Skill in the hand."""
    _single_hit(card, combat, target_index, is_upgraded, sum(c.type == CardType.Skill for c in combat.combat_state.player.hand))

def play_sidestep(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.ENERGY_NEXT_TURN, 2 if is_upgraded else 1)

def play_hand_trick(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """A Skill of the hand that is not Sly yet gets Sly this turn."""
    _gain_block(combat, 10 if is_upgraded else 7)
    hand = combat.combat_state.player.hand
    options = [i for i, c in enumerate(hand) if c.type == CardType.Skill and not c.sly]
    if options:
        combat.request_choice("sly", options, "hand", 1)

def play_haze(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in living_enemies(combat):
        _debuff(combat, target, StatusId.POISON, 6 if is_upgraded else 4)
    for target in living_enemies(combat):
        _weak(combat, target, 2 if is_upgraded else 1)

def play_hidden_daggers(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Discard 2 cards, then 2 Shivs (upgraded Shivs when this is upgraded)."""
    combat.request_discard(2)
    if combat.combat_state.pending_choice is not None:
        combat.combat_state.continuations = combat.combat_state.continuations + [("shivs", 2, is_upgraded)]
    else:
        combat.create_shivs(2, is_upgraded)

def play_leg_sweep(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 14 if is_upgraded else 11)
    _weak(combat, enemy_at(combat, target_index), 3 if is_upgraded else 2)

def play_memento_mori(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """9 (11) damage plus 4 (5) for every card discarded this turn."""
    base, extra = (11, 5) if is_upgraded else (9, 4)
    _single_hit(card, combat, target_index, is_upgraded, damage=base + extra * combat.combat_state.player.discards_this_turn)

def play_mirage(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Block equal to the Poison on the living enemies."""
    poison = sum(e.status_amount(StatusId.POISON) for e in living_enemies(combat))
    if poison > 0:
        _gain_block(combat, poison)

def play_phantom_blades(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """PhantomBladesPower.AfterApplied: every Shiv of the fight gets Retain."""
    player = combat.combat_state.player
    player.apply_status(StatusId.PHANTOM_BLADES, 12 if is_upgraded else 9)
    for pile in (player.hand, player.draw_pile, player.discard_pile, player.exhaust_pile):
        for i, c in enumerate(pile):
            if c.card_id is CardId.SHIV:
                pile[i] = c.with_keyword(CardKeyword.RETAIN)

def play_pounce(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _single_hit(card, combat, target_index, is_upgraded)
    combat.combat_state.player.apply_status(StatusId.FREE_SKILL, 1)

def play_precise_cut(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """13 (16) damage, 2 less for every other card in the hand."""
    damage = (16 if is_upgraded else 13) - 2 * len(combat.combat_state.player.hand)
    _single_hit(card, combat, target_index, is_upgraded, damage=max(0, damage))

def play_reflex(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.draw_cards(3 if is_upgraded else 2)

def play_skewer(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    _single_hit(card, combat, target_index, is_upgraded, x)

def play_strangle(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, _damage(card, is_upgraded), target)
    apply_strangle(combat, target, 3 if is_upgraded else 2)

def play_tactician(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_energy(2 if is_upgraded else 1)

def play_up_my_sleeve(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Shivs, then this card costs 1 less for the rest of the combat (EnergyCost.AddThisCombat; `card` is this play's own copy)."""
    combat.create_shivs(4 if is_upgraded else 3)
    if card.energy_cost != "X" and card.energy_cost > 0:
        card.energy_cost -= 1
    if isinstance(card.restore_cost, int) and card.restore_cost > 0:
        card.restore_cost -= 1

# ------------------------------------------------------------ Shiv, Rare

def play_shiv(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """With Fan of Knives the Shiv targets every enemy (its target type is AllEnemies then)."""
    if card.target_type is TargetType.AllEnemies:
        _hit_all(combat, _damage(card, is_upgraded))
    else:
        _attack(combat, _damage(card, is_upgraded), enemy_at(combat, target_index))

def play_abrasive(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.apply_status(StatusId.DEXTERITY, 1)
    player.apply_status(StatusId.THORNS, 6 if is_upgraded else 4)

def play_adrenaline(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_energy(2 if is_upgraded else 1)
    combat.combat_state.player.draw_cards(2)

def play_afterimage(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    apply_fresh(combat, combat.combat_state.player, StatusId.AFTERIMAGE, 1)

def play_assassinate(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, 13 if is_upgraded else 10, target)
    _debuff(combat, target, StatusId.VULNERABLE, 2 if is_upgraded else 1)

def play_blade_of_ink(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.create_shivs(3 if is_upgraded else 2, enchantment=EnchantmentId.INKY)

def play_bullet_time(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Every card in the hand is free this turn (not X cards); no more draws this turn."""
    player = combat.combat_state.player
    player.hand[:] = [c.free_this_turn() for c in player.hand]
    player.apply_status(StatusId.NO_DRAW, 1)

def play_fan_of_knives(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.apply_status(StatusId.FAN_OF_KNIVES, 1)
    player.fan_shivs()
    combat.create_shivs(5 if is_upgraded else 4)

def play_grand_finale(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _hit_all(combat, 75 if is_upgraded else 60)

def play_knife_trap(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Every Shiv in the exhaust pile is played at the target (upgraded first, when this is)."""
    enemy_at(combat, target_index)
    player = combat.combat_state.player
    shivs = [c for c in player.exhaust_pile if c.card_id is CardId.SHIV]
    for shiv in shivs:
        if combat.is_over:
            break
        if is_upgraded and not shiv.is_upgraded:
            i = next(i for i, c in enumerate(player.exhaust_pile) if c is shiv)
            shiv = Card.create_copy(shiv)            # CardCmd.Upgrade: a Shiv's upgrade is only its damage
            shiv.is_upgraded = True
            player.exhaust_pile[i] = shiv
        combat.auto_play(shiv, target_index=target_index)

def play_malaise(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    """X (+1 upgraded): the target loses that much Strength and gets that much Weak."""
    target = enemy_at(combat, target_index)
    amount = x + (1 if is_upgraded else 0)
    if amount > 0:
        _debuff(combat, target, StatusId.STRENGTH, -amount)
        _weak(combat, target, amount)

def play_murder(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """1 damage, plus 1 for every card drawn this combat."""
    _attack(combat, 1 + combat.combat_state.player.cards_drawn, enemy_at(combat, target_index))

def play_nightmare(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    hand = combat.combat_state.player.hand
    if hand:
        combat.request_choice("nightmare", list(range(len(hand))), "hand", 1)

def play_outbreak(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Poison every enemy, then their Poison triggers at once (PoisonPower.Trigger, Accelerant included)."""
    from sts2_lite.status import poison_trigger
    for target in living_enemies(combat):
        _debuff(combat, target, StatusId.POISON, 12 if is_upgraded else 9)
    accelerant = combat.combat_state.player.status_amount(StatusId.ACCELERANT)
    for target in living_enemies(combat):
        poison_trigger(target, accelerant)
    combat.resolve_deaths()

def play_serpent_form(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    apply_fresh(combat, combat.combat_state.player, StatusId.SERPENT_FORM, 6 if is_upgraded else 4)

def play_shadow_step(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Discard the hand (Sly cards play); next turn, Double Damage."""
    player = combat.combat_state.player
    player.apply_status(StatusId.SHADOW_STEP, 1)
    if player.hand:
        combat.discard_cards(list(player.hand))

def play_storm_of_steel(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Discard the hand, then a Shiv (upgraded when this is) for every card discarded."""
    player = combat.combat_state.player
    count = len(player.hand)
    if count:
        combat.discard_cards(list(player.hand))
    if combat.combat_state.pending_choice is not None:
        combat.combat_state.continuations = combat.combat_state.continuations + [("shivs", count, is_upgraded)]
    else:
        combat.create_shivs(count, is_upgraded)

def play_the_hunt(card : Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """A kill (not of a minion) earns an extra card reward after the fight: marked with The Hunt (the reward itself is not modelled)."""
    target = enemy_at(combat, target_index)
    _attack(combat, 15 if is_upgraded else 10, target)
    if target.current_hp <= 0 and not target.is_minion:
        combat.combat_state.player.apply_status(StatusId.THE_HUNT, 1)


SILENT_PLAYS = {
    CardId.DEFEND_SILENT : play_defend_silent,
    CardId.NEUTRALIZE : play_neutralize,
    CardId.SHIV : play_shiv,
    CardId.STRIKE_SILENT : _plain_attack,
    CardId.SURVIVOR : play_survivor,
    CardId.ANTICIPATE : play_anticipate,
    CardId.BACKFLIP : play_backflip,
    CardId.BLADE_DANCE : play_blade_dance,
    CardId.CLOAK_AND_DAGGER : play_cloak_and_dagger,
    CardId.DAGGER_SPRAY : play_dagger_spray,
    CardId.DAGGER_THROW : play_dagger_throw,
    CardId.DEADLY_POISON : play_deadly_poison,
    CardId.DEFLECT : play_deflect,
    CardId.DODGE_AND_ROLL : play_dodge_and_roll,
    CardId.FLICK_FLACK : play_flick_flack,
    CardId.LEADING_STRIKE : play_leading_strike,
    CardId.PIERCING_WAIL : play_piercing_wail,
    CardId.POISONED_STAB : play_poisoned_stab,
    CardId.PREDATOR : play_predator,
    CardId.PREPARED : play_prepared,
    CardId.RICOCHET : play_ricochet,
    CardId.SLICE : _plain_attack,
    CardId.SNAKEBITE : play_snakebite,
    CardId.SUCKER_PUNCH : play_sucker_punch,
    CardId.UNTOUCHABLE : play_untouchable,
    CardId.ACCELERANT : _power(StatusId.ACCELERANT, 1, 2),
    CardId.ACCURACY : _power(StatusId.ACCURACY, 4, 6),
    CardId.ACROBATICS : play_acrobatics,
    CardId.BACKSTAB : _plain_attack,
    CardId.BLUR : play_blur,
    CardId.BOUNCING_FLASK : play_bouncing_flask,
    CardId.BUBBLE_BUBBLE : play_bubble_bubble,
    CardId.CALCULATED_GAMBLE : play_calculated_gamble,
    CardId.DASH : play_dash,
    CardId.ECHOING_SLASH : play_echoing_slash,
    CardId.ESCAPE_PLAN : play_escape_plan,
    CardId.EXPERTISE : play_expertise,
    CardId.EXPOSE : play_expose,
    CardId.FINISHER : play_finisher,
    CardId.FLECHETTES : play_flechettes,
    CardId.SIDESTEP : play_sidestep,
    CardId.FOOTWORK : _power(StatusId.DEXTERITY, 2, 3),
    CardId.HAND_TRICK : play_hand_trick,
    CardId.HAZE : play_haze,
    CardId.HIDDEN_DAGGERS : play_hidden_daggers,
    CardId.INFINITE_BLADES : _power(StatusId.INFINITE_BLADES, 1, 1),
    CardId.LEG_SWEEP : play_leg_sweep,
    CardId.MEMENTO_MORI : play_memento_mori,
    CardId.MIRAGE : play_mirage,
    CardId.NOXIOUS_FUMES : _power(StatusId.NOXIOUS_FUMES, 2, 3),
    CardId.PHANTOM_BLADES : play_phantom_blades,
    CardId.PINPOINT : _plain_attack,
    CardId.POUNCE : play_pounce,
    CardId.PRECISE_CUT : play_precise_cut,
    CardId.REFLEX : play_reflex,
    CardId.SKEWER : play_skewer,
    CardId.SPEEDSTER : _power(StatusId.SPEEDSTER, 2, 2),
    CardId.STRANGLE : play_strangle,
    CardId.TACTICIAN : play_tactician,
    CardId.UP_MY_SLEEVE : play_up_my_sleeve,
    CardId.ABRASIVE : play_abrasive,
    CardId.ADRENALINE : play_adrenaline,
    CardId.AFTERIMAGE : play_afterimage,
    CardId.ASSASSINATE : play_assassinate,
    CardId.BLADE_OF_INK : play_blade_of_ink,
    CardId.BULLET_TIME : play_bullet_time,
    CardId.BURST : _power(StatusId.BURST, 1, 2),
    CardId.CORROSIVE_WAVE : _power(StatusId.CORROSIVE_WAVE, 2, 3),
    CardId.ENVENOM : _power(StatusId.ENVENOM, 1, 2),
    CardId.FAN_OF_KNIVES : play_fan_of_knives,
    CardId.GRAND_FINALE : play_grand_finale,
    CardId.KNIFE_TRAP : play_knife_trap,
    CardId.MALAISE : play_malaise,
    CardId.MASTER_PLANNER : _power(StatusId.MASTER_PLANNER, 1, 1),
    CardId.MURDER : play_murder,
    CardId.NIGHTMARE : play_nightmare,
    CardId.OUTBREAK : play_outbreak,
    CardId.SERPENT_FORM : play_serpent_form,
    CardId.SHADOW_STEP : play_shadow_step,
    CardId.SHADOWMELD : _power(StatusId.SHADOWMELD, 1, 1),
    CardId.STORM_OF_STEEL : play_storm_of_steel,
    CardId.THE_HUNT : play_the_hunt,
    CardId.TOOLS_OF_THE_TRADE : _power(StatusId.TOOLS_OF_THE_TRADE, 1, 1),
    CardId.TRACKING : _power(StatusId.TRACKING, 50, 50),
    CardId.WELL_LAID_PLANS : _power(StatusId.WELL_LAID_PLANS, 1, 1),
}
