"""The relic grab bag and what a relic does on pickup."""
import random

from sts2_lite.event import CardPicker, card_entry
from sts2_lite.event.core import Ctx
from sts2_lite.relic.bag import RelicGrabBag, RELIC_INFO
from sts2_lite.relic.pickup import obtain_relic
from sts2_lite.run import new_run


def ctx_with_bag(seed=0, ascension=0):
    run = new_run(ascension)
    run.act, run.floor = 1, 5
    run.hidden.relic_bag = RelicGrabBag(random.Random(seed))
    return Ctx(run, random.Random(seed), CardPicker(random.Random(seed)))


def test_drawn_relics_are_distinct_and_never_the_starter():
    c = ctx_with_bag()
    got = [obtain_relic(c) for _ in range(40)]
    assert len(set(got)) == len(got) and "BURNING_BLOOD" not in got[1:]


def test_bag_is_deterministic_per_seed():
    a, b = ctx_with_bag(3), ctx_with_bag(3)
    assert [obtain_relic(a) for _ in range(10)] == [obtain_relic(b) for _ in range(10)]


def test_stat_pickups():
    c = ctx_with_bag()
    c.run.hp = 40
    obtain_relic(c, "STRAWBERRY")
    assert c.run.max_hp == 87 and c.run.hp == 47
    obtain_relic(c, "LEES_WAFFLE")
    assert c.run.max_hp == 94 and c.run.hp == 94
    g = c.run.gold
    obtain_relic(c, "OLD_COIN")
    assert c.run.gold == g + 300
    slots = c.run.potion_slots
    obtain_relic(c, "POTION_BELT")
    assert c.run.potion_slots == slots + 2


def test_war_paint_and_whetstone_upgrade_two():
    c = ctx_with_bag()
    c.run.deck += [card_entry("BODY_SLAM"), card_entry("ARMAMENTS")]
    obtain_relic(c, "WHETSTONE")
    assert sum(1 for x in c.run.deck if x.get("type") == "Attack" and x.get("is_upgraded")) == 2


def test_orrery_queues_five_card_screens_and_cauldron_five_potions():
    c = ctx_with_bag()
    obtain_relic(c, "ORRERY")
    obtain_relic(c, "CAULDRON")
    assert [o["kind"] for o in c.run.offers].count("cards") == 5 and [o["kind"] for o in c.run.offers].count("potion") == 5
    assert all(len(o["cards"]) == 3 for o in c.run.offers if o["kind"] == "cards")


def test_enchanting_relics_enchant_three_cards():
    c = ctx_with_bag()
    obtain_relic(c, "GNARLED_HAMMER")
    assert sum(1 for x in c.run.deck if x.get("enchantment")) == 3


def test_cursed_pearl_and_cape():
    c = ctx_with_bag()
    n = len(c.run.deck)
    obtain_relic(c, "CURSED_PEARL")
    obtain_relic(c, "DISTINGUISHED_CAPE")
    assert len(c.run.deck) == n + 4 and c.run.max_hp == 80 - 9


def test_early_only_relics_leave_the_bag_late():
    c = ctx_with_bag()
    c.run.floor = 45
    early = {r for r, i in RELIC_INFO.items() if i["early_only"]}
    got = {obtain_relic(c) for _ in range(60)}
    assert not (got & early)


def test_swift_on_a_card_that_picks_from_the_draw_pile_draws_after_the_pick():
    """Secret Weapon with Swift: the draw must not move the pile under the choice that is still open."""
    from sts2_lite.card import Card, CardId, EnchantmentId
    from sts2_lite.run import GameRng
    from sandbox.combat import start_fight
    from sts2_lite.encounters import ENCOUNTERS
    run = new_run(0)
    run.deck = [card_entry("SECRET_WEAPON")] + [card_entry("STRIKE_IRONCLAD") for _ in range(12)] + [card_entry("BASH")]
    run.deck[0] = dict(run.deck[0], enchantment={"id": "SWIFT", "amount": 1})
    sim = start_fight(run, next(e.id for e in ENCOUNTERS.values() if e.room == "Monster"), "monster", GameRng(0))
    hand = sim.combat_state.player.hand
    while not any(c.card_id == CardId.SECRET_WEAPON for c in hand):          # a hand without it: reshuffle through a new fight
        run.deck.append(card_entry("STRIKE_IRONCLAD"))
        sim = start_fight(run, next(e.id for e in ENCOUNTERS.values() if e.room == "Monster"), "monster", GameRng(len(run.deck)))
        hand = sim.combat_state.player.hand
    play = next(a for a in sim.get_available_actions() if a["action"] == "play_card" and hand[a["card_index"]].card_id == CardId.SECRET_WEAPON)
    sim.perform_action(play)
    actions = sim.get_available_actions()          # must not raise
    assert actions
