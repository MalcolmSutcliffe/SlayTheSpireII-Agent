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
