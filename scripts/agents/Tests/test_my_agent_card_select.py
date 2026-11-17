"""MyAgent's card screens: which cards a removal, an enchantment and an upgrade take."""
from agents.decision import Decision, Option
from agents.my_agent import MyAgent, enchant_score


def screen(prompt, screen_type, cards, can_confirm=True):
    options = [Option(c["name"], {"action": "select_card", "index": c["index"]}, c) for c in cards]
    if can_confirm:
        options.append(Option("confirm", {"action": "confirm_selection"}))
    return Decision("card_select", {"prompt": prompt, "screen_type": screen_type, "player": {}}, options)

def card(index, name, id, rarity="Common", cost="1", description="Deal 6 damage.", **rest):
    return {"index": index, "name": name, "id": id, "rarity": rarity, "cost": cost, "description": description, "type": "Attack", **rest}

def run(agent, prompt, screen_type, cards, times):
    out = []
    for _ in range(times):
        option = agent.get_decision(screen(prompt, screen_type, cards))
        out.append(option.action)
    return out

def test_a_five_card_removal_takes_curses_then_strikes_then_defends_then_the_rarest_last():
    cards = [card(0, "Omnislice", "OMNISLICE", "Uncommon"), card(1, "Strike", "STRIKE_IRONCLAD", "Basic"), card(2, "Defend", "DEFEND_IRONCLAD", "Basic"),
             card(3, "Strike", "STRIKE_IRONCLAD", "Basic"), card(4, "Rampage", "RAMPAGE", "Rare"), card(5, "Anger", "ANGER", "Common"), card(6, "Doubt", "DOUBT", "Curse", type="Curse")]
    actions = run(MyAgent(seed=1), "Choose 5 cards to Remove.", "select", cards, 6)
    assert [a["action"] for a in actions] == ["select_card"] * 5 + ["confirm_selection"]
    assert [a["index"] for a in actions[:5]] == [6, 1, 3, 2, 5]

def test_a_transform_takes_strikes_then_defends_then_the_lowest_rarity_and_curses_last():
    cards = [card(0, "Omnislice", "OMNISLICE", "Uncommon"), card(1, "Strike", "STRIKE_IRONCLAD", "Basic"), card(2, "Defend", "DEFEND_IRONCLAD", "Basic"),
             card(3, "Rampage", "RAMPAGE", "Rare"), card(4, "Anger", "ANGER", "Common"), card(5, "Doubt", "DOUBT", "Curse", type="Curse")]
    actions = run(MyAgent(seed=1), "Choose 5 cards to Transform.", "select", cards, 6)
    assert [a["index"] for a in actions[:5]] == [1, 2, 4, 0, 3]
    assert [a["index"] for a in run(MyAgent(seed=1), "Choose a card to Transform.", "select", [cards[5], cards[3]], 1)] == [3]

def test_an_enchantment_goes_to_three_different_good_cards():
    cards = [card(0, "Strike", "STRIKE_IRONCLAD", "Basic"), card(1, "Whirlwind", "WHIRLWIND", "Uncommon", cost="X"), card(2, "Rampage", "RAMPAGE", "Uncommon"),
             card(3, "Twin Strike", "TWIN_STRIKE", "Common", description="Deal 5 damage twice."), card(4, "Anger", "ANGER", "Common", cost="0", enchantment="SHARP")]
    actions = run(MyAgent(seed=1), "Choose 3 cards to Enchant.", "NDeckEnchantSelectScreen", cards, 4)
    picked = [a["index"] for a in actions[:3]]
    assert len(set(picked)) == 3 and 4 not in picked and actions[3]["action"] == "confirm_selection"

def test_enchant_score_prefers_multi_hits_cheap_cards_and_ignores_enchanted_ones():
    assert enchant_score(card(0, "Twin", "T", description="Deal 5 damage twice.")) > enchant_score(card(0, "S", "S", "Basic"))
    assert enchant_score(card(0, "A", "A", enchantment="SHARP")) < 0
