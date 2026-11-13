import pytest
from sts2_lite.card import CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.player import Player
from sts2_lite.relic import RelicId, RelicInstance
from sts2_lite.status import StatusId, StatusInstance
from sts2_lite.Tests.card.test_card import hps
from sts2_lite.Tests.relic.test_always_on import card, strike, bash, defend, inflame, state, relic, enemy_attack, plays


GROUP_4 = ["BRILLIANT_SCARF", "VELVET_CHOKER", "THROWING_AXE", "MUSIC_BOX", "DIAMOND_DIADEM"]

def havoc():
    return card(CardId.HAVOC, 1, CardType.Skill, TargetType.Self)

def next_turn(cs):
    cs.player.draw_pile = [defend() for _ in range(20)]
    sim = CombatSimulator(cs)
    sim.end_turn()
    return sim


@pytest.mark.parametrize("bridge_id", GROUP_4)
def test_loads_from_the_bridge(bridge_id):
    assert RelicInstance.from_dict({"id": bridge_id, "counter": 0}).relic_id == RelicId[bridge_id]


# ---------------------------------------------------------------- Brilliant Scarf
def test_scarf_makes_the_5th_card_free():
    cs = state([defend() for _ in range(6)], RelicId.BRILLIANT_SCARF)
    cs.energy = 4
    sim = plays(cs, (0, 0), (0, 0), (0, 0), (0, 0))
    assert cs.energy == 0 and cs.player.hand[0].current_cost(cs.player) == 0
    sim.play_card(0, 0)
    assert cs.energy == 0 and cs.player.hand[0].current_cost(cs.player) == 1

def test_scarf_ignores_auto_plays():
    cs = state([havoc()], RelicId.BRILLIANT_SCARF)
    cs.player.draw_pile = [defend()]
    plays(cs, (0, 0))
    assert relic(cs, RelicId.BRILLIANT_SCARF).counter == 1

def test_scarf_resets_each_turn():
    cs = state([], RelicId.BRILLIANT_SCARF)
    relic(cs, RelicId.BRILLIANT_SCARF).counter = 5
    next_turn(cs)
    assert relic(cs, RelicId.BRILLIANT_SCARF).counter == 0

def test_scarf_hidden_counter_means_5_played():
    assert RelicInstance.from_dict({"id": "BRILLIANT_SCARF", "counter": None}).counter == 5


# ---------------------------------------------------------------- Velvet Choker
def test_choker_blocks_the_7th_card():
    cs = state([defend() for _ in range(8)], RelicId.VELVET_CHOKER)
    cs.energy = 10
    sim = plays(cs, *[(0, 0)] * 6)
    assert sim.get_available_actions() == [{"action": "end_turn"}]

def test_choker_counts_auto_plays():
    # Havoc's own count comes after its OnPlay, so the Strike is the 6th card and is played
    cs = state([havoc()], RelicId.VELVET_CHOKER)
    relic(cs, RelicId.VELVET_CHOKER).counter = 5
    cs.player.draw_pile = [strike()]
    plays(cs, (0, 0))
    assert hps(cs) == [94] and relic(cs, RelicId.VELVET_CHOKER).counter == 7

def test_choker_stops_auto_plays():
    cs = state([], RelicId.VELVET_CHOKER)
    relic(cs, RelicId.VELVET_CHOKER).counter = 6
    CombatSimulator(cs).auto_play(strike(), force_exhaust=True)
    assert hps(cs) == [100] and [c.card_id for c in cs.player.exhaust_pile] == [CardId.STRIKE_IRONCLAD]

def test_choker_resets_each_turn():
    cs = state([], RelicId.VELVET_CHOKER)
    relic(cs, RelicId.VELVET_CHOKER).counter = 6
    next_turn(cs)
    assert relic(cs, RelicId.VELVET_CHOKER).counter == 0


# ---------------------------------------------------------------- Throwing Axe (ModifyCardPlayCount)
def test_axe_plays_the_first_card_twice():
    cs = state([strike(), strike()], RelicId.THROWING_AXE)
    plays(cs, (0, 0), (0, 0))
    assert hps(cs) == [100 - 12 - 6] and cs.energy == 1

def test_axe_works_on_any_card_type():
    cs = state([inflame()], RelicId.THROWING_AXE)
    plays(cs, (0, 0))
    assert cs.player.status_amount(StatusId.STRENGTH) == 4

def test_axe_second_play_counts_as_a_card_played():
    cs = state([strike()], RelicId.THROWING_AXE, RelicId.VELVET_CHOKER)
    plays(cs, (0, 0))
    assert relic(cs, RelicId.VELVET_CHOKER).counter == 2

def test_axe_spent_status_loads():
    assert RelicInstance.from_dict({"id": "THROWING_AXE", "counter": None, "status": "Normal"}).used
    assert not RelicInstance.from_dict({"id": "THROWING_AXE", "counter": None, "status": "Active"}).used

def test_axe_and_one_two_punch_play_three_times():
    cs = state([strike()], RelicId.THROWING_AXE)
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    plays(cs, (0, 0))
    assert hps(cs) == [100 - 18]

def test_axe_refused_play_keeps_it():
    cs = state([strike()], RelicId.THROWING_AXE)
    with pytest.raises(ValueError):
        CombatSimulator(cs).play_card(0, 5)
    assert not relic(cs, RelicId.THROWING_AXE).used

def test_one_two_punch_second_play_fires_card_played_hooks():
    cs = state([strike()], RelicId.KUNAI)
    cs.player.apply_status(StatusId.ONE_TWO_PUNCH, 1)
    plays(cs, (0, 0))
    assert relic(cs, RelicId.KUNAI).counter == 2


# ---------------------------------------------------------------- Music Box
def test_music_box_adds_an_ethereal_clone_of_the_first_attack():
    cs = state([strike(up=True), strike()], RelicId.MUSIC_BOX)
    plays(cs, (0, 0))
    clone = cs.player.hand[-1]
    assert clone.card_id == CardId.STRIKE_IRONCLAD and clone.ethereal and clone.is_upgraded
    plays(cs, (0, 0))
    assert len(cs.player.hand) == 1

def test_music_box_ignores_skills_and_resets_each_turn():
    cs = state([defend()], RelicId.MUSIC_BOX)
    plays(cs, (0, 0))
    assert cs.player.hand == [] and not relic(cs, RelicId.MUSIC_BOX).used
    relic(cs, RelicId.MUSIC_BOX).used = True
    next_turn(cs)
    assert not relic(cs, RelicId.MUSIC_BOX).used

def test_music_box_once_with_throwing_axe():
    cs = state([strike()], RelicId.MUSIC_BOX, RelicId.THROWING_AXE)
    plays(cs, (0, 0))
    assert len(cs.player.hand) == 1


# ---------------------------------------------------------------- Diamond Diadem
def test_diadem_halves_attacks_after_a_quiet_turn():
    cs = state([strike(), strike()], RelicId.DIAMOND_DIADEM)
    enemy_attack(cs, 11)
    plays(cs, (0, 0), (0, 0)).end_turn()
    assert cs.player.current_hp == 50 - 5 and StatusId.DIAMOND_DIADEM not in cs.player.status

def test_diadem_not_after_3_cards():
    cs = state([defend(), defend(), defend()], RelicId.DIAMOND_DIADEM)
    enemy_attack(cs, 25)
    plays(cs, (0, 0), (0, 0), (0, 0)).end_turn()
    assert cs.player.current_hp == 50 - 10 and relic(cs, RelicId.DIAMOND_DIADEM).counter == 0

def test_diadem_power_loads():
    assert StatusInstance.from_dict({"id": "DIAMOND_DIADEM_POWER", "amount": 1}).status_id == StatusId.DIAMOND_DIADEM


# ---------------------------------------------------------------- Crossbow (AfterSideTurnStart)
def test_crossbow_adds_a_free_attack_each_turn():
    cs = state([], RelicId.CROSSBOW)
    sim = next_turn(cs)
    added = cs.player.hand[-1]
    assert len(cs.player.hand) == 6 and added.type is CardType.Attack
    assert added.current_cost(cs.player) == 0 and added.restore_cost is not None
    sim.end_turn()
    assert len(cs.player.hand) == 6 and cs.player.hand[-1].type is CardType.Attack

def test_crossbow_card_is_playable_with_no_energy():
    cs = state([], RelicId.CROSSBOW)
    next_turn(cs)
    cs.energy = 0
    assert cs.player.hand[-1].can_play_card(CombatSimulator(cs), 0)

def test_crossbow_with_a_full_hand_goes_to_discard():
    cs = state([], RelicId.CROSSBOW)
    cs.player.draw_pile = [defend() for _ in range(20)]
    sim = CombatSimulator(cs)
    for r in (RelicId.PAELS_BLOOD, RelicId.SNECKO_EYE, RelicId.FIDDLE):
        cs.player.relics[r] = RelicInstance(r)
    sim.end_turn()                              # draws 5 + 1 + 2 + 2 = 10, so the generated card cannot fit
    assert len(cs.player.hand) == 10 and len(cs.player.discard_pile) >= 1


# ---------------------------------------------------------------- Biiig Hug (AfterShuffle)
def hug_shuffle(*relic_ids, discard=4, seed=0):
    from sts2_lite import rng
    rng.seed(seed)
    cs = state([], RelicId.BIIIG_HUG, *relic_ids)
    cs.player.draw_pile = []
    cs.player.discard_pile = [defend() for _ in range(discard)]
    CombatSimulator(cs)                         # wires the shuffle hook
    cs.player.draw_card()
    return cs

def test_biiig_hug_adds_a_soot_when_the_draw_pile_is_reshuffled():
    cs = hug_shuffle()
    cards = cs.player.hand + cs.player.draw_pile
    assert sorted(c.card_id.name for c in cards) == ["DEFEND_IRONCLAD"] * 4 + ["SOOT"]

def test_soot_is_an_unplayable_status_with_no_cost():
    from sts2_lite.card import Card
    soot = Card.create_soot()
    assert soot.type is CardType.Status and soot.unplayable and soot.energy_cost == 0 and not soot.exhausts
    cs = state([soot], RelicId.BIIIG_HUG)
    assert CombatSimulator(cs).get_available_actions() == [{"action": "end_turn"}]

def test_biiig_hug_soot_lands_anywhere_in_the_pile():
    spots = set()
    for seed in range(60):
        cs = hug_shuffle(seed=seed)
        spots.add(next(i for i, c in enumerate(cs.player.hand + cs.player.draw_pile) if c.card_id.name == "SOOT"))
    assert spots == {0, 1, 2, 3, 4}

def test_biiig_hug_does_nothing_without_a_shuffle():
    cs = state([], RelicId.BIIIG_HUG)
    CombatSimulator(cs)
    cs.player.draw_pile = [defend() for _ in range(3)]
    cs.player.draw_cards(3)
    assert all(c.card_id.name != "SOOT" for c in cs.player.hand)

def test_biiig_hug_adds_a_soot_with_each_shuffle():
    cs = hug_shuffle(discard=2)
    pl = cs.player
    pl.discard_pile.extend(pl.hand + pl.draw_pile)      # everything back to the discard pile, then draw: second shuffle
    pl.hand, pl.draw_pile = [], []
    pl.draw_card()
    cards = pl.hand + pl.draw_pile + pl.discard_pile
    assert sum(c.card_id is CardId.SOOT for c in cards) == 2

def test_biiig_hug_soot_is_deck_filler_in_the_enemy_card_table():
    from sts2_lite.card import Card
    assert Card.create(CardId.SOOT).card_id is CardId.SOOT
