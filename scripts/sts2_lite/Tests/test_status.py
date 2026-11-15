"""Status tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.creature import Creature
from sts2_lite.enemy import Enemy
from sts2_lite.hooks import HookType
from sts2_lite.player import Player
from sts2_lite.status import StatusId, StatusInstance, TICKS_DOWN


# ---------------------------------------------------------------- helpers
def make_card(card_id, name, card_type, cost, target):
    c = Card()
    c.card_id, c.name, c.type = card_id, name, card_type
    c.energy_cost, c.target_type = cost, target
    c.is_upgraded = False
    c.is_unplayable = False
    return c

def strike():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def defend():
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.Self)

def make_state(hand=None, enemy_hp=40, energy=3):
    p = Player()
    p.max_hp = p.current_hp = 50
    p.hand = list(hand or [])
    p.draw_pile = [strike() for _ in range(10)]
    e = Enemy()
    e.max_hp = e.current_hp = enemy_hp
    e.enemy_id = "TEST_ENEMY"
    e.attack_damage, e.num_attacks = 0, 1
    cs = CombatState()
    cs.player, cs.enemies = p, [e]
    cs.energy = cs.max_energy = energy
    cs.turn_number = 1
    return cs


# ---------------------------------------------------------------- applying / sharing
def test_apply_status_creates_then_stacks():
    c = Creature()
    c.apply_status(StatusId.VULNERABLE, 2)
    assert c.status_amount(StatusId.VULNERABLE) == 2
    c.apply_status(StatusId.VULNERABLE, 3)
    assert c.status_amount(StatusId.VULNERABLE) == 5

def test_status_amount_is_zero_when_absent():
    assert Creature().status_amount(StatusId.STRENGTH) == 0

def test_status_dicts_and_piles_not_shared_between_instances():
    a, b = Player(), Player()
    a.apply_status(StatusId.STRENGTH, 1)
    a.hand.append("x"); a.draw_pile.append("y"); a.discard_pile.append("z")
    assert b.status == {} and b.hand == [] and b.draw_pile == [] and b.discard_pile == []

def test_creature_constructor_honours_status_argument():
    given = {StatusId.STRENGTH: StatusInstance(StatusId.STRENGTH, 4)}
    assert Creature(status=given).status is given

def test_from_dict_strips_suffix():
    s = StatusInstance.from_dict({"id": "STRENGTH_POWER", "amount": 2})
    assert s.status_id == StatusId.STRENGTH and s.amount == 2


# ---------------------------------------------------------------- cloning
def test_cloned_state_statuses_are_independent():
    cs = make_state()
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 2)
    cs.player.apply_status(StatusId.STRENGTH, 1)
    clone = CombatState.deepcopy(cs)
    clone.enemies[0].apply_status(StatusId.VULNERABLE, 5)
    clone.player.apply_status(StatusId.STRENGTH, 5)
    assert cs.enemies[0].status_amount(StatusId.VULNERABLE) == 2
    assert cs.player.status_amount(StatusId.STRENGTH) == 1
    assert clone.enemies[0].status is not cs.enemies[0].status

def test_simulating_a_clone_does_not_change_the_original():
    cs = make_state(hand=[strike()])
    cs.player.apply_status(StatusId.STRENGTH, 2)
    clone = CombatState.deepcopy(cs)
    CombatSimulator(clone).play_card(0, 0)
    assert cs.enemies[0].current_hp == 40
    assert len(cs.player.hand) == 1


# ---------------------------------------------------------------- damage maths
def _damage_dealt(player_status=None, enemy_status=None):
    cs = make_state(hand=[strike()])
    for sid, amt in (player_status or {}).items():
        cs.player.apply_status(sid, amt)
    for sid, amt in (enemy_status or {}).items():
        cs.enemies[0].apply_status(sid, amt)
    CombatSimulator(cs).play_card(0, 0)
    return 40 - cs.enemies[0].current_hp

def test_plain_strike_does_6():
    assert _damage_dealt() == 6

def test_strength_adds():
    assert _damage_dealt({StatusId.STRENGTH: 2}) == 8

def test_weak_reduces_by_quarter_rounded_down():
    assert _damage_dealt({StatusId.WEAK: 1}) == 4      # 6 * 0.75 = 4.5 -> 4

def test_vulnerable_increases_by_half():
    assert _damage_dealt(enemy_status={StatusId.VULNERABLE: 1}) == 9

def test_modifiers_combine_in_order():
    # (6 + 2) * 0.75 * 1.5 = 9.0
    assert _damage_dealt({StatusId.STRENGTH: 2, StatusId.WEAK: 1},
                         {StatusId.VULNERABLE: 1}) == 9

def test_negative_strength_never_heals():
    cs = make_state()
    cs.player.apply_status(StatusId.STRENGTH, -20)
    assert CombatSimulator(cs).calculate_damage(6, cs.player, cs.enemies[0]) == 0

def test_vulnerable_only_affects_the_vulnerable_target():
    cs = make_state()
    cs.player.apply_status(StatusId.VULNERABLE, 2)     # on the attacker, not the target
    assert CombatSimulator(cs).calculate_damage(6, cs.player, cs.enemies[0]) == 6


# ---------------------------------------------------------------- block maths
def _block_gained(player_status=None):
    cs = make_state(hand=[defend()])
    for sid, amt in (player_status or {}).items():
        cs.player.apply_status(sid, amt)
    CombatSimulator(cs).play_card(0, 0)
    return cs.player.block

def test_plain_defend_gives_5():
    assert _block_gained() == 5

def test_dexterity_adds_block():
    assert _block_gained({StatusId.DEXTERITY: 2}) == 7

def test_frail_reduces_block():
    assert _block_gained({StatusId.FRAIL: 1}) == 3     # 5 * 0.75 = 3.75 -> 3

def test_dexterity_then_frail():
    assert _block_gained({StatusId.DEXTERITY: 2, StatusId.FRAIL: 1}) == 5   # 7 * 0.75 = 5.25


# ---------------------------------------------------------------- event handlers
def test_ritual_grants_strength_on_enemy_turn_end():
    cs = make_state()
    cs.enemies[0].apply_status(StatusId.RITUAL, 3)
    CombatSimulator(cs)._play_enemy_turn()
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 3

def test_ritual_and_territorial_stack_without_mutation_errors():
    # handlers add STRENGTH during fire()
    cs = make_state()
    cs.enemies[0].apply_status(StatusId.RITUAL, 3)
    cs.enemies[0].apply_status(StatusId.TERRITORIAL, 1)
    CombatSimulator(cs).fire(HookType.ENEMY_TURN_END)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 4

def test_fire_with_no_handlers_is_a_noop():
    cs = make_state(hand=[strike()])
    sim = CombatSimulator(cs)
    sim.fire(HookType.CARD_PLAYED, cs.player.hand[0])
    sim.fire(HookType.END_TURN)
    assert cs.player.status == {}

def test_handler_fires_for_clones_without_any_setup():
    cs = make_state()
    cs.enemies[0].apply_status(StatusId.RITUAL, 2)
    clone = CombatState.deepcopy(cs)
    CombatSimulator(clone).fire(HookType.ENEMY_TURN_END)
    assert clone.enemies[0].status_amount(StatusId.STRENGTH) == 2
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 0


# ---------------------------------------------------------------- ticking down
def tick(creature):
    cs = make_state()
    CombatSimulator(cs)._decrease_statuses(creature)
    return creature

def test_a_duration_status_loses_one_per_tick_and_goes_at_zero():
    c = Creature()
    c.apply_status(StatusId.WEAK, 2)
    assert tick(c).status_amount(StatusId.WEAK) == 1
    assert StatusId.WEAK not in tick(c).status

def test_every_ticking_status_counts_down():
    for status_id in TICKS_DOWN:
        c = Creature()
        c.apply_status(status_id, 3)
        assert tick(c).status_amount(status_id) == 2, status_id

def test_a_negative_shrink_never_runs_out():
    c = Creature()
    c.apply_status(StatusId.SHRINK, -1)
    assert tick(c).status_amount(StatusId.SHRINK) == -1

def test_slow_resets_to_zero_but_stays():
    c = Creature()
    c.apply_status(StatusId.SLOW, 4)
    assert tick(c).status_amount(StatusId.SLOW) == 0
    assert StatusId.SLOW in c.status

def test_other_statuses_are_left_alone():
    c = Creature()
    c.apply_status(StatusId.STRENGTH, 3)
    c.apply_status(StatusId.THORNS, 2)
    tick(c)
    assert (c.status_amount(StatusId.STRENGTH), c.status_amount(StatusId.THORNS)) == (3, 2)

def test_skipped_statuses_do_not_tick():
    c = Creature()
    c.apply_status(StatusId.VULNERABLE, 2)
    CombatSimulator(make_state())._decrease_statuses(c, skip={StatusId.VULNERABLE})
    assert c.status_amount(StatusId.VULNERABLE) == 2
