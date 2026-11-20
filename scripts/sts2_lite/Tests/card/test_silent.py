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
        new_run(0, "WATCHER")

def test_silent_reward_pool_holds_its_commons():
    from sts2_lite.rewards.cards import card_pool_ids
    pool = set(card_pool_ids("SILENT"))
    assert {CardId.BLADE_DANCE, CardId.DEADLY_POISON, CardId.SLICE} <= pool
    assert CardId.STRIKE_SILENT not in pool and CardId.SHIV not in pool and CardId.BASH not in pool

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


# ------------------------------------------------------------ Common cards
def ids(cards):
    return [c.card_id for c in cards]

def two_enemies(hand, hp=100):
    return make_state(hand, enemy_count=2, enemy_hp=hp)

@pytest.mark.parametrize("card_id, damage", [(CardId.SLICE, 6), (CardId.PREDATOR, 15), (CardId.SUCKER_PUNCH, 8), (CardId.DAGGER_THROW, 9)])
def test_common_attack_damage(card_id, damage):
    cs = one_enemy([gen(card_id)])
    play(cs)
    assert cs.enemies[0].current_hp == 100 - damage

@pytest.mark.parametrize("card_id, upgraded, block", [(CardId.DEFLECT, False, 4), (CardId.DEFLECT, True, 7),
                                                       (CardId.UNTOUCHABLE, False, 6), (CardId.BACKFLIP, False, 5)])
def test_common_block(card_id, upgraded, block):
    cs = one_enemy([gen(card_id, upgraded)])
    play(cs)
    assert cs.player.block == block

def test_slice_and_deflect_are_free():
    for cid in (CardId.SLICE, CardId.DEFLECT, CardId.ANTICIPATE, CardId.PREPARED):
        assert gen(cid).energy_cost == 0

def test_backflip_draws_two():
    cs = one_enemy([gen(CardId.BACKFLIP)])
    cs.player.draw_pile = [gen(CardId.SLICE), gen(CardId.SLICE), gen(CardId.SLICE)]
    play(cs)
    assert len(cs.player.hand) == 2 and len(cs.player.draw_pile) == 1

@pytest.mark.parametrize("upgraded, shivs", [(False, 3), (True, 4)])
def test_blade_dance_makes_shivs_and_exhausts(upgraded, shivs):
    cs = one_enemy([gen(CardId.BLADE_DANCE, upgraded)])
    play(cs)
    assert ids(cs.player.hand) == [CardId.SHIV] * shivs and ids(cs.player.exhaust_pile) == [CardId.BLADE_DANCE]

def test_cloak_and_dagger():
    cs = one_enemy([gen(CardId.CLOAK_AND_DAGGER, True)])
    play(cs)
    assert cs.player.block == 6 and ids(cs.player.hand) == [CardId.SHIV] * 2

def test_leading_strike_hits_and_makes_two_shivs():
    cs = one_enemy([gen(CardId.LEADING_STRIKE)])
    play(cs)
    assert cs.enemies[0].current_hp == 97 and ids(cs.player.hand) == [CardId.SHIV] * 2

def test_dagger_spray_hits_every_enemy_twice():
    cs = two_enemies([gen(CardId.DAGGER_SPRAY)])
    play(cs)
    assert [e.current_hp for e in cs.enemies] == [92, 92]

def test_flick_flack_hits_every_enemy():
    cs = two_enemies([gen(CardId.FLICK_FLACK, True)])
    play(cs)
    assert [e.current_hp for e in cs.enemies] == [91, 91]

def test_ricochet_hits_random_enemies_four_times():
    cs = two_enemies([gen(CardId.RICOCHET)])
    play(cs)
    assert sum(100 - e.current_hp for e in cs.enemies) == 12

def test_dagger_throw_draws_then_discards():
    cs = one_enemy([gen(CardId.DAGGER_THROW), gen(CardId.STRIKE_SILENT)])
    cs.player.draw_pile = [gen(CardId.SLICE)]
    sim = play(cs)
    pending = cs.pending_choice
    assert pending is not None and pending.kind == "discard" and len(pending.indices) == 2
    sim.choose_card(next(i for i in pending.indices if cs.player.hand[i].card_id == CardId.SLICE))
    assert ids(cs.player.hand) == [CardId.STRIKE_SILENT]

@pytest.mark.parametrize("card_id, upgraded, poison", [(CardId.DEADLY_POISON, False, 5), (CardId.DEADLY_POISON, True, 7),
                                                        (CardId.SNAKEBITE, False, 7), (CardId.SNAKEBITE, True, 10)])
def test_poison_cards(card_id, upgraded, poison):
    cs = one_enemy([gen(card_id, upgraded)])
    play(cs)
    assert cs.enemies[0].status_amount(StatusId.POISON) == poison

def test_snakebite_is_retained():
    from sts2_lite.card import RETAINING_CARDS
    assert CardId.SNAKEBITE in RETAINING_CARDS

def test_poisoned_stab():
    cs = one_enemy([gen(CardId.POISONED_STAB, True)])
    play(cs)
    e = cs.enemies[0]
    assert e.current_hp == 92 and e.status_amount(StatusId.POISON) == 4

def test_sucker_punch_weakens():
    cs = one_enemy([gen(CardId.SUCKER_PUNCH, True)])
    play(cs)
    assert cs.enemies[0].current_hp == 90 and cs.enemies[0].status_amount(StatusId.WEAK) == 2

def test_predator_draws_two_more_next_turn():
    cs = one_enemy([gen(CardId.PREDATOR)])
    play(cs)
    assert cs.player.status_amount(StatusId.DRAW_CARDS_NEXT_TURN) == 2

def test_anticipate_dexterity_wears_off_at_end_of_turn():
    cs = one_enemy([gen(CardId.ANTICIPATE), gen(CardId.DEFLECT)])
    sim = play(cs)
    assert cs.player.status_amount(StatusId.DEXTERITY) == 2
    sim.play_card(0, 0)
    assert cs.player.block == 6
    sim.end_turn()
    assert cs.player.status_amount(StatusId.DEXTERITY) == 0 and StatusId.ANTICIPATE not in cs.player.status

def test_dodge_and_roll_blocks_again_next_turn():
    cs = one_enemy([gen(CardId.DODGE_AND_ROLL)])
    sim = play(cs)
    assert cs.player.block == 4 and cs.player.status_amount(StatusId.BLOCK_NEXT_TURN) == 4
    sim.end_turn()
    assert cs.player.block == 4

def test_piercing_wail_takes_strength_until_the_enemy_turn_ends():
    cs = two_enemies([gen(CardId.PIERCING_WAIL)])
    for e in cs.enemies:
        e.attack_damage, e.num_attacks = 10, 1
    sim = play(cs)
    assert all(e.status_amount(StatusId.STRENGTH) == -6 for e in cs.enemies)
    assert ids(cs.player.exhaust_pile) == [CardId.PIERCING_WAIL]
    sim.end_turn()
    assert cs.player.current_hp == 50 - 4 - 4
    assert all(e.status_amount(StatusId.STRENGTH) == 0 for e in cs.enemies)

def test_prepared_upgraded_draws_two_and_discards_two():
    cs = one_enemy([gen(CardId.PREPARED, True), gen(CardId.STRIKE_SILENT), gen(CardId.DEFEND_SILENT)])
    cs.player.draw_pile = [gen(CardId.SLICE), gen(CardId.DEFLECT)]
    sim = play(cs)
    for _ in range(2):
        pending = cs.pending_choice
        assert pending is not None and pending.kind == "discard"
        sim.choose_card(next(i for i in pending.indices if cs.player.hand[i].card_id in (CardId.SLICE, CardId.DEFLECT)))
    assert cs.pending_choice is None
    assert set(ids(cs.player.hand)) == {CardId.STRIKE_SILENT, CardId.DEFEND_SILENT} and len(cs.player.hand) == 2
    assert {CardId.SLICE, CardId.DEFLECT} <= set(ids(cs.player.discard_pile))


# ------------------------------------------------------------ Sly
def test_sly_card_discarded_by_an_effect_plays_for_free():
    cs = one_enemy([gen(CardId.SURVIVOR), gen(CardId.FLICK_FLACK)])
    play(cs)
    assert cs.enemies[0].current_hp == 93 and cs.energy == 2
    assert set(ids(cs.player.discard_pile)) == {CardId.SURVIVOR, CardId.FLICK_FLACK}

def test_sly_untouchable_blocks_when_discarded():
    cs = one_enemy([gen(CardId.SURVIVOR), gen(CardId.UNTOUCHABLE)])
    play(cs)
    assert cs.player.block == 8 + 6

def test_sly_card_is_not_played_at_end_of_turn_discard():
    cs = one_enemy([gen(CardId.FLICK_FLACK)])
    CombatSimulator(cs).end_turn()
    assert cs.enemies[0].current_hp == 100
