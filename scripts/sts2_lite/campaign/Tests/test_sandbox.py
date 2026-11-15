"""The campaign simulator: whole runs with simple agents, determinism, the wall between the game's dice and the agent's, and the reward rules."""
import pytest

from agents.base_agent import BaseAgent
from sts2_lite.campaign import RunSimulator
from sts2_lite.campaign.combat import agent_view, start_fight
from sts2_lite.campaign.rewards import generate_rewards, gold_range
from sts2_lite import rng
from sts2_lite.combat import CombatSimulator
from sts2_lite.encounters import ENCOUNTERS
from sts2_lite.card.ids import CardKeyword
from sts2_lite.event import card_entry
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


def test_relics_are_drawn_from_the_bag_and_never_repeat():
    for seed in range(6):
        result = sim_of(RandomFighter(), seed=seed).run()
        assert len(set(result.relics)) == len(result.relics)          # a drawn relic is never offered twice
        assert result.pending_relics == 0                              # bosses drop no relic; an event's bag relic is drawn on the spot


def test_a_relic_that_conjures_cards_at_the_start_of_a_fight_does_not_crash():
    from sts2_lite.run import new_run
    run = new_run(0)
    for relic in ("VEXING_PUZZLEBOX", "ORANGE_DOUGH", "BIG_HAT"):
        run.relics.append({"id": relic, "name": relic})
    game = GameRng(1)
    for _ in range(5):
        start_fight(run, next(e.id for e in ENCOUNTERS.values() if e.room == "Monster"), "monster", game)


RUN_MODIFIERS = ("AMETHYST_AUBERGINE", "BLACK_STAR", "PRAYER_WHEEL", "WHITE_STAR", "WHITE_BEAST_STATUE", "WONGOS_MYSTERY_TICKET", "LASTING_CANDY", "DINGY_RUG", "MOLTEN_EGG", "TOXIC_EGG",
                 "LAVA_LAMP", "WING_CHARM", "BOWLER_HAT", "DRAGON_FRUIT", "SHOVEL", "REGAL_PILLOW", "DREAM_CATCHER", "TINY_MAILBOX", "JUZU_BRACELET", "ETERNAL_FEATHER",
                 "MEAL_TICKET", "PLANISPHERE", "MAW_BANK", "LAVA_ROCK", "MINIATURE_TENT", "LUCKY_FYSH", "BOOK_OF_FIVE_RINGS", "BING_BONG", "CHOSEN_CHEESE", "STONE_HUMIDIFIER",
                 "SWORD_OF_STONE", "DARKSTONE_PERIAPT", "TOOLBOX", "CHOICES_PARADOX", "GAMBLING_CHIP", "PETRIFIED_TOAD", "DELICATE_FROND", "MYSTIC_LIGHTER")


def test_runs_with_every_run_modifier_relic_stay_legal():
    for seed in range(4):
        sim = sim_of(RandomFighter(), seed=seed)
        for relic in RUN_MODIFIERS:
            sim.run_state.relics.append({"id": relic, "name": relic})
            sim.run_state.hidden.relic_bag.remove(relic)
        result = sim.run()
        assert result.illegal_choices == 0
        others = [r for r in result.relics if r != "CIRCLET"]          # the fallback relic of an empty bag may repeat
        dupes = {r for r in others if others.count(r) > 1}
        assert dupes <= set(RUN_MODIFIERS)          # only a relic an ancient offers on top of an injected copy (an ancient does not check what you own)


def fight_with(*relics, deck=None, seed=0):
    run = new_run(0)
    run.relics += [{"id": r, "name": r} for r in relics]
    if deck is not None:
        run.deck = deck
    return run, start_fight(run, next(e.id for e in ENCOUNTERS.values() if e.room == "Monster"), "monster", GameRng(seed))


def test_toolbox_opens_the_fight_with_a_pick_of_three_colorless_cards():
    _, sim = fight_with("TOOLBOX")
    pending = sim.combat_state.pending_choice
    assert pending.kind == "pick_to_hand" and len(pending.offers) == 3
    hand = len(sim.combat_state.player.hand)
    sim.perform_action(sim.get_available_actions()[0])
    assert sim.combat_state.pending_choice is None and len(sim.combat_state.player.hand) == hand + 1


def test_opening_choices_queue_in_order_and_gambling_chip_redraws():
    _, sim = fight_with("TOOLBOX", "CHOICES_PARADOX", "GAMBLING_CHIP")
    seen = []
    while sim.combat_state.pending_choice is not None:
        pending = sim.combat_state.pending_choice
        seen.append(pending.kind)
        sim.perform_action({"action": "confirm_choice"} if pending.kind == "discard_any" else sim.get_available_actions()[0])
    assert seen[:2] == ["pick_to_hand", "pick_to_hand"] and seen[2] == "discard_any"
    paradox = [c for c in sim.combat_state.player.hand if CardKeyword.RETAIN in c.keywords]
    assert paradox


def test_petrified_toad_and_delicate_frond_fill_the_belt():
    run, sim = fight_with("PETRIFIED_TOAD")
    assert [p["id"] for p in run.potions] == ["POTION_SHAPED_ROCK"]
    run, sim = fight_with("DELICATE_FROND")
    assert len(run.potions) == run.potion_slots


def test_mystic_lighter_adds_nine_to_an_enchanted_card_only():
    from sts2_lite.event.run import enchanted
    plain = card_entry("STRIKE_IRONCLAD")
    for entry, bonus in ((plain, 0), (enchanted(plain, "SWIFT", 1), 9)):
        hits = []
        for relic in (None, "MYSTIC_LIGHTER"):
            run, sim = fight_with(*(["MYSTIC_LIGHTER"] if relic else []), deck=[entry] * 10)
            enemy = sim.combat_state.enemies[0]
            hp = enemy.current_hp
            hand = sim.combat_state.player.hand
            sim.perform_action({"action": "play_card", "card_index": 0, "target": 0})
            hits.append(hp - enemy.current_hp)
        assert hits[1] - hits[0] == bonus
