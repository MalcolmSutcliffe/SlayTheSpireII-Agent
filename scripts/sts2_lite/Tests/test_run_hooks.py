"""What relics do around the fights: gold, reward extras, card offers, rest sites, "?" rooms, room entry, prices."""
import random

from sts2_lite.event import card_entry
from sts2_lite.map.odds import UnknownRoomOdds
from sts2_lite.relic import run_hooks as H
from sts2_lite.run import new_run


def run_with(*relics, act=1):
    run = new_run(0)
    run.act = act
    for r in relics:
        run.relics.append({"id": r, "name": r})
    return run


def test_bowler_hat_and_dragon_fruit():
    run = run_with("BOWLER_HAT", "DRAGON_FRUIT")
    g, m = run.gold, run.max_hp
    assert H.gain_gold(run, 20) == 25 and run.gold == g + 25 and run.max_hp == m + 1


def test_reward_extras():
    run = run_with("AMETHYST_AUBERGINE", "BLACK_STAR", "PRAYER_WHEEL", "WHITE_STAR")
    assert H.reward_extras(run, "Monster") == [("gold", 15), ("cards", "Monster")]
    assert H.reward_extras(run, "Elite") == [("gold", 15), ("relic",), ("cards", "Boss")]
    assert H.reward_extras(run, "Boss", last_act_boss=True) == []
    assert H.reward_extras(run, "Shop") == []


def test_lava_rock_pays_two_relics_once_on_the_first_boss_only():
    run = run_with("LAVA_ROCK")
    assert H.reward_extras(run, "Boss") == [("relic",)] * 2
    assert H.reward_extras(run, "Boss") == []
    assert H.reward_extras(run_with("LAVA_ROCK", act=2), "Boss") == []


def test_wongos_ticket_pays_three_relics_after_the_fifth_combat():
    run = run_with("WONGOS_MYSTERY_TICKET")
    got = [H.reward_extras(run, "Monster") for _ in range(7)]
    assert got[:4] == [[]] * 4 and got[4] == [("relic",)] * 3 and got[5:] == [[], []]


def test_lasting_candy_every_second_combat():
    run = run_with("LASTING_CANDY")
    seen = []
    for _ in range(4):
        H.combat_finished(run)
        seen.append(H.candy_adds_power(run))
    assert seen == [False, True, False, True]


def test_eggs_and_lava_lamp_upgrade_offers():
    run = run_with("MOLTEN_EGG", "TOXIC_EGG")
    cards = [card_entry("STRIKE_IRONCLAD"), card_entry("DEFEND_IRONCLAD"), card_entry("BASH")]
    out = H.modify_card_offers(run, cards, random.Random(0), True)
    assert [c["is_upgraded"] for c in out] == [True, True, True]
    run = run_with("LAVA_LAMP")
    assert not any(c["is_upgraded"] for c in H.modify_card_offers(run, cards, random.Random(0), True, took_damage=True))
    assert all(c["is_upgraded"] for c in H.modify_card_offers(run, cards, random.Random(0), True, took_damage=False))
    assert not any(c["is_upgraded"] for c in H.modify_card_offers(run, cards, random.Random(0), False, took_damage=False))


def test_wing_charm_enchants_exactly_one_card():
    run = run_with("WING_CHARM")
    out = H.modify_card_offers(run, [card_entry("BASH"), card_entry("ARMAMENTS"), card_entry("ANGER")], random.Random(1), True)
    assert sum(1 for c in out if c.get("enchantment")) == 1


def test_a_card_joining_the_deck_is_upgraded_by_its_egg():
    run = run_with("MOLTEN_EGG")
    H.add_to_deck(run, card_entry("BASH"))
    H.add_to_deck(run, card_entry("ARMAMENTS"))
    assert run.deck[-2]["is_upgraded"] and not run.deck[-1]["is_upgraded"]


def test_juzu_bracelet_never_rolls_a_fight_from_a_question_mark():
    run = run_with("JUZU_BRACELET")
    odds, rng = UnknownRoomOdds(), random.Random(0)
    assert all(odds.roll(rng, H.unknown_room_blacklist(run)) != "Monster" for _ in range(300))


def test_room_entry_heals_and_gold():
    run = run_with("EternalFeather".upper().replace("ETERNALFEATHER", "ETERNAL_FEATHER"), "MEAL_TICKET", "PLANISPHERE", "MAW_BANK")
    run.hp = 10
    g = run.gold
    H.room_entered(run, "RestSite")                     # 10 cards: 3 * 2
    assert run.hp == 16 and run.gold == g + 12
    H.room_entered(run, "Shop")
    assert run.hp == 31
    H.room_entered(run, "Event", from_unknown=True)
    assert run.hp == 36
    H.state(run, "MAW_BANK")["bought"] = True
    g = run.gold
    H.room_entered(run, "Monster")
    assert run.gold == g


def test_rest_site_options_and_prices():
    run = run_with("REGAL_PILLOW", "SHOVEL", "DREAM_CATCHER", "TINY_MAILBOX")
    assert H.rest_heal(run) == 24 + 15 and H.rest_extra_options(run) == ["DIG"]
    assert [o["kind"] for o in H.rest_heal_offers(run)] == ["cards", "potion", "potion"]
    assert H.merchant_price(run_with("MEMBERSHIP_CARD", "THE_COURIER"), 100) == 40


def test_fresnel_lens_makes_every_valid_offer_nimble():
    run = run_with("FRESNEL_LENS")
    out = H.modify_card_offers(run, [card_entry("DEFEND_IRONCLAD"), card_entry("ARMAMENTS")], random.Random(0), True)
    assert all(c.get("enchantment", {}).get("id") == "NIMBLE" for c in out)


def test_deck_gain_relics():
    run = run_with("LUCKY_FYSH", "BOOK_OF_FIVE_RINGS", "DARKSTONE_PERIAPT")
    run.hp = 40
    g, m = run.gold, run.max_hp
    for _ in range(4):
        H.add_to_deck(run, card_entry("BASH"))
    assert run.gold == g + 60 and run.hp == 40
    H.add_to_deck(run, card_entry("INJURY"))
    assert run.hp == 40 + 20 + 6 and run.max_hp == m + 6          # the fifth card heals 20, the curse gives 6 max HP


def test_bing_bong_copies_each_new_card_once():
    run = run_with("BING_BONG", "LUCKY_FYSH")
    n, g = len(run.deck), run.gold
    H.add_to_deck(run, card_entry("BASH"))
    assert len(run.deck) == n + 2 and run.gold == g + 30          # the copy is a card change too, but not copied again


def test_chosen_cheese_fishing_rod_and_sword_of_stone():
    run = run_with("CHOSEN_CHEESE", "FISHING_ROD", "SWORD_OF_STONE")
    m = run.max_hp
    for _ in range(3):
        H.combat_finished(run, "Monster", random.Random(0))
    assert run.max_hp == m + 3 and sum(1 for c in run.deck if c.get("is_upgraded")) == 1
    for _ in range(5):
        H.combat_finished(run, "Elite", random.Random(0))
    assert run.has_relic("SWORD_OF_JADE") and not run.has_relic("SWORD_OF_STONE")


def test_paels_tooth_takes_five_cards_and_gives_one_back_after_each_combat():
    from sts2_lite.event import CardPicker
    from sts2_lite.event.core import Ctx
    from sts2_lite.relic.pickup import obtain_relic
    run = run_with()
    c = Ctx(run, random.Random(0), CardPicker(random.Random(0)))
    n = len(run.deck)
    obtain_relic(c, "PAELS_TOOTH")
    assert len(run.deck) == n - 5 and len(H.state(run, "PAELS_TOOTH")["cards"]) == 5
    H.combat_finished(run, "Monster", random.Random(1))
    assert len(run.deck) == n - 4 and len(H.state(run, "PAELS_TOOTH")["cards"]) == 4 and run.deck[-1]["is_upgraded"]


def test_stone_humidifier_after_resting():
    run = run_with("STONE_HUMIDIFIER")
    m = run.max_hp
    H.rest_healed(run)
    assert run.max_hp == m + 5
