"""Colorless cards, group 2: picks from the draw pile and Thinking Ahead."""
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.verify import is_random_step
from test_cards import make_card, make_state, hps
from test_colorless import card, strike, defend, play

def bash():
    return make_card(CardId.BASH, "Bash", CardType.Attack, 2, TargetType.AnyEnemy)

def ids(pile):
    return [c.card_id for c in pile]

# ------------------------------------------------------------ Secret Technique / Secret Weapon
def test_secret_technique_offers_only_skills_from_the_draw_pile():
    cs = make_state([card(CardId.SECRET_TECHNIQUE)], enemy_count=1)
    cs.player.draw_pile = [strike(), defend(), card(CardId.FINESSE), bash()]
    sim = play(cs)
    assert cs.pending_choice.pile == "draw" and not cs.pending_choice.optional
    offered = {cs.player.draw_pile[i].card_id for i in cs.pending_choice.indices}
    assert offered == {CardId.DEFEND_IRONCLAD, CardId.FINESSE}
    assert {a["action"] for a in sim.get_available_actions()} == {"choose_card"}

def test_secret_technique_moves_the_pick_to_the_hand_and_exhausts():
    cs = make_state([card(CardId.SECRET_TECHNIQUE)], enemy_count=1)
    cs.player.draw_pile = [strike(), defend(), card(CardId.FINESSE)]
    sim = play(cs)
    index = next(i for i in cs.pending_choice.indices if cs.player.draw_pile[i].card_id == CardId.FINESSE)
    sim.choose_card(index)
    assert ids(cs.player.hand) == [CardId.FINESSE] and len(cs.player.draw_pile) == 2
    assert len(cs.player.exhaust_pile) == 1 and cs.pending_choice is None

def test_upgraded_secret_technique_does_not_exhaust():
    cs = make_state([card(CardId.SECRET_TECHNIQUE).upgraded_copy()], enemy_count=1)
    cs.player.draw_pile = [defend()]
    play(cs)
    assert cs.player.exhaust_pile == [] and len(cs.player.discard_pile) == 1

def test_a_single_matching_skill_is_taken_without_asking():
    cs = make_state([card(CardId.SECRET_TECHNIQUE)], enemy_count=1)
    cs.player.draw_pile = [strike(), defend()]
    play(cs)
    assert cs.pending_choice is None and ids(cs.player.hand) == [CardId.DEFEND_IRONCLAD]

def test_no_matching_card_asks_nothing():
    cs = make_state([card(CardId.SECRET_TECHNIQUE)], enemy_count=1)
    cs.player.draw_pile = [strike()]
    play(cs)
    assert cs.pending_choice is None and cs.player.hand == []

def test_secret_weapon_offers_attacks():
    cs = make_state([card(CardId.SECRET_WEAPON)], enemy_count=1)
    cs.player.draw_pile = [strike(), bash(), defend()]
    play(cs)
    offered = {cs.player.draw_pile[i].card_id for i in cs.pending_choice.indices}
    assert offered == {CardId.STRIKE_IRONCLAD, CardId.BASH}

def test_taking_a_known_top_card_forgets_that_it_was_on_top():
    cs = make_state([card(CardId.SECRET_WEAPON)], enemy_count=1)
    cs.player.draw_pile = [defend(), bash(), strike()]
    cs.player.known_top = 1
    sim = play(cs)
    sim.choose_card(next(i for i in cs.pending_choice.indices if cs.player.draw_pile[i].card_id == CardId.STRIKE_IRONCLAD))
    assert cs.player.known_top == 0

def test_a_full_hand_sends_the_pick_to_the_discard_pile():
    cs = make_state([card(CardId.SECRET_WEAPON)] + [defend() for _ in range(10)], enemy_count=1)
    cs.player.draw_pile = [strike(), bash()]
    sim = play(cs)
    sim.choose_card(cs.pending_choice.indices[0])
    assert len(cs.player.hand) == 10 and len(cs.player.discard_pile) == 1

# ------------------------------------------------------------ Seeker Strike
def test_seeker_strike_hits_and_offers_three_cards():
    cs = make_state([card(CardId.SEEKER_STRIKE)], enemy_count=1, enemy_hp=40)
    cs.player.draw_pile = [strike(), defend(), bash(), card(CardId.FINESSE), card(CardId.PRODUCTION)]
    play(cs)
    assert hps(cs) == [31] and len(cs.pending_choice.indices) == 3 and cs.pending_choice.hidden

def test_upgraded_seeker_strike_deals_twelve():
    cs = make_state([card(CardId.SEEKER_STRIKE).upgraded_copy()], enemy_count=1, enemy_hp=40)
    cs.player.draw_pile = [strike()]
    play(cs)
    assert hps(cs) == [28]

def test_seeker_strike_with_fewer_cards_offers_what_there_is():
    cs = make_state([card(CardId.SEEKER_STRIKE)], enemy_count=1)
    cs.player.draw_pile = [strike(), bash()]
    play(cs)
    assert len(cs.pending_choice.indices) == 2

def test_seeker_strike_with_an_empty_draw_pile_asks_nothing():
    cs = make_state([card(CardId.SEEKER_STRIKE)], enemy_count=1)
    play(cs)
    assert cs.pending_choice is None

def test_adopting_the_games_offer_replaces_the_random_one():
    cs = make_state([card(CardId.SEEKER_STRIKE)], enemy_count=1)
    cs.player.draw_pile = [strike(), defend(), bash(), card(CardId.FINESSE), card(CardId.PRODUCTION)]
    play(cs)
    offered = [{"index": 0, "id": "FINESSE", "is_upgraded": False}, {"index": 1, "id": "BASH", "is_upgraded": False},
               {"index": 2, "id": "PRODUCTION", "is_upgraded": False}]
    cs.adopt_offer(offered)
    assert {cs.player.draw_pile[i].card_id for i in cs.pending_choice.indices} == {CardId.FINESSE, CardId.BASH, CardId.PRODUCTION}
    assert not cs.pending_choice.hidden

def test_seeker_strike_is_a_random_step_and_a_strike():
    from sts2_lite.card import STRIKE_CARDS
    assert CardId.SEEKER_STRIKE in STRIKE_CARDS
    cs = make_state([card(CardId.SEEKER_STRIKE)], enemy_count=1)
    cs.player.draw_pile = [strike(), bash()]
    from sts2_lite.combat import CombatState
    before = CombatState.deepcopy(cs)
    play(cs)
    assert is_random_step(before, cs, [{"action": "play_card", "card_index": 0, "target": 0}])

# ------------------------------------------------------------ Thinking Ahead
def test_thinking_ahead_draws_two_then_puts_a_card_on_top():
    cs = make_state([card(CardId.THINKING_AHEAD), strike()], enemy_count=1)
    cs.player.draw_pile = [defend(), bash(), card(CardId.FINESSE)]
    sim = play(cs)
    assert len(cs.player.hand) == 3 and cs.pending_choice.pile == "hand" and not cs.pending_choice.optional
    pick = next(i for i in cs.pending_choice.indices if cs.player.hand[i].card_id == CardId.BASH)
    sim.choose_card(pick)
    assert cs.player.draw_pile[-1].card_id == CardId.BASH and cs.player.known_top == 1
    assert len(cs.player.hand) == 2 and len(cs.player.exhaust_pile) == 1

def test_the_card_put_back_is_drawn_next():
    cs = make_state([card(CardId.THINKING_AHEAD)], enemy_count=1)
    cs.player.draw_pile = [defend(), bash(), strike()]
    sim = play(cs)
    sim.choose_card(next(i for i in cs.pending_choice.indices if cs.player.hand[i].card_id == CardId.STRIKE_IRONCLAD))
    drawn = cs.player.draw_card()
    assert drawn.card_id == CardId.STRIKE_IRONCLAD

def test_thinking_ahead_with_a_lone_hand_card_puts_it_back_without_asking():
    cs = make_state([card(CardId.THINKING_AHEAD)], enemy_count=1)
    cs.player.draw_pile = [defend()]
    play(cs)
    assert cs.pending_choice is None and cs.player.hand == [] and ids(cs.player.draw_pile) == [CardId.DEFEND_IRONCLAD]

def test_thinking_ahead_with_nothing_to_draw_or_hold_does_nothing():
    cs = make_state([card(CardId.THINKING_AHEAD)], enemy_count=1)
    play(cs)
    assert cs.pending_choice is None

def test_upgraded_thinking_ahead_does_not_exhaust():
    cs = make_state([card(CardId.THINKING_AHEAD).upgraded_copy()], enemy_count=1)
    cs.player.draw_pile = [defend()]
    play(cs)
    assert cs.player.exhaust_pile == []

def test_group_two_ids_exist():
    for name in ("SECRET_TECHNIQUE", "SECRET_WEAPON", "SEEKER_STRIKE", "THINKING_AHEAD"):
        assert CardId[name]

# ------------------------------------------------------------ captures: Tests/data/cards/colorless
import json
from pathlib import Path
from sts2_lite.combat import CombatState
from sts2_lite.selection import game_index

CAPTURES = Path(__file__).parent / "data" / "cards" / "colorless"

def capture(name):
    return json.loads((CAPTURES / f"{name}.json").read_text())

def test_capture_secret_technique_with_two_identical_skills_is_settled_by_the_sim():
    screen = capture("secret_technique")
    assert screen["can_skip"] is False and [c["id"] for c in screen["cards"]] == ["DEFEND_IRONCLAD"] * 2
    cs = make_state([card(CardId.SECRET_TECHNIQUE)], enemy_count=1)
    cs.player.draw_pile = [strike(), defend(), defend(), bash()]
    play(cs)
    # the game still shows a screen for two identical cards; the sim takes one at once and the tester's auto_pick clicks the first
    assert cs.pending_choice is None and ids(cs.player.hand) == [CardId.DEFEND_IRONCLAD] and len(cs.player.draw_pile) == 3

def test_capture_seeker_strike_offer_is_adopted_by_the_sim():
    screen = capture("seeker_strike")
    cs = make_state([card(CardId.SEEKER_STRIKE)], enemy_count=1)
    cs.player.draw_pile = [defend(), strike(), strike(), bash(), defend(), card(CardId.FINESSE)]
    sim = play(cs)
    cs.adopt_offer(screen["cards"])
    actions = [a for a in sim.get_available_actions() if a["action"] == "choose_card"]
    assert sorted(a["card_id"] for a in actions) == ["BASH", "STRIKE_IRONCLAD"]
    for a in actions:
        assert game_index(a, screen["cards"]) is not None
    sim.choose_card(next(a["card_index"] for a in actions if a["card_id"] == "BASH"))
    assert CardId.BASH in ids(cs.player.hand)

def test_capture_thinking_ahead_screen_loads_as_a_required_pick_of_the_hand():
    cs = CombatState.from_dict(capture("thinking_ahead"))
    pending = cs.pending_choice
    assert pending.kind == "to_draw_pile" and pending.pile == "hand" and not pending.optional
    assert sorted(cs.player.hand[i].card_id.name for i in pending.indices) == ["BASH", "DEFEND_IRONCLAD", "STRIKE_IRONCLAD"]
    sim = CombatSimulator(cs)
    hand = len(cs.player.hand)
    sim.choose_card(next(i for i in pending.indices if cs.player.hand[i].card_id == CardId.BASH))
    assert cs.player.draw_pile[-1].card_id == CardId.BASH and len(cs.player.hand) == hand - 1
