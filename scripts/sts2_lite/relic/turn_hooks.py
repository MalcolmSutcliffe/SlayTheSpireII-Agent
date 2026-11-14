from __future__ import annotations
from typing import TYPE_CHECKING

from sts2_lite import rng
from sts2_lite.hooks import HookType
from sts2_lite.helpers import living_enemies, player_of
from sts2_lite.status import StatusId

from sts2_lite.relic.card_hooks import _card_types, _count, _hurt_all, _hurt_random
from sts2_lite.relic.ids import HAPPY_FLOWER_TURNS, RelicId

if TYPE_CHECKING:
    from sts2_lite.card import Card
    from sts2_lite.creature import Creature

# --- relics that act on a particular turn, or on every turn after the first.
# A relic that only acts on turn 1 (Lantern, Akabeko, Anchor, Bag of Preparation...) is not modelled: its effect is already in
# the state the bridge gives us, and the simulation never plays turn 1 again.
def _turn(combat) -> int:
    """PlayerCombatState.TurnNumber (relics count player turns, not rounds)."""
    return combat.combat_state.player_turn

CANDELABRA_TURN, CANDELABRA_ENERGY = 2, 2

CHANDELIER_TURN, CHANDELIER_ENERGY = 3, 3

HORN_CLEAT_TURN, HORN_CLEAT_BLOCK = 2, 14

CAPTAINS_WHEEL_TURN, CAPTAINS_WHEEL_BLOCK = 3, 18

SPARKLING_ROUGE_TURN = 3

MERCURY_HOURGLASS_DAMAGE = 3

STONE_CALENDAR_TURN, STONE_CALENDAR_DAMAGE = 7, 52

BRIMSTONE_SELF, BRIMSTONE_ENEMY = 2, 1

ORICHALCUM_BLOCK = {RelicId.ORICHALCUM : 6, RelicId.FAKE_ORICHALCUM : 3}

SCREAMING_FLAGON_DAMAGE = 20

PARRYING_SHIELD_BLOCK, PARRYING_SHIELD_DAMAGE = 10, 6

def _candelabra(combat, relic):
    if _turn(combat) == CANDELABRA_TURN:
        combat.gain_energy(CANDELABRA_ENERGY)

def _chandelier(combat, relic):
    if _turn(combat) == CHANDELIER_TURN:
        combat.gain_energy(CHANDELIER_ENERGY)

def _happy_flower(combat, relic):
    """The counter is the turns seen since the last energy. It reads 3 for a moment while the relic flashes, which is 0."""
    turns = HAPPY_FLOWER_TURNS[relic.relic_id]
    relic.counter = (_count(relic) % turns + 1) % turns
    if relic.counter == 0:
        combat.gain_energy(1)

def _horn_cleat(combat, relic):
    if _turn(combat) == HORN_CLEAT_TURN:
        combat.gain_block(player_of(combat), HORN_CLEAT_BLOCK)

def _captains_wheel(combat, relic):
    if _turn(combat) == CAPTAINS_WHEEL_TURN:
        combat.gain_block(player_of(combat), CAPTAINS_WHEEL_BLOCK)

def _sparkling_rouge(combat, relic):
    if _turn(combat) == SPARKLING_ROUGE_TURN:
        player_of(combat).apply_status(StatusId.STRENGTH, 1)
        player_of(combat).apply_status(StatusId.DEXTERITY, 1)

def _mercury_hourglass(combat, relic):
    _hurt_all(combat, MERCURY_HOURGLASS_DAMAGE)

def _brimstone(combat, relic):
    player_of(combat).apply_status(StatusId.STRENGTH, BRIMSTONE_SELF)
    for enemy in living_enemies(combat):
        enemy.apply_status(StatusId.STRENGTH, BRIMSTONE_ENEMY)

def _stone_calendar(combat, relic):
    if _turn(combat) == STONE_CALENDAR_TURN:
        _hurt_all(combat, STONE_CALENDAR_DAMAGE)

def _orichalcum_check(combat, relic):
    """Looked at before anything else ends the turn: only block you already had counts (`value`: there was none)."""
    relic.value = 1 if player_of(combat).block == 0 else 0

def _orichalcum(combat, relic):
    if relic.value:
        combat.gain_block(player_of(combat), ORICHALCUM_BLOCK[relic.relic_id])
    relic.value = 0

def _cloak_clasp(combat, relic):
    if player_of(combat).hand:
        combat.gain_block(player_of(combat), len(player_of(combat).hand))

def _screaming_flagon(combat, relic):
    if not player_of(combat).hand:
        _hurt_all(combat, SCREAMING_FLAGON_DAMAGE)

SAI_BLOCK = 7

PAELS_TEARS_ENERGY = 2

def _crossbow(combat, relic):
    """Crossbow.AfterSideTurnStart: a random Attack from the character pool, free this turn."""
    from sts2_lite.card import Card, INFERNAL_BLADE_POOL
    player_of(combat).add_to_hand(Card.create_generated(rng.choice(INFERNAL_BLADE_POOL)).free_this_turn())     # X stays X

TOASTY_MITTENS_STRENGTH = 1

PHILOSOPHERS_STONE_STRENGTH = 1

def _toasty_mittens(combat, relic):
    """ToastyMittens.BeforeHandDraw: exhaust the top card of the draw pile (reshuffling first), +1 Strength."""
    player = player_of(combat)
    top = player.take_top()
    if top is not None:
        player.exhaust_card(top)
        combat.fire(HookType.CARD_EXHAUSTED, top)
    player.apply_status(StatusId.STRENGTH, TOASTY_MITTENS_STRENGTH)

def _history_course_record(combat, relic, card):
    """Remember the last Attack or Skill of the turn; `used` is set while History Course's own dupe plays."""
    if not relic.used and card.type in _card_types()[:2]:
        relic.triggering = card
        relic.value = combat.card_x if card.energy_cost == "X" else 0

def _history_course(combat, relic):
    """HistoryCourse.AfterAutoPrePlayPhaseEntered: from turn 2, play a dupe of last turn's last Attack or Skill."""
    from sts2_lite.card import Card
    card, relic.triggering, x = relic.triggering, None, relic.value
    if card is None or _turn(combat) <= 1:
        return
    relic.used = True
    try:
        combat.auto_play(Card.create_copy(card), dupe=True, x_value=x if card.energy_cost == "X" else None)
    finally:
        relic.used = False

def _sai(combat, relic):
    combat.gain_block(player_of(combat), SAI_BLOCK)

def _mr_struggles(combat, relic):
    _hurt_all(combat, _turn(combat))

def _paels_tears_check(combat, relic):
    """PaelsTears.BeforeSideTurnEnd: `value` = energy was left over."""
    relic.value = 1 if combat.combat_state.energy > 0 else 0

def _paels_tears(combat, relic):
    if relic.value:
        combat.gain_energy(PAELS_TEARS_ENERGY)

SEAL_OF_GOLD_ENERGY = 1

SEAL_OF_GOLD_GOLD = 5

def _seal_of_gold(combat, relic):
    """SealOfGold.AfterSideTurnStart: Gold >= 5 -> GainEnergy(1), then LoseGold(5)."""
    player = player_of(combat)
    if player.gold >= SEAL_OF_GOLD_GOLD:
        combat.gain_energy(SEAL_OF_GOLD_ENERGY)
        player.gold -= SEAL_OF_GOLD_GOLD

def _paels_legion_turn(combat, relic):
    """PaelsLegion.AfterSideTurnStart: Cooldown--; ready again at 0."""
    if relic.counter:
        relic.counter -= 1

def _paels_eye_ready(combat, relic) -> bool:
    """PaelsEye: !UsedThisCombat && !AnyCardsPlayedThisTurn (auto-plays don't count)."""
    return not relic.used and combat.combat_state.cards_played == 0

def _paels_eye_exhaust(combat, relic):
    """PaelsEye.BeforeSideTurnEndEarly: exhaust the hand (a snapshot; cards drawn meanwhile stay)."""
    if not _paels_eye_ready(combat, relic):
        return
    player = player_of(combat)
    for card in list(player.hand):
        player.exhaust_card(card)
        combat.fire(HookType.CARD_EXHAUSTED, card)

def take_extra_turn(combat) -> bool:
    """PaelsEye.ShouldTakeExtraTurn, then AfterTakingExtraTurn (UsedThisCombat = true)."""
    relic = player_of(combat).relics.get(RelicId.PAELS_EYE)
    if relic is None or not _paels_eye_ready(combat, relic):
        return False
    relic.used = True
    return True

def _parrying_shield(combat, relic):
    if player_of(combat).block >= PARRYING_SHIELD_BLOCK:
        _hurt_random(combat, PARRYING_SHIELD_DAMAGE)

# ---
# Reactions: HP lost, shuffles, kills, an empty hand
# ---
CENTENNIAL_PUZZLE_CARDS = 3

GREMLIN_HORN_ENERGY = 1

GREMLIN_HORN_CARDS = 1

PENDULUM_TURNS = 3

ABACUS_BLOCK = 6

RED_SKULL_STRENGTH = 3

SELF_FORMING_CLAY_BLOCK = 3

def _centennial_puzzle(combat, relic, amount):
    if not relic.used:
        relic.used = True
        player_of(combat).draw_cards(CENTENNIAL_PUZZLE_CARDS)

def _gremlin_horn(combat, relic, creature):
    if creature is not player_of(combat):
        combat.gain_energy(GREMLIN_HORN_ENERGY)
        player_of(combat).draw_cards(GREMLIN_HORN_CARDS)

def _pendulum(combat, relic):
    relic.counter = (_count(relic) % PENDULUM_TURNS + 1) % PENDULUM_TURNS    # it reads 3 for a moment while it flashes, which is 0
    if relic.counter == 0:
        player_of(combat).draw_cards(1)

def _biiig_hug(combat, relic):
    """BiiigHug.AfterShuffle: a Soot at a random place in the new draw pile."""
    from sts2_lite.card import Card
    player_of(combat).insert_into_draw_pile(Card.create_soot())

def _abacus(combat, relic):
    combat.gain_block(player_of(combat), ABACUS_BLOCK)

def _unceasing_top(combat, relic):
    player_of(combat).draw_cards(1)

def _demon_tongue(combat, relic, amount):
    """The first time hit points are lost on the player's own turn they are healed back."""
    if combat.in_enemy_turn or relic.used:
        return
    relic.used = True
    player = player_of(combat)
    player.current_hp = min(player.max_hp, player.current_hp + amount)

def _demon_tongue_reset(combat, relic):
    relic.used = False

def _red_skull(combat, relic):
    player = player_of(combat)
    low = player.current_hp * 2 <= player.max_hp
    if low and not relic.used:
        relic.used = True
        player.apply_status(StatusId.STRENGTH, RED_SKULL_STRENGTH)
    elif not low and relic.used:
        relic.used = False
        player.apply_status(StatusId.STRENGTH, -RED_SKULL_STRENGTH)

def _self_forming_clay(combat, relic, amount):
    player_of(combat).apply_status(StatusId.SELF_FORMING_CLAY, SELF_FORMING_CLAY_BLOCK)

# ---
# Max energy and victory.
# ---
BREAD_ENERGY = 1

PAELS_FLESH_ENERGY = 1

MEAT_ON_THE_BONE_HEAL = 12

VICTORY_HEAL : dict[RelicId, int] = {RelicId.BURNING_BLOOD : 6, RelicId.BLACK_BLOOD : 12}     # AfterCombatVictory

REPTILE_TRINKET_STRENGTH = 3

BELT_BUCKLE_DEXTERITY = 2

def dexterity_bonus(owner : Creature) -> int:
    """Belt Buckle: 2 additional Dexterity while the player holds no Potions (assumed to count for card Block only, like Dexterity)."""
    if RelicId.BELT_BUCKLE in owner.relics and not getattr(owner, "potions", True):
        return BELT_BUCKLE_DEXTERITY
    return 0

def max_energy_gain(owner : Creature, turn : int) -> int:
    """ModifyMaxEnergy: Bread +1 from turn 2, Pael's Flesh +1 from turn 3 (player turns). The bridge already includes them once
    active, so each is added only on the turn it starts."""
    if turn == 2 and RelicId.BREAD in owner.relics:
        return BREAD_ENERGY
    if turn == 3 and RelicId.PAELS_FLESH in owner.relics:
        return PAELS_FLESH_ENERGY
    return 0

def victory_heal(owner : Creature):
    """Meat on the Bone (victory early: +12 if HP <= floor(max / 2)), then Burning Blood / Black Blood."""
    if RelicId.MEAT_ON_THE_BONE in owner.relics and owner.current_hp <= owner.max_hp // 2:
        owner.current_hp = min(owner.max_hp, owner.current_hp + MEAT_ON_THE_BONE_HEAL)
    for relic_id, heal in VICTORY_HEAL.items():
        if relic_id in owner.relics:
            owner.current_hp = min(owner.max_hp, owner.current_hp + heal)
