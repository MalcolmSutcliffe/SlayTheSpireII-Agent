"""The Regent: Stars, star-cost cards, Forge and the Sovereign Blade, the character's run setup and pools."""
import random

import pytest

from sts2_lite.card import Card, CardId, CardType
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.relic.combat_start import Opening
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_state


def gen(card_id, upgraded=False):
    return Card.create_generated(card_id, upgraded)

def one_enemy(hand, hp=100, stars=0):
    cs = make_state(hand, enemy_count=1, enemy_hp=hp)
    cs.player.stars = stars
    cs.player.character = "REGENT"
    return cs

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim


# ------------------------------------------------------------ starter cards
@pytest.mark.parametrize("upgraded, damage", [(False, 6), (True, 9)])
def test_strike_regent(upgraded, damage):
    cs = one_enemy([gen(CardId.STRIKE_REGENT, upgraded)])
    play(cs)
    assert cs.enemies[0].current_hp == 100 - damage and cs.energy == 2

@pytest.mark.parametrize("upgraded, block", [(False, 5), (True, 8)])
def test_defend_regent(upgraded, block):
    cs = one_enemy([gen(CardId.DEFEND_REGENT, upgraded)])
    play(cs)
    assert cs.player.block == block

@pytest.mark.parametrize("upgraded, damage", [(False, 8), (True, 12)])
def test_falling_star_costs_two_stars_and_debuffs(upgraded, damage):
    cs = one_enemy([gen(CardId.FALLING_STAR, upgraded)], stars=3)
    play(cs)
    enemy = cs.enemies[0]
    assert cs.player.stars == 1 and cs.energy == 3
    assert enemy.status_amount(StatusId.WEAK) == 1 and enemy.status_amount(StatusId.VULNERABLE) == 1
    assert enemy.current_hp == 100 - damage

@pytest.mark.parametrize("upgraded, stars", [(False, 2), (True, 3)])
def test_venerate_gains_stars(upgraded, stars):
    cs = one_enemy([gen(CardId.VENERATE, upgraded)], stars=1)
    play(cs)
    assert cs.player.stars == 1 + stars and cs.energy == 2


# ------------------------------------------------------------ Stars
def test_a_card_needs_the_stars_it_costs():
    cs = one_enemy([gen(CardId.FALLING_STAR)], stars=1)
    sim = CombatSimulator(cs)
    assert not [a for a in sim.get_available_actions() if a["action"] == "play_card"]
    with pytest.raises(Exception):
        sim.play_card(0, 0)
    cs.player.stars = 2
    assert [a for a in sim.get_available_actions() if a["action"] == "play_card"]

def test_stars_are_kept_between_turns():
    cs = one_enemy([gen(CardId.STRIKE_REGENT)], stars=4)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert cs.player.stars == 4

def test_stars_spent_are_counted_for_the_turn():
    cs = one_enemy([gen(CardId.FALLING_STAR)], stars=2)
    play(cs)
    assert cs.player.stars_spent_this_turn == 2

def test_a_free_play_costs_no_stars():
    cs = one_enemy([gen(CardId.FALLING_STAR)], stars=0)
    CombatSimulator(cs).auto_play(cs.player.hand[0])
    assert cs.player.stars == 0 and cs.enemies[0].current_hp == 92


# ------------------------------------------------------------ Forge and the Sovereign Blade
def test_forge_makes_the_blade_and_grows_it():
    cs = one_enemy([])
    sim = CombatSimulator(cs)
    sim.forge(5)
    [blade] = cs.player.hand
    assert blade.card_id is CardId.SOVEREIGN_BLADE and blade.bonus_damage == 5
    sim.forge(3)
    assert cs.player.hand[0].bonus_damage == 8 and len(cs.player.hand) == 1

def test_the_blade_hits_for_ten_plus_forge():
    cs = one_enemy([])
    sim = CombatSimulator(cs)
    sim.forge(4)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 86 and cs.energy == 1
    assert cs.player.exhaust_pile == [] and len(cs.player.discard_pile) == 1       # it is not Exhaust: it goes round again

def test_the_blade_is_retained_and_upgrade_makes_it_cost_one():
    blade = gen(CardId.SOVEREIGN_BLADE)
    assert CardId.SOVEREIGN_BLADE.keyword_mask & 16 and blade.energy_cost == 2
    assert blade.upgraded_copy().energy_cost == 1

def test_forge_grows_every_blade_including_an_exhausted_one():
    cs = one_enemy([])
    sim = CombatSimulator(cs)
    sim.forge(2)
    blade = cs.player.hand.pop()
    cs.player.exhaust_pile.append(blade)
    sim.forge(3)        # none is left unexhausted: a new one (10) joins, and both grow
    assert sorted(c.bonus_damage for c in cs.player.hand) == [3]
    assert cs.player.exhaust_pile[0].bonus_damage == 5

def test_forge_with_a_blade_in_the_draw_pile_makes_no_new_one():
    cs = one_enemy([])
    cs.player.draw_pile.append(gen(CardId.SOVEREIGN_BLADE))
    CombatSimulator(cs).forge(6)
    assert not cs.player.hand and cs.player.draw_pile[0].bonus_damage == 6

def test_a_blade_loaded_from_the_game_reads_its_forge_from_the_text():
    cs = one_enemy([])
    raw = {"id": "SOVEREIGN_BLADE", "name": "Sovereign Blade", "type": "Attack", "cost": "2", "star_cost": None, "target_type": "AnyEnemy", "can_play": True,
           "is_upgraded": False, "description": "Deal 17 damage.", "card_keywords": ["Retain"]}
    cs.player.hand = [Card.from_dict(raw)]
    cs.player._read_growing_cards()
    assert cs.player.hand[0].bonus_damage == 7


# ------------------------------------------------------------ reading the game's state
def card_dict(card_id, cost, star_cost, can_play=True, reason=None, target="AnyEnemy", type_="Attack"):
    return {"id": card_id, "name": card_id.title(), "type": type_, "cost": cost, "star_cost": star_cost, "target_type": target,
            "can_play": can_play, "unplayable_reason": reason, "is_upgraded": False, "description": "", "card_keywords": []}

def test_star_cost_is_read_from_the_card():
    card = Card.from_dict(card_dict("FALLING_STAR", "0", "2"))
    assert card.star_cost == 2 and card.energy_cost == 0
    assert Card.from_dict(card_dict("STRIKE_REGENT", "1", None)).star_cost is None

@pytest.mark.parametrize("reason", ["EnergyCostTooHigh", "StarCostTooHigh", "EnergyCostTooHigh, StarCostTooHigh"])
def test_a_card_that_is_only_unaffordable_is_not_unplayable(reason):
    assert not Card.from_dict(card_dict("FALLING_STAR", "0", "2", can_play=False, reason=reason)).is_unplayable

def test_another_reason_still_makes_the_card_unplayable():
    assert Card.from_dict(card_dict("FALLING_STAR", "0", "2", can_play=False, reason="BlockedByHook, StarCostTooHigh")).is_unplayable

def test_a_copied_state_carries_the_stars():
    cs = one_enemy([gen(CardId.VENERATE)], stars=5)
    cs.player.stars_spent_this_turn = 2
    clone = CombatState.deepcopy(cs)
    assert (clone.player.stars, clone.player.stars_spent_this_turn) == (5, 2)

def test_stars_are_loaded_from_the_bridge_player():
    from sts2_lite.player import Player
    player = Player.from_dict({"max_hp": 75, "hp": 75, "block": 0, "status": [], "hand": [], "draw_pile": [], "discard_pile": [], "stars": 4,
                               "character": "The Regent"})
    assert player.stars == 4 and player.character == "REGENT"


# ------------------------------------------------------------ the character
def test_new_regent_run():
    from sts2_lite.run.state import new_run
    run = new_run(0, "REGENT")
    assert (run.character, run.hp, run.max_hp, run.gold, run.potion_slots) == ("REGENT", 75, 75, 99, 3)
    assert [r["id"] for r in run.relics] == ["DIVINE_RIGHT"]
    assert sorted(c["id"] for c in run.deck) == sorted(["STRIKE_REGENT"] * 4 + ["DEFEND_REGENT"] * 4 + ["FALLING_STAR", "VENERATE"])
    falling = next(c for c in run.deck if c["id"] == "FALLING_STAR")
    assert falling["cost"] in (0, "0") and falling["star_cost"] == 2

def test_divine_right_gives_three_stars_when_a_fight_starts():
    cs = one_enemy([])
    cs.player.stars = 0
    Opening([{"id": "DIVINE_RIGHT"}], "monster").before_combat(cs)
    assert cs.player.stars == 3

def test_relic_bag_holds_the_regents_relics():
    from sts2_lite.relic.bag import RelicGrabBag
    regent = {r for d in RelicGrabBag(random.Random(1), "REGENT").deques.values() for r in d}
    silent = {r for d in RelicGrabBag(random.Random(1), "SILENT").deques.values() for r in d}
    assert {"FENCING_MANUAL", "GALACTIC_DUST", "LUNAR_PASTRY", "MINI_REGENT", "ORANGE_DOUGH", "REGALITE", "VITRUVIAN_MINION"} <= regent
    assert "DIVINE_RIGHT" not in regent                     # a Starter is never in the bag
    assert not regent & {"TINGSHA", "RED_SKULL"} and "FENCING_MANUAL" not in silent

def test_character_of_title():
    from sts2_lite.character import character_of_title
    assert character_of_title("The Regent") == "REGENT"


# ============================================================ Commons
def hand_of(*cards):
    return [gen(c) if isinstance(c, CardId) else c for c in cards]

def enemy_status(cs, status, i=0):
    return cs.enemies[i].status_amount(status)

def test_astral_pulse_hits_every_enemy_twice_for_three_stars():
    cs = make_state(hand_of(CardId.ASTRAL_PULSE), enemy_count=2, enemy_hp=100)
    cs.player.stars = 3
    play(cs)
    assert [e.current_hp for e in cs.enemies] == [88, 88] and cs.player.stars == 0 and cs.energy == 3

def test_astral_pulse_upgraded():
    cs = make_state([gen(CardId.ASTRAL_PULSE, True)], enemy_count=1, enemy_hp=100)
    cs.player.stars = 3
    play(cs)
    assert cs.enemies[0].current_hp == 84

@pytest.mark.parametrize("upgraded, hits", [(False, 3), (True, 4)])
def test_celestial_might(upgraded, hits):
    cs = one_enemy([gen(CardId.CELESTIAL_MIGHT, upgraded)])
    play(cs)
    assert cs.enemies[0].current_hp == 100 - 6 * hits and cs.energy == 1

@pytest.mark.parametrize("upgraded, block", [(False, 7), (True, 10)])
def test_cloak_of_stars(upgraded, block):
    cs = one_enemy([gen(CardId.CLOAK_OF_STARS, upgraded)], stars=1)
    play(cs)
    assert cs.player.block == block and cs.player.stars == 0 and cs.energy == 3

def test_collision_course_adds_debris_that_can_be_played_and_exhausts():
    cs = one_enemy([gen(CardId.COLLISION_COURSE)])
    sim = play(cs)
    assert cs.enemies[0].current_hp == 90
    [debris] = cs.player.hand
    assert debris.card_id is CardId.DEBRIS and debris.type is CardType.Status and debris.exhausts
    sim.play_card(0, 0)
    assert cs.player.exhaust_pile and cs.player.exhaust_pile[0].card_id is CardId.DEBRIS and cs.energy == 2

def test_cosmic_indifference_puts_a_discarded_card_on_the_draw_pile():
    cs = one_enemy([gen(CardId.COSMIC_INDIFFERENCE)])
    cs.player.discard_pile = [gen(CardId.STRIKE_REGENT), gen(CardId.DEFEND_REGENT)]
    sim = play(cs)
    assert cs.player.block == 6 and cs.pending_choice is not None
    sim.choose_card(cs.pending_choice.indices[1])
    assert cs.player.draw_pile[-1].card_id is CardId.DEFEND_REGENT
    assert [c.card_id for c in cs.player.discard_pile] == [CardId.STRIKE_REGENT, CardId.COSMIC_INDIFFERENCE]

@pytest.mark.parametrize("upgraded, per_card", [(False, 2), (True, 3)])
def test_crescent_spear_counts_the_cards_with_a_star_cost(upgraded, per_card):
    spear = gen(CardId.CRESCENT_SPEAR, upgraded)
    cs = one_enemy([spear, gen(CardId.FALLING_STAR)], stars=1)
    cs.player.draw_pile = [gen(CardId.GUIDING_STAR), gen(CardId.STRIKE_REGENT)]
    cs.player.discard_pile = [gen(CardId.CLOAK_OF_STARS)]
    play(cs)
    assert cs.enemies[0].current_hp == 100 - (8 + per_card * 4)         # itself, Falling Star, Guiding Star, Cloak of Stars

def test_crush_under_hits_all_and_takes_their_strength_for_the_turn():
    cs = make_state([gen(CardId.CRUSH_UNDER)], enemy_count=2, enemy_hp=100)
    sim = play(cs)
    assert [e.current_hp for e in cs.enemies] == [92, 92]
    assert [e.status_amount(StatusId.STRENGTH) for e in cs.enemies] == [-1, -1]
    sim._return_temporary_strength(cs.enemies[0])
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 0

def test_gather_light():
    cs = one_enemy([gen(CardId.GATHER_LIGHT)], stars=0)
    play(cs)
    assert cs.player.block == 8 and cs.player.stars == 1

def test_glitterstream_gives_block_now_and_next_turn_with_dexterity():
    cs = one_enemy([gen(CardId.GLITTERSTREAM)])
    cs.player.apply_status(StatusId.DEXTERITY, 2)
    play(cs)
    assert cs.player.block == 13 and cs.player.status_amount(StatusId.BLOCK_NEXT_TURN) == 7 and cs.energy == 1

def test_glow_gains_stars_draws_and_draws_next_turn():
    cs = one_enemy([gen(CardId.GLOW)])
    cs.player.draw_pile = [gen(CardId.STRIKE_REGENT), gen(CardId.DEFEND_REGENT)]
    play(cs)
    assert cs.player.stars == 1 and len(cs.player.hand) == 1 and cs.player.status_amount(StatusId.DRAW_CARDS_NEXT_TURN) == 1

def test_guiding_star():
    cs = one_enemy([gen(CardId.GUIDING_STAR, True)], stars=2)
    play(cs)
    assert cs.enemies[0].current_hp == 87 and cs.player.stars == 1 and cs.player.status_amount(StatusId.DRAW_CARDS_NEXT_TURN) == 3

def test_hidden_cache_gives_stars_now_and_next_turn():
    cs = one_enemy([gen(CardId.HIDDEN_CACHE)])
    sim = play(cs)
    assert cs.player.stars == 1
    sim.end_turn()
    assert cs.player.stars == 1 + 3 and StatusId.STAR_NEXT_TURN not in cs.player.status

def test_know_thy_place_weakens_and_exposes_and_exhausts_until_upgraded():
    cs = one_enemy([gen(CardId.KNOW_THY_PLACE)])
    play(cs)
    assert enemy_status(cs, StatusId.WEAK) == 1 and enemy_status(cs, StatusId.VULNERABLE) == 1 and cs.energy == 3
    assert cs.player.exhaust_pile and not gen(CardId.KNOW_THY_PLACE, True).exhausts

def test_patter():
    cs = one_enemy([gen(CardId.PATTER, True)])
    play(cs)
    assert cs.player.block == 10 and cs.player.status_amount(StatusId.VIGOR) == 3

def test_photon_cut_draws_then_puts_one_back():
    cs = one_enemy([gen(CardId.PHOTON_CUT), gen(CardId.VENERATE)])
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT), gen(CardId.STRIKE_REGENT)]
    sim = play(cs)
    assert cs.enemies[0].current_hp == 90 and len(cs.player.hand) == 2
    pick = next(i for i in cs.pending_choice.indices if cs.player.hand[i].card_id is CardId.VENERATE)
    sim.choose_card(pick)
    assert [c.card_id for c in cs.player.hand] == [CardId.STRIKE_REGENT] and cs.player.draw_pile[-1].card_id is CardId.VENERATE

def test_refine_blade_forges_and_gives_energy_next_turn():
    cs = one_enemy([gen(CardId.REFINE_BLADE)])
    sim = play(cs)
    [blade] = cs.player.hand
    assert blade.bonus_damage == 8 and cs.player.status_amount(StatusId.ENERGY_NEXT_TURN) == 1
    sim.end_turn()
    assert cs.energy == 4        # 3 and the one from Refine Blade

def test_solar_strike_is_a_strike_that_gains_stars():
    cs = one_enemy([gen(CardId.SOLAR_STRIKE, True)])
    play(cs)
    assert cs.enemies[0].current_hp == 90 and cs.player.stars == 2 and gen(CardId.SOLAR_STRIKE).is_strike

def test_spoils_of_battle_forges_and_draws_two():
    cs = one_enemy([gen(CardId.SPOILS_OF_BATTLE)])
    cs.player.draw_pile = [gen(CardId.STRIKE_REGENT)] * 3
    play(cs)
    assert len(cs.player.hand) == 3 and any(c.card_id is CardId.SOVEREIGN_BLADE and c.bonus_damage == 6 for c in cs.player.hand)

def test_wrought_in_war_hits_then_forges():
    cs = one_enemy([gen(CardId.WROUGHT_IN_WAR)])
    play(cs)
    assert cs.enemies[0].current_hp == 93 and cs.player.hand[0].bonus_damage == 7

@pytest.mark.parametrize("upgraded, damage", [(False, 6), (True, 9)])
def test_begone_turns_a_card_into_a_minion_strike(upgraded, damage):
    cs = one_enemy([gen(CardId.BEGONE, upgraded), gen(CardId.DEFEND_REGENT), gen(CardId.VENERATE)])
    sim = play(cs)
    assert cs.pending_choice is not None
    sim.choose_card(cs.pending_choice.indices[0])
    strike = cs.player.hand[0]
    assert strike.card_id is CardId.MINION_STRIKE and strike.is_upgraded == upgraded and strike.is_strike and strike.exhausts
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT)]
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - damage and cs.player.exhaust_pile[0].card_id is CardId.MINION_STRIKE and len(cs.player.hand) == 2

def test_the_regent_reward_pool_holds_its_commons():
    from sts2_lite.rewards.cards import card_pool
    pool = card_pool("REGENT")
    assert len(pool["Common"]) == 20 and CardId.SOLAR_STRIKE in pool["Common"] and CardId.FALLING_STAR not in pool["Common"]

def test_hand_select_of_begone_is_read_from_the_prompt():
    from sts2_lite.Tests.card.test_card import make_state as _make
    cs = _make([gen(CardId.STRIKE_REGENT), gen(CardId.DEFEND_REGENT)], enemy_count=1)
    cs._load_hand_select({"mode": "simple_select", "prompt": "Choose a card to Transform.", "selected_cards": [],
                          "cards": [{"id": "STRIKE_REGENT", "is_upgraded": False}, {"id": "DEFEND_REGENT", "is_upgraded": False}]})
    assert cs.pending_choice.kind == "begone"


# ============================================================ the tables against the game's source
import re
from pathlib import Path

from sts2_lite.card.constants import STAR_COST
from sts2_lite.card.tables import REGENT_CARDS, TOKEN_CARDS, CARD_RARITY
from sts2_lite.card.ids import TargetType

CARD_SOURCES = Path(__file__).resolve().parents[4] / "sts2_decompiled" / "Core" / "Models" / "Cards"
REGENT_TOKENS = [CardId.SOVEREIGN_BLADE, CardId.MINION_STRIKE, CardId.DEBRIS, CardId.MINION_DIVE_BOMB, CardId.MINION_SACRIFICE]

def _class_of(card_id):
    return "".join(part.capitalize() for part in card_id.name.split("_"))

@pytest.mark.skipif(not CARD_SOURCES.is_dir(), reason="decompiled sources not present")
@pytest.mark.parametrize("card_id", [*REGENT_CARDS, *REGENT_TOKENS], ids=lambda c: c.name)
def test_regent_card_matches_the_decompiled_class(card_id):
    source = (CARD_SOURCES / f"{_class_of(card_id)}.cs").read_text()
    energy, ctype, rarity, target = re.search(r": base\((-?\d+|[^,]+), CardType\.(\w+), CardRarity\.(\w+), TargetType\.(\w+)\)", source).groups()
    table = REGENT_CARDS.get(card_id) or TOKEN_CARDS.get(card_id) or {CardId.DEBRIS: ("Debris", CardType.Status, 1, TargetType.NONE)}[card_id]
    expected_cost = "X" if "HasEnergyCostX => true" in source else int(energy)
    assert (table[2], table[1].name, table[3].name.lower()) == (expected_cost, ctype, target.lower()), card_id
    assert CARD_RARITY[card_id].name == rarity, card_id
    star = re.search(r"CanonicalStarCost => (-?\d+)", source)
    expected = int(star.group(1)) if star else "X" if "HasStarCostX => true" in source else None
    assert STAR_COST.get(card_id) == expected, card_id

@pytest.mark.skipif(not CARD_SOURCES.is_dir(), reason="decompiled sources not present")
@pytest.mark.parametrize("card_id", [c for c in [*REGENT_CARDS, *REGENT_TOKENS] if c in __import__("sts2_lite.card.effects", fromlist=["PLAIN_DAMAGE"]).PLAIN_DAMAGE], ids=lambda c: c.name)
def test_regent_printed_damage_matches_the_decompiled_class(card_id):
    """The base and upgraded damage of the Attacks that print one number."""
    from sts2_lite.card.effects import PLAIN_DAMAGE
    source = (CARD_SOURCES / f"{_class_of(card_id)}.cs").read_text()
    base = re.search(r"new DamageVar\((\d+)m", source)
    if base is None:
        pytest.skip("no plain DamageVar")
    upgrade = sum(int(n) for n in re.findall(r"DynamicVars\.Damage\.UpgradeValueBy\((\d+)m\)", source))
    assert PLAIN_DAMAGE[card_id] == (int(base.group(1)), int(base.group(1)) + upgrade), card_id


# ------------------------------------------------------------ Uncommons
def end_and_start_turn(sim):
    sim.end_turn()
    return sim.combat_state

def test_alignment_gains_energy():
    for up, gain in ((False, 2), (True, 3)):
        cs = one_enemy([gen(CardId.ALIGNMENT, up)], stars=2)
        play(cs)
        assert cs.energy == 3 + gain and cs.player.stars == 0

def test_bulwark_blocks_and_forges():
    cs = one_enemy([gen(CardId.BULWARK, True)])
    play(cs)
    assert cs.player.block == 15 and cs.energy == 1
    assert [c.bonus_damage for c in cs.player.hand if c.card_id is CardId.SOVEREIGN_BLADE] == [13]

def test_charge_turns_two_draw_pile_cards_into_dive_bombs():
    cs = one_enemy([gen(CardId.CHARGE, True)])
    cs.player.draw_pile = [gen(CardId.STRIKE_REGENT), gen(CardId.DEFEND_REGENT), gen(CardId.VENERATE)]
    sim = play(cs)
    assert cs.pending_choice is not None and cs.pending_choice.kind == "charge"
    sim.choose_card(cs.pending_choice.indices[0])
    sim.choose_card(cs.pending_choice.indices[0])
    bombs = [c for c in cs.player.draw_pile if c.card_id is CardId.MINION_DIVE_BOMB]
    assert len(bombs) == 2 and all(b.is_upgraded and b.exhausts for b in bombs) and len(cs.player.draw_pile) == 3

def test_dive_bomb_hits_for_13():
    cs = one_enemy([gen(CardId.MINION_DIVE_BOMB)])
    play(cs)
    assert cs.enemies[0].current_hp == 87 and cs.energy == 3

def test_child_of_the_stars_blocks_for_stars_spent():
    cs = one_enemy([gen(CardId.CHILD_OF_THE_STARS, True), gen(CardId.FALLING_STAR)], stars=2)
    sim = play(cs)
    assert cs.player.block == 0
    sim.play_card(0, 0)
    assert cs.player.block == 6

def test_black_hole_hits_on_stars_gained_and_after_a_star_card():
    cs = make_state([gen(CardId.BLACK_HOLE), gen(CardId.VENERATE), gen(CardId.FALLING_STAR)], enemy_count=2, enemy_hp=100)
    cs.player.character = "REGENT"
    sim = play(cs)
    assert [e.current_hp for e in cs.enemies] == [100, 100]
    sim.play_card(0, 0)                      # Venerate: +2 Stars
    assert [e.current_hp for e in cs.enemies] == [97, 97]
    sim.play_card(0, 0)                      # Falling Star: 8 damage, then 3 to everyone for the Stars it cost
    assert [e.current_hp for e in cs.enemies] == [97 - 8 - 3, 94]

def test_conqueror_forges_and_doubles_the_blade_on_its_target():
    cs = one_enemy([gen(CardId.CONQUEROR), gen(CardId.SOVEREIGN_BLADE)])
    sim = play(cs)
    enemy = cs.enemies[0]
    assert enemy.status_amount(StatusId.CONQUEROR) == 1
    blade = next(c for c in cs.player.hand if c.card_id is CardId.SOVEREIGN_BLADE)
    assert blade.bonus_damage == 3
    sim.play_card(cs.player.hand.index(blade), 0)
    assert enemy.current_hp == 100 - 26

def test_convergence_retains_and_gives_energy_and_stars_next_turn():
    cs = one_enemy([gen(CardId.CONVERGENCE, True), gen(CardId.DEFEND_REGENT)])
    sim = play(cs)
    assert StatusId.RETAIN_HAND in cs.player.status
    assert cs.player.status_amount(StatusId.ENERGY_NEXT_TURN) == 1 and cs.player.status_amount(StatusId.STAR_NEXT_TURN) == 2

def test_devastate_and_gamma_blast():
    cs = one_enemy([gen(CardId.DEVASTATE)], stars=4)
    play(cs)
    assert cs.enemies[0].current_hp == 65 and cs.player.stars == 0
    cs = one_enemy([gen(CardId.GAMMA_BLAST, True)], stars=3)
    play(cs)
    enemy = cs.enemies[0]
    assert enemy.current_hp == 82 and cs.energy == 3 and enemy.status_amount(StatusId.WEAK) == 2 and enemy.status_amount(StatusId.VULNERABLE) == 2

def test_furnace_forges_each_turn():
    cs = one_enemy([gen(CardId.FURNACE)])
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT) for _ in range(10)]
    sim = play(cs)
    sim.end_turn()
    blades = [c for c in cs.player.hand if c.card_id is CardId.SOVEREIGN_BLADE]
    assert len(blades) == 1 and blades[0].bonus_damage == 5

def test_glimmer_draws_then_returns_a_card():
    cs = one_enemy([gen(CardId.GLIMMER)])
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT), gen(CardId.VENERATE), gen(CardId.STRIKE_REGENT)]
    sim = play(cs)
    assert len(cs.player.hand) == 3 and cs.pending_choice.kind == "to_draw_pile"
    sim.choose_card(cs.pending_choice.indices[0])
    assert len(cs.player.hand) == 2 and len(cs.player.draw_pile) == 1

def test_hegemony_gives_energy_next_turn():
    cs = one_enemy([gen(CardId.HEGEMONY, True)])
    play(cs)
    assert cs.enemies[0].current_hp == 82 and cs.player.status_amount(StatusId.ENERGY_NEXT_TURN) == 3

def test_kingly_kick_is_cheaper_each_time_it_is_drawn():
    cs = one_enemy([gen(CardId.GLOW)])
    cs.player.draw_pile = [gen(CardId.KINGLY_KICK)]
    sim = play(cs)
    kick = cs.player.hand[0]
    assert kick.card_id is CardId.KINGLY_KICK and kick.energy_cost == 3

def test_kingly_punch_grows_each_time_it_is_drawn():
    cs = one_enemy([gen(CardId.GLOW)])
    cs.player.draw_pile = [gen(CardId.KINGLY_PUNCH, True)]
    sim = play(cs)
    punch = cs.player.hand[0]
    assert punch.bonus_damage == 6
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - 16

def test_lunar_blast_hits_once_per_skill_played():
    cs = one_enemy([gen(CardId.DEFEND_REGENT), gen(CardId.DEFEND_REGENT), gen(CardId.LUNAR_BLAST)])
    sim = play(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - 8

def test_manifest_authority_blocks_and_adds_a_colorless_card():
    cs = one_enemy([gen(CardId.MANIFEST_AUTHORITY, True)])
    play(cs)
    assert cs.player.block == 8 and len(cs.player.hand) == 1 and cs.player.hand[0].is_upgraded and cs.player.cards_generated == 1

def test_monologue_gives_strength_for_each_later_card_this_turn():
    cs = one_enemy([gen(CardId.MONOLOGUE), gen(CardId.DEFEND_REGENT), gen(CardId.DEFEND_REGENT)])
    sim = play(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == 0
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.STRENGTH) == 2
    sim.end_turn()
    assert cs.player.status_amount(StatusId.STRENGTH) == 0 and StatusId.MONOLOGUE not in cs.player.status

def test_orbit_pays_back_energy_for_every_four_spent():
    cs = one_enemy([gen(CardId.ORBIT, True), gen(CardId.BULWARK), gen(CardId.BULWARK)])
    cs.energy = 6
    sim = play(cs)                     # Orbit costs 1: nothing counted yet
    assert cs.energy == 5
    sim.play_card(0, 0)                # 2 spent
    sim.play_card(0, 0)                # 4 spent: one Energy back
    assert cs.energy == 5 - 2 - 2 + 1

def test_pale_blue_dot_draws_extra_after_five_cards():
    cs = one_enemy([gen(CardId.PALE_BLUE_DOT)] + [gen(CardId.VENERATE) for _ in range(5)])
    cs.energy = 10
    sim = play(cs)
    for _ in range(3):
        sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.DRAW_CARDS_NEXT_TURN) == 0
    sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.DRAW_CARDS_NEXT_TURN) == 1

def test_parry_gives_block_with_each_blade_play():
    cs = one_enemy([gen(CardId.PARRY, True), gen(CardId.SOVEREIGN_BLADE)])
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.block == 14 and cs.enemies[0].current_hp == 90

def test_particle_wall_returns_to_the_hand():
    cs = one_enemy([gen(CardId.PARTICLE_WALL, True)], stars=2)
    play(cs)
    assert cs.player.block == 12 and cs.player.stars == 0
    assert [c.card_id for c in cs.player.hand] == [CardId.PARTICLE_WALL] and not cs.player.discard_pile

def test_pillar_of_creation_blocks_for_each_card_made():
    cs = one_enemy([gen(CardId.PILLAR_OF_CREATION), gen(CardId.REFINE_BLADE)])
    sim = play(cs)
    assert cs.player.block == 0
    sim.play_card(0, 0)            # Forge makes the Blade
    assert cs.player.block == 2

def test_prophesize_draws():
    cs = one_enemy([gen(CardId.PROPHESIZE, True)])
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT) for _ in range(10)]
    play(cs)
    assert len(cs.player.hand) == 9

def test_quasar_offers_three_colorless_cards():
    cs = one_enemy([gen(CardId.QUASAR, True)], stars=2)
    sim = play(cs)
    assert cs.pending_choice.kind == "pick_to_hand" and len(cs.pending_choice.offers) == 3 and all(c.is_upgraded for c in cs.pending_choice.offers)
    sim.choose_card(0)
    assert len(cs.player.hand) == 1

def test_radiate_hits_every_enemy_for_the_stars_gained_this_turn():
    cs = make_state([gen(CardId.VENERATE), gen(CardId.RADIATE, True)], enemy_count=2, enemy_hp=100)
    cs.player.character = "REGENT"
    sim = play(cs)
    sim.play_card(0, 0)
    assert [e.current_hp for e in cs.enemies] == [100 - 8, 100 - 8]

def test_reflect_returns_blocked_damage():
    cs = one_enemy([gen(CardId.REFLECT)], stars=3)
    sim = play(cs)
    assert cs.player.block == 15 and cs.player.status_amount(StatusId.REFLECT) == 1
    cs.enemies[0].block = 0
    cs.player.apply_damage(7, cs.enemies[0], powered=True)
    assert cs.player.block == 8 and cs.enemies[0].current_hp == 100 - 7
    cs.player.apply_damage(20, cs.enemies[0], powered=True)       # 8 blocked and given back
    assert cs.enemies[0].current_hp == 100 - 7 - 8

def test_resonance_gives_strength_and_takes_it_from_enemies():
    cs = make_state([gen(CardId.RESONANCE, True)], enemy_count=2, enemy_hp=100)
    cs.player.stars = 2
    cs.player.character = "REGENT"
    play(cs)
    assert cs.player.status_amount(StatusId.STRENGTH) == 2 and [e.status_amount(StatusId.STRENGTH) for e in cs.enemies] == [-1, -1]

def test_royal_gamble_gains_nine_stars_and_exhausts():
    cs = one_enemy([gen(CardId.ROYAL_GAMBLE)], stars=5)
    play(cs)
    assert cs.player.stars == 9 and cs.player.exhaust_pile[0].card_id is CardId.ROYAL_GAMBLE

def test_shining_strike_gains_stars_and_goes_on_the_draw_pile():
    cs = one_enemy([gen(CardId.SHINING_STRIKE, True)])
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT)]
    play(cs)
    assert cs.enemies[0].current_hp == 89 and cs.player.stars == 2
    assert cs.player.draw_pile[-1].card_id is CardId.SHINING_STRIKE

def test_spectrum_shift_adds_colorless_cards_before_the_hand_draw():
    cs = one_enemy([gen(CardId.SPECTRUM_SHIFT)])
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT) for _ in range(10)]
    sim = play(cs)
    sim.end_turn()
    assert len(cs.player.hand) == 7 and cs.player.cards_generated == 2

def test_stardust_hits_once_per_star_spent():
    cs = one_enemy([gen(CardId.STARDUST, True)], stars=3)
    play(cs)
    assert cs.enemies[0].current_hp == 100 - 21 and cs.player.stars == 0

def test_summon_forth_gathers_every_blade_and_forges():
    cs = one_enemy([gen(CardId.SUMMON_FORTH)])
    cs.player.discard_pile = [gen(CardId.SOVEREIGN_BLADE)]
    cs.player.exhaust_pile = [gen(CardId.SOVEREIGN_BLADE)]
    play(cs)
    blades = [c for c in cs.player.hand if c.card_id is CardId.SOVEREIGN_BLADE]
    assert len(blades) == 2 and all(b.bonus_damage == 8 for b in blades) and not any(c.card_id is CardId.SOVEREIGN_BLADE for c in cs.player.discard_pile + cs.player.exhaust_pile)

def test_supermassive_counts_cards_made_in_the_fight():
    cs = one_enemy([gen(CardId.REFINE_BLADE), gen(CardId.SUPERMASSIVE)])
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - 8

def test_terraforming_gives_vigor():
    cs = one_enemy([gen(CardId.TERRAFORMING), gen(CardId.STRIKE_REGENT)])
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - 13

def test_the_regent_reward_pool_holds_its_uncommons():
    from sts2_lite.rewards.cards import card_pool
    pool = card_pool("REGENT")
    assert len(pool["Uncommon"]) == 35 and CardId.BLACK_HOLE in pool["Uncommon"]


# ------------------------------------------------------------ Rares
def test_knockout_blow_gives_stars_on_a_kill():
    cs = one_enemy([gen(CardId.KNOCKOUT_BLOW, True)], hp=38)
    play(cs)
    assert cs.player.stars == 5
    cs = one_enemy([gen(CardId.KNOCKOUT_BLOW)], hp=100)
    play(cs)
    assert cs.player.stars == 0 and cs.enemies[0].current_hp == 70

def test_arsenal_gives_strength_for_each_card_made():
    cs = one_enemy([gen(CardId.ARSENAL), gen(CardId.REFINE_BLADE)])
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.STRENGTH) == 1

def test_beat_into_shape_forges_more_for_each_earlier_hit_this_turn():
    cs = one_enemy([gen(CardId.STRIKE_REGENT), gen(CardId.STRIKE_REGENT), gen(CardId.BEAT_INTO_SHAPE)])
    cs.player.counts_hits = True
    sim = play(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    blade = next(c for c in cs.player.hand if c.card_id is CardId.SOVEREIGN_BLADE)
    assert blade.bonus_damage == 5 + 5 * 2 and cs.enemies[0].current_hp == 100 - 6 - 6 - 5

def test_big_bang():
    cs = one_enemy([gen(CardId.BIG_BANG)])
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT)]
    play(cs)
    assert cs.player.stars == 1 and cs.energy == 4 and cs.player.exhaust_pile and len(cs.player.hand) == 2
    assert cs.player.hand[0].card_id is CardId.DEFEND_REGENT or cs.player.hand[1].card_id is CardId.DEFEND_REGENT

def test_bombardment_plays_itself_from_the_exhaust_pile_each_turn():
    cs = one_enemy([gen(CardId.BOMBARDMENT, True)])
    cs.energy = 3
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT) for _ in range(10)]
    sim = play(cs)
    assert cs.enemies[0].current_hp == 76 and cs.player.exhaust_pile[0].card_id is CardId.BOMBARDMENT
    sim.end_turn()
    assert cs.enemies[0].current_hp == 52

def test_bundle_of_joy_adds_distinct_colorless_cards():
    cs = one_enemy([gen(CardId.BUNDLE_OF_JOY, True)])
    play(cs)
    assert len(cs.player.hand) == 4 and len({c.card_id for c in cs.player.hand}) == 4

def test_comet_costs_five_stars():
    cs = one_enemy([gen(CardId.COMET)], stars=5)
    play(cs)
    enemy = cs.enemies[0]
    assert cs.player.stars == 0 and cs.energy == 3 and enemy.current_hp == 67
    assert enemy.status_amount(StatusId.WEAK) == 3 and enemy.status_amount(StatusId.VULNERABLE) == 3

def test_crash_landing_fills_the_hand_with_debris():
    cs = one_enemy([gen(CardId.CRASH_LANDING), gen(CardId.DEFEND_REGENT)])
    play(cs)
    assert cs.enemies[0].current_hp == 79
    assert len(cs.player.hand) == 10 and sum(c.card_id is CardId.DEBRIS for c in cs.player.hand) == 9

def test_decisions_decisions_plays_a_skill_three_times():
    cs = one_enemy([gen(CardId.DECISIONS_DECISIONS), gen(CardId.DEFEND_REGENT)], stars=6)
    cs.player.draw_pile = [gen(CardId.STRIKE_REGENT)] * 3
    play(cs)                  # the only Skill is picked without asking
    assert cs.pending_choice is None and cs.player.block == 15 and sum(c.card_id is CardId.DEFEND_REGENT for c in cs.player.discard_pile) == 1

def test_dying_star_hits_all_and_takes_strength_until_their_turn_ends():
    cs = make_state([gen(CardId.DYING_STAR, True)], enemy_count=2, enemy_hp=100)
    cs.player.stars, cs.player.character = 3, "REGENT"
    sim = play(cs)
    assert [e.current_hp for e in cs.enemies] == [89, 89]
    assert [e.status_amount(StatusId.STRENGTH) for e in cs.enemies] == [-11, -11]
    sim._return_temporary_strength(cs.enemies[0])
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 0

def test_foregone_conclusion_picks_cards_next_turn():
    cs = one_enemy([gen(CardId.FOREGONE_CONCLUSION, True)])
    cs.player.draw_pile = [gen(CardId.VENERATE)] + [gen(CardId.DEFEND_REGENT) for _ in range(8)] + [gen(CardId.STRIKE_REGENT)]
    sim = play(cs)
    sim.end_turn()
    assert cs.pending_choice is not None and StatusId.FOREGONE_CONCLUSION not in cs.player.status

def test_genesis_gives_stars_each_turn():
    cs = one_enemy([gen(CardId.GENESIS)])
    cs.energy = 2
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT) for _ in range(10)]
    sim = play(cs)
    sim.end_turn()
    assert cs.player.stars == 2 and cs.player.stars_gained_this_turn == 2

def test_guards_turns_cards_into_minion_sacrifices():
    cs = one_enemy([gen(CardId.GUARDS, True), gen(CardId.STRIKE_REGENT), gen(CardId.VENERATE), gen(CardId.DEFEND_REGENT)])
    sim = play(cs)
    assert cs.pending_choice.kind == "guards"
    sim.choose_card(cs.pending_choice.indices[0])
    sim.confirm_choice()
    sacrifices = [c for c in cs.player.hand if c.card_id is CardId.MINION_SACRIFICE]
    assert len(sacrifices) == 1 and sacrifices[0].is_upgraded and sacrifices[0].exhausts
    sim.play_card(cs.player.hand.index(sacrifices[0]), 0)
    assert cs.player.block == 10

def test_heavenly_drill_hits_twice_as_often_with_four_energy():
    cs = one_enemy([gen(CardId.HEAVENLY_DRILL)])
    cs.energy = 4
    play(cs)
    assert cs.enemies[0].current_hp == 100 - 8 * 8 and cs.energy == 0
    cs = one_enemy([gen(CardId.HEAVENLY_DRILL, True)])
    play(cs)
    assert cs.enemies[0].current_hp == 100 - 10 * 3

def test_heirloom_hammer_copies_a_colorless_card():
    cs = one_enemy([gen(CardId.HEIRLOOM_HAMMER), gen(CardId.FINESSE)])
    sim = play(cs)
    assert cs.enemies[0].current_hp == 80
    assert sum(c.card_id is CardId.FINESSE for c in cs.player.hand) == 2

def test_i_am_invincible_plays_itself_from_the_top_of_the_draw_pile():
    cs = one_enemy([gen(CardId.DEFEND_REGENT)])
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT) for _ in range(9)] + [gen(CardId.I_AM_INVINCIBLE, True)]
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert any(c.card_id is CardId.I_AM_INVINCIBLE for c in cs.player.discard_pile)

def test_make_it_so_returns_after_every_third_skill():
    cs = one_enemy([gen(CardId.DEFEND_REGENT)] * 3)
    cs.player.discard_pile = [gen(CardId.MAKE_IT_SO)]
    sim = play(cs)
    sim.play_card(0, 0)
    assert not any(c.card_id is CardId.MAKE_IT_SO for c in cs.player.hand)
    sim.play_card(0, 0)
    assert any(c.card_id is CardId.MAKE_IT_SO for c in cs.player.hand)

def test_monarchs_gaze_takes_strength_from_what_it_hits():
    cs = one_enemy([gen(CardId.MONARCHS_GAZE, True), gen(CardId.STRIKE_REGENT)])
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == -1
    sim._return_temporary_strength(cs.enemies[0])
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 0

def test_neutron_aegis_gives_plating():
    cs = one_enemy([gen(CardId.NEUTRON_AEGIS, True)], stars=5)
    play(cs)
    assert cs.player.status_amount(StatusId.PLATING) == 11 and cs.player.stars == 0

def test_seeking_edge_makes_the_blade_hit_everyone():
    cs = make_state([gen(CardId.SEEKING_EDGE)], enemy_count=2, enemy_hp=100)
    cs.player.character = "REGENT"
    sim = play(cs)
    blade = next(c for c in cs.player.hand if c.card_id is CardId.SOVEREIGN_BLADE)
    assert blade.bonus_damage == 7
    sim.play_card(cs.player.hand.index(blade), 0)
    assert [e.current_hp for e in cs.enemies] == [100 - 17, 100 - 17]

def test_seven_stars_hits_seven_times():
    cs = make_state([gen(CardId.SEVEN_STARS)], enemy_count=2, enemy_hp=100)
    cs.player.stars, cs.player.character = 7, "REGENT"
    play(cs)
    assert [e.current_hp for e in cs.enemies] == [51, 51] and cs.player.stars == 0

def test_sword_sage_plays_the_blade_again():
    cs = one_enemy([gen(CardId.SWORD_SAGE, True), gen(CardId.SOVEREIGN_BLADE)])
    cs.energy = 4
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 80

def test_the_smith_forges_thirty():
    cs = one_enemy([gen(CardId.THE_SMITH)], stars=4)
    play(cs)
    blade = next(c for c in cs.player.hand if c.card_id is CardId.SOVEREIGN_BLADE)
    assert blade.bonus_damage == 30 and cs.player.stars == 0

def test_tyranny_draws_more_and_exhausts_cards():
    cs = one_enemy([gen(CardId.TYRANNY)])
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT) for _ in range(12)]
    sim = play(cs)
    sim.end_turn()          # 6 cards are drawn, then one is exhausted (the cards are all the same: no asking)
    assert len(cs.player.exhaust_pile) == 1 and len(cs.player.hand) == 5

def test_void_form_makes_the_first_cards_free_and_ends_the_turn():
    cs = one_enemy([gen(CardId.VOID_FORM, True)])
    cs.energy = 3
    cs.player.draw_pile = [gen(CardId.BULWARK) for _ in range(10)]
    sim = play(cs)
    assert StatusId.VOID_FORM in cs.player.status
    assert cs.turn_number >= 2 and len(cs.player.hand) == 5
    # new turn: the first 2 cards are free
    bulwark = next(i for i, c in enumerate(cs.player.hand) if c.card_id is CardId.BULWARK)
    energy = cs.energy
    sim.play_card(bulwark, 0)
    assert cs.energy == energy


# ------------------------------------------------------------ relics
from sts2_lite.relic import RelicId, RelicInstance


def with_relic(cs, relic_id):
    cs.player.relics[relic_id] = RelicInstance(relic_id)
    return cs

def test_fencing_manual_forges_when_the_fight_opens():
    cs = one_enemy([])
    sim = CombatSimulator(cs)
    Opening([{"id": "FENCING_MANUAL"}], "monster").after_draw(sim)
    blades = [c for c in cs.player.hand if c.card_id is CardId.SOVEREIGN_BLADE]
    assert len(blades) == 1 and blades[0].bonus_damage == 10

def test_galactic_dust_gives_block_for_every_ten_stars_spent():
    cs = with_relic(one_enemy([gen(CardId.DEVASTATE), gen(CardId.DEVASTATE), gen(CardId.DEVASTATE)], stars=12), RelicId.GALACTIC_DUST)
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.block == 0
    cs.player.stars = 4
    sim.play_card(0, 0)               # 12 stars spent so far: 10 Block, 2 left over
    assert cs.player.block == 10 and cs.player.relics[RelicId.GALACTIC_DUST].counter == 2

def test_lunar_pastry_gives_a_star_at_the_end_of_the_turn():
    cs = with_relic(one_enemy([]), RelicId.LUNAR_PASTRY)
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT) for _ in range(10)]
    CombatSimulator(cs).end_turn()
    assert cs.player.stars == 1

def test_mini_regent_gives_strength_for_the_first_stars_spent_each_turn():
    cs = with_relic(one_enemy([gen(CardId.FALLING_STAR), gen(CardId.FALLING_STAR)], stars=4), RelicId.MINI_REGENT)
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.STRENGTH) == 1

def test_regalite_gives_block_for_the_first_card_made_each_turn():
    cs = with_relic(one_enemy([gen(CardId.REFINE_BLADE), gen(CardId.BUNDLE_OF_JOY)]), RelicId.REGALITE)
    sim = play(cs)
    assert cs.player.block == 4
    sim.play_card(0, 0)
    assert cs.player.block == 4

def test_vitruvian_minion_doubles_minion_cards():
    cs = with_relic(one_enemy([gen(CardId.MINION_STRIKE), gen(CardId.MINION_SACRIFICE), gen(CardId.STRIKE_REGENT)]), RelicId.VITRUVIAN_MINION)
    cs.player.draw_pile = [gen(CardId.DEFEND_REGENT)]
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.block == 14
    sim.play_card(0, 0)
    assert cs.enemies[0].current_hp == 100 - 12 - 6


# ------------------------------------------------------------ potions
def test_the_regents_potions():
    from sts2_lite.potion import Potion, PotionId, PotionRarity
    from sts2_lite.potion_pool import potion_pool
    regent = potion_pool("REGENT")
    assert {PotionId.STAR_POTION, PotionId.KINGS_COURAGE, PotionId.COSMIC_CONCOCTION} <= set(regent)
    assert PotionId.STAR_POTION not in potion_pool("SILENT") and PotionId.POISON_POTION not in regent
    assert (PotionId.STAR_POTION.rarity, PotionId.KINGS_COURAGE.rarity, PotionId.COSMIC_CONCOCTION.rarity) == (PotionRarity.COMMON, PotionRarity.UNCOMMON, PotionRarity.RARE)

def drink_potion(cs, potion_id):
    from sts2_lite.potion import Potion
    cs.player.potions = [Potion(potion_id, 0)]
    sim = CombatSimulator(cs)
    sim.perform_action({"action": "use_potion", "slot": 0, "target": 0})
    return sim

def test_star_potion_gives_three_stars():
    from sts2_lite.potion import PotionId
    cs = one_enemy([])
    drink_potion(cs, PotionId.STAR_POTION)
    assert cs.player.stars == 3

def test_kings_courage_forges_fifteen():
    from sts2_lite.potion import PotionId
    cs = one_enemy([])
    drink_potion(cs, PotionId.KINGS_COURAGE)
    assert [c.bonus_damage for c in cs.player.hand if c.card_id is CardId.SOVEREIGN_BLADE] == [15]

def test_cosmic_concoction_adds_three_upgraded_colorless_cards():
    from sts2_lite.potion import PotionId
    cs = one_enemy([])
    drink_potion(cs, PotionId.COSMIC_CONCOCTION)
    assert len(cs.player.hand) == 3 and all(c.is_upgraded for c in cs.player.hand)
