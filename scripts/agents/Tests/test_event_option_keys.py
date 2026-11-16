"""An event option of the game is told from the engine's by its text key (THIS_OR_THAT.pages.INITIAL.options.PLAIN -> plain), not by its title ("This").
Run from scripts/."""
from agents.decision import Option as GameOption
from agents.deck_eval.route_sim import event_option_key, find_event_option
from sts2_lite.event.core import Option


def game(title, text_key=None, index=0, page_size=2):
    data = {"index": index, "page_size": page_size, "title": title}
    if text_key:
        data["text_key"] = text_key
    return GameOption(title, {"action": "choose_event_option", "index": index}, data)

def page(*keys, locked=()):
    return [Option(k, lambda c: None, locked=k in locked) for k in keys]


def test_the_text_key_names_the_option_not_its_title():
    plain = game("This", "THIS_OR_THAT.pages.INITIAL.options.PLAIN")
    assert event_option_key(plain) == "PLAIN"
    options = page("plain", "ornate")
    assert find_event_option(options, event_option_key(plain)) is options[0]

def test_names_match_without_case_or_underscores():
    options = page("dragon_bones", "ornate")
    assert find_event_option(options, "DRAGON_BONES") is options[0] and find_event_option(options, "Ornate") is options[1]

def test_a_numbered_option_is_the_option_without_the_number():
    option = game("Hold on", "SLIPPERY_BRIDGE.pages.INITIAL.options.HOLD_ON_0")
    assert event_option_key(option) == "HOLD_ON"
    assert find_event_option(page("hold_on", "overcome"), event_option_key(option)).key == "hold_on"

def test_the_game_names_the_engine_spells_differently_are_aliased():
    assert find_event_option(page("exit", "linger"), event_option_key(game("Leave", "ABYSSAL_BATHS.pages.INITIAL.options.EXIT_BATHS"))).key == "exit"
    assert find_event_option(page("let_it_in", "reject"), event_option_key(game("No", "SPIRIT_GRAFTER.pages.INITIAL.options.REJECTION"))).key == "reject"

def test_an_option_the_engine_does_not_have_is_not_found():
    assert find_event_option(page("plain", "ornate"), "SHATTER") is None

def test_a_locked_option_is_not_found():
    assert find_event_option(page("bone_tea", "ember_tea", locked=("bone_tea",)), "BONE_TEA") is None

def test_without_the_text_key_an_option_is_told_by_its_position_on_a_page_of_the_same_size():
    second = game("That", index=1, page_size=2)
    key = event_option_key(second)
    assert key == "#1/2:That"
    options = page("plain", "ornate")
    assert find_event_option(options, key) is options[1]
    assert find_event_option(page("plain", "ornate", "third"), key) is None         # a page of another size: no guess
    assert find_event_option(page("plain", "ornate", locked=("ornate",)), key) is None

def test_a_title_that_is_the_engines_key_still_matches_without_the_text_key():
    options = page("immerse", "abstain")
    assert find_event_option(options, event_option_key(game("abstain", index=1, page_size=0))) is options[1]
