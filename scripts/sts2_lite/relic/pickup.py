"""What a relic does the moment it is obtained (`AfterObtained`), for the relics the bag, shops and events hand out.

`obtain_relic(ctx, relic_id)` puts the relic in the run (pulling one from the grab bag when no id is given) and plays its effect through the event `Ctx`:
hit points, gold, potion slots, card upgrades / enchantments / removals, cards added to the deck. Whatever the game *offers* (card reward screens, potions)
is queued in `run.offers`, for whoever plays the run to put to the agent. Relics that need parts of the run the sandbox does not model yet are listed in
`NOT_MODELLED` and still enter the relic list."""
from __future__ import annotations

from typing import Callable

from sts2_lite.event.run import card_entry, can_upgrade, is_curse
from sts2_lite.relic.bag import pull_relic, relic_name

# --- queued offers ---------------------------------------------------------------------------------------------------------------------------------------


def offer_cards(ctx, count : int, pool_rarity : str | None = None, uniform : bool = False, no_upgrade : bool = False, n_screens : int = 1, pool=None):
    """`n_screens` card reward screens of `count` cards. `pool_rarity` limits the pool to one rarity (a uniform draw); `pool` is a list of card ids to draw from."""
    from sts2_lite.rewards import CardRarityOdds, create_card_reward
    from sts2_lite.rewards.cards import card_pool
    from sts2_lite.rewards.odds import OddsType
    run = ctx.run
    for _ in range(n_screens):
        odds = CardRarityOdds(ctx.rng, run.ascension, run.hidden.rarity_offset)
        pool = list(pool) if pool is not None else None
        if pool_rarity:
            pool = list(card_pool(run.character)[pool_rarity])
        offers = create_card_reward(ctx.rng, odds, max(0, run.act - 1), count, OddsType.UNIFORM if (uniform or pool_rarity) else OddsType.REGULAR_ENCOUNTER,
                                    pool=pool, no_upgrade_roll=no_upgrade, character=run.character)
        run.offers.append({"kind": "cards", "cards": [card_entry(o.card_id, o.upgraded) for o in offers]})


def offer_potions(ctx, n : int):
    ctx.run.offers.extend({"kind": "potion"} for _ in range(n))


# --- effects ---------------------------------------------------------------------------------------------------------------------------------------------


def _max_hp(n : int, heal_full : bool = False) -> Callable:
    def effect(c):
        c.gain_max_hp(n)
        if heal_full:
            c.heal_to_full()
    return effect


def _gold(n : int) -> Callable:
    return lambda c: c.gain_gold(n)


def _upgrade_type(card_type : str, n : int = 2) -> Callable:
    def effect(c):
        allowed = [i for i, x in enumerate(c.run.deck) if x.get("type") == card_type and can_upgrade(x)]
        c.rng.shuffle(allowed)
        for i in allowed[:n]:
            c.upgrade_at(i)
    return effect


def _enchant_n(enchantment : str, amount : int, count : int) -> Callable:
    return lambda c: c.enchant(enchantment, amount, count=count)


def _enchant_random(enchantment : str, amount : int, count : int) -> Callable:
    """`count` random enchantable cards of the deck (no choice: Beautiful Bracelet)."""
    def effect(c):
        from sts2_lite.event.run import enchanted
        allowed = c.enchantable(enchantment, None)
        for i in c.rng.sample(allowed, min(count, len(allowed))):
            c.run.deck[i] = enchanted(c.run.deck[i], enchantment, amount)
    return effect


def _fragrant_mushroom(c):
    c.lose_hp(15)
    allowed = [i for i, x in enumerate(c.run.deck) if can_upgrade(x)]
    c.rng.shuffle(allowed)
    for i in allowed[:2]:
        c.upgrade_at(i)


def _dollys_mirror(c):
    allowed = list(range(len(c.run.deck)))
    for i in c.picker.take([c.run.deck[i] for i in allowed], 1)[:1]:        # the card to copy
        from sts2_lite.relic.run_hooks import add_to_deck
        add_to_deck(c.run, dict(c.run.deck[allowed[i]]))


def _potion_belt(c):
    c.run.potion_slots += 2


def _large_capsule(c):
    for _ in range(2):
        obtain_relic(c)
    c.add_card("STRIKE_IRONCLAD")
    c.add_card("DEFEND_IRONCLAD")


def _neows_sacrifice(c):
    """Neow's curse option: an Ambergris potion (heals half the max HP) and a Guilty (unplayable, gone after 5 combats)."""
    c.gain_potion("AMBERGRIS")
    c.add_card("GUILTY")


def _dowsing_rod(c):
    """Neow's curse option: a Dowsing (Quest, Unplayable) that turns into Abundance after 5 more ? rooms (campaign.simulator.enter)."""
    c.add_placeholder("DOWSING", "Dowsing", "Quest")


def _cursed_pearl(c):
    c.add_card("GREED")
    c.gain_gold(333)


def _distinguished_cape(c):
    """Two different random curses (CanBeGeneratedByModifiers) and three Apparitions (the downside it took from Sere Talon)."""
    pool = list(MODIFIER_CURSES)
    for _ in range(2):
        curse = c.rng.choice(pool)
        pool.remove(curse)
        c.add_card(curse)
    for _ in range(3):
        c.add_card("APPARITION")


def _empty_cage(c):
    c.remove_cards(2)


def _calling_bell(c):
    c.add_card("CURSE_OF_THE_BELL")
    for _ in range(3):
        c.run.offers.append({"kind": "relic"})


def _glass_eye(c):
    for rarity in ("Common", "Common", "Uncommon", "Uncommon", "Rare"):
        offer_cards(c, 3, pool_rarity=rarity, no_upgrade=True)


def _alchemical_coffer(c):
    c.run.potion_slots += 4
    offer_potions(c, 4)


def _paels_tooth(c):
    """Five upgradable cards leave the deck; one comes back (upgraded) after each combat."""
    from sts2_lite.relic.run_hooks import state
    state(c.run, "PAELS_TOOTH")["cards"] = c.remove_cards(5, can_upgrade)


def _give_potions(c, n : int):
    """Random potions go straight on the belt (PotionCmd.TryToProcure): the ones that find no free slot are lost."""
    from sts2_lite.potion_pool import create_random_potions
    for potion in create_random_potions(c.rng, n, c.run.character):
        if len(c.run.potions) < c.run.potion_slots:
            c.run.potions.append({"id": potion.name, "name": potion.name.replace("_", " ").title()})


def _phial_holster(c):
    c.run.potion_slots += 1
    _give_potions(c, 2)


def _lead_paperweight(c):
    from sts2_lite.card.tables import COLORLESS_CARDS
    offer_cards(c, 2, pool=list(COLORLESS_CARDS))


def _upgrade_last_basic(c):
    """Neow's Talisman: the last Basic Strike and the last Basic Defend."""
    from sts2_lite.event.run import is_basic_defend, is_basic_strike
    for test in (is_basic_strike, is_basic_defend):
        found = [i for i, x in enumerate(c.run.deck) if test(x)]
        if found and can_upgrade(c.run.deck[found[-1]]):
            c.upgrade_at(found[-1])


def _hefty_tablet(c):
    offer_cards(c, 3, pool_rarity="Rare", no_upgrade=True)
    c.add_card("INJURY")


def _leafy_poultice(c):
    """12 max HP for the first Basic Strike and the first Basic Defend becoming random cards."""
    from sts2_lite.event.run import class_pool_ids, is_basic_defend, is_basic_strike
    c.lose_max_hp(12)
    for test in (is_basic_strike, is_basic_defend):
        found = next((i for i, x in enumerate(c.run.deck) if test(x)), None)
        if found is not None:
            old = c.run.deck[found]
            c.run.deck[found] = card_entry(c.rng.choice([cid for cid in class_pool_ids(c.run.character) if cid.name != old["id"]]))


def _neows_bones(c):
    """Two relics Neow could have offered (curses and boons alike; not Bones itself), both taken, and a random curse card (Niche rng, modifier-safe curses)."""
    from sts2_lite.relic.ancient_data import neow_relics
    relics = neow_relics()
    c.rng.shuffle(relics)
    for relic in relics[:2]:
        obtain_relic(c, relic)
    c.add_card(c.rng.choice(MODIFIER_CURSES))


MODIFIER_CURSES = sorted(("CLUMSY", "DEBT", "DECAY", "DOUBT", "GUILTY", "INJURY", "NORMALITY", "REGRET", "SHAME", "WRITHE"))      # curses with CanBeGeneratedByModifiers


def _precarious_shears(c):
    c.remove_cards(2)
    c.lose_hp(16)


def _scroll_boxes(c):
    """Two bundles of 2 Common + 1 Uncommon (six different cards); the agent keeps one bundle."""
    from sts2_lite.rewards.cards import card_pool
    pool = card_pool(c.run.character)
    commons, uncommons, used, bundles = list(pool["Common"]), list(pool["Uncommon"]), set(), []
    for _ in range(2):
        bundle = []
        for pool, n in ((commons, 2), (uncommons, 1)):
            for _ in range(n):
                card = c.rng.choice([x for x in pool if x not in used])
                used.add(card)
                bundle.append(card_entry(card))
        bundles.append(bundle)
    c.run.offers.append({"kind": "bundle", "bundles": bundles})


def _enchant_all(enchantment : str, amount : int = 1) -> Callable:
    def effect(c):
        from sts2_lite.event.run import can_enchant, enchanted
        for i, card in enumerate(c.run.deck):
            if can_enchant(card, enchantment):
                c.run.deck[i] = enchanted(card, enchantment, amount)
    return effect


def _add_cards(card_id : str, n : int = 1) -> Callable:
    def effect(c):
        for _ in range(n):
            c.add_card(card_id)
    return effect


def _touch_of_orobas(c):
    """The starter relic is replaced by its upgrade (Burning Blood: Black Blood)."""
    upgrades = {"BURNING_BLOOD": ("BLACK_BLOOD", "Black Blood"), "RING_OF_THE_SNAKE": ("RING_OF_THE_DRAKE", "Ring of the Drake"),
                "BOUND_PHYLACTERY": ("PHYLACTERY_UNBOUND", "Phylactery Unbound"), "CRACKED_CORE": ("INFUSED_CORE", "Infused Core")}
    for i, r in enumerate(c.run.relics):
        if r["id"] in upgrades:
            c.run.relics[i] = {"id": upgrades[r["id"]][0], "name": upgrades[r["id"]][1]}
            return


def _archaic_tooth(c):
    """A starter card becomes its Ancient version (Bash: Break), keeping its upgrade and enchantment."""
    transcend = {"BASH": "BREAK", "FALLING_STAR": "METEOR_SHOWER", "NEUTRALIZE": "SUPPRESS", "UNLEASH": "PROTECTOR"}
    for i, card in enumerate(c.run.deck):
        if card["id"] in transcend:
            new = card_entry(transcend[card["id"]], bool(card.get("is_upgraded")))
            if card.get("enchantment"):
                new["enchantment"] = card["enchantment"]
            c.run.deck[i] = new
            return


def _dusty_tome(c):
    from sts2_lite.relic.run_hooks import add_to_deck, state
    card = state(c.run, "DUSTY_TOME").get("card", "CORRUPTION")
    add_to_deck(c.run, card_entry(card, True))


def _claws(c):
    """Up to 6 picked cards become Maul, keeping the upgrade (when Maul can take it) and the enchantment (when Maul can carry it)."""
    from sts2_lite.event.run import can_enchant, can_upgrade, enchanted
    allowed = [i for i, x in enumerate(c.run.deck) if x.get("removable") is not False and not is_curse(x)]
    for i in sorted(set(c.picker.transform(c.run.deck, 6, allowed)) & set(allowed)):
        old = c.run.deck[i]
        new = card_entry("MAUL", False)
        if old.get("is_upgraded") and can_upgrade(new):
            new = dict(new, is_upgraded=True, _upgrade=True)
        ench = old.get("enchantment")
        if ench and can_enchant(new, ench["id"]):
            new = enchanted(new, ench["id"], ench.get("amount", 1))
        c.run.deck[i] = new


def _transform_picked(c, indices, upgrade : bool = False):
    from sts2_lite.event.run import class_pool_ids
    for i in indices:
        old = c.run.deck[i]
        new = card_entry(c.rng.choice([cid for cid in class_pool_ids(c.run.character) if cid.name != old["id"]]), upgrade)
        c.run.deck[i] = new


def _astrolabe(c):
    allowed = [i for i, x in enumerate(c.run.deck) if x.get("removable") is not False and not is_curse(x)]
    _transform_picked(c, sorted(set(c.picker.transform(c.run.deck, 3, allowed)) & set(allowed)), upgrade=True)


def _pandoras_box(c):
    from sts2_lite.event.run import is_basic_strike, is_basic_defend
    _transform_picked(c, [i for i, x in enumerate(c.run.deck) if x.get("removable") is not False and (is_basic_strike(x) or is_basic_defend(x))])


def _preserved_fog(c):
    c.remove_cards(3)
    c.add_card("FOLLY")


def _sere_talon(c):
    """9 Max HP and three Wishes (the downside it took from Distinguished Cape)."""
    c.lose_max_hp(9)
    for _ in range(3):
        c.add_card("WISH")


def _golden_compass(c):
    """The act's map becomes the golden path (one column, no choices) and its "?" rooms are all events (see `golden_path_act`)."""
    from sts2_lite.map import golden_path_map
    from sts2_lite.relic.run_hooks import state
    state(c.run, "GOLDEN_COMPASS")["act"] = c.run.act
    if getattr(c.run, "map", None) is not None:
        c.run.map = golden_path_map()


def _fur_coat(c):
    """Eight random fight points (Monster or Elite) of this act's map are marked: the enemies there start with 1 hit point."""
    from sts2_lite.map import PointType
    from sts2_lite.relic.run_hooks import state
    s = state(c.run, "FUR_COAT")
    s["act"] = c.run.act
    act_map = getattr(c.run, "map", None)
    if act_map is not None:
        points = [p for p in act_map.points() if p.type in (PointType.MONSTER, PointType.ELITE)]
        c.rng.shuffle(points)
        s["marked"] = sorted(p.coord for p in points[:8])


TOY_BOX_RELICS, TOY_BOX_COMBATS = 5, 3

def _toy_box(c):
    """Five relics come from the front of the bag and are taken as wax: one melts away (stops working) every 3 fights."""
    from sts2_lite.relic.bag import pull_relic
    for _ in range(TOY_BOX_RELICS):
        c.run.offers.append({"kind": "relic", "relic": pull_relic(c.run), "wax": True})


def _lost_coffer(c):
    offer_cards(c, 3)
    offer_potions(c, 1)


EFFECTS : dict[str, Callable] = {
    "NEOWS_TORMENT": lambda c: c.add_card("NEOWS_FURY"), "NEOWS_SACRIFICE": _neows_sacrifice, "DOWSING_ROD": _dowsing_rod, "LOST_COFFER": _lost_coffer, "NEW_LEAF": lambda c: c.transform(1),
    "PHIAL_HOLSTER": _phial_holster, "PRECISE_SCISSORS": lambda c: c.remove_cards(1), "LEAD_PAPERWEIGHT": _lead_paperweight, "NEOWS_TALISMAN": _upgrade_last_basic,
    "NUTRITIOUS_OYSTER": lambda c: c.gain_max_hp(11), "POMANDER": lambda c: c.upgrade_picked(1), "SMALL_CAPSULE": lambda c: c.run.offers.append({"kind": "relic"}),
    "HEFTY_TABLET": _hefty_tablet, "LEAFY_POULTICE": _leafy_poultice, "NEOWS_BONES": _neows_bones, "PRECARIOUS_SHEARS": _precarious_shears,
    "PAELS_CLAW": _enchant_all("GOOPY"), "PAELS_GROWTH": lambda c: c.enchant("CLONE", 4), "PAELS_HORN": _add_cards("RELAX", 2), "STORYBOOK": _add_cards("BRIGHTEST_FLAME"),
    "YUMMY_COOKIE": lambda c: c.upgrade_picked(4), "NUTRITIOUS_SOUP": _enchant_all("TEZCATARAS_EMBER"),
    "TOUCH_OF_OROBAS": _touch_of_orobas, "ARCHAIC_TOOTH": _archaic_tooth, "DUSTY_TOME": _dusty_tome,
    "SCROLL_BOXES": _scroll_boxes, "SAND_CASTLE": lambda c: c.upgrade_random(6), "SILKEN_TRESS": lambda c: c.lose_gold(c.run.gold),
    "PAELS_TOOTH": _paels_tooth,
    "GOLDEN_COMPASS": _golden_compass, "FUR_COAT": _fur_coat, "TOY_BOX": _toy_box,
    "ASTROLABE": _astrolabe, "PANDORAS_BOX": _pandoras_box, "PRESERVED_FOG": _preserved_fog, "SERE_TALON": _sere_talon,
    "LOOMING_FRUIT": lambda c: c.gain_max_hp(31), "SIGNET_RING": lambda c: c.gain_gold(888), "TANXS_WHISTLE": lambda c: c.add_card("WHISTLE"),
    "CLAWS": _claws, "TRI_BOOMERANG": lambda c: c.enchant("INSTINCT", 1, count=3),
    "STRAWBERRY": _max_hp(7), "MANGO": _max_hp(14), "PEAR": _max_hp(10), "LEES_WAFFLE": _max_hp(7, heal_full=True), "FAKE_MANGO": _max_hp(3),
    "FAKE_LEES_WAFFLE": lambda c: c.heal(int(c.run.max_hp * 0.10)),
    "OLD_COIN": _gold(300), "GOLDEN_PEARL": _gold(150), "CURSED_PEARL": _cursed_pearl, "BLOOD_SOAKED_ROSE": lambda c: c.add_card("ENTHRALLED"),
    "POTION_BELT": _potion_belt, "ALCHEMICAL_COFFER": _alchemical_coffer,
    "WAR_PAINT": _upgrade_type("Skill"), "WHETSTONE": _upgrade_type("Attack"), "FRAGRANT_MUSHROOM": _fragrant_mushroom,
    "KIFUDA": _enchant_n("ADROIT", 3, 3), "GNARLED_HAMMER": _enchant_n("SHARP", 3, 3), "PUNCH_DAGGER": _enchant_n("MOMENTUM", 5, 1), "ROYAL_STAMP": _enchant_n("ROYALLY_APPROVED", 1, 1),
    "BEAUTIFUL_BRACELET": _enchant_random("SWIFT", 2, 4), "ELECTRIC_SHRYMP": _enchant_n("IMBUED", 1, 1),
    "DOLLYS_MIRROR": _dollys_mirror, "EMPTY_CAGE": _empty_cage, "LARGE_CAPSULE": _large_capsule,
    "DISTINGUISHED_CAPE": _distinguished_cape, "JEWELRY_BOX": lambda c: c.add_card("APOTHEOSIS"),
    "ORRERY": lambda c: offer_cards(c, 3, n_screens=5), "CAULDRON": lambda c: offer_potions(c, 5),
    "ARCANE_SCROLL": lambda c: offer_cards(c, 1, pool_rarity="Rare", no_upgrade=True),
    "GLASS_EYE": _glass_eye, "CALLING_BELL": _calling_bell, "BYRDPIP": lambda c: _byrdpip(c),
}

def _byrdpip(c):
    """Byrdpip.AfterObtained: every Byrdonis Egg in the deck becomes a Byrd Swoop (the pet itself does nothing)."""
    c.run.deck[:] = [dict(card_entry("BYRD_SWOOP"), is_upgraded=card.get("is_upgraded", False)) if card["id"] == "BYRDONIS_EGG" else card for card in c.run.deck]


# relics whose pickup effect needs something the sandbox does not model (maps, colourless / other-class cards, transformations into set cards, ...)
NOT_MODELLED = frozenset({"KALEIDOSCOPE", "SEA_GLASS"})      # other characters' cards (the engine has only Ironclad's)


def obtain_relic(ctx, relic_id : str | None = None, name : str | None = None, **pull):
    """Put a relic in the run (drawn from the bag when `relic_id` is None) and play what it does on pickup."""
    run = ctx.run
    if relic_id is None:
        relic_id = pull_relic(run, **pull)
    run.relics.append({"id": relic_id, "name": name or relic_name(relic_id)})
    if getattr(run.hidden, "relic_bag", None) is not None:
        run.hidden.relic_bag.remove(relic_id)         # a relic that came another way (event, shop) is gone from the bag too
    effect = EFFECTS.get(relic_id)
    if effect is not None:
        effect(ctx)
    return relic_id


# RelicModel.IsTradable (Relic Trader, Ranwid the Elder): not a Starter / Event / Ancient relic, not used up, no pickup effect, no pet
HAS_PICKUP_EFFECT = frozenset("""ALCHEMICAL_COFFER ASTROLABE BYRDPIP CALLING_BELL CAULDRON DISTINGUISHED_CAPE DOLLYS_MIRROR ELECTRIC_SHRYMP EMPTY_CAGE FAKE_LEES_WAFFLE FAKE_MANGO
FRAGRANT_MUSHROOM GNARLED_HAMMER GOLDEN_COMPASS GOLDEN_PEARL HEFTY_TABLET JEWELRY_BOX KALEIDOSCOPE KIFUDA LEES_WAFFLE LOOMING_FRUIT LOST_COFFER MANGO
DOWSING_ROD NEOWS_SACRIFICE NEOWS_TALISMAN NEOWS_TORMENT NEW_LEAF NUTRITIOUS_OYSTER OLD_COIN ORRERY PAELS_TOOTH PANDORAS_BOX PEAR PHIAL_HOLSTER POTION_BELT PRECARIOUS_SHEARS
PRECISE_SCISSORS PUNCH_DAGGER ROYAL_STAMP SAND_CASTLE SEA_GLASS SERE_TALON STRAWBERRY TOY_BOX WAR_PAINT WHETSTONE YUMMY_COOKIE BOUND_PHYLACTERY PHYLACTERY_UNBOUND CRACKED_CORE INFUSED_CORE""".split())
TRADABLE_RARITIES = frozenset({"Common", "Uncommon", "Rare", "Shop"})


def tradable(run, relic_id : str) -> bool:
    from sts2_lite.relic.pool_data import POOL
    from sts2_lite.relic.run_hooks import state
    rarity = {r[0]: r[1] for r in POOL}.get(relic_id)
    if rarity not in TRADABLE_RARITIES or relic_id in HAS_PICKUP_EFFECT:
        return False
    s = run.relic_state.get(relic_id, {})
    return not ((relic_id == "WONGOS_MYSTERY_TICKET" and s.get("gave")) or (relic_id == "MAW_BANK" and s.get("bought")) or (relic_id == "WINGED_BOOTS" and s.get("used", 0) >= 3))


def remove_relic(run, relic_id : str):
    """RelicCmd.Remove: none of the tradable relics undoes anything when it goes."""
    for i, r in enumerate(run.relics):
        if r["id"] == relic_id:
            del run.relics[i]
            break
