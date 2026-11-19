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
REGENT_TOKENS = [CardId.SOVEREIGN_BLADE, CardId.MINION_STRIKE, CardId.DEBRIS]

def _class_of(card_id):
    return "".join(part.capitalize() for part in card_id.name.split("_"))

@pytest.mark.skipif(not CARD_SOURCES.is_dir(), reason="decompiled sources not present")
@pytest.mark.parametrize("card_id", [*REGENT_CARDS, *REGENT_TOKENS], ids=lambda c: c.name)
def test_regent_card_matches_the_decompiled_class(card_id):
    source = (CARD_SOURCES / f"{_class_of(card_id)}.cs").read_text()
    energy, ctype, rarity, target = re.search(r": base\((-?\d+|[^,]+), CardType\.(\w+), CardRarity\.(\w+), TargetType\.(\w+)\)", source).groups()
    table = REGENT_CARDS.get(card_id) or TOKEN_CARDS.get(card_id) or {CardId.DEBRIS: ("Debris", CardType.Status, 1, TargetType.NONE)}[card_id]
    assert (table[2], table[1].name, table[3].name.lower()) == (int(energy), ctype, target.lower()), card_id
    assert CARD_RARITY[card_id].name == rarity, card_id
    star = re.search(r"CanonicalStarCost => (-?\d+)", source)
    assert STAR_COST.get(card_id) == (int(star.group(1)) if star else None), card_id

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
