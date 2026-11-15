"""Run events: the numbers of each modelled event, the pages, and that a visit never touches the original run."""
import random

import pytest

from sts2_lite.event import EVENTS, CardPicker, EventSession, RunSnapshot, available, card_entry
from sts2_lite.event.core import Ctx
from sts2_lite.event.events import TRASH_HEAP_CARDS
from sts2_lite.event.run import is_basic_defend, is_basic_strike, placeholder_entry


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


# ---------------------------------------------------------------- the second batch
def test_jungle_maze_solo_costs_18_and_pays_about_150_join_pays_about_50():
    _, run = visit("JUNGLE_MAZE_ADVENTURE", ["solo_quest"])
    assert run.hp == 70 - 18 and 200 + 135 <= run.gold <= 200 + 165
    _, run = visit("JUNGLE_MAZE_ADVENTURE", ["join_forces"])
    assert run.hp == 70 and 200 + 35 <= run.gold <= 200 + 65


def test_tablet_of_truth_smash_heals_20():
    _, run = visit("TABLET_OF_TRUTH", ["smash"], starter(hp=50))
    assert run.hp == 70


def test_tablet_of_truth_decipher_costs_3_6_12_24_then_all_but_one_and_the_last_upgrades_everything():
    s, run = visit("TABLET_OF_TRUTH", ["decipher", "give_up"], starter(max_hp=80))
    assert run.max_hp == 77 and sum(c["is_upgraded"] for c in run.deck) == 1 and s.finished
    s, run = visit("TABLET_OF_TRUTH", ["decipher"] * 5, starter(hp=80, max_hp=80))
    assert run.max_hp == 1 and s.finished and not run.dead
    assert all(c["is_upgraded"] for c in run.deck)
    assert 80 - 3 - 6 - 12 - 24 - 34 == 1


def test_tablet_of_truth_can_kill_when_the_cost_is_the_max_hp():
    s, run = visit("TABLET_OF_TRUTH", ["decipher"], starter(hp=3, max_hp=3))
    assert run.dead and s.finished


def test_trash_heap_dive_takes_8_hp_for_one_of_five_relics_grab_gives_100_gold_and_a_playable_event_card():
    _, run = visit("TRASH_HEAP", ["dive_in"])
    assert run.hp == 62 and run.relics[0]["id"] in ("DARKSTONE_PERIAPT", "DREAM_CATCHER", "HAND_DRILL", "MAW_BANK", "THE_BOOT")
    _, run = visit("TRASH_HEAP", ["grab"])
    assert run.gold == 300 and len(run.deck) == 11 and run.deck[-1]["id"] in TRASH_HEAP_CARDS and run.deck[-1].get("modelled") is not False and run.deck[-1]["rarity"] == "Event"
    assert not EVENTS["TRASH_HEAP"].allowed(starter(hp=5))


def test_waterlogged_scriptorium_steady_enchants_one_or_two_cards():
    assert not EVENTS["WATERLOGGED_SCRIPTORIUM"].allowed(starter(gold=54))
    _, run = visit("WATERLOGGED_SCRIPTORIUM", ["bloody_ink"])
    assert run.max_hp == 86
    _, run = visit("WATERLOGGED_SCRIPTORIUM", ["tentacle_quill"])
    assert run.gold == 145 and sum(bool(c.get("enchantment")) for c in run.deck) == 1
    _, run = visit("WATERLOGGED_SCRIPTORIUM", ["prickly_sponge"])
    assert run.gold == 101 and sum(bool(c.get("enchantment")) and c["enchantment"]["id"] == "STEADY" for c in run.deck) == 2
    assert EventSession(EVENTS["WATERLOGGED_SCRIPTORIUM"], starter(gold=60), random.Random(0)).options[2].locked


def test_infested_automaton_adds_a_power_or_a_free_card():
    _, run = visit("INFESTED_AUTOMATON", ["study"], starter(act=2))
    assert run.deck[-1]["type"] == "Power"
    _, run = visit("INFESTED_AUTOMATON", ["touch_core"], starter(act=2))
    assert run.deck[-1]["cost"] == 0


def test_potion_courier_gives_three_foul_potions_or_one_uncommon_potion_and_not_in_act_one():
    _, run = visit("POTION_COURIER", ["grab_potions"], starter(act=2))
    assert [p["id"] for p in run.potions] == ["FOUL_POTION"] * 3
    _, run = visit("POTION_COURIER", ["ransack"], starter(act=2))
    assert len(run.potions) == 1
    assert not EVENTS["POTION_COURIER"].allowed(starter(act=1))


def test_tea_master_sells_teas_and_needs_150_gold_before_act_three():
    assert not EVENTS["TEA_MASTER"].allowed(starter(gold=149)) and not EVENTS["TEA_MASTER"].allowed(starter(act=3))
    _, run = visit("TEA_MASTER", ["bone_tea"])
    assert run.gold == 150 and [r["id"] for r in run.relics] == ["BONE_TEA"]
    _, run = visit("TEA_MASTER", ["tea_of_discourtesy"])
    assert run.gold == 200 and [r["id"] for r in run.relics] == ["TEA_OF_DISCOURTESY"]


def test_the_legends_were_true_map_or_eight_hp_for_a_potion():
    _, run = visit("THE_LEGENDS_WERE_TRUE", ["nab_the_map"])
    assert run.deck[-1]["id"] == "SPOILS_MAP"
    _, run = visit("THE_LEGENDS_WERE_TRUE", ["slowly_find_an_exit"])
    assert run.hp == 62 and len(run.potions) == 1
    assert not EVENTS["THE_LEGENDS_WERE_TRUE"].allowed(starter(hp=9)) and not EVENTS["THE_LEGENDS_WERE_TRUE"].allowed(starter(act=2))


def test_doll_room_random_free_or_paid_choice_and_act_two_only():
    assert EVENTS["DOLL_ROOM"].allowed(starter(act=2)) and not EVENTS["DOLL_ROOM"].allowed(starter(act=1))
    _, run = visit("DOLL_ROOM", ["random"], starter(act=2))
    assert len(run.relics) == 1 and run.hp == 70
    s = EventSession(EVENTS["DOLL_ROOM"], starter(act=2), random.Random(0))
    s.choose("examine")
    assert len(s.available()) == 3 and s.run.hp == 55
    s2 = EventSession(EVENTS["DOLL_ROOM"], starter(act=2), random.Random(0))
    s2.choose("take_some_time")
    assert len(s2.available()) == 2 and s2.run.hp == 65
    s2.choose(s2.available()[0].key)
    assert s2.finished and len(s2.run.relics) == 1


def test_wongos_buys_relics_and_leaving_downgrades_an_upgraded_card():
    assert not EVENTS["WELCOME_TO_WONGOS"].allowed(starter(gold=99, act=2)) and not EVENTS["WELCOME_TO_WONGOS"].allowed(starter(act=1))
    _, run = visit("WELCOME_TO_WONGOS", ["mystery_box"], starter(gold=350, act=2))
    assert run.gold == 50 and [r["id"] for r in run.relics] == ["WONGOS_MYSTERY_TICKET"]
    _, run = visit("WELCOME_TO_WONGOS", ["bargain_bin"], starter(gold=150, act=2))
    assert run.gold == 50 and run.pending_relics + len(run.relics) == 1
    run = starter(gold=150, act=2)
    run.deck[0] = dict(run.deck[0], is_upgraded=True)
    _, run = visit("WELCOME_TO_WONGOS", ["leave"], run)
    assert not any(c.get("is_upgraded") for c in run.deck)


def test_endless_conveyor_costs_forty_per_dish_and_leaving_is_offered_after_a_grab():
    assert not EVENTS["ENDLESS_CONVEYOR"].allowed(starter(gold=119))
    s = EventSession(EVENTS["ENDLESS_CONVEYOR"], starter(gold=200), random.Random(3))
    first = s.available()[0].key
    assert first != "golden_fysh" and s.available()[1].key == "observe_chef"
    s.choose(first)
    keys = [o.key for o in s.available()]
    assert keys[-1] == "leave" and keys[0] != first and not s.finished
    assert s.run.gold >= 200 - 40
    s.choose("leave")
    assert s.finished


def test_endless_conveyor_fifth_dish_is_seapunk_salad():
    s = EventSession(EVENTS["ENDLESS_CONVEYOR"], starter(gold=900), random.Random(1))
    seen = [s.available()[0].key]
    for _ in range(4):
        s.choose(s.available()[0].key)
        seen.append(s.available()[0].key)
    assert seen[4] == "seapunk_salad"


def test_crystal_sphere_costs_and_a_random_outcome():
    assert not EVENTS["CRYSTAL_SPHERE"].allowed(starter(gold=99, act=2)) and not EVENTS["CRYSTAL_SPHERE"].allowed(starter(gold=200, act=1))
    _, run = visit("CRYSTAL_SPHERE", ["payment_plan"], starter(act=2))
    assert "DEBT" in ids(run)
    _, run = visit("CRYSTAL_SPHERE", ["uncover_future"], starter(gold=300, act=2))
    assert run.gold != 300


def with_relics(run, *ids):
    run.relics = [{"id": i, "name": i} for i in ids]
    return run


def test_relic_trader_needs_five_tradable_relics_and_swaps_one():
    tradables = ("ANCHOR", "BLOOD_VIAL", "BRONZE_SCALES", "BAG_OF_MARBLES", "CENTENNIAL_PUZZLE")
    assert not EVENTS["RELIC_TRADER"].allowed(with_relics(starter(act=2), *tradables[:4], "STRAWBERRY", "BURNING_BLOOD"))
    assert not EVENTS["RELIC_TRADER"].allowed(with_relics(starter(act=1), *tradables))
    run = with_relics(starter(act=2), *tradables)
    s, run = visit("RELIC_TRADER", ["trade_top"], run)
    assert s.finished and len(run.relics) + run.pending_relics == 5


def test_ranwid_costs_a_potion_gold_or_a_relic():
    run = with_relics(starter(act=2), "ANCHOR")
    run.potions = [{"id": "FIRE_POTION", "name": "Fire Potion"}]
    _, r = visit("RANWID_THE_ELDER", ["gold"], run)
    assert r.gold == 100 and len(r.relics) + r.pending_relics == 2
    run = with_relics(starter(act=2), "ANCHOR")
    run.potions = [{"id": "FIRE_POTION", "name": "Fire Potion"}]
    _, r = visit("RANWID_THE_ELDER", ["relic"], run)
    assert "ANCHOR" not in [x["id"] for x in r.relics] and len(r.relics) + r.pending_relics == 2
    run = with_relics(starter(act=2), "ANCHOR")
    run.potions = [{"id": "FIRE_POTION", "name": "Fire Potion"}]
    _, r = visit("RANWID_THE_ELDER", ["potion"], run)
    assert r.potions == []
    assert not EVENTS["RANWID_THE_ELDER"].allowed(with_relics(starter(act=2), "ANCHOR"))


def test_stone_of_all_time_lift_or_push():
    run = starter(act=2)
    run.potions = [{"id": "FIRE_POTION", "name": "Fire Potion"}]
    _, r = visit("STONE_OF_ALL_TIME", ["lift"], run)
    assert r.max_hp == 90 and r.potions == []
    run = starter(act=2)
    run.potions = [{"id": "FIRE_POTION", "name": "Fire Potion"}]
    _, r = visit("STONE_OF_ALL_TIME", ["push"], run)
    assert r.hp == 64 and any((c.get("enchantment") or {}).get("id") == "VIGOROUS" and c["type"] == "Attack" for c in r.deck)


def test_future_of_potions_pays_three_upgraded_cards_of_the_potions_rarity():
    run = starter()
    run.potions = [{"id": "FIRE_POTION", "name": "Fire Potion"}, {"id": "DUPLICATOR", "name": "Duplicator"}]
    assert not EVENTS["THE_FUTURE_OF_POTIONS"].allowed(starter())
    s = EventSession(EVENTS["THE_FUTURE_OF_POTIONS"], run, random.Random(2))
    assert [o.key for o in s.available()] == ["potion_0", "potion_1"]
    s.choose("potion_1")
    new = s.run.deck[-1]
    assert s.finished and len(s.run.potions) == 1 and new["rarity"] == "Uncommon" and new["is_upgraded"]


def test_round_tea_party_tea_or_a_fight_for_a_relic():
    assert not EVENTS["ROUND_TEA_PARTY"].allowed(starter(hp=11, act=3))
    _, run = visit("ROUND_TEA_PARTY", ["enjoy_tea"], starter(hp=30, act=3))
    assert run.hp == 80 and [r["id"] for r in run.relics] == ["ROYAL_POISON"]
    _, run = visit("ROUND_TEA_PARTY", ["pick_fight", "continue_fight"], starter(hp=30, act=3))
    assert run.hp == 19 and len(run.relics) + run.pending_relics == 1


def test_trial_outcomes_by_defendant():
    seen = set()
    for seed in range(12):
        s = EventSession(EVENTS["TRIAL"], starter(act=3), random.Random(seed))
        s.choose("accept")
        keys = [o.key for o in s.available()]
        seen.add(keys[0].split("_")[0])
        s.choose(keys[0])
        assert s.finished
    assert seen == {"merchant", "noble", "nondescript"}
    s = EventSession(EVENTS["TRIAL"], starter(act=3), random.Random(0))
    s.choose("reject")
    assert [o.key for o in s.available()] == ["accept", "double_down"]
    s.choose("double_down")
    assert s.run.dead


def test_trial_merchant_and_noble_numbers():
    for seed in range(40):
        s = EventSession(EVENTS["TRIAL"], starter(hp=50, act=3), random.Random(seed))
        s.choose("accept")
        keys = [o.key for o in s.available()]
        if keys[0] == "noble_guilty":
            s.choose("noble_innocent")
            assert s.run.gold == 500 and "REGRET" in ids(s.run)
            break
    else:
        pytest.fail("no noble in 40 seeds")


def test_tinker_time_builds_a_mad_science_card_from_a_type_and_a_rider():
    s = EventSession(EVENTS["TINKER_TIME"], starter(act=3), random.Random(1))
    s.choose("choose_card_type")
    types = [o.key for o in s.available()]
    assert len(types) == 2 and set(types) <= {"attack", "skill", "power"}
    s.choose(types[0])
    riders = [o.key.upper() for o in s.available()]
    assert len(riders) == 2
    s.choose(riders[1].lower())
    card = s.run.deck[-1]
    assert s.finished and card["id"] == "MAD_SCIENCE" and card["type"] == types[0].title() and card["rider"] == riders[1] and card["cost"] == 1


# --- quest cards ---------------------------------------------------------------------------------------------------------------------------------------
def with_keys(n, **kw):
    run = starter(**kw)
    run.deck += [placeholder_entry("LANTERN_KEY", "Lantern Key", "Quest") for _ in range(n)]
    return run


def test_the_lantern_key_returned_pays_100_gold_and_kept_leads_to_the_knight():
    _, run = visit("THE_LANTERN_KEY", ["return_the_key"])
    assert run.gold == starter().gold + 100 and run.pending_fight is None
    _, run = visit("THE_LANTERN_KEY", ["keep_the_key", "fight"])
    assert run.pending_fight == "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER" and run.pending_fight_args == {"on_win": "lantern_key"}


def test_war_historian_repy_is_never_drawn_and_one_key_buys_one_choice():
    assert not EVENTS["WAR_HISTORIAN_REPY"].allowed(starter(act=3))
    s, run = visit("WAR_HISTORIAN_REPY", ["unlock_cage"], run=with_keys(1, act=3))
    assert run.has_relic("HISTORY_COURSE") and s.finished and not any(c["id"] == "LANTERN_KEY" for c in run.deck)
    s, run = visit("WAR_HISTORIAN_REPY", ["unlock_chest"], run=with_keys(1, act=3))
    assert run.pending_relics == 2 and len(run.potions) == 2 and s.finished and not run.has_relic("HISTORY_COURSE")


def test_war_historian_repy_with_a_second_key_gives_the_other_reward_too():
    s, run = visit("WAR_HISTORIAN_REPY", ["unlock_chest", "unlock_cage"], run=with_keys(2, act=3))
    assert run.has_relic("HISTORY_COURSE") and run.pending_relics == 2 and s.finished and not any(c["id"] == "LANTERN_KEY" for c in run.deck)


def test_byrdonis_nest_eat_gives_7_max_hp_and_take_the_egg_card():
    _, run = visit("BYRDONIS_NEST", ["eat"])
    assert run.max_hp == starter().max_hp + 7
    _, run = visit("BYRDONIS_NEST", ["take"])
    assert run.deck[-1]["id"] == "BYRDONIS_EGG" and run.deck[-1]["type"] == "Quest"
    pet = starter()
    pet.relics.append({"id": "BYRDPIP", "name": "Byrdpip"})
    assert not EVENTS["BYRDONIS_NEST"].allowed(pet) and EVENTS["BYRDONIS_NEST"].allowed(starter(act=1))


def test_byrdpip_turns_every_egg_into_a_byrd_swoop_and_hatch_is_a_rest_option_only_with_an_egg():
    from sts2_lite.relic import run_hooks
    from sts2_lite.relic.pickup import obtain_relic
    run = starter()
    assert "HATCH" not in run_hooks.rest_extra_options(run)
    run.deck += [placeholder_entry("BYRDONIS_EGG", "Byrdonis Egg", "Quest")]
    assert "HATCH" in run_hooks.rest_extra_options(run)
    obtain_relic(Ctx(run, random.Random(0), None), "BYRDPIP")
    assert run.has_relic("BYRDPIP") and run.deck[-1]["id"] == "BYRD_SWOOP" and not any(c["id"] == "BYRDONIS_EGG" for c in run.deck)
    assert "HATCH" not in run_hooks.rest_extra_options(run)


def test_dollys_mirror_can_copy_a_quest_card_and_the_thieving_hopper_cannot_take_one():
    from sts2_lite.card.card import Card
    from sts2_lite.card.ids import CardType
    from sts2_lite.card.tables import CARD_RARITY
    from sts2_lite.relic.pickup import obtain_relic

    class Pick:
        def take(self, cards, n):
            return [next(i for i, c in enumerate(cards) if c["id"] == "SPOILS_MAP")]
    run = starter()
    run.deck.append(placeholder_entry("SPOILS_MAP", "Spoils Map", "Quest"))
    obtain_relic(Ctx(run, random.Random(0), Pick()), "DOLLYS_MIRROR")
    assert sum(c["id"] == "SPOILS_MAP" for c in run.deck) == 2
    quest = Card.from_dict(run.deck[-1])          # in a fight it is a Wound-like Status card, which the hopper's steal skips
    assert quest.type == CardType.Status and CARD_RARITY[quest.card_id].name == "Status"
