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


def test_a_two_card_removal_confirms_after_two_picks_even_when_the_runner_hid_a_card_the_game_seemed_not_to_react_to():
    """Run silent-a0-1, floor 20 (Arachnid Acupuncture): the first pick changes nothing on the game's screen, so the runner drops it from the options;
    the count of picks restarted when the preview came up, and the agent kept picking until the game had removed six cards."""
    cards = [card(i, "Strike", "STRIKE_SILENT", "Basic") for i in range(5)] + [card(i, "Defend", "DEFEND_SILENT", "Basic") for i in range(5, 8)]
    agent = MyAgent(seed=1)
    def screen_for(options, preview):
        d = screen("Choose 2 cards to Remove.", "select", [c for c in cards if c["index"] in options], can_confirm=preview)
        d.state["cards"] = cards
        return d
    first = agent.get_decision(screen_for(range(8), False)).action
    second = agent.get_decision(screen_for([i for i in range(8) if i != first["index"]], False)).action     # the first pick was hidden
    third = agent.get_decision(screen_for(range(8), True)).action                                           # the preview is up: every card is on offer again
    assert [first["action"], second["action"], third["action"]] == ["select_card", "select_card", "confirm_selection"]


def test_a_card_pack_screen_opens_one_pack_then_takes_it():
    """Scroll Boxes: the bridge lists each pack as an entry of a card screen; opening one shows the preview with Confirm."""
    packs = [card(i, "A + B + C", "CARD_PACK", "Pack", type="Pack") for i in range(2)]
    agent = MyAgent(seed=1)
    def screen_for(preview):
        d = screen("Choose a card pack.", "bundle", packs, can_confirm=preview)
        d.state["cards"] = packs
        return d
    assert agent.get_decision(screen_for(False)).action["action"] == "select_card"
    assert agent.get_decision(screen_for(True)).action["action"] == "confirm_selection"
