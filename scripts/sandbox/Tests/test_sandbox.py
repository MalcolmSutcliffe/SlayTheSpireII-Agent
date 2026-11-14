"""The run sandbox: whole runs with simple agents, determinism, the wall between the game's dice and the agent's, and the reward rules."""
import pytest

from agents.base_agent import BaseAgent
from sandbox import RunSimulator
from sandbox.combat import agent_view, start_fight
from sandbox.rewards import generate_rewards, gold_range
from sts2_lite import rng
from sts2_lite.combat import CombatSimulator
from sts2_lite.encounters import ENCOUNTERS
from sts2_lite.run import GameRng, SearchRng, new_run

TOUGH = 3000


class RandomFighter(BaseAgent):
    def __init__(self):
        super().__init__()
        self._rng = None        # screens are answered from the search generator too, so a run is a function of its two seeds

    def _rng_choice(self, options):
        return rng.current().choice(options)

    """Plays a random legal action; its dice are the search generator's (the sandbox scopes it), so it must never change the game."""
    def get_combat_action(self, combat_state, time_budget=None):
        return rng.current().choice(CombatSimulator(combat_state).get_available_actions())


class DiceBurner(RandomFighter):
    """Same choices as RandomFighter would make, but burns search randomness at every decision."""
    def get_decision(self, decision):
        for _ in range(rng.current().randint(0, 5)):
            rng.current().random()
        return super().get_decision(decision)


def sim_of(agent, seed, ascension=0, hp=TOUGH, search_seed=0):
    sim = RunSimulator(agent, seed=seed, ascension=ascension, search_seed=search_seed, time_budget=None)
    sim.run_state.hp = sim.run_state.max_hp = hp
    return sim


def signature(result):
    return (result.won, result.act, result.floor, result.hp, tuple(result.deck), tuple(result.relics), result.pending_relics, result.fights,
            tuple((v.floor, v.room, v.id) for v in result.history))


def test_full_run_completes_without_illegal_choices():
    for ascension in (0, 5, 10):
        r = sim_of(RandomFighter(), seed=ascension + 1, ascension=ascension).run()
        assert r.illegal_choices == 0 and r.fights >= 1
        assert r.won or (r.cause in ENCOUNTERS)         # a run ends by winning or by an encounter's kill (Miasma drain can kill any HP), never by a stall or a crash


def test_every_room_type_is_visited():
    rooms = set()
    for seed in range(1, 6):
        rooms |= {v.room for v in sim_of(RandomFighter(), seed).run().history}
    assert {"Ancient", "Monster", "Elite", "RestSite", "Treasure", "Event", "Shop"} <= rooms


def test_same_seeds_same_run():
    a = sim_of(RandomFighter(), seed=7).run()
    b = sim_of(RandomFighter(), seed=7).run()
    assert signature(a) == signature(b)


def test_different_game_seeds_differ():
    assert signature(sim_of(RandomFighter(), seed=7).run()) != signature(sim_of(RandomFighter(), seed=8).run())


def test_agent_dice_do_not_change_the_game():
    """The map, the rooms and the rewards come from the game's streams only: an agent that burns search randomness sees the same dungeon."""
    a = sim_of(RandomFighter(), seed=11, search_seed=1)
    b = sim_of(DiceBurner(), seed=11, search_seed=2)
    a.start_act(0)
    b.start_act(0)
    assert a.run_state.map.start.coord == b.run_state.map.start.coord
    edges = lambda m: [[(c.col, c.row) for c in p.children] for p in m.points()]
    assert edges(a.run_state.map) == edges(b.run_state.map)
    assert a.run_state.boss == b.run_state.boss


def test_game_rng_hidden_from_agent_scope():
    """While the agent thinks, the active generator is a SearchRng, never the game's."""
    seen = []

    class Spy(BaseAgent):
        def get_decision(self, decision):
            seen.append(rng.owner())
            return super().get_decision(decision)

        def get_combat_action(self, combat_state, time_budget=None):
            seen.append(rng.owner())
            return super().get_combat_action(combat_state, time_budget)
    sim_of(Spy(), seed=3).run()
    assert seen and set(seen) == {"search"}


def test_agent_view_hides_draw_order_but_keeps_the_cards():
    run = new_run(0)
    game = GameRng(5)
    sim = start_fight(run, next(e.id for e in ENCOUNTERS.values() if e.room == "Monster"), "monster", game)
    cs = sim.combat_state
    seen = agent_view(cs, SearchRng(1))
    ids = lambda s: sorted(str(c.card_id) for c in s.player.draw_pile)
    assert ids(seen) == ids(cs)
    orders = {tuple(str(c.card_id) for c in agent_view(cs, SearchRng(k)).player.draw_pile) for k in range(8)}
    assert len(orders) > 1          # the agent's view of the order is its own guess, not the real one


def test_gold_ranges_and_poverty():
    for room, (lo, hi) in {"Monster": (10, 20), "Elite": (35, 45)}.items():
        enc = next(e for e in ENCOUNTERS.values() if e.room == room)
        assert gold_range(enc, 0) == (lo, hi)
        plo, phi = gold_range(enc, 3)
        assert plo < lo and phi < hi


def test_elite_rewards_include_a_relic_and_boss_final_pays_nothing():
    run = new_run(0)
    game = GameRng(2)
    elite = next(e for e in ENCOUNTERS.values() if e.room == "Elite")
    boss = next(e for e in ENCOUNTERS.values() if e.room == "Boss")
    assert any(r.kind == "relic" for r in generate_rewards(run, elite, False, game))
    assert generate_rewards(run, boss, True, game) == []


def test_double_boss_only_from_ascension_10_in_the_last_act():
    for ascension, expected in ((9, False), (10, True)):
        sim = sim_of(RandomFighter(), seed=4, ascension=ascension)
        sim.start_act(2)
        assert (sim.run_state.map.second_boss is not None) == expected
        sim.start_act(0)
        assert sim.run_state.map.second_boss is None


def test_illegal_choice_falls_back_and_is_counted():
    class Cheater(RandomFighter):
        def get_decision(self, decision):
            from agents.decision import Option
            return Option("bogus", {})
    r = sim_of(Cheater(), seed=2).run()
    assert r.illegal_choices > 0
