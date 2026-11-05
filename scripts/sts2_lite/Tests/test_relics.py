"""Relics in combat. Run from scripts/: python -m pytest sts2_lite/Tests"""
from sts2_lite.card import Card, CardId, CardType, TargetType, STRIKE_CARDS
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.player import Player
from sts2_lite.relic import RelicId, RelicInstance, damage_bonus, DAMAGE_ADDITIVE, STRIKE_DUMMY_BONUS
from sts2_lite.status import StatusId
from sts2_lite.Tests.test_cards import make_card, make_state, play, hps


def card(card_id, cost, kind, target=TargetType.AnyEnemy, upgraded=False):
    return make_card(card_id, card_id.name.title(), kind, cost, target, upgraded)

def strike():
    return card(CardId.STRIKE_IRONCLAD, 1, CardType.Attack)

def bash():
    return card(CardId.BASH, 2, CardType.Attack)

def defend():
    return card(CardId.DEFEND_IRONCLAD, 1, CardType.Skill, TargetType.Self)

def with_relic(cs, relic_id=RelicId.STRIKE_DUMMY, counter=None):
    cs.player.relics[relic_id] = RelicInstance(relic_id, counter)
    return cs

def bridge_player(relics):
    return {"max_hp": 80, "hp": 80, "block": 0, "hand": [], "draw_pile": [], "discard_pile": [], "status": [],
            "relics": relics}

def bridge_relic(relic_id, counter=None):
    return {"id": relic_id, "name": relic_id.title(), "description": "", "counter": counter, "keywords": []}


# ---------------------------------------------------------------- the structure
def test_relics_are_separate_from_statuses():
    cs = with_relic(make_state([strike()]))
    assert RelicId.STRIKE_DUMMY in cs.player.relics and cs.player.status == {}

def test_a_new_player_has_no_relics():
    assert Player().relics == {}

def test_every_relic_id_is_registered_for_its_effect():
    assert set(DAMAGE_ADDITIVE) <= set(RelicId)

def test_the_bridge_id_is_the_enum_name():
    assert RelicInstance.from_dict(bridge_relic("STRIKE_DUMMY")).relic_id == RelicId.STRIKE_DUMMY


# ---------------------------------------------------------------- loading
def test_a_relic_is_loaded_from_the_bridge():
    pl = Player.from_dict(bridge_player([bridge_relic("STRIKE_DUMMY")]))
    assert list(pl.relics) == [RelicId.STRIKE_DUMMY]

def test_relics_without_a_combat_effect_are_ignored():
    pl = Player.from_dict(bridge_player([bridge_relic("BURNING_BLOOD"), bridge_relic("STRIKE_DUMMY"),
                                         bridge_relic("SOME_NEW_RELIC")]))
    assert list(pl.relics) == [RelicId.STRIKE_DUMMY]

def test_a_player_with_no_relic_list_loads():
    d = bridge_player([]); del d["relics"]
    assert Player.from_dict(d).relics == {}

def test_the_counter_is_loaded():
    pl = Player.from_dict(bridge_player([bridge_relic("STRIKE_DUMMY", 4)]))
    assert pl.relics[RelicId.STRIKE_DUMMY].counter == 4

def test_relics_come_through_combat_state_loading():
    cs = CombatState.from_dict({"energy": 3, "max_energy": 3, "round": 1, "enemies": [],
                                "player": {**bridge_player([bridge_relic("STRIKE_DUMMY")]), "deck": []}})
    assert RelicId.STRIKE_DUMMY in cs.player.relics


# ---------------------------------------------------------------- copying
def test_relics_survive_a_copy_of_the_player():
    cs = with_relic(make_state([]), counter=2)
    copy = Player.deepcopy(cs.player)
    assert copy.relics[RelicId.STRIKE_DUMMY].counter == 2

def test_a_copied_relic_is_independent():
    cs = with_relic(make_state([]), counter=2)
    copy = Player.deepcopy(cs.player)
    copy.relics[RelicId.STRIKE_DUMMY].counter = 9
    assert cs.player.relics[RelicId.STRIKE_DUMMY].counter == 2

def test_relics_survive_the_deepcopy_of_a_combat_state():
    cs = with_relic(make_state([strike()], enemy_count=1))
    assert RelicId.STRIKE_DUMMY in CombatState.deepcopy(cs).player.relics


# ---------------------------------------------------------------- Strike Dummy
def test_strike_dummy_adds_three_to_a_strike():
    cs = with_relic(make_state([strike()], enemy_count=1, enemy_hp=100))
    play(cs)
    assert hps(cs) == [100 - 6 - 3]

def test_without_the_relic_a_strike_is_unchanged():
    cs = make_state([strike()], enemy_count=1, enemy_hp=100)
    play(cs)
    assert hps(cs) == [94]

def test_strike_dummy_ignores_other_attacks():
    cs = with_relic(make_state([bash()], enemy_count=1, enemy_hp=100))
    play(cs)
    assert hps(cs) == [92]

def test_strike_dummy_ignores_skills():
    cs = with_relic(make_state([defend()], enemy_count=1))
    play(cs)
    assert cs.player.block == 5

def test_strike_dummy_applies_to_every_hit_of_twin_strike():
    twin = card(CardId.TWIN_STRIKE, 1, CardType.Attack)
    cs = with_relic(make_state([twin], enemy_count=1, enemy_hp=100))
    play(cs)
    assert hps(cs) == [100 - 2 * (5 + 3)]

def test_strike_dummy_applies_to_pommel_strike():
    cs = with_relic(make_state([card(CardId.POMMEL_STRIKE, 1, CardType.Attack)], enemy_count=1, enemy_hp=100))
    cs.player.draw_pile = [defend()]
    play(cs)
    assert hps(cs) == [100 - 9 - 3]

def test_strike_dummy_applies_to_setup_strike():
    cs = with_relic(make_state([card(CardId.SETUP_STRIKE, 1, CardType.Attack)], enemy_count=1, enemy_hp=100))
    play(cs)
    assert hps(cs) == [100 - 7 - 3]

def test_strike_dummy_is_added_before_weak_and_vulnerable():
    cs = with_relic(make_state([strike()], enemy_count=1, enemy_hp=100))
    cs.player.apply_status(StatusId.STRENGTH, 2)
    cs.player.apply_status(StatusId.WEAK, 1)
    cs.enemies[0].apply_status(StatusId.VULNERABLE, 1)
    play(cs)
    assert hps(cs) == [100 - int((6 + 2 + 3) * 0.75 * 1.5)]

def test_strike_dummy_does_not_change_enemy_attacks():
    cs = with_relic(make_state([], enemy_count=1))
    assert CombatSimulator(cs).calculate_damage(10, cs.enemies[0], cs.player) == 10

def test_strike_dummy_adds_nothing_when_no_card_is_being_played():
    cs = with_relic(make_state([], enemy_count=1))
    assert CombatSimulator(cs).calculate_damage(6, cs.player, cs.enemies[0]) == 6

def test_strike_dummy_applies_to_a_strike_played_for_free_by_another_card():
    cs = with_relic(make_state([], enemy_count=1, enemy_hp=100))
    sim = CombatSimulator(cs)
    sim.auto_play(strike())
    assert hps(cs) == [100 - 6 - 3]

def test_the_card_in_play_is_cleared_afterwards():
    cs = with_relic(make_state([strike()], enemy_count=1, enemy_hp=100))
    sim = play(cs)
    assert sim.card_in_play is None

def test_a_card_that_plays_another_card_restores_the_outer_one():
    cs = with_relic(make_state([], enemy_count=1, enemy_hp=100))
    sim = CombatSimulator(cs)
    outer, inner = bash(), strike()
    with sim._playing(outer):
        with sim._playing(inner):
            assert sim.card_in_play is inner
        assert sim.card_in_play is outer
    assert sim.card_in_play is None

def test_a_failed_play_does_not_leave_a_card_in_play():
    cs = with_relic(make_state([strike()], enemy_count=1))
    cs.energy = 0
    sim = CombatSimulator(cs)
    try:
        sim.play_card(0, 0)
    except Exception:
        pass
    assert sim.card_in_play is None

def test_strike_dummy_is_the_strike_tag():
    assert strike().is_strike and not bash().is_strike
    for card_id in STRIKE_CARDS:
        assert card(card_id, 1, CardType.Attack).is_strike

def test_damage_bonus_without_relics_or_card_is_zero():
    cs = make_state([], enemy_count=1)
    assert damage_bonus(cs.player, strike()) == 0
    assert damage_bonus(cs.enemies[0], strike()) == 0
    with_relic(cs)
    assert damage_bonus(cs.player, None) == 0
    assert damage_bonus(cs.player, strike()) == STRIKE_DUMMY_BONUS
