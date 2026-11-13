from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.helpers import enemy_at, living_enemies
from sts2_lite.relic import debuff_multiplier
from sts2_lite.status import AUTOMATION_CARDS, PANACHE_CARDS, StatusId, is_debuff

from sts2_lite.card.card import Card
from sts2_lite.card.effects import PLAIN_DAMAGE, _attack, _gain_block, _vulnerable, temp_strength
from sts2_lite.card.ids import CardId, CardType
from sts2_lite.card.tables import GENERATABLE_CARDS, JACK_POOL, RARE_CARDS, ZERO_COST_POOL

if TYPE_CHECKING:
    from sts2_lite.combat import CombatSimulator

def play_equilibrium(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 16 if is_upgraded else 13)
    combat.combat_state.player.apply_status(StatusId.RETAIN_HAND, 1)

def play_salvo(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index))
    combat.combat_state.player.apply_status(StatusId.RETAIN_HAND, 1)

def play_panic_button(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 40 if is_upgraded else 30)
    combat.combat_state.player.apply_status(StatusId.NO_BLOCK, 2)       # after the block: this and the next turn's cards give none

def play_prolong(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if player.block > 0:
        player.apply_status(StatusId.BLOCK_NEXT_TURN, player.block)

def play_fasten(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.FASTEN, 6 if is_upgraded else 4)

def play_prep_time(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.PREP_TIME, 6 if is_upgraded else 4)

def play_dark_shackles(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    temp_strength(enemy_at(combat, target_index), StatusId.DARK_SHACKLES, 15 if is_upgraded else 9, -1, combat)

def play_automation(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.add_instance(StatusId.AUTOMATION, [AUTOMATION_CARDS])

def play_panache(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.add_instance(StatusId.PANACHE, [PANACHE_CARDS, 14 if is_upgraded else 10, 0])

def play_rolling_boulder(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.add_instance(StatusId.ROLLING_BOULDER, [10 if is_upgraded else 5])

def play_the_bomb(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.add_instance(StatusId.THE_BOMB, [3, 50 if is_upgraded else 40])

def play_the_gambit(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 75 if is_upgraded else 50)
    combat.combat_state.player.apply_status(StatusId.THE_GAMBIT, 1)

def play_mayhem(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.MAYHEM, 1)

def play_nostalgia(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.NOSTALGIA, 1)

def play_bolas(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index))

def play_thrumming_hatchet(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index))

def play_jackpot(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index))
    for _ in range(3):      # CardFactory.GetForCombat: with repeats
        combat.combat_state.player.add_to_hand(Card.create_generated(rng.choice(ZERO_COST_POOL), is_upgraded))

def play_calamity(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.CALAMITY, 1)

def play_jack_of_all_trades(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for card_id in rng.sample(JACK_POOL, 2 if is_upgraded else 1):       # distinct
        combat.combat_state.player.add_to_hand(Card.create_generated(card_id))

def play_catastrophe(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.play_random_from_draw_pile(3 if is_upgraded else 2)

def play_beat_down(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    attacks = [c for c in player.discard_pile if c.type == CardType.Attack and not c.unplayable]
    combat._run_autoplay(rng.sample(attacks, min(len(attacks), 4 if is_upgraded else 3)))       # all chosen before the first is played; a card that asks for a pick holds the rest back

def play_anointed(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    rares = [c for c in player.draw_pile if c.card_id in RARE_CARDS]
    for pick in rng.sample(rares, min(len(rares), MAX_HAND_SIZE - len(player.hand))):
        player.remove_from_draw_pile(pick)
        player.hand.append(pick)

def play_discovery(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    # CardFactory.GetDistinctForCombat: three different cards; the game shows its own three (see CombatState.adopt_offer)
    combat.request_discovery([Card.create_generated(card_id) for card_id in rng.sample(list(GENERATABLE_CARDS), 3)])

def play_entropy(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.ENTROPY, 1)

def play_alchemize(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    """Procure a random potion (never Fruit Juice); nothing happens when every potion slot is full."""
    from sts2_lite.potion import procure_random_potion, PotionId
    procure_random_potion(combat.combat_state.player, exclude=(PotionId.FRUIT_JUICE,))

def play_hidden_gem(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    # a playable card without Replay that is not a Curse; Attacks, Skills and Powers first
    candidates = [i for i, c in enumerate(player.draw_pile) if not c.unplayable and c.type != CardType.Curse and c.replay == 0 and not c.has_glam_replay]
    preferred = [i for i in candidates if player.draw_pile[i].type != CardType.Status]
    if not candidates:
        return
    i = rng.choice(preferred or candidates)
    gained = player.draw_pile[i].with_replay(3 if is_upgraded else 2)
    player.draw_pile[i] = gained            # in place: a known top card stays where it is

MAX_HAND_SIZE = 10

def play_finesse(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 7 if is_upgraded else 4)
    combat.combat_state.player.draw_cards(1)

def play_flash_of_steel(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index))
    combat.combat_state.player.draw_cards(1)

def play_ultimate_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index))

def play_ultimate_defend(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _gain_block(combat, 15 if is_upgraded else 11)

def play_production(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.gain_energy(3 if is_upgraded else 2)

def play_master_of_strategy(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.draw_cards(4 if is_upgraded else 3)

def play_dramatic_entrance(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    for target in list(combat.combat_state.enemies):
        _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)

def play_shockwave(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    amount = 5 if is_upgraded else 3
    for target in living_enemies(combat):
        target.apply_status(StatusId.WEAK, amount * debuff_multiplier(player, combat.card_in_play, target) if player.relics else amount)
        _vulnerable(combat, target, amount)

def play_prowess(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.apply_status(StatusId.STRENGTH, 2 if is_upgraded else 1)
    player.apply_status(StatusId.DEXTERITY, 2 if is_upgraded else 1)

def play_impatience(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if not any(c.type == CardType.Attack for c in player.hand):
        player.draw_cards(3 if is_upgraded else 2)

def play_restlessness(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    if not player.hand:         # the card being played has left the hand
        player.draw_cards(3 if is_upgraded else 2)
        combat.gain_energy(3 if is_upgraded else 2)

def play_scrawl(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.draw_cards(MAX_HAND_SIZE - len(player.hand))

def play_fisticuffs(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    before = target.damage_taken
    _attack(combat, 9 if is_upgraded else 7, target)
    dealt = target.damage_taken - before
    if dealt > 0:
        _gain_block(combat, dealt)       # powered block: Dexterity and Frail apply

def play_mind_blast(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, len(combat.combat_state.player.draw_pile), enemy_at(combat, target_index))

def play_gold_axe(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, combat.combat_state.player.cards_played_total, enemy_at(combat, target_index))

def play_rend(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    debuffs = sum(1 for status_id, inst in target.status.items() if is_debuff(status_id, inst.amount) and status_id not in (StatusId.MANGLE, StatusId.DARK_SHACKLES))
    _attack(combat, (18 if is_upgraded else 15) + (8 if is_upgraded else 5) * debuffs, target)    # temporary debuffs do not count

def play_omnislice(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    before = target.damage_taken
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
    dealt = target.damage_taken - before
    if dealt > 0:       # the rest take what the first hit dealt, unpowered (no Strength or Vulnerable)
        for other in living_enemies(combat):
            if other is not target:
                other.apply_damage(dealt, combat.combat_state.player)

def play_volley(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False, x=0):
    for _ in range(x):
        living = living_enemies(combat)
        if not living:
            break
        _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], rng.pick_target(living))
        combat.resolve_deaths()

def play_eternal_armor(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    combat.combat_state.player.apply_status(StatusId.PLATING, 12 if is_upgraded else 9)

def play_hand_of_greed(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    target = enemy_at(combat, target_index)
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], target)
    if target.current_hp <= 0 and StatusId.MINION not in target.status:
        combat.combat_state.player.gold += 25 if is_upgraded else 20

def play_purity(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    hand = combat.combat_state.player.hand
    combat.request_choice("exhaust_any", list(range(len(hand))), amount=5 if is_upgraded else 3)

def _pick_from_draw_pile(combat : CombatSimulator, card_type : CardType):
    """Secret Technique / Secret Weapon: take a Skill / Attack of your choice from the draw pile."""
    draw = combat.combat_state.player.draw_pile
    combat.request_choice("draw_to_hand", [i for i, c in enumerate(draw) if c.type == card_type], pile="draw")

def play_secret_technique(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _pick_from_draw_pile(combat, CardType.Skill)

def play_secret_weapon(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _pick_from_draw_pile(combat, CardType.Attack)

SEEKER_STRIKE_OPTIONS = 3

def play_seeker_strike(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    _attack(combat, PLAIN_DAMAGE[card.card_id][is_upgraded], enemy_at(combat, target_index))
    draw = combat.combat_state.player.draw_pile
    if draw:        # three random cards of the draw pile (the game's own three are adopted when its screen appears)
        offered = rng.sample(range(len(draw)), min(SEEKER_STRIKE_OPTIONS, len(draw)))
        combat.request_choice("draw_to_hand", offered, pile="draw", hidden=True)

def play_thinking_ahead(card: Card, combat : CombatSimulator, target_index=0, is_upgraded=False):
    player = combat.combat_state.player
    player.draw_cards(2)
    combat.request_choice("to_draw_pile", list(range(len(player.hand))), pile="hand")


COLORLESS_PLAYS = {
    CardId.ALCHEMIZE : play_alchemize,
    CardId.ANOINTED : play_anointed,
    CardId.AUTOMATION : play_automation,
    CardId.BEAT_DOWN : play_beat_down,
    CardId.BOLAS : play_bolas,
    CardId.CALAMITY : play_calamity,
    CardId.CATASTROPHE : play_catastrophe,
    CardId.DARK_SHACKLES : play_dark_shackles,
    CardId.DISCOVERY : play_discovery,
    CardId.DRAMATIC_ENTRANCE : play_dramatic_entrance,
    CardId.ENTROPY : play_entropy,
    CardId.EQUILIBRIUM : play_equilibrium,
    CardId.ETERNAL_ARMOR : play_eternal_armor,
    CardId.FASTEN : play_fasten,
    CardId.FINESSE : play_finesse,
    CardId.FISTICUFFS : play_fisticuffs,
    CardId.FLASH_OF_STEEL : play_flash_of_steel,
    CardId.GOLD_AXE : play_gold_axe,
    CardId.HAND_OF_GREED : play_hand_of_greed,
    CardId.HIDDEN_GEM : play_hidden_gem,
    CardId.IMPATIENCE : play_impatience,
    CardId.JACKPOT : play_jackpot,
    CardId.JACK_OF_ALL_TRADES : play_jack_of_all_trades,
    CardId.MASTER_OF_STRATEGY : play_master_of_strategy,
    CardId.MAYHEM : play_mayhem,
    CardId.MIND_BLAST : play_mind_blast,
    CardId.NOSTALGIA : play_nostalgia,
    CardId.OMNISLICE : play_omnislice,
    CardId.PANACHE : play_panache,
    CardId.PANIC_BUTTON : play_panic_button,
    CardId.PREP_TIME : play_prep_time,
    CardId.PRODUCTION : play_production,
    CardId.PROLONG : play_prolong,
    CardId.PROWESS : play_prowess,
    CardId.PURITY : play_purity,
    CardId.REND : play_rend,
    CardId.RESTLESSNESS : play_restlessness,
    CardId.ROLLING_BOULDER : play_rolling_boulder,
    CardId.SALVO : play_salvo,
    CardId.SCRAWL : play_scrawl,
    CardId.SECRET_TECHNIQUE : play_secret_technique,
    CardId.SECRET_WEAPON : play_secret_weapon,
    CardId.SEEKER_STRIKE : play_seeker_strike,
    CardId.SHOCKWAVE : play_shockwave,
    CardId.THE_BOMB : play_the_bomb,
    CardId.THE_GAMBIT : play_the_gambit,
    CardId.THINKING_AHEAD : play_thinking_ahead,
    CardId.THRUMMING_HATCHET : play_thrumming_hatchet,
    CardId.ULTIMATE_DEFEND : play_ultimate_defend,
    CardId.ULTIMATE_STRIKE : play_ultimate_strike,
    CardId.VOLLEY : play_volley,
}
