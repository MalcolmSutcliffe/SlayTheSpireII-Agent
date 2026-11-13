"""Act 2 (Hive) monsters with simple move sets: Bowlbugs, Chomper, Spiny Toad, Myte, The Obscura and Parafright.
Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite.card import CardId
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy import STUNNED
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.status import StatusId, StatusInstance
from sts2_lite.Tests.enemies.test_bridge_moves import attack, load, raw_enemy


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)

def at(monster, move, ascension=0, log=None, status=(), slot=0):
    """A state with one `monster` about to perform `move`, as the bridge would show it."""
    table = MOVE_TABLES[monster](ascension)
    m = table[move]
    intents = attack(m.damage, m.hits) if m.hits else []
    intents += [{"type": t.title(), "label": ""} for t in sorted(m.intents - {"attack"})]
    game_id = move + "_MOVE"
    cs = load(raw_enemy(monster, game_id, log or [game_id], intents, status=status, slot=slot))
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


# ---------------------------------------------------------------- the values
@pytest.mark.parametrize("monster, move, base, deadly", [
    ("BOWLBUG_EGG", "BITE", 7, 8), ("BOWLBUG_SILK", "THRASH", 4, 5), ("BOWLBUG_ROCK", "HEADBUTT", 15, 16),
    ("CHOMPER", "CLAMP", 8, 9), ("SPINY_TOAD", "TONGUE_LASH", 17, 19), ("SPINY_TOAD", "SPIKE_EXPLOSION", 23, 25),
    ("MYTE", "BITE", 13, 15), ("MYTE", "SUCK", 4, 6), ("PARAFRIGHT", "SLAM", 16, 17),
    ("THE_OBSCURA", "PIERCING_GAZE", 10, 11), ("THE_OBSCURA", "HARDENING_STRIKE", 6, 7),
])
def test_damage_rises_on_deadly_ascension(monster, move, base, deadly):
    assert MOVE_TABLES[monster](0)[move].damage == base
    assert MOVE_TABLES[monster](9)[move].damage == deadly

def test_hit_counts():
    assert MOVE_TABLES["BOWLBUG_SILK"](0)["THRASH"].hits == 2 and MOVE_TABLES["CHOMPER"](0)["CLAMP"].hits == 2


# ---------------------------------------------------------------- move cycles
@pytest.mark.parametrize("monster, start, expected", [
    ("BOWLBUG_EGG", "BITE", ["BITE"] * 3),
    ("BOWLBUG_NECTAR", "THRASH", ["THRASH", "BUFF", "THRASH2", "THRASH2", "THRASH2"]),
    ("BOWLBUG_SILK", "TOXIC_SPIT", ["TOXIC_SPIT", "THRASH", "TOXIC_SPIT", "THRASH"]),
    ("CHOMPER", "CLAMP", ["CLAMP", "SCREECH", "CLAMP", "SCREECH"]),
    ("SPINY_TOAD", "PROTRUDING_SPIKES", ["PROTRUDING_SPIKES", "SPIKE_EXPLOSION", "TONGUE_LASH", "PROTRUDING_SPIKES"]),
    ("MYTE", "TOXIC", ["TOXIC", "BITE", "SUCK", "TOXIC", "BITE"]),
    ("PARAFRIGHT", "SLAM", ["SLAM", "SLAM"]),
])
def test_move_cycle(monster, start, expected):
    assert moves_over(at(monster, start), len(expected) - 1) == expected

def test_the_game_ids_read_from_the_bridge():
    cs = load(raw_enemy("THE_OBSCURA", "SAIL_MOVE", ["ILLUSION_MOVE", "SAIL_MOVE"], [{"type": "Buff", "label": ""}]))
    assert cs.enemies[0].move_id == "WAIL" and cs.enemies[0].used_moves == {"ILLUSION"}


# ---------------------------------------------------------------- effects
def test_egg_blocks_as_it_bites():
    cs = at("BOWLBUG_EGG", "BITE")
    turn(cs)
    assert cs.player.current_hp == 73 and cs.enemies[0].block == 7

def test_nectar_gains_strength_for_its_last_thrashes():
    cs = at("BOWLBUG_NECTAR", "THRASH")
    turn(cs); turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 15 and cs.player.current_hp == 77
    turn(cs)
    assert cs.player.current_hp == 77 - 18

def test_silk_weakens_then_hits_twice():
    cs = at("BOWLBUG_SILK", "TOXIC_SPIT")
    turn(cs)
    assert cs.player.status_amount(StatusId.WEAK) == 1
    turn(cs)
    assert cs.player.current_hp == 72

def test_chomper_adds_dazed_to_the_discard_pile():
    cs = at("CHOMPER", "SCREECH")
    turn(cs)
    assert [c.card_id for c in cs.player.discard_pile] == [CardId.DAZED] * 3

def test_myte_puts_toxic_in_the_hand():
    cs = at("MYTE", "TOXIC")
    turn(cs)
    assert [c.card_id for c in cs.player.hand] == [CardId.TOXIC] * 2

def test_myte_suck_hits_and_grows():
    cs = at("MYTE", "SUCK")
    turn(cs)
    assert cs.player.current_hp == 76 and cs.enemies[0].status_amount(StatusId.STRENGTH) == 2

def test_spiny_toad_wears_thorns_between_its_spikes_and_its_explosion():
    cs = at("SPINY_TOAD", "PROTRUDING_SPIKES")
    toad = cs.enemies[0]
    turn(cs)
    assert toad.status_amount(StatusId.THORNS) == 5
    turn(cs)                    # the explosion takes the spikes back
    assert StatusId.THORNS not in toad.status and cs.player.current_hp == 80 - 23

def test_rock_stumbles_after_an_attack_that_is_fully_blocked():
    cs = at("BOWLBUG_ROCK", "HEADBUTT", status=[status("IMBALANCED")])
    cs.player.block = 30
    turn(cs)
    rock = cs.enemies[0]
    assert cs.player.current_hp == 80 and rock.move_id == STUNNED
    turn(cs)
    assert rock.move_id == "HEADBUTT" and cs.player.current_hp == 80
    cs.player.block = 0
    turn(cs)
    assert cs.player.current_hp == 65 and rock.move_id == "HEADBUTT"

def test_rock_with_a_partly_blocked_attack_does_not_stumble():
    cs = at("BOWLBUG_ROCK", "HEADBUTT", status=[status("IMBALANCED")])
    cs.player.block = 10
    turn(cs)
    assert cs.player.current_hp == 75 and cs.enemies[0].move_id == "HEADBUTT"


# ---------------------------------------------------------------- the Obscura
def obscura(move="ILLUSION"):
    return at("THE_OBSCURA", move)

def boss(cs):
    return next(e for e in cs.enemies if e.enemy_id == "THE_OBSCURA_0")      # a Parafright joins at the front

def test_obscura_summons_a_parafright_with_illusion():
    cs = obscura()
    turn(cs)
    assert [e.enemy_id for e in cs.enemies] == ["PARAFRIGHT_0", "THE_OBSCURA_0"]
    p = cs.enemies[0]
    assert p.max_hp == 21 and p.move_id == "SLAM" and p.num_attacks == 1
    assert StatusId.ILLUSION in p.status and p.is_minion

def test_obscura_never_repeats_a_move_and_uses_all_three():
    seen = set()
    for seed in range(40):
        from sts2_lite import rng
        rng.seed(seed)
        cs = obscura("PIERCING_GAZE")
        for _ in range(6):
            before = boss(cs).move_id
            turn(cs)
            after = boss(cs).move_id
            assert after != before and after != "ILLUSION"
            seen.add(after)
    assert seen == {"PIERCING_GAZE", "WAIL", "HARDENING_STRIKE"}

def test_wail_strengthens_the_whole_team():
    cs = obscura()
    turn(cs)                    # Parafright joins
    cs.enemies[1].move_id = "WAIL"
    cs.enemies[1].attack_damage = cs.enemies[1].num_attacks = 0
    turn(cs)
    assert all(e.status_amount(StatusId.STRENGTH) == 3 for e in cs.enemies)

def test_hardening_strike_blocks():
    cs = obscura("HARDENING_STRIKE")
    turn(cs)
    assert cs.player.current_hp == 74 and boss(cs).block == 6

def test_a_killed_parafright_comes_back():
    cs = obscura()
    turn(cs)
    sim = CombatSimulator(cs)
    cs.enemies[0].current_hp = 0
    sim.resolve_deaths()
    assert [e.enemy_id for e in cs.enemies] == ["THE_OBSCURA_0"]
    sim._play_enemy_turn()
    assert sorted(e.enemy_id for e in cs.enemies) == ["PARAFRIGHT_0", "THE_OBSCURA_0"]
    assert next(e for e in cs.enemies if e.enemy_id == "PARAFRIGHT_0").current_hp == 21

def test_a_loaded_obscura_state_without_its_parafright_revives_it():
    cs = at("THE_OBSCURA", "PIERCING_GAZE", log=["ILLUSION_MOVE", "PIERCING_GAZE_MOVE"])
    assert cs.revivals == [("PARAFRIGHT", 0)]

def test_the_fight_is_won_when_only_the_parafright_is_left():
    cs = obscura()
    turn(cs)
    sim = CombatSimulator(cs)
    cs.enemies[1].current_hp = 0
    sim.resolve_deaths()
    sim._check_is_over()
    assert sim.is_over and cs.won


# ---------------------------------------------------------------- Exoskeleton, Hunter Killer, Entomancer, Prism, Louse
from sts2_lite import rng
from sts2_lite.card import Card, CardType, TargetType


def make_card(card_id, name, card_type, cost, target):
    c = Card()
    c.card_id, c.name, c.type = card_id, name, card_type
    c.energy_cost, c.target_type = cost, target
    c.is_upgraded = False
    c.is_unplayable = False
    return c

def defend():
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.Self)

def strike():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def follow_ups(monster, move, seeds=60, ascension=0):
    """Every move that can follow `move` over many seeds."""
    seen = set()
    for seed in range(seeds):
        rng.seed(seed)
        cs = at(monster, move, ascension)
        turn(cs)
        seen.add(cs.enemies[0].move_id)
    return seen

def test_exoskeleton_values():
    t = MOVE_TABLES["EXOSKELETON"](0)
    assert (t["SKITTER"].damage, t["SKITTER"].hits, t["MANDIBLES"].damage) == (1, 3, 8)
    t = MOVE_TABLES["EXOSKELETON"](9)
    assert (t["SKITTER"].hits, t["MANDIBLES"].damage) == (4, 9)

def test_exoskeleton_follow_ups():
    assert follow_ups("EXOSKELETON", "SKITTER") == {"MANDIBLES"}
    assert follow_ups("EXOSKELETON", "MANDIBLES") == {"ENRAGE"}
    assert follow_ups("EXOSKELETON", "ENRAGE") == {"SKITTER", "MANDIBLES"}

def test_exoskeleton_enrage_gives_strength_and_hard_to_kill_caps_hits():
    cs = at("EXOSKELETON", "ENRAGE", status=[status("HARD_TO_KILL", 9)])
    turn(cs)
    ex = cs.enemies[0]
    assert ex.status_amount(StatusId.STRENGTH) == 2
    ex.apply_damage(30, cs.player, True)
    assert ex.current_hp == 40 - 9

def test_hunter_killer_follow_ups():
    assert follow_ups("HUNTER_KILLER", "TENDERIZING_GOOP") == {"BITE", "PUNCTURE"}
    assert follow_ups("HUNTER_KILLER", "BITE") == {"PUNCTURE"}

def test_hunter_killer_punctures_at_most_twice_in_a_row():
    for seed in range(60):
        rng.seed(seed)
        cs = at("HUNTER_KILLER", "PUNCTURE", log=["PUNCTURE_MOVE", "PUNCTURE_MOVE"])
        assert cs.enemies[0].move_streak == 2
        turn(cs)
        assert cs.enemies[0].move_id == "BITE"

def test_goop_applies_tender():
    cs = at("HUNTER_KILLER", "TENDERIZING_GOOP")
    turn(cs)
    assert cs.player.status_amount(StatusId.TENDER) == 1

def test_tender_costs_strength_and_dexterity_per_card_until_the_turn_ends():
    cs = at("HUNTER_KILLER", "BITE", status=[])
    cs.player.status[StatusId.TENDER] = StatusInstance(StatusId.TENDER, 1)
    cs.player.hand = [defend(), defend(), strike()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.STRENGTH) == -2 and cs.player.status_amount(StatusId.DEXTERITY) == -2
    sim.end_turn()
    assert cs.player.status_amount(StatusId.STRENGTH) == 0 and cs.player.status_amount(StatusId.DEXTERITY) == 0

def test_entomancer_cycle_and_values():
    assert moves_over(at("ENTOMANCER", "BEES"), 4) == ["BEES", "SPEAR", "PHEROMONE_SPIT", "BEES", "SPEAR"]
    t = MOVE_TABLES["ENTOMANCER"](9)
    assert (t["BEES"].damage, t["BEES"].hits, t["SPEAR"].damage) == (3, 8, 20)

def test_pheromone_spit_grows_the_hive_then_only_strength():
    cs = at("ENTOMANCER", "PHEROMONE_SPIT", status=[status("PERSONAL_HIVE", 1)])
    e = cs.enemies[0]
    for hive, strength in ((2, 1), (3, 2), (3, 4)):
        e.move_id = "PHEROMONE_SPIT"
        turn(cs)
        assert (e.status_amount(StatusId.PERSONAL_HIVE), e.status_amount(StatusId.STRENGTH)) == (hive, strength)

def test_hitting_the_entomancer_shuffles_dazed_into_the_draw_pile():
    cs = at("ENTOMANCER", "BEES", status=[status("PERSONAL_HIVE", 2)])
    cs.player.hand = [strike()]
    CombatSimulator(cs).play_card(0, 0)
    assert [c.card_id for c in cs.player.draw_pile] == [CardId.DAZED] * 2

def test_prism_cycle():
    assert moves_over(at("INFESTED_PRISM", "JAB"), 4) == ["JAB", "RADIATE", "WHIRLWIND", "PULSATE", "JAB"]

def test_prism_pulsate_blocks_and_adds_vital_spark():
    cs = at("INFESTED_PRISM", "PULSATE", status=[status("VITAL_SPARK", 2)])
    turn(cs)
    p = cs.enemies[0]
    assert (p.block, p.status_amount(StatusId.VITAL_SPARK), cs.player.current_hp) == (20, 4, 72)
    assert MOVE_TABLES["INFESTED_PRISM"](8)["PULSATE"].block == 22

def test_playing_a_skill_taints_the_player_until_the_enemies_have_acted():
    cs = at("INFESTED_PRISM", "JAB", status=[status("VITAL_SPARK", 2)])
    cs.player.hand = [defend(), strike()]
    sim = CombatSimulator(cs)
    sim.play_card(1, 0)         # attacks do not
    assert StatusId.TAINTED not in cs.player.status
    sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.TAINTED) == 2
    cs.player.block = 0
    sim._play_enemy_turn()
    assert StatusId.TAINTED not in cs.player.status
    assert cs.player.current_hp == 80 - 17          # the jab hit for 15 + 2 Tainted

def test_tainted_jab_hits_harder():
    cs = at("INFESTED_PRISM", "JAB", status=[status("VITAL_SPARK", 2)])
    cs.player.status[StatusId.TAINTED] = StatusInstance(StatusId.TAINTED, 2)
    cs.player.block = 0
    turn(cs)
    assert cs.player.current_hp == 80 - 17

def test_louse_progenitor_cycle_and_values():
    assert moves_over(at("LOUSE_PROGENITOR", "WEB_CANNON"), 3) == ["WEB_CANNON", "CURL_AND_GROW", "POUNCE", "WEB_CANNON"]
    t = MOVE_TABLES["LOUSE_PROGENITOR"](8)
    assert t["CURL_AND_GROW"].block == 18 and MOVE_TABLES["LOUSE_PROGENITOR"](0)["CURL_AND_GROW"].block == 14

def test_web_cannon_hits_and_frails():
    cs = at("LOUSE_PROGENITOR", "WEB_CANNON")
    turn(cs)
    assert cs.player.current_hp == 71 and cs.player.status_amount(StatusId.FRAIL) == 2

def test_curl_and_grow_blocks_and_strengthens():
    cs = at("LOUSE_PROGENITOR", "CURL_AND_GROW", status=[status("CURL_UP", 14)])
    turn(cs)
    e = cs.enemies[0]
    assert e.block == 14 and e.status_amount(StatusId.STRENGTH) == 5

def test_curl_up_pays_out_once_after_the_card():
    cs = at("LOUSE_PROGENITOR", "WEB_CANNON", status=[status("CURL_UP", 14)])
    cs.player.hand = [strike(), strike()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.enemies[0].block == 14 and StatusId.CURL_UP not in cs.enemies[0].status


# ---------------------------------------------------------------- Tunneler, Slumbering Beetle, Ovicopter, Tough Egg, Thieving Hopper
from sts2_lite.card import CARD_RARITY, CardRarity


def test_tunneler_cycle_and_burrow():
    assert moves_over(at("TUNNELER", "BITE"), 3) == ["BITE", "BURROW", "BELOW", "BELOW"]
    cs = at("TUNNELER", "BURROW")
    turn(cs)
    t = cs.enemies[0]
    assert t.block == 32 and StatusId.BURROWED in t.status
    assert MOVE_TABLES["TUNNELER"](8)["BURROW"].block == 37

def test_a_burrowed_tunneler_keeps_its_block_and_hits_from_below():
    cs = at("TUNNELER", "BURROW")
    turn(cs)
    turn(cs)
    t = cs.enemies[0]
    assert t.block == 32 and cs.player.current_hp == 80 - 23

def test_breaking_the_burrow_block_stuns_the_tunneler_into_a_bite():
    cs = at("TUNNELER", "BURROW")
    turn(cs)
    t = cs.enemies[0]
    t.apply_damage(32, cs.player, True)
    assert StatusId.BURROWED not in t.status and t.block == 0
    assert t.move_id == STUNNED
    turn(cs)
    assert t.move_id == "BITE" and cs.player.current_hp == 80

def test_beetle_snores_while_it_slumbers_and_wakes_after_three_enemy_turns():
    cs = at("SLUMBERING_BEETLE", "SNORE", status=[status("SLUMBER", 3), status("PLATING", 15)])
    b = cs.enemies[0]
    seen = []
    for _ in range(5):
        turn(cs)
        seen.append(b.move_id)
    assert seen == ["SNORE", "SNORE", "SNORE", "ROLL_OUT", "ROLL_OUT"]
    assert StatusId.SLUMBER not in b.status and StatusId.PLATING not in b.status

def test_hits_wake_the_beetle_into_a_stun_and_then_a_roll():
    cs = at("SLUMBERING_BEETLE", "SNORE", status=[status("SLUMBER", 3), status("PLATING", 15)])
    b = cs.enemies[0]
    for _ in range(3):
        b.apply_damage(1, cs.player, True)
    assert b.move_id == STUNNED and b.after_stun == "ROLL_OUT"
    assert StatusId.PLATING in b.status
    turn(cs)
    assert b.move_id == "ROLL_OUT" and StatusId.PLATING not in b.status and cs.player.current_hp == 80

def test_blocked_hits_do_not_wake_the_beetle():
    cs = at("SLUMBERING_BEETLE", "SNORE", status=[status("SLUMBER", 1)])
    cs.enemies[0].block = 50
    cs.enemies[0].apply_damage(10, cs.player, True)
    assert cs.enemies[0].status_amount(StatusId.SLUMBER) == 1

def test_roll_out_hits_and_grows():
    cs = at("SLUMBERING_BEETLE", "ROLL_OUT")
    turn(cs)
    assert cs.player.current_hp == 64 and cs.enemies[0].status_amount(StatusId.STRENGTH) == 2

def test_ovicopter_lays_three_eggs_then_pastes():
    cs = at("OVICOPTER", "LAY_EGGS")
    turn(cs)
    eggs = [e for e in cs.enemies if e.enemy_id.startswith("TOUGH_EGG")]
    assert sorted(e.enemy_id for e in eggs) == ["TOUGH_EGG_0", "TOUGH_EGG_1", "TOUGH_EGG_2"]
    assert all(e.is_minion and 14 <= e.max_hp <= 18 and e.move_id == "HATCH" for e in eggs)
    ov = next(e for e in cs.enemies if e.enemy_id == "OVICOPTER_0")
    assert ov.move_id == "SMASH"
    turn(cs)
    assert ov.move_id == "TENDERIZER"
    turn(cs)
    assert ov.move_id == "NUTRITIONAL_PASTE"        # four creatures are alive: too crowded to lay
    assert cs.player.status_amount(StatusId.VULNERABLE) == 2

def test_ovicopter_lays_again_when_the_eggs_are_gone():
    cs = at("OVICOPTER", "TENDERIZER")
    turn(cs)
    assert cs.enemies[0].move_id == "LAY_EGGS"

def test_ovicopter_never_has_more_than_five_eggs():
    cs = at("OVICOPTER", "LAY_EGGS")
    for _ in range(3):
        ov = next(e for e in cs.enemies if e.enemy_id == "OVICOPTER_0")
        ov.move_id = "LAY_EGGS"
        turn(cs)
    assert len([e for e in cs.enemies if e.enemy_id.startswith("TOUGH_EGG")]) == 5

def test_an_egg_hatches_into_a_hatchling_that_nibbles():
    cs = at("TOUGH_EGG", "HATCH", status=[status("HATCH", 1), status("MINION")])
    egg = cs.enemies[0]
    turn(cs)
    assert 19 <= egg.max_hp <= 22 and egg.current_hp == egg.max_hp
    assert set(egg.status) == {StatusId.MINION} and egg.move_id == "NIBBLE" and cs.player.current_hp == 80
    turn(cs)
    assert cs.player.current_hp == 76

def test_hopper_cycle_ends_in_an_escape():
    cs = at("THIEVING_HOPPER", "THIEVERY")
    cs.enemies.append(at("PARAFRIGHT", "SLAM").enemies[0])      # something else keeps the fight going
    hopper = cs.enemies[0]
    moves = [hopper.move_id]
    for _ in range(4):
        turn(cs)
        moves.append(hopper.move_id)
    assert moves == ["THIEVERY", "FLUTTER", "HAT_TRICK", "NAB", "ESCAPE"]
    turn(cs)
    assert hopper not in cs.enemies

def test_thievery_takes_an_uncommon_card_first():
    from sts2_lite.card import GENERATABLE_CARDS
    cs = at("THIEVING_HOPPER", "THIEVERY")
    strike_card, defend_card = strike(), defend()
    uncommon = next(c for c, r in CARD_RARITY.items() if r == CardRarity.Uncommon and c in GENERATABLE_CARDS)
    other = Card.create_generated(uncommon)
    other.generated = False         # as if it were a card of the deck
    cs.player.draw_pile = [strike_card, defend_card]
    cs.player.discard_pile = [other, strike()]
    turn(cs)
    assert other not in cs.player.discard_pile and len(cs.player.discard_pile) == 1
    assert len(cs.player.draw_pile) == 2 and cs.enemies[0].status_amount(StatusId.SWIPE) == 1
    assert cs.player.current_hp == 80 - 17

def test_thievery_falls_back_to_basic_cards_and_ignores_status_cards():
    cs = at("THIEVING_HOPPER", "THIEVERY")
    cs.player.draw_pile = [Card.create(CardId.DAZED)]
    cs.player.discard_pile = [strike()]
    turn(cs)
    assert cs.player.discard_pile == [] and len(cs.player.draw_pile) == 1

def test_thievery_with_nothing_to_take_still_hits():
    cs = at("THIEVING_HOPPER", "THIEVERY")
    turn(cs)
    assert cs.player.current_hp == 63 and StatusId.SWIPE not in cs.enemies[0].status

def test_flutter_halves_damage_and_five_hits_stun_the_hopper():
    from sts2_lite.damage import modify_damage
    cs = at("THIEVING_HOPPER", "FLUTTER")
    turn(cs)
    h = cs.enemies[0]
    assert h.status_amount(StatusId.FLUTTER) == 5 and modify_damage(10, cs.player, h) == 5
    h.apply_damage(5, cs.player, True)
    assert h.current_hp == 40 - 5
    for _ in range(4):
        h.apply_damage(3, cs.player, True)
    assert StatusId.FLUTTER not in h.status and h.move_id == STUNNED and h.after_stun == "NAB"      # the stun replaces HAT_TRICK, so it is skipped


def test_thievery_cannot_take_a_card_made_this_fight():
    cs = at("THIEVING_HOPPER", "THIEVERY")
    made = Card.create(CardId.WOUND)
    made.generated = True
    kept = strike()
    cs.player.draw_pile = [made]
    cs.player.discard_pile = [kept]
    turn(cs)
    assert cs.player.draw_pile == [made] and cs.player.discard_pile == []

def test_cards_the_game_marks_as_generated_are_read_from_the_bridge():
    from sts2_lite.card import GENERATABLE_CARDS
    assert Card.from_dict({"id": "STRIKE_IRONCLAD", "type": "Attack", "name": "Strike", "can_play": True, "cost": "1",
                           "is_upgraded": False, "target_type": "AnyEnemy", "generated": True}).generated
    assert Card.create(CardId.DAZED).generated and Card.create_generated(next(iter(GENERATABLE_CARDS))).generated
    assert not strike().generated and Card.create_copy(Card.create(CardId.DAZED)).generated


def test_a_tunneler_stunned_by_thorns_during_its_own_attack_finishes_the_move():
    """Found by fuzzing: thorns break the Burrowed block mid-attack, which stuns it before the move is over (was a KeyError)."""
    cs = at("TUNNELER", "BELOW", status=[status("BURROWED")])
    tunneler = cs.enemies[0]
    tunneler.block = 3
    cs.player.apply_status(StatusId.THORNS, 10)
    cs.player.block = 0
    turn(cs)
    assert tunneler.move_id == "STUNNED" and tunneler.after_stun == "BITE" and StatusId.BURROWED not in tunneler.status
    turn(cs)            # the stunned turn does nothing, then it bites
    assert tunneler.move_id == "BITE"
