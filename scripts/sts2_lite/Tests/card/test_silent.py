"""The Silent: starter cards, Shiv, Poison, the discard choice, the character's run setup and pools."""
import random

import pytest

from sts2_lite.card import Card, CardId, CardType
from sts2_lite.combat import CombatSimulator
from sts2_lite.potion import Potion, PotionId, use_potion
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_state


def gen(card_id, upgraded=False):
    return Card.create_generated(card_id, upgraded)

def one_enemy(hand, hp=100):
    return make_state(hand, enemy_count=1, enemy_hp=hp)

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim


# ------------------------------------------------------------ starter cards
@pytest.mark.parametrize("upgraded, damage", [(False, 6), (True, 9)])
def test_strike_silent(upgraded, damage):
    cs = one_enemy([gen(CardId.STRIKE_SILENT, upgraded)])
    play(cs)
    assert cs.enemies[0].current_hp == 100 - damage and cs.energy == 2

@pytest.mark.parametrize("upgraded, block", [(False, 5), (True, 8)])
def test_defend_silent(upgraded, block):
    cs = one_enemy([gen(CardId.DEFEND_SILENT, upgraded)])
    play(cs)
    assert cs.player.block == block

@pytest.mark.parametrize("upgraded, damage, weak", [(False, 3, 1), (True, 4, 2)])
def test_neutralize_hits_and_weakens_for_free(upgraded, damage, weak):
    cs = one_enemy([gen(CardId.NEUTRALIZE, upgraded)])
    play(cs)
    e = cs.enemies[0]
    assert e.current_hp == 100 - damage and e.status_amount(StatusId.WEAK) == weak and cs.energy == 3

def test_survivor_blocks_then_discards_a_card_of_choice():
    cs = one_enemy([gen(CardId.SURVIVOR), gen(CardId.STRIKE_SILENT), gen(CardId.NEUTRALIZE)])
    sim = play(cs)
    pending = cs.pending_choice
    assert cs.player.block == 8 and pending is not None and pending.kind == "discard" and len(pending.indices) == 2
    sim.choose_card(next(i for i in pending.indices if cs.player.hand[i].card_id == CardId.NEUTRALIZE))
    assert [c.card_id for c in cs.player.hand] == [CardId.STRIKE_SILENT]
    assert {c.card_id for c in cs.player.discard_pile} == {CardId.NEUTRALIZE, CardId.SURVIVOR}

def test_survivor_with_one_card_left_discards_it_and_fires_the_discard_hook():
    from sts2_lite.hooks import HookType
    cs = one_enemy([gen(CardId.SURVIVOR, True), gen(CardId.STRIKE_SILENT)])
    sim = CombatSimulator(cs)
    seen = []
    fire = sim.fire
    sim.fire = lambda event, *args: (seen.append((event, args)), fire(event, *args))
    sim.play_card(0, 0)
    assert cs.player.block == 11 and not cs.player.hand and cs.pending_choice is None
    assert any(e is HookType.CARD_DISCARDED and a[0].card_id == CardId.STRIKE_SILENT for e, a in seen)

def test_survivor_with_an_empty_hand_asks_nothing():
    cs = one_enemy([gen(CardId.SURVIVOR)])
    play(cs)
    assert cs.pending_choice is None and cs.player.block == 8

def test_starter_strike_and_defend_carry_their_tags():
    from sts2_lite.card import STRIKE_CARDS, DEFEND_CARDS
    assert CardId.STRIKE_SILENT in STRIKE_CARDS and CardId.DEFEND_SILENT in DEFEND_CARDS


# ------------------------------------------------------------ Shiv
@pytest.mark.parametrize("upgraded, damage", [(False, 4), (True, 6)])
def test_shiv_is_free_and_exhausts(upgraded, damage):
    shiv = gen(CardId.SHIV, upgraded)
    assert shiv.type == CardType.Attack and shiv.energy_cost == 0
    cs = one_enemy([shiv])
    play(cs)
    assert cs.enemies[0].current_hp == 100 - damage and cs.energy == 3
    assert [c.card_id for c in cs.player.exhaust_pile] == [CardId.SHIV] and not cs.player.discard_pile


# ------------------------------------------------------------ Poison
def test_poison_hits_the_enemy_when_its_turn_starts_and_wears_down():
    cs = one_enemy([], hp=30)
    cs.enemies[0].apply_status(StatusId.POISON, 5)
    sim = CombatSimulator(cs)
    sim.end_turn()
    e = cs.enemies[0]
    assert e.current_hp == 25 and e.status_amount(StatusId.POISON) == 4
    sim.end_turn()
    assert e.current_hp == 21 and e.status_amount(StatusId.POISON) == 3

def test_poison_ignores_block():
    cs = one_enemy([], hp=30)
    e = cs.enemies[0]
    e.apply_status(StatusId.POISON, 3)
    e.block = 20
    CombatSimulator(cs).end_turn()
    assert e.current_hp == 27

def test_poison_can_kill_before_the_enemy_acts():
    cs = one_enemy([], hp=4)
    e = cs.enemies[0]
    e.attack_damage, e.num_attacks = 30, 1
    e.apply_status(StatusId.POISON, 5)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert sim.is_over and cs.player.current_hp == 50

def test_poison_of_one_runs_out():
    cs = one_enemy([], hp=30)
    cs.enemies[0].apply_status(StatusId.POISON, 1)
    CombatSimulator(cs).end_turn()
    assert cs.enemies[0].current_hp == 29 and StatusId.POISON not in cs.enemies[0].status

def test_poison_on_the_player_ticks_at_the_start_of_their_turn():
    cs = one_enemy([])
    cs.player.apply_status(StatusId.POISON, 3)
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 47 and cs.player.status_amount(StatusId.POISON) == 2

def test_artifact_stops_poison():
    cs = one_enemy([])
    e = cs.enemies[0]
    e.apply_status(StatusId.ARTIFACT, 1)
    e.apply_status(StatusId.POISON, 6)
    assert StatusId.POISON not in e.status

def test_poison_loads_from_the_bridge_id():
    from sts2_lite.status import status_id_of
    assert status_id_of("POISON_POWER") is StatusId.POISON


# ------------------------------------------------------------ the Silent's potions
def test_poison_potion():
    cs = one_enemy([])
    cs.player.potions = [Potion(PotionId.POISON_POTION, 0)]
    use_potion(CombatSimulator(cs), 0, 0)
    assert cs.enemies[0].status_amount(StatusId.POISON) == 6

def test_cunning_potion_adds_three_upgraded_shivs():
    cs = one_enemy([])
    cs.player.potions = [Potion(PotionId.CUNNING_POTION, 0)]
    use_potion(CombatSimulator(cs), 0, 0)
    assert [(c.card_id, c.is_upgraded) for c in cs.player.hand] == [(CardId.SHIV, True)] * 3

def test_ghost_in_a_jar():
    cs = one_enemy([])
    cs.player.potions = [Potion(PotionId.GHOST_IN_A_JAR, 0)]
    use_potion(CombatSimulator(cs), 0, 0)
    assert cs.player.status_amount(StatusId.INTANGIBLE) == 1


# ------------------------------------------------------------ the character
def test_new_silent_run():
    from sts2_lite.run.state import new_run
    run = new_run(0, "SILENT")
    assert (run.character, run.hp, run.max_hp, run.gold, run.potion_slots) == ("SILENT", 70, 70, 99, 3)
    assert [r["id"] for r in run.relics] == ["RING_OF_THE_SNAKE"]
    ids = sorted(c["id"] for c in run.deck)
    assert ids == sorted(["STRIKE_SILENT"] * 5 + ["DEFEND_SILENT"] * 5 + ["NEUTRALIZE", "SURVIVOR"])
    neutralize = next(c for c in run.deck if c["id"] == "NEUTRALIZE")
    assert neutralize["cost"] in (0, "0") and neutralize["type"] == "Attack"

def test_ironclad_run_is_unchanged():
    from sts2_lite.run.state import new_run
    run = new_run(0)
    assert (run.character, run.hp, len(run.deck), run.relics[0]["id"]) == ("IRONCLAD", 80, 10, "BURNING_BLOOD")

def test_unknown_character_is_refused():
    from sts2_lite.run.state import new_run
    with pytest.raises(NotImplementedError):
        new_run(0, "DEFECT")

def test_silent_reward_pool_is_refused_until_its_cards_exist():
    from sts2_lite.rewards.cards import card_pool
    with pytest.raises(NotImplementedError):
        card_pool("SILENT")

def test_silent_potion_pool():
    from sts2_lite.potion_pool import potion_pool
    pool = potion_pool("SILENT")
    assert {PotionId.POISON_POTION, PotionId.CUNNING_POTION, PotionId.GHOST_IN_A_JAR} <= set(pool)
    assert PotionId.BLOOD_POTION not in pool

def test_relic_bag_holds_the_characters_own_relics():
    from sts2_lite.relic.bag import RelicGrabBag
    silent = {r for d in RelicGrabBag(random.Random(1), "SILENT").deques.values() for r in d}
    ironclad = {r for d in RelicGrabBag(random.Random(1), "IRONCLAD").deques.values() for r in d}
    assert "TINGSHA" in silent and "TINGSHA" not in ironclad
    assert "RED_SKULL" in ironclad and "RED_SKULL" not in silent

def test_character_of_title():
    from sts2_lite.character import character_of_title
    assert character_of_title("The Silent") == "SILENT" and character_of_title("The Ironclad") == "IRONCLAD" and character_of_title(None) == "IRONCLAD"
