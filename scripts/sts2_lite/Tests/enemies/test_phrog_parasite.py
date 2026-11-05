"""Phrog Parasite, Wriggler, Infection, summoning and death hooks. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import rng
from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.enemy import Enemy
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.Tests import captures
from sts2_lite.status import StatusId


def phrog(name):
    return captures.load("phrog_parasite", name)

def enemy_turn(cs):
    CombatSimulator(cs)._play_enemy_turn()

def discard_ids(cs):
    return [c.card_id for c in cs.player.discard_pile]

def index_of(cs, card_id):
    return next(i for i, c in enumerate(cs.player.hand) if c.card_id.name == card_id)

def kill_phrog(cs):
    """Play a Strike at the Phrog while it has 1 hit point."""
    cs.enemies[0].current_hp = 1
    sim = CombatSimulator(cs)
    sim.play_card(index_of(cs, "STRIKE_IRONCLAD"), 0)
    return sim


# ---------------------------------------------------------------- tables
def test_phrog_and_wriggler_have_tables():
    assert "PHROG_PARASITE" in MOVE_TABLES and "WRIGGLER" in MOVE_TABLES

def test_phrog_alternates_infect_and_lash():
    t = MOVE_TABLES["PHROG_PARASITE"](0)
    assert (t["INFECT"].next_move, t["LASH"].next_move) == ("LASH", "INFECT")

def test_phrog_values():
    t = MOVE_TABLES["PHROG_PARASITE"]
    assert t(0)["INFECT"].cards == ((CardId.INFECTION, 3),)
    assert (t(0)["LASH"].damage, t(0)["LASH"].hits) == (4, 4)
    assert (t(9)["LASH"].damage, t(9)["LASH"].hits) == (5, 4)
    assert t(8)["LASH"].damage == 4

def test_wriggler_values():
    t = MOVE_TABLES["WRIGGLER"]
    assert (t(0)["BITE"].damage, t(9)["BITE"].damage, t(8)["BITE"].damage) == (6, 7, 6)
    assert t(0)["WRIGGLE"].cards == ((CardId.INFECTION, 1),)
    assert t(0)["WRIGGLE"].self_status == ((StatusId.STRENGTH, 2),)
    assert t(0)["SPAWNED"].hits == 0

def test_wriggler_opening_depends_on_slot():
    opening = MOVE_TABLES["WRIGGLER"](0)["SPAWNED"].next_by_slot
    assert opening == ("BITE", "WRIGGLE", "BITE", "WRIGGLE")


# ---------------------------------------------------------------- Phrog captures (ascension 0)
def test_captured_infect_turn():
    cs = phrog("infect")
    e = cs.enemies[0]
    assert (e.move_id, e.num_attacks) == ("INFECT", 0)
    assert e.status[StatusId.INFESTED].amount == 4
    assert e.current_hp == 61

def test_captured_lash_turn():
    e = phrog("lash").enemies[0]
    assert (e.move_id, e.attack_damage, e.num_attacks) == ("LASH", 4, 4)

def test_infect_adds_three_infections_to_the_discard_pile():
    cs = phrog("infect")
    enemy_turn(cs)
    assert discard_ids(cs) == [CardId.INFECTION] * 3
    assert cs.player.current_hp == 80
    assert cs.enemies[0].move_id == "LASH"

def test_lash_hits_four_times():
    cs = phrog("lash")
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 16
    assert cs.enemies[0].move_id == "INFECT"

def test_phrog_uses_no_randomness():
    cs = phrog("infect")
    before = rng.calls
    for _ in range(4):
        enemy_turn(cs)
    assert rng.calls == before


# ---------------------------------------------------------------- Infection
def test_created_infection_matches_the_real_card():
    real = next(c for c in phrog("infection_in_hand").player.hand if c.card_id == CardId.INFECTION)
    made = Card.create_infection()
    for f in ("card_id", "name", "type", "energy_cost", "target_type", "is_upgraded", "is_unplayable"):
        assert getattr(made, f) == getattr(real, f), f
    assert made.type == CardType.Status and made.is_unplayable

def test_infection_in_hand_cannot_be_played():
    cs = phrog("infection_in_hand")
    i = index_of(cs, "INFECTION")
    sim = CombatSimulator(cs)
    assert not any(a.get("card_index") == i for a in sim.get_available_actions())

def test_infection_hurts_at_end_of_turn_if_still_in_hand():
    cs = phrog("infection_in_hand")
    cs.enemies.clear()
    cs.enemies.append(Enemy.spawn("WRIGGLER", 0, 0))      # a harmless target
    cs.enemies[0].num_attacks = 0
    hp = cs.player.current_hp
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert hp - cs.player.current_hp == 3

def test_two_infections_hurt_twice():
    cs = phrog("lash")
    cs.player.hand = [Card.create_infection(), Card.create_infection()]
    cs.enemies[0].num_attacks = 0
    cs.enemies[0].moves = None
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 80 - 6

def test_infection_damage_is_absorbed_by_block():
    cs = phrog("lash")
    cs.player.hand = [Card.create_infection()]
    cs.player.block = 2
    cs.enemies[0].num_attacks = 0
    cs.enemies[0].moves = None
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 80 - 1

def test_infection_in_the_discard_pile_does_nothing():
    cs = phrog("lash")
    cs.player.hand = []
    cs.enemies[0].num_attacks = 0
    cs.enemies[0].moves = None
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 80

def test_infection_can_end_the_fight_before_enemies_act():
    cs = phrog("lash")
    cs.player.current_hp = 3
    cs.player.hand = [Card.create_infection()]
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert sim.is_over and cs.player.current_hp <= 0
    assert cs.enemies[0].move_id == "LASH"        # nobody acted

def test_infection_goes_to_the_discard_pile_after_the_turn():
    cs = phrog("lash")
    cs.player.hand = [Card.create_infection()]
    cs.player.draw_pile = [Card.create_slimed() for _ in range(6)]
    cs.enemies[0].num_attacks = 0
    cs.enemies[0].moves = None
    CombatSimulator(cs).end_turn()
    assert any(c.card_id == CardId.INFECTION for c in cs.player.discard_pile)


# ---------------------------------------------------------------- summoning and death hooks
def test_killing_the_phrog_summons_four_wrigglers():
    cs = phrog("lash")
    sim = kill_phrog(cs)
    assert [e.enemy_id for e in cs.enemies] == [f"WRIGGLER_{i}" for i in range(4)]
    assert not sim.is_over

def test_summoned_wrigglers_start_stunned():
    cs = phrog("lash")
    kill_phrog(cs)
    assert all(e.move_id == "SPAWNED" and e.num_attacks == 0 for e in cs.enemies)

def test_summoned_wrigglers_have_random_hit_points_in_range():
    seen = set()
    for seed in range(40):
        rng.seed(seed)
        cs = phrog("lash")
        kill_phrog(cs)
        for e in cs.enemies:
            assert 17 <= e.max_hp <= 21 and e.current_hp == e.max_hp
            seen.add(e.max_hp)
    assert len(seen) > 1

def test_tough_ascension_wrigglers_have_more_hit_points():
    for seed in range(40):
        rng.seed(seed)
        cs = phrog("lash")
        cs.ascension = 8
        kill_phrog(cs)
        assert all(18 <= e.max_hp <= 22 for e in cs.enemies)

def test_summoning_uses_the_shared_rng():
    cs = phrog("lash")
    before = rng.calls
    kill_phrog(cs)
    assert rng.calls > before

def test_the_fight_continues_until_every_wriggler_is_dead():
    cs = phrog("lash")
    sim = kill_phrog(cs)
    for e in cs.enemies:
        e.current_hp = 0
    sim.resolve_deaths()
    sim._check_is_over()
    assert sim.is_over and cs.enemies == []

def test_wrigglers_do_not_act_the_turn_they_appear():
    cs = phrog("lash")
    kill_phrog(cs)
    hp = cs.player.current_hp
    CombatSimulator(cs)._play_enemy_turn()
    assert cs.player.current_hp == hp and discard_ids(cs).count(CardId.INFECTION) == 3

def test_an_enemy_summoned_during_the_enemy_turn_waits():
    cs = phrog("lash")
    sim = CombatSimulator(cs)
    original = Enemy.perform_turn
    done = []
    def summoning(self, combat):
        if not done:
            done.append(True)
            combat.summon(Enemy.spawn("WRIGGLER", 0, 0))
        original(self, combat)
    Enemy.perform_turn = summoning
    try:
        sim._play_enemy_turn()
    finally:
        Enemy.perform_turn = original
    assert len(cs.enemies) == 2 and cs.enemies[1].move_id == "SPAWNED"

def test_other_deaths_summon_nothing():
    cs = CombatState.from_dict({
        "round": 1, "energy": 3, "max_energy": 3,
        "player": {"max_hp": 80, "hp": 80, "block": 0, "status": [], "hand": [], "draw_pile": [],
                   "discard_pile": [], "deck": []},
        "enemies": [{"entity_id": "NIBBIT_0", "max_hp": 44, "hp": 0, "block": 0, "status": [],
                     "intents": [{"type": "Attack", "label": "12"}]}],
    })
    CombatSimulator(cs).resolve_deaths()
    assert cs.enemies == []

def test_resolve_deaths_runs_a_death_effect_once():
    cs = phrog("lash")
    cs.enemies[0].current_hp = 0
    sim = CombatSimulator(cs)
    sim.resolve_deaths()
    sim.resolve_deaths()
    assert len(cs.enemies) == 4

def test_wrigglers_can_be_hit_after_resolving_deaths_mid_card():
    cs = phrog("lash")
    sim = CombatSimulator(cs)
    cs.enemies[0].current_hp = 0                  # first hit of a multi-hit card kills it
    sim.resolve_deaths()                          # the card resolves deaths between hits
    target = cs.enemies[0]
    target.apply_damage(5)
    assert target.current_hp == target.max_hp - 5

def test_second_hit_of_a_single_target_card_does_not_reach_the_wrigglers():
    cs = phrog("lash")
    cs.enemies[0].current_hp = 3
    sim = CombatSimulator(cs)
    sim.play_card(index_of(cs, "TWIN_STRIKE"), 0)
    assert len(cs.enemies) == 4
    assert all(e.current_hp == e.max_hp for e in cs.enemies)

def test_summon_adds_to_the_end_of_the_enemy_list():
    cs = phrog("lash")
    sim = CombatSimulator(cs)
    w = Enemy.spawn("WRIGGLER", 0, 0)
    sim.summon(w)
    assert cs.enemies[-1] is w and len(cs.enemies) == 2


# ---------------------------------------------------------------- Wrigglers (captures, ascension 0)
def test_captured_wrigglers_are_stunned():
    cs = phrog("after_killed")
    assert [e.move_id for e in cs.enemies] == ["SPAWNED"] * 4
    assert [e.slot for e in cs.enemies] == [0, 1, 2, 3]
    assert [e.current_hp for e in cs.enemies] == [20, 21, 19, 18]

def test_stun_turn_does_nothing_and_opens_by_slot():
    cs = phrog("after_killed")
    discard = len(cs.player.discard_pile)
    enemy_turn(cs)
    assert cs.player.current_hp == 80 and len(cs.player.discard_pile) == discard
    assert [e.move_id for e in cs.enemies] == ["BITE", "WRIGGLE", "BITE", "WRIGGLE"]

def test_opening_moves_match_the_real_game():
    cs = phrog("wrigglers_move")
    assert [e.move_id for e in cs.enemies] == ["BITE", "WRIGGLE", "BITE", "WRIGGLE"]

def test_captured_bite_turn_reads_damage():
    e = phrog("wrigglers_move").enemies[0]
    assert (e.attack_damage, e.num_attacks) == (6, 1)

def test_wriggler_turn_bites_and_wriggles():
    cs = phrog("wrigglers_move")
    discard = len(cs.player.discard_pile)
    enemy_turn(cs)
    assert cs.player.current_hp == 80 - 12
    assert discard_ids(cs).count(CardId.INFECTION) == 2 and len(cs.player.discard_pile) == discard + 2
    assert [e.status_amount(StatusId.STRENGTH) for e in cs.enemies] == [0, 2, 0, 2]
    assert [e.move_id for e in cs.enemies] == ["WRIGGLE", "BITE", "WRIGGLE", "BITE"]

def test_strength_makes_the_next_bite_hit_harder():
    cs = phrog("wrigglers_move")
    enemy_turn(cs)
    hp = cs.player.current_hp
    enemy_turn(cs)
    assert hp - cs.player.current_hp == 8 + 8

def test_captured_second_wriggler_round():
    cs = phrog("infection_in_hand")
    assert [e.move_id for e in cs.enemies] == ["WRIGGLE", "BITE", "WRIGGLE", "BITE"]
    assert cs.enemies[1].status_amount(StatusId.STRENGTH) == 2
    assert cs.enemies[1].attack_damage == 6 and cs.enemies[1].num_attacks == 1

def test_captured_second_round_bites_for_the_displayed_damage():
    cs = phrog("infection_in_hand")
    hp = cs.player.current_hp
    enemy_turn(cs)
    assert hp - cs.player.current_hp == 8 + 8

def test_wrigglers_use_no_randomness_once_spawned():
    cs = phrog("after_killed")
    before = rng.calls
    for _ in range(5):
        enemy_turn(cs)
    assert rng.calls == before

def test_wriggler_number_in_the_id_sets_its_slot():
    assert phrog("after_killed").enemies[3].slot == 3

def test_clone_keeps_slot_and_ascension():
    cs = phrog("after_killed")
    cs.ascension = 8
    clone = CombatState.deepcopy(cs)
    assert clone.ascension == 8 and [e.slot for e in clone.enemies] == [0, 1, 2, 3]

def test_captured_states_offer_actions():
    for name in ("infect", "lash", "after_killed", "wrigglers_move", "infection_in_hand"):
        assert CombatSimulator(phrog(name)).get_available_actions()
