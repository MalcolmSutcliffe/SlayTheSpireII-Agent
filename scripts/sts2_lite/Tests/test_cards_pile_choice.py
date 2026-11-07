"""Headbutt, True Grit, Burning Pact and Havoc. Run from scripts/: python -m pytest sts2_lite/Tests"""
import json
from pathlib import Path

import pytest

from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState, IllegalActionError
from sts2_lite.selection import game_index
from sts2_lite.status import StatusId
from sts2_lite.Tests.test_cards import make_card, make_state, play, hps


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
    raw = json.loads((Path(__file__).parent / "data" / "headbutt_example.json").read_text())
    cards = raw["cards"]
    assert game_index({"card_id": "STRIKE_IRONCLAD", "is_upgraded": False}, cards) == 4
    assert game_index({"card_id": "STRIKE_IRONCLAD", "is_upgraded": True}, cards) == 3
    assert game_index({"card_id": "DEFEND_IRONCLAD", "is_upgraded": False}, cards) == 0
    assert game_index({"card_id": "ARMAMENTS", "is_upgraded": False}, cards) == 1
    assert game_index({"card_id": "BASH", "is_upgraded": False}, cards) is None

def test_actions_from_a_pile_choice_can_be_matched_to_the_game_list():
    raw = json.loads((Path(__file__).parent / "data" / "headbutt_example.json").read_text())
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
    cs = with_discard([neows_fury()], [bash(), headbutt()])
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
    assert ids(cs.player.discard_pile) == [CardId.HEADBUTT, CardId.NEOWS_FURY]
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
    assert len(cs.player.discard_pile) >= 3     # Fury itself + the two unpicked

def test_neows_fury_capture_matches_the_sim_choice():
    """Captured screen: "Choose up to 2 cards", two identical Strikes, confirm allowed with nothing picked."""
    raw = json.loads((Path(__file__).parent / "data" / "neows_fury_example.json").read_text())
    assert raw["prompt"] == "Choose up to 2 cards to put into your Hand." and raw["can_confirm"] and not raw["can_skip"]
    cs = with_discard([neows_fury()], [Card.from_dict({**c, "can_play": True, "target_type": "AnyEnemy"}) for c in raw["cards"]])
    sim = play(cs)
    options = choices(sim)
    assert len(options) == 1
    assert game_index(options[0], raw["cards"]) == 0

def test_game_index_skips_indices_already_picked():
    raw = json.loads((Path(__file__).parent / "data" / "neows_fury_example.json").read_text())
    action = {"card_id": "STRIKE_IRONCLAD", "is_upgraded": False}
    assert game_index(action, raw["cards"]) == 0
    assert game_index(action, raw["cards"], skip=[0]) == 1
    assert game_index(action, raw["cards"], skip=[0, 1]) is None
