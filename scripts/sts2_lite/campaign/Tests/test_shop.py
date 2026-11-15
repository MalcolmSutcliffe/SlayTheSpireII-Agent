"""The merchant: stock, prices, purchases, card removal."""
from sts2_lite import rng
from sts2_lite.campaign import RunSimulator
from sts2_lite.campaign.shop import Shop
from sts2_lite.campaign.Tests.test_sandbox import RandomFighter, sim_of
from sts2_lite.potion import POTION_INFO, PotionId
from sts2_lite.potion_pool import create_random_potions, potion_pool


def shop_of(seed=0, ascension=0, relics=(), gold=500):
    sim = sim_of(RandomFighter(), seed=seed, ascension=ascension)
    sim.run_state.gold = gold
    for r in relics:
        sim.run_state.relics.append({"id": r, "name": r})
    return sim, Shop(sim.run_state, sim.game, sim.game.stream("relics"))


def test_stock_shape():
    for seed in range(20):
        sim, shop = shop_of(seed)
        types = [e.item["type"] for e in shop.cards[:5]]
        assert types == ["Attack", "Attack", "Skill", "Skill", "Power"]
        assert sum(e.on_sale for e in shop.cards) == 1
        assert [e.slot for e in shop.cards[5:]] == ["Uncommon", "Rare"]
        assert len({e.item["id"] for e in shop.cards}) == 7          # no card twice
        assert len(shop.relics) == 3 and shop.relics[2].slot == "Shop"
        assert len({e.item for e in shop.potions}) == 3
        assert all(e.cost > 0 for e in shop.entries)


def test_card_prices_by_rarity():
    bounds = {"Common": (47, 53), "Uncommon": (71, 79), "Rare": (142, 158)}
    for seed in range(20):
        sim, shop = shop_of(seed)
        for e in shop.cards[:5]:
            low, high = bounds[e.item["rarity"]]
            low, high = (low // 2, high // 2 + 1) if e.on_sale else (low, high)
            assert low <= e.cost <= high
        for e in shop.cards[5:]:
            assert e.cost >= 80


def test_removal_price_and_inflation():
    _, shop = shop_of(0)
    assert shop.removal.cost == 75
    _, shop = shop_of(0, ascension=6)
    assert shop.removal.cost == 100
    sim, _ = shop_of(0, ascension=6)
    sim.run_state.hidden.shop_removals = 2
    assert Shop(sim.run_state, sim.game, sim.game.stream("relics")).removal.cost == 200


def test_membership_card_and_courier_discount():
    sim, shop = shop_of(0, relics=("MEMBERSHIP_CARD",))
    assert shop.price(shop.removal) == 37
    sim, shop = shop_of(0, relics=("THE_COURIER",))
    assert shop.price(shop.removal) == 60


def test_relics_never_include_shop_banned_ones():
    for seed in range(30):
        _, shop = shop_of(seed)
        assert not {e.item for e in shop.relics} & {"AMETHYST_AUBERGINE", "LUCKY_FYSH", "OLD_COIN", "BOWLER_HAT", "THE_COURIER"}


def test_courier_restocks_a_bought_slot():
    sim, shop = shop_of(1, relics=("THE_COURIER",))
    first = shop.relics[0].item
    shop.after(shop.relics[0], 100)
    assert shop.relics[0].item is not None and shop.relics[0].item != first
    shop.after(shop.cards[0], 50)
    assert shop.cards[0].item is not None and not shop.cards[0].on_sale
    _, plain = shop_of(1)
    plain.after(plain.potions[0], 50)
    assert plain.potions[0].item is None


def test_maw_bank_notes_spending():
    sim, shop = shop_of(2, relics=("MAW_BANK",))
    shop.after(shop.potions[0], 0)
    assert not sim.run_state.relic_state.get("MAW_BANK", {}).get("bought")
    shop.after(shop.potions[1], 50)
    assert sim.run_state.relic_state["MAW_BANK"]["bought"]


def test_potion_factory_pools_and_rarity():
    pool = potion_pool()
    assert {PotionId.BLOOD_POTION, PotionId.ASHWATER, PotionId.SOLDIERS_STEW} <= set(pool)
    assert not {PotionId.FOUL_POTION, PotionId.GLOWWATER_POTION, PotionId.AMBERGRIS, PotionId.POTION_SHAPED_ROCK} & set(pool)
    sim = sim_of(RandomFighter(), 0)
    rng = sim.game.stream("potion_rewards")
    counts = {}
    for _ in range(2000):
        p = create_random_potions(rng, 1)[0]
        counts[POTION_INFO[p].rarity.name] = counts.get(POTION_INFO[p].rarity.name, 0) + 1
    assert 0.05 < counts["RARE"] / 2000 < 0.15 and 0.2 < counts["UNCOMMON"] / 2000 < 0.3
    assert len(set(create_random_potions(rng, 3))) == 3


def test_full_runs_shop_without_illegal_choices():
    shopped = 0
    for seed in range(8):
        result = sim_of(RandomFighter(), seed=seed).run()
        shopped += any(v.room == "Shop" for v in result.history)
        assert result.illegal_choices == 0
    assert shopped


class Spender(RandomFighter):
    """Buys whatever is on offer until it cannot, then leaves."""
    def get_decision(self, decision):
        buys = [o for o in decision.options if o.action.get("action") == "shop_purchase"]
        return rng.current().choice(buys) if buys else super().get_decision(decision)


def test_a_spending_agent_buys_every_kind_of_item_legally():
    kinds, gold_ok = set(), True
    orig = Shop.after
    def watch(self, entry, spent):
        kinds.add(entry.kind)
        return orig(self, entry, spent)
    Shop.after = watch
    try:
        for seed in range(12):
            sim = sim_of(Spender(), seed=seed)
            result = sim.run()
            gold_ok &= sim.run_state.gold >= 0 and result.illegal_choices == 0
    finally:
        Shop.after = orig
    assert gold_ok and kinds >= {"card", "relic", "potion", "removal"}


def test_lords_parasol_style_free_purchase_takes_everything_without_gold():
    sim, shop = shop_of(3, gold=50)
    r = sim.run_state
    decks, relics = len(r.deck), len(r.relics)
    for e in [e for e in shop.entries if e.kind != "removal"]:
        assert sim.buy(shop, e, 0)
    assert r.gold == 50 and len(r.deck) >= decks + 7 and len(r.relics) == relics + 3 and len(r.potions) >= 1


def test_meat_cleaver_and_paels_growth_add_rest_options():
    from sts2_lite.relic import run_hooks
    sim, _ = shop_of(0, relics=("MEAT_CLEAVER", "PAELS_GROWTH"))
    assert run_hooks.rest_extra_options(sim.run_state) == ["COOK", "CLONE"]


class AlwaysAlternative(RandomFighter):
    """Takes the reroll when the card reward offers one, the sacrifice otherwise."""
    def __init__(self, prefer):
        super().__init__()
        self.prefer, self.seen = prefer, []

    def get_decision(self, decision):
        if decision.kind == "card_reward":
            ids = [o.action.get("option_id") for o in decision.options if o.action["action"] == "card_reward_alternative"]
            self.seen.append(tuple(ids))
            for o in decision.options:
                if o.action["action"] == "card_reward_alternative" and o.action["option_id"] == self.prefer:
                    return o
        return super().get_decision(decision)


def test_driftwood_rerolls_once_and_paels_wing_gives_a_relic_for_two_sacrifices():
    agent = AlwaysAlternative("REROLL")
    sim = sim_of(agent, seed=2)
    sim.run_state.relics.append({"id": "DRIFTWOOD", "name": "Driftwood"})
    result = sim.run()
    assert result.illegal_choices == 0
    assert ("REROLL",) in agent.seen and () in agent.seen            # offered once, gone after the reroll

    agent = AlwaysAlternative("SACRIFICE")
    sim = sim_of(agent, seed=2)
    sim.run_state.relics.append({"id": "PAELS_WING", "name": "Pael's Wing", "counter": 0})
    before = len(sim.run_state.relics)
    result = sim.run()
    wing = sim.run_state.relic_state["PAELS_WING"]["sacrificed"]
    assert result.illegal_choices == 0 and wing >= 2
    assert len(sim.run_state.relics) - before >= wing // 2 and not any(c["id"] == "PAELS_WING" for c in sim.run_state.deck)


class Buyer(RandomFighter):
    def get_decision(self, decision):
        if decision.kind == "shop":
            for o in decision.options:
                if o.action["action"] == "shop_purchase":
                    return o
            return decision.options[-1]
        return super().get_decision(decision)


def test_fake_merchant_sells_six_fake_relics_at_fifty_gold():
    from sts2_lite.event import EVENTS, available
    sim = sim_of(Buyer(), seed=4)
    r = sim.run_state
    r.gold, r.act = 160, 2
    assert "FAKE_MERCHANT" in {e.id for e in available(r)} and "FAKE_MERCHANT" not in {e.id for e in available(r, 1)}
    r.gold = 99
    assert "FAKE_MERCHANT" not in {e.id for e in available(r)}
    r.gold = 160
    before = len(r.relics)
    sim.fake_merchant()
    spent = 160 - r.gold
    assert len(r.relics) == before + 3 and all(x["id"].startswith("FAKE_") for x in r.relics[before:]) and 3 * 42 <= spent <= 3 * 58
    sim2 = sim_of(Buyer(), seed=4)
    sim2.run_state.gold, sim2.run_state.act = 160, 2
    sim2.run_state.relics.append({"id": "MEMBERSHIP_CARD", "name": "Membership Card"})
    n = len(sim2.run_state.relics)
    sim2.fake_merchant()
    assert 160 - sim2.run_state.gold == spent and len(sim2.run_state.relics) == n + 3          # no half price


def test_venerable_tea_set_gives_energy_in_the_fight_after_a_rest():
    from sts2_lite.relic import run_hooks
    from sts2_lite.campaign.combat import start_fight
    for relic, extra in (("VENERABLE_TEA_SET", 2), ("FAKE_VENERABLE_TEA_SET", 1)):
        sim = sim_of(RandomFighter(), seed=1)
        r = sim.run_state
        r.relics.append({"id": relic, "name": relic})
        base = start_fight(r, "NIBBITS_WEAK", "monster", sim.game).combat_state.energy
        run_hooks.room_entered(r, "RestSite")
        boosted = start_fight(r, "NIBBITS_WEAK", "monster", sim.game).combat_state.energy
        again = start_fight(r, "NIBBITS_WEAK", "monster", sim.game).combat_state.energy
        assert boosted == base + extra and again == base
