"""Seeded randomness. Run from scripts/: python -m pytest sts2_lite/Tests"""
from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy import Enemy
from sts2_lite.player import Player


def make_card(i):
    c = Card()
    c.card_id, c.name, c.type = CardId.STRIKE_IRONCLAD, f"Strike{i}", CardType.Attack
    c.energy_cost, c.target_type = 1, TargetType.AnyEnemy
    c.is_upgraded = False
    c.is_unplayable = False
    return c

def make_state(n_discard=20):
    p = Player()
    p.max_hp = p.current_hp = 50
    p.discard_pile = [make_card(i) for i in range(n_discard)]
    e = Enemy()
    e.max_hp = e.current_hp = 40
    e.enemy_id = "E"
    e.attack_damage, e.num_attacks = 0, 0
    cs = CombatState()
    cs.player, cs.enemies = p, [e]
    cs.energy = cs.max_energy = 3
    cs.turn_number = 1
    cs.deck = []
    return cs

def draw_order(cs):
    cs.player.shuffle_discard_into_draw()
    return [c.name for c in cs.player.draw_pile]


def test_same_seed_gives_the_same_shuffle():
    rng.seed(123)
    a = draw_order(make_state())
    rng.seed(123)
    b = draw_order(make_state())
    assert a == b

def test_different_seeds_give_different_shuffles():
    rng.seed(1)
    a = draw_order(make_state())
    rng.seed(2)
    b = draw_order(make_state())
    assert a != b

def test_shuffle_keeps_every_card():
    rng.seed(5)
    order = draw_order(make_state())
    assert sorted(order) == sorted(f"Strike{i}" for i in range(20))

def test_consecutive_shuffles_differ_without_reseeding():
    cs = make_state()
    first = draw_order(cs)
    cs.player.discard_pile, cs.player.draw_pile = cs.player.draw_pile, []
    second = draw_order(cs)
    assert first != second

def test_clones_share_the_stream():
    cs = make_state()
    clone = CombatState.deepcopy(cs)
    rng.seed(9)
    a = draw_order(cs)
    rng.seed(9)
    b = draw_order(clone)
    assert a == b

def test_clones_of_one_state_get_different_shuffles_from_one_stream():
    cs = make_state()
    first = draw_order(CombatState.deepcopy(cs))
    second = draw_order(CombatState.deepcopy(cs))
    assert first != second

def test_full_game_is_reproducible_from_a_seed():
    def run(seed):
        rng.seed(seed)
        cs = make_state(12)
        cs.player.hand = []
        sim = CombatSimulator(cs)
        seen = []
        for _ in range(6):
            sim.end_turn()
            seen.append([c.name for c in cs.player.hand])
        return seen
    assert run(77) == run(77)
    assert run(77) != run(78)

def test_getstate_setstate_replays_the_stream():
    rng.seed(3)
    state = rng.getstate()
    a = draw_order(make_state())
    rng.setstate(state)
    b = draw_order(make_state())
    assert a == b


# ---------------------------------------------------------------- randomness signals
def test_rng_calls_count_random_draws():
    start = rng.calls
    rng.shuffle([1, 2, 3])
    rng.randrange(10)
    rng.choice([1, 2, 3])
    assert rng.calls == start + 3

def test_seeding_and_state_changes_are_not_random_draws():
    start = rng.calls
    rng.seed(4)
    rng.setstate(rng.getstate())
    assert rng.calls == start

def test_reshuffle_counts_as_one_rng_call():
    cs = make_state(5)
    start = rng.calls
    cs.player.draw_card()                       # empty draw pile: reshuffles the discard
    assert rng.calls == start + 1

def test_reshuffle_with_nothing_to_shuffle_is_not_a_random_draw():
    cs = make_state(0)
    start = rng.calls
    cs.player.draw_card()
    assert rng.calls == start

def test_drawing_from_a_nonempty_pile_does_not_touch_rng():
    cs = make_state(5)
    cs.player.draw_pile, cs.player.discard_pile = cs.player.discard_pile, []
    start = rng.calls
    cs.player.draw_cards(3)
    assert rng.calls == start

def test_cards_drawn_counts_each_draw():
    cs = make_state(5)
    cs.player.draw_pile, cs.player.discard_pile = cs.player.discard_pile, []
    cs.player.draw_cards(3)
    assert cs.player.cards_drawn == 3

def test_cards_drawn_counts_across_a_reshuffle():
    cs = make_state(4)
    cs.player.draw_cards(4)
    assert cs.player.cards_drawn == 4

def test_cards_drawn_ignores_draws_that_fail():
    cs = make_state(0)
    cs.player.draw_cards(3)                     # nothing to draw
    assert cs.player.cards_drawn == 0

def test_cards_drawn_ignores_draws_with_a_full_hand():
    cs = make_state(5)
    cs.player.hand = [make_card(i) for i in range(10)]
    cs.player.draw_cards(3)
    assert cs.player.cards_drawn == 0

def test_cards_drawn_on_a_clone_does_not_touch_the_original():
    cs = make_state(5)
    cs.player.draw_pile, cs.player.discard_pile = cs.player.discard_pile, []
    clone = CombatState.deepcopy(cs)
    before = clone.player.cards_drawn
    clone.player.draw_cards(2)
    assert clone.player.cards_drawn == before + 2
    assert cs.player.cards_drawn == 0
