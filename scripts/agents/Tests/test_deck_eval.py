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
    assert skip_floor() == 0.3


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
    assert len(logged) == 2 and "needs" in logged[0] and "cards to come" in logged[1]


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


@needs_pool
def test_only_the_next_elite_is_narrowed():
    from agents.deck_eval.future_cards import sample_future
    seen = ["ENTOMANCER_ELITE", "DECIMILLIPEDE_ELITE"]
    route = PlannedRoute(["rest", "elite", "combat", "elite", "boss"], 4, 2, None, "HIVE", seen)
    fights, _ = sample_future(POOL, route, 2, 0, 300, 1)
    # the first elite on the route can only be the Prisms; the second one is open
    assert {f.encounter for f in fights if f.kind == "elite"} > {"INFESTED_PRISMS_ELITE"}
    one = PlannedRoute(["rest", "elite", "combat", "boss"], 4, 2, None, "HIVE", seen)
    fights, _ = sample_future(POOL, one, 2, 0, 200, 1)
    assert {f.encounter for f in fights if f.kind == "elite"} == {"INFESTED_PRISMS_ELITE"}


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


from agents.deck_eval.fight_mix import fights_until_next_rest
from agents.deck_eval.upgrade_chooser import full_heal
import random


def test_full_heal_is_not_capped():
    assert full_heal(None, {"hp": 79, "max_hp": 80}) == 24


@needs_pool
def test_rule_one_upgrades_when_the_rest_would_be_cut_short():
    chooser = UpgradeChooser(DeckAdvisor(fights=10, pool=POOL, log=lambda *_: None))
    assert chooser.choose_rest(_rest_decision(70)).data["id"] == "SMITH"        # 10 HP missing, a rest heals 24


@needs_pool
def test_fights_until_next_rest_stop_at_the_rest_site():
    route = PlannedRoute(["rest", "combat", "elite", "rest", "combat", "boss"], 3, 1)
    fights = fights_until_next_rest(POOL, route, 1, 0, random.Random(1))
    assert [f.kind for f in fights][0] in ("normal", "weak") and fights[1].kind in ("elite", "normal", "weak") and len(fights) == 2
    last = fights_until_next_rest(POOL, PlannedRoute(["rest", "combat", "boss"], 3, 1), 1, 0, random.Random(1))
    assert last[-1].kind == "boss"


@needs_pool
def test_a_chain_carries_hp_and_a_dead_deck_fails_it():
    ev, p = DeckEvaluator(POOL, target_types(POOL)), _player()
    fights = fights_until_next_rest(POOL, PlannedRoute(["rest", "combat", "elite", "boss"], 0, 1), 1, 0, random.Random(2))
    alive, hp = ev.play_chain(p["deck"], {**p, "hp": 1}, fights, 5)
    assert alive is False and hp == 0


def test_early_floor_is_halved_for_the_first_three_rewards():
    assert skip_floor(early=True) == skip_floor() / 2 and skip_floor(early=True) == 0.15


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
    assert skip_floor(win_rate=0.8) == skip_floor() == 0.3
    assert skip_floor(win_rate=0.4) == 0.15
    assert abs(skip_floor(win_rate=0.3) - 0.3 * 0.375) < 1e-9


def test_fights_fit_the_time_budget():
    from agents.deck_eval.card_reward_chooser import fights_for, MIN_FIGHTS, MAX_FIGHTS
    assert fights_for(15.0, 0.002, 4) == 1875
    assert fights_for(15.0, 0.002, 4) > fights_for(8.0, 0.002, 4)
    assert fights_for(15.0, 1.0, 4) == MIN_FIGHTS and fights_for(15.0, 1e-9, 4) == MAX_FIGHTS


@needs_pool
def test_pilot_sets_the_fight_count_and_big_decisions_get_the_longer_budget(monkeypatch):
    from types import SimpleNamespace
    from agents.deck_eval import card_reward_chooser as crc
    monkeypatch.setattr(crc, "BUDGET_SECONDS", 0.01)
    monkeypatch.setattr(crc, "BIG_BUDGET_SECONDS", 0.02)
    monkeypatch.setattr(crc, "MAX_FIGHTS", 400)
    p = _player()
    state = lambda floor: {"type": "decision", "decision": "card_reward", "player": p, "context": {"act": 1, "floor": floor}}
    options = [Option("Bash", {"action": "select_card_reward", "card_index": 0}, {"index": 0, "id": "BASH", "name": "Bash", "type": "Attack", "cost": 2}),
               Option("skip", {"action": "skip_card_reward"})]
    route = SimpleNamespace(kinds=["combat", "combat"], combats_before=0, act=1, boss=None, act_model=None)
    logs = []
    chooser = CardRewardChooser(pool=POOL, route_provider=lambda: route, log=logs.append)
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


@needs_pool
def test_future_sample_is_repeatable_and_a_deck_with_extras_plays_them():
    from types import SimpleNamespace
    from agents.deck_eval.future_cards import sample_future
    route = SimpleNamespace(kinds=["combat", "combat", "elite", "boss"], combats_before=0, boss=None, act_model=None)
    a = sample_future(POOL, route, 1, 0, 30, 5)
    b = sample_future(POOL, route, 1, 0, 30, 5)
    assert [f.name for f in a[0]] == [f.name for f in b[0]] and a[1] == b[1]
    assert {len(e) for e in a[1]} <= {0, 1, 2, 3}      # act 1: 0.8 cards per fight ahead, 3 fights ahead
    ev, p = DeckEvaluator(POOL, target_types(POOL)), _player()
    with_extras = ev.score(p["deck"], p, a[0][:5], 3, a[1][:5])
    assert len(with_extras.rewards) == 5


def test_extra_cards_scale_with_the_act():
    from agents.deck_eval.future_cards import cards_gained, fight_act
    from types import SimpleNamespace
    import random
    r = random.Random(3)
    mean = lambda k, act: sum(cards_gained(k, act, r) for _ in range(4000)) / 4000
    assert abs(mean(10, 1) - 8.0) < 0.01 and abs(mean(10, 2) - 5.0) < 0.01 and abs(mean(10, 3) - 3.0) < 0.01
    assert abs(mean(3, 1) - 2.4) < 0.1 and abs(mean(1, 3) - 0.3) < 0.05
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
