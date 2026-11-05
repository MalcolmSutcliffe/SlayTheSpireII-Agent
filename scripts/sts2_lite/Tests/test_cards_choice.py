"""Cards that make the player pick a card, and Aggression. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState, IllegalActionError
from sts2_lite.Tests.test_cards import make_card, make_state, play, hps
from sts2_lite.status import StatusId


def strike(upgraded=False):
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy, upgraded)

def defend(upgraded=False):
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.Self, upgraded)

def bash():
    return make_card(CardId.BASH, "Bash", CardType.Attack, 2, TargetType.AnyEnemy)

def armaments(upgraded=False):
    return make_card(CardId.ARMAMENTS, "Armaments", CardType.Skill, 1, TargetType.Self, upgraded)

def aggression():
    return make_card(CardId.AGGRESSION, "Aggression", CardType.Power, 1, TargetType.Self)

def state(hand):
    return make_state(hand, enemy_count=1, enemy_hp=100)

def choices(sim):
    return [a for a in sim.get_available_actions() if a["action"] == "choose_card"]


# ---------------------------------------------------------------- Armaments
def test_armaments_gives_five_block():
    cs = state([armaments(), strike()])
    play(cs)
    assert cs.player.block == 5

def test_armaments_block_follows_dexterity():
    cs = state([armaments(), strike()])
    cs.player.apply_status(StatusId.DEXTERITY, 2)
    play(cs)
    assert cs.player.block == 7

def test_armaments_with_one_option_upgrades_it_straight_away():
    cs = state([armaments(), strike()])
    play(cs)
    assert cs.pending_choice is None and cs.player.hand[0].is_upgraded

def test_armaments_with_nothing_to_upgrade_asks_nothing():
    cs = state([armaments(), strike(upgraded=True), Card.create_dazed()])
    play(cs)
    assert cs.pending_choice is None

def test_armaments_asks_which_card_to_upgrade():
    cs = state([armaments(), strike(), defend(), bash()])
    sim = play(cs)
    assert cs.pending_choice is not None
    assert [a["card_index"] for a in choices(sim)] == [0, 1, 2]

def test_armaments_choice_upgrades_the_picked_card_only():
    cs = state([armaments(), strike(), defend(), bash()])
    sim = play(cs)
    sim.perform_action({"action": "choose_card", "card_index": 1})
    assert [c.is_upgraded for c in cs.player.hand] == [False, True, False]
    assert cs.pending_choice is None

def test_identical_cards_are_offered_once():
    cs = state([armaments(), strike(), strike(), strike(), defend()])
    sim = play(cs)
    assert [a["card_index"] for a in choices(sim)] == [0, 3]

def test_an_upgraded_and_a_plain_copy_are_different_options():
    cs = state([armaments(), strike(), strike(upgraded=True), defend()])
    sim = play(cs)
    assert [a["card_index"] for a in choices(sim)] == [0, 2]      # the upgraded strike is not an option

def test_only_choices_are_legal_while_one_is_pending():
    cs = state([armaments(), strike(), defend()])
    sim = play(cs)
    actions = sim.get_available_actions()
    assert {a["action"] for a in actions} == {"choose_card"}

def test_playing_or_ending_the_turn_is_refused_while_choosing():
    cs = state([armaments(), strike(), defend()])
    sim = play(cs)
    with pytest.raises(IllegalActionError):
        sim.play_card(0, 0)
    with pytest.raises(IllegalActionError):
        sim.end_turn()
    assert cs.pending_choice is not None

def test_choosing_a_card_that_is_not_offered_is_refused():
    cs = state([armaments(), strike(), strike(), defend()])
    sim = play(cs)
    with pytest.raises(IllegalActionError):
        sim.choose_card(1)
    with pytest.raises(IllegalActionError):
        sim.choose_card(9)
    assert cs.pending_choice is not None

def test_choosing_with_nothing_pending_is_refused():
    cs = state([strike()])
    with pytest.raises(IllegalActionError):
        CombatSimulator(cs).choose_card(0)

def test_play_resumes_after_the_choice():
    cs = state([armaments(), strike(), defend()])
    sim = play(cs)
    sim.perform_action({"action": "choose_card", "card_index": 0})
    assert {a["action"] for a in sim.get_available_actions()} >= {"play_card", "end_turn"}
    sim.play_card(0, 0)
    assert hps(cs) == [91]

def test_upgraded_armaments_upgrades_the_whole_hand():
    cs = state([armaments(upgraded=True), strike(), defend(), strike(upgraded=True), Card.create_dazed()])
    play(cs)
    assert cs.pending_choice is None
    assert [c.is_upgraded for c in cs.player.hand] == [True, True, True, False]

def test_armaments_goes_to_the_discard_pile_unupgraded():
    cs = state([armaments(), strike(), defend()])
    play(cs)
    assert [c.is_upgraded for c in cs.player.discard_pile] == [False]

def test_pending_choice_is_copied_with_the_state():
    cs = state([armaments(), strike(), defend()])
    play(cs)
    copy = CombatState.deepcopy(cs)
    assert copy.pending_choice is not cs.pending_choice
    assert copy.pending_choice.indices == cs.pending_choice.indices and copy.pending_choice.kind == "upgrade"
    CombatSimulator(copy).choose_card(0)
    assert cs.pending_choice is not None and not cs.player.hand[0].is_upgraded

def test_a_choice_in_one_branch_leaves_the_other_cards_alone():
    cs = state([armaments(), strike(), defend()])
    play(cs)
    a, b = CombatState.deepcopy(cs), CombatState.deepcopy(cs)
    CombatSimulator(a).choose_card(0)
    CombatSimulator(b).choose_card(1)
    assert [c.is_upgraded for c in a.player.hand] == [True, False]
    assert [c.is_upgraded for c in b.player.hand] == [False, True]
    assert [c.is_upgraded for c in cs.player.hand] == [False, False]

def test_an_upgraded_card_costs_its_new_price():
    barricade = make_card(CardId.BARRICADE, "Barricade", CardType.Power, 3, TargetType.Self)
    cs = state([armaments(), barricade])
    cs.energy = 3
    sim = play(cs)
    assert cs.player.hand[0].energy_cost == 2 and cs.energy == 2
    assert any(a["action"] == "play_card" for a in sim.get_available_actions())

def test_random_playout_through_choices_never_gets_stuck():
    for seed in range(15):
        rng.seed(seed)
        cs = make_state([], enemy_count=2, enemy_hp=60)
        cs.player.draw_pile = [rng.choice([strike, defend, armaments, bash])() for _ in range(30)]
        sim = CombatSimulator(cs)
        for _ in range(60):
            if sim.is_over:
                break
            sim.perform_action(rng.choice(sim.get_available_actions()))


# ---------------------------------------------------------------- Aggression
def test_aggression_card_applies_the_power():
    cs = state([aggression()])
    play(cs)
    assert cs.player.status_amount(StatusId.AGGRESSION) == 1 and cs.energy == 2

def test_aggression_returns_an_upgraded_attack_from_the_discard_pile():
    cs = state([])
    cs.player.discard_pile = [strike(), defend()]
    cs.player.draw_pile = [bash() for _ in range(6)]
    cs.player.apply_status(StatusId.AGGRESSION, 1)
    CombatSimulator(cs).end_turn()
    assert (cs.player.hand[0].card_id, cs.player.hand[0].is_upgraded) == (CardId.STRIKE_IRONCLAD, True)
    assert [c.card_id for c in cs.player.discard_pile] == [CardId.DEFEND_IRONCLAD]

def test_aggression_acts_before_the_new_hand_is_drawn():
    cs = state([])
    cs.player.discard_pile = [strike()]
    cs.player.draw_pile = [defend() for _ in range(7)]
    cs.player.apply_status(StatusId.AGGRESSION, 1)
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == 6 and cs.player.hand[0].is_upgraded
    assert len(cs.player.draw_pile) == 2

def test_aggression_takes_attacks_from_this_turns_discards():
    cs = state([strike(), defend()])
    cs.player.apply_status(StatusId.AGGRESSION, 1)
    CombatSimulator(cs).end_turn()
    assert any(c.card_id == CardId.STRIKE_IRONCLAD and c.is_upgraded for c in cs.player.hand)

def test_aggression_does_nothing_with_no_attacks_in_the_discard_pile():
    cs = state([])
    cs.player.discard_pile = [defend()]
    cs.player.draw_pile = [bash() for _ in range(6)]
    cs.player.apply_status(StatusId.AGGRESSION, 1)
    CombatSimulator(cs).end_turn()
    assert [c.card_id for c in cs.player.hand] == [CardId.BASH] * 5

def test_aggression_amount_is_how_many_come_back():
    cs = state([])
    cs.player.discard_pile = [strike(), strike(), strike(), strike()]
    cs.player.draw_pile = [defend() for _ in range(6)]
    cs.player.apply_status(StatusId.AGGRESSION, 3)
    CombatSimulator(cs).end_turn()
    assert [c.card_id for c in cs.player.hand[:3]] == [CardId.STRIKE_IRONCLAD] * 3
    assert all(c.is_upgraded for c in cs.player.hand[:3]) and len(cs.player.discard_pile) == 1

def test_aggression_takes_everything_when_there_are_few_attacks():
    cs = state([])
    cs.player.discard_pile = [strike(), bash()]
    cs.player.apply_status(StatusId.AGGRESSION, 3)
    CombatSimulator(cs).end_turn()
    assert len(cs.player.hand) == 2 and cs.player.discard_pile == []

def test_aggression_picks_randomly_among_the_attacks():
    seen = set()
    for seed in range(30):
        rng.seed(seed)
        cs = state([])
        cs.player.discard_pile = [strike(), bash(), defend()]
        cs.player.apply_status(StatusId.AGGRESSION, 1)
        CombatSimulator(cs).end_turn()
        seen.add(cs.player.hand[0].card_id)
    assert seen == {CardId.STRIKE_IRONCLAD, CardId.BASH}

def test_aggression_returns_an_already_upgraded_attack_as_it_is():
    cs = state([])
    cs.player.discard_pile = [strike(upgraded=True)]
    cs.player.apply_status(StatusId.AGGRESSION, 1)
    CombatSimulator(cs).end_turn()
    assert cs.player.hand[0].is_upgraded and cs.player.discard_pile == []

def test_aggression_cannot_overfill_the_hand():
    cs = state([])
    cs.player.discard_pile = [strike() for _ in range(3)]
    cs.player.hand = [defend() for _ in range(10)]
    cs.player.apply_status(StatusId.AGGRESSION, 3)
    CombatSimulator(cs)._start_player_turn()
    assert len(cs.player.hand) == 10 and len(cs.player.discard_pile) == 3

def test_aggression_upgrade_does_not_change_the_card_in_other_branches():
    cs = state([])
    original = strike()
    cs.player.discard_pile = [original]
    cs.player.apply_status(StatusId.AGGRESSION, 1)
    other = CombatState.deepcopy(cs)
    CombatSimulator(cs).end_turn()
    assert not original.is_upgraded and not other.player.discard_pile[0].is_upgraded

def test_upgraded_returned_attack_hits_harder():
    cs = state([])
    cs.player.discard_pile = [strike()]
    cs.player.apply_status(StatusId.AGGRESSION, 1)
    sim = CombatSimulator(cs)
    sim.end_turn()
    sim.play_card(0, 0)
    assert hps(cs) == [91]

def test_bridge_ids_load():
    from sts2_lite.status import StatusInstance
    assert StatusInstance.from_dict({"id": "AGGRESSION_POWER", "amount": 1}).status_id == StatusId.AGGRESSION

def test_same_card_at_different_costs_are_different_options():
    cheap = strike()
    cheap.energy_cost = 0
    cs = state([armaments(), strike(), cheap, defend()])
    sim = play(cs)
    assert [a["card_index"] for a in choices(sim)] == [0, 1, 2]


# ---------------------------------------------------------------- loading a card selection screen
def selection_state():
    import json
    from pathlib import Path
    raw = json.loads((Path(__file__).parent / "data" / "card_selection.json").read_text())
    return raw, CombatState.from_dict(raw)

def test_selection_screen_loads_the_fight_behind_it():
    raw, cs = selection_state()
    assert cs.energy == 2 and cs.max_energy == 3 and cs.player.block == 5
    assert cs.turn_number == 1 and [e.enemy_id for e in cs.enemies] == ["NIBBIT_0"]
    assert [c.card_id for c in cs.player.hand] == [CardId.STRIKE_IRONCLAD, CardId.DEFEND_IRONCLAD, CardId.BASH, CardId.STRIKE_IRONCLAD]

def test_selection_screen_becomes_a_pending_upgrade_choice():
    raw, cs = selection_state()
    assert cs.pending_choice.kind == "upgrade"
    sim = CombatSimulator(cs)
    assert [a["card_index"] for a in choices(sim)] == [0, 1, 2]      # the second Strike is the same option as the first
    assert {a["action"] for a in sim.get_available_actions()} == {"choose_card"}

def test_choosing_on_a_loaded_selection_screen_upgrades_that_card():
    raw, cs = selection_state()
    sim = CombatSimulator(cs)
    sim.perform_action({"action": "choose_card", "card_index": 2})
    assert [c.is_upgraded for c in cs.player.hand] == [False, False, True, False]
    assert cs.pending_choice is None

def test_ordinary_combat_states_have_no_pending_choice():
    from sts2_lite.Tests.captures import load
    assert load("nibbit", "butt").pending_choice is None

def test_unknown_selection_modes_are_reported():
    raw, _ = selection_state()
    raw["mode"] = "mystery_select"
    with pytest.raises(ValueError):
        CombatState.from_dict(raw)
