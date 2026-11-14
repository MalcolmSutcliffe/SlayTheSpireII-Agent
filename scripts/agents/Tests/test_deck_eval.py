import pytest

from agents.decision import Decision, Option, CARD_REWARD
from agents.pathing import PlannedRoute
from agents.deck_eval.fight_pool import load_pool, target_types
from agents.deck_eval.fight_mix import mix_ahead, new_act_mix, pick_fights
from agents.deck_eval.evaluator import DeckEvaluator
from agents.deck_eval.card_reward_chooser import CardRewardChooser, paired_gain, skip_floor

POOL = load_pool()
needs_pool = pytest.mark.skipif(not POOL, reason="no round-1 captures in data/runs")


def test_skip_floor_falls_as_the_deck_grows():
    assert skip_floor(10) > skip_floor(20) > skip_floor(40)
    assert skip_floor(5) == skip_floor(10)


def test_paired_gain():
    mean, se = paired_gain([3, 4, 5, 6], [1, 2, 3, 4])
    assert mean == 2 and se == 0


def test_mix_follows_the_planned_route():
    # act 1: 3 weak fights, 1 already fought, the room in progress is a combat -> 1 weak left; route ahead: 3 combats, 1 elite, boss
    route = PlannedRoute(["combat", "combat", "rest", "combat", "elite", "combat", "boss"], 1, 1)
    mix = mix_ahead(1, route)
    assert (mix.weak, mix.normal, mix.elite, mix.act) == (1, 2, 1, 1)
    near_end = mix_ahead(1, PlannedRoute(["rest", "boss"], 7, 1))
    assert near_end.boss > mix.boss > new_act_mix(1).boss - 0.01        # the boss counts for more the closer it is


def test_boss_reward_looks_at_the_next_act():
    mix = mix_ahead(1, PlannedRoute(["boss"], 6, 1))
    assert mix.act == 2 and mix.weak == 2
    assert mix_ahead(3, PlannedRoute(["boss"], 6, 3)).act == 3


@needs_pool
def test_pool_kinds():
    assert {t.kind for t in POOL} <= {"weak", "normal", "elite", "boss"}
    assert any(t.kind == "boss" for t in POOL)
    fights = pick_fights(POOL, new_act_mix(1), 50, 1)
    assert fights == pick_fights(POOL, new_act_mix(1), 50, 1)


def _player():
    template = next(t for t in POOL if t.kind == "weak").state["player"]
    return {"hp": 70, "max_hp": 80, "relics": template["relics"], "deck": template["deck"]}


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
    assert len(logged) == 1 and "needs" in logged[0]


from agents.deck_eval.boss_spawner import BOSS_ACTS, boss_of, bosses_of_act, enemy_dict, normalize_boss_id, spawn_boss


def test_boss_ids():
    assert normalize_boss_id("soul fysh") == "SOUL_FYSH_BOSS" and normalize_boss_id("VANTOM_BOSS") == "VANTOM_BOSS" and normalize_boss_id(None) is None
    assert boss_of(["CRUSHER_0", "ROCKET_0"]) == "KAISER_CRAB_BOSS" and boss_of(["TOADPOLE_0"]) is None
    assert {v for a, v in BOSS_ACTS.values() if a == 1} == {"OVERGROWTH", "UNDERDOCKS"}


def test_enemy_dict_first_move_comes_from_the_sim_table():
    giant = enemy_dict("WATERFALL_GIANT", "Waterfall Giant", 240, "PRESSURIZE", 0)
    assert giant["move_id"] == "PRESSURIZE_MOVE" and giant["follow_up_id"] == "STOMP_MOVE" and giant["intents"][0]["type"] == "Buff"
    assert enemy_dict("SOUL_FYSH", "Soul Fysh", 211, "BECKON", 0)["intents"][0]["type"] == "StatusCard"


@needs_pool
def test_spawned_bosses_by_ascension_and_played_to_the_end():
    ev, p = DeckEvaluator(POOL, target_types(POOL)), _player()
    for enc, hp0, hp9 in (("WATERFALL_GIANT_BOSS", 240, 250), ("SOUL_FYSH_BOSS", 211, 221), ("KNOWLEDGE_DEMON_BOSS", 379, 399)):
        base = next(t for t in POOL if t.act == BOSS_ACTS[enc][0])
        assert spawn_boss(enc, base, 0).state["enemies"][0]["max_hp"] == hp0
        assert spawn_boss(enc, base, 9).state["enemies"][0]["max_hp"] == hp9
        s = ev.score(p["deck"], p, [spawn_boss(enc, base, 0)] * 3, 1)
        assert len(s.rewards) == 3


@needs_pool
def test_pick_fights_uses_the_boss_the_map_showed():
    for enc in ("SOUL_FYSH_BOSS", "VANTOM_BOSS"):
        if enc == "VANTOM_BOSS" and not any(t.boss == enc for t in POOL):
            continue        # no capture of it in this checkout
        mix = new_act_mix(1).__class__(1, 0, 0, 0, 1.0, BOSS_ACTS[enc][1], enc)
        assert {f.boss for f in pick_fights(POOL, mix, 20, 1)} == {enc}


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
