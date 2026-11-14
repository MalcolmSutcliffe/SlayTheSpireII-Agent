"""The events whose options only change hit points, gold, the deck, relics and potions. Numbers are the game's (sts2_decompiled/.../Models/Events).

Not modelled yet (they start a fight, trade a relic, or offer something the sim has no model for): the Ancients (Nonupeipe, Pael, Orobas ...), Fake Merchant,
Dense Vegetation, Punch Off, Battleworn Dummy, Round Tea Party's fight, Relic Trader, Ranwid, Endless Conveyor, Crystal Sphere, Trial, Tinker Time. 
`EVENTS` lists what is modelled; an event not in it is left to the agent to play by hand."""
from __future__ import annotations

from sts2_lite.event.core import Ctx, EventDef, Option, Page
from sts2_lite.event.run import RunSnapshot, can_enchant, is_basic_defend, is_basic_strike, is_curse

EVENTS : dict[str, EventDef] = {}


def event(event_id : str, allowed=lambda run: True, acts=(1, 2, 3)):
    def register(start):
        EVENTS[event_id] = EventDef(event_id, start, allowed, acts)
        return start
    return register


def gold_at_least(n : int):
    return lambda run: run.gold >= n


def roll(c : Ctx, key : str, base : int, low : int, high : int) -> int:
    """base + a whole number in [low, high], rolled once per visit."""
    c.vars[key] = base + c.rng.randint(low, high)
    return c.vars[key]


# --- hit points -------------------------------------------------------------------------------------------------------------------------------------------

@event("ABYSSAL_BATHS", acts=(1,))
def abyssal_baths(c : Ctx) -> Page:
    c.vars.update(damage=3, lingers=0)

    def immerse(c : Ctx) -> Page:
        c.gain_max_hp(2)
        c.lose_hp(c.vars["damage"])
        c.vars["damage"] += 1
        return after()

    def after() -> Page:
        return [Option("linger", immerse, hp_cost=c.vars["damage"], lethal=c.run.hp <= c.vars["damage"]), Option("exit", lambda c: None)]

    return [Option("immerse", immerse, hp_cost=3), Option("abstain", lambda c: c.heal(10))]


@event("UNREST_SITE", allowed=lambda run: run.hp <= 0.7 * run.max_hp, acts=(1,))
def unrest_site(c : Ctx) -> Page:
    def rest(c : Ctx):
        c.heal_to_full()
        c.add_card("POOR_SLEEP")

    def kill(c : Ctx):
        c.lose_max_hp(8)
        c.gain_relic()
    return [Option("rest", rest), Option("kill", kill)]


@event("SPIRIT_GRAFTER", acts=(2,))
def spirit_grafter(c : Ctx) -> Page:
    def let_it_in(c : Ctx):
        c.heal(25)
        c.add_card("METAMORPHOSIS")

    def reject(c : Ctx):
        c.lose_hp(10)
        c.upgrade_picked(1)
    return [Option("let_it_in", let_it_in), Option("reject", reject, hp_cost=10, lethal=c.run.hp <= 10)]


@event("COLOSSAL_FLOWER", allowed=lambda run: run.hp >= 19, acts=(2,))
def colossal_flower(c : Ctx) -> Page:
    prizes, damage = (35, 75, 135), (5, 6, 7)

    def dig(c : Ctx) -> Page:
        c.lose_hp(damage[c.vars["digs"]])
        c.vars["digs"] += 1
        return page()

    def page() -> Page:
        d = c.vars["digs"]
        if d < 2:
            return [Option("extract", lambda c: c.gain_gold(prizes[d])), Option("reach_deeper", dig, hp_cost=damage[d], lethal=c.run.hp <= damage[d])]
        def core(c : Ctx):
            c.lose_hp(damage[2])
            c.gain_relic("POLLINOUS_CORE", "Pollinous Core")
        return [Option("extract_instead", lambda c: c.gain_gold(prizes[2])), Option("pollinous_core", core, hp_cost=damage[2])]
    c.vars["digs"] = 0
    return page()


@event("DROWNING_BEACON", acts=(1,))
def drowning_beacon(c : Ctx) -> Page:
    def climb(c : Ctx):
        c.lose_max_hp(13)
        c.gain_relic("FRESNEL_LENS", "Fresnel Lens")
    return [Option("bottle", lambda c: c.gain_potion("GLOWWATER_POTION")), Option("climb", climb)]


@event("HUNGRY_FOR_MUSHROOMS", acts=(3,))
def hungry_for_mushrooms(c : Ctx) -> Page:
    def fragrant(c : Ctx):
        c.lose_hp(15)
        c.gain_relic("FRAGRANT_MUSHROOM", "Fragrant Mushroom")
    return [Option("big_mushroom", lambda c: c.gain_relic("BIG_MUSHROOM", "Big Mushroom")), Option("fragrant_mushroom", fragrant, hp_cost=15)]


# --- gold ------------------------------------------------------------------------------------------------------------------------------------------------

@event("SUNKEN_TREASURY", acts=(1,))
def sunken_treasury(c : Ctx) -> Page:
    small, large = roll(c, "small", 60, -8, 7), roll(c, "large", 333, -30, 30)

    def second(c : Ctx):
        c.gain_gold(large)
        c.add_card("GREED")
    return [Option("first_chest", lambda c: c.gain_gold(small)), Option("second_chest", second)]


@event("SUNKEN_STATUE", acts=(1,))
def sunken_statue(c : Ctx) -> Page:
    gold = roll(c, "gold", 111, -10, 10)

    def dive(c : Ctx):
        c.lose_hp(7)
        c.gain_gold(gold)
    return [Option("grab_sword", lambda c: c.gain_relic("SWORD_OF_STONE", "Sword of Stone")), Option("dive", dive, hp_cost=7)]


@event("THIS_OR_THAT")
def this_or_that(c : Ctx) -> Page:
    gold = roll(c, "gold", 0, 41, 68)

    def plain(c : Ctx):
        c.lose_hp(6)
        c.gain_gold(gold)

    def ornate(c : Ctx):
        c.add_card("CLUMSY")
        c.gain_relic()
    return [Option("plain", plain, hp_cost=6), Option("ornate", ornate)]


@event("LOST_WISP", acts=(2,))
def lost_wisp(c : Ctx) -> Page:
    gold = roll(c, "gold", 60, -15, 15)

    def claim(c : Ctx):
        c.add_card("DECAY")
        c.gain_relic("LOST_WISP", "Lost Wisp")
    return [Option("claim", claim), Option("search", lambda c: c.gain_gold(gold))]


@event("WHISPERING_HOLLOW", allowed=gold_at_least(44), acts=(1,))
def whispering_hollow(c : Ctx) -> Page:
    cost = roll(c, "cost", 35, -9, 9)

    def gold(c : Ctx):
        c.lose_gold(cost)
        c.gain_potion()
        c.gain_potion()

    def hug(c : Ctx):
        c.lose_hp(9)
        c.transform(1)
    return [Option("gold", gold, locked=c.run.gold < cost), Option("hug", hug, hp_cost=9)]


# --- the deck --------------------------------------------------------------------------------------------------------------------------------------------

@event("AMALGAMATOR", allowed=lambda run: sum(map(is_basic_strike, run.deck)) >= 2 and sum(map(is_basic_defend, run.deck)) >= 2, acts=(2,))
def amalgamator(c : Ctx) -> Page:
    def strikes(c : Ctx):
        c.remove_cards(2, is_basic_strike)
        c.add_card("ULTIMATE_STRIKE")

    def defends(c : Ctx):
        c.remove_cards(2, is_basic_defend)
        c.add_card("ULTIMATE_DEFEND")
    return [Option("combine_strikes", strikes), Option("combine_defends", defends)]


@event("AROMA_OF_CHAOS", acts=(1,))
def aroma_of_chaos(c : Ctx) -> Page:
    return [Option("let_go", lambda c: c.transform(1)), Option("maintain_control", lambda c: c.upgrade_picked(1))]


@event("BUGSLAYER", acts=(2,))
def bugslayer(c : Ctx) -> Page:
    return [Option("extermination", lambda c: c.add_card("EXTERMINATE")), Option("squash", lambda c: c.add_card("SQUASH"))]


@event("BRAIN_LEECH", acts=(1, 2))
def brain_leech(c : Ctx) -> Page:
    def share(c : Ctx):
        c.pick_from_offer(c.reward_cards(5), 1)

    def rip(c : Ctx):
        c.lose_hp(5)
        c.pick_from_offer(c.reward_cards(3, colorless=True), 1)
    return [Option("share_knowledge", share), Option("rip", rip, hp_cost=5, lethal=c.run.hp <= 5)]


@event("DOORS_OF_LIGHT_AND_DARK", acts=(1,))
def doors(c : Ctx) -> Page:
    return [Option("light", lambda c: c.upgrade_random(2)), Option("dark", lambda c: c.remove_cards(1))]


@event("LUMINOUS_CHOIR", allowed=gold_at_least(149), acts=(1,))
def luminous_choir(c : Ctx) -> Page:
    cost = 149 - c.rng.randint(0, 49)
    c.vars["cost"] = cost

    def reach(c : Ctx):
        c.remove_cards(2)
        c.add_card("SPORE_MIND")

    def tribute(c : Ctx):
        c.lose_gold(cost)
        c.gain_relic()
    return [Option("reach_into_the_flesh", reach), Option("offer_tribute", tribute, locked=c.run.gold < cost)]


@event("MORPHIC_GROVE", allowed=lambda run: run.gold >= 100 and sum(not is_curse(x) for x in run.deck) >= 2, acts=(1,))
def morphic_grove(c : Ctx) -> Page:
    def group(c : Ctx):
        c.lose_gold(c.run.gold)
        c.transform(2)
    return [Option("group", group), Option("loner", lambda c: c.gain_max_hp(5))]


@event("ROOM_FULL_OF_CHEESE", acts=(1, 2))
def room_full_of_cheese(c : Ctx) -> Page:
    def search(c : Ctx):
        c.lose_hp(14)
        c.gain_relic("CHOSEN_CHEESE", "Chosen Cheese")
    return [Option("gorge", lambda c: c.pick_from_offer(c.reward_cards(8), 2)), Option("search", search, hp_cost=14, lethal=c.run.hp <= 14)]


@event("WELLSPRING", acts=(1,))
def wellspring(c : Ctx) -> Page:
    def bathe(c : Ctx):
        c.remove_cards(1)
        c.add_card("GUILTY")
    return [Option("bottle", lambda c: c.gain_potion()), Option("bathe", bathe)]


@event("ZEN_WEAVER", allowed=gold_at_least(125), acts=(2,))
def zen_weaver(c : Ctx) -> Page:
    def breathing(c : Ctx):
        c.lose_gold(50)
        c.add_card("ENLIGHTENMENT")
        c.add_card("ENLIGHTENMENT")

    def removal(cost : int, n : int):
        def apply(c : Ctx):
            c.remove_cards(n)
            c.lose_gold(cost)
        return apply
    return [Option("breathing_techniques", breathing), Option("emotional_awareness", removal(125, 1), locked=c.run.gold < 125),
            Option("arachnid_acupuncture", removal(250, 2), locked=c.run.gold < 250)]


@event("SLIPPERY_BRIDGE", allowed=lambda run: run.floor > 6 and any(c.get("removable") is not False for c in run.deck))
def slippery_bridge(c : Ctx) -> Page:
    c.vars["holds"] = 0

    c.vars["skipped"] = set()

    def draw_card() -> int | None:
        """The first card is never a Basic one; after that any removable card of a different kind than the last, not one already passed over."""
        removable = [i for i, x in enumerate(c.run.deck) if x.get("removable") is not False]
        last = c.vars.get("lose")
        if last is None:
            pool = [i for i in removable if c.run.deck[i].get("rarity") != "Basic"]
        else:
            c.vars["skipped"].add(last)
            pool = [i for i in removable if i not in c.vars["skipped"] and c.run.deck[i]["id"] != c.run.deck[last]["id"]]
        pool = pool or removable
        return c.rng.choice(pool) if pool else None

    def page() -> Page:
        c.vars["lose"] = draw_card()
        loss = 3 + c.vars["holds"]
        return [Option("overcome", overcome), Option("hold_on", hold, hp_cost=loss, lethal=c.run.hp <= loss)]

    def overcome(c : Ctx):
        if c.vars["lose"] is not None:
            c.run.deck.pop(c.vars["lose"])

    def hold(c : Ctx) -> Page:
        c.lose_hp(3 + c.vars["holds"])
        c.vars["holds"] += 1
        return page()
    return page()


@event("REFLECTIONS", acts=(3,))
def reflections(c : Ctx) -> Page:
    def touch(c : Ctx):
        upgraded = [i for i, x in enumerate(c.run.deck) if x.get("is_upgraded")]
        for i in c.rng.sample(upgraded, min(2, len(upgraded))):
            c.run.deck[i] = {k: v for k, v in c.run.deck[i].items() if k != "_upgrade"} | {"is_upgraded": False}
        c.upgrade_random(4)

    def shatter(c : Ctx):
        c.run.deck.extend(dict(x) for x in list(c.run.deck))
        c.add_card("BAD_LUCK")
    return [Option("touch_a_mirror", touch), Option("shatter", shatter)]


# --- enchantments ----------------------------------------------------------------------------------------------------------------------------------------

def any_enchantable(enchantment : str, card_type : str | None = None):
    return lambda run: any(can_enchant(x, enchantment, card_type) for x in run.deck)


@event("FIELD_OF_MAN_SIZED_HOLES", allowed=any_enchantable("PERFECT_FIT"), acts=(2,))
def field_of_man_sized_holes(c : Ctx) -> Page:
    def resist(c : Ctx):
        c.remove_cards(2)
        c.add_card("NORMALITY")
    return [Option("resist", resist), Option("enter_your_hole", lambda c: c.enchant("PERFECT_FIT", 1))]


@event("GRAVE_OF_THE_FORGOTTEN", allowed=any_enchantable("SOULS_POWER"), acts=(3,))
def grave_of_the_forgotten(c : Ctx) -> Page:
    def confront(c : Ctx):
        c.add_card("DECAY")
        c.enchant("SOULS_POWER", 1)
    return [Option("confront", confront), Option("accept", lambda c: c.gain_relic("FORGOTTEN_SOUL", "Forgotten Soul"))]


@event("SAPPHIRE_SEED", acts=(1,))
def sapphire_seed(c : Ctx) -> Page:
    def eat(c : Ctx):
        c.heal(9)
        c.upgrade_picked(1)
    return [Option("eat", eat), Option("plant", lambda c: c.enchant("SOWN", 1), locked=not any_enchantable("SOWN")(c.run))]


@event("SPIRALING_WHIRLPOOL", allowed=any_enchantable("SPIRAL"), acts=(1,))
def spiraling_whirlpool(c : Ctx) -> Page:
    return [Option("observe_the_spiral", lambda c: c.enchant("SPIRAL", 1)), Option("drink", lambda c: c.heal(int(c.run.max_hp * 0.33)))]


@event("SYMBIOTE", acts=(2, 3))
def symbiote(c : Ctx) -> Page:
    return [Option("approach", lambda c: c.enchant("CORRUPTED", 1), locked=not any_enchantable("CORRUPTED")(c.run)), Option("kill_with_fire", lambda c: c.transform(1))]


@event("WOOD_CARVINGS", allowed=lambda run: any(x.get("rarity") == "Basic" and x.get("removable") is not False for x in run.deck), acts=(1,))
def wood_carvings(c : Ctx) -> Page:
    def basic(card_id : str):
        def apply(c : Ctx):
            c.transform_into(card_id, lambda x: x.get("rarity") == "Basic")
        return apply
    return [Option("bird", basic("PECK")), Option("snake", lambda c: c.enchant("SLITHER", 1), locked=not any_enchantable("SLITHER")(c.run)), Option("torus", basic("TORIC_TOUGHNESS"))]


@event("SELF_HELP_BOOK")
def self_help_book(c : Ctx) -> Page:
    books = [("read_the_back", "SHARP", "Attack"), ("read_passage", "NIMBLE", "Skill"), ("read_entire_book", "SWIFT", "Power")]
    page = [Option(key, (lambda e, t: lambda c: c.enchant(e, 2, t))(ench, ctype), locked=not any_enchantable(ench, ctype)(c.run)) for key, ench, ctype in books]
    return page if any(not o.locked for o in page) else [Option("no_options", lambda c: None)]


def modelled() -> list[str]:
    return sorted(EVENTS)


def available(run : RunSnapshot, act : int | None = None) -> list[EventDef]:
    """The modelled events the run could meet right now (the game's own IsAllowed and act)."""
    act = act or run.act
    return [e for e in EVENTS.values() if act in e.acts and e.allowed(run)]
