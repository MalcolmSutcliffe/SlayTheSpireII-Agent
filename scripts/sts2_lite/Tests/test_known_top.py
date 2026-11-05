"""Known cards on top of the draw pile (Headbutt). Run from scripts/: python -m pytest sts2_lite/Tests"""
from sts2_lite import rng
from sts2_lite.card import CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.Tests.test_cards import make_card, make_state, play
from sts2_lite.Tests.test_cards_pile_choice import (
    strike, defend, bash, headbutt, havoc, burning_pact, state, ids)


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
