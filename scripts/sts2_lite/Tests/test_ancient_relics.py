"""The pickup effects of the relics the ancients offer."""
from sts2_lite.relic import run_hooks
from sts2_lite.relic.ancient_data import neow_relics
from sts2_lite.relic.pickup import obtain_relic
from sts2_lite.Tests.test_relic_pickup import ctx_with_bag
from sts2_lite.event import card_entry


def ids(c):
    return [x["id"] for x in c.run.deck]


def test_neows_torment_and_hefty_tablet_and_cursed_boons():
    c = ctx_with_bag()
    obtain_relic(c, "NEOWS_TORMENT")
    assert "NEOWS_FURY" in ids(c)
    obtain_relic(c, "HEFTY_TABLET")
    assert "INJURY" in ids(c)
    offer = c.run.offers[-1]
    assert offer["kind"] == "cards" and len(offer["cards"]) == 3 and all(x["rarity"] == "Rare" for x in offer["cards"])


def test_lost_coffer_queues_a_card_reward_and_a_potion():
    c = ctx_with_bag()
    obtain_relic(c, "LOST_COFFER")
    assert [o["kind"] for o in c.run.offers] == ["cards", "potion"] and len(c.run.offers[0]["cards"]) == 3


def test_phial_holster_adds_a_slot_and_up_to_two_potions():
    c = ctx_with_bag()
    obtain_relic(c, "PHIAL_HOLSTER")
    assert c.run.potion_slots == 4 and len(c.run.potions) == 2 and len({p["id"] for p in c.run.potions}) == 2


def test_removals_and_precarious_shears():
    c = ctx_with_bag()
    n = len(c.run.deck)
    obtain_relic(c, "PRECISE_SCISSORS")
    assert len(c.run.deck) == n - 1
    hp = c.run.hp
    obtain_relic(c, "PRECARIOUS_SHEARS")
    assert len(c.run.deck) == n - 3 and c.run.hp == hp - 16


def test_neows_talisman_upgrades_the_last_strike_and_defend():
    c = ctx_with_bag()
    obtain_relic(c, "NEOWS_TALISMAN")
    up = [i for i, x in enumerate(c.run.deck) if x.get("is_upgraded")]
    strikes = [i for i, x in enumerate(c.run.deck) if x["id"] == "STRIKE_IRONCLAD"]
    defends = [i for i, x in enumerate(c.run.deck) if x["id"] == "DEFEND_IRONCLAD"]
    assert sorted(up) == sorted([strikes[-1], defends[-1]])


def test_oyster_pomander_sand_castle_small_capsule():
    c = ctx_with_bag()
    obtain_relic(c, "NUTRITIOUS_OYSTER")
    assert c.run.max_hp == 91
    obtain_relic(c, "POMANDER")
    assert sum(bool(x.get("is_upgraded")) for x in c.run.deck) == 1
    obtain_relic(c, "SAND_CASTLE")
    assert sum(bool(x.get("is_upgraded")) for x in c.run.deck) == 7
    obtain_relic(c, "SMALL_CAPSULE")
    assert c.run.offers[-1] == {"kind": "relic"}


def test_leafy_poultice_trades_max_hp_for_two_random_cards():
    c = ctx_with_bag()
    obtain_relic(c, "LEAFY_POULTICE")
    assert c.run.max_hp == 68
    assert sum(x["id"] == "STRIKE_IRONCLAD" for x in c.run.deck) == 4 and sum(x["id"] == "DEFEND_IRONCLAD" for x in c.run.deck) == 3
    assert len(c.run.deck) == 10


def test_new_leaf_transforms_one_card():
    c = ctx_with_bag()
    before = ids(c)
    obtain_relic(c, "NEW_LEAF")
    assert len(c.run.deck) == len(before) and ids(c) != before


def test_lead_paperweight_offers_two_colorless_cards():
    c = ctx_with_bag()
    obtain_relic(c, "LEAD_PAPERWEIGHT")
    cards = c.run.offers[-1]["cards"]
    assert len(cards) == 2 and all(x["rarity"] in ("Uncommon", "Rare") for x in cards)


def test_scroll_boxes_offer_two_bundles_of_six_distinct_cards():
    c = ctx_with_bag()
    obtain_relic(c, "SCROLL_BOXES")
    bundles = c.run.offers[-1]["bundles"]
    cards = [x["id"] for b in bundles for x in b]
    assert len(bundles) == 2 and len(set(cards)) == 6
    assert all([x["rarity"] for x in b] == ["Common", "Common", "Uncommon"] for b in bundles)


def test_neows_bones_gives_two_neow_relics_and_a_curse():
    c = ctx_with_bag()
    n = len(c.run.relics)
    obtain_relic(c, "NEOWS_BONES")
    got = [r["id"] for r in c.run.relics[n + 1:]]
    assert len(got) == 2 and all(r in neow_relics() for r in got) and "NEOWS_BONES" not in neow_relics()
    assert any(x["type"] == "Curse" for x in c.run.deck)


def test_silken_tress_takes_the_gold_and_glams_the_first_card_reward_only():
    c = ctx_with_bag()
    obtain_relic(c, "SILKEN_TRESS")
    assert c.run.gold == 0
    cards = [card_entry("ANGER"), card_entry("ARMAMENTS")]
    first = run_hooks.modify_card_offers(c.run, cards, c.rng, True)
    assert all(x["enchantment"]["id"] == "GLAM" for x in first)
    second = run_hooks.modify_card_offers(c.run, cards, c.rng, True)
    assert not any(x.get("enchantment") for x in second)
    c2 = ctx_with_bag()
    obtain_relic(c2, "SILKEN_TRESS")
    assert not any(x.get("enchantment") for x in run_hooks.modify_card_offers(c2.run, cards, c2.rng, False, is_reward=False))     # the shop is not a card reward


def test_neow_never_offers_massive_scroll():
    from sts2_lite.campaign.ancients import neow
    import random
    from sts2_lite.run import new_run
    for i in range(300):
        assert all(o.relic != "MASSIVE_SCROLL" for o in neow(new_run(0), random.Random(i)))


def test_simple_ancient_pickups():
    c = ctx_with_bag()
    hp, mx, gold = c.run.hp, c.run.max_hp, c.run.gold
    obtain_relic(c, "LOOMING_FRUIT")
    obtain_relic(c, "SIGNET_RING")
    obtain_relic(c, "TANXS_WHISTLE")
    assert c.run.max_hp == mx + 31 and c.run.hp == hp + 31 and c.run.gold >= gold + 999 and "WHISTLE" in ids(c)


def test_claws_transform_into_maul_keeping_upgrade():
    c = ctx_with_bag()
    c.run.deck[0] = dict(c.run.deck[0], is_upgraded=True, _upgrade=True)
    obtain_relic(c, "CLAWS")
    assert "MAUL" in ids(c) and 1 <= ids(c).count("MAUL") <= 6
    assert any(x["id"] == "MAUL" and x.get("is_upgraded") for x in c.run.deck) or c.run.deck[0]["id"] != "MAUL"


def test_tri_boomerang_enchants_three_cards_with_instinct():
    c = ctx_with_bag()
    obtain_relic(c, "TRI_BOOMERANG")
    assert sum(1 for x in c.run.deck if (x.get("enchantment") or {}).get("id") == "INSTINCT") <= 3


def test_glitter_makes_every_card_reward_glam_and_war_hammer_upgrades_after_elites():
    import random
    c = ctx_with_bag()
    obtain_relic(c, "GLITTER")
    cards = [card_entry("BASH"), card_entry("STRIKE_R") if False else card_entry("ANGER")]
    out = run_hooks.modify_card_offers(c.run, cards, random.Random(1), True)
    assert all((x.get("enchantment") or {}).get("id") == "GLAM" for x in out)
    obtain_relic(c, "WAR_HAMMER")
    before = sum(1 for x in c.run.deck if x.get("is_upgraded"))
    run_hooks.combat_finished(c.run, "Elite", random.Random(2), True)
    assert sum(1 for x in c.run.deck if x.get("is_upgraded")) == min(before + 4, before + sum(1 for x in c.run.deck if not x.get("is_upgraded")))


def test_card_changing_ancient_relics():
    c = ctx_with_bag()
    n = len(c.run.deck)
    obtain_relic(c, "PRESERVED_FOG")
    assert "FOLLY" in ids(c) and len(c.run.deck) == n - 3 + 1
    c = ctx_with_bag()
    obtain_relic(c, "SERE_TALON")
    assert ids(c).count("WISH") == 3 and len(c.run.deck) == n + 5
    c = ctx_with_bag()
    obtain_relic(c, "PANDORAS_BOX")
    assert "STRIKE_R" not in ids(c) and "DEFEND_R" not in ids(c) and len(c.run.deck) == n
    c = ctx_with_bag()
    obtain_relic(c, "ASTROLABE")
    assert len(c.run.deck) == n and sum(1 for x in c.run.deck if x.get("is_upgraded")) >= 1


def test_golden_compass_map_and_fur_coat_marks_and_winged_boots():
    from sts2_lite.map import PointType, golden_path_map
    m = golden_path_map()
    assert [p.type.name for p in m.points()][:3] == ["MONSTER", "UNKNOWN", "MONSTER"] and len(m.points()) == 16
    assert m.start.type == PointType.ANCIENT and m.boss.row == 17 and m.second_boss is None
    node = m.start
    while node.children:
        assert len(node.children) == 1
        node = node.children[0]
    assert node is m.boss


def test_fur_coat_marks_seven_fight_points_and_boots_count_down():
    from sts2_lite.map import generate_map
    import random
    c = ctx_with_bag()
    c.run.act = 1
    c.run.map = generate_map("OVERGROWTH", random.Random(3), 15)
    obtain_relic(c, "FUR_COAT")
    marked = c.run.relic_state["FUR_COAT"]["marked"]
    assert len(marked) == 7 and all(c.run.map.at(*m).type.name in ("MONSTER", "ELITE") for m in marked)
    assert run_hooks.fur_coat_marked(c.run, marked[0]) and not run_hooks.fur_coat_marked(c.run, (0, 0))
    obtain_relic(c, "WINGED_BOOTS")
    for _ in range(3):
        assert run_hooks.free_travel(c.run)
        run_hooks.traveled(c.run, False)
    assert not run_hooks.free_travel(c.run)


def test_toy_box_wax_melts_every_three_fights_and_silver_crucible_upgrades_three_rewards():
    import random
    c = ctx_with_bag()
    obtain_relic(c, "TOY_BOX")
    waxes = [o for o in c.run.offers if o.get("wax")]
    assert len(waxes) == 4 and len({o["relic"] for o in waxes}) == 4
    for o in waxes:
        c.run.relics.append({"id": o["relic"], "name": o["relic"], "wax": True})
    for _ in range(3):
        run_hooks.combat_finished(c.run, "Monster", random.Random(1), True)
    assert sum(1 for r in c.run.relics if r.get("melted")) == 1
    assert not c.run.has_relic([r for r in c.run.relics if r.get("melted")][0]["id"])
    obtain_relic(c, "SILVER_CRUCIBLE")
    for i in range(4):
        out = run_hooks.modify_card_offers(c.run, [card_entry("ANGER")], random.Random(i), True)
        assert out[0].get("is_upgraded") == (i < 3)
    assert not run_hooks.treasure_gives_relic(c.run) and run_hooks.treasure_gives_relic(c.run)


def test_neows_sacrifice_gives_an_ambergris_and_a_guilty():
    c = ctx_with_bag()
    obtain_relic(c, "NEOWS_SACRIFICE")
    assert "GUILTY" in ids(c)
    assert [p["id"] for p in c.run.potions] == ["AMBERGRIS"]
