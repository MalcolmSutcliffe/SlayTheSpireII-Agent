"""The events whose options only change hit points, gold, the deck, relics and potions. Numbers are the game's (sts2_decompiled/.../Models/Events).

Not modelled yet (they start a fight, trade a relic, or offer something the sim has no model for): the Ancients (Nonupeipe, Pael, Orobas ...), Fake Merchant,
Dense Vegetation, Punch Off, Battleworn Dummy, Round Tea Party's fight, Relic Trader, Ranwid, Endless Conveyor, Crystal Sphere, Trial, Tinker Time. 
`EVENTS` lists what is modelled; an event not in it is left to the agent to play by hand."""
from __future__ import annotations

from sts2_lite.event.core import Ctx, EventDef, Option, Page
from sts2_lite.event.run import RunSnapshot, can_enchant, can_upgrade, is_basic_defend, is_basic_strike, is_curse

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


# --- more events: HP, gold, relics, potions and cards the engine has --------------------------------------------------------------------------------------

@event("JUNGLE_MAZE_ADVENTURE", acts=(1,))
def jungle_maze_adventure(c : Ctx) -> Page:
    solo, joint = int(150 + c.rng.uniform(-15, 15)), int(50 + c.rng.uniform(-15, 15))

    def solo_quest(c : Ctx):
        c.lose_hp(18)
        c.gain_gold(solo)
    return [Option("solo_quest", solo_quest, hp_cost=18, lethal=c.run.hp <= 18), Option("join_forces", lambda c: c.gain_gold(joint))]


@event("TABLET_OF_TRUTH", acts=(1,))
def tablet_of_truth(c : Ctx) -> Page:
    """Decipher costs 3, 6, 12, 24 max HP and then all but 1; each upgrades a random card, the fifth upgrades the whole deck. Smash heals 20."""
    c.vars.update(deciphered=0, cost=3)
    cost_after = {1: lambda run: 6, 2: lambda run: 12, 3: lambda run: 24, 4: lambda run: run.max_hp - 1}

    def decipher(c : Ctx) -> Page | None:
        cost, run = c.vars["cost"], c.run
        if cost >= run.max_hp:
            c.lose_max_hp(run.max_hp - 1)
            run.hp, run.dead = 0, True
            return None
        c.lose_max_hp(cost)
        if c.vars["deciphered"] == 4:
            for i in [i for i, x in enumerate(run.deck) if can_upgrade(x)]:
                c.upgrade_at(i)
        else:
            c.upgrade_random(1)
        c.vars["deciphered"] += 1
        if c.vars["deciphered"] == 5:
            return None
        c.vars["cost"] = cost_after[c.vars["deciphered"]](run)
        return page(True)

    def page(again : bool) -> Page:
        cost = c.vars["cost"]
        options = [Option("decipher", decipher, lethal=c.run.max_hp <= cost)]
        return options + [Option("give_up", lambda c: None)] if again else options + [Option("smash", lambda c: c.heal(20))]
    return page(False)


TRASH_HEAP_RELICS = ("DARKSTONE_PERIAPT", "DREAM_CATCHER", "HAND_DRILL", "MAW_BANK", "THE_BOOT")
TRASH_HEAP_CARDS = ("CALTROPS", "CLASH", "DISTRACTION", "DUAL_WIELD", "ENTRENCH", "HELLO_WORLD", "OUTMANEUVER", "REBOUND", "RIP_AND_TEAR", "STACK")


@event("TRASH_HEAP", allowed=lambda run: run.hp > 5, acts=(1,))
def trash_heap(c : Ctx) -> Page:
    """Dive in: 8 HP for one of five relics. Grab: 100 gold and one of ten cards (one of ten event cards, all playable)."""
    def dive_in(c : Ctx):
        c.lose_hp(8)
        c.gain_relic(c.rng.choice(TRASH_HEAP_RELICS))

    def grab(c : Ctx):
        c.gain_gold(100)
        c.add_card(c.rng.choice(TRASH_HEAP_CARDS))
    return [Option("dive_in", dive_in, hp_cost=8, lethal=c.run.hp <= 8), Option("grab", grab)]


@event("WATERLOGGED_SCRIPTORIUM", allowed=gold_at_least(55), acts=(1,))
def waterlogged_scriptorium(c : Ctx) -> Page:
    def quill(c : Ctx):
        c.lose_gold(55)
        c.enchant("STEADY", 1)

    def sponge(c : Ctx):
        c.lose_gold(99)
        c.enchant("STEADY", 1, count=2)
    return [Option("bloody_ink", lambda c: c.gain_max_hp(6)), Option("tentacle_quill", quill), Option("prickly_sponge", sponge, locked=c.run.gold < 99)]


@event("INFESTED_AUTOMATON", acts=(2,))
def infested_automaton(c : Ctx) -> Page:
    return [Option("study", lambda c: c.add_pool_card(lambda x: x["type"] == "Power")),
            Option("touch_core", lambda c: c.add_pool_card(lambda x: x["cost"] == 0))]


@event("POTION_COURIER", allowed=lambda run: run.act > 1, acts=(2, 3))
def potion_courier(c : Ctx) -> Page:
    from sts2_lite.potion import POTION_INFO, PotionRarity
    from sts2_lite.potion_pool import potion_pool

    def grab_potions(c : Ctx):
        for _ in range(3):
            c.gain_potion("FOUL_POTION")

    def ransack(c : Ctx):
        c.gain_potion(c.rng.choice([p for p in potion_pool(c.run.character) if POTION_INFO[p].rarity == PotionRarity.UNCOMMON]).name)
    return [Option("grab_potions", grab_potions), Option("ransack", ransack)]


@event("TEA_MASTER", allowed=lambda run: run.act < 3 and run.gold >= 150, acts=(1, 2))
def tea_master(c : Ctx) -> Page:
    def buy(relic : str, cost : int):
        def apply(c : Ctx):
            c.lose_gold(cost)
            c.gain_relic(relic)
        return apply
    return [Option("bone_tea", buy("BONE_TEA", 50), locked=c.run.gold < 50), Option("ember_tea", buy("EMBER_TEA", 150), locked=c.run.gold < 150),
            Option("tea_of_discourtesy", lambda c: c.gain_relic("TEA_OF_DISCOURTESY"))]


@event("THE_LEGENDS_WERE_TRUE", allowed=lambda run: run.act == 1 and run.hp >= 10 and len(run.deck) > 0, acts=(1,))
def the_legends_were_true(c : Ctx) -> Page:
    """Nab the map: the Spoils Map quest card (600 gold at the act 2 treasure). Slowly find an exit: 8 HP and a random potion."""
    from sts2_lite.potion_pool import potion_pool

    def exit_slowly(c : Ctx):
        c.lose_hp(8)
        c.gain_potion(c.rng.choice(potion_pool(c.run.character)).name)
    return [Option("nab_the_map", lambda c: c.add_placeholder("SPOILS_MAP", "Spoils Map", "Quest")), Option("slowly_find_an_exit", exit_slowly, hp_cost=8, lethal=c.run.hp <= 8)]


@event("THE_LANTERN_KEY", acts=(2,))
def the_lantern_key(c : Ctx) -> Page:
    """Return the key: 100 gold. Keep it: fight the Mysterious Knight for the Lantern Key quest card (it turns act 3's "?" rooms into War Historian Repy)."""
    def keep(c : Ctx) -> Page:
        return [Option("fight", lambda c: c.start_fight("MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER", on_win="lantern_key"))]
    return [Option("return_the_key", lambda c: c.gain_gold(100)), Option("keep_the_key", keep)]


def _keys(c : Ctx) -> int:
    return sum(card["id"] == "LANTERN_KEY" for card in c.run.deck)


def _remove_keys(c : Ctx, every : bool):
    """WarHistorianRepy.RemoveFirstLanternKey / RemoveLanternKeysForSecondChoice (the quest is completed)."""
    keys = [i for i, card in enumerate(c.run.deck) if card["id"] == "LANTERN_KEY"]
    for i in sorted(keys if every else keys[:1], reverse=True):
        c.run.deck.pop(i)


@event("WAR_HISTORIAN_REPY", allowed=lambda run: False)
def war_historian_repy(c : Ctx) -> Page:
    """Only the Lantern Key leads here. Unlock the cage: the History Course relic. Unlock the chest: two potions and two relics. With a second key (single player) the other one too."""
    def cage(c : Ctx):
        c.gain_relic("HISTORY_COURSE")

    def chest(c : Ctx):
        c.gain_potion()
        c.gain_potion()
        c.gain_relic()
        c.gain_relic()

    def first(do, other_key : str, other):
        def apply(c : Ctx) -> Page | None:
            _remove_keys(c, False)
            do(c)
            if _keys(c):                 # ShouldGetSecondReward: a key is still held
                def second(c : Ctx):
                    _remove_keys(c, True)
                    other(c)
                return [Option(other_key, second)]
            return None
        return apply
    return [Option("unlock_cage", first(cage, "unlock_chest", chest)), Option("unlock_chest", first(chest, "unlock_cage", cage))]


@event("BYRDONIS_NEST", allowed=lambda run: not run.has_relic("BYRDPIP"), acts=(1,))
def byrdonis_nest(c : Ctx) -> Page:
    """Eat the eggs: 7 max HP. Take one: the Byrdonis Egg quest card, hatched at a rest site into Byrdpip (the egg becomes a Byrd Swoop)."""
    return [Option("eat", lambda c: c.gain_max_hp(7)), Option("take", lambda c: c.add_placeholder("BYRDONIS_EGG", "Byrdonis Egg", "Quest"))]


@event("DOLL_ROOM", allowed=lambda run: run.act == 2, acts=(2,))
def doll_room(c : Ctx) -> Page:
    dolls = ["DAUGHTER_OF_THE_WIND", "MR_STRUGGLES", "BING_BONG"]

    def take(doll : str):
        return lambda c: c.gain_relic(doll)

    def random_doll(c : Ctx):
        c.gain_relic(c.rng.choice(dolls))

    def choose(cost : int, n : int):
        def apply(c : Ctx) -> Page:
            c.lose_hp(cost)
            shuffled = list(dolls)
            c.rng.shuffle(shuffled)
            return [Option(d.lower(), take(d)) for d in shuffled[:n]]
        return apply
    return [Option("random", random_doll), Option("take_some_time", choose(5, 2), hp_cost=5), Option("examine", choose(15, 3), hp_cost=15)]


WONGOS_BARGAIN, WONGOS_FEATURED, WONGOS_MYSTERY = 100, 200, 300


@event("WELCOME_TO_WONGOS", allowed=lambda run: run.act == 2 and run.gold >= 100, acts=(2,))
def welcome_to_wongos(c : Ctx) -> Page:
    """A rare relic from the front of the bag (200), a common one (100), a Wongo's Mystery Ticket (300). Leaving downgrades an upgraded card. The Wongo badge points are not modelled."""
    def featured(c : Ctx):
        c.lose_gold(WONGOS_FEATURED)
        _obtain_pulled(c, "Rare")

    def bargain(c : Ctx):
        c.lose_gold(WONGOS_BARGAIN)
        _obtain_pulled(c, "Common")

    def mystery(c : Ctx):
        c.lose_gold(WONGOS_MYSTERY)
        c.gain_relic("WONGOS_MYSTERY_TICKET")

    def leave(c : Ctx):
        upgraded = [i for i, x in enumerate(c.run.deck) if x.get("is_upgraded")]
        if upgraded:
            i = c.rng.choice(upgraded)
            c.run.deck[i] = dict(c.run.deck[i], is_upgraded=False, _upgrade=False)
    return [Option("bargain_bin", bargain, locked=c.run.gold < WONGOS_BARGAIN), Option("featured_item", featured, locked=c.run.gold < WONGOS_FEATURED),
            Option("mystery_box", mystery, locked=c.run.gold < WONGOS_MYSTERY), Option("leave", leave)]


def _obtain_pulled(c : Ctx, rarity : str):
    """A relic of `rarity` from the front of the bag that shops may sell (a run without a bag counts it as pending)."""
    from sts2_lite.relic.pickup import obtain_relic
    if getattr(c.run.hidden, "relic_bag", None) is None:
        c.run.pending_relics += 1
    else:
        obtain_relic(c, None, None, rarity=rarity)


@event("CRYSTAL_SPHERE", allowed=lambda run: run.act >= 2 and run.gold >= 100, acts=(2, 3))
def crystal_sphere(c : Ctx) -> Page:
    """A divination minigame (the game plays it on a grid the bridge cannot show). Mimicked: the real costs (50 gold plus 1-50, or the Debt curse) and a
    random outcome for each of its 3 (6) reveals. The real reward table is not in the decompile, so the outcomes are an approximation."""
    cost = 50 + c.rng.randint(1, 50)

    def reveals(c : Ctx, n : int):
        for _ in range(n):
            roll = c.rng.random()
            if roll < 0.35:
                c.gain_gold(c.rng.randint(15, 45))
            elif roll < 0.6:
                c.gain_potion()
            elif roll < 0.85:
                c.pick_from_offer(c.reward_cards(3), 1)
            else:
                c.gain_relic()

    def uncover(c : Ctx):
        c.lose_gold(cost)
        reveals(c, 3)

    def payment_plan(c : Ctx):
        c.add_card("DEBT")
        reveals(c, 6)
    return [Option("uncover_future", uncover, locked=c.run.gold < cost), Option("payment_plan", payment_plan)]


ENDLESS_CONVEYOR_DISHES = (("CAVIAR", 6), ("SPICY_SNAPPY", 3), ("JELLY_LIVER", 3), ("FRIED_EEL", 3))
CONVEYOR_PRICE = 40


@event("ENDLESS_CONVEYOR", allowed=gold_at_least(120), acts=(1,))
def endless_conveyor(c : Ctx) -> Page:
    """Sushi belt: each dish costs 40 gold (the Golden Fysh pays 75), the next one is rolled after every grab, and every fifth is Seapunk Salad (Feeding Frenzy)."""
    c.vars.setdefault("grabs", 0)

    def roll(c : Ctx) -> str:
        c.vars["grabs"] += 1
        if c.vars["grabs"] % 5 == 0:
            c.vars["last"] = "SEAPUNK_SALAD"
            return "SEAPUNK_SALAD"
        dishes = list(ENDLESS_CONVEYOR_DISHES)
        if len(c.run.potions) < c.run.potion_slots:
            dishes.append(("SUSPICIOUS_CONDIMENT", 3))
        if c.run.hp != c.run.max_hp:
            dishes.append(("CLAM_ROLL", 6))
        if c.vars["grabs"] > 1:
            dishes.append(("GOLDEN_FYSH", 1))
        dishes = [d for d in dishes if d[0] != c.vars.get("last", "")]
        roll_ = c.rng.random() * sum(w for _, w in dishes)
        acc = 0.0
        for dish, w in dishes:
            acc += w
            if roll_ < acc:
                c.vars["last"] = dish
                return dish
        c.vars["last"] = dishes[-1][0]
        return dishes[-1][0]

    def eat(c : Ctx, dish : str):
        if dish == "CAVIAR":
            c.gain_max_hp(4)
        elif dish == "SPICY_SNAPPY":
            c.upgrade_random(1)
        elif dish == "JELLY_LIVER":
            c.transform(1)
        elif dish == "FRIED_EEL":
            c.add_card(c.reward_cards(1, colorless=True)[0]["id"])
        elif dish == "SUSPICIOUS_CONDIMENT":
            c.gain_potion()
        elif dish == "CLAM_ROLL":
            c.heal(10)
        elif dish == "GOLDEN_FYSH":
            c.gain_gold(75)
        elif dish == "SEAPUNK_SALAD":
            c.add_card("FEEDING_FRENZY")

    def grab_option(c : Ctx, dish : str) -> Option:
        def apply(c : Ctx) -> Page:
            if dish != "GOLDEN_FYSH":
                c.lose_gold(CONVEYOR_PRICE)
            eat(c, dish)
            nxt = roll(c)
            return [grab_option(c, nxt), Option("leave", lambda c: None)]
        return Option(dish.lower(), apply, locked=c.run.gold < CONVEYOR_PRICE)

    def observe(c : Ctx):
        c.upgrade_random(1)
    return [grab_option(c, roll(c)), Option("observe_chef", observe)]


def _pull(c : Ctx, rarity : str | None = None) -> str | None:
    """A relic from the front of the bag (None when the run has no bag: the caller counts it as pending)."""
    from sts2_lite.relic.bag import pull_relic
    if getattr(c.run.hidden, "relic_bag", None) is None:
        return None
    return pull_relic(c.run, rarity)


def _obtain(c : Ctx, relic : str | None):
    from sts2_lite.relic.pickup import obtain_relic
    if relic is None:
        c.run.pending_relics += 1
    else:
        obtain_relic(c, relic)


@event("RELIC_TRADER", allowed=lambda run: run.act > 1 and len(_tradable(run)) >= 5, acts=(2, 3))
def relic_trader(c : Ctx) -> Page:
    """Three of your tradable relics, each offered against one relic pulled from the front of the bag (all three are pulled, only the one traded for is kept)."""
    owned = _tradable(c.run)
    c.rng.shuffle(owned)
    owned = owned[:3]
    new = [_pull(c) for _ in owned]

    def trade(i : int):
        def apply(c : Ctx):
            c.lose_relic(owned[i])
            _obtain(c, new[i])
        return apply
    c.vars["offers"] = list(zip(owned, new))
    return [Option(f"trade_{('top', 'middle', 'bottom')[i]}", trade(i)) for i in range(len(owned))] or [Option("proceed", lambda c: None)]


def _tradable(run) -> list[str]:
    from sts2_lite.relic.pickup import tradable
    return [r["id"] for r in run.relics if tradable(run, r["id"])]


@event("RANWID_THE_ELDER", allowed=lambda run: run.act > 1 and bool(_tradable(run)) and run.gold >= 100 and bool(run.potions), acts=(2, 3))
def ranwid_the_elder(c : Ctx) -> Page:
    """Give a random potion, 100 gold, or a random tradable relic, for a relic from the bag (two for the relic)."""
    def potion(c : Ctx):
        c.discard_potion(c.vars["potion"])
        _obtain(c, _pull(c))

    def gold(c : Ctx):
        c.lose_gold(100)
        _obtain(c, _pull(c))

    def relic(c : Ctx):
        c.lose_relic(c.vars["relic"])
        for _ in range(2):
            _obtain(c, _pull(c))
    options = []
    if c.run.potions:
        c.vars["potion"] = c.rng.randrange(len(c.run.potions))
        options.append(Option("potion", potion))
    else:
        options.append(Option("potion", potion, locked=True))
    options.append(Option("gold", gold))
    tradable = _tradable(c.run)
    if tradable:
        c.vars["relic"] = c.rng.choice(tradable)
        options.append(Option("relic", relic))
    else:
        options.append(Option("relic", relic, locked=True))
    return options


@event("STONE_OF_ALL_TIME", allowed=lambda run: run.act == 2 and bool(run.potions), acts=(2,))
def stone_of_all_time(c : Ctx) -> Page:
    """Lift: drink (lose) a random potion for +10 max HP. Push: 6 HP for Vigorous 8 on an Attack."""
    def lift(c : Ctx):
        c.discard_potion(c.vars["potion"])
        c.gain_max_hp(10)

    def push(c : Ctx):
        c.lose_hp(6)
        c.enchant("VIGOROUS", 8)
    if c.run.potions:
        c.vars["potion"] = c.rng.randrange(len(c.run.potions))
    return [Option("lift", lift, locked=not c.run.potions), Option("push", push, hp_cost=6, locked=not c.enchantable("VIGOROUS"))]


def _potion_rarity(potion : dict) -> str:
    """The card rarity The Future of Potions pays for a potion (Rare / Event: rare, Uncommon: uncommon, Common / Token: common)."""
    from sts2_lite.potion import POTION_INFO, PotionId, PotionRarity
    pid = PotionId.from_game_id(potion.get("id"))
    rarity = POTION_INFO[pid].rarity if pid in POTION_INFO else PotionRarity.COMMON
    if potion.get("id") == "FOUL_POTION":
        return "Rare"        # an Event potion (assumed: the potion classes are not in the decompile)
    return {PotionRarity.RARE: "Rare", PotionRarity.UNCOMMON: "Uncommon"}.get(rarity, "Common")


@event("THE_FUTURE_OF_POTIONS", allowed=lambda run: len(run.potions) >= 2)
def the_future_of_potions(c : Ctx) -> Page:
    """Trade one of your first three potions for 3 upgraded cards of its rarity (a random type, no Power for a common potion): pick one."""
    from sts2_lite.event.run import class_pool_ids, card_entry
    from sts2_lite.relic.run_hooks import add_to_deck

    def trade(i : int, rarity : str, card_type : str):
        def apply(c : Ctx):
            c.discard_potion(i)
            pool = [card_entry(cid) for cid in class_pool_ids(c.run.character)]
            pool = [x for x in pool if x.get("rarity") == rarity and x.get("type") == card_type]
            offered = [dict(x, is_upgraded=True, _upgrade=True) for x in c.rng.sample(pool, min(3, len(pool)))]
            c.pick_from_offer(offered, 1)
        return apply
    options = []
    for i, potion in enumerate(c.run.potions[:3]):
        rarity = _potion_rarity(potion)
        types = ["Attack", "Skill"] + (["Power"] if rarity != "Common" else [])
        options.append(Option(f"potion_{i}", trade(i, rarity, c.rng.choice(types))))
    return options


@event("DENSE_VEGETATION", acts=(1,))
def dense_vegetation(c : Ctx) -> Page:
    """Trudge on: 8 HP (unblockable) for 61-99 gold. Rest: the rest-site heal, then a fight with four Wrigglers."""
    from sts2_lite.relic import run_hooks
    gold = c.rng.randint(61, 99)

    def trudge(c : Ctx):
        c.lose_hp(8)
        c.gain_gold(gold)

    def rest(c : Ctx) -> Page:
        c.heal(run_hooks.rest_heal(c.run))
        run_hooks.rest_healed(c.run)
        return [Option("fight", lambda c: c.start_fight("DENSE_VEGETATION_EVENT_ENCOUNTER"))]
    return [Option("trudge_on", trudge, hp_cost=8), Option("rest", rest)]


@event("PUNCH_OFF", allowed=lambda run: run.floor >= 6, acts=(1,))
def punch_off(c : Ctx) -> Page:
    """Two Punch Constructs fight each other. Nab: an Injury curse and a relic. Take them on: a fight that pays a relic and a potion on top of its usual rewards."""
    def nab(c : Ctx):
        c.add_card("INJURY")
        c.gain_relic()

    def take_them(c : Ctx) -> Page:
        return [Option("fight", lambda c: c.start_fight("PUNCH_OFF_EVENT_ENCOUNTER", extra=[("relic",), ("potion",)]))]
    return [Option("nab", nab), Option("i_can_take_them", take_them)]


DUMMY_TURNS = 3
DUMMY_WINS = {1: "potion", 2: "upgrade_two", 3: "relic"}


@event("BATTLEWORN_DUMMY", acts=(3,))
def battleworn_dummy(c : Ctx) -> Page:
    """Beat a dummy (75, 150 or 300 HP; it does nothing) within 3 turns: a potion, two upgrades or a relic. No reward when the time runs out."""
    def setting(n : int):
        return lambda c: c.start_fight("BATTLEWORN_DUMMY_EVENT_ENCOUNTER", variant=n, turn_limit=DUMMY_TURNS, on_win=DUMMY_WINS[n])
    return [Option(f"setting_{n}", setting(n)) for n in (1, 2, 3)]


@event("ROUND_TEA_PARTY", allowed=lambda run: run.hp >= 12, acts=(3,))
def round_tea_party(c : Ctx) -> Page:
    """Enjoy the tea: Royal Poison and full healing. Pick a fight: 11 HP and a relic."""
    def enjoy(c : Ctx):
        c.gain_relic("ROYAL_POISON")
        c.heal_to_full()

    def pick_fight(c : Ctx) -> Page:
        def go(c : Ctx):
            c.lose_hp(11)
            c.gain_relic()
        return [Option("continue_fight", go, hp_cost=11)]
    return [Option("enjoy_tea", enjoy), Option("pick_fight", pick_fight, hp_cost=11)]


@event("TRIAL", acts=(3,))
def trial(c : Ctx) -> Page:
    """Accept the trial (a random one of three defendants, guilty or innocent) or reject it (then accept, or double down: the run ends)."""
    from sts2_lite.event.run import random_class_cards

    def merchant_guilty(c : Ctx):
        c.add_card("REGRET")
        c.gain_relic()
        c.gain_relic()

    def merchant_innocent(c : Ctx):
        c.add_card("SHAME")
        c.upgrade_picked(2)

    def noble_innocent(c : Ctx):
        c.add_card("REGRET")
        c.gain_gold(300)

    def nondescript_guilty(c : Ctx):
        c.add_card("DOUBT")
        for _ in range(2):
            c.pick_from_offer(random_class_cards(3, c.rng, ascension=c.run.ascension, character=c.run.character), 1)

    def nondescript_innocent(c : Ctx):
        c.add_card("DOUBT")
        c.transform(2)

    def accept(c : Ctx) -> Page:
        return [
            [Option("merchant_guilty", merchant_guilty), Option("merchant_innocent", merchant_innocent)],
            [Option("noble_guilty", lambda c: c.heal(10)), Option("noble_innocent", noble_innocent)],
            [Option("nondescript_guilty", nondescript_guilty), Option("nondescript_innocent", nondescript_innocent)],
        ][c.rng.randrange(3)]

    def reject(c : Ctx) -> Page:
        return [Option("accept", accept), Option("double_down", lambda c: c.lose_hp(c.run.hp), lethal=True)]
    return [Option("accept", accept), Option("reject", reject)]


@event("TINKER_TIME", acts=(3,))
def tinker_time(c : Ctx) -> Page:
    """Build a Mad Science card: a card type (two of three offered), then one of two riders for it."""
    from sts2_lite.card.constants import MAD_SCIENCE_RIDERS
    from sts2_lite.event.run import mad_science_entry
    from sts2_lite.relic.run_hooks import add_to_deck

    def rider_page(card_type : str):
        def apply(c : Ctx) -> Page:
            riders = c.rng.sample(MAD_SCIENCE_RIDERS[card_type], 2)
            return [Option(r.lower(), lambda c, r=r: add_to_deck(c.run, mad_science_entry(card_type, r))) for r in riders]
        return apply

    def type_page(c : Ctx) -> Page:
        return [Option(t.lower(), rider_page(t)) for t in c.rng.sample(["Attack", "Skill", "Power"], 2)]
    return [Option("choose_card_type", type_page)]


FAKE_MERCHANT_RELICS = ("FAKE_ANCHOR", "FAKE_BLOOD_VIAL", "FAKE_HAPPY_FLOWER", "FAKE_LEES_WAFFLE", "FAKE_MANGO", "FAKE_ORICHALCUM", "FAKE_SNECKO_EYE",
                        "FAKE_STRIKE_DUMMY", "FAKE_VENERABLE_TEA_SET")
FAKE_MERCHANT_PRICE, FAKE_MERCHANT_STOCK = 50, 6


@event("FAKE_MERCHANT", allowed=lambda run: run.gold >= 100 or any(p.get("id") == "FOUL_POTION" for p in getattr(run, "potions", ())), acts=(2, 3))
def fake_merchant(c : Ctx) -> Page:
    """A shop of fake relics (50 gold each). The simulator plays it as a shop (`RunSimulator.fake_merchant`); the fight a thrown Foul Potion starts is not modelled."""
    return []


def modelled() -> list[str]:
    return sorted(EVENTS)


def available(run : RunSnapshot, act : int | None = None) -> list[EventDef]:
    """The modelled events the run could meet right now (the game's own IsAllowed and act)."""
    act = act or run.act
    return [e for e in EVENTS.values() if act in e.acts and e.allowed(run)]
