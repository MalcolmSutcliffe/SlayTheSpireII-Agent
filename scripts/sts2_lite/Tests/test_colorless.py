"""Colorless cards, group 1. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.card import Card, CardId, CardKeyword, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.status import StatusId
from test_cards import make_card, make_state, hps

S, A, ALL, RAND = TargetType.NONE, TargetType.AnyEnemy, TargetType.AllEnemies, TargetType.RandomEnemy

def card(card_id, upgraded=False):
    name, kind, cost, target = __import__("sts2_lite.card", fromlist=["x"]).COLORLESS_CARDS[card_id]
    return make_card(card_id, name, kind, cost, ALL if target == TargetType.AllEnemies else target, upgraded)

def strike():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, A)

def defend():
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, S)

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim

def fill(cs, n, kind=defend):
    cs.player.draw_pile = [kind() for _ in range(n)]

# ------------------------------------------------------------ simple cards
def test_finesse_blocks_and_draws():
    cs = make_state([card(CardId.FINESSE)], enemy_count=1); fill(cs, 3)
    play(cs)
    assert cs.player.block == 4 and len(cs.player.hand) == 1 and cs.energy == 3

def test_upgraded_finesse_blocks_seven():
    cs = make_state([card(CardId.FINESSE, True)], enemy_count=1); fill(cs, 3)
    play(cs)
    assert cs.player.block == 7

def test_flash_of_steel_hits_and_draws():
    cs = make_state([card(CardId.FLASH_OF_STEEL)], enemy_count=1, enemy_hp=40); fill(cs, 2)
    play(cs)
    assert hps(cs) == [35] and len(cs.player.hand) == 1

def test_ultimate_strike_damage():
    for upgraded, damage in ((False, 14), (True, 20)):
        cs = make_state([card(CardId.ULTIMATE_STRIKE, upgraded)], enemy_count=1, enemy_hp=40)
        play(cs)
        assert hps(cs) == [40 - damage]

def test_ultimate_strike_is_a_strike_for_perfected_strike():
    from sts2_lite.card import STRIKE_CARDS
    assert CardId.ULTIMATE_STRIKE in STRIKE_CARDS

def test_ultimate_defend_block():
    for upgraded, block in ((False, 11), (True, 15)):
        cs = make_state([card(CardId.ULTIMATE_DEFEND, upgraded)], enemy_count=1)
        play(cs)
        assert cs.player.block == block

def test_production_gives_energy_and_exhausts():
    cs = make_state([card(CardId.PRODUCTION)], enemy_count=1)
    play(cs)
    assert cs.energy == 5 and len(cs.player.exhaust_pile) == 1

def test_upgraded_production_gives_three():
    cs = make_state([card(CardId.PRODUCTION, True)], enemy_count=1)
    play(cs)
    assert cs.energy == 6

def test_master_of_strategy_draws_three_or_four_and_exhausts():
    for upgraded, drawn in ((False, 3), (True, 4)):
        cs = make_state([card(CardId.MASTER_OF_STRATEGY, upgraded)], enemy_count=1); fill(cs, 6)
        play(cs)
        assert len(cs.player.hand) == drawn and len(cs.player.exhaust_pile) == 1

def test_dramatic_entrance_hits_everyone_and_exhausts():
    cs = make_state([card(CardId.DRAMATIC_ENTRANCE)], enemy_count=2)
    play(cs)
    assert hps(cs) == [29, 29] and len(cs.player.exhaust_pile) == 1

def test_dramatic_entrance_is_innate_and_exhausts():
    assert CardId.DRAMATIC_ENTRANCE.keyword_mask & 4 and CardId.DRAMATIC_ENTRANCE.keyword_mask & 1

def test_shockwave_weakens_and_vulnerables_every_enemy():
    cs = make_state([card(CardId.SHOCKWAVE)], enemy_count=2)
    play(cs)
    for e in cs.enemies:
        assert e.status_amount(StatusId.WEAK) == 3 and e.status_amount(StatusId.VULNERABLE) == 3
    assert len(cs.player.exhaust_pile) == 1

def test_upgraded_shockwave_gives_five():
    cs = make_state([card(CardId.SHOCKWAVE, True)], enemy_count=1)
    play(cs)
    assert cs.enemies[0].status_amount(StatusId.WEAK) == 5

def test_prowess_gives_strength_and_dexterity():
    for upgraded, amount in ((False, 1), (True, 2)):
        cs = make_state([card(CardId.PROWESS, upgraded)], enemy_count=1)
        play(cs)
        assert cs.player.status_amount(StatusId.STRENGTH) == amount and cs.player.status_amount(StatusId.DEXTERITY) == amount

def test_eternal_armor_gives_plating():
    for upgraded, amount in ((False, 9), (True, 12)):
        cs = make_state([card(CardId.ETERNAL_ARMOR, upgraded)], enemy_count=1)
        play(cs)
        assert cs.player.status_amount(StatusId.PLATING) == amount

# ------------------------------------------------------------ conditional draws
def test_impatience_draws_only_without_an_attack_in_hand():
    cs = make_state([card(CardId.IMPATIENCE), defend()], enemy_count=1); fill(cs, 4)
    play(cs)
    assert len(cs.player.hand) == 3
    cs = make_state([card(CardId.IMPATIENCE), strike()], enemy_count=1); fill(cs, 4)
    play(cs)
    assert len(cs.player.hand) == 1

def test_upgraded_impatience_draws_three():
    cs = make_state([card(CardId.IMPATIENCE, True)], enemy_count=1); fill(cs, 4)
    play(cs)
    assert len(cs.player.hand) == 3

def test_restlessness_pays_out_only_as_the_last_card():
    cs = make_state([card(CardId.RESTLESSNESS)], enemy_count=1); fill(cs, 4)
    play(cs)
    assert len(cs.player.hand) == 2 and cs.energy == 5
    cs = make_state([card(CardId.RESTLESSNESS), defend()], enemy_count=1); fill(cs, 4)
    play(cs)
    assert len(cs.player.hand) == 1 and cs.energy == 3

def test_restlessness_retains():
    assert CardId.RESTLESSNESS.keyword_mask & 16

def test_scrawl_draws_up_to_ten():
    cs = make_state([card(CardId.SCRAWL), defend(), defend()], enemy_count=1); fill(cs, 20)
    play(cs)
    assert len(cs.player.hand) == 10 and len(cs.player.exhaust_pile) == 1

def test_upgraded_scrawl_retains_and_the_base_does_not():
    assert not card(CardId.SCRAWL).retains and card(CardId.SCRAWL, False).upgraded_copy().retains

# ------------------------------------------------------------ damage that depends on state
def test_fisticuffs_blocks_for_the_damage_dealt():
    cs = make_state([card(CardId.FISTICUFFS)], enemy_count=1)
    play(cs)
    assert hps(cs) == [33] and cs.player.block == 7

def test_fisticuffs_counts_damage_the_enemy_blocked():
    cs = make_state([card(CardId.FISTICUFFS)], enemy_count=1)
    cs.enemies[0].block = 5
    play(cs)
    assert hps(cs) == [38] and cs.player.block == 7

def test_fisticuffs_counts_overkill():
    cs = make_state([card(CardId.FISTICUFFS)], enemy_count=1, enemy_hp=3)
    play(cs)
    assert cs.player.block == 7

def test_fisticuffs_block_is_reduced_by_frail():
    cs = make_state([card(CardId.FISTICUFFS)], enemy_count=1)
    cs.player.apply_status(StatusId.FRAIL, 2)
    play(cs)
    assert cs.player.block == 5      # 7 * 0.75

def test_mind_blast_counts_the_draw_pile():
    cs = make_state([card(CardId.MIND_BLAST)], enemy_count=1, enemy_hp=40); fill(cs, 12)
    play(cs)
    assert hps(cs) == [28]

def test_mind_blast_is_innate_and_upgrades_to_free():
    assert CardId.MIND_BLAST.keyword_mask & 4
    assert card(CardId.MIND_BLAST).upgraded_copy().energy_cost == 0

def test_gold_axe_counts_plays_this_combat():
    cs = make_state([strike(), strike(), card(CardId.GOLD_AXE)], enemy_count=1, enemy_hp=40)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0); sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert hps(cs) == [40 - 12 - 2]

def test_gold_axe_counts_auto_plays_and_survives_turns():
    cs = make_state([card(CardId.GOLD_AXE)], enemy_count=1, enemy_hp=40)
    cs.player.cards_played_total = 7
    play(cs)
    assert hps(cs) == [33] and cs.player.cards_played_total == 8

def test_upgraded_gold_axe_retains():
    assert card(CardId.GOLD_AXE).upgraded_copy().retains

def test_gold_axe_total_is_read_from_the_card_text():
    raw = {"index": 0, "id": "GOLD_AXE", "name": "Gold Axe", "type": "Attack", "cost": "1", "description": "Deal 9 damage.",
           "target_type": "AnyEnemy", "can_play": True, "is_upgraded": False, "keywords": [], "card_keywords": []}
    from sts2_lite.player import Player
    p = Player(); p.hand = []; p.draw_pile = []; p.discard_pile = [Card.from_dict(raw)]; p.exhaust_pile = []
    p._read_growing_cards()
    assert p.cards_played_total == 9

def test_rend_counts_debuffs():
    cs = make_state([card(CardId.REND)], enemy_count=1, enemy_hp=60)
    cs.enemies[0].apply_status(StatusId.WEAK, 2); cs.enemies[0].apply_status(StatusId.FRAIL, 1)
    play(cs)
    assert hps(cs) == [60 - 25]

def test_rend_without_debuffs_and_upgraded():
    cs = make_state([card(CardId.REND)], enemy_count=1, enemy_hp=60); play(cs)
    assert hps(cs) == [45]
    cs = make_state([card(CardId.REND, True)], enemy_count=1, enemy_hp=60)
    cs.enemies[0].apply_status(StatusId.WEAK, 1)
    play(cs)
    assert hps(cs) == [60 - 26]

def test_rend_ignores_temporary_debuffs():
    cs = make_state([card(CardId.REND)], enemy_count=1, enemy_hp=60)
    cs.enemies[0].apply_status(StatusId.MANGLE, 3)
    play(cs)
    assert hps(cs) == [45]

def test_omnislice_copies_the_damage_to_the_others_unpowered():
    cs = make_state([card(CardId.OMNISLICE)], enemy_count=3, enemy_hp=40)
    cs.player.apply_status(StatusId.STRENGTH, 2)
    cs.enemies[1].apply_status(StatusId.VULNERABLE, 2)
    play(cs, target=0)
    assert hps(cs) == [30, 30, 30]       # 8 + 2 Strength; the others take exactly 10, their Vulnerable ignored

def test_omnislice_passes_on_blocked_damage_too():
    cs = make_state([card(CardId.OMNISLICE)], enemy_count=2, enemy_hp=40)
    cs.enemies[0].block = 20
    play(cs)
    assert hps(cs) == [40, 32]

def test_omnislice_alone():
    cs = make_state([card(CardId.OMNISLICE, True)], enemy_count=1, enemy_hp=40)
    play(cs)
    assert hps(cs) == [29]

def test_volley_hits_once_per_energy():
    cs = make_state([card(CardId.VOLLEY)], enemy_count=1, enemy_hp=100)
    play(cs)
    assert hps(cs) == [100 - 30] and cs.energy == 0

def test_volley_with_no_energy_does_nothing():
    cs = make_state([card(CardId.VOLLEY)], enemy_count=1, enemy_hp=100)
    cs.energy = 0
    play(cs)
    assert hps(cs) == [100]

def test_hand_of_greed_gives_gold_on_a_kill():
    cs = make_state([card(CardId.HAND_OF_GREED)], enemy_count=1, enemy_hp=20)
    cs.player.gold = 5
    play(cs)
    assert cs.player.gold == 25

def test_hand_of_greed_gives_nothing_without_a_kill_or_for_a_minion():
    cs = make_state([card(CardId.HAND_OF_GREED)], enemy_count=1, enemy_hp=40); play(cs)
    assert cs.player.gold == 0
    cs = make_state([card(CardId.HAND_OF_GREED)], enemy_count=1, enemy_hp=20)
    cs.enemies[0].apply_status(StatusId.MINION, 1)
    play(cs)
    assert cs.player.gold == 0

def test_upgraded_hand_of_greed_pays_twenty_five():
    cs = make_state([card(CardId.HAND_OF_GREED, True)], enemy_count=1, enemy_hp=25)
    play(cs)
    assert cs.player.gold == 25

# ------------------------------------------------------------ Purity
def purity_state(hand_size=4, upgraded=False):
    cs = make_state([card(CardId.PURITY, upgraded)] + [strike() for _ in range(hand_size)], enemy_count=1)
    return cs

def test_purity_offers_up_to_three_cards_and_can_stop():
    cs = purity_state(5)
    sim = play(cs)
    assert cs.pending_choice is not None and {a["action"] for a in sim.get_available_actions()} == {"choose_card", "confirm_choice"}
    sim.choose_card(cs.pending_choice.indices[0])
    sim.confirm_choice()
    assert len(cs.player.exhaust_pile) == 2 and cs.pending_choice is None       # Purity itself and one card

def test_purity_exhausts_three_when_asked():
    cs = purity_state(5)
    sim = play(cs)
    for _ in range(3):
        sim.choose_card(cs.pending_choice.indices[0])
    assert cs.pending_choice is None and len(cs.player.exhaust_pile) == 4 and len(cs.player.hand) == 2

def test_upgraded_purity_exhausts_up_to_five():
    cs = purity_state(7, True)
    sim = play(cs)
    for _ in range(5):
        sim.choose_card(cs.pending_choice.indices[0])
    assert cs.pending_choice is None and len(cs.player.hand) == 2

def test_purity_with_an_empty_hand_asks_nothing():
    cs = purity_state(0)
    play(cs)
    assert cs.pending_choice is None

def test_purity_a_lone_card_can_still_be_declined():
    cs = purity_state(1)
    sim = play(cs)
    assert cs.pending_choice is not None
    sim.confirm_choice()
    assert len(cs.player.hand) == 1

def test_purity_keywords():
    assert CardId.PURITY.keyword_mask & 16 and CardId.PURITY.keyword_mask & 1

def test_purity_stops_when_the_hand_runs_out():
    cs = purity_state(2)
    sim = play(cs)
    sim.choose_card(cs.pending_choice.indices[0])
    sim.choose_card(cs.pending_choice.indices[0]) if cs.pending_choice else None
    assert cs.pending_choice is None

# ------------------------------------------------------------ plumbing
def test_damage_taken_counts_blocked_and_unblocked_damage():
    e = make_state([], enemy_count=1).enemies[0]
    e.block = 4
    e.apply_damage(10)
    assert e.damage_taken == 10 and e.current_hp == 34

def test_every_colorless_card_has_a_play_function_and_a_table_entry():
    from sts2_lite.card import COLORLESS_CARDS, GET_CARD_FUNCTION
    assert len(COLORLESS_CARDS) == 51
    for card_id in COLORLESS_CARDS:
        assert card_id in GET_CARD_FUNCTION
        assert Card.create_generated(card_id).card_id == card_id

def test_card_ids_load_from_the_bridge():
    for name in ("FINESSE", "FLASH_OF_STEEL", "ULTIMATE_STRIKE", "MASTER_OF_STRATEGY", "HAND_OF_GREED", "GOLD_AXE"):
        assert CardId[name]

# ------------------------------------------------------------ captures: Tests/data/cards/colorless
import json
from pathlib import Path
from sts2_lite.combat import CombatState
from sts2_lite.verify import compare

CAPTURES = Path(__file__).parent / "data" / "cards" / "colorless"

def capture(name):
    return json.loads((CAPTURES / f"{name}.json").read_text())

def replay_from_discard(name, card_id, enemy_hp):
    """A capture taken after a play: put the card back in the hand with the energy and enemy HP from before it."""
    cs = CombatState.from_dict(capture(name))
    played = next(c for c in cs.player.discard_pile if c.card_id == card_id)
    cs.player.discard_pile.remove(played)
    cs.player.hand.insert(0, played)
    cs.energy += played.energy_cost
    played.is_unplayable = False       # the capture was taken when it could not be afforded
    cs.enemies[0].current_hp = enemy_hp
    return cs

def test_capture_rend_counts_strength_loss_but_not_the_temporary_marker():
    cs = replay_from_discard("rend_temp_debuff", CardId.REND, 38)
    assert cs.enemies[0].status_amount(StatusId.MANGLE) == 1
    play(cs)
    assert hps(cs) == [18]       # 15 + 5 for the Strength loss, none for Mangle

def test_capture_fisticuffs_for_zero_matches_the_game():
    cs = CombatState.from_dict(capture("fisticuffs_for_0_before"))
    index = next(i for i, c in enumerate(cs.player.hand) if c.card_id == CardId.FISTICUFFS)
    CombatSimulator(cs).play_card(index, 0)
    assert compare(cs, CombatState.from_dict(capture("fisticuffs_for_0_after"))) == []
    assert cs.player.block == 0

def test_capture_fisticuffs_with_frail_gives_five():
    cs = replay_from_discard("fisticuffs_frail", CardId.FISTICUFFS, 38)
    expected_block = cs.player.block
    cs.player.block = 0
    play(cs)
    assert hps(cs) == [31] and cs.player.block == expected_block == 5

def test_capture_gold_axe_total_is_read_from_the_text_with_strength_removed():
    cs = CombatState.from_dict(capture("gold_axe"))
    assert cs.player.cards_played_total == 3
    index = next(i for i, c in enumerate(cs.player.hand) if c.card_id == CardId.GOLD_AXE)
    CombatSimulator(cs).play_card(index, 0)
    assert hps(cs)[0] == 37 - 6

def test_capture_purity_screen_loads_as_an_optional_pick_of_up_to_three():
    cs = CombatState.from_dict(capture("purity"))
    pending = cs.pending_choice
    assert pending.kind == "exhaust_any" and pending.amount == 3 and pending.optional
    assert len(pending.indices) == 4           # the three Strikes are the same card
    sim = CombatSimulator(cs)
    assert {a["action"] for a in sim.get_available_actions()} == {"choose_card", "confirm_choice"}

def test_capture_omnislice_passes_on_damage_the_target_blocked():
    cs = CombatState.from_dict(capture("omnislice_attack_target_0_with_block"))
    omnislice = next(c for c in cs.player.discard_pile if c.card_id == CardId.OMNISLICE)
    cs.player.discard_pile.remove(omnislice)
    cs.player.hand.insert(0, omnislice)
    omnislice.is_unplayable = False
    cs.enemies[0].block = 11             # the 11 damage (8 + 3 Strength) is absorbed whole
    cs.enemies[1].current_hp = 46
    play(cs, target=0)
    assert hps(cs) == [38, 35] and cs.enemies[0].block == 0

def test_capture_purity_with_two_ticked_cards_has_one_pick_left():
    cs = CombatState.from_dict(capture("purity_with_selected"))
    pending = cs.pending_choice
    assert pending.kind == "exhaust_any" and pending.amount == 1
    names = [cs.player.hand[i].name for i in pending.indices]
    assert sorted(names) == ["Bash", "Gold Axe", "Strike"]       # the ticked Strike and Defend are not offered again
