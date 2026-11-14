"""RunState and the game / search random sources."""
import pytest

from sts2_lite import rng
from sts2_lite.event import EVENTS, EventSession, RunSnapshot, card_entry
from sts2_lite.run import GameRng, RunState, STREAMS, SearchRng, new_run
from sts2_lite.run.state import Hidden


def draws(generator, n=5):
    return [generator.random() for _ in range(n)]


# --- the two random sources -----------------------------------------------------------------------------------------------------------------------
def test_a_seed_replays_every_stream():
    a, b = GameRng(5), GameRng(5)
    assert all(draws(a.stream(name)) == draws(b.stream(name)) for name in STREAMS)
    assert draws(GameRng(5).stream("shuffle")) != draws(GameRng(6).stream("shuffle"))


def test_streams_do_not_move_each_other():
    a, b = GameRng(9), GameRng(9)
    draws(a.stream("card_rewards"), 50)
    assert draws(a.stream("shuffle")) == draws(b.stream("shuffle"))


def test_unknown_stream_is_refused_and_the_seed_is_not_shown():
    game = GameRng(123456)
    with pytest.raises(KeyError):
        game.stream("nope")
    assert "123456" not in repr(game) and "123456" not in repr(SearchRng(123456))


def test_state_can_be_saved_and_restored():
    game = GameRng(3)
    saved = game.getstate()
    first = draws(game.stream("events"))
    game.setstate(saved)
    assert draws(game.stream("events")) == first


def test_game_scope_takes_over_the_simulator_rng_and_gives_it_back():
    game = GameRng(11)
    assert rng.owner() == "search"
    before = rng.current()
    with game.scope("shuffle"):
        assert rng.owner() == "game:shuffle" and rng.current() is game.stream("shuffle")
        rng.choice([1, 2, 3])
    assert rng.owner() == "search" and rng.current() is before


def test_scope_restores_after_an_error():
    game = GameRng(11)
    with pytest.raises(RuntimeError):
        with game.scope("shuffle"):
            raise RuntimeError
    assert rng.owner() == "search"


def test_search_draws_never_move_the_game_and_the_reverse():
    game, other = GameRng(21), GameRng(21)
    search = SearchRng(1)
    with search.scope():
        for _ in range(100):
            rng.choice(range(10))
    assert game.getstate() == other.getstate() or draws(game.stream("shuffle")) == draws(other.stream("shuffle"))
    s1, s2 = SearchRng(1), SearchRng(1)
    with game.scope("shuffle"):
        for _ in range(100):
            rng.shuffle(list(range(10)))
    with s1.scope():
        a = [rng.randrange(1000) for _ in range(5)]
    with s2.scope():
        b = [rng.randrange(1000) for _ in range(5)]
    assert a == b


def test_search_rng_cannot_be_made_from_the_game():
    with pytest.raises(TypeError):
        SearchRng(GameRng(1))
    assert SearchRng(4).spawn().random.random() == SearchRng(4).spawn().random.random()
    assert SearchRng(4).spawn().random.random() != SearchRng(4).random.random()


def test_unseeded_search_rngs_differ():
    assert draws(SearchRng().random) != draws(SearchRng().random)


def test_the_counter_still_counts_draws_inside_a_scope():
    game = GameRng(2)
    before = rng.calls
    with game.scope("niche"):
        rng.choice([1, 2])
    assert rng.calls == before + 1


# --- RunState ---------------------------------------------------------------------------------------------------------------------------------------
def test_a_new_run_has_the_starter_deck_and_the_ascension_changes():
    run = new_run()
    ids = [c["id"] for c in run.deck]
    assert ids.count("STRIKE_IRONCLAD") == 5 and ids.count("DEFEND_IRONCLAD") == 4 and ids.count("BASH") == 1 and len(ids) == 10
    assert run.hp == run.max_hp == 80 and run.gold == 99 and run.potion_slots == 3 and run.has_relic("BURNING_BLOOD")
    assert new_run(4).potion_slots == 2 and "ASCENDERS_BANE" not in [c["id"] for c in new_run(4).deck]
    assert "ASCENDERS_BANE" in [c["id"] for c in new_run(5).deck] and new_run(10).ascension == 10


def test_public_view_hides_what_the_player_cannot_see():
    run = new_run()
    run.hidden.rarity_offset = 0.2
    seen = run.public()
    assert seen.hidden is None and run.hidden.rarity_offset == 0.2 and seen.deck == run.deck


def test_copy_is_independent():
    run = new_run()
    other = run.copy()
    other.deck.append(card_entry("ANGER"))
    other.hidden.rarity_offset = 0.3
    other.visit("Event", "WELLSPRING")
    assert len(run.deck) == 10 and run.hidden.rarity_offset == -0.05 and not run.history and not run.seen_events


def test_visits_record_where_the_run_has_been():
    run = new_run()
    run.act, run.floor = 1, 3
    run.visit("Monster", "SLIMES_WEAK")
    run.visit("Event", "WELLSPRING")
    assert [(v.floor, v.room, v.id) for v in run.history] == [(3, "Monster", "SLIMES_WEAK"), (3, "Event", "WELLSPRING")] and run.seen_events == ["WELLSPRING"]


def test_events_play_on_the_run_state():
    assert RunSnapshot is RunState
    run = new_run()
    run.act, run.floor = 1, 5
    session = EventSession(EVENTS["ABYSSAL_BATHS"], run.copy(), GameRng(1).stream("events"))
    session.choose(session.options[0].key)
    assert isinstance(session.run, RunState)


def test_from_player_matches_the_bridge():
    run = RunState.from_player({"hp": 50, "max_hp": 80, "gold": 12, "relics": [{"id": "BURNING_BLOOD", "name": "x"}], "potions": [None, {"id": "FIRE_POTION"}], "potion_slots": 2},
                               [card_entry("BASH")], act=2, floor=20, ascension=7)
    assert (run.hp, run.gold, run.act, run.floor, run.ascension, run.potion_slots) == (50, 12, 2, 20, 7, 2) and len(run.potions) == 1 and run.hidden is None
