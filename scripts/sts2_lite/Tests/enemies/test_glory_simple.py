"""Act 3 (Glory) monsters, phase 1: Axebot, Punch Construct, Globe Head, Scroll of Biting, Slimed Berserker, Frog Knight,
The Lost and The Forgotten. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite import rng
from sts2_lite.card import CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.status import StatusId, StatusInstance
from sts2_lite.Tests.enemies.test_bridge_moves import attack, load, raw_enemy
from sts2_lite.Tests.enemies.test_hive_simple import defend, make_card, strike


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)

def at(monster, move, ascension=0, status=(), slot=0, hp=40, max_hp=40, extra=None):
    """A state with one `monster` about to perform `move`, as the bridge would show it."""
    table = MOVE_TABLES[monster](ascension)
    m = table[move]
    intents = attack(m.damage, m.hits) if m.hits else []
    intents += [{"type": t.title(), "label": ""} for t in sorted(m.intents - {"attack"})]
    game_id = move + "_MOVE"
    raw = raw_enemy(monster, game_id, [game_id], intents, status=status, slot=slot)
    raw["hp"], raw["max_hp"] = hp, max_hp
    cs = load(*([raw] + (extra or [])))
    cs.ascension = ascension
    return cs

def turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def moves_over(cs, turns):
    seen = [cs.enemies[0].move_id]
    for _ in range(turns):
        turn(cs)
        seen.append(cs.enemies[0].move_id)
    return seen

def status(name, amount=1):
    return {"id": f"{name}_POWER", "amount": amount}

def inflame():
    return make_card(CardId.INFLAME, "Inflame", CardType.Power, 1, TargetType.Self)


# ---------------------------------------------------------------- the values
@pytest.mark.parametrize("monster, move, base, deadly, hits", [
    ("AXEBOT", "ONE_TWO", 9, 10, 2), ("AXEBOT", "HAMMER_UPPERCUT", 12, 14, 1),
    ("PUNCH_CONSTRUCT", "STRONG_PUNCH", 14, 16, 1), ("PUNCH_CONSTRUCT", "FAST_PUNCH", 5, 6, 2),
    ("GLOBE_HEAD", "THUNDER_STRIKE", 6, 7, 3), ("GLOBE_HEAD", "SHOCKING_SLAP", 13, 14, 1), ("GLOBE_HEAD", "GALVANIC_BURST", 16, 17, 1),
    ("SCROLL_OF_BITING", "CHOMP", 14, 16, 1), ("SCROLL_OF_BITING", "CHEW", 5, 6, 2),
    ("SLIMED_BERSERKER", "FURIOUS_PUMMELING", 4, 5, 4), ("SLIMED_BERSERKER", "SMOTHER", 30, 33, 1),
    ("FROG_KNIGHT", "STRIKE_DOWN_EVIL", 21, 23, 1), ("FROG_KNIGHT", "TONGUE_LASH", 13, 14, 1), ("FROG_KNIGHT", "BEETLE_CHARGE", 35, 40, 1),
    ("THE_LOST", "EYE_LASERS", 4, 5, 2), ("THE_FORGOTTEN", "DREAD", 13, 15, 1),
])
def test_damage_rises_on_deadly_ascension(monster, move, base, deadly, hits):
    for ascension, damage in ((0, base), (9, deadly)):
        m = MOVE_TABLES[monster](ascension)[move]
        assert (m.damage, m.hits) == (damage, hits)


# ---------------------------------------------------------------- Axebot
def test_axebot_alternates_hammer_and_one_two():
    assert moves_over(at("AXEBOT", "HAMMER_UPPERCUT"), 4) == ["HAMMER_UPPERCUT", "ONE_TWO", "HAMMER_UPPERCUT", "ONE_TWO", "HAMMER_UPPERCUT"]

def test_hammer_uppercut_weakens_and_frails():
    cs = at("AXEBOT", "HAMMER_UPPERCUT")
    turn(cs)
    assert cs.player.current_hp == 80 - 12
    assert (cs.player.status_amount(StatusId.WEAK), cs.player.status_amount(StatusId.FRAIL)) == (2, 2)

def test_boot_up_blocks_and_grants_strength_by_lives_used():
    for stock, strength in ((1, 3), (0, 6)):
        status_list = [status("STOCK", stock)] if stock else []
        cs = at("AXEBOT", "BOOT_UP", status=status_list)
        turn(cs)
        e = cs.enemies[0]
        assert (e.block, e.status_amount(StatusId.STRENGTH), e.move_id) == (10, strength, "HAMMER_UPPERCUT")
    cs = at("AXEBOT", "BOOT_UP", ascension=9, status=[status("STOCK", 1)])
    cs.enemies[0].moves = MOVE_TABLES["AXEBOT"](9)
    turn(cs)
    assert (cs.enemies[0].block, cs.enemies[0].status_amount(StatusId.STRENGTH)) == (15, 4)

def test_a_dead_axebot_returns_with_one_life_fewer_in_the_same_place():
    other = raw_enemy("AXEBOT", "ONE_TWO_MOVE", ["ONE_TWO_MOVE"], attack(9, 2), slot=1)
    cs = at("AXEBOT", "HAMMER_UPPERCUT", status=[status("STOCK", 2)], hp=3, extra=[other])
    cs.player.hand = [strike()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert len(cs.enemies) == 2 and not sim.is_over
    new = cs.enemies[0]
    assert new.enemy_id == "AXEBOT_0" and new.current_hp == new.max_hp and 70 <= new.max_hp <= 78
    assert new.move_id == "BOOT_UP" and new.status_amount(StatusId.STOCK) == 1
    assert cs.enemies[1].move_id == "ONE_TWO"

def test_the_last_life_has_no_stock_and_the_fight_ends_when_it_dies():
    cs = at("AXEBOT", "HAMMER_UPPERCUT", status=[status("STOCK", 1)], hp=3)
    cs.player.hand = [strike(), strike()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert StatusId.STOCK not in cs.enemies[0].status and not sim.is_over
    cs.enemies[0].current_hp = 3
    sim.play_card(0, 0)
    assert sim.is_over and cs.won


# ---------------------------------------------------------------- Punch Construct
def test_punch_construct_cycle_and_effects():
    cs = at("PUNCH_CONSTRUCT", "READY")
    assert moves_over(cs, 3) == ["READY", "FAST_PUNCH", "STRONG_PUNCH", "READY"]
    cs = at("PUNCH_CONSTRUCT", "READY")
    turn(cs)
    assert cs.enemies[0].block == 10
    turn(cs)
    assert cs.player.current_hp == 80 - 10 and cs.player.status_amount(StatusId.FRAIL) == 1

def test_the_construct_can_start_with_the_fast_punch():
    assert moves_over(at("PUNCH_CONSTRUCT", "FAST_PUNCH"), 2) == ["FAST_PUNCH", "STRONG_PUNCH", "READY"]

def test_artifact_stops_the_construct_s_frail():
    cs = at("PUNCH_CONSTRUCT", "FAST_PUNCH")
    cs.player.status[StatusId.ARTIFACT] = StatusInstance(StatusId.ARTIFACT, 1)
    turn(cs)
    assert cs.player.status_amount(StatusId.FRAIL) == 0


# ---------------------------------------------------------------- Globe Head
def test_globe_head_cycle():
    assert moves_over(at("GLOBE_HEAD", "SHOCKING_SLAP"), 4) == ["SHOCKING_SLAP", "THUNDER_STRIKE", "GALVANIC_BURST", "SHOCKING_SLAP", "THUNDER_STRIKE"]

def test_shocking_slap_frails_and_galvanic_burst_grows_strength():
    cs = at("GLOBE_HEAD", "SHOCKING_SLAP")
    turn(cs)
    assert cs.player.status_amount(StatusId.FRAIL) == 2
    cs = at("GLOBE_HEAD", "GALVANIC_BURST")
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2

def test_playing_a_power_hurts_while_galvanic_lives():
    cs = at("GLOBE_HEAD", "SHOCKING_SLAP", status=[status("GALVANIC", 6)])
    cs.player.hand = [defend(), inflame()]
    sim = CombatSimulator(cs)
    sim.play_card(1, 0)
    assert cs.player.current_hp == 74
    sim.play_card(0, 0)         # a Skill costs nothing
    assert cs.player.current_hp == 74

def test_galvanic_damage_is_absorbed_by_block_and_ignores_vulnerable():
    cs = at("GLOBE_HEAD", "SHOCKING_SLAP", status=[status("GALVANIC", 6)])
    cs.player.block = 4
    cs.player.status[StatusId.VULNERABLE] = StatusInstance(StatusId.VULNERABLE, 2)
    cs.player.hand = [inflame()]
    CombatSimulator(cs).play_card(0, 0)
    assert (cs.player.block, cs.player.current_hp) == (0, 78)

def test_no_galvanic_no_damage():
    cs = at("GLOBE_HEAD", "SHOCKING_SLAP")
    cs.player.hand = [inflame()]
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.current_hp == 80


# ---------------------------------------------------------------- Scroll of Biting
def test_paper_cuts_cost_maximum_hp_for_each_unblocked_hit():
    cs = at("SCROLL_OF_BITING", "CHEW", status=[status("PAPER_CUTS", 2)])
    turn(cs)        # two hits of 5, nothing blocked
    assert (cs.player.current_hp, cs.player.max_hp) == (70, 76)

def test_a_blocked_hit_costs_no_maximum_hp():
    cs = at("SCROLL_OF_BITING", "CHEW", status=[status("PAPER_CUTS", 2)])
    cs.player.block = 6        # the first hit is absorbed (5), the second breaks through (1 + 4)
    turn(cs)
    assert (cs.player.current_hp, cs.player.max_hp) == (76, 78)
    cs = at("SCROLL_OF_BITING", "CHOMP", status=[status("PAPER_CUTS", 2)])
    cs.player.block = 20
    turn(cs)
    assert cs.player.max_hp == 80

def test_maximum_hp_loss_cannot_leave_current_hp_above_it():
    cs = at("SCROLL_OF_BITING", "CHOMP", status=[status("PAPER_CUTS", 8)])
    cs.player.current_hp = cs.player.max_hp = 20
    turn(cs)
    assert (cs.player.current_hp, cs.player.max_hp) == (6, 12)

def test_chomp_leads_to_more_teeth_which_leads_to_chew():
    cs = at("SCROLL_OF_BITING", "CHOMP")
    assert moves_over(cs, 2) == ["CHOMP", "MORE_TEETH", "CHEW"]
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2

def test_chew_follows_with_chomp_or_one_more_chew_never_two():
    seen = set()
    for seed in range(200):
        rng.seed(seed) if hasattr(rng, "seed") else None
        cs = at("SCROLL_OF_BITING", "CHEW")
        e = cs.enemies[0]
        for _ in range(6):
            turn(cs)
            if e.move_id == "CHEW":
                e.move_streak  # streak is tracked by the table
            assert not (e.move_id == "CHEW" and e.move_streak > 2)
            assert not (e.move_id == "CHOMP" and e.move_streak > 1)
            seen.add(e.move_id)
    assert {"CHOMP", "CHEW", "MORE_TEETH"} <= seen


# ---------------------------------------------------------------- Slimed Berserker
def test_berserker_cycle():
    assert moves_over(at("SLIMED_BERSERKER", "VOMIT_ICHOR"), 4) == ["VOMIT_ICHOR", "FURIOUS_PUMMELING", "LEECHING_HUG", "SMOTHER", "VOMIT_ICHOR"]

def test_vomit_ichor_puts_ten_slimed_in_the_discard_pile():
    cs = at("SLIMED_BERSERKER", "VOMIT_ICHOR")
    turn(cs)
    assert [c.card_id for c in cs.player.discard_pile] == [CardId.SLIMED] * 10

def test_leeching_hug_weakens_the_player_and_strengthens_the_berserker():
    cs = at("SLIMED_BERSERKER", "LEECHING_HUG")
    turn(cs)
    assert cs.player.status_amount(StatusId.WEAK) == 3 and cs.enemies[0].status_amount(StatusId.STRENGTH) == 3


# ---------------------------------------------------------------- Frog Knight
def test_frog_knight_opens_with_tongue_lash_and_loops_while_healthy():
    assert moves_over(at("FROG_KNIGHT", "TONGUE_LASH", status=[status("PLATING", 15)]), 5) == \
        ["TONGUE_LASH", "STRIKE_DOWN_EVIL", "FOR_THE_QUEEN", "TONGUE_LASH", "STRIKE_DOWN_EVIL", "FOR_THE_QUEEN"]

def test_tongue_lash_frails_and_for_the_queen_adds_five_strength():
    cs = at("FROG_KNIGHT", "TONGUE_LASH")
    turn(cs)
    assert cs.player.status_amount(StatusId.FRAIL) == 2
    cs = at("FROG_KNIGHT", "FOR_THE_QUEEN")
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 5

def test_below_half_health_it_charges_once():
    cs = at("FROG_KNIGHT", "FOR_THE_QUEEN", hp=99, max_hp=200)
    e = cs.enemies[0]
    turn(cs)
    assert e.move_id == "BEETLE_CHARGE"
    turn(cs)
    assert e.move_id == "TONGUE_LASH" and cs.player.current_hp == 80 - 40
    e.move_id = "FOR_THE_QUEEN"      # at the end of the next loop it is still hurt, but has charged
    turn(cs)
    assert e.move_id == "TONGUE_LASH"

def test_exactly_half_health_does_not_charge():
    cs = at("FROG_KNIGHT", "FOR_THE_QUEEN", hp=100, max_hp=200)
    turn(cs)
    assert cs.enemies[0].move_id == "TONGUE_LASH"

def test_a_charge_in_the_log_counts_as_used():
    cs = load(raw_enemy("FROG_KNIGHT", "FOR_THE_QUEEN", ["BEETLE_CHARGE", "TONGUE_LASH", "STRIKE_DOWN_EVIL", "FOR_THE_QUEEN"],
                        [{"type": "Buff", "label": ""}]))
    e = cs.enemies[0]
    e.current_hp, e.max_hp = 10, 200
    turn(cs)
    assert e.move_id == "TONGUE_LASH"


# ---------------------------------------------------------------- The Lost
def test_the_lost_cycle():
    assert moves_over(at("THE_LOST", "DEBILITATING_SMOG"), 3) == ["DEBILITATING_SMOG", "EYE_LASERS", "DEBILITATING_SMOG", "EYE_LASERS"]

def test_smog_moves_strength_from_the_player_to_the_lost():
    cs = at("THE_LOST", "DEBILITATING_SMOG", status=[status("POSSESS_STRENGTH")])
    cs.player.status[StatusId.STRENGTH] = StatusInstance(StatusId.STRENGTH, 3)
    turn(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == 1 and cs.enemies[0].status_amount(StatusId.STRENGTH) == 2

def test_smog_can_take_the_player_below_zero():
    cs = at("THE_LOST", "DEBILITATING_SMOG", status=[status("POSSESS_STRENGTH")])
    turn(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == -2 and cs.enemies[0].status_amount(StatusId.STRENGTH) == 2

def test_artifact_stops_the_theft_but_the_lost_still_grows():
    cs = at("THE_LOST", "DEBILITATING_SMOG", status=[status("POSSESS_STRENGTH")])
    cs.player.status[StatusId.ARTIFACT] = StatusInstance(StatusId.ARTIFACT, 1)
    turn(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == 0 and cs.enemies[0].status_amount(StatusId.STRENGTH) == 2
    assert StatusId.ARTIFACT not in cs.player.status

def test_killing_the_lost_gives_the_strength_back():
    cs = at("THE_LOST", "DEBILITATING_SMOG", status=[status("POSSESS_STRENGTH")], hp=2)
    cs.player.hand = [strike()]
    sim = CombatSimulator(cs)
    turn(cs)
    turn(cs)
    turn(cs)        # two smogs: 4 taken
    assert cs.player.status_amount(StatusId.STRENGTH) == -4
    sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.STRENGTH) == 0

def test_a_lost_read_mid_fight_remembers_what_it_took_from_its_strength():
    cs = at("THE_LOST", "DEBILITATING_SMOG", status=[status("POSSESS_STRENGTH"), status("STRENGTH", 4)], hp=1)
    cs.player.status[StatusId.STRENGTH] = StatusInstance(StatusId.STRENGTH, -4)
    cs.player.hand = [strike()]
    CombatSimulator(cs).play_card(0, 0)
    assert cs.player.status_amount(StatusId.STRENGTH) == 0


# ---------------------------------------------------------------- The Forgotten
def test_forgotten_cycle():
    assert moves_over(at("THE_FORGOTTEN", "MIASMA"), 3) == ["MIASMA", "DREAD", "MIASMA", "DREAD"]

def test_miasma_takes_dexterity_blocks_and_grows_dread():
    cs = at("THE_FORGOTTEN", "MIASMA", status=[status("POSSESS_SPEED")])
    turn(cs)
    e = cs.enemies[0]
    assert cs.player.status_amount(StatusId.DEXTERITY) == -2 and e.status_amount(StatusId.DEXTERITY) == 2
    assert e.block == 8
    assert (e.move_id, e.attack_damage) == ("DREAD", 15)

def test_dexterity_adds_to_later_miasma_block_and_dread_damage():
    cs = at("THE_FORGOTTEN", "MIASMA", status=[status("POSSESS_SPEED")])
    turn(cs)
    turn(cs)            # Dread for 15
    assert cs.player.current_hp == 80 - 15
    turn(cs)            # Miasma again: block 8 + 2, dexterity now 4
    e = cs.enemies[0]
    assert (e.block, e.status_amount(StatusId.DEXTERITY), e.attack_damage) == (10, 4, 17)

def test_killing_the_forgotten_gives_the_dexterity_back():
    cs = at("THE_FORGOTTEN", "MIASMA", status=[status("POSSESS_SPEED")], hp=3)
    cs.player.hand = [strike()]
    sim = CombatSimulator(cs)
    turn(cs)
    assert cs.player.status_amount(StatusId.DEXTERITY) == -2
    cs.enemies[0].block = 0
    sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.DEXTERITY) == 0

def test_negative_dexterity_is_a_debuff_for_artifact():
    cs = at("THE_FORGOTTEN", "MIASMA", status=[status("POSSESS_SPEED")])
    cs.player.status[StatusId.ARTIFACT] = StatusInstance(StatusId.ARTIFACT, 1)
    turn(cs)
    assert cs.player.status_amount(StatusId.DEXTERITY) == 0 and cs.enemies[0].status_amount(StatusId.DEXTERITY) == 2


# ---------------------------------------------------------------- captured from the game (Tests/data/act3_glory)
def test_globe_head_galvanic_matches_the_game_capture():
    """Inflame with 10 block and Galvanic 6: the block takes the damage (10 -> 4), hit points stay."""
    from sts2_lite import verify
    from sts2_lite.Tests import captures
    before = captures.load("globe_head", "before_power", captures.GLORY)
    after = captures.load("globe_head", "after_power", captures.GLORY)
    assert (before.player.block, before.player.current_hp) == (10, 80)
    sim = CombatSimulator(before)
    inflame_index = next(i for i, c in enumerate(before.player.hand) if c.card_id == CardId.INFLAME)
    sim.play_card(inflame_index, 0)
    assert (before.player.block, before.player.current_hp) == (4, 80)
    assert verify.compare(before, after) == []
