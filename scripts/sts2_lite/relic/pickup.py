"""What a relic does the moment it is obtained (`AfterObtained`), for the relics the bag, shops and events hand out.

`obtain_relic(ctx, relic_id)` puts the relic in the run (pulling one from the grab bag when no id is given) and plays its effect through the event `Ctx`:
hit points, gold, potion slots, card upgrades / enchantments / removals, cards added to the deck. Whatever the game *offers* (card reward screens, potions)
is queued in `run.offers`, for whoever plays the run to put to the agent. Relics that need parts of the run the sandbox does not model yet are listed in
`NOT_MODELLED` and still enter the relic list."""
from __future__ import annotations

from typing import Callable

from sts2_lite.event.run import card_entry, can_upgrade
from sts2_lite.relic.bag import pull_relic, relic_name

# --- queued offers ---------------------------------------------------------------------------------------------------------------------------------------


def offer_cards(ctx, count : int, pool_rarity : str | None = None, uniform : bool = False, no_upgrade : bool = False, n_screens : int = 1):
    """`n_screens` card reward screens of 3 cards. `pool_rarity` limits the pool to one rarity (a uniform draw)."""
    from sts2_lite.rewards import CardRarityOdds, create_card_reward
    from sts2_lite.rewards.cards import IRONCLAD_POOL
    from sts2_lite.rewards.odds import OddsType
    run = ctx.run
    for _ in range(n_screens):
        odds = CardRarityOdds(ctx.rng, run.ascension, run.hidden.rarity_offset)
        pool = None
        if pool_rarity:
            pool = list(IRONCLAD_POOL[pool_rarity])
        offers = create_card_reward(ctx.rng, odds, max(0, run.act - 1), count, OddsType.UNIFORM if (uniform or pool_rarity) else OddsType.REGULAR_ENCOUNTER,
                                    pool=pool, no_upgrade_roll=no_upgrade)
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


def _cursed_pearl(c):
    c.add_card("GREED")
    c.gain_gold(333)


def _distinguished_cape(c):
    c.lose_max_hp(9)
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


EFFECTS : dict[str, Callable] = {
    "PAELS_TOOTH": _paels_tooth,
    "STRAWBERRY": _max_hp(7), "MANGO": _max_hp(14), "PEAR": _max_hp(10), "LEES_WAFFLE": _max_hp(7, heal_full=True), "FAKE_MANGO": _max_hp(3),
    "FAKE_LEES_WAFFLE": lambda c: c.heal(int(c.run.max_hp * 0.10)),
    "OLD_COIN": _gold(300), "GOLDEN_PEARL": _gold(150), "CURSED_PEARL": _cursed_pearl,
    "POTION_BELT": _potion_belt, "ALCHEMICAL_COFFER": _alchemical_coffer,
    "WAR_PAINT": _upgrade_type("Skill"), "WHETSTONE": _upgrade_type("Attack"), "FRAGRANT_MUSHROOM": _fragrant_mushroom,
    "KIFUDA": _enchant_n("ADROIT", 3, 3), "GNARLED_HAMMER": _enchant_n("SHARP", 3, 3), "PUNCH_DAGGER": _enchant_n("MOMENTUM", 5, 1), "ROYAL_STAMP": _enchant_n("ROYALLY_APPROVED", 1, 1),
    "BEAUTIFUL_BRACELET": _enchant_n("SWIFT", 3, 3), "ELECTRIC_SHRYMP": _enchant_n("IMBUED", 1, 1),
    "DOLLYS_MIRROR": _dollys_mirror, "EMPTY_CAGE": _empty_cage, "LARGE_CAPSULE": _large_capsule,
    "DISTINGUISHED_CAPE": _distinguished_cape, "JEWELRY_BOX": lambda c: c.add_card("APOTHEOSIS"),
    "ORRERY": lambda c: offer_cards(c, 3, n_screens=5), "CAULDRON": lambda c: offer_potions(c, 5),
    "ARCANE_SCROLL": lambda c: offer_cards(c, 1, pool_rarity="Rare", no_upgrade=True),
    "GLASS_EYE": _glass_eye, "CALLING_BELL": _calling_bell,
}

# relics whose pickup effect needs something the sandbox does not model (maps, colourless / other-class cards, transformations into set cards, ...)
NOT_MODELLED = frozenset({"ARCHAIC_TOOTH", "ASTROLABE", "BYRDPIP", "CLAWS", "DUSTY_TOME", "FAKE_SNECKO_EYE", "FUR_COAT", "GOLDEN_COMPASS", "HEFTY_TABLET", "KALEIDOSCOPE",
                          "LEAD_PAPERWEIGHT", "LOST_COFFER", "MASSIVE_SCROLL", "NEOWS_BONES", "NEOWS_TALISMAN", "NEOWS_TORMENT", "NEW_LEAF", "NUTRITIOUS_OYSTER",
                          "NUTRITIOUS_SOUP", "PAELS_CLAW", "PAELS_GROWTH", "PAELS_HORN", "PAELS_TOOTH", "PANDORAS_BOX", "PHIAL_HOLSTER", "POMANDER", "PRECARIOUS_SHEARS", "PRECISE_SCISSORS",
                          "PRESERVED_FOG", "SAND_CASTLE", "SCROLL_BOXES", "SEA_GLASS", "SERE_TALON", "SIGNET_RING", "SILKEN_TRESS", "SMALL_CAPSULE", "STORYBOOK", "TANXS_WHISTLE",
                          "TOUCH_OF_OROBAS", "TOY_BOX", "TRI_BOOMERANG", "YUMMY_COOKIE", "LEAFY_POULTICE", "LOOMING_FRUIT"})


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
