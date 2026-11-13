"""Move tables of the Act 3 Glory enemies and bosses."""
from __future__ import annotations

from sts2_lite import rng
from sts2_lite.card import Card, CardId
from sts2_lite.status import StatusId
from sts2_lite.enemy_moves.core import Branch, Move, MoveTable, deadly, tough


# ---------------------------------------------------------------- Act 3: Glory
def axebot(ascension : int) -> MoveTable:
    # Stock (2) brings it back when it dies; each return opens with Boot Up, which grants more Strength the fewer lives are left
    def boot_up(enemy, combat):
        lives_used = 2 - enemy.status_amount(StatusId.STOCK)
        enemy.apply_status(StatusId.STRENGTH, deadly(ascension, 3, 4) * lives_used)
    return {
        "BOOT_UP": Move(frozenset({"defend", "buff"}), "HAMMER_UPPERCUT", block=deadly(ascension, 10, 15), effect=boot_up),
        "ONE_TWO": Move(frozenset({"attack"}), "HAMMER_UPPERCUT", damage=deadly(ascension, 9, 10), hits=2),
        "HAMMER_UPPERCUT": Move(frozenset({"attack", "debuff"}), "ONE_TWO", damage=deadly(ascension, 12, 14), hits=1,
                                player_status=((StatusId.WEAK, 2), (StatusId.FRAIL, 2))),
    }


def punch_construct(ascension : int) -> MoveTable:
    return {
        "READY": Move(frozenset({"defend"}), "FAST_PUNCH", block=10),
        "FAST_PUNCH": Move(frozenset({"attack", "debuff"}), "STRONG_PUNCH", damage=deadly(ascension, 5, 6), hits=2,
                           player_status=((StatusId.FRAIL, 1),)),
        "STRONG_PUNCH": Move(frozenset({"attack"}), "READY", damage=deadly(ascension, 14, 16), hits=1),
    }


def globe_head(ascension : int) -> MoveTable:
    return {
        "SHOCKING_SLAP": Move(frozenset({"attack", "debuff"}), "THUNDER_STRIKE", damage=deadly(ascension, 13, 14), hits=1,
                              player_status=((StatusId.FRAIL, 2),)),
        "THUNDER_STRIKE": Move(frozenset({"attack"}), "GALVANIC_BURST", damage=deadly(ascension, 6, 7), hits=3),
        "GALVANIC_BURST": Move(frozenset({"attack", "buff"}), "SHOCKING_SLAP", damage=deadly(ascension, 16, 17), hits=1,
                               self_status=((StatusId.STRENGTH, 2),)),
    }


def scroll_of_biting(ascension : int) -> MoveTable:
    # Chew can repeat once (CanRepeatXTimes 2); Chomp never twice in a row
    return {
        "CHOMP": Move(frozenset({"attack"}), "MORE_TEETH", damage=deadly(ascension, 14, 16), hits=1),
        "CHEW": Move(frozenset({"attack"}), "", damage=deadly(ascension, 5, 6), hits=2,
                     branches=(Branch("CHOMP"), Branch("CHEW", max_streak=2))),
        "MORE_TEETH": Move(frozenset({"buff"}), "CHEW", self_status=((StatusId.STRENGTH, 2),)),
    }


def slimed_berserker(ascension : int) -> MoveTable:
    return {
        "VOMIT_ICHOR": Move(frozenset({"status"}), "FURIOUS_PUMMELING", cards=((CardId.SLIMED, 10),)),
        "FURIOUS_PUMMELING": Move(frozenset({"attack"}), "LEECHING_HUG", damage=deadly(ascension, 4, 5), hits=4),
        "LEECHING_HUG": Move(frozenset({"debuff", "buff"}), "SMOTHER",
                             player_status=((StatusId.WEAK, 3),), self_status=((StatusId.STRENGTH, 3),)),
        "SMOTHER": Move(frozenset({"attack"}), "VOMIT_ICHOR", damage=deadly(ascension, 30, 33), hits=1),
    }


def _frog_next(enemy, combat) -> str:
    # HALF_HEALTH: once, below half of its maximum (integer division), it charges instead of lashing
    if "BEETLE_CHARGE" not in enemy.used_moves and enemy.current_hp < enemy.max_hp // 2:
        return "BEETLE_CHARGE"
    return "TONGUE_LASH"


def frog_knight(ascension : int) -> MoveTable:
    return {
        "TONGUE_LASH": Move(frozenset({"attack", "debuff"}), "STRIKE_DOWN_EVIL", damage=deadly(ascension, 13, 14), hits=1,
                            player_status=((StatusId.FRAIL, 2),)),
        "STRIKE_DOWN_EVIL": Move(frozenset({"attack"}), "FOR_THE_QUEEN", damage=deadly(ascension, 21, 23), hits=1),
        "FOR_THE_QUEEN": Move(frozenset({"buff"}), "", self_status=((StatusId.STRENGTH, 5),), choose=_frog_next),
        "BEETLE_CHARGE": Move(frozenset({"attack"}), "TONGUE_LASH", damage=deadly(ascension, 35, 40), hits=1),
    }


def _possess(stat : StatusId, possess : StatusId, amount : int, block : int = 0):
    """Take `amount` of Strength or Dexterity from the player and give it to the mover; the Possess power remembers what was
    taken (Artifact stops it) and hands it back when the mover dies."""
    def effect(enemy, combat):
        player = combat.combat_state.player
        before = player.status_amount(stat)
        player.apply_status(stat, -amount)
        taken = before - player.status_amount(stat)
        if taken > 0 and possess in enemy.status:
            records = enemy.status[possess].records
            if records:
                records[0][0] += taken
            else:
                records.append([taken])
        if block:
            enemy.apply_block(block + enemy.status_amount(StatusId.DEXTERITY))     # Move block is powered: Dexterity counts
        enemy.apply_status(stat, amount)
    return effect


def the_lost(ascension : int) -> MoveTable:
    return {
        "DEBILITATING_SMOG": Move(frozenset({"debuff", "buff"}), "EYE_LASERS",
                                  effect=_possess(StatusId.STRENGTH, StatusId.POSSESS_STRENGTH, 2)),
        "EYE_LASERS": Move(frozenset({"attack"}), "DEBILITATING_SMOG", damage=deadly(ascension, 4, 5), hits=2),
    }


def the_forgotten(ascension : int) -> MoveTable:
    return {
        "MIASMA": Move(frozenset({"debuff", "defend", "buff"}), "DREAD",
                       effect=_possess(StatusId.DEXTERITY, StatusId.POSSESS_SPEED, 2, block=8)),
        "DREAD": Move(frozenset({"attack"}), "MIASMA", damage=deadly(ascension, 13, 15), hits=1, dex_damage=True),
    }



def _living_shield_next(enemy, combat) -> str:
    # SHIELD_SLAM_BRANCH: keep slamming while any other enemy lives, then smash forever
    if combat is None or any(e is not enemy and e.current_hp > 0 for e in combat.combat_state.enemies):
        return "SHIELD_SLAM"
    return "SMASH"


def living_shield(ascension : int) -> MoveTable:
    return {
        "SHIELD_SLAM": Move(frozenset({"attack"}), "", damage=6, hits=1, choose=_living_shield_next),
        "SMASH": Move(frozenset({"attack", "buff"}), "SMASH", damage=deadly(ascension, 16, 18), hits=1,
                      self_status=((StatusId.STRENGTH, 3),)),
    }


def turret_operator(ascension : int) -> MoveTable:
    # two identical unloads, then a reload (the cycle starts on round 1)
    fire = deadly(ascension, 3, 4)
    return {
        "UNLOAD": Move(frozenset({"attack"}), "UNLOAD_2", damage=fire, hits=5, round_mod=(3, 1)),
        "UNLOAD_2": Move(frozenset({"attack"}), "RELOAD", damage=fire, hits=5, round_mod=(3, 2)),
        "RELOAD": Move(frozenset({"buff"}), "UNLOAD", self_status=((StatusId.STRENGTH, 1),)),
    }


def _incantation(enemy, combat):
    enemy.apply_status(StatusId.RITUAL, 9)
    enemy.status[StatusId.RITUAL].records = [[1]]       # RitualPower.WasJustAppliedByEnemy: no Strength at the end of this turn


def devoted_sculptor(ascension : int) -> MoveTable:
    return {
        "FORBIDDEN_INCANTATION": Move(frozenset({"buff"}), "SAVAGE", effect=_incantation),
        "SAVAGE": Move(frozenset({"attack"}), "SAVAGE", damage=deadly(ascension, 12, 15), hits=1),
    }


def _take_off(enemy, combat):
    enemy.status.pop(StatusId.SOAR, None)


def owl_magistrate(ascension : int) -> MoveTable:
    return {
        "MAGISTRATE_SCRUTINY": Move(frozenset({"attack"}), "PECK_ASSAULT", damage=deadly(ascension, 16, 17), hits=1),
        "PECK_ASSAULT": Move(frozenset({"attack"}), "JUDICIAL_FLIGHT", damage=4, hits=6),
        "JUDICIAL_FLIGHT": Move(frozenset({"buff"}), "VERDICT", self_status=((StatusId.SOAR, 1),)),
        "VERDICT": Move(frozenset({"attack", "debuff"}), "MAGISTRATE_SCRUTINY", damage=deadly(ascension, 33, 36), hits=1,
                        player_status=((StatusId.VULNERABLE, 4),), effect=_take_off),
    }


# Fabricator: bots it can make, as codes in Enemy.counter (the last one made is never made twice in a row from the same list)
BOT_CODES = {"ZAPBOT": 1, "STABBOT": 2, "GUARDBOT": 3, "NOISEBOT": 4}
AGGRO_BOTS, DEFENSE_BOTS = ("ZAPBOT", "STABBOT"), ("GUARDBOT", "NOISEBOT")
FABRICATOR_TEAM = 4


def _make_bot(enemy, combat, options):
    from sts2_lite.enemy import Enemy     # enemy.py imports this module
    last = {code: name for name, code in BOT_CODES.items()}.get(enemy.counter)
    choices = [b for b in options if b != last]
    bot = rng.choice(choices)
    enemy.counter = BOT_CODES[bot]
    enemies = combat.combat_state.enemies
    bot_enemy = Enemy.spawn(bot, 0, combat.combat_state.ascension)
    # GetNextSlot: the encounter's slots run bot1, bot2, fabricator, bot3, bot4 from left to right and a new bot takes the first free one
    home = enemies.index(enemy) if enemy in enemies else len(enemies)
    left, right = home, len(enemies) - home - 1
    if left < 2:
        at = left
    elif right < 2:
        at = home + 1 + right
    else:
        at = len(enemies)
    combat.summon(bot_enemy, at=at)
    same = [e for e in combat.combat_state.enemies if e.enemy_id.rpartition("_")[0] == bot]
    for i, e in enumerate(same):        # the bridge numbers monsters of a kind by their place in the line
        e.enemy_id, e.slot = f"{bot}_{i}", i


def _fabricate(enemy, combat):
    _make_bot(enemy, combat, DEFENSE_BOTS)
    _make_bot(enemy, combat, AGGRO_BOTS)


def _fabricating_strike(enemy, combat):
    _make_bot(enemy, combat, AGGRO_BOTS)


def _fabricator_next(enemy, combat) -> str:
    # fabricateBranch: while fewer than four creatures live on its side it builds (an even pick), then it only disintegrates
    if combat is not None and sum(1 for e in combat.combat_state.enemies if e.current_hp > 0) >= FABRICATOR_TEAM:
        return "DISINTEGRATE"
    return rng.choice(("FABRICATE", "FABRICATING_STRIKE"))


def fabricator(ascension : int) -> MoveTable:
    return {
        "FABRICATE": Move(frozenset({"summon"}), "", effect=_fabricate, choose=_fabricator_next),
        "FABRICATING_STRIKE": Move(frozenset({"attack", "summon"}), "", damage=deadly(ascension, 18, 21), hits=1,
                                   effect=_fabricating_strike, choose=_fabricator_next),
        "DISINTEGRATE": Move(frozenset({"attack"}), "", damage=deadly(ascension, 11, 13), hits=1, choose=_fabricator_next),
    }


def zapbot(ascension : int) -> MoveTable:
    return {"ZAP": Move(frozenset({"attack"}), "ZAP", damage=deadly(ascension, 14, 15), hits=1)}


def stabbot(ascension : int) -> MoveTable:
    return {"STAB": Move(frozenset({"attack", "debuff"}), "STAB", damage=deadly(ascension, 11, 12), hits=1,
                         player_status=((StatusId.FRAIL, 1),))}


def _guard(enemy, combat):
    for ally in combat.combat_state.enemies:
        if ally.enemy_id.startswith("FABRICATOR") and ally.current_hp > 0:
            ally.apply_block(15)        # unpowered


def guardbot(ascension : int) -> MoveTable:
    return {"GUARD": Move(frozenset({"defend"}), "GUARD", effect=_guard)}


def _noise(enemy, combat):
    player = combat.combat_state.player
    player.discard_pile.append(Card.create(CardId.DAZED))
    player.insert_into_draw_pile(Card.create(CardId.DAZED))


def noisebot(ascension : int) -> MoveTable:
    return {"NOISE": Move(frozenset({"status"}), "NOISE", effect=_noise)}



def soul_nexus(ascension : int) -> MoveTable:
    # the next move is any of the three except the one just used
    follow = (Branch("SOUL_BURN"), Branch("MAELSTROM"), Branch("DRAIN_LIFE"))
    return {
        "SOUL_BURN": Move(frozenset({"attack"}), "", damage=deadly(ascension, 29, 31), hits=1, branches=follow),
        "MAELSTROM": Move(frozenset({"attack"}), "", damage=deadly(ascension, 6, 7), hits=4, branches=follow),
        "DRAIN_LIFE": Move(frozenset({"attack", "debuff"}), "", damage=deadly(ascension, 18, 19), hits=1, branches=follow,
                           player_status=((StatusId.VULNERABLE, 2), (StatusId.WEAK, 2))),
    }


def mecha_knight(ascension : int) -> MoveTable:
    return {
        "CHARGE": Move(frozenset({"attack"}), "FLAMETHROWER", damage=deadly(ascension, 25, 30), hits=1),
        "FLAMETHROWER": Move(frozenset({"status"}), "WINDUP", hand_cards=((CardId.BURN, 4),)),
        "WINDUP": Move(frozenset({"defend", "buff"}), "HEAVY_CLEAVE", block=15, self_status=((StatusId.STRENGTH, 5),)),
        "HEAVY_CLEAVE": Move(frozenset({"attack"}), "FLAMETHROWER", damage=deadly(ascension, 35, 40), hits=1),
    }


def flail_knight(ascension : int) -> MoveTable:
    follow = (Branch("WAR_CHANT"), Branch("FLAIL", max_streak=2), Branch("RAM", max_streak=2))
    return {
        "WAR_CHANT": Move(frozenset({"buff"}), "", self_status=((StatusId.STRENGTH, 3),), branches=follow),
        "FLAIL": Move(frozenset({"attack"}), "", damage=deadly(ascension, 9, 10), hits=2, branches=follow),
        "RAM": Move(frozenset({"attack"}), "", damage=deadly(ascension, 15, 17), hits=1, branches=follow),
    }


def spectral_knight(ascension : int) -> MoveTable:
    follow = (Branch("SOUL_SLASH", max_streak=2), Branch("SOUL_FLAME"))
    return {
        "HEX": Move(frozenset({"debuff"}), "SOUL_SLASH", player_status=((StatusId.HEX, 2),)),
        "SOUL_SLASH": Move(frozenset({"attack"}), "", damage=deadly(ascension, 15, 17), hits=1, branches=follow),
        "SOUL_FLAME": Move(frozenset({"attack"}), "", damage=deadly(ascension, 3, 4), hits=3, branches=follow),
    }


def _dampen(enemy, combat):
    from sts2_lite.status import downgrade_cards, StatusInstance
    player = combat.combat_state.player
    if StatusId.DAMPEN in player.status:
        return
    before = len(player.status)
    player.apply_status(StatusId.DAMPEN, 1)
    if StatusId.DAMPEN in player.status:        # Artifact stops it
        downgrade_cards(player)


def magi_knight(ascension : int) -> MoveTable:
    block = tough(ascension, 5, 9)
    return {
        "POWER_SHIELD": Move(frozenset({"attack", "defend"}), "DAMPEN", damage=deadly(ascension, 6, 7), hits=1, block=block),
        "DAMPEN": Move(frozenset({"debuff"}), "RAM", effect=_dampen),
        "RAM": Move(frozenset({"attack"}), "PREP", damage=deadly(ascension, 10, 11), hits=1),
        "PREP": Move(frozenset({"defend"}), "MAGIC_BOMB", block=block),
        "MAGIC_BOMB": Move(frozenset({"attack"}), "RAM", damage=deadly(ascension, 35, 40), hits=1),
    }


# ---------------------------------------------------------------- Act 3 bosses

def _queen_next(enemy, combat) -> str:
    """The Queen's branch: Burn Bright For Me while the Torch Head Amalgam lives, Off With Your Head once it has died."""
    return "OFF_WITH_YOUR_HEAD" if enemy.counter else "BURN_BRIGHT_FOR_ME"


def _burn_bright(enemy, combat):
    for ally in combat.combat_state.enemies:
        if ally is not enemy and ally.current_hp > 0:
            ally.apply_status(StatusId.STRENGTH, 1)


def queen(ascension : int) -> MoveTable:
    return {
        "PUPPET_STRINGS": Move(frozenset({"carddebuff"}), "YOU_ARE_MINE", player_status=((StatusId.CHAINS_OF_BINDING, 3),)),
        "YOU_ARE_MINE": Move(frozenset({"debuff"}), "", choose=_queen_next,
                             player_status=((StatusId.FRAIL, 99), (StatusId.WEAK, 99), (StatusId.VULNERABLE, 99))),
        "BURN_BRIGHT_FOR_ME": Move(frozenset({"buff", "defend"}), "", block=20, effect=_burn_bright, choose=_queen_next),
        "OFF_WITH_YOUR_HEAD": Move(frozenset({"attack"}), "EXECUTION", damage=deadly(ascension, 3, 4), hits=5),
        "EXECUTION": Move(frozenset({"attack"}), "ENRAGE", damage=deadly(ascension, 15, 18), hits=1),
        "ENRAGE": Move(frozenset({"buff"}), "OFF_WITH_YOUR_HEAD", self_status=((StatusId.STRENGTH, 2),)),
    }


def queen_ally_died(queen_enemy, killed, combat):
    """Queen.AfterDeath: the Torch Head Amalgam falling turns a coming Burn Bright For Me into Enrage."""
    if not killed.enemy_id.startswith("TORCH_HEAD_AMALGAM"):
        return
    queen_enemy.counter = 1
    if queen_enemy.move_id == "BURN_BRIGHT_FOR_ME":
        queen_enemy.move_id, queen_enemy.move_streak = "ENRAGE", 1
        queen_enemy.attack_damage = queen_enemy.num_attacks = 0


ALLY_DEATH_HOOKS = {"QUEEN": queen_ally_died}


def torch_head_amalgam(ascension : int) -> MoveTable:
    tackle, weak = deadly(ascension, 18, 19), deadly(ascension, 14, 15)
    return {
        "TACKLE": Move(frozenset({"attack"}), "TACKLE_2", damage=tackle, hits=1),
        "TACKLE_2": Move(frozenset({"attack"}), "BEAM", damage=tackle, hits=1),
        "BEAM": Move(frozenset({"attack"}), "TACKLE_3", damage=8, hits=3),
        "TACKLE_3": Move(frozenset({"attack"}), "TACKLE_4", damage=weak, hits=1),
        "TACKLE_4": Move(frozenset({"attack"}), "BEAM", damage=weak, hits=1),
    }


def subject_respawns(enemy) -> int:
    """Which form the Test Subject is in, read off the powers each one gives it (the game counts its respawns privately)."""
    if StatusId.NEMESIS in enemy.status:
        return 2
    return 1 if StatusId.PAINFUL_STABS in enemy.status else 0


def _respawn(enemy, combat):
    asc = combat.combat_state.ascension
    if subject_respawns(enemy) == 0:
        enemy.max_hp = tough(asc, 200, 212)
        enemy.apply_status(StatusId.PAINFUL_STABS, 1)
    else:
        enemy.max_hp = tough(asc, 300, 313)
        enemy.apply_status(StatusId.NEMESIS, 1)
        enemy.status[StatusId.NEMESIS].records = [[0]]
        enemy.status.pop(StatusId.ADAPTABLE, None)
        enemy.status.pop(StatusId.PAINFUL_STABS, None)
    enemy.current_hp = enemy.max_hp


def _after_respawn(enemy, combat) -> str:
    return "MULTI_CLAW" if subject_respawns(enemy) < 2 else "PHASE3_LACERATE"


def _claw(enemy, combat):
    enemy.counter += 1          # ExtraMultiClawCount


def test_subject(ascension : int) -> MoveTable:
    return {
        "BITE": Move(frozenset({"attack"}), "SKULL_BASH", damage=deadly(ascension, 20, 22), hits=1),
        "SKULL_BASH": Move(frozenset({"attack", "debuff"}), "BITE", damage=deadly(ascension, 14, 16), hits=1,
                           player_status=((StatusId.VULNERABLE, 1),)),
        "RESPAWN": Move(frozenset({"heal", "buff"}), "", effect=_respawn, choose=_after_respawn),
        "MULTI_CLAW": Move(frozenset({"attack"}), "MULTI_CLAW", damage=deadly(ascension, 10, 11), hits=3,
                           effect=_claw, extra_hits=lambda enemy: enemy.counter),
        "PHASE3_LACERATE": Move(frozenset({"attack"}), "BIG_POUNCE", damage=deadly(ascension, 10, 11), hits=3),
        "BIG_POUNCE": Move(frozenset({"attack"}), "BURNING_GROWL", damage=45, hits=1),
        "BURNING_GROWL": Move(frozenset({"status", "buff"}), "PHASE3_LACERATE", cards=((CardId.BURN, deadly(ascension, 3, 5)),),
                              self_status=((StatusId.STRENGTH, deadly(ascension, 2, 3)),)),
    }


def _increasing_intensity(enemy, combat):
    """Every Wither in the deck gets one more step, the new ones are made at that step, and the Strength it gains grows each time."""
    asc = combat.combat_state.ascension
    player = combat.combat_state.player
    for pile in (player.hand, player.draw_pile, player.discard_pile, player.exhaust_pile):
        for i, card in enumerate(pile):
            if card.card_id == CardId.WITHER:
                pile[i] = Card.create_wither(card.wither_level + 1)
    strength = deadly(asc, 3, 4) + enemy.counter
    enemy.counter += 1
    for _ in range(deadly(asc, 1, 2)):
        player.discard_pile.append(Card.create_wither(enemy.counter))
    enemy.apply_status(StatusId.STRENGTH, strength)


def aeonglass(ascension : int) -> MoveTable:
    return {
        "EBB": Move(frozenset({"attack", "defend"}), "EYE_LASERS", damage=deadly(ascension, 26, 32), hits=1, block=33),
        "EYE_LASERS": Move(frozenset({"attack"}), "INCREASING_INTENSITY", damage=deadly(ascension, 11, 12), hits=2),
        "INCREASING_INTENSITY": Move(frozenset({"status", "buff"}), "EBB", effect=_increasing_intensity),
    }


