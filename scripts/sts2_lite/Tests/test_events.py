"""Run events: the numbers of each modelled event, the pages, and that a visit never touches the original run."""
import random

import pytest

from sts2_lite.event import EVENTS, CardPicker, EventSession, RunSnapshot, available, card_entry
from sts2_lite.event.run import is_basic_defend, is_basic_strike


def starter(hp=70, max_hp=80, gold=200, extra=(), act=1, floor=8):
    deck = [card_entry("STRIKE_IRONCLAD") for _ in range(5)] + [card_entry("DEFEND_IRONCLAD") for _ in range(4)] + [card_entry("BASH")]
    deck += [card_entry(c) for c in extra]
    return RunSnapshot(hp=hp, max_hp=max_hp, gold=gold, deck=deck, act=act, floor=floor)


def visit(name, keys, run=None, seed=0, picker=None):
    run = run or starter()
    session = EventSession(EVENTS[name], run, random.Random(seed), picker)
    session.play(keys)
    return session, run


def ids(run):
    return sorted(c["id"] for c in run.deck)


def test_abyssal_baths_immerse_then_linger_damage_grows():
    s, run = visit("ABYSSAL_BATHS", ["immerse", "linger", "linger", "exit"])
    assert run.max_hp == 86 and run.hp == 70 + 6 - (3 + 4 + 5) and s.finished


def test_abyssal_baths_abstain_heals_ten():
    _, run = visit("ABYSSAL_BATHS", ["abstain"], starter(hp=60))
    assert run.hp == 70


def test_abyssal_baths_can_kill_and_ends_the_event():
    s, run = visit("ABYSSAL_BATHS", ["immerse", "linger", "linger"], starter(hp=6, max_hp=80))
    assert run.dead and s.finished


def test_amalgamator_needs_two_basic_strikes_and_defends():
    assert EVENTS["AMALGAMATOR"].allowed(starter())
    assert not EVENTS["AMALGAMATOR"].allowed(RunSnapshot(50, 80, 0, [card_entry("STRIKE_IRONCLAD")] * 3 + [card_entry("DEFEND_IRONCLAD")]))


def test_amalgamator_combines_strikes_into_ultimate_strike():
    _, run = visit("AMALGAMATOR", ["combine_strikes"])
    assert sum(map(is_basic_strike, run.deck)) == 3 and "ULTIMATE_STRIKE" in ids(run) and len(run.deck) == 9


def test_amalgamator_defends():
    _, run = visit("AMALGAMATOR", ["combine_defends"])
    assert sum(map(is_basic_defend, run.deck)) == 2 and "ULTIMATE_DEFEND" in ids(run)


def test_colossal_flower_extract_after_two_digs_pays_75_then_core_costs_seven():
    _, run = visit("COLOSSAL_FLOWER", ["reach_deeper", "extract"])
    assert run.gold == 200 + 75 and run.hp == 70 - 5
    _, run = visit("COLOSSAL_FLOWER", ["reach_deeper", "reach_deeper", "pollinous_core"])
    assert run.hp == 70 - 5 - 6 - 7 and run.has_relic("POLLINOUS_CORE")
    _, run = visit("COLOSSAL_FLOWER", ["reach_deeper", "reach_deeper", "extract_instead"])
    assert run.gold == 200 + 135


def test_colossal_flower_needs_19_hp():
    assert not EVENTS["COLOSSAL_FLOWER"].allowed(starter(hp=18))


def test_unrest_site_only_when_hurt_and_rest_heals_fully_for_a_curse():
    assert not EVENTS["UNREST_SITE"].allowed(starter(hp=70, max_hp=80))
    _, run = visit("UNREST_SITE", ["rest"], starter(hp=30))
    assert run.hp == 80 and "POOR_SLEEP" in ids(run)
    _, run = visit("UNREST_SITE", ["kill"], starter(hp=30))
    assert run.max_hp == 72 and run.pending_relics == 1


def test_spirit_grafter_options():
    _, run = visit("SPIRIT_GRAFTER", ["let_it_in"], starter(hp=40))
    assert run.hp == 65 and "METAMORPHOSIS" in ids(run)
    _, run = visit("SPIRIT_GRAFTER", ["reject"])
    assert run.hp == 60 and sum(c["is_upgraded"] for c in run.deck) == 1


def test_sunken_treasury_gold_ranges_and_curse():
    golds = {visit("SUNKEN_TREASURY", ["first_chest"], seed=s)[1].gold - 200 for s in range(60)}
    assert min(golds) >= 52 and max(golds) <= 67 and len(golds) > 5
    _, run = visit("SUNKEN_TREASURY", ["second_chest"])
    assert 303 <= run.gold - 200 <= 363 and "GREED" in ids(run)


def test_sunken_statue_dive_loses_seven_for_about_111_gold():
    _, run = visit("SUNKEN_STATUE", ["dive"])
    assert run.hp == 63 and 101 <= run.gold - 200 <= 121
    _, run = visit("SUNKEN_STATUE", ["grab_sword"])
    assert run.has_relic("SWORD_OF_STONE")


def test_whispering_hollow_pays_gold_for_two_potions_and_hug_transforms():
    _, run = visit("WHISPERING_HOLLOW", ["gold"], starter(gold=100))
    assert 100 - 44 <= run.gold <= 100 - 26 and len(run.potions) == 2
    before = ids(starter())
    _, run = visit("WHISPERING_HOLLOW", ["hug"])
    assert run.hp == 61 and len(run.deck) == 10 and ids(run) != before


def test_potions_stop_at_the_slot_count():
    run = starter(gold=100); run.potion_slots = 1
    _, run = visit("WHISPERING_HOLLOW", ["gold"], run)
    assert len(run.potions) == 1


def test_morphic_grove_group_takes_all_gold_and_transforms_two():
    _, run = visit("MORPHIC_GROVE", ["group"])
    assert run.gold == 0 and len(run.deck) == 10
    _, run = visit("MORPHIC_GROVE", ["loner"])
    assert run.max_hp == 85 and run.hp == 75


def test_luminous_choir_costs_between_100_and_149():
    assert not EVENTS["LUMINOUS_CHOIR"].allowed(starter(gold=148))
    for seed in range(20):
        _, run = visit("LUMINOUS_CHOIR", ["offer_tribute"], starter(gold=300), seed)
        assert 300 - 149 <= run.gold <= 300 - 100 and run.pending_relics == 1
    _, run = visit("LUMINOUS_CHOIR", ["reach_into_the_flesh"], starter(gold=300))
    assert len(run.deck) == 9 and "SPORE_MIND" in ids(run)


def test_locked_options_cannot_be_chosen():
    session = EventSession(EVENTS["ZEN_WEAVER"], starter(gold=130), random.Random(0))
    assert [o.key for o in session.available()] == ["breathing_techniques", "emotional_awareness"]
    with pytest.raises(ValueError):
        session.choose("arachnid_acupuncture")


def test_zen_weaver_prices():
    _, run = visit("ZEN_WEAVER", ["breathing_techniques"])
    assert run.gold == 150 and ids(run).count("ENLIGHTENMENT") == 2
    _, run = visit("ZEN_WEAVER", ["arachnid_acupuncture"], starter(gold=300))
    assert run.gold == 50 and len(run.deck) == 8


def test_doors_upgrade_two_or_remove_one():
    _, run = visit("DOORS_OF_LIGHT_AND_DARK", ["light"])
    assert sum(c["is_upgraded"] for c in run.deck) == 2
    _, run = visit("DOORS_OF_LIGHT_AND_DARK", ["dark"])
    assert len(run.deck) == 9


def test_room_full_of_cheese_gorge_takes_two_of_eight_and_search_costs_14():
    _, run = visit("ROOM_FULL_OF_CHEESE", ["gorge"])
    assert len(run.deck) == 12
    _, run = visit("ROOM_FULL_OF_CHEESE", ["search"])
    assert run.hp == 56 and run.has_relic("CHOSEN_CHEESE")


def test_brain_leech_rip_costs_five_and_offers_a_colorless_card():
    _, run = visit("BRAIN_LEECH", ["rip"])
    assert run.hp == 65 and len(run.deck) == 11
    _, run = visit("BRAIN_LEECH", ["share_knowledge"])
    assert len(run.deck) == 11


def test_slippery_bridge_hold_on_costs_more_each_time_and_overcome_loses_a_non_basic_card_first():
    run = starter(extra=("POMMEL_STRIKE",))
    s = EventSession(EVENTS["SLIPPERY_BRIDGE"], run, random.Random(0))
    lost = run.deck[s.ctx.vars["lose"]]["id"]
    assert lost in ("POMMEL_STRIKE", "BASH")            # not a Strike / Defend while other cards exist
    s.choose("hold_on"); s.choose("hold_on")
    assert run.hp == 70 - 3 - 4
    before = len(run.deck)
    s.choose("overcome")
    assert len(run.deck) == before - 1 and s.finished


def test_slippery_bridge_not_before_floor_seven():
    assert not EVENTS["SLIPPERY_BRIDGE"].allowed(starter(floor=6))


def test_reflections_touch_downgrades_two_and_upgrades_four_and_shatter_doubles_the_deck():
    run = starter(extra=("POMMEL_STRIKE", "SHRUG_IT_OFF", "ANGER"))
    for i in (0, 1, 10, 11):
        run.deck[i] = dict(run.deck[i], is_upgraded=True)
    _, after = visit("REFLECTIONS", ["touch_a_mirror"], run)
    assert sum(c["is_upgraded"] for c in after.deck) == 4 - 2 + 4          # two downgraded, then four different cards upgraded
    _, after = visit("REFLECTIONS", ["shatter"], starter())
    assert len(after.deck) == 21 and "BAD_LUCK" in ids(after)


def test_a_visit_does_not_change_the_original_run():
    original = starter()
    snapshot = original.copy()
    visit("AMALGAMATOR", ["combine_strikes"], original.copy())
    assert original.deck == snapshot.deck and original.hp == snapshot.hp


def test_every_event_can_be_played_to_the_end_by_random_choices():
    for name, event in EVENTS.items():
        for seed in range(15):
            run = starter(gold=400, extra=("POMMEL_STRIKE", "SHRUG_IT_OFF"))
            rng = random.Random(seed)
            session = EventSession(event, run, rng)
            steps = 0
            while not session.finished and steps < 30:
                session.choose(rng.choice(session.available()).key)
                steps += 1
            assert session.finished, name
            assert run.hp <= run.max_hp and run.gold >= 0 and all(c["id"] for c in run.deck), name


def test_available_follows_act_and_rules():
    names = {e.id for e in available(starter(act=1))}
    assert "ABYSSAL_BATHS" in names and "AMALGAMATOR" not in names and "THIS_OR_THAT" in names
    assert "BRAIN_LEECH" not in {e.id for e in available(starter(act=3))}


def test_transform_is_uniform_over_the_pool_not_by_rarity():
    from sts2_lite.event.run import CLASS_POOL
    rare = 0
    for seed in range(2000):
        run = starter(); run.deck = [card_entry("BASH")]
        _, run = visit("AROMA_OF_CHAOS", ["let_go"], run, seed)
        rare += run.deck[0]["rarity"] == "Rare"
    pool_share = len(CLASS_POOL["Rare"]) / sum(len(v) for v in CLASS_POOL.values())
    assert abs(rare / 2000 - pool_share) < 0.04 and abs(pool_share - 0.15) > 0.05      # follows the pool, not the 15% of a reward


def test_transform_never_returns_the_same_card():
    for seed in range(100):
        run = starter(); run.deck = [card_entry("BASH")]
        _, run = visit("AROMA_OF_CHAOS", ["let_go"], run, seed)
        assert run.deck[0]["id"] != "BASH"


def test_slippery_bridge_first_card_is_never_basic_but_later_ones_can_be():
    later_basic = False
    for seed in range(200):
        run = starter(extra=("POMMEL_STRIKE", "SHRUG_IT_OFF"))
        s = EventSession(EVENTS["SLIPPERY_BRIDGE"], run, random.Random(seed))
        assert run.deck[s.ctx.vars["lose"]]["rarity"] != "Basic"
        first = s.ctx.vars["lose"]
        s.choose("hold_on")
        second = s.ctx.vars["lose"]
        assert second != first and run.deck[second]["id"] != run.deck[first]["id"]
        later_basic |= run.deck[second]["rarity"] == "Basic"
    assert later_basic


# --- enchantments

def enchanted_cards(run):
    return [c for c in run.deck if c.get("enchantment")]


def test_enchant_rules_follow_the_game():
    from sts2_lite.event.run import can_enchant
    strike, defend, curse = card_entry("STRIKE_IRONCLAD"), card_entry("DEFEND_IRONCLAD"), card_entry("DECAY")
    assert can_enchant(strike, "SHARP") and not can_enchant(defend, "SHARP") and not can_enchant(curse, "PERFECT_FIT")
    assert can_enchant(strike, "CORRUPTED") and not can_enchant(defend, "CORRUPTED")
    assert not can_enchant(dict(strike, enchantment={"id": "SHARP", "amount": 2}), "SOWN")       # one enchantment per card
    assert can_enchant(card_entry("TREMBLE"), "SOULS_POWER") and not can_enchant(strike, "SOULS_POWER")       # needs a card with Exhaust of its own
    assert can_enchant(strike, "SLITHER") and not can_enchant(card_entry("WHIRLWIND"), "SLITHER")             # not X cost


def test_sapphire_seed_plant_enchants_one_card_with_sown_and_eat_heals_and_upgrades():
    _, run = visit("SAPPHIRE_SEED", ["plant"])
    assert [c["enchantment"] for c in enchanted_cards(run)] == [{"id": "SOWN", "amount": 1}]
    _, run = visit("SAPPHIRE_SEED", ["eat"], starter(hp=60))
    assert run.hp == 69 and sum(c["is_upgraded"] for c in run.deck) == 1


def test_field_of_man_sized_holes_resist_costs_two_cards_for_normality():
    _, run = visit("FIELD_OF_MAN_SIZED_HOLES", ["resist"])
    assert len(run.deck) == 9 and "NORMALITY" in ids(run)
    _, run = visit("FIELD_OF_MAN_SIZED_HOLES", ["enter_your_hole"])
    assert enchanted_cards(run)[0]["enchantment"]["id"] == "PERFECT_FIT"


def test_grave_of_the_forgotten_needs_an_exhaust_card():
    assert not EVENTS["GRAVE_OF_THE_FORGOTTEN"].allowed(starter())
    run = starter(extra=("TREMBLE",), act=3)
    assert EVENTS["GRAVE_OF_THE_FORGOTTEN"].allowed(run)
    _, run = visit("GRAVE_OF_THE_FORGOTTEN", ["confront"], run)
    assert "DECAY" in ids(run) and enchanted_cards(run)[0]["id"] == "TREMBLE"


def test_symbiote_corrupts_an_attack_or_transforms_one_card():
    _, run = visit("SYMBIOTE", ["approach"])
    assert enchanted_cards(run)[0]["type"] == "Attack" and enchanted_cards(run)[0]["enchantment"]["id"] == "CORRUPTED"
    _, run = visit("SYMBIOTE", ["kill_with_fire"])
    assert len(run.deck) == 10


def test_wood_carvings_turns_a_basic_card_into_peck_or_toric_toughness():
    _, run = visit("WOOD_CARVINGS", ["bird"])
    assert "PECK" in ids(run) and len(run.deck) == 10
    _, run = visit("WOOD_CARVINGS", ["torus"])
    assert "TORIC_TOUGHNESS" in ids(run)
    _, run = visit("WOOD_CARVINGS", ["snake"])
    assert enchanted_cards(run)[0]["enchantment"] == {"id": "SLITHER", "amount": 1}
    assert not EVENTS["WOOD_CARVINGS"].allowed(RunSnapshot(50, 80, 0, [card_entry("POMMEL_STRIKE")]))


def test_self_help_book_locks_a_book_without_a_matching_card():
    run = starter()
    session = EventSession(EVENTS["SELF_HELP_BOOK"], run, random.Random(0))
    locked = {o.key: o.locked for o in session.options}
    assert locked == {"read_the_back": False, "read_passage": False, "read_entire_book": True}      # no Power in the starter deck
    session.choose("read_the_back")
    assert enchanted_cards(run)[0]["enchantment"] == {"id": "SHARP", "amount": 2} and enchanted_cards(run)[0]["type"] == "Attack"
    only_curses = RunSnapshot(50, 80, 0, [card_entry("DECAY")])
    assert [o.key for o in EventSession(EVENTS["SELF_HELP_BOOK"], only_curses, random.Random(0)).options] == ["no_options"]




def test_spiraling_whirlpool_spiral_goes_on_a_basic_strike_or_defend_and_drink_heals_a_third():
    _, run = visit("SPIRALING_WHIRLPOOL", ["observe_the_spiral"])
    card = enchanted_cards(run)[0]
    assert card["enchantment"] == {"id": "SPIRAL", "amount": 1} and card["id"] in ("STRIKE_IRONCLAD", "DEFEND_IRONCLAD")
    _, run = visit("SPIRALING_WHIRLPOOL", ["drink"], starter(hp=30, max_hp=80))
    assert run.hp == 30 + 26
    assert not EVENTS["SPIRALING_WHIRLPOOL"].allowed(RunSnapshot(50, 80, 0, [card_entry("BASH"), card_entry("POMMEL_STRIKE")]))


def test_a_spiral_card_plays_twice_in_the_sim():
    from sts2_lite.card import Card
    from sts2_lite.event.run import enchanted
    entry = enchanted(card_entry("STRIKE_IRONCLAD"), "SPIRAL", 1)
    card = Card.from_dict(dict(entry, can_play=True, target_type="AnyEnemy", description="Deal 6 damage."))
    assert card.replay == 1
    assert Card.from_dict(dict(entry, can_play=True, target_type="AnyEnemy", description="Deal 6 damage. Replay 1.")).replay == 1     # not counted twice
