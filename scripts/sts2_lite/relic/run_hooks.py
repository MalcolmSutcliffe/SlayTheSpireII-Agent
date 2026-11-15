"""What relics do to the run around the fights: gold, rewards, card offers, rest sites, "?" rooms, shop prices, room entry, cards joining the deck.

Each function takes the `RunState` and answers or changes it; the simulator calls them at the matching moments (the names follow the game's hooks). Counters a relic
keeps (`CombatsFinished`, `HasTriggered`, ...) live in `run.relic_state[relic_id]`.

Rounding the decompile does not show (Bowler Hat's 1.25, the shop discounts) is truncated toward zero: marked as assumed in unimplemented_features.md."""
from __future__ import annotations

from sts2_lite.event.run import can_enchant, can_upgrade, enchanted

REST_HEAL_SHARE = 0.30
COMBAT_ROOMS = ("Monster", "Elite", "Boss")
EGG_TYPES = {"MOLTEN_EGG": "Attack", "TOXIC_EGG": "Skill", "FROZEN_EGG": "Power"}


def state(run, relic_id : str) -> dict:
    return run.relic_state.setdefault(relic_id, {})


def _heal(run, n : int):
    run.hp = min(run.max_hp, run.hp + max(0, n))


def _upgraded(card : dict) -> dict:
    return dict(card, is_upgraded=True, _upgrade=True)


# --- gold ------------------------------------------------------------------------------------------------------------------------------------------------

def gain_gold(run, amount : int) -> int:
    """PlayerCmd.GainGold: Bowler Hat first, then After-gold relics (Dragon Fruit). Returns what was added."""
    if amount <= 0:
        return 0
    if run.has_relic("BOWLER_HAT"):
        amount = int(amount * 1.25)
    run.gold += amount
    if run.has_relic("DRAGON_FRUIT"):
        run.max_hp += 1
        run.hp += 1
    return amount


# --- rewards ---------------------------------------------------------------------------------------------------------------------------------------------

def reward_extras(run, room : str, last_act_boss : bool = False) -> list[tuple]:
    """TryModifyRewards: what relics add to the rewards of a combat room, as ("gold", n) / ("relic",) / ("cards", room_for_odds). Counts the fight for Wongo's Mystery Ticket."""
    extras : list[tuple] = []
    if room not in COMBAT_ROOMS:
        return extras
    if run.has_relic("AMETHYST_AUBERGINE") and not (room == "Boss" and last_act_boss):
        extras.append(("gold", 15))
    if run.has_relic("BLACK_STAR") and room == "Elite":
        extras.append(("relic",))
    if run.has_relic("LAVA_ROCK") and room == "Boss" and run.act == 1 and not state(run, "LAVA_ROCK").get("triggered"):
        state(run, "LAVA_ROCK")["triggered"] = True
        extras += [("relic",)] * 2
    if run.has_relic("PRAYER_WHEEL") and room == "Monster":
        extras.append(("cards", "Monster"))
    if run.has_relic("WHITE_STAR") and room == "Elite":
        extras.append(("cards", "Boss"))
    if run.has_relic("WONGOS_MYSTERY_TICKET"):
        s = state(run, "WONGOS_MYSTERY_TICKET")
        s["combats"] = s.get("combats", 0) + 1
        if s["combats"] >= 5 and not s.get("gave"):
            s["gave"] = True
            extras += [("relic",)] * 3
    return extras


def forces_potion_reward(run, room : str) -> bool:
    return room in COMBAT_ROOMS and run.has_relic("WHITE_BEAST_STATUE")


def candy_adds_power(run) -> bool:
    """Lasting Candy: the card reward of every second combat gets one more option, a Power."""
    if not run.has_relic("LASTING_CANDY"):
        return False
    return state(run, "LASTING_CANDY").get("combats", 0) > 0 and state(run, "LASTING_CANDY")["combats"] % 2 == 0


def combat_finished(run, room : str = "Monster", rng=None, won : bool = True):
    """AfterCombatEnd (and AfterCombatVictory), before the rewards are made."""
    if run.has_relic("LASTING_CANDY"):
        s = state(run, "LASTING_CANDY")
        s["combats"] = s.get("combats", 0) + 1
    if run.has_relic("CHOSEN_CHEESE"):
        run.max_hp += 1
        run.hp += 1
    if run.has_relic("FISHING_ROD") and room == "Monster":
        s = state(run, "FISHING_ROD")
        s["combats"] = s.get("combats", 0) + 1
        if s["combats"] % 3 == 0 and rng is not None:
            allowed = [i for i, c in enumerate(run.deck) if can_upgrade(c)]
            if allowed:
                i = rng.choice(allowed)
                run.deck[i] = _upgraded(run.deck[i])
    if run.has_relic("PAELS_TOOTH") and won and state(run, "PAELS_TOOTH").get("cards") and rng is not None:
        stored = state(run, "PAELS_TOOTH")["cards"]
        card = stored.pop(rng.randrange(len(stored)))
        add_to_deck(run, _upgraded(card) if can_upgrade(card) else card)
    if run.has_relic("WAR_HAMMER") and room == "Elite" and won and rng is not None:
        allowed = [i for i, c in enumerate(run.deck) if can_upgrade(c)]
        rng.shuffle(allowed)
        for i in allowed[:4]:
            run.deck[i] = _upgraded(run.deck[i])
    if run.has_relic("TOY_BOX"):
        s = state(run, "TOY_BOX")
        s["combats"] = s.get("combats", 0) + 1
        if s["combats"] % 3 == 0 and s["combats"] <= 12:
            for relic in run.relics:
                if relic.get("wax") and not relic.get("melted"):
                    relic["melted"] = True
                    break
    if run.has_relic("SWORD_OF_STONE") and room == "Elite" and won:
        s = state(run, "SWORD_OF_STONE")
        s["elites"] = s.get("elites", 0) + 1
        if s["elites"] >= 5:
            for relic in run.relics:
                if relic["id"] == "SWORD_OF_STONE":
                    relic["id"], relic["name"] = "SWORD_OF_JADE", "Sword of Jade"


def modify_card_offers(run, cards : list[dict], rng, in_combat_room : bool, took_damage : bool = True, is_reward : bool = True) -> list[dict]:
    """TryModifyCardRewardOptions(Late) on a card reward's cards (deck entries): the eggs upgrade their type, Lava Lamp upgrades all after a hit-free fight, Wing Charm
    makes one card Swift, Fresnel Lens makes every valid card Nimble."""
    cards = list(cards)
    for relic, kind in EGG_TYPES.items():
        if run.has_relic(relic):
            cards = [_upgraded(c) if c.get("type") == kind and can_upgrade(c) else c for c in cards]
    if run.has_relic("LAVA_LAMP") and in_combat_room and not took_damage:
        cards = [_upgraded(c) if can_upgrade(c) else c for c in cards]
    if run.has_relic("WING_CHARM"):
        valid = [i for i, c in enumerate(cards) if can_enchant(c, "SWIFT")]
        if valid:
            i = rng.choice(valid)
            cards[i] = enchanted(cards[i], "SWIFT", 1)
    if run.has_relic("FRESNEL_LENS"):
        cards = [enchanted(c, "NIMBLE", 2) if can_enchant(c, "NIMBLE") else c for c in cards]
    if is_reward and run.has_relic("SILKEN_TRESS") and not state(run, "SILKEN_TRESS").get("used"):
        cards = [enchanted(c, "GLAM", 1) if can_enchant(c, "GLAM") else c for c in cards]      # the first card reward only
        state(run, "SILKEN_TRESS")["used"] = True
    if is_reward and run.has_relic("SILVER_CRUCIBLE") and state(run, "SILVER_CRUCIBLE").get("used", 0) < 3:
        cards = [_upgraded(c) if can_upgrade(c) else c for c in cards]           # the first three card rewards come upgraded
        state(run, "SILVER_CRUCIBLE")["used"] = state(run, "SILVER_CRUCIBLE").get("used", 0) + 1
    if run.has_relic("GLITTER"):
        cards = [enchanted(c, "GLAM", 1) if can_enchant(c, "GLAM") else c for c in cards]      # every card reward
    return cards


def modify_added_card(run, card : dict) -> dict:
    """TryModifyCardBeingAddedToDeck: an egg upgrades the card of its type when it joins the deck; Fresnel Lens makes it Nimble."""
    for relic, kind in EGG_TYPES.items():
        if run.has_relic(relic) and card.get("type") == kind and can_upgrade(card):
            card = _upgraded(card)
    if run.has_relic("FRESNEL_LENS") and can_enchant(card, "NIMBLE"):
        card = enchanted(card, "NIMBLE", 2)
    return card


def add_to_deck(run, card : dict, cloned : bool = False) -> dict:
    """A card joins the deck: the egg / Fresnel Lens change first (TryModifyCardBeingAddedToDeck), then AfterCardChangedPiles for Book of Five Rings (every 5th
    card heals 20), Lucky Fysh (15 gold a card), Darkstone Periapt (6 max HP a curse) and Bing Bong (a copy of every card that is not itself a copy)."""
    card = modify_added_card(run, card)
    run.deck.append(card)
    if run.has_relic("BOOK_OF_FIVE_RINGS"):
        s = state(run, "BOOK_OF_FIVE_RINGS")
        s["cards"] = s.get("cards", 0) + 1
        if s["cards"] % 5 == 0:
            _heal(run, 20)
    if run.has_relic("LUCKY_FYSH"):
        gain_gold(run, 15)
    if run.has_relic("DARKSTONE_PERIAPT") and card.get("type") == "Curse":
        run.max_hp += 6
        run.hp += 6
    if run.has_relic("BING_BONG") and not cloned:
        add_to_deck(run, dict(card), cloned=True)
    return card


# --- map ----------------------------------------------------------------------------------------------------------------------------------------------------

def unknown_room_blacklist(run) -> frozenset[str]:
    """ModifyUnknownMapPointRoomTypes: Juzu Bracelet takes the fights out of "?" rooms."""
    return frozenset({"Monster"}) if run.has_relic("JUZU_BRACELET") else frozenset()


def golden_path_act(run) -> bool:
    """Golden Compass: in the act it was taken in every "?" room is an event."""
    return run.has_relic("GOLDEN_COMPASS") and state(run, "GOLDEN_COMPASS").get("act") == run.act


def fur_coat_marked(run, coord) -> bool:
    """Fur Coat: the enemies of a marked fight start with 1 hit point."""
    s = state(run, "FUR_COAT")
    return run.has_relic("FUR_COAT") and s.get("act") == run.act and tuple(coord) in {tuple(c) for c in s.get("marked", ())}


def free_travel(run) -> bool:
    """Winged Boots: any room of the next row can be entered, three times."""
    return run.has_relic("WINGED_BOOTS") and state(run, "WINGED_BOOTS").get("used", 0) < 3


def sacrificed(run):
    """Pael's Wing: a card reward given up; the counter on the relic follows (every second one gives a relic: the simulator draws it)."""
    s = state(run, "PAELS_WING")
    s["sacrificed"] = s.get("sacrificed", 0) + 1
    for relic in run.relics:
        if relic["id"] == "PAELS_WING":
            relic["counter"] = s["sacrificed"] % 2


def traveled(run, was_child : bool):
    if run.has_relic("WINGED_BOOTS") and not was_child:
        s = state(run, "WINGED_BOOTS")
        s["used"] = s.get("used", 0) + 1


def treasure_gives_relic(run) -> bool:
    """Silver Crucible: the first treasure room of the run is empty (ShouldGenerateTreasure, checked after the room is entered)."""
    if not run.has_relic("SILVER_CRUCIBLE"):
        return True
    s = state(run, "SILVER_CRUCIBLE")
    s["treasures"] = s.get("treasures", 0) + 1
    return s["treasures"] > 1


def room_entered(run, room : str, from_unknown : bool = False):
    """AfterRoomEntered for the relics that act on entering a room."""
    if run.has_relic("MAW_BANK") and not state(run, "MAW_BANK").get("bought"):
        gain_gold(run, 12)
    if room == "RestSite":
        for relic in run.relics:
            if relic["id"] in ("VENERABLE_TEA_SET", "FAKE_VENERABLE_TEA_SET") and not relic.get("melted"):
                relic["status"] = "Active"          # GainEnergyInNextCombat
    if room == "RestSite" and run.has_relic("ETERNAL_FEATHER"):
        _heal(run, 3 * (len(run.deck) // 5))
    if room == "Shop" and run.has_relic("MEAL_TICKET"):
        _heal(run, 15)
    if from_unknown and run.has_relic("PLANISPHERE"):
        _heal(run, 5)


# --- rest sites ---------------------------------------------------------------------------------------------------------------------------------------------

def rest_heal(run) -> int:
    """What Rest heals: 30% of max HP (Regal Pillow adds 15)."""
    return int(run.max_hp * REST_HEAL_SHARE) + (15 if run.has_relic("REGAL_PILLOW") else 0)


def rest_healed(run):
    """AfterRestSiteHeal: Stone Humidifier gives 5 max HP."""
    if run.has_relic("STONE_HUMIDIFIER"):
        run.max_hp += 5
        run.hp += 5


def rest_extra_options(run) -> list[str]:
    names = [name for relic, name in (("SHOVEL", "DIG"), ("MEAT_CLEAVER", "COOK"), ("PAELS_GROWTH", "CLONE")) if run.has_relic(relic)]
    if any(c["id"] == "BYRDONIS_EGG" for c in run.deck):         # ByrdonisEgg.TryModifyRestSiteOptions: the quest card adds HATCH
        names.append("HATCH")
    return names


def rest_heal_offers(run) -> list[dict]:
    """TryModifyRestSiteHealRewards: Dream Catcher adds a card reward, Tiny Mailbox two potions."""
    out = []
    if run.has_relic("DREAM_CATCHER"):
        out.append({"kind": "cards", "room": "Monster"})
    if run.has_relic("TINY_MAILBOX"):
        out += [{"kind": "potion"}] * 2
    return out


# --- shops --------------------------------------------------------------------------------------------------------------------------------------------------

def merchant_price(run, price : int) -> int:
    """ModifyMerchantPrice: Membership Card halves, The Courier takes 20% off."""
    value = float(price)
    if run.has_relic("MEMBERSHIP_CARD"):
        value *= 0.5
    if run.has_relic("THE_COURIER"):
        value *= 0.8
    return int(value)
