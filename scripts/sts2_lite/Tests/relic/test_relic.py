import json
import pytest
from sts2_lite.card import Card, CardId, CardType, TargetType, STRIKE_CARDS
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.player import Player
from sts2_lite.relic import RelicId, RelicInstance, damage_bonus, DAMAGE_ADDITIVE, STRIKE_DUMMY_BONUS
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_card, make_state, play, hps
from pathlib import Path
from sts2_lite.Tests.relic.test_always_on import held, strike as strike_energy_victory, card as card_hand_draw, defend as defend_hand_draw, state, relic, plays
from data_paths import RELICS


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
    pl = Player.from_dict(bridge_player([bridge_relic("FISHING_ROD"), bridge_relic("STRIKE_DUMMY"),
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


RELICS = RELICS

def capture(name):
    return json.loads((RELICS / f"{name}.json").read_text())


# ---------------------------------------------------------------- Bread (Bread.ModifyMaxEnergy)
def test_bread_loads():
    assert RelicInstance.from_dict({"id": "BREAD", "counter": None}).relic_id == RelicId.BREAD

def test_bread_turn_1_to_2_matches_capture():
    cs = CombatState.from_dict(capture("bread_turn_1"))
    CombatSimulator(cs).end_turn()
    expected = capture("bread_turn_2")["max_energy"]
    assert cs.turn_number == 2 and cs.max_energy == expected and cs.energy == expected

def test_bread_turn_2_capture_already_includes_it():
    cs = CombatState.from_dict(capture("bread_turn_2"))
    before = cs.max_energy
    CombatSimulator(cs).end_turn()
    assert cs.max_energy == before

def test_no_bread_no_gain():
    cs = make_state([], enemy_count=1, enemy_hp=100)
    cs.player.draw_pile = [strike_energy_victory() for _ in range(10)]
    CombatSimulator(cs).end_turn()
    assert cs.max_energy == 3


# ---------------------------------------------------------------- Meat on the Bone (MeatOnTheBone.AfterCombatVictoryEarly)
def kill_last_enemy(hp, max_hp=80, *relic_ids):
    cs = held(make_state([strike_energy_victory()], enemy_count=1, enemy_hp=5), *relic_ids)
    cs.player.current_hp, cs.player.max_hp = hp, max_hp
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert sim.is_over
    return cs

def test_meat_on_the_bone_heals_at_half_or_less():
    assert kill_last_enemy(40, 80, RelicId.MEAT_ON_THE_BONE).player.current_hp == 52

def test_meat_on_the_bone_does_nothing_above_half():
    assert kill_last_enemy(41, 80, RelicId.MEAT_ON_THE_BONE).player.current_hp == 41

def test_meat_on_the_bone_threshold_rounds_down():
    assert kill_last_enemy(37, 75, RelicId.MEAT_ON_THE_BONE).player.current_hp == 49
    assert kill_last_enemy(38, 75, RelicId.MEAT_ON_THE_BONE).player.current_hp == 38

def test_meat_on_the_bone_heal_is_capped():
    assert kill_last_enemy(5, 10, RelicId.MEAT_ON_THE_BONE).player.current_hp == 10

def test_no_heal_without_the_relic():
    assert kill_last_enemy(10, 80).player.current_hp == 10

def test_no_heal_on_a_loss():
    cs = held(make_state([], enemy_count=1, enemy_hp=100), RelicId.MEAT_ON_THE_BONE)
    cs.player.current_hp = 0
    sim = CombatSimulator(cs)
    assert sim.is_over and cs.player.current_hp == 0

def test_victory_heal_is_applied_once():
    cs = kill_last_enemy(20, 80, RelicId.MEAT_ON_THE_BONE)
    copy = CombatState.deepcopy(cs)
    CombatSimulator(copy)                       # a new simulator on a finished fight
    assert copy.player.current_hp == 32

def test_victory_with_only_minions_left_heals():
    cs = held(make_state([strike_energy_victory()], enemy_count=2, enemy_hp=5), RelicId.MEAT_ON_THE_BONE)
    cs.enemies[1].is_minion = True
    cs.player.current_hp = 20
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert sim.is_over and cs.player.current_hp == 32


# ---------------------------------------------------------------- Burning Blood / Black Blood (AfterCombatVictory)
def test_burning_blood_heals_6_on_victory():
    assert kill_last_enemy(50, 80, RelicId.BURNING_BLOOD).player.current_hp == 56

def test_black_blood_heals_12_on_victory():
    assert kill_last_enemy(50, 80, RelicId.BLACK_BLOOD).player.current_hp == 62

def test_burning_blood_heal_is_capped():
    assert kill_last_enemy(78, 80, RelicId.BURNING_BLOOD).player.current_hp == 80

def test_meat_on_the_bone_checks_hp_before_burning_blood():
    # 40/80 qualifies for Meat; healing Burning Blood first (46) would not
    assert kill_last_enemy(40, 80, RelicId.BURNING_BLOOD, RelicId.MEAT_ON_THE_BONE).player.current_hp == 58

def test_burning_blood_loads_from_capture():
    cs = CombatState.from_dict(capture("bread_turn_1"))
    assert RelicId.BURNING_BLOOD in cs.player.relics

def test_no_victory_heal_on_a_loss():
    cs = held(make_state([], enemy_count=1, enemy_hp=100), RelicId.BURNING_BLOOD)
    cs.player.current_hp = 0
    CombatSimulator(cs)
    assert cs.player.current_hp == 0


GROUP_3 = ["PAELS_BLOOD", "RING_OF_THE_DRAKE", "POLLINOUS_CORE", "FIDDLE", "SNECKO_EYE"]

def deck(cs):
    cs.player.draw_pile = [defend_hand_draw() for _ in range(40)]
    return cs

def hand_sizes(cs, turns):
    sim, sizes = CombatSimulator(deck(cs)), []
    for _ in range(turns):
        sim.end_turn()
        sizes.append(len(cs.player.hand))
    return sizes

def pommel_strike():
    return card_hand_draw(CardId.POMMEL_STRIKE, 1, CardType.Attack)


@pytest.mark.parametrize("bridge_id", GROUP_3)
def test_loads_from_the_bridge(bridge_id):
    assert RelicInstance.from_dict({"id": bridge_id, "counter": None}).relic_id == RelicId[bridge_id]

@pytest.mark.parametrize("relic_id, size", [(RelicId.PAELS_BLOOD, 6), (RelicId.SNECKO_EYE, 7), (RelicId.FIDDLE, 7)])
def test_fixed_hand_draw(relic_id, size):
    assert hand_sizes(state([], relic_id), 2) == [size, size]

def test_no_relic_draws_5():
    assert hand_sizes(state([]), 1) == [5]

def test_bonuses_stack():
    assert hand_sizes(state([], RelicId.PAELS_BLOOD, RelicId.FIDDLE), 1) == [8]


# ---------------------------------------------------------------- Ring of the Drake (TurnNumber <= 3)
def test_ring_of_the_drake_through_turn_3():
    assert hand_sizes(state([], RelicId.RING_OF_THE_DRAKE), 3) == [7, 7, 5]


# ---------------------------------------------------------------- Pollinous Core (TurnsSeen, every 4th turn)
def test_pollinous_core_every_4_turns():
    cs = state([], RelicId.POLLINOUS_CORE)
    relic(cs, RelicId.POLLINOUS_CORE).counter = 1          # turn 1 already seen
    assert hand_sizes(cs, 5) == [5, 5, 7, 5, 5]
    assert relic(cs, RelicId.POLLINOUS_CORE).counter == 2

def test_pollinous_core_flash_reading_of_4_is_0():
    cs = state([], RelicId.POLLINOUS_CORE)
    relic(cs, RelicId.POLLINOUS_CORE).counter = 4
    assert hand_sizes(cs, 1) == [5] and relic(cs, RelicId.POLLINOUS_CORE).counter == 1

def test_pollinous_core_bonus_is_one_turn():
    cs = state([], RelicId.POLLINOUS_CORE)
    relic(cs, RelicId.POLLINOUS_CORE).counter = 3
    assert hand_sizes(cs, 2) == [7, 5]


# ---------------------------------------------------------------- Fiddle (ShouldDraw: hand draw only)
def test_fiddle_blocks_card_draw():
    cs = deck(state([pommel_strike()], RelicId.FIDDLE))
    plays(cs, (0, 0))
    assert cs.player.hand == []

def test_fiddle_blocks_relic_draw():
    cs = deck(state([card_hand_draw(CardId.INFLAME, 1, CardType.Power, TargetType.Self)], RelicId.FIDDLE, RelicId.GAME_PIECE))
    plays(cs, (0, 0))
    assert cs.player.hand == []

def test_without_fiddle_cards_draw():
    cs = deck(state([pommel_strike()]))
    plays(cs, (0, 0))
    assert len(cs.player.hand) == 1
