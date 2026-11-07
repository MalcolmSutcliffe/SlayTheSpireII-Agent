"""Colorless cards, group 4b: Discovery (choose a card), Entropy (transform) and Hidden Gem (permanent Replay). Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.card import Card, CardId, CardType, GENERATABLE_CARDS, transform_options, COLORLESS_CARDS
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.status import StatusId
from test_cards import make_state, hps
from test_colorless import card, strike, defend, capture

def one_enemy(hand, hp=100):
    return make_state(hand, enemy_count=1, enemy_hp=hp)

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim

# ------------------------------------------------------------ Discovery
def test_discovery_offers_three_different_ironclad_cards_and_can_be_skipped():
    cs = one_enemy([card(CardId.DISCOVERY)])
    sim = play(cs)
    pending = cs.pending_choice
    assert pending.kind == "discover" and pending.optional and pending.hidden and pending.pile == "offer"
    assert len(pending.offers) == 3 and len({c.card_id for c in pending.offers}) == 3
    assert all(c.card_id in GENERATABLE_CARDS for c in pending.offers)
    actions = sim.get_available_actions()
    assert [a["action"] for a in actions] == ["choose_card"] * 3 + ["confirm_choice"]
    sim.confirm_choice()
    assert cs.pending_choice is None and not cs.player.hand and cs.player.exhaust_pile

def test_discovery_pick_is_free_this_turn():
    cs = one_enemy([card(CardId.DISCOVERY)])
    sim = play(cs)
    offered = cs.pending_choice.offers[1]
    sim.choose_card(1)
    assert [c.card_id for c in cs.player.hand] == [offered.card_id]
    assert cs.player.hand[0].energy_cost == 0 and cs.player.hand[0].restore_cost == offered.energy_cost
    assert cs.pending_choice is None

def test_upgraded_discovery_does_not_exhaust():
    cs = one_enemy([card(CardId.DISCOVERY).upgraded_copy()])
    sim = play(cs)
    sim.confirm_choice()
    assert not cs.player.exhaust_pile and len(cs.player.discard_pile) == 1

def test_discovery_is_a_pick_before_anything_else():
    cs = one_enemy([card(CardId.DISCOVERY), strike()])
    sim = play(cs)
    with pytest.raises(Exception):
        sim.play_card(0, 0)

def test_capture_discovery_screen_replaces_the_sims_offer():
    cs = one_enemy([card(CardId.DISCOVERY)])
    sim = play(cs)
    cs.adopt_offer(capture("discovery_select")["cards"])
    assert [c.card_id for c in cs.pending_choice.offers] == [CardId.HEADBUTT, CardId.STONE_ARMOR, CardId.WHIRLWIND]
    assert not cs.pending_choice.hidden
    sim.choose_card(2)
    assert cs.player.hand[0].card_id == CardId.WHIRLWIND and cs.player.hand[0].energy_cost == "X"

# ------------------------------------------------------------ Entropy
def test_entropy_transforms_a_chosen_card_at_the_start_of_the_turn():
    cs = one_enemy([card(CardId.ENTROPY)])
    play(cs)
    cs.player.draw_pile = [defend() for _ in range(2)] + [strike(), Card.create_generated(CardId.ANGER), Card.create_generated(CardId.FINESSE), defend(), defend()]
    sim = CombatSimulator(cs)
    sim.end_turn()
    pending = cs.pending_choice
    assert pending.kind == "transform" and pending.amount == 1 and len(cs.player.hand) == 5
    before = [c.card_id for c in cs.player.hand]
    pick = pending.indices[0]
    sim.choose_card(pick)
    after = [c.card_id for c in cs.player.hand]
    assert len(after) == 5 and after[pick] != before[pick]
    assert [a for i, a in enumerate(after) if i != pick] == [b for i, b in enumerate(before) if i != pick]

def test_transform_options_follow_the_cards_pool():
    ironclad = transform_options(strike())
    assert ironclad and set(ironclad) <= set(GENERATABLE_CARDS) and CardId.STRIKE_IRONCLAD not in ironclad
    colorless = transform_options(card(CardId.FINESSE))
    assert colorless and set(colorless) <= set(COLORLESS_CARDS) and CardId.FINESSE not in colorless
    assert CardId.HAND_OF_GREED not in colorless
    assert transform_options(Card.create_dazed()) == []

def test_entropy_skips_statuses_and_picks_what_is_left():
    cs = one_enemy([Card.create_dazed(), strike()])
    cs.player.apply_status(StatusId.ENTROPY, 1)
    CombatSimulator(cs).request_transform(1)
    assert cs.player.hand[0].card_id == CardId.DAZED and cs.player.hand[1].card_id != CardId.STRIKE_IRONCLAD
    assert cs.pending_choice is None

def test_entropy_with_two_stacks_picks_two_different_cards():
    cs = one_enemy([strike(), defend(), Card.create_generated(CardId.ANGER)])
    cs.player.apply_status(StatusId.ENTROPY, 2)
    sim = CombatSimulator(cs)
    sim.request_transform(2)
    assert cs.pending_choice.amount == 2
    sim.choose_card(cs.pending_choice.indices[0])
    assert cs.pending_choice.amount == 1 and len(cs.pending_choice.picked) == 1 and cs.pending_choice.picked[0] not in cs.pending_choice.indices
    sim.choose_card(cs.pending_choice.indices[0])
    assert cs.pending_choice is None and len(cs.player.hand) == 3

def test_entropy_upgrade_is_innate():
    assert not card(CardId.ENTROPY).upgraded_copy().card_id == CardId.STRIKE_IRONCLAD
    assert card(CardId.ENTROPY).upgraded_copy()._mask & 4 and not card(CardId.ENTROPY)._mask & 4

def test_capture_entropy_screen_becomes_a_transform_choice():
    cs = CombatState.from_dict(capture("entropy_select"))
    assert cs.pending_choice.kind == "transform" and cs.pending_choice.amount == 1
    # Strike appears three times and counts once
    assert len(cs.pending_choice.indices) == 3
    sim = CombatSimulator(cs)
    sim.choose_card(cs.pending_choice.indices[0])
    assert cs.pending_choice is None and len(cs.player.hand) == 5

# ------------------------------------------------------------ Hidden Gem
def test_hidden_gem_gives_a_draw_pile_card_replay_two():
    cs = one_enemy([card(CardId.HIDDEN_GEM)])
    cs.player.draw_pile = [strike(), defend(), strike()]
    play(cs)
    gained = [c for c in cs.player.draw_pile if c.replay]
    assert len(gained) == 1 and gained[0].replay == 2 and len(cs.player.draw_pile) == 3

def test_hidden_gem_upgrade_gives_three_and_skips_cards_with_replay():
    cs = one_enemy([card(CardId.HIDDEN_GEM).upgraded_copy()])
    marked = strike().with_replay(2)
    cs.player.draw_pile = [marked, defend()]
    play(cs)
    assert cs.player.draw_pile[0].replay == 2 and cs.player.draw_pile[1].replay == 3

def test_hidden_gem_ignores_unplayable_cards_and_curses():
    cs = one_enemy([card(CardId.HIDDEN_GEM)])
    cs.player.draw_pile = [Card.create_dazed(), Card.create_curse(CardId.REGRET)]
    play(cs)
    assert all(c.replay == 0 for c in cs.player.draw_pile)

def test_hidden_gem_with_an_empty_draw_pile_does_nothing():
    cs = one_enemy([card(CardId.HIDDEN_GEM)])
    play(cs)
    assert len(cs.player.discard_pile) == 1

def test_replay_plays_a_card_extra_times():
    cs = one_enemy([strike().with_replay(2)], hp=100)
    play(cs)
    assert hps(cs) == [82]

def test_replay_survives_copying_and_upgrading():
    c = strike().with_replay(2)
    assert Card.create_copy(c).replay == 2 and c.upgraded_copy().replay == 2

def test_capture_hidden_gem_replay_is_read_from_the_card_text():
    cs = CombatState.from_dict(capture("hidden_gem"))
    assert [c.replay for c in cs.player.draw_pile] == [0, 0, 0, 2, 0]
    assert all(c.replay == 0 for c in cs.player.hand + cs.player.discard_pile)       # Hidden Gem's own tooltip is not a Replay
    cs.player.hand = [cs.player.draw_pile[3]]
    cs.enemies[0].current_hp = 100
    play(cs)
    assert hps(cs)[0] == 100 - 3 * 6
