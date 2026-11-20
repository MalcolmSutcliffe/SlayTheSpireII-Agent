"""Player.aligned_shuffle (experiments): a seeded order that keeps the common cards of two decks in the same order, draws nothing from the rng, and is not
copied into a search's states."""
from sts2_lite import rng
from sts2_lite.campaign.combat import start_fight
from sts2_lite.event.run import card_entry
from sts2_lite.player import Player
from sts2_lite.run import RunState
from sts2_lite.run.streams import GameRng

STARTER = ["STRIKE_IRONCLAD"] * 5 + ["DEFEND_IRONCLAD"] * 4 + ["BASH"]


def run_with(deck):
    player = {"hp": 70, "max_hp": 80, "gold": 0, "relics": [{"id": "BURNING_BLOOD"}], "potions": []}
    return RunState.from_player(player, [card_entry(c) for c in deck])


def order(sim):
    """The deck as it will be drawn: the hand, then the draw pile from the top."""
    p = sim.combat_state.player
    return [c.card_id.name for c in p.hand] + [c.card_id.name for c in reversed(p.draw_pile)]


def test_adding_a_card_keeps_the_others_in_the_same_order():
    deck = STARTER + ["SHRUG_IT_OFF", "INFLAME"]
    a = order(start_fight(run_with(deck), "TOADPOLES_WEAK", "monster", GameRng(5), aligned_shuffle=11))
    b = order(start_fight(run_with(deck + ["BLUDGEON"]), "TOADPOLES_WEAK", "monster", GameRng(5), aligned_shuffle=11))
    assert [c for c in b if c != "BLUDGEON"] == a
    again = order(start_fight(run_with(deck), "TOADPOLES_WEAK", "monster", GameRng(5), aligned_shuffle=11))
    assert again == a
    other = order(start_fight(run_with(deck), "TOADPOLES_WEAK", "monster", GameRng(5), aligned_shuffle=12))
    assert other != a           # another seed, another order


def test_the_aligned_order_draws_nothing_from_the_rng_and_counts_its_shuffles():
    sim = start_fight(run_with(STARTER), "TOADPOLES_WEAK", "monster", GameRng(5), aligned_shuffle=3)
    p = sim.combat_state.player
    rng.seed(1)
    before = rng.getstate()
    p.discard_pile, p.draw_pile = p.draw_pile + p.hand, []
    p.shuffle_discard_into_draw()
    assert rng.getstate() == before and p.aligned_shuffles == 2


def test_a_search_copy_shuffles_at_random():
    sim = start_fight(run_with(STARTER), "TOADPOLES_WEAK", "monster", GameRng(5), aligned_shuffle=3)
    copy = Player.deepcopy(sim.combat_state.player)
    assert copy.aligned_shuffle is None
    assert start_fight(run_with(STARTER), "TOADPOLES_WEAK", "monster", GameRng(5)).combat_state.player.aligned_shuffle is None
