from agents.decision import EVENT, Decision, Option
from agents.deck_eval.route_sim import WalkAgent
from sts2_lite.campaign import screens
from sts2_lite.event.core import Option as EventOption


def options(costs):
    return [Option(f"o{i}", {"action": "choose_event_option", "index": i}, {"index": i, **({"hp_cost": c} if c else {})}) for i, c in enumerate(costs)]


def test_a_walk_never_takes_an_option_that_costs_all_its_hp_while_another_is_left():
    for seed in range(50):
        d = Decision(EVENT, {"event_id": "SLIPPERY_BRIDGE", "player": {"hp": 5}}, options([0, 6]))
        assert WalkAgent(1.0, seed).get_decision(d).label == "o0"
    d = Decision(EVENT, {"event_id": "X", "player": {"hp": 5}}, options([7, 9]))
    assert WalkAgent(1.0, 0).get_decision(d).label in ("o0", "o1")         # nothing safe: any


def test_the_event_screen_shows_an_option_s_hp_cost():
    from sts2_lite.event.run import card_entry
    from sts2_lite.run import RunState
    run = RunState.from_player({"hp": 5, "max_hp": 80, "gold": 0, "relics": [], "potions": []}, [card_entry("STRIKE_IRONCLAD")])
    shown = screens.event_choice(run, "SLIPPERY_BRIDGE", [EventOption("overcome", None), EventOption("hold_on", None, hp_cost=6, lethal=True)])
    assert shown["options"][1]["hp_cost"] == 6 and "hp_cost" not in shown["options"][0]


def test_a_walk_leaves_options_that_end_the_run_or_take_much_max_hp():
    opts = [Option("decipher", {"index": 0}, {"index": 0, "max_hp_cost": 12}), Option("give_up", {"index": 1}, {"index": 1}),
            Option("double_down", {"index": 2}, {"index": 2, "lethal": True})]
    for seed in range(50):
        d = Decision(EVENT, {"event_id": "TABLET_OF_TRUTH", "player": {"hp": 50}}, opts)
        assert WalkAgent(1.0, seed).get_decision(d).label == "give_up"


def test_the_event_screen_shows_lethal_and_max_hp_cost():
    from sts2_lite.event.run import card_entry
    from sts2_lite.run import RunState
    run = RunState.from_player({"hp": 50, "max_hp": 80, "gold": 0, "relics": [], "potions": []}, [card_entry("STRIKE_IRONCLAD")])
    shown = screens.event_choice(run, "TRIAL", [EventOption("double_down", None, lethal=True), EventOption("decipher", None, max_hp_cost=24)])
    assert shown["options"][0]["lethal"] is True and shown["options"][1]["max_hp_cost"] == 24
