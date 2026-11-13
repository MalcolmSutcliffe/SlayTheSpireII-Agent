"""Move tables of the Act 2 Hive enemies."""
from __future__ import annotations

from sts2_lite import rng
from sts2_lite.card import Card, CARD_RARITY, CardId, CardRarity, EnchantmentId
from sts2_lite.status import StatusId
from sts2_lite.enemy_moves.core import Branch, Move, MoveTable, TOUGH_ASCENSION, deadly, tough, escape


EGG_SLOTS = 5
HATCHLING_HP = ((19, 22), (20, 23))     # (base, tough) hit points of a hatched Tough Egg


# ---------------------------------------------------------------- Act 2: the Hive
def bowlbug_egg(ascension : int) -> MoveTable:
    return {
        "BITE": Move(frozenset({"attack", "defend"}), "BITE",
                     damage=deadly(ascension, 7, 8), hits=1, block=deadly(ascension, 7, 8)),
    }


def bowlbug_nectar(ascension : int) -> MoveTable:
    return {
        "THRASH": Move(frozenset({"attack"}), "BUFF", damage=3, hits=1),
        "BUFF": Move(frozenset({"buff"}), "THRASH2", self_status=((StatusId.STRENGTH, deadly(ascension, 15, 16)),)),
        "THRASH2": Move(frozenset({"attack"}), "THRASH2", damage=3, hits=1),
    }


def bowlbug_silk(ascension : int) -> MoveTable:
    return {
        "TOXIC_SPIT": Move(frozenset({"debuff"}), "THRASH", player_status=((StatusId.WEAK, 1),)),
        "THRASH": Move(frozenset({"attack"}), "TOXIC_SPIT", damage=deadly(ascension, 4, 5), hits=2),
    }


def bowlbug_rock(ascension : int) -> MoveTable:
    # Imbalanced: when an attack of its is fully blocked it is stunned after finishing it (Enemy.imbalanced)
    return {
        "HEADBUTT": Move(frozenset({"attack"}), "HEADBUTT", damage=deadly(ascension, 15, 16), hits=1),
    }


def chomper(ascension : int) -> MoveTable:
    return {
        "CLAMP": Move(frozenset({"attack"}), "SCREECH", damage=deadly(ascension, 8, 9), hits=2),
        "SCREECH": Move(frozenset({"statuscard"}), "CLAMP", cards=((CardId.DAZED, 3),)),
    }


def spiny_toad(ascension : int) -> MoveTable:
    # the spikes are Thorns 5, taken back by the explosion
    return {
        "PROTRUDING_SPIKES": Move(frozenset({"buff"}), "SPIKE_EXPLOSION", self_status=((StatusId.THORNS, 5),)),
        "SPIKE_EXPLOSION": Move(frozenset({"attack"}), "TONGUE_LASH", damage=deadly(ascension, 23, 25), hits=1,
                                self_status=((StatusId.THORNS, -5),)),
        "TONGUE_LASH": Move(frozenset({"attack"}), "PROTRUDING_SPIKES", damage=deadly(ascension, 17, 19), hits=1),
    }


def myte(ascension : int) -> MoveTable:
    return {
        "TOXIC": Move(frozenset({"statuscard"}), "BITE", hand_cards=((CardId.TOXIC, 2),)),
        "BITE": Move(frozenset({"attack"}), "SUCK", damage=deadly(ascension, 13, 15), hits=1),
        "SUCK": Move(frozenset({"attack", "buff"}), "TOXIC", damage=deadly(ascension, 4, 6), hits=1,
                     self_status=((StatusId.STRENGTH, deadly(ascension, 2, 3)),)),
    }


def parafright(ascension : int) -> MoveTable:
    return {
        "SLAM": Move(frozenset({"attack"}), "SLAM", damage=deadly(ascension, 16, 17), hits=1),
    }


def the_obscura(ascension : int) -> MoveTable:
    after = (Branch("PIERCING_GAZE"), Branch("WAIL"), Branch("HARDENING_STRIKE"))      # never the same move twice in a row
    return {
        "ILLUSION": Move(frozenset({"summon"}), "", branches=after, summon=("PARAFRIGHT", 0)),
        "PIERCING_GAZE": Move(frozenset({"attack"}), "", branches=after, damage=deadly(ascension, 10, 11), hits=1),
        "WAIL": Move(frozenset({"buff"}), "", branches=after, team_status=((StatusId.STRENGTH, 3),)),
        "HARDENING_STRIKE": Move(frozenset({"attack", "defend"}), "", branches=after,
                                 damage=deadly(ascension, 6, 7), hits=1, block=deadly(ascension, 6, 7)),
    }


def _pheromone_spit(enemy, combat):
    # Personal Hive grows up to 3 (with 1 Strength each time); after that it is 2 Strength
    if enemy.status_amount(StatusId.PERSONAL_HIVE) < 3:
        enemy.apply_status(StatusId.PERSONAL_HIVE, 1)
        enemy.apply_status(StatusId.STRENGTH, 1)
    else:
        enemy.apply_status(StatusId.STRENGTH, 2)


def exoskeleton(ascension : int) -> MoveTable:
    # after a skitter it is always the mandibles (neither may repeat); after the mandibles it enrages
    either = (Branch("SKITTER"), Branch("MANDIBLES"))
    return {
        "SKITTER": Move(frozenset({"attack"}), "", branches=either, damage=1, hits=deadly(ascension, 3, 4)),
        "MANDIBLES": Move(frozenset({"attack"}), "ENRAGE", damage=deadly(ascension, 8, 9), hits=1),
        "ENRAGE": Move(frozenset({"buff"}), "", branches=either, self_status=((StatusId.STRENGTH, 2),)),
    }


def hunter_killer(ascension : int) -> MoveTable:
    after = (Branch("BITE"), Branch("PUNCTURE", max_streak=2))
    return {
        "TENDERIZING_GOOP": Move(frozenset({"debuff"}), "", branches=after, player_status=((StatusId.TENDER, 1),)),
        "BITE": Move(frozenset({"attack"}), "", branches=after, damage=deadly(ascension, 17, 19), hits=1),
        "PUNCTURE": Move(frozenset({"attack"}), "", branches=after, damage=deadly(ascension, 7, 8), hits=3),
    }


def entomancer(ascension : int) -> MoveTable:
    return {
        "BEES": Move(frozenset({"attack"}), "SPEAR", damage=3, hits=deadly(ascension, 7, 8)),
        "SPEAR": Move(frozenset({"attack"}), "PHEROMONE_SPIT", damage=deadly(ascension, 18, 20), hits=1),
        "PHEROMONE_SPIT": Move(frozenset({"buff"}), "BEES", effect=_pheromone_spit),
    }


def infested_prism(ascension : int) -> MoveTable:
    spark = deadly(ascension, 2, 3)
    return {
        "JAB": Move(frozenset({"attack"}), "RADIATE", damage=deadly(ascension, 15, 17), hits=1),
        "RADIATE": Move(frozenset({"attack", "defend"}), "WHIRLWIND",
                        damage=deadly(ascension, 11, 13), hits=1, block=deadly(ascension, 11, 13)),
        "WHIRLWIND": Move(frozenset({"attack"}), "PULSATE", damage=deadly(ascension, 5, 6), hits=3),
        "PULSATE": Move(frozenset({"attack", "buff", "defend"}), "JAB", damage=deadly(ascension, 8, 10), hits=1,
                        block=tough(ascension, 20, 22), self_status=((StatusId.VITAL_SPARK, spark),)),
    }


def louse_progenitor(ascension : int) -> MoveTable:
    return {
        "WEB_CANNON": Move(frozenset({"attack", "debuff"}), "CURL_AND_GROW", damage=deadly(ascension, 9, 10), hits=1,
                           player_status=((StatusId.FRAIL, 2),)),
        "CURL_AND_GROW": Move(frozenset({"defend", "buff"}), "POUNCE",
                              block=tough(ascension, 14, 18), self_status=((StatusId.STRENGTH, 5),)),
        "POUNCE": Move(frozenset({"attack"}), "WEB_CANNON", damage=deadly(ascension, 14, 16), hits=1),
    }


def _lay_eggs(enemy, combat):
    """Three Tough Eggs, as many as there are free slots (five). They stand in slot order, the newest to the left, and
    every egg's id is its position among the eggs, as the bridge reports it."""
    from sts2_lite.enemy import Enemy
    cs = combat.combat_state
    for _ in range(min(3, EGG_SLOTS - sum(e.enemy_id.startswith("TOUGH_EGG_") for e in cs.enemies))):
        combat.summon(Enemy.spawn("TOUGH_EGG", 0, cs.ascension), front=True)
    for i, egg in enumerate(e for e in cs.enemies if e.enemy_id.startswith("TOUGH_EGG_")):
        egg.enemy_id, egg.slot = f"TOUGH_EGG_{i}", i


def _can_lay(enemy, combat) -> bool:
    return len(combat.combat_state.enemies) <= 3        # every living enemy counts, the Ovicopter too


def _hatch(enemy, combat):
    # the egg becomes a hatchling: new hit points, and every power but Minion is lost
    low, high = HATCHLING_HP[0 if combat.combat_state.ascension < TOUGH_ASCENSION else 1]
    enemy.max_hp = enemy.current_hp = rng.randrange(low, high + 1)
    for status_id in [s for s in enemy.status if s is not StatusId.MINION]:
        del enemy.status[status_id]


def _steal_priority(card) -> int:
    """ThievingHopper._stealPriorities: the index of the first rule that accepts the card (Imbued cards count last)."""
    if card.enchantment == EnchantmentId.IMBUED:
        return 3
    rarity = CARD_RARITY[card.card_id]
    return {CardRarity.Uncommon: 0, CardRarity.Common: 1, CardRarity.Rare: 1, CardRarity.Event: 1,
            CardRarity.Basic: 2, CardRarity.Ancient: 3}.get(rarity, 4)


def _steal_a_card(enemy, combat):
    """Takes a card of the deck (not one made this fight) from the draw or discard pile, the Uncommon ones first."""
    player = combat.combat_state.player
    deck = [c for c in [*player.draw_pile, *player.discard_pile]
            if not c.generated and CARD_RARITY[c.card_id] not in (CardRarity.Status, CardRarity.Token)]
    if not deck:
        return
    best = min(_steal_priority(c) for c in deck)
    pool = [c for c in deck if _steal_priority(c) == best] if best < 4 else deck
    card = rng.choice(pool)
    if any(card is c for c in player.draw_pile):
        player.remove_from_draw_pile(card)
    else:
        player.discard_pile = [c for c in player.discard_pile if c is not card]
    enemy.apply_status(StatusId.SWIPE, 1)



def tunneler(ascension : int) -> MoveTable:
    # Burrowed keeps the block; breaking it stuns the Tunneler and it bites again (Creature._after_damage)
    return {
        "BITE": Move(frozenset({"attack"}), "BURROW", damage=deadly(ascension, 13, 15), hits=1),
        "BURROW": Move(frozenset({"buff", "defend"}), "BELOW", block=tough(ascension, 32, 37),
                       self_status=((StatusId.BURROWED, 1),)),
        "BELOW": Move(frozenset({"attack"}), "BELOW", damage=deadly(ascension, 23, 26), hits=1),
    }


def slumbering_beetle(ascension : int) -> MoveTable:
    # Slumber ticks at the end of each enemy turn; at zero (or when hit down to it) the Plating goes and it rolls
    return {
        "SNORE": Move(frozenset({"sleep"}), "",
                      choose=lambda e, c: "SNORE" if StatusId.SLUMBER in e.status else "ROLL_OUT"),
        "ROLL_OUT": Move(frozenset({"attack", "buff"}), "ROLL_OUT", damage=deadly(ascension, 16, 18), hits=1,
                         self_status=((StatusId.STRENGTH, 2),)),
        "STUNNED": Move(frozenset({"stun"}), "", effect=lambda e, c: e.status.pop(StatusId.PLATING, None)),
    }


def ovicopter(ascension : int) -> MoveTable:
    return {
        "LAY_EGGS": Move(frozenset({"summon"}), "SMASH", effect=_lay_eggs),
        "SMASH": Move(frozenset({"attack"}), "TENDERIZER", damage=deadly(ascension, 16, 17), hits=1),
        "TENDERIZER": Move(frozenset({"attack", "debuff"}), "", damage=deadly(ascension, 7, 8), hits=1,
                           player_status=((StatusId.VULNERABLE, 2),),
                           choose=lambda e, c: "LAY_EGGS" if _can_lay(e, c) else "NUTRITIONAL_PASTE"),
        "NUTRITIONAL_PASTE": Move(frozenset({"buff"}), "SMASH", self_status=((StatusId.STRENGTH, deadly(ascension, 3, 4)),)),
    }


def tough_egg(ascension : int) -> MoveTable:
    return {
        "HATCH": Move(frozenset({"summon"}), "NIBBLE", effect=_hatch),
        "NIBBLE": Move(frozenset({"attack"}), "NIBBLE", damage=deadly(ascension, 4, 5), hits=1),
    }


def thieving_hopper(ascension : int) -> MoveTable:
    return {
        "THIEVERY": Move(frozenset({"attack", "carddebuff"}), "FLUTTER", damage=deadly(ascension, 17, 19), hits=1,
                         effect=_steal_a_card),
        "FLUTTER": Move(frozenset({"buff"}), "HAT_TRICK", self_status=((StatusId.FLUTTER, 5),)),
        "HAT_TRICK": Move(frozenset({"attack"}), "NAB", damage=deadly(ascension, 21, 23), hits=1),
        "NAB": Move(frozenset({"attack"}), "ESCAPE", damage=deadly(ascension, 14, 16), hits=1),
        "ESCAPE": Move(frozenset({"escape"}), "ESCAPE", effect=escape),
    }


def the_insatiable(ascension : int) -> MoveTable:
    # Sandpit (4) counts down at the start of each enemy turn and kills the player at zero; Frantic Escape adds one
    return {
        "LIQUIFY_GROUND": Move(frozenset({"buff", "statuscard"}), "THRASH", self_status=((StatusId.SANDPIT, 4),),
                               draw_cards=((CardId.FRANTIC_ESCAPE, 3),), cards=((CardId.FRANTIC_ESCAPE, 3),)),
        "THRASH": Move(frozenset({"attack"}), "LUNGING_BITE", damage=deadly(ascension, 8, 9), hits=2),
        "LUNGING_BITE": Move(frozenset({"attack"}), "SALIVATE", damage=deadly(ascension, 28, 31), hits=1),
        "SALIVATE": Move(frozenset({"buff"}), "THRASH_2", self_status=((StatusId.STRENGTH, deadly(ascension, 2, 3)),)),
        "THRASH_2": Move(frozenset({"attack"}), "THRASH", damage=deadly(ascension, 8, 9), hits=2),
    }


CURSE_SETS = ((CardId.DISINTEGRATION, CardId.MIND_ROT), (CardId.DISINTEGRATION, CardId.SLOTH), (CardId.DISINTEGRATION, CardId.WASTE_AWAY))
CURSE_CASTS = 3
DISINTEGRATION_DAMAGE = (6, 7, 8)       # by cast


def _curse_of_knowledge(enemy, combat):
    # the player picks one of two curses; the pick is applied (and the next player turn begins) when it is made
    from sts2_lite.card import Card
    combat.request_curse([Card.create_knowledge_curse(c) for c in CURSE_SETS[enemy.counter]], DISINTEGRATION_DAMAGE[enemy.counter])
    enemy.counter += 1


def knowledge_demon(ascension : int) -> MoveTable:
    return {
        "CURSE_OF_KNOWLEDGE": Move(frozenset({"debuff"}), "SLAP", effect=_curse_of_knowledge),
        "SLAP": Move(frozenset({"attack"}), "KNOWLEDGE_OVERWHELMING", damage=deadly(ascension, 17, 18), hits=1),
        "KNOWLEDGE_OVERWHELMING": Move(frozenset({"attack"}), "PONDER", damage=deadly(ascension, 8, 9), hits=3),
        "PONDER": Move(frozenset({"attack", "heal", "buff"}), "", damage=deadly(ascension, 11, 13), hits=1, heal=30,
                       self_status=((StatusId.STRENGTH, deadly(ascension, 2, 3)),),
                       choose=lambda e, c: "CURSE_OF_KNOWLEDGE" if e.counter < CURSE_CASTS else "SLAP"),
    }


def decimillipede_segment(ascension : int) -> MoveTable:
    # CONSTRICT -> BULK -> WRITHE in a ring; a killed segment lies DEAD for a turn, then REATTACHes and picks one of the three at random
    revive = (Branch("WRITHE"), Branch("BULK"), Branch("CONSTRICT"))
    return {
        "WRITHE": Move(frozenset({"attack"}), "CONSTRICT", damage=deadly(ascension, 5, 6), hits=2),
        "BULK": Move(frozenset({"attack", "buff"}), "WRITHE", damage=deadly(ascension, 6, 7), hits=1,
                     self_status=((StatusId.STRENGTH, 2),)),
        "CONSTRICT": Move(frozenset({"attack", "debuff"}), "BULK", damage=deadly(ascension, 8, 9), hits=1,
                          player_status=((StatusId.WEAK, 1),)),
        "DEAD": Move(frozenset(), "REATTACH"),
        "REATTACH": Move(frozenset({"heal"}), "", branches=revive),
    }


SEGMENTS = ("DECIMILLIPEDE_SEGMENT_FRONT", "DECIMILLIPEDE_SEGMENT_MIDDLE", "DECIMILLIPEDE_SEGMENT_BACK")      # left to right


def crusher(ascension : int) -> MoveTable:
    # the Kaiser Crab's left arm; it hits 1.5x while the player faces away from it (Surrounded)
    return {
        "THRASH": Move(frozenset({"attack"}), "ENLARGING_STRIKE", damage=deadly(ascension, 12, 14), hits=1),
        "ENLARGING_STRIKE": Move(frozenset({"attack"}), "BUG_STING", damage=4, hits=1),
        "BUG_STING": Move(frozenset({"attack", "debuff"}), "ADAPT", damage=deadly(ascension, 6, 7), hits=2,
                          player_status=((StatusId.WEAK, 2), (StatusId.FRAIL, 2))),
        "ADAPT": Move(frozenset({"buff"}), "GUARDED_STRIKE", self_status=((StatusId.STRENGTH, deadly(ascension, 2, 3)),)),
        "GUARDED_STRIKE": Move(frozenset({"attack", "defend"}), "THRASH", damage=deadly(ascension, 12, 14), hits=1, block=18),
    }


def rocket(ascension : int) -> MoveTable:
    # the right arm; RECHARGE is a turn of doing nothing
    return {
        "TARGETING_RETICLE": Move(frozenset({"attack"}), "PRECISION_BEAM", damage=deadly(ascension, 3, 4), hits=1),
        "PRECISION_BEAM": Move(frozenset({"attack"}), "CHARGE_UP", damage=deadly(ascension, 18, 20), hits=1),
        "CHARGE_UP": Move(frozenset({"buff"}), "LASER", self_status=((StatusId.STRENGTH, deadly(ascension, 2, 3)),)),
        "LASER": Move(frozenset({"attack"}), "RECHARGE", damage=deadly(ascension, 31, 35), hits=1),
        "RECHARGE": Move(frozenset({"sleep"}), "TARGETING_RETICLE"),
    }


