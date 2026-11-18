"""Potion cycling on the rewards screen: Fruit Juice is drunk, a full belt drinks Blood Potion / Fruit Juice first, else throws away its worst potion for a better one."""
from agents.decision import Decision, Option, REWARDS
from agents.my_agent import MyAgent
from agents.potion_cycle import cycle
from agent_runner.executors import command_for


def potion(slot, id):
    return {"id": id, "name": id.title(), "slot": slot}

def screen(held, offered=None, slots=3):
    items = [{"index": 0, "type": "gold", "description": "10 Gold"}] + ([{"index": 1, "type": "potion", "potion_id": offered, "description": offered}] if offered else [])
    open_slots = slots - len(held)
    options = [Option("gold", {"action": "claim_reward", "index": 0}, items[0])]
    if offered and open_slots > 0:
        options.append(Option("potion", {"action": "claim_reward", "index": 1}, items[1]))
    options.append(Option("proceed", {"action": "proceed"}))
    return Decision(REWARDS, {"items": items, "player": {"potions": held, "potion_slots": slots, "open_potion_slots": open_slots}}, options)


def test_fruit_juice_is_drunk_at_once():
    option = cycle(screen([potion(0, "FIRE_POTION"), potion(1, "FRUIT_JUICE")]))
    assert option.action["action"] == "use_potion" and option.action["slot"] == 1

def test_a_belt_with_room_just_claims_the_potion():
    assert cycle(screen([potion(0, "FIRE_POTION")], "BLOCK_POTION")) is None

def test_a_full_belt_drinks_a_blood_potion_first():
    option = cycle(screen([potion(0, "FIRE_POTION"), potion(1, "BLOOD_POTION"), potion(2, "BLOCK_POTION")], "STRENGTH_POTION"))
    assert option.action["action"] == "use_potion" and option.action["slot"] == 1

def test_a_full_belt_throws_away_its_worst_potion_for_a_better_one():
    belt = [potion(0, "OROBIC_ACID"), potion(1, "FORTIFIER"), potion(2, "OROBIC_ACID")]          # priced 20, 15, 20 (RewardParams.potion_bonus)
    option = cycle(screen(belt, "LUCKY_TONIC"))                                                  # 18: better than the Fortifier only
    assert option.action == {"action": "discard_potion", "slot": 1, "potion_id": "FORTIFIER"}
    assert cycle(screen(belt, "FORTIFIER")) is None

def test_a_potion_worth_no_more_is_not_swapped_in():
    belt = [potion(0, "OROBIC_ACID"), potion(1, "OROBIC_ACID"), potion(2, "OROBIC_ACID")]
    assert cycle(screen(belt, "OROBIC_ACID")) is None

def test_no_potion_on_offer_changes_nothing():
    assert cycle(screen([potion(0, "FIRE_POTION")] * 1 + [potion(1, "FIRE_POTION"), potion(2, "FIRE_POTION")])) is None

def test_the_agent_cycles_before_it_claims_and_claims_after():
    agent = MyAgent(seed=1)
    full = screen([potion(0, "FIRE_POTION"), potion(1, "BLOOD_POTION"), potion(2, "FIRE_POTION")], "STRENGTH_POTION")
    assert agent.get_decision(full).action["action"] == "use_potion"
    room = screen([potion(0, "FIRE_POTION"), potion(2, "FIRE_POTION")], "STRENGTH_POTION")
    assert agent.get_decision(room).action["action"] == "claim_reward"

def test_the_runner_sends_the_potion_actions():
    assert command_for({"action": "use_potion", "slot": 2}) == ["use-potion", "2"]
    assert command_for({"action": "discard_potion", "slot": 1}) == ["discard-potion", "1"]


def shop(held, floor=5):
    options = [Option("leave shop", {"action": "proceed"})]
    return Decision("shop", {"items": [], "context": {"floor": floor}, "player": {"gold": 10, "deck": [], "potions": held, "potion_slots": 3, "open_potion_slots": 3 - len(held)}}, options)

def test_a_foul_potion_is_used_in_a_shop_and_a_failed_use_is_not_repeated():
    agent = MyAgent(seed=1)
    belt = [potion(0, "FIRE_POTION"), potion(1, "FOUL_POTION")]
    option = agent.get_decision(shop(belt))
    assert option.action["action"] == "use_potion" and option.action["slot"] == 1
    assert agent.get_decision(shop(belt)).action == {"action": "proceed"}          # still held: it did not work, so the agent goes on (this shop: no items to buy)
    gone = agent.get_decision(shop([belt[0]]))
    assert gone.action["action"] == "proceed"
    assert agent.get_decision(shop([potion(0, "FOUL_POTION")], floor=9)).action["action"] == "use_potion"          # the next shop tries again


def test_the_screens_list_the_potion_actions_the_agent_may_choose():
    from agent_runner.decision_builders import rewards_options, shop_options
    belt = [potion(0, "FIRE_POTION"), potion(1, "FOUL_POTION"), potion(2, "BLOOD_POTION")]
    state = {"items": [{"index": 0, "type": "gold", "description": "10 Gold"}], "can_proceed": True, "player": {"potions": belt, "open_potion_slots": 0}}
    names = lambda options: [(o.action["action"], o.action["slot"]) for o in options if o.action["action"].endswith("_potion")]
    expect = [("use_potion", 1), ("use_potion", 2), ("discard_potion", 0), ("discard_potion", 1), ("discard_potion", 2)]
    assert names(rewards_options(state)) == expect and names(shop_options(state)) == expect
    assert rewards_options({"items": [], "can_proceed": False, "player": {"potions": belt}}) == []          # nothing to click yet: nothing to choose
    agent = MyAgent(seed=1)
    decision = Decision("shop", {"items": [], "context": {"floor": 3}, "player": {"gold": 0, "deck": [], "potions": belt}}, shop_options(state))
    assert agent.get_decision(decision) in decision.options                                            # the runner takes only what the screen lists

def test_a_heart_of_iron_replaces_a_swift_potion_on_a_full_belt():
    belt = [potion(0, "LUCKY_TONIC"), potion(1, "SWIFT_POTION")]
    option = cycle(screen(belt, "HEART_OF_IRON", slots=2))
    assert option.action == {"action": "discard_potion", "slot": 1, "potion_id": "SWIFT_POTION"}
