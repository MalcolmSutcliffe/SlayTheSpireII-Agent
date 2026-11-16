import pytest

from agents.decision import Decision, Option, CARD_REWARD
from agents.pathing import PlannedRoute
from agents.deck_eval.fight_pool import load_pool, target_types
from agents.deck_eval.fight_mix import mix_ahead, new_act_mix, pick_fights
from agents.deck_eval.evaluator import DeckEvaluator
from agents.deck_eval.card_reward_chooser import CardRewardChooser, paired_gain, skip_floor

POOL = load_pool()
needs_pool = pytest.mark.skipif(not POOL, reason="the engine has no encounters")


def test_skip_floor_does_not_depend_on_the_deck_size():
    import inspect
    assert "deck_size" not in inspect.signature(skip_floor).parameters
    from agents.deck_eval.config import DEFAULT
    assert skip_floor() == DEFAULT.card_floor


def test_paired_gain():
    mean, se = paired_gain([3, 4, 5, 6], [1, 2, 3, 4])
    assert mean == 2 and se == 0


def test_mix_follows_the_planned_route():
    # act 1: 3 weak fights, 1 already fought, the room in progress is a combat -> 1 weak left; route ahead: 3 combats, 1 elite, boss
    route = PlannedRoute(["combat", "combat", "rest", "combat", "elite", "combat", "boss"], 1, 1)
    mix = mix_ahead(1, route)
    assert (mix.weak, mix.normal, mix.elite, mix.act) == (1, 2, 1, 1)
    share = lambda m: m.boss / (m.weak + m.normal + m.elite + m.boss)
    near_end = mix_ahead(1, PlannedRoute(["rest", "combat", "boss"], 7, 1))
    assert mix.boss == 1 and share(near_end) > share(mix)        # one boss among fewer fights ahead: it comes up more as the route runs out


def test_boss_reward_looks_at_the_next_act():
    mix = mix_ahead(1, PlannedRoute(["boss"], 6, 1))
    assert mix.act == 2 and mix.weak == 2
    assert mix_ahead(3, PlannedRoute(["boss"], 6, 3)).act == 3


def test_pool_is_the_engines_encounters():
    from sts2_lite.encounters import ACTS
    from agents.deck_eval.fight_pool import ACT_NUMBER, WEAK_FIGHTS
    assert WEAK_FIGHTS == {1: 3, 2: 2, 3: 2}
    for act in ACTS.values():
        mine = {t.encounter: t for t in POOL if t.encounter in act.encounters and t.act == ACT_NUMBER[act.id]}
        assert set(mine) == set(act.encounters)
        for kind, encounters in (("weak", act.weak), ("normal", act.regular), ("elite", act.elites), ("boss", act.bosses)):
            assert {e for e, t in mine.items() if t.kind == kind} == {e.id for e in encounters}
        assert all(t.variant == (act.id if ACT_NUMBER[act.id] == 1 else None) for t in mine.values())
        assert all(t.state is None and (t.boss == t.encounter) == (t.kind == "boss") for t in mine.values())


def test_pool_kinds():
    assert {t.kind for t in POOL} <= {"weak", "normal", "elite", "boss"}
    assert any(t.kind == "boss" for t in POOL)
    fights = pick_fights(POOL, new_act_mix(1), 50, 1)
    assert fights == pick_fights(POOL, new_act_mix(1), 50, 1)
    assert len({f.seed for f in fights}) > 1 and all(f.ascension == 0 for f in fights)
    assert all(f.ascension == 7 for f in pick_fights(POOL, new_act_mix(2), 5, 1, 7))


def _player():
    import copy
    from sts2_lite.run import new_run
    run = new_run()
    return {"hp": 70, "max_hp": 80, "relics": copy.deepcopy(run.relics), "deck": copy.deepcopy(run.deck)}


@needs_pool
def test_same_seed_same_result():
    ev, p = DeckEvaluator(POOL, target_types(POOL)), _player()
    fights = pick_fights(POOL, new_act_mix(1), 10, 3)
    a, b = ev.score(p["deck"], p, fights, 3), ev.score(p["deck"], p, fights, 3)
    assert a.rewards == b.rewards


@needs_pool
def test_chooser_returns_one_of_the_options_and_skips_a_useless_card():
    p = _player()
    state = {"type": "decision", "decision": "card_reward", "player": p, "context": {"act": 1}}
    cards = [{"index": 0, "id": "BASH", "name": "Bash", "type": "Attack", "cost": 2}, {"index": 1, "id": "SHRUG_IT_OFF", "name": "Shrug It Off", "type": "Skill", "cost": 1}]
    options = [Option(c["name"], {"action": "select_card_reward", "card_index": c["index"]}, c) for c in cards] + [Option("skip", {"action": "skip_card_reward"})]
    logged = []
    chooser = CardRewardChooser(fights=20, pool=POOL, log=logged.append)
    assert chooser.choose(Decision(CARD_REWARD, state, options)) in options
    assert len(logged) == 2 and "needs" in logged[0] and "walking the rest of the act" in logged[1]


from agents.deck_eval.boss_spawner import BOSS_ACTS, bosses_of_act, normalize_boss_id
from agents.deck_eval.fight_builder import build_fight
from agents.deck_eval.fight_pool import instance
import random


def test_boss_ids():
    assert normalize_boss_id("soul fysh") == "SOUL_FYSH_BOSS" and normalize_boss_id("VANTOM_BOSS") == "VANTOM_BOSS" and normalize_boss_id(None) is None
    assert {v for a, v in BOSS_ACTS.values() if a == 1} == {"OVERGROWTH", "UNDERDOCKS"}
    assert BOSS_ACTS["KAISER_CRAB_BOSS"] == (2, "HIVE") and BOSS_ACTS["QUEEN_BOSS"] == (3, "GLORY")
    assert {t.boss for t in bosses_of_act(POOL, 1, variant="UNDERDOCKS")} == {"WATERFALL_GIANT_BOSS", "SOUL_FYSH_BOSS", "LAGAVULIN_MATRIARCH_BOSS"}
    assert [t.boss for t in bosses_of_act(POOL, 2, "knowledge demon")] == ["KNOWLEDGE_DEMON_BOSS"]


def test_bosses_are_built_by_the_engine_with_the_hit_points_of_the_ascension():
    p = _player()
    for enc, hp0, hp9 in (("WATERFALL_GIANT_BOSS", 240, 250), ("SOUL_FYSH_BOSS", 211, 221), ("KNOWLEDGE_DEMON_BOSS", 379, 399)):
        template = next(t for t in POOL if t.boss == enc)
        for ascension, hp in ((0, hp0), (9, hp9)):
            cs = build_fight(instance(template, ascension, random.Random(1)), p["deck"], p, target_types()).combat_state
            assert cs.enemies[0].max_hp == hp and cs.ascension == ascension


def test_a_drawn_fight_rolls_the_same_monsters_for_every_deck():
    p = _player()
    for fight in pick_fights(POOL, new_act_mix(1), 10, 4):
        a = build_fight(fight, p["deck"], p, target_types()).combat_state
        b = build_fight(fight, p["deck"][:-1], p, target_types()).combat_state
        key = lambda cs: [(e.enemy_id, e.max_hp, e.move_id) for e in cs.enemies]
        assert key(a) == key(b)


@needs_pool
def test_a_boss_is_played_to_the_end():
    ev, p = DeckEvaluator(POOL, target_types(POOL)), _player()
    template = next(t for t in POOL if t.boss == "WATERFALL_GIANT_BOSS")
    s = ev.score(p["deck"], p, [instance(template, 0, random.Random(i)) for i in range(3)], 1)
    assert len(s.rewards) == 3


def test_pick_fights_uses_the_boss_the_map_showed():
    for enc in ("SOUL_FYSH_BOSS", "VANTOM_BOSS"):
        mix = new_act_mix(1).__class__(1, 0, 0, 0, 1.0, BOSS_ACTS[enc][1], enc)
        assert {f.boss for f in pick_fights(POOL, mix, 20, 1)} == {enc}


def test_the_elites_left_in_the_bag():
    from agents.deck_eval.elite_odds import elites_left
    hive = ("DECIMILLIPEDE_ELITE", "ENTOMANCER_ELITE", "INFESTED_PRISMS_ELITE")
    assert set(elites_left("HIVE", [])) == set(hive)
    assert elites_left("HIVE", ["ENTOMANCER_ELITE", "DECIMILLIPEDE_ELITE"]) == ("INFESTED_PRISMS_ELITE",)
    assert set(elites_left("HIVE", [None, "DECIMILLIPEDE_ELITE"])) == {"ENTOMANCER_ELITE", "INFESTED_PRISMS_ELITE"}
    again = elites_left("HIVE", list(hive))                 # the bag refilled: anything but the last one
    assert set(again) == set(hive) - {hive[-1]}
    assert elites_left("OVERGROWTH", ["BYRDONIS_ELITE"]) != elites_left("OVERGROWTH", [])
    assert elites_left(None, []) is None


def test_an_elite_is_told_by_its_monsters():
    from agents.deck_eval.elite_odds import identify
    assert identify("HIVE", ["ENTOMANCER_0"]) == "ENTOMANCER_ELITE"
    assert identify("HIVE", ["DECIMILLIPEDE_SEGMENT_FRONT_0", "DECIMILLIPEDE_SEGMENT_MIDDLE_1"]) == "DECIMILLIPEDE_ELITE"
    assert identify("OVERGROWTH", ["PHROG_PARASITE_0", "WRIGGLER_1"]) == "PHROG_PARASITE_ELITE"
    assert identify("GLORY", ["ENTOMANCER_0"]) is None


@needs_pool
def test_the_last_elite_is_the_one_not_fought_yet():
    seen = ["ENTOMANCER_ELITE", "DECIMILLIPEDE_ELITE"]
    route = PlannedRoute(["rest", "combat", "elite", "combat", "boss"], 4, 2, None, "HIVE", seen)
    mix = mix_ahead(2, route)
    assert mix.elites == ("INFESTED_PRISMS_ELITE",)
    elites = [f for f in pick_fights(POOL, mix, 60, 3) if f.kind == "elite"]
    assert elites and {f.encounter for f in elites} == {"INFESTED_PRISMS_ELITE"}
    fresh = mix_ahead(2, PlannedRoute(["rest", "combat", "elite", "combat", "boss"], 4, 2, None, "HIVE", []))
    assert {f.encounter for f in pick_fights(POOL, fresh, 200, 3) if f.kind == "elite"} == set(fresh.elites)


def test_the_planner_counts_an_elite_room_once():
    from agents.pathing import PathPlanner
    planner = PathPlanner()
    planner.route = PlannedRoute(["elite", "rest"], 3, 2, None, "HIVE", planner.elites.setdefault(2, []))
    planner.note_elite("ENTOMANCER_ELITE")
    planner.note_elite("ENTOMANCER_ELITE")
    assert planner.elites[2] == ["ENTOMANCER_ELITE"]
    planner.route = PlannedRoute(["combat"], 3, 2, None, "HIVE", planner.elites[2])
    planner.note_elite("X")
    assert planner.elites[2] == ["ENTOMANCER_ELITE"]


from agents.deck_eval.advisor import DeckAdvisor
from agents.deck_eval.upgrade_chooser import UpgradeChooser, heal_amount


def test_heal_amount_is_capped_by_missing_hp():
    assert heal_amount(None, {"hp": 70, "max_hp": 80}) == 10
    assert heal_amount(None, {"hp": 20, "max_hp": 80}) == 24
    assert heal_amount(Option("Rest", {}, {"description": "Heal 12 HP."}), {"hp": 20, "max_hp": 80}) == 12


def _rest_decision(hp):
    p = _player()
    p["hp"] = hp
    options = [Option("Rest", {"action": "choose_rest_option", "index": 0}, {"id": "HEAL", "index": 0}),
               Option("Smith", {"action": "choose_rest_option", "index": 1}, {"id": "SMITH", "index": 1})]
    return Decision("REST", {"type": "decision", "decision": "rest_site", "player": p, "context": {"act": 1}}, options)


@needs_pool
def test_rest_chooser_heals_when_nearly_dead_and_upgrade_picks_a_non_basic_first():
    chooser = UpgradeChooser(DeckAdvisor(fights=30, pool=POOL, log=lambda *_: None))
    low = _rest_decision(8)
    assert chooser.choose_rest(low).data["id"] == "HEAL"
    gains = chooser.best_gains(low)
    assert "STRIKE_IRONCLAD" not in gains and "DEFEND_IRONCLAD" not in gains and "BASH" in gains
    picks = [Option(c["name"], {"action": "select_card", "index": i}, {**c, "index": i}) for i, c in enumerate(_player()["deck"])]
    assert chooser.choose_card(low, picks).data["id"] in gains


def test_upgrade_marker_upgrades_the_card_in_the_fight():
    from agents.deck_eval.fight_builder import build_fight
    p = _player()
    if not POOL:
        pytest.skip("no captures")
    deck = [dict(c, _upgrade=(c["id"] == "BASH")) for c in p["deck"]]
    sim = build_fight(next(t for t in POOL if t.kind == "weak"), deck, p, target_types(POOL))
    cards = sim.combat_state.player.hand + sim.combat_state.player.draw_pile
    assert [c.is_upgraded for c in cards if c.name.startswith("Bash")] == [True]


from agents.deck_eval.upgrade_chooser import full_heal
import random


def test_full_heal_is_not_capped():
    assert full_heal(None, {"hp": 79, "max_hp": 80}) == 24


@needs_pool
def test_rule_one_upgrades_when_the_rest_would_be_cut_short():
    chooser = UpgradeChooser(DeckAdvisor(fights=10, pool=POOL, log=lambda *_: None))
    assert chooser.choose_rest(_rest_decision(70)).data["id"] == "SMITH"        # 10 HP missing, a rest heals 24


def test_the_route_steps_keep_every_room_but_the_fight_kinds_drop_the_others():
    from agents.deck_eval.future_cards import route_steps, fight_kinds
    route = PlannedRoute(["combat", "combat", "rest", "elite", "unknown", "treasure", "shop", "rest", "combat", "boss"], 3, 1)
    assert route_steps(route, 1) == ["normal", "rest", "elite", "unknown", "treasure", "shop", "rest", "normal", "boss"]
    assert fight_kinds(route, 1) == ["normal", "elite", "normal", "boss"]
    assert "rest" not in route_steps(PlannedRoute(["boss"], 6, 1), 1)


def test_the_elites_to_come_follow_the_ones_fought():
    from agents.deck_eval.elite_odds import elite_sequence
    from sts2_lite.encounters import ACTS
    hive = {e.id for e in ACTS["HIVE"].elites}
    seq = elite_sequence("HIVE", ["ENTOMANCER_ELITE", "DECIMILLIPEDE_ELITE"], random.Random(1))
    assert [e.id for e in seq[:3]] == ["ENTOMANCER_ELITE", "DECIMILLIPEDE_ELITE", "INFESTED_PRISMS_ELITE"] and {e.id for e in seq} == hive
    assert [e.id for e in elite_sequence("HIVE", [], random.Random(1))[:3]] and len({e.id for e in elite_sequence("HIVE", [], random.Random(1))[:3]}) == 3


@needs_pool
def test_walks_follow_the_route_and_what_the_agent_knows_of_the_act():
    from agents.deck_eval.route_sim import sample_walks
    route = PlannedRoute(["combat", "combat", "rest", "elite", "unknown", "treasure", "rest", "combat", "boss"], 3, 2, "KAISER_CRAB_BOSS", "HIVE", ["ENTOMANCER_ELITE", "DECIMILLIPEDE_ELITE"])
    walks, again = sample_walks(route, 2, 0, 12, 4, floor=20), sample_walks(route, 2, 0, 12, 4, floor=20)
    assert [w.seed for w in walks] == [w.seed for w in again] and [w.rooms.boss.id for w in walks] == [w.rooms.boss.id for w in again]
    for w in walks:
        assert w.steps == ["normal", "rest", "elite", "unknown", "treasure", "rest", "normal", "boss"] and w.act == 2 and w.act_id == "HIVE" and w.fights == 4
        assert w.rooms.boss.id == "KAISER_CRAB_BOSS" and w.rooms.elite[2].id == "INFESTED_PRISMS_ELITE" and w.elite_fought == 2 and w.normal_fought == 4 and w.floor == 20


@needs_pool
def test_a_boss_reward_looks_at_the_next_act_with_nothing_behind_it():
    from agents.deck_eval.route_sim import sample_walks
    walks = sample_walks(PlannedRoute(["boss"], 6, 1), 1, 0, 5, 2)
    assert all(w.act == 2 and w.act_id == "HIVE" and w.elite_fought == 0 and w.normal_fought == 0 and w.steps[-1] == "boss" for w in walks)
    assert all(w.act_id in ("OVERGROWTH", "UNDERDOCKS") for w in sample_walks(None, 1, 0, 5, 2))


@needs_pool
def test_the_last_act_at_ascension_ten_has_two_bosses():
    from agents.deck_eval.route_sim import sample_walks
    walks = sample_walks(PlannedRoute(["combat", "combat", "boss"], 5, 3, None, "GLORY"), 3, 10, 4, 1)
    assert all(w.rooms.second_boss is not None and w.rooms.second_boss.id != w.rooms.boss.id and w.fights == 3 for w in walks)
    assert all(w.rooms.second_boss is None for w in sample_walks(PlannedRoute(["combat", "combat", "boss"], 5, 3, None, "GLORY"), 3, 9, 4, 1))


def _walk_run(walk, hp=80, max_hp=80):
    """The run a walk starts from, as play_walk builds it."""
    from agents.deck_eval import route_sim as rs
    from sts2_lite.run import RunState
    p = _player()
    p.update(hp=hp, max_hp=max_hp)
    run = RunState.from_player(p, rs._normalized(p["deck"], target_types(POOL)), act=walk.act, floor=walk.floor, ascension=walk.ascension)
    run.act_id, run.boss = walk.act_id, walk.rooms.boss.id
    run.hidden = rs.Hidden()
    run.hidden.rooms, run.hidden.normal_fought, run.hidden.elite_fought = walk.rooms, walk.normal_fought, walk.elite_fought
    run.hidden.relic_bag = rs.RelicGrabBag(random.Random(walk.seed))
    run.hidden.relic_bag.remove("BURNING_BLOOD")
    return run


@needs_pool
def test_the_engine_pays_an_elite_a_relic_a_rest_site_heals_and_a_treasure_room_gives_gold():
    from agents.deck_eval.route_sim import RouteSimulator, sample_walks
    ev = DeckEvaluator(POOL, target_types(POOL))
    walk = sample_walks(PlannedRoute(["combat", "elite", "rest", "treasure", "combat", "boss"], 4, 1, None, "OVERGROWTH"), 1, 0, 1, 3)[0]
    run = _walk_run(walk, hp=500, max_hp=500)       # a deck that wins everything
    relics, gold = len(run.relics), run.gold
    result = RouteSimulator(run, walk, ev.config).walk_route()
    rooms = [v.room for v in run.history]
    assert rooms[:4] == ["Elite", "RestSite", "Treasure", "Monster"]
    assert len(run.relics) >= relics + 2 and run.gold > gold      # the elite's and the chest's relic, the gold of the fights and the chest
    hurt = _walk_run(walk, hp=20, max_hp=80)
    sim = RouteSimulator(hurt, walk, ev.config)
    sim.reseed(0)
    sim.rest_site()
    assert hurt.hp == 44 and [v.room for v in hurt.history] == ["RestSite"]       # a hurt agent heals: 30% of 80 HP


@needs_pool
def test_a_walk_is_repeatable_and_a_deck_that_dies_early_scores_only_what_it_got_through():
    from agents.deck_eval.route_sim import sample_walks
    ev, p = DeckEvaluator(POOL, target_types(POOL)), _player()
    walks = sample_walks(PlannedRoute(["combat", "elite", "combat", "boss"], 3, 1, None, "OVERGROWTH"), 1, 0, 4, 2)       # the first fight ahead is an elite
    healthy, again = ev.score_walks(p["deck"], p, walks), ev.score_walks(p["deck"], p, walks)
    assert healthy.rewards == again.rewards
    dying = ev.score_walks(p["deck"], {**p, "hp": 1}, walks)
    assert dying.win_rate == 0 and dying.mean_hp_left == 0 and dying.mean < healthy.mean
    assert all(r < 1.0 for r in dying.rewards)       # dead in the first fight: at most the share of it that was got through, nothing of the rooms after it


@needs_pool
def test_the_walk_agent_takes_the_rarest_card_at_its_take_rate():
    from agents.deck_eval.route_sim import WalkAgent
    cards = [{"index": i, "id": c, "name": c, "type": "Attack", "rarity": r} for i, (c, r) in enumerate((("A", "Common"), ("B", "Rare"), ("C", "Uncommon")))]
    options = [Option(c["name"], {"action": "select_card_reward", "card_index": c["index"]}, c) for c in cards] + [Option("skip", {"action": "skip_card_reward"})]
    decision = Decision(CARD_REWARD, {"type": "decision", "decision": "card_reward"}, options)
    assert WalkAgent(1.0, 1).get_decision(decision).data["id"] == "B"
    assert WalkAgent(0.0, 1).get_decision(decision).name == "skip_card_reward"
    taken = sum(WalkAgent(0.5, s).get_decision(decision).name == "select_card_reward" for s in range(200))
    assert 70 < taken < 130


@needs_pool
def test_the_advisor_hands_every_chooser_the_same_kind_of_walks():
    advisor = DeckAdvisor(fights=30, pool=POOL, log=lambda *_: None, route_provider=lambda: PlannedRoute(["combat", "combat", "rest", "elite", "combat", "boss"], 3, 1))
    decision = Decision("REST", {"type": "decision", "decision": "rest_site", "player": _player(), "context": {"act": 1, "floor": 7}}, [])
    walks = advisor.walks(decision)
    assert len(walks) == 30 // 4 and all(w.steps[-1] == "boss" and w.floor == 7 for w in walks)         # 4 fights ahead; the route ends with its boss
    assert len(advisor.walks(decision, 4)) == 6          # never fewer than the fewest walks
    assert len(advisor.walks(decision, 2500)) == 2500 // 4 and advisor.walks(decision)[0].seed != walks[0].seed       # every call a new seed


def test_early_floor_is_halved_for_the_first_three_rewards():
    assert skip_floor(early=True) == skip_floor() / 2


@needs_pool
def test_early_floor_applies_to_the_first_three_rewards_of_a_run():
    p = _player()
    state = lambda floor: {"type": "decision", "decision": "card_reward", "player": p, "context": {"act": 1, "floor": floor}}
    options = [Option("Bash", {"action": "select_card_reward", "card_index": 0}, {"index": 0, "id": "BASH", "name": "Bash", "type": "Attack", "cost": 2}),
               Option("skip", {"action": "skip_card_reward"})]
    logs = []
    chooser = CardRewardChooser(fights=5, pool=POOL, log=logs.append)
    for floor in (2, 3, 4, 6):
        chooser.choose(Decision(CARD_REWARD, state(floor), options))
    assert chooser._rewards == 4
    chooser.choose(Decision(CARD_REWARD, state(1), options))        # the floor number went down: a new run
    assert chooser._rewards == 1


def test_skip_floor_shrinks_with_a_weak_deck():
    from agents.deck_eval.config import DEFAULT
    FLOOR = DEFAULT.card_floor
    assert skip_floor(win_rate=0.8) == skip_floor() == FLOOR
    assert abs(skip_floor(win_rate=0.4) - FLOOR / 2) < 1e-9
    assert abs(skip_floor(win_rate=0.3) - FLOOR * 0.375) < 1e-9


def test_fights_fit_the_time_budget():
    from agents.deck_eval.card_reward_chooser import fights_for
    from agents.deck_eval.config import DEFAULT
    assert fights_for(15.0, 0.002, 4) == 1875
    assert fights_for(15.0, 0.002, 4) > fights_for(8.0, 0.002, 4)
    assert fights_for(15.0, 1.0, 4) == DEFAULT.min_fights and fights_for(15.0, 1e-9, 4) == DEFAULT.max_fights


@needs_pool
def test_pilot_sets_the_fight_count_and_big_decisions_get_the_longer_budget(monkeypatch):
    from types import SimpleNamespace
    from agents.deck_eval.config import DEFAULT
    quick = DEFAULT.tuned(card_seconds=0.01, card_big_seconds=0.02, max_fights=400)
    p = _player()
    state = lambda floor: {"type": "decision", "decision": "card_reward", "player": p, "context": {"act": 1, "floor": floor}}
    options = [Option("Bash", {"action": "select_card_reward", "card_index": 0}, {"index": 0, "id": "BASH", "name": "Bash", "type": "Attack", "cost": 2}),
               Option("skip", {"action": "skip_card_reward"})]
    route = SimpleNamespace(kinds=["combat", "combat"], combats_before=0, act=1, boss=None, act_model=None, elites_seen=[])
    logs = []
    chooser = CardRewardChooser(advisor=DeckAdvisor(pool=POOL, route_provider=lambda: route, log=logs.append, config=quick))
    fights = lambda: int([l for l in logs if l.startswith("card reward")][-1].split(" fights")[0].split()[-1])
    counts = []
    for floor in (2, 3, 4, 6):
        chooser.choose(Decision(CARD_REWARD, state(floor), options))
        counts.append(fights())
    assert counts[0] > 0 and counts[3] > 0


def test_future_fights_count_fights_only_and_cards_follow_the_position():
    from types import SimpleNamespace
    from agents.deck_eval.future_cards import fight_kinds, extra_cards, CARD_POOL, RARE_START, RARE_MAX
    import random
    route = SimpleNamespace(kinds=["combat", "combat", "rest", "elite", "shop", "unknown", "combat", "boss"], combats_before=1)
    assert fight_kinds(route, 1) == ["weak", "elite", "normal", "boss"]       # the rest site, shop and "?" are not fights
    assert fight_kinds(SimpleNamespace(kinds=["boss"], combats_before=3), 1)[-1] == "boss"
    assert [len(extra_cards(n, random.Random(1))) for n in (1, 4, 6)] == [1, 4, 6]
    assert all(c["type"] in ("Attack", "Skill", "Power") for rarity in CARD_POOL.values() for c in rarity)


def test_extra_cards_follow_the_reward_rarity_odds():
    from agents.deck_eval.future_cards import extra_cards, CARD_POOL
    import random
    r = random.Random(7)
    rarity = {c["id"]: name for name, cards in CARD_POOL.items() for c in cards}
    drawn = [rarity[c["id"]] for _ in range(1500) for c in extra_cards(1, r)]
    share = lambda name: drawn.count(name) / len(drawn)
    assert abs(share("Common") - 0.60) < 0.05 and abs(share("Uncommon") - 0.25) < 0.05 and abs(share("Rare") - 0.15) < 0.05


def test_a_boss_reward_looks_at_the_next_act():
    from agents.deck_eval.future_cards import fight_act
    from types import SimpleNamespace
    assert fight_act(SimpleNamespace(kinds=["boss"]), 1) == 2 and fight_act(SimpleNamespace(kinds=["combat", "boss"]), 1) == 1
    assert fight_act(SimpleNamespace(kinds=["boss"]), 3) == 3


def test_a_deck_changed_by_an_event_builds_a_fight_with_its_enchantment_and_new_cards():
    """An event's result (enchanted card, added card) goes straight into a fight: the sim reads the enchantment and knows the new card."""
    import random as _random
    from agents.deck_eval.fight_builder import build_fight
    from sts2_lite.event import EVENTS, EventSession, RunSnapshot, card_entry
    if not POOL:
        pytest.skip("no captures")
    deck = [card_entry("STRIKE_IRONCLAD") for _ in range(5)] + [card_entry("DEFEND_IRONCLAD") for _ in range(5)] + [card_entry("BASH")]
    run = RunSnapshot(hp=70, max_hp=80, gold=0, deck=deck)
    EventSession(EVENTS["SAPPHIRE_SEED"], run, _random.Random(3)).play(["plant"])
    EventSession(EVENTS["BUGSLAYER"], run, _random.Random(3)).play(["squash"])
    sim = build_fight(next(t for t in POOL if t.kind == "weak"), run.deck, {"hp": 70, "max_hp": 80, "relics": []}, target_types(POOL))
    cards = sim.combat_state.player.hand + sim.combat_state.player.draw_pile
    assert [c.enchantment.name for c in cards if c.enchantment] == ["SOWN"] and any(c.name == "Squash" for c in cards)


def test_a_spiral_strike_hits_twice_in_a_built_fight():
    from agents.deck_eval.fight_builder import build_fight
    from sts2_lite.event.run import card_entry, enchanted
    if not POOL:
        pytest.skip("no captures")

    def damage(card):
        deck = [card] + [card_entry("DEFEND_IRONCLAD")] * 4
        sim = build_fight(next(t for t in POOL if t.kind == "weak"), deck, {"hp": 70, "max_hp": 80, "relics": []}, target_types(POOL))
        state = sim.combat_state
        before = sum(e.current_hp for e in state.enemies)
        sim.play_card(next(i for i, c in enumerate(state.player.hand) if c.card_id.name == "STRIKE_IRONCLAD"), 0)
        return before - sum(e.current_hp for e in state.enemies)
    assert damage(enchanted(card_entry("STRIKE_IRONCLAD"), "SPIRAL", 1)) == 2 * damage(card_entry("STRIKE_IRONCLAD"))


# --- events and the time caps -------------------------------------------------------------------------------------------------------------------------

def _event_walk():
    from agents.deck_eval.route_sim import sample_walks
    return sample_walks(PlannedRoute(["combat", "rest", "combat", "boss"], 4, 1, None, "OVERGROWTH"), 1, 0, 1, 3)[0]


@needs_pool
def test_an_event_option_is_played_by_the_engine_before_the_walk():
    from agents.deck_eval.route_sim import EventPlan, RouteSimulator, EventMismatch
    ev = DeckEvaluator(POOL, target_types(POOL))
    walk = _event_walk()
    run = _walk_run(walk, hp=70, max_hp=80)
    sim = RouteSimulator(run, walk, ev.config, EventPlan("ABYSSAL_BATHS", [], "immerse"))
    sim.reseed("event")
    sim.play_event(sim.opening)
    assert (run.max_hp, run.hp) == (82 + 0, 69) and [] == run.offers          # +2 max HP (hp+2), -3 HP
    run = _walk_run(walk, hp=70, max_hp=80)
    sim = RouteSimulator(run, walk, ev.config, EventPlan("ABYSSAL_BATHS", ["immerse"], "linger"))
    sim.reseed("event")
    sim.play_event(sim.opening)
    assert run.max_hp == 84 and run.hp == 70 + 4 - 3 - 4          # the second dip costs one more
    with pytest.raises(EventMismatch):
        RouteSimulator(_walk_run(walk), walk, ev.config, EventPlan("ABYSSAL_BATHS", [], "no such option")).play_event(EventPlan("ABYSSAL_BATHS", [], "no such option"))
    with pytest.raises(EventMismatch):
        RouteSimulator(_walk_run(walk), walk, ev.config, None).play_event(EventPlan("NOT_AN_EVENT", [], "x"))


@needs_pool
def test_an_option_that_kills_scores_nothing_and_a_cleared_act_goes_on_into_the_next_one():
    from agents.deck_eval.route_sim import EventPlan, sample_walks
    from agents.deck_eval.config import DEFAULT
    ev = DeckEvaluator(POOL, target_types(POOL))
    p = _player()
    dying = ev.score_walks(p["deck"], {**p, "hp": 1, "max_hp": 80}, [_event_walk()], EventPlan("ABYSSAL_BATHS", [], "immerse"))          # +2 HP, then 3 damage: dead
    assert dying.win_rate == 0 and dying.rewards[0] == 0.0
    walks = sample_walks(PlannedRoute(["rest", "combat"], 4, 0, None, "OVERGROWTH"), 1, 0, 1, 3)          # one fight a deck that cannot lose wins
    strong = {**p, "hp": 500, "max_hp": 500}
    score = ev.score_walks(p["deck"], strong, walks)
    assert score.win_rate == 1.0 and score.rewards[0] >= len(walks[0].steps) + 1          # the act's rooms and a good part of the next act's first ones
    from agents.deck_eval import route_sim as rs
    run = _walk_run(walks[0], hp=500, max_hp=500)
    sim = rs.RouteSimulator(run, walks[0], ev.config)
    result = sim.walk_route()
    assert run.act == 2 and run.act_id == "HIVE" and result.fights >= len(walks[0].steps) and len(sim.credits) <= len(walks[0].steps) + DEFAULT.lookahead_rooms


@needs_pool
def test_dying_at_the_boss_costs_what_comes_after_it():
    from agents.deck_eval.route_sim import sample_walks
    ev, p = DeckEvaluator(POOL, target_types(POOL)), _player()
    walks = sample_walks(PlannedRoute(["combat", "rest", "boss"], 4, 1, None, "OVERGROWTH"), 1, 0, 6, 3)
    weak, strong = ev.score_walks(p["deck"], p, walks), ev.score_walks(p["deck"], {**p, "hp": 500, "max_hp": 500}, walks)
    assert strong.mean - weak.mean > 2.0          # clearing the boss is worth the next act's rooms too, not one more fight in twenty


@needs_pool
def test_a_walk_that_survives_is_credited_with_a_share_of_the_run_still_ahead():
    from agents.deck_eval.route_sim import sample_walks
    from agents.deck_eval.config import DEFAULT
    ev, p = DeckEvaluator(POOL, target_types(POOL)), _player()
    walks = sample_walks(PlannedRoute(["combat", "rest", "boss"], 4, 1, None, "OVERGROWTH"), 1, 0, 2, 3)
    strong = {**p, "hp": 500, "max_hp": 500}
    flat = DeckEvaluator(POOL, target_types(POOL), config=DEFAULT.tuned(continuation_share=0.0))
    gap = ev.score_walks(p["deck"], strong, walks).mean - flat.score_walks(p["deck"], strong, walks).mean
    assert abs(gap - DEFAULT.continuation_share * (DEFAULT.act_rooms + DEFAULT.act_rooms - DEFAULT.lookahead_rooms)) < 1e-6          # act 1: all of act 3 and the act 2 rooms beyond the lookahead


@needs_pool
def test_potions_held_and_max_hp_gained_count_once_at_the_end():
    from agents.deck_eval.route_sim import sample_walks
    from agents.deck_eval.config import DEFAULT
    ev, p = DeckEvaluator(POOL, target_types(POOL)), _player()
    walks = sample_walks(PlannedRoute(["rest", "combat"], 4, 0, None, "OVERGROWTH"), 1, 0, 1, 3)
    plain = {**p, "hp": 500, "max_hp": 500, "potions": []}
    held = {**plain, "potions": [{"id": "FIRE_POTION", "name": "Fire Potion"}] * 2}
    gap = ev.score_walks(p["deck"], held, walks).rewards[0] - ev.score_walks(p["deck"], plain, walks).rewards[0]
    assert 0 < gap <= 2 * DEFAULT.potion_credit + 1e-6


@needs_pool
def test_the_event_chooser_takes_the_better_option_and_leaves_what_it_cannot_play():
    from agents.deck_eval.event_chooser import EventChooser
    from agents.deck_eval.config import DEFAULT
    advisor = DeckAdvisor(pool=POOL, log=lambda *_: None, route_provider=lambda: PlannedRoute(["combat", "rest", "combat", "boss"], 4, 1, None, "OVERGROWTH"),
                          config=DEFAULT.tuned(event_seconds=0.2))
    p = _player()
    p.update(hp=1, max_hp=80)
    def screen(event_id, keys):
        options = [Option(k, {"action": "choose_event_option", "index": i}, {"index": i, "title": k}) for i, k in enumerate(keys)]
        return Decision("event", {"event_id": event_id, "player": p, "context": {"act": 1, "floor": 5}}, options)
    chooser = EventChooser(advisor)
    assert chooser.choose(screen("ABYSSAL_BATHS", ["immerse", "abstain"])).label == "abstain"        # immersing at 1 HP is death, abstaining heals 10
    assert [k.rpartition(":")[2] for k in chooser.path] == ["abstain"]          # the key of an option told by its title (no text key from this bridge): its position, then its title
    assert chooser.choose(screen("ABYSSAL_BATHS", ["only"])).label == "only"
    assert chooser.choose(screen("SOME_UNMODELLED_EVENT", ["a", "b"])) is None
    assert chooser.choose(screen("ABYSSAL_BATHS", ["x", "y"])) is None and chooser.path == []          # option names the model does not know


@needs_pool
def test_the_event_chooser_plays_options_the_game_titles_differently():
    """THIS_OR_THAT: the game shows "This" and "That" for what the engine calls plain and ornate; the text key (sent by the bridge) tells them."""
    from agents.deck_eval.event_chooser import EventChooser
    from agents.deck_eval.config import DEFAULT
    advisor = DeckAdvisor(pool=POOL, log=lambda *_: None, route_provider=lambda: PlannedRoute(["combat", "rest", "combat", "boss"], 4, 1, None, "OVERGROWTH"),
                          config=DEFAULT.tuned(event_seconds=0.2))
    p = _player()
    p.update(hp=40, max_hp=80)
    def screen(with_text_key):
        titles = (("This", "PLAIN"), ("That", "ORNATE"))
        options = [Option(t, {"action": "choose_event_option", "index": i},
                          {"index": i, "title": t, "page_size": 2, **({"text_key": "THIS_OR_THAT.pages.INITIAL.options." + k} if with_text_key else {})})
                   for i, (t, k) in enumerate(titles)]
        return Decision("event", {"event_id": "THIS_OR_THAT", "player": p, "context": {"act": 1, "floor": 5}}, options)
    for with_text_key in (True, False):          # by name, and by position when the bridge sends no text key
        chosen = EventChooser(advisor).choose(screen(with_text_key))
        assert chosen is not None and chosen.label in ("This", "That")


@needs_pool
def test_the_race_stops_at_its_time_and_pairs_the_candidates():
    advisor = DeckAdvisor(pool=POOL, log=lambda *_: None, route_provider=lambda: PlannedRoute(["combat", "rest", "combat", "boss"], 4, 1, None, "OVERGROWTH"))
    decision = Decision("rest", {"player": _player(), "context": {"act": 1, "floor": 5}}, [])
    ev, p = advisor.evaluator, _player()
    plays = {"a": lambda walks: ev.score_walks(p["deck"], p, walks).rewards, "b": lambda walks: ev.score_walks(p["deck"], {**p, "hp": 20}, walks).rewards}
    rewards, count, seconds = advisor.race(decision, plays, 0.5)
    assert len(rewards["a"]) == len(rewards["b"]) == count and count >= 2 and 0.4 < seconds < 3.0
    assert advisor.race(decision, plays, 0.0)[1] == 2                  # one batch is always played
    assert advisor.race(decision, plays, 99, max_walks=6)[1] == 6


@needs_pool
def test_an_event_fight_is_not_a_room_and_leaves_the_dice_of_later_fights_alone():
    from agents.deck_eval.route_sim import EventPlan, RouteSimulator
    ev = DeckEvaluator(POOL, target_types(POOL))
    walk = _event_walk()
    plain = RouteSimulator(_walk_run(walk, hp=70), walk, ev.config)
    fought = RouteSimulator(_walk_run(walk, hp=70), walk, ev.config, EventPlan("BATTLEWORN_DUMMY", [], "setting_1"))
    a, b = plain.walk_route(), fought.walk_route()
    assert plain.credits == fought.credits and a.reward == b.reward and a.fights == b.fights          # the dummy changes nothing it does not pay for


@needs_pool
def test_the_ancient_chooser_reads_the_screen_and_takes_the_best_relic():
    import agents.deck_eval.ancient_chooser as ac
    from agents.deck_eval.route_sim import AncientPlan
    from agents.deck_eval.config import DEFAULT
    chooser = ac.AncientChooser(DeckAdvisor(pool=POOL, log=lambda *_: None, config=DEFAULT.tuned(ancient_seconds=0.3)))
    assert chooser.names["seaglass"] == "SEA_GLASS" and chooser.names["paelsflesh"] == "PAELS_FLESH" and chooser.names["lostcoffer"] == "LOST_COFFER"
    for title, relic in (("Pael's Flesh", "PAELS_FLESH"), ("Pael's Tears", "PAELS_TEARS"), ("Tanx's Whistle", "TANXS_WHISTLE"), ("Lord's Parasol", "LORDS_PARASOL"), ("Neow's Bones", "NEOWS_BONES")):
        assert ac.resolve(title, "PAEL", chooser.names).relic == relic, title          # the game writes the apostrophe, the engine's names do not
    assert ac.resolve("Sea Glass (Silent)", "OROBAS", chooser.names) == AncientPlan("OROBAS", "SEA_GLASS", {"character": "SILENT"})
    assert ac.resolve("Dusty Tome", "DARV", chooser.names).setup == {"card": "CORRUPTION"} and ac.resolve("Not A Relic", "DARV", chooser.names) is None
    p = _player()
    def screen(ancient, titles):
        options = [Option(t, {"action": "choose_event_option", "index": i}, {"index": i, "title": t}) for i, t in enumerate(titles)]
        return Decision("event", {"event_id": ancient, "player": p, "context": {"act": 1, "floor": 0}}, options)
    assert chooser.choose(screen("PAEL", ["Paels Flesh", "Paels Claw", "Paels Legion"])).label in ("Paels Flesh", "Paels Claw", "Paels Legion")
    assert chooser.choose(screen("PAEL", ["Paels Flesh", "A Thing The Engine Lacks"])) is None          # a relic it does not know: left to the default
    assert chooser.choose(screen("ABYSSAL_BATHS", ["immerse", "abstain"])) is None                       # not an ancient


@needs_pool
def test_a_relic_from_an_ancient_is_in_the_run_before_the_walk_and_is_the_same_walk_for_each():
    from agents.deck_eval.route_sim import AncientPlan, RouteSimulator, sample_walks
    ev = DeckEvaluator(POOL, target_types(POOL))
    walk = sample_walks(None, 1, 0, 1, 5)[0]
    run = _walk_run(walk)
    sim = RouteSimulator(run, walk, ev.config, AncientPlan("DARV", "ASTROLABE", {}))
    sim.reseed("ancient")
    sim.take_ancient_relic(sim.opening.option())
    assert any(r["id"] == "ASTROLABE" for r in run.relics)
    p = _player()
    a = ev.score_walks(p["deck"], p, [walk], AncientPlan("DARV", "ASTROLABE", {}))
    assert a.rewards == ev.score_walks(p["deck"], p, [walk], AncientPlan("DARV", "ASTROLABE", {})).rewards


# --- the planned path -----------------------------------------------------------------------------------------------------------------------------------

def _map(*rows):
    """A tiny act: `rows` is a list of (col, row, type, children)."""
    return [{"col": c, "row": r, "type": t, "children": [list(x) for x in ch]} for c, r, t, ch in rows]


def test_paths_that_differ_only_in_where_the_question_marks_are_count_once():
    from agents.deck_eval.path_search import enumerate_paths, path_key
    from agents.route import node_kind
    nodes = {(n["col"], n["row"]): n for n in _map((0, 1, "Monster", [(0, 2), (1, 2)]), (0, 2, "Unknown", [(0, 3)]), (1, 2, "Monster", [(1, 3)]),
                                                   (0, 3, "RestSite", [(0, 4)]), (1, 3, "RestSite", [(1, 4)]), (0, 4, "Boss", []), (1, 4, "Boss", []))}
    paths = enumerate_paths(nodes, (0, 1), "Monster", node_kind)
    assert sorted(paths) == [("combat", "combat", "rest", "boss"), ("combat", "unknown", "rest", "boss")]
    assert path_key(("combat", "unknown", "rest")) != path_key(("combat", "rest"))


def test_the_path_score_is_the_node_score_of_the_best_route():
    from agents.pathing import PathPlanner
    planner = PathPlanner()
    nodes = {(n["col"], n["row"]): n for n in _map((0, 1, "Monster", [(0, 2)]), (0, 2, "Elite", [(0, 3)]), (0, 3, "RestSite", [(0, 4)]), (0, 4, "Boss", []))}
    score, rests, kinds = planner.best_route(nodes, (0, 1), "Monster", 0, False, False, 0, 0)
    assert abs(planner.path_score(tuple(kinds), 1, 0, False, False, 0, 0) - score) < 1e-9


@needs_pool
def test_the_planner_walks_the_paths_and_keeps_the_best_as_the_planned_route():
    import agents.deck_eval.path_search as ps
    from agents.pathing import PathPlanner
    from agents.decision import MAP
    nodes = _map((0, 1, "Monster", [(0, 2)]), (1, 1, "RestSite", [(1, 2)]), (0, 2, "Elite", [(0, 3)]), (1, 2, "Monster", [(1, 3)]),
                 (0, 3, "RestSite", [(0, 4)]), (1, 3, "RestSite", [(1, 4)]), (0, 4, "Boss", []), (1, 4, "Boss", []))
    logs = []
    from agents.deck_eval.config import DEFAULT
    advisor = DeckAdvisor(pool=POOL, log=logs.append, config=DEFAULT.tuned(path_seconds=1.0))
    planner = PathPlanner()
    planner.advisor = advisor
    choices = [n for n in nodes if n["row"] == 1]
    options = [Option(c["type"], {"action": "choose_map_node", "index": i}, {**c, "index": i}) for i, c in enumerate(choices)]
    state = {"nodes": nodes, "visited": [], "choices": choices, "player": _player(), "context": {"act": 1, "floor": 1}, "boss": {"encounter": "VANTOM_BOSS"}, "act_model": "OVERGROWTH"}
    chosen = planner.choose(Decision(MAP, state, options))
    assert chosen in options and planner.route.kinds[0] == _kind_of(chosen) and planner.route.kinds[-1] == "boss" and planner.route.act == 1
    assert logs and logs[0].startswith("path (") and "through" in logs[0]
    planner.advisor = None
    again = planner.choose(Decision(MAP, {**state, "player": {"hp": 70, "max_hp": 80}}, options))          # no deck, no advisor: the node scores
    assert again in options


def _kind_of(option):
    from agents.route import node_kind
    return node_kind(option.data["type"])


@needs_pool
def test_a_shop_in_a_walk_spends_the_gold_relics_first_then_a_strike_removal_then_cards():
    from agents.deck_eval.route_sim import RouteSimulator
    ev = DeckEvaluator(POOL, target_types(POOL))
    walk = _event_walk()
    run = _walk_run(walk)
    run.gold, deck, relics = 900, len(run.deck), len(run.relics)
    sim = RouteSimulator(run, walk, ev.config)
    sim.reseed("shop")
    sim.shop()
    assert len(run.relics) > relics                                          # a relic first
    strikes = lambda r: sum(c["id"].startswith("STRIKE") for c in r.deck)
    assert strikes(run) == 4                                                 # then a Strike went
    assert run.gold < 900 and len(run.deck) != deck                          # the rest went on cards
    poor = _walk_run(walk)
    poor.gold = 0
    sim = RouteSimulator(poor, walk, ev.config)
    sim.reseed("shop")
    sim.shop()
    assert poor.gold == 0 and len(poor.deck) == len(_walk_run(walk).deck)


def test_a_shop_on_the_route_is_a_walk_room():
    from agents.deck_eval.route_sim import sample_walks, ROOM_OF_STEP
    walk = sample_walks(PlannedRoute(["combat", "shop", "combat", "boss"], 3, 1, None, "OVERGROWTH"), 1, 0, 1, 2)[0]
    assert "shop" in walk.steps and ROOM_OF_STEP["shop"] == "Shop" and walk.fights == 2


def test_a_walk_never_buys_the_shops_third_relic_and_buys_the_cheapest_of_the_others():
    from agents.deck_eval.route_sim import WalkAgent
    items = [{"index": i, "category": "relic", "cost": c, "can_afford": True, "is_stocked": True} for i, c in enumerate((120, 200, 300))]
    options = [Option(f"buy {i['index']}", {"action": "shop_purchase", "index": i["index"]}, i) for i in items] + [Option("leave shop", {"action": "proceed"})]
    agent = WalkAgent(1.0, 1)
    state = {"items": items, "player": {"gold": 999, "deck": []}}
    assert agent.get_decision(Decision("shop", state, options)).data["index"] == 0          # the 300 gold relic is the shop's own; of the others the 120 gold one is cheaper
    assert agent.get_decision(Decision("shop", state, [options[1], options[2], options[3]])).data["index"] == 1
    assert agent.get_decision(Decision("shop", state, options[:1] + options[2:])).name in ("shop_purchase", "proceed")
    only_third = [options[2], options[3]]
    assert agent.get_decision(Decision("shop", state, only_third)).name == "proceed"


@needs_pool
def test_a_question_mark_in_a_walk_becomes_what_the_odds_make_of_it_and_costs_the_same_for_every_deck():
    from agents.deck_eval.route_sim import sample_walks, play_walk, ROOM_OF_STEP
    ev = DeckEvaluator(POOL, target_types(POOL))
    p = _player()
    walks = sample_walks(PlannedRoute(["combat", "unknown", "unknown", "unknown", "combat", "boss"], 3, 1, None, "OVERGROWTH"), 1, 0, 12, 7)
    assert ROOM_OF_STEP["unknown"] == "Unknown" and all(w.steps[:3] == ["unknown"] * 3 and w.fights == 2 for w in walks)
    again = ev.score_walks(p["deck"], p, walks)
    assert again.rewards == ev.score_walks(p["deck"], p, walks).rewards          # repeatable
    seen = set()
    from agents.deck_eval import route_sim as rs
    for w in walks:
        run = _walk_run(w)
        sim = rs.RouteSimulator(run, w, ev.config)
        sim.walk_route()
        seen |= {v.room for v in run.history}
    assert {"Event", "Monster"} & seen and not {"Unknown"} & seen                   # the "?" shows as the room it turned into


def test_an_event_option_in_a_walk_is_a_random_one_the_same_for_every_deck():
    from agents.deck_eval.route_sim import WalkAgent
    options = [Option(k, {"action": "choose_event_option", "index": i}, {"index": i, "title": k}) for i, k in enumerate(("a", "b", "c", "d"))]
    decision = Decision("event", {"event_id": "SOME_EVENT"}, options)
    a, b = WalkAgent(1.0, 5), WalkAgent(0.0, 5)
    b._rng.random()            # a deck that used the walk's dice differently
    assert a.get_decision(decision).label == b.get_decision(decision).label
    assert len({WalkAgent(1.0, s).get_decision(decision).label for s in range(30)}) > 1


@needs_pool
def test_an_engine_error_in_a_rollout_ends_the_walk_instead_of_the_run(monkeypatch, capsys):
    from agents.deck_eval import route_sim as rs
    from sts2_lite.combat import CombatSimulator
    ev, p = DeckEvaluator(POOL, target_types(POOL)), _player()
    walks = rs.sample_walks(PlannedRoute(["rest", "combat", "boss"], 4, 0, None, "OVERGROWTH"), 1, 0, 2, 3)
    monkeypatch.setattr(CombatSimulator, "perform_action", lambda self, action: (_ for _ in ()).throw(IndexError("list index out of range")))
    rs.ENGINE_ERRORS.clear()
    score = ev.score_walks(p["deck"], p, walks)
    assert score.win_rate == 0 and all(r < 1.0 for r in score.rewards)             # a death in the first fight, whatever it was
    assert rs.ENGINE_ERRORS == {"IndexError: list index out of range": 2}
    assert capsys.readouterr().out.count("engine error in a rollout") == 1          # reported once, not per walk


@needs_pool
def test_the_fight_correction_turns_some_of_the_policys_losses_into_wins_the_same_for_every_deck(monkeypatch):
    from agents.deck_eval import route_sim
    from agents.deck_eval.route_sim import sample_walks
    from agents.deck_eval.config import DEFAULT
    ev, p = DeckEvaluator(POOL, target_types(POOL)), _player()
    walks = sample_walks(PlannedRoute(["combat", "elite", "combat", "boss"], 3, 1, None, "OVERGROWTH"), 1, 0, 4, 2)
    dying = {**p, "hp": 1}
    raw = DeckEvaluator(POOL, target_types(POOL), config=DEFAULT.tuned(correct=False)).score_walks(p["deck"], dying, walks)
    monkeypatch.setattr(route_sim, "CORRECTION", {k: (0.5, (1.0, 1.0, 1.0), 0.5) for k in route_sim.CORRECTION})
    sure = ev.score_walks(p["deck"], dying, walks)
    assert sure.mean > raw.mean and sure.rewards == ev.score_walks(p["deck"], dying, walks).rewards          # rescued, and the rolls repeat
    monkeypatch.setattr(route_sim, "CORRECTION", {k: (0.5, (0.0, 0.0, 0.0), 0.5) for k in route_sim.CORRECTION})
    assert ev.score_walks(p["deck"], dying, walks).rewards == raw.rewards           # no chance of a rescue: the policy's own losses


def test_the_elite_bonus_grows_with_the_row_of_the_elite():
    import agents.deck_eval.path_search as ps
    from agents.deck_eval.config import DEFAULT
    early = ps.elite_bonus(("combat", "elite", "rest"), 1, 14)
    late = ps.elite_bonus(("combat", "elite", "rest"), 9, 14)
    assert 0 < early < late <= DEFAULT.elite_bonus and ps.elite_bonus(("combat", "rest"), 1, 14) == 0
    assert ps.elite_bonus(("elite", "elite"), 1, 14) > ps.elite_bonus(("elite",), 1, 14)
