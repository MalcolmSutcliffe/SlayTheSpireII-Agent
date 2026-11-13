import pytest
import json
from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState, IllegalActionError
from sts2_lite.Tests.card.test_card import make_card, make_state, play, hps
from sts2_lite.status import StatusId
from pathlib import Path
from sts2_lite.selection import game_index
from data_paths import CARDS


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
    sim = play(cs)
    assert cs.player.discard_pile == []         # the card reaches its pile once the choice is answered
    sim.choose_card(0)
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
    raw = json.loads((CARDS / "card_selection.json").read_text())
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

def test_exhaust_one_card_prompt_loads_as_an_exhaust_pick():
    """A pick the sim did not expect (Cascade played an unforeseen Brand): the screen's prompt says what it is for."""
    import json
    from pathlib import Path
    cs = CombatState.from_dict(json.loads((CARDS / "card_selection_exhaust.json").read_text()))
    pending = cs.pending_choice
    assert pending.kind == "exhaust" and pending.amount == 0 and pending.pile == "hand"
    assert len(pending.indices) == 6 and pending.indices == sorted(pending.indices)      # the three Defends and two Strikes count once each
    hand = len(cs.player.hand)
    sim = CombatSimulator(cs)
    sim.perform_action({"action": "choose_card", "card_index": pending.indices[0]})
    assert cs.pending_choice is None and len(cs.player.hand) == hand - 1 and len(cs.player.exhaust_pile) == 2

def test_unknown_selection_modes_are_reported():
    raw, _ = selection_state()
    raw["mode"] = "mystery_select"
    with pytest.raises(ValueError):
        CombatState.from_dict(raw)


def test_tear_asunder_text_gives_the_times_hp_was_lost():
    """Captured (engine_mismatches): the sim counted 16 hits where the game's text said "Hits 12 times"; the text is the game's own count."""
    from sts2_lite.Tests.captures import raw
    state = raw("nibbit", "butt")
    card = dict(state["hand"][0])
    card.update({"id": "TEAR_ASUNDER", "name": "Tear Asunder", "type": "Attack", "cost": "2", "target_type": "AnyEnemy",
                 "description": "Deal 7 damage. Hits an additional time for each time you lost HP this combat. (Hits 12 times)"})
    state["hand"] = [card] + state["hand"][1:]
    cs = CombatState.from_dict(state)
    assert cs.player.hp_loss_events == 11
    earlier = CombatState.deepcopy(cs)
    earlier.player.hp_loss_events = 15                  # what the sim had counted
    cs.carry_combat_counters(earlier)
    assert cs.player.hp_loss_events == 11               # the game's number wins over the larger simulated one


def strike(upgraded=False):
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy, upgraded)

def defend(upgraded=False):
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.Self, upgraded)

def bash():
    return make_card(CardId.BASH, "Bash", CardType.Attack, 2, TargetType.AnyEnemy)

def headbutt(upgraded=False):
    return make_card(CardId.HEADBUTT, "Headbutt", CardType.Attack, 1, TargetType.AnyEnemy, upgraded)

def true_grit(upgraded=False):
    return make_card(CardId.TRUE_GRIT, "True Grit", CardType.Skill, 1, TargetType.Self, upgraded)

def burning_pact(upgraded=False):
    return make_card(CardId.BURNING_PACT, "Burning Pact", CardType.Skill, 1, TargetType.Self, upgraded)

def havoc(upgraded=False):
    return make_card(CardId.HAVOC, "Havoc", CardType.Skill, 1 if not upgraded else 0, TargetType.Self, upgraded)

def state(hand):
    return make_state(hand, enemy_count=1, enemy_hp=100)

def choices(sim):
    return [a for a in sim.get_available_actions() if a["action"] == "choose_card"]

def ids(cards):
    return [c.card_id for c in cards]


# ---------------------------------------------------------------- Headbutt
def test_headbutt_deals_nine_and_upgraded_twelve():
    cs = state([headbutt()])
    play(cs)
    assert hps(cs) == [91]
    cs = state([headbutt(upgraded=True)])
    play(cs)
    assert hps(cs) == [88]

def test_headbutt_with_an_empty_discard_pile_asks_nothing():
    cs = state([headbutt()])
    play(cs)
    assert cs.pending_choice is None and cs.player.draw_pile == []

def test_headbutt_with_one_discard_takes_it_without_asking():
    cs = state([headbutt()])
    cs.player.discard_pile = [defend()]
    play(cs)
    assert cs.pending_choice is None
    assert ids(cs.player.draw_pile) == [CardId.DEFEND_IRONCLAD] and cs.player.discard_pile[0].card_id == CardId.HEADBUTT

def test_headbutt_asks_which_discarded_card_goes_on_top():
    cs = state([headbutt()])
    cs.player.discard_pile = [strike(), defend(), bash(), strike()]
    sim = play(cs)
    options = choices(sim)
    assert [a["card_index"] for a in options] == [0, 1, 2]
    assert {a["pile"] for a in options} == {"discard"}
    assert [(a["card_id"], a["is_upgraded"]) for a in options] == [("STRIKE_IRONCLAD", False), ("DEFEND_IRONCLAD", False), ("BASH", False)]

def test_headbutt_choice_puts_the_card_on_top_of_the_draw_pile():
    cs = state([headbutt()])
    cs.player.draw_pile = [strike(), strike()]
    cs.player.discard_pile = [defend(), bash()]
    sim = play(cs)
    sim.perform_action({"action": "choose_card", "card_index": 1})
    assert ids(cs.player.draw_pile) == [CardId.STRIKE_IRONCLAD, CardId.STRIKE_IRONCLAD, CardId.BASH]
    assert ids(cs.player.discard_pile) == [CardId.DEFEND_IRONCLAD, CardId.HEADBUTT]

def test_the_picked_card_is_the_next_one_drawn():
    cs = state([headbutt()])
    cs.player.draw_pile = [strike(), strike(), strike(), strike(), strike(), strike()]
    cs.player.discard_pile = [defend(), bash()]
    sim = play(cs)
    sim.perform_action({"action": "choose_card", "card_index": 1})
    sim.end_turn()
    assert cs.player.hand[0].card_id == CardId.BASH

def test_headbutt_cannot_choose_its_own_card():
    cs = state([headbutt()])
    cs.player.discard_pile = [defend(), bash()]
    sim = play(cs)
    assert all(a["card_index"] < 2 for a in choices(sim))

def test_headbutt_choice_is_only_legal_action_and_refuses_bad_index():
    cs = state([headbutt()])
    cs.player.discard_pile = [defend(), bash()]
    sim = play(cs)
    with pytest.raises(IllegalActionError):
        sim.choose_card(2)
    with pytest.raises(IllegalActionError):
        sim.end_turn()

def test_headbutt_choice_does_not_leak_between_copies():
    cs = state([headbutt()])
    cs.player.discard_pile = [defend(), bash()]
    play(cs)
    a, b = CombatState.deepcopy(cs), CombatState.deepcopy(cs)
    CombatSimulator(a).choose_card(0)
    CombatSimulator(b).choose_card(1)
    assert ids(a.player.draw_pile) == [CardId.DEFEND_IRONCLAD] and ids(b.player.draw_pile) == [CardId.BASH]
    assert cs.player.draw_pile == [] and cs.pending_choice is not None

def test_headbutt_deals_its_damage_before_the_choice():
    cs = state([headbutt()])
    cs.player.discard_pile = [defend(), bash()]
    play(cs)
    assert hps(cs) == [91]

def test_game_index_matches_by_card_identity():
    raw = json.loads((CARDS / "ironclad" / "headbutt_example.json").read_text())
    cards = raw["cards"]
    assert game_index({"card_id": "STRIKE_IRONCLAD", "is_upgraded": False}, cards) == 4
    assert game_index({"card_id": "STRIKE_IRONCLAD", "is_upgraded": True}, cards) == 3
    assert game_index({"card_id": "DEFEND_IRONCLAD", "is_upgraded": False}, cards) == 0
    assert game_index({"card_id": "ARMAMENTS", "is_upgraded": False}, cards) == 1
    assert game_index({"card_id": "BASH", "is_upgraded": False}, cards) is None

def test_actions_from_a_pile_choice_can_be_matched_to_the_game_list():
    raw = json.loads((CARDS / "ironclad" / "headbutt_example.json").read_text())
    cs = state([headbutt()])
    cs.player.discard_pile = [defend(), make_card(CardId.ARMAMENTS, "Armaments", CardType.Skill, 1, TargetType.Self),
                              strike(upgraded=True), strike()]
    sim = play(cs)
    mapped = [game_index(a, raw["cards"]) for a in choices(sim)]
    assert mapped == [0, 1, 3, 4]


# ---------------------------------------------------------------- True Grit
def test_true_grit_block_and_upgraded_block():
    cs = state([true_grit()])
    play(cs)
    assert cs.player.block == 7
    cs = state([true_grit(upgraded=True)])
    play(cs)
    assert cs.player.block == 9

def test_true_grit_exhausts_a_random_card_when_not_upgraded():
    seen = set()
    for seed in range(40):
        rng.seed(seed)
        cs = state([true_grit(), strike(), defend(), bash()])
        play(cs)
        assert cs.pending_choice is None and len(cs.player.exhaust_pile) == 1
        seen.add(cs.player.exhaust_pile[0].card_id)
    assert seen == {CardId.STRIKE_IRONCLAD, CardId.DEFEND_IRONCLAD, CardId.BASH}

def test_true_grit_random_exhaust_uses_no_randomness_with_one_card():
    cs = state([true_grit(), strike()])
    before = rng.calls
    play(cs)
    assert rng.calls == before and ids(cs.player.exhaust_pile) == [CardId.STRIKE_IRONCLAD]

def test_true_grit_with_an_empty_hand_just_blocks():
    cs = state([true_grit()])
    play(cs)
    assert cs.player.exhaust_pile == [] and cs.player.block == 7

def test_true_grit_exhaust_fires_the_exhaust_hooks():
    cs = state([true_grit(), strike()])
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 3)
    play(cs)
    assert cs.player.block == 10 and cs.player.cards_exhausted_this_turn == 1

def test_upgraded_true_grit_lets_the_player_choose():
    cs = state([true_grit(upgraded=True), strike(), defend(), strike()])
    sim = play(cs)
    assert [a["card_index"] for a in choices(sim)] == [0, 1]
    sim.perform_action({"action": "choose_card", "card_index": 1})
    assert ids(cs.player.exhaust_pile) == [CardId.DEFEND_IRONCLAD] and ids(cs.player.hand) == [CardId.STRIKE_IRONCLAD] * 2
    assert cs.pending_choice is None

def test_upgraded_true_grit_with_one_card_exhausts_it_at_once():
    cs = state([true_grit(upgraded=True), strike()])
    play(cs)
    assert cs.pending_choice is None and ids(cs.player.exhaust_pile) == [CardId.STRIKE_IRONCLAD]

def test_upgraded_true_grit_can_exhaust_a_status_card():
    cs = state([true_grit(upgraded=True), Card.create_dazed(), strike()])
    sim = play(cs)
    assert len(choices(sim)) == 2
    sim.perform_action({"action": "choose_card", "card_index": 0})
    assert ids(cs.player.exhaust_pile) == [CardId.DAZED]

def test_true_grit_blocks_before_the_choice():
    cs = state([true_grit(upgraded=True), strike(), defend()])
    play(cs)
    assert cs.player.block == 9


# ---------------------------------------------------------------- Burning Pact
def test_burning_pact_exhausts_the_choice_then_draws_two():
    cs = state([burning_pact(), strike(), defend()])
    cs.player.draw_pile = [bash(), bash(), bash()]
    sim = play(cs)
    assert cs.player.hand and len(cs.player.hand) == 2 and cs.player.cards_drawn == 0
    sim.perform_action({"action": "choose_card", "card_index": 0})
    assert ids(cs.player.exhaust_pile) == [CardId.STRIKE_IRONCLAD]
    assert ids(cs.player.hand) == [CardId.DEFEND_IRONCLAD, CardId.BASH, CardId.BASH]

def test_burning_pact_upgraded_draws_three():
    cs = state([burning_pact(upgraded=True), strike(), defend()])
    cs.player.draw_pile = [bash(), bash(), bash(), bash()]
    sim = play(cs)
    sim.perform_action({"action": "choose_card", "card_index": 1})
    assert len(cs.player.hand) == 1 + 3

def test_burning_pact_with_a_single_card_does_it_all_at_once():
    cs = state([burning_pact(), strike()])
    cs.player.draw_pile = [bash(), bash()]
    play(cs)
    assert cs.pending_choice is None
    assert ids(cs.player.exhaust_pile) == [CardId.STRIKE_IRONCLAD] and len(cs.player.hand) == 2

def test_burning_pact_with_an_empty_hand_still_draws():
    cs = state([burning_pact()])
    cs.player.draw_pile = [bash(), bash(), bash()]
    play(cs)
    assert cs.pending_choice is None and len(cs.player.hand) == 2 and cs.player.exhaust_pile == []

def test_burning_pact_draw_counts_as_drawing():
    cs = state([burning_pact(), strike(), defend()])
    cs.player.draw_pile = [bash(), bash(), bash()]
    sim = play(cs)
    sim.choose_card(0)
    assert cs.player.cards_drawn == 2

def test_burning_pact_exhaust_triggers_dark_embrace_and_feel_no_pain():
    cs = state([burning_pact(), strike(), defend()])
    cs.player.draw_pile = [bash() for _ in range(8)]
    cs.player.apply_status(StatusId.DARK_EMBRACE, 1)
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 2)
    sim = play(cs)
    sim.choose_card(0)
    assert cs.player.block == 2 and len(cs.player.hand) == 1 + 1 + 2

def test_burning_pact_is_stuck_until_a_choice_is_made():
    cs = state([burning_pact(), strike(), defend()])
    sim = play(cs)
    with pytest.raises(IllegalActionError):
        sim.end_turn()
    assert {a["action"] for a in sim.get_available_actions()} == {"choose_card"}

def test_burning_pact_options_do_not_include_itself():
    cs = state([burning_pact(), strike(), defend()])
    sim = play(cs)
    assert [a["card_index"] for a in choices(sim)] == [0, 1] and all(a["pile"] == "hand" for a in choices(sim))

def test_amount_survives_copying_the_state():
    cs = state([burning_pact(), strike(), defend()])
    cs.player.draw_pile = [bash(), bash(), bash()]
    play(cs)
    copy = CombatState.deepcopy(cs)
    CombatSimulator(copy).choose_card(0)
    assert len(copy.player.hand) == 3 and len(cs.player.hand) == 2


# ---------------------------------------------------------------- Havoc
def test_havoc_plays_the_top_card_and_exhausts_it():
    cs = state([havoc()])
    cs.player.draw_pile = [defend(), strike()]
    play(cs)
    assert hps(cs) == [94] and ids(cs.player.exhaust_pile) == [CardId.STRIKE_IRONCLAD]
    assert ids(cs.player.draw_pile) == [CardId.DEFEND_IRONCLAD]

def test_havoc_does_not_spend_energy_for_the_other_card():
    cs = state([havoc()])
    cs.player.draw_pile = [bash()]
    play(cs)
    assert cs.energy == 2 and hps(cs) == [92]

def test_havoc_upgraded_is_free():
    cs = state([havoc(upgraded=True)])
    cs.player.draw_pile = [bash()]
    play(cs)
    assert cs.energy == 3

def test_havoc_skill_card_is_played_and_exhausted():
    cs = state([havoc()])
    cs.player.draw_pile = [defend()]
    play(cs)
    assert cs.player.block == 5 and ids(cs.player.exhaust_pile) == [CardId.DEFEND_IRONCLAD]

def test_havoc_shuffles_the_discard_pile_when_the_draw_pile_is_empty():
    cs = state([havoc()])
    cs.player.discard_pile = [defend()]
    play(cs)
    assert ids(cs.player.exhaust_pile) == [CardId.DEFEND_IRONCLAD] and cs.player.draw_pile == []

def test_havoc_with_no_cards_anywhere_does_nothing():
    cs = state([havoc()])
    play(cs)
    assert cs.player.exhaust_pile == [] and cs.energy == 2

def test_havoc_exhausts_a_status_card_without_playing_it():
    cs = state([havoc()])
    cs.player.draw_pile = [Card.create_dazed()]
    play(cs)
    assert ids(cs.player.exhaust_pile) == [CardId.DAZED]

def test_havoc_exhaust_hooks_fire_for_the_other_card():
    cs = state([havoc()])
    cs.player.draw_pile = [defend()]
    cs.player.apply_status(StatusId.FEEL_NO_PAIN, 4)
    play(cs)
    assert cs.player.block == 5 + 4

def test_havoc_power_is_played_and_gone():
    cs = state([havoc()])
    cs.player.draw_pile = [make_card(CardId.DEMON_FORM, "Demon Form", CardType.Power, 3, TargetType.Self)]
    play(cs)
    assert cs.player.status_amount(StatusId.DEMON_FORM) == 2
    assert cs.player.exhaust_pile == [] and cs.player.discard_pile[0].card_id == CardId.HAVOC

def test_havoc_counts_as_a_chance_event():
    cs = state([havoc()])
    cs.player.draw_pile = [defend(), strike()]
    play(cs)
    assert cs.player.unknown_draws == 1

def test_havoc_can_kill_and_end_the_fight():
    cs = state([havoc()])
    cs.enemies[0].current_hp = 5
    cs.player.draw_pile = [strike()]
    sim = play(cs)
    assert sim.is_over

def test_havoc_attack_picks_a_random_target_among_several():
    seen = set()
    for seed in range(30):
        rng.seed(seed)
        cs = make_state([havoc()], enemy_count=3, enemy_hp=50)
        cs.player.draw_pile = [strike()]
        play(cs)
        seen.add(hps(cs).index(44))
    assert seen == {0, 1, 2}

def test_havoc_leaves_its_own_card_in_the_discard_pile():
    cs = state([havoc()])
    cs.player.draw_pile = [defend()]
    play(cs)
    assert ids(cs.player.discard_pile) == [CardId.HAVOC]

def test_havoc_cost_drops_when_upgraded():
    c = make_card(CardId.HAVOC, "Havoc", CardType.Skill, 1, TargetType.Self)
    assert c.upgraded_copy().energy_cost == 0


# ---------------------------------------------------------------- whole fights
def test_random_playouts_with_all_four_cards_never_get_stuck():
    for seed in range(20):
        rng.seed(seed)
        cs = make_state([], enemy_count=2, enemy_hp=60)
        makers = [strike, defend, bash, headbutt, true_grit, burning_pact, havoc]
        cs.player.draw_pile = [rng.choice(makers)() for _ in range(30)]
        sim = CombatSimulator(cs)
        for _ in range(80):
            if sim.is_over:
                break
            sim.perform_action(rng.choice(sim.get_available_actions()))


# ---------------------------------------------------------------- Neow's Fury
def strike_card():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def neows_fury():
    return make_card(CardId.NEOWS_FURY, "Neow's Fury", CardType.Attack, 1, TargetType.AnyEnemy)

def with_discard(hand, discard):
    cs = state(hand)
    cs.player.discard_pile = list(discard)
    return cs

def test_neows_fury_deals_ten():
    cs = state([neows_fury()])
    play(cs)
    assert hps(cs) == [90]

def test_neows_fury_is_always_optional():
    """Captured: "Choose up to 2 cards" is asked even when the discard pile holds only two."""
    cs = with_discard([neows_fury()], [bash(), headbutt()])
    sim = play(cs)
    assert {a["action"] for a in sim.get_available_actions()} == {"choose_card", "confirm_choice"}
    sim.perform_action({"action": "confirm_choice"})
    assert cs.pending_choice is None and ids(cs.player.hand) == []

def test_neows_fury_can_stop_after_one_pick():
    cs = with_discard([neows_fury()], [bash(), headbutt(), strike_card()])
    sim = play(cs)
    sim.choose_card(0)
    assert ids(cs.player.hand) == [CardId.BASH]
    assert {a["action"] for a in sim.get_available_actions()} == {"choose_card", "confirm_choice"}
    sim.confirm_choice()
    assert cs.pending_choice is None and CardId.HEADBUTT in ids(cs.player.discard_pile)

def test_neows_fury_with_two_identical_cards_offers_one_option_twice():
    cs = with_discard([neows_fury()], [strike_card(), strike_card()])
    sim = play(cs)
    assert len(choices(sim)) == 1
    sim.choose_card(choices(sim)[0]["card_index"])
    assert len(choices(sim)) == 1
    sim.choose_card(choices(sim)[0]["card_index"])
    assert ids(cs.player.hand) == [CardId.STRIKE_IRONCLAD] * 2 and cs.pending_choice is None

def test_neows_fury_with_a_single_discard_card_still_lets_the_player_decline():
    cs = with_discard([neows_fury()], [bash()])
    sim = play(cs)
    assert cs.pending_choice is not None and ids(cs.player.hand) == []
    sim.confirm_choice()
    assert ids(cs.player.hand) == [] and cs.pending_choice is None

def test_upgraded_neows_fury_deals_14_and_offers_three_cards():
    f = neows_fury().upgraded_copy()
    cs = with_discard([f], [bash(), headbutt(), strike_card(), bash().upgraded_copy()])
    hp = cs.enemies[0].current_hp
    sim = play(cs)
    assert hp - cs.enemies[0].current_hp == 14
    for _ in range(3):
        sim.choose_card(choices(sim)[0]["card_index"])
    assert len(cs.player.hand) == 3 and cs.pending_choice is None

def test_neows_fury_with_an_empty_discard_asks_nothing():
    cs = state([neows_fury()])
    play(cs)
    assert cs.pending_choice is None

def test_confirm_choice_without_an_optional_choice_is_illegal():
    cs = state([neows_fury()])
    with pytest.raises(IllegalActionError):
        CombatSimulator(cs).confirm_choice()

def test_headbutt_is_not_optional():
    cs = with_discard([headbutt()], [bash(), true_grit()])
    sim = play(cs)
    assert "confirm_choice" not in {a["action"] for a in sim.get_available_actions()}

def test_neows_fury_picks_two_cards_into_the_hand():
    cs = with_discard([neows_fury()], [bash(), headbutt(), true_grit()])
    sim = play(cs)
    assert {a["card_id"] for a in choices(sim)} == {"BASH", "HEADBUTT", "TRUE_GRIT"}
    sim.choose_card(0)
    assert ids(cs.player.hand) == [CardId.BASH] and cs.pending_choice is not None
    assert {a["card_id"] for a in choices(sim)} == {"HEADBUTT", "TRUE_GRIT"}
    sim.choose_card(1)
    assert ids(cs.player.hand) == [CardId.BASH, CardId.TRUE_GRIT]
    assert ids(cs.player.discard_pile) == [CardId.HEADBUTT] and ids(cs.player.exhaust_pile) == [CardId.NEOWS_FURY]
    assert cs.pending_choice is None

def test_neows_fury_identical_cards_are_one_choice_each_time():
    cs = with_discard([neows_fury()], [bash(), bash(), bash(), headbutt()])
    sim = play(cs)
    assert len(choices(sim)) == 2
    sim.choose_card(choices(sim)[0]["card_index"])
    assert len(choices(sim)) == 2          # Bash x2 and Headbutt remain

def test_neows_fury_does_not_touch_the_draw_pile():
    cs = with_discard([neows_fury()], [bash(), headbutt(), true_grit()])
    cs.player.draw_pile = [havoc()]
    sim = play(cs)
    sim.choose_card(0)
    sim.choose_card(0)
    assert ids(cs.player.draw_pile) == [CardId.HAVOC]

def test_neows_fury_with_a_full_hand_leaves_the_cards():
    cs = with_discard([neows_fury()] + [true_grit() for _ in range(9)], [bash(), headbutt(), havoc()])
    sim = play(cs)          # the played card leaves a hand of 9
    sim.choose_card(0)
    assert len(cs.player.hand) == 9 + 1 and cs.pending_choice is None
    assert len(cs.player.discard_pile) == 2 and len(cs.player.exhaust_pile) == 1     # the two unpicked; Fury itself exhausts

def test_neows_fury_capture_matches_the_sim_choice():
    """Captured screen: "Choose up to 2 cards", two identical Strikes, confirm allowed with nothing picked."""
    raw = json.loads((CARDS / "neows_fury_example.json").read_text())
    assert raw["prompt"] == "Choose up to 2 cards to put into your Hand." and raw["can_confirm"] and not raw["can_skip"]
    cs = with_discard([neows_fury()], [Card.from_dict({**c, "can_play": True, "target_type": "AnyEnemy"}) for c in raw["cards"]])
    sim = play(cs)
    options = choices(sim)
    assert len(options) == 1
    assert game_index(options[0], raw["cards"]) == 0

def test_game_index_skips_indices_already_picked():
    raw = json.loads((CARDS / "neows_fury_example.json").read_text())
    action = {"card_id": "STRIKE_IRONCLAD", "is_upgraded": False}
    assert game_index(action, raw["cards"]) == 0
    assert game_index(action, raw["cards"], skip=[0]) == 1
    assert game_index(action, raw["cards"], skip=[0, 1]) is None


def test_neows_fury_exhausts_after_the_pick():
    """Captured (engine_mismatches): the game puts it in the exhaust pile, not the discard pile."""
    cs = with_discard([neows_fury()], [bash(), headbutt()])
    sim = play(cs)
    sim.confirm_choice()
    assert ids(cs.player.exhaust_pile) == [CardId.NEOWS_FURY] and CardId.NEOWS_FURY not in ids(cs.player.discard_pile)


def with_known(draw, known):
    cs = state([])
    cs.player.draw_pile = list(draw)
    cs.player.known_top = known
    return cs


# ---------------------------------------------------------------- Headbutt sets it
def test_headbutt_puts_the_card_on_top_and_knows_it():
    cs = state([headbutt()])
    cs.player.discard_pile = [bash()]
    cs.player.draw_pile = [defend(), defend()]
    play(cs)
    assert cs.player.draw_pile[-1].card_id == CardId.BASH and cs.player.known_top == 1

def test_headbutt_after_a_choice_knows_the_chosen_card():
    cs = state([headbutt()])
    cs.player.discard_pile = [bash(), strike()]
    sim = play(cs)
    sim.choose_card(1)
    assert cs.player.draw_pile[-1].card_id == CardId.STRIKE_IRONCLAD and cs.player.known_top == 1

def test_two_headbutts_stack_the_known_cards():
    cs = state([headbutt(), headbutt()])
    cs.player.discard_pile = [bash()]
    sim = play(cs)
    cs.player.discard_pile = [strike()]
    sim.play_card(0, 0)
    assert cs.player.known_top == 2
    assert ids(cs.player.draw_pile) == [CardId.BASH, CardId.STRIKE_IRONCLAD]

def test_headbutt_with_an_empty_discard_adds_nothing():
    cs = state([headbutt()])
    play(cs)
    assert cs.player.known_top == 0


# ---------------------------------------------------------------- drawing
def test_drawing_a_known_card_is_not_unforeseen():
    cs = with_known([defend(), bash()], 1)
    cs.player.draw_card()
    assert cs.player.hand[0].card_id == CardId.BASH
    assert cs.player.known_top == 0 and cs.player.unknown_draws == 0 and cs.player.cards_drawn == 1

def test_drawing_past_the_known_cards_is_unforeseen():
    cs = with_known([defend(), bash()], 1)
    cs.player.draw_cards(2)
    assert cs.player.known_top == 0 and cs.player.unknown_draws == 1 and cs.player.cards_drawn == 2

def test_drawing_with_no_known_cards_is_unforeseen():
    cs = with_known([defend(), bash()], 0)
    cs.player.draw_card()
    assert cs.player.unknown_draws == 1

def test_a_failed_draw_changes_nothing():
    cs = with_known([], 0)
    cs.player.draw_card()
    assert cs.player.unknown_draws == 0 and cs.player.known_top == 0

def test_a_draw_with_a_full_hand_keeps_the_known_card():
    cs = with_known([defend(), bash()], 1)
    cs.player.hand = [strike() for _ in range(10)]
    cs.player.draw_card()
    assert cs.player.known_top == 1

def test_reshuffling_the_discard_pile_forgets_nothing_because_the_pile_was_empty():
    cs = with_known([], 0)
    cs.player.discard_pile = [strike(), defend()]
    cs.player.draw_card()
    assert cs.player.known_top == 0 and cs.player.unknown_draws == 1

def test_reshuffle_resets_known_top():
    cs = with_known([bash()], 1)
    cs.player.discard_pile = [strike(), defend()]
    cs.player.shuffle_discard_into_draw()
    assert cs.player.known_top == 0 and len(cs.player.draw_pile) == 3


# ---------------------------------------------------------------- shuffling
def test_shuffle_keeps_the_known_top_in_place():
    for seed in range(20):
        rng.seed(seed)
        cs = with_known([strike(), strike(), strike(), defend(), bash(), headbutt()], 2)
        top = list(cs.player.draw_pile[-2:])
        cs.player.shuffle_draw_pile()
        assert cs.player.draw_pile[-2:] == top
        assert len(cs.player.draw_pile) == 6

def test_shuffle_still_mixes_the_rest():
    orders = set()
    for seed in range(30):
        rng.seed(seed)
        cs = with_known([strike(), defend(), bash(), headbutt(), havoc()], 1)
        cs.player.shuffle_draw_pile()
        orders.add(tuple(ids(cs.player.draw_pile[:-1])))
    assert len(orders) > 1

def test_shuffle_with_everything_known_changes_nothing_and_stays_valid():
    cs = with_known([strike(), bash()], 2)
    before = list(cs.player.draw_pile)
    cs.player.shuffle_draw_pile()
    assert cs.player.draw_pile == before

def test_shuffle_without_known_cards_matches_a_plain_shuffle():
    rng.seed(5)
    a = with_known([strike(), defend(), bash(), headbutt()], 0)
    a.player.shuffle_draw_pile()
    rng.seed(5)
    b = [strike(), defend(), bash(), headbutt()]
    rng.shuffle(b)
    assert ids(a.player.draw_pile) == ids(b)


# ---------------------------------------------------------------- copies
def test_deepcopy_carries_known_top_and_counters():
    cs = with_known([defend(), bash()], 1)
    cs.player.draw_card()
    clone = CombatState.deepcopy(cs)
    assert clone.player.known_top == 0 and clone.player.unknown_draws == 0 and clone.player.cards_drawn == 1
    cs2 = with_known([defend(), bash()], 1)
    assert CombatState.deepcopy(cs2).player.known_top == 1

def test_changing_a_clone_leaves_the_original_known_top_alone():
    cs = with_known([defend(), bash()], 1)
    clone = CombatState.deepcopy(cs)
    clone.player.draw_card()
    assert cs.player.known_top == 1


# ---------------------------------------------------------------- Havoc
def test_havoc_on_a_known_top_is_not_a_chance_event():
    cs = state([havoc()])
    cs.player.draw_pile = [defend(), strike()]
    cs.player.known_top = 1
    play(cs)
    assert cs.player.unknown_draws == 0 and cs.player.known_top == 0
    assert ids(cs.player.exhaust_pile) == [CardId.STRIKE_IRONCLAD]

def test_havoc_on_an_unknown_top_is_a_chance_event():
    cs = state([havoc()])
    cs.player.draw_pile = [defend(), strike()]
    play(cs)
    assert cs.player.unknown_draws == 1 and cs.player.known_top == 0

def test_havoc_keeps_the_rest_of_the_known_cards():
    cs = state([havoc()])
    cs.player.draw_pile = [defend(), bash(), strike()]
    cs.player.known_top = 2
    play(cs)
    assert cs.player.known_top == 1 and ids(cs.player.draw_pile) == [CardId.DEFEND_IRONCLAD, CardId.BASH]

def test_havoc_exhausting_a_known_status_card_forgets_it():
    dazed = make_card(CardId.DAZED, "Dazed", CardType.Status, 0, TargetType.Self)
    cs = state([havoc()])
    cs.player.draw_pile = [strike(), dazed]
    cs.player.known_top = 1
    play(cs)
    assert cs.player.known_top == 0 and cs.player.unknown_draws == 0


# ---------------------------------------------------------------- removing cards from the pile
def test_exhausting_a_known_card_from_the_pile_forgets_it():
    cs = with_known([defend(), bash(), strike()], 2)
    cs.player.exhaust_card(cs.player.draw_pile[-1])
    assert cs.player.known_top == 1

def test_exhausting_an_unknown_card_from_the_pile_keeps_the_known_ones():
    cs = with_known([defend(), bash(), strike()], 1)
    cs.player.exhaust_card(cs.player.draw_pile[0])
    assert cs.player.known_top == 1

def test_removing_one_of_two_identical_cards_uses_the_right_one():
    a, b = strike(), strike()
    cs = with_known([a, b], 1)
    cs.player.remove_from_draw_pile(b)
    assert cs.player.draw_pile == [a] and cs.player.known_top == 0
    cs = with_known([a, b], 1)
    cs.player.remove_from_draw_pile(a)
    assert cs.player.known_top == 1


# ---------------------------------------------------------------- carrying across a load
def loaded(draw, known=0):
    cs = state([])
    cs.player.draw_pile = list(draw)
    cs.player.known_top = known
    return cs

def test_carry_known_top_puts_the_cards_back_on_top_in_order():
    prev = loaded([defend(), strike(), bash()], 2)
    new = loaded([bash(), defend(), strike(), headbutt()])
    new.carry_known_top(prev)
    assert new.player.known_top == 2
    assert ids(new.player.draw_pile[-2:]) == [CardId.STRIKE_IRONCLAD, CardId.BASH]
    assert len(new.player.draw_pile) == 4

def test_carry_known_top_matches_upgrades():
    prev = loaded([strike(upgraded=True)], 1)
    new = loaded([strike(), strike(upgraded=True)])
    new.carry_known_top(prev)
    assert new.player.known_top == 1 and new.player.draw_pile[-1].is_upgraded

def test_carry_known_top_drops_everything_if_a_card_is_missing():
    prev = loaded([defend(), bash()], 2)
    new = loaded([defend()])
    new.carry_known_top(prev)
    assert new.player.known_top == 0 and len(new.player.draw_pile) == 1

def test_carry_known_top_missing_upgrade_counts_as_missing():
    prev = loaded([strike(upgraded=True)], 1)
    new = loaded([strike()])
    new.carry_known_top(prev)
    assert new.player.known_top == 0

def test_carry_known_top_with_duplicates_takes_each_once():
    prev = loaded([strike(), strike()], 2)
    new = loaded([strike(), defend()])
    new.carry_known_top(prev)
    assert new.player.known_top == 0

def test_carry_known_top_with_nothing_known_clears_it():
    prev = loaded([defend()], 0)
    new = loaded([defend()], 1)
    new.carry_known_top(prev)
    assert new.player.known_top == 0
    new.carry_known_top(None)
    assert new.player.known_top == 0

def test_carry_known_top_holds_across_turns():
    prev = loaded([defend(), bash()], 1)
    prev.turn_number = 3
    new = loaded([bash(), defend()])
    new.turn_number = 4
    new.carry_known_top(prev)
    assert new.player.known_top == 1 and new.player.draw_pile[-1].card_id == CardId.BASH


# ---------------------------------------------------------------- through the simulator
def test_headbutt_then_end_turn_draws_the_known_card_first():
    cs = state([headbutt()])
    cs.player.discard_pile = [bash()]
    cs.player.draw_pile = [defend() for _ in range(6)]
    sim = play(cs)
    before = cs.player.unknown_draws
    sim.end_turn()
    assert any(c.card_id == CardId.BASH for c in cs.player.hand)
    assert cs.player.unknown_draws - before == 4 and cs.player.known_top == 0

def test_deepcopy_carries_unknown_draws():
    cs = with_known([defend(), bash()], 0)
    cs.player.draw_card()
    assert CombatState.deepcopy(cs).player.unknown_draws == 1
