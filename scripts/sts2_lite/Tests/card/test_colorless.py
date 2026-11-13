import pytest
import json
from sts2_lite.card import Card, CardId, CardKeyword, CardType, TargetType, COLORLESS_CARDS, GENERATABLE_CARDS, JACK_POOL, ZERO_COST_POOL, RARE_CARDS, transform_options
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.status import StatusId, StatusInstance
from sts2_lite.Tests.card.test_card import make_card, make_state, hps
from pathlib import Path
from sts2_lite.verify import compare, is_random_step
from sts2_lite.selection import game_index
from sts2_lite import rng


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

CAPTURES = Path(__file__).parents[1] / "data" / "cards" / "colorless"

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


def bash():
    return make_card(CardId.BASH, "Bash", CardType.Attack, 2, TargetType.AnyEnemy)

def ids(pile):
    return [c.card_id for c in pile]

# ------------------------------------------------------------ Secret Technique / Secret Weapon
def test_secret_technique_offers_only_skills_from_the_draw_pile():
    cs = make_state([card(CardId.SECRET_TECHNIQUE)], enemy_count=1)
    cs.player.draw_pile = [strike(), defend(), card(CardId.FINESSE), bash()]
    sim = play(cs)
    assert cs.pending_choice.pile == "draw" and not cs.pending_choice.optional
    offered = {cs.player.draw_pile[i].card_id for i in cs.pending_choice.indices}
    assert offered == {CardId.DEFEND_IRONCLAD, CardId.FINESSE}
    assert {a["action"] for a in sim.get_available_actions()} == {"choose_card"}

def test_secret_technique_moves_the_pick_to_the_hand_and_exhausts():
    cs = make_state([card(CardId.SECRET_TECHNIQUE)], enemy_count=1)
    cs.player.draw_pile = [strike(), defend(), card(CardId.FINESSE)]
    sim = play(cs)
    index = next(i for i in cs.pending_choice.indices if cs.player.draw_pile[i].card_id == CardId.FINESSE)
    sim.choose_card(index)
    assert ids(cs.player.hand) == [CardId.FINESSE] and len(cs.player.draw_pile) == 2
    assert len(cs.player.exhaust_pile) == 1 and cs.pending_choice is None

def test_upgraded_secret_technique_does_not_exhaust():
    cs = make_state([card(CardId.SECRET_TECHNIQUE).upgraded_copy()], enemy_count=1)
    cs.player.draw_pile = [defend()]
    play(cs)
    assert cs.player.exhaust_pile == [] and len(cs.player.discard_pile) == 1

def test_a_single_matching_skill_is_taken_without_asking():
    cs = make_state([card(CardId.SECRET_TECHNIQUE)], enemy_count=1)
    cs.player.draw_pile = [strike(), defend()]
    play(cs)
    assert cs.pending_choice is None and ids(cs.player.hand) == [CardId.DEFEND_IRONCLAD]

def test_no_matching_card_asks_nothing():
    cs = make_state([card(CardId.SECRET_TECHNIQUE)], enemy_count=1)
    cs.player.draw_pile = [strike()]
    play(cs)
    assert cs.pending_choice is None and cs.player.hand == []

def test_secret_weapon_offers_attacks():
    cs = make_state([card(CardId.SECRET_WEAPON)], enemy_count=1)
    cs.player.draw_pile = [strike(), bash(), defend()]
    play(cs)
    offered = {cs.player.draw_pile[i].card_id for i in cs.pending_choice.indices}
    assert offered == {CardId.STRIKE_IRONCLAD, CardId.BASH}

def test_taking_a_known_top_card_forgets_that_it_was_on_top():
    cs = make_state([card(CardId.SECRET_WEAPON)], enemy_count=1)
    cs.player.draw_pile = [defend(), bash(), strike()]
    cs.player.known_top = 1
    sim = play(cs)
    sim.choose_card(next(i for i in cs.pending_choice.indices if cs.player.draw_pile[i].card_id == CardId.STRIKE_IRONCLAD))
    assert cs.player.known_top == 0

def test_a_full_hand_sends_the_pick_to_the_discard_pile():
    cs = make_state([card(CardId.SECRET_WEAPON)] + [defend() for _ in range(10)], enemy_count=1)
    cs.player.draw_pile = [strike(), bash()]
    sim = play(cs)
    sim.choose_card(cs.pending_choice.indices[0])
    assert len(cs.player.hand) == 10 and len(cs.player.discard_pile) == 1

# ------------------------------------------------------------ Seeker Strike
def test_seeker_strike_hits_and_offers_three_cards():
    cs = make_state([card(CardId.SEEKER_STRIKE)], enemy_count=1, enemy_hp=40)
    cs.player.draw_pile = [strike(), defend(), bash(), card(CardId.FINESSE), card(CardId.PRODUCTION)]
    play(cs)
    assert hps(cs) == [31] and len(cs.pending_choice.indices) == 3 and cs.pending_choice.hidden

def test_upgraded_seeker_strike_deals_twelve():
    cs = make_state([card(CardId.SEEKER_STRIKE).upgraded_copy()], enemy_count=1, enemy_hp=40)
    cs.player.draw_pile = [strike()]
    play(cs)
    assert hps(cs) == [28]

def test_seeker_strike_with_fewer_cards_offers_what_there_is():
    cs = make_state([card(CardId.SEEKER_STRIKE)], enemy_count=1)
    cs.player.draw_pile = [strike(), bash()]
    play(cs)
    assert len(cs.pending_choice.indices) == 2

def test_seeker_strike_with_an_empty_draw_pile_asks_nothing():
    cs = make_state([card(CardId.SEEKER_STRIKE)], enemy_count=1)
    play(cs)
    assert cs.pending_choice is None

def test_adopting_the_games_offer_replaces_the_random_one():
    cs = make_state([card(CardId.SEEKER_STRIKE)], enemy_count=1)
    cs.player.draw_pile = [strike(), defend(), bash(), card(CardId.FINESSE), card(CardId.PRODUCTION)]
    play(cs)
    offered = [{"index": 0, "id": "FINESSE", "is_upgraded": False}, {"index": 1, "id": "BASH", "is_upgraded": False},
               {"index": 2, "id": "PRODUCTION", "is_upgraded": False}]
    cs.adopt_offer(offered)
    assert {cs.player.draw_pile[i].card_id for i in cs.pending_choice.indices} == {CardId.FINESSE, CardId.BASH, CardId.PRODUCTION}
    assert not cs.pending_choice.hidden

def test_seeker_strike_is_a_random_step_and_a_strike():
    from sts2_lite.card import STRIKE_CARDS
    assert CardId.SEEKER_STRIKE in STRIKE_CARDS
    cs = make_state([card(CardId.SEEKER_STRIKE)], enemy_count=1)
    cs.player.draw_pile = [strike(), bash()]
    from sts2_lite.combat import CombatState
    before = CombatState.deepcopy(cs)
    play(cs)
    assert is_random_step(before, cs, [{"action": "play_card", "card_index": 0, "target": 0}])

# ------------------------------------------------------------ Thinking Ahead
def test_thinking_ahead_draws_two_then_puts_a_card_on_top():
    cs = make_state([card(CardId.THINKING_AHEAD), strike()], enemy_count=1)
    cs.player.draw_pile = [defend(), bash(), card(CardId.FINESSE)]
    sim = play(cs)
    assert len(cs.player.hand) == 3 and cs.pending_choice.pile == "hand" and not cs.pending_choice.optional
    pick = next(i for i in cs.pending_choice.indices if cs.player.hand[i].card_id == CardId.BASH)
    sim.choose_card(pick)
    assert cs.player.draw_pile[-1].card_id == CardId.BASH and cs.player.known_top == 1
    assert len(cs.player.hand) == 2 and len(cs.player.exhaust_pile) == 1

def test_the_card_put_back_is_drawn_next():
    cs = make_state([card(CardId.THINKING_AHEAD)], enemy_count=1)
    cs.player.draw_pile = [defend(), bash(), strike()]
    sim = play(cs)
    sim.choose_card(next(i for i in cs.pending_choice.indices if cs.player.hand[i].card_id == CardId.STRIKE_IRONCLAD))
    drawn = cs.player.draw_card()
    assert drawn.card_id == CardId.STRIKE_IRONCLAD

def test_thinking_ahead_with_a_lone_hand_card_puts_it_back_without_asking():
    cs = make_state([card(CardId.THINKING_AHEAD)], enemy_count=1)
    cs.player.draw_pile = [defend()]
    play(cs)
    assert cs.pending_choice is None and cs.player.hand == [] and ids(cs.player.draw_pile) == [CardId.DEFEND_IRONCLAD]

def test_thinking_ahead_with_nothing_to_draw_or_hold_does_nothing():
    cs = make_state([card(CardId.THINKING_AHEAD)], enemy_count=1)
    play(cs)
    assert cs.pending_choice is None

def test_upgraded_thinking_ahead_does_not_exhaust():
    cs = make_state([card(CardId.THINKING_AHEAD).upgraded_copy()], enemy_count=1)
    cs.player.draw_pile = [defend()]
    play(cs)
    assert cs.player.exhaust_pile == []

def test_secret_and_seeker_cards_exist():
    for name in ("SECRET_TECHNIQUE", "SECRET_WEAPON", "SEEKER_STRIKE", "THINKING_AHEAD"):
        assert CardId[name]

# ------------------------------------------------------------ captures: Tests/data/cards/colorless

CAPTURES = Path(__file__).parents[1] / "data" / "cards" / "colorless"

def capture(name):
    return json.loads((CAPTURES / f"{name}.json").read_text())

def test_capture_secret_technique_with_two_identical_skills_is_settled_by_the_sim():
    screen = capture("secret_technique")
    assert screen["can_skip"] is False and [c["id"] for c in screen["cards"]] == ["DEFEND_IRONCLAD"] * 2
    cs = make_state([card(CardId.SECRET_TECHNIQUE)], enemy_count=1)
    cs.player.draw_pile = [strike(), defend(), defend(), bash()]
    play(cs)
    # the game still shows a screen for two identical cards; the sim takes one at once and the tester's auto_pick clicks the first
    assert cs.pending_choice is None and ids(cs.player.hand) == [CardId.DEFEND_IRONCLAD] and len(cs.player.draw_pile) == 3

def test_capture_seeker_strike_offer_is_adopted_by_the_sim():
    screen = capture("seeker_strike")
    cs = make_state([card(CardId.SEEKER_STRIKE)], enemy_count=1)
    cs.player.draw_pile = [defend(), strike(), strike(), bash(), defend(), card(CardId.FINESSE)]
    sim = play(cs)
    cs.adopt_offer(screen["cards"])
    actions = [a for a in sim.get_available_actions() if a["action"] == "choose_card"]
    assert sorted(a["card_id"] for a in actions) == ["BASH", "STRIKE_IRONCLAD"]
    for a in actions:
        assert game_index(a, screen["cards"]) is not None
    sim.choose_card(next(a["card_index"] for a in actions if a["card_id"] == "BASH"))
    assert CardId.BASH in ids(cs.player.hand)

def test_capture_thinking_ahead_screen_loads_as_a_required_pick_of_the_hand():
    cs = CombatState.from_dict(capture("thinking_ahead"))
    pending = cs.pending_choice
    assert pending.kind == "to_draw_pile" and pending.pile == "hand" and not pending.optional
    assert sorted(cs.player.hand[i].card_id.name for i in pending.indices) == ["BASH", "DEFEND_IRONCLAD", "STRIKE_IRONCLAD"]
    sim = CombatSimulator(cs)
    hand = len(cs.player.hand)
    sim.choose_card(next(i for i in pending.indices if cs.player.hand[i].card_id == CardId.BASH))
    assert cs.player.draw_pile[-1].card_id == CardId.BASH and len(cs.player.hand) == hand - 1


def one_enemy(hand, hp=100):
    return make_state(hand, enemy_count=1, enemy_hp=hp)

def attacker(cs, damage, hits=1, index=0):
    e = cs.enemies[index]
    e.attack_damage, e.num_attacks = damage, hits
    return e

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim

def end_turn(cs):
    sim = CombatSimulator(cs)
    sim.end_turn()
    return sim

def status(creature, status_id):
    return creature.status_amount(status_id)

# ------------------------------------------------------------ Equilibrium, Salvo: the hand is retained
def test_equilibrium_blocks_and_keeps_the_hand_for_one_turn():
    cs = one_enemy([card(CardId.EQUILIBRIUM), strike(), defend()])
    play(cs)
    assert cs.player.block == 13 and status(cs.player, StatusId.RETAIN_HAND) == 1
    end_turn(cs)
    assert [c.card_id for c in cs.player.hand][:2] == [CardId.STRIKE_IRONCLAD, CardId.DEFEND_IRONCLAD]
    assert StatusId.RETAIN_HAND not in cs.player.status
    assert cs.player.discard_pile == [c for c in cs.player.discard_pile if c.card_id == CardId.EQUILIBRIUM]

def test_equilibrium_upgrade_block():
    cs = one_enemy([card(CardId.EQUILIBRIUM, True)])
    play(cs)
    assert cs.player.block == 16

def test_hand_is_discarded_after_the_retained_turn():
    cs = one_enemy([card(CardId.EQUILIBRIUM), strike()])
    play(cs)
    end_turn(cs)
    cs.player.draw_pile = [defend() for _ in range(10)]
    end_turn(cs)
    assert CardId.STRIKE_IRONCLAD not in [c.card_id for c in cs.player.hand]
    assert CardId.STRIKE_IRONCLAD in [c.card_id for c in cs.player.discard_pile]

def test_two_retains_last_two_turns():
    cs = one_enemy([card(CardId.EQUILIBRIUM), card(CardId.EQUILIBRIUM), strike()])
    cs.energy = 4
    sim = CombatSimulator(cs)
    sim.play_card(0, 0); sim.play_card(0, 0)
    assert status(cs.player, StatusId.RETAIN_HAND) == 2
    sim.end_turn()
    assert status(cs.player, StatusId.RETAIN_HAND) == 1

def test_salvo_hits_and_retains():
    for upgraded, damage in ((False, 12), (True, 16)):
        cs = one_enemy([card(CardId.SALVO, upgraded), strike()], hp=40)
        play(cs)
        assert hps(cs) == [40 - damage] and status(cs.player, StatusId.RETAIN_HAND) == 1

# ------------------------------------------------------------ Panic Button: no card block for two turns
def test_panic_button_blocks_then_stops_card_block():
    cs = one_enemy([card(CardId.PANIC_BUTTON), defend()])
    sim = play(cs)
    assert cs.player.block == 30 and status(cs.player, StatusId.NO_BLOCK) == 2
    sim.play_card(0, 0)
    assert cs.player.block == 30            # the Defend gave nothing

def test_panic_button_upgrade_and_exhaust():
    cs = one_enemy([card(CardId.PANIC_BUTTON, True)])
    play(cs)
    assert cs.player.block == 40 and cs.player.exhaust_pile

def test_no_block_covers_this_turn_and_the_next_only():
    cs = one_enemy([card(CardId.PANIC_BUTTON)])
    play(cs)
    end_turn(cs)
    assert status(cs.player, StatusId.NO_BLOCK) == 1     # next turn's cards still give nothing
    cs.player.hand = [defend()]
    cs.player.block = 0
    play(cs)
    assert cs.player.block == 0
    end_turn(cs)
    assert StatusId.NO_BLOCK not in cs.player.status

def test_no_block_does_not_stop_block_that_is_not_from_a_card():
    cs = one_enemy([defend()])
    attacker(cs, 4)
    cs.player.apply_status(StatusId.NO_BLOCK, 2)
    cs.player.apply_status(StatusId.PLATING, 4)
    end_turn(cs)
    assert cs.player.current_hp == 50 and StatusId.NO_BLOCK in cs.player.status

# ------------------------------------------------------------ Prolong
def test_prolong_stores_the_current_block():
    cs = one_enemy([card(CardId.PROLONG)])
    cs.player.block = 12
    play(cs)
    assert status(cs.player, StatusId.BLOCK_NEXT_TURN) == 12 and cs.player.exhaust_pile

def test_prolong_with_no_block_does_nothing():
    cs = one_enemy([card(CardId.PROLONG)])
    play(cs)
    assert StatusId.BLOCK_NEXT_TURN not in cs.player.status

def test_prolong_returns_the_block_next_turn_unpowered():
    cs = one_enemy([card(CardId.PROLONG)])
    cs.player.block = 12
    cs.player.apply_status(StatusId.FRAIL, 2)
    cs.player.apply_status(StatusId.DEXTERITY, -3)
    play(cs)
    end_turn(cs)
    assert cs.player.block == 12 and StatusId.BLOCK_NEXT_TURN not in cs.player.status

def test_upgraded_prolong_does_not_exhaust():
    cs = one_enemy([card(CardId.PROLONG).upgraded_copy()])
    cs.player.block = 5
    play(cs)
    assert not cs.player.exhaust_pile and len(cs.player.discard_pile) == 1

# ------------------------------------------------------------ Fasten
def test_fasten_adds_block_to_defends_only():
    for upgraded, extra in ((False, 4), (True, 6)):
        cs = one_enemy([card(CardId.FASTEN, upgraded), defend(), card(CardId.ULTIMATE_DEFEND), card(CardId.FINESSE)])
        cs.energy = 6
        sim = play(cs)
        sim.play_card(0, 0)
        assert cs.player.block == 5 + extra
        sim.play_card(0, 0)
        assert cs.player.block == 5 + extra + 11 + extra
        sim.play_card(0, 0)
        assert cs.player.block == 5 + extra + 11 + extra + 4     # Finesse is not a Defend

def test_fasten_is_added_before_frail():
    cs = one_enemy([defend()])
    cs.player.apply_status(StatusId.FASTEN, 4)
    cs.player.apply_status(StatusId.FRAIL, 2)
    play(cs)
    assert cs.player.block == 6        # (5 + 4) * 0.75

# ------------------------------------------------------------ Prep Time
def test_prep_time_gives_vigor_every_turn():
    cs = one_enemy([card(CardId.PREP_TIME)])
    play(cs)
    assert status(cs.player, StatusId.PREP_TIME) == 4 and StatusId.VIGOR not in cs.player.status
    end_turn(cs)
    assert status(cs.player, StatusId.VIGOR) == 4
    cs.player.hand = [card(CardId.SALVO)]
    sim = CombatSimulator(cs)
    before = hps(cs)[0]
    sim.play_card(0, 0)
    assert before - hps(cs)[0] == 12 + 4 and StatusId.VIGOR not in cs.player.status

def test_prep_time_upgrade():
    cs = one_enemy([card(CardId.PREP_TIME, True)])
    play(cs)
    assert status(cs.player, StatusId.PREP_TIME) == 6

# ------------------------------------------------------------ Dark Shackles
def test_dark_shackles_takes_strength_until_the_enemy_turn_ends():
    for upgraded, loss in ((False, 9), (True, 15)):
        cs = one_enemy([card(CardId.DARK_SHACKLES, upgraded)])
        cs.enemies[0].apply_status(StatusId.STRENGTH, 3)
        play(cs)
        e = cs.enemies[0]
        assert status(e, StatusId.STRENGTH) == 3 - loss and status(e, StatusId.DARK_SHACKLES) == loss
        assert cs.player.exhaust_pile
        end_turn(cs)
        assert status(e, StatusId.STRENGTH) == 3 and StatusId.DARK_SHACKLES not in e.status

def test_dark_shackles_weakens_the_attack_that_turn():
    cs = one_enemy([card(CardId.DARK_SHACKLES)])
    attacker(cs, 15)
    play(cs)
    end_turn(cs)
    assert cs.player.current_hp == 50 - 6

def test_artifact_stops_dark_shackles():
    cs = one_enemy([card(CardId.DARK_SHACKLES)])
    cs.enemies[0].apply_status(StatusId.ARTIFACT, 1)
    play(cs)
    assert StatusId.STRENGTH not in cs.enemies[0].status and StatusId.DARK_SHACKLES not in cs.enemies[0].status

def test_rend_does_not_count_dark_shackles():
    cs = one_enemy([card(CardId.DARK_SHACKLES), card(CardId.REND)], hp=100)
    cs.energy = 3
    sim = play(cs)
    cs.enemies[0].apply_status(StatusId.WEAK, 1)
    sim.play_card(0, 0)
    assert hps(cs) == [100 - (15 + 2 * 5)]      # Weak and the Strength loss count; the temporary marker does not

# ------------------------------------------------------------ Automation
def test_automation_pays_energy_every_ten_draws():
    cs = one_enemy([card(CardId.AUTOMATION)])
    cs.player.draw_pile = [defend() for _ in range(25)]
    sim = play(cs)
    assert cs.player.status[StatusId.AUTOMATION].records == [[10]]
    cs.player.draw_cards(9)
    assert cs.energy == 2 and status(cs.player, StatusId.AUTOMATION) == 1
    cs.player.hand = []
    cs.player.draw_cards(1)
    assert cs.energy == 3 and status(cs.player, StatusId.AUTOMATION) == 10

def test_automation_counts_the_turn_start_hand():
    cs = one_enemy([])
    cs.player.draw_pile = [defend() for _ in range(20)]
    cs.player.apply_status(StatusId.AUTOMATION, 7)
    cs.player.status[StatusId.AUTOMATION].records = [[7]]
    end_turn(cs)
    assert status(cs.player, StatusId.AUTOMATION) == 2      # five cards drawn

def test_two_automations_count_separately():
    cs = one_enemy([card(CardId.AUTOMATION), card(CardId.AUTOMATION)])
    cs.player.draw_pile = [defend() for _ in range(20)]
    sim = play(cs)
    cs.player.draw_cards(4)
    sim.play_card(0, 0)
    cs.player.hand = []
    assert cs.player.status[StatusId.AUTOMATION].records == [[6], [10]]
    cs.player.draw_cards(6)
    assert cs.player.status[StatusId.AUTOMATION].records == [[10], [4]]

def test_automation_upgrade_is_cheaper():
    assert card(CardId.AUTOMATION).upgraded_copy().energy_cost == 0
    assert card(CardId.NOSTALGIA).upgraded_copy().energy_cost == 0 and card(CardId.MAYHEM).upgraded_copy().energy_cost == 1

# ------------------------------------------------------------ Panache
def test_panache_hits_every_enemy_on_the_fifth_card_after_it():
    cs = make_state([card(CardId.PANACHE)] + [defend() for _ in range(6)], enemy_count=2)
    cs.energy = 9
    sim = play(cs)
    record = cs.player.status[StatusId.PANACHE].records[0]
    assert record == [5, 10, 1] or record[0] == 5       # the Panache card does not count itself
    for _ in range(4):
        sim.play_card(0, 0)
    assert hps(cs) == [40, 40] and status(cs.player, StatusId.PANACHE) == 1
    sim.play_card(0, 0)
    assert hps(cs) == [30, 30] and status(cs.player, StatusId.PANACHE) == 5

def test_panache_damage_ignores_strength_and_resets_each_turn():
    cs = one_enemy([card(CardId.PANACHE, True), defend(), defend()])
    cs.player.apply_status(StatusId.STRENGTH, 5)
    sim = play(cs)
    sim.play_card(0, 0)
    assert status(cs.player, StatusId.PANACHE) == 4
    sim.end_turn()
    assert status(cs.player, StatusId.PANACHE) == 5 and cs.player.status[StatusId.PANACHE].records[0][1] == 14

def test_panache_can_win_the_fight():
    cs = one_enemy([card(CardId.PANACHE)] + [defend() for _ in range(5)], hp=10)
    cs.energy = 9
    sim = play(cs)
    for _ in range(5):
        sim.play_card(0, 0)
    assert sim.is_over and not cs.enemies

# ------------------------------------------------------------ Rolling Boulder
def test_rolling_boulder_hits_all_enemies_at_turn_start_and_grows():
    cs = make_state([card(CardId.ROLLING_BOULDER)], enemy_count=2)
    cs.energy = 3
    play(cs)
    assert status(cs.player, StatusId.ROLLING_BOULDER) == 5
    end_turn(cs)
    assert hps(cs) == [35, 35] and status(cs.player, StatusId.ROLLING_BOULDER) == 10
    end_turn(cs)
    assert hps(cs) == [25, 25] and status(cs.player, StatusId.ROLLING_BOULDER) == 15

def test_rolling_boulder_upgrade_starts_at_ten():
    cs = one_enemy([card(CardId.ROLLING_BOULDER, True)])
    play(cs)
    end_turn(cs)
    assert hps(cs) == [90]

def test_rolling_boulder_kills():
    cs = one_enemy([card(CardId.ROLLING_BOULDER)], hp=5)
    play(cs)
    sim = end_turn(cs)
    assert sim.is_over

def test_two_rolling_boulders_are_separate():
    cs = one_enemy([card(CardId.ROLLING_BOULDER), card(CardId.ROLLING_BOULDER)])
    cs.energy = 6
    sim = play(cs)
    sim.play_card(0, 0)
    sim.end_turn()
    assert hps(cs) == [90] and cs.player.status[StatusId.ROLLING_BOULDER].records == [[10], [10]]

# ------------------------------------------------------------ The Bomb
def test_the_bomb_explodes_at_the_end_of_the_third_turn():
    for upgraded, damage in ((False, 40), (True, 50)):
        cs = make_state([card(CardId.THE_BOMB, upgraded)], enemy_count=2, enemy_hp=100)
        play(cs)
        assert status(cs.player, StatusId.THE_BOMB) == 3
        cs.player.draw_pile = [defend() for _ in range(15)]
        end_turn(cs)
        assert status(cs.player, StatusId.THE_BOMB) == 2 and hps(cs) == [100, 100]
        end_turn(cs)
        assert status(cs.player, StatusId.THE_BOMB) == 1 and hps(cs) == [100, 100]
        end_turn(cs)
        assert hps(cs) == [100 - damage] * 2 and StatusId.THE_BOMB not in cs.player.status

def test_the_bomb_ignores_strength():
    cs = one_enemy([card(CardId.THE_BOMB)])
    cs.player.apply_status(StatusId.STRENGTH, 9)
    cs.player.status[StatusId.THE_BOMB] = StatusInstance(StatusId.THE_BOMB, 1, [[1, 40]])
    end_turn(cs)
    assert hps(cs) == [60]

def test_two_bombs_tick_separately():
    cs = one_enemy([card(CardId.THE_BOMB), card(CardId.THE_BOMB)])
    cs.energy = 6
    sim = play(cs)
    sim.play_card(0, 0)
    sim.end_turn()
    cs.energy = 6
    cs.player.hand = [card(CardId.THE_BOMB).upgraded_copy()]
    sim.play_card(0, 0)
    assert cs.player.status[StatusId.THE_BOMB].records == [[2, 40], [2, 40], [3, 50]]
    sim.end_turn()
    assert cs.player.status[StatusId.THE_BOMB].records == [[1, 40], [1, 40], [2, 50]]
    sim.end_turn()
    assert hps(cs) == [100 - 80] and cs.player.status[StatusId.THE_BOMB].records == [[1, 50]]

# ------------------------------------------------------------ The Gambit
def test_the_gambit_blocks_and_marks_the_player():
    for upgraded, block in ((False, 50), (True, 75)):
        cs = one_enemy([card(CardId.THE_GAMBIT, upgraded)])
        play(cs)
        assert cs.player.block == block and StatusId.THE_GAMBIT in cs.player.status

def test_the_gambit_kills_on_unblocked_attack_damage():
    cs = one_enemy([card(CardId.THE_GAMBIT)])
    attacker(cs, 60)
    sim = play(cs)
    sim.end_turn()
    assert cs.player.current_hp <= 0 and sim.is_over     # 10 got through

def test_the_gambit_survives_fully_blocked_attacks():
    cs = one_enemy([card(CardId.THE_GAMBIT)])
    attacker(cs, 20)
    sim = play(cs)
    sim.end_turn()
    assert cs.player.current_hp == 50 and StatusId.THE_GAMBIT in cs.player.status

def test_the_gambit_ignores_unpowered_damage():
    cs = one_enemy([card(CardId.THE_GAMBIT)])
    play(cs)
    cs.player.block = 0
    cs.player.apply_damage(5)
    assert cs.player.current_hp == 45 and StatusId.THE_GAMBIT in cs.player.status

# ------------------------------------------------------------ Mayhem
def test_mayhem_plays_the_top_card_when_the_turn_begins():
    cs = one_enemy([card(CardId.MAYHEM)])
    play(cs)
    cs.player.draw_pile = [defend() for _ in range(5)] + [strike()] + [defend() for _ in range(5)]     # the end of the list is the top
    end_turn(cs)
    assert hps(cs) == [94] and len(cs.player.hand) == 5

def test_mayhem_upgrade_cost_and_stacking():
    cs = one_enemy([card(CardId.MAYHEM).upgraded_copy(), card(CardId.MAYHEM).upgraded_copy()])
    cs.energy = 2
    sim = play(cs)
    sim.play_card(0, 0)
    assert status(cs.player, StatusId.MAYHEM) == 2 and cs.energy == 0

def test_mayhem_takes_its_cards_before_playing_any():
    cs = one_enemy([card(CardId.MAYHEM)])
    play(cs)
    cs.player.apply_status(StatusId.MAYHEM, 1)
    cs.player.draw_pile = [strike(), strike()] + [defend() for _ in range(5)]
    sim = end_turn(cs)
    assert hps(cs) == [88]

def test_mayhem_discards_an_unplayable_card():
    cs = one_enemy([card(CardId.MAYHEM)])
    play(cs)
    cs.player.draw_pile = [Card.create_dazed()] + [defend() for _ in range(5)]
    end_turn(cs)
    assert any(c.card_id == CardId.DAZED for c in cs.player.discard_pile)

# ------------------------------------------------------------ Nostalgia
def test_nostalgia_puts_the_first_attack_or_skill_on_top_of_the_draw_pile():
    cs = one_enemy([card(CardId.NOSTALGIA), strike(), strike(), defend()])
    sim = play(cs)
    cs.player.draw_pile = []
    sim.play_card(0, 0)
    assert cs.player.draw_pile[-1].card_id == CardId.STRIKE_IRONCLAD and cs.player.known_top == 1
    assert not cs.player.discard_pile
    sim.play_card(0, 0)                         # the second Strike goes to the discard pile
    assert len(cs.player.discard_pile) == 1 and len(cs.player.draw_pile) == 1

def test_nostalgia_counts_cards_played_before_it():
    cs = one_enemy([strike(), card(CardId.NOSTALGIA), strike()])
    sim = play(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert len(cs.player.discard_pile) == 2 and not cs.player.draw_pile

def test_nostalgia_does_not_catch_an_exhausted_card():
    cs = one_enemy([card(CardId.NOSTALGIA), card(CardId.PANIC_BUTTON)])
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.exhaust_pile and not cs.player.draw_pile

def test_nostalgia_does_not_catch_powers():
    cs = one_enemy([card(CardId.NOSTALGIA), card(CardId.FASTEN)])
    sim = play(cs)
    sim.play_card(0, 0)
    assert not cs.player.draw_pile and not cs.player.discard_pile

def test_nostalgia_resets_each_turn():
    cs = one_enemy([card(CardId.NOSTALGIA)])
    play(cs)
    cs.player.hand = [strike()]
    cs.player.draw_pile = [defend() for _ in range(10)]
    sim = CombatSimulator(cs)
    sim.end_turn()
    cs.player.hand = [strike()]
    sim.play_card(0, 0)
    assert cs.player.draw_pile[-1].card_id == CardId.STRIKE_IRONCLAD

def test_nostalgia_two_stacks_catch_two_cards():
    cs = one_enemy([strike(), strike(), strike()])
    cs.player.apply_status(StatusId.NOSTALGIA, 2)
    sim = CombatSimulator(cs)
    for _ in range(3):
        sim.play_card(0, 0)
    assert len(cs.player.draw_pile) == 2 and len(cs.player.discard_pile) == 1

# ------------------------------------------------------------ Bolas and Thrumming Hatchet
@pytest.mark.parametrize("card_id,damage,upgraded_damage,cost", [(CardId.BOLAS, 3, 4, 0), (CardId.THRUMMING_HATCHET, 11, 14, 1)])
def test_returning_attacks_hit_and_come_back(card_id, damage, upgraded_damage, cost):
    for upgraded, expected in ((False, damage), (True, upgraded_damage)):
        cs = one_enemy([card(card_id, upgraded)], hp=100)
        cs.player.draw_pile = [defend() for _ in range(10)]
        play(cs)
        assert hps(cs) == [100 - expected] and len(cs.player.discard_pile) == 1
        end_turn(cs)
        assert sum(c.card_id == card_id for c in cs.player.hand) == 1 and len(cs.player.hand) == 6
        assert not cs.player.discard_pile or all(c.card_id != card_id for c in cs.player.discard_pile)

def test_returning_attack_comes_back_from_the_exhaust_pile():
    cs = one_enemy([card(CardId.BOLAS)])
    cs.player.draw_pile = [defend() for _ in range(10)]
    sim = play(cs)
    cs.player.exhaust_card(cs.player.discard_pile.pop())
    sim.end_turn()
    assert sum(c.card_id == CardId.BOLAS for c in cs.player.hand) == 1

def test_returning_attack_only_returns_once():
    cs = one_enemy([card(CardId.BOLAS)])
    cs.player.draw_pile = [defend() for _ in range(20)]
    sim = play(cs)
    sim.end_turn()
    sim.end_turn()                  # not played this time: it is discarded and stays there
    assert all(c.card_id != CardId.BOLAS for c in cs.player.hand)

def test_returning_attacks_follow_the_turn_counter_of_the_state():
    cs = one_enemy([card(CardId.BOLAS)])
    play(cs)
    new = one_enemy([])
    new.turn_number = cs.turn_number
    new.carry_turn_counters(cs)
    assert new.player.returning == [(CardId.BOLAS, False)]

# ------------------------------------------------------------ tables and loading
def test_utility_cards_are_in_the_tables():
    for card_id in (CardId.EQUILIBRIUM, CardId.SALVO, CardId.PANIC_BUTTON, CardId.PROLONG, CardId.FASTEN, CardId.PREP_TIME, CardId.DARK_SHACKLES,
                    CardId.AUTOMATION, CardId.PANACHE, CardId.ROLLING_BOULDER, CardId.THE_BOMB, CardId.THE_GAMBIT, CardId.MAYHEM, CardId.NOSTALGIA,
                    CardId.BOLAS, CardId.THRUMMING_HATCHET):
        assert card_id in COLORLESS_CARDS

def test_status_ids_load_from_the_bridge():
    for name in ("RETAIN_HAND", "NO_BLOCK", "BLOCK_NEXT_TURN", "FASTEN", "PREP_TIME", "DARK_SHACKLES", "AUTOMATION", "PANACHE",
                 "ROLLING_BOULDER", "THE_BOMB", "THE_GAMBIT", "MAYHEM", "NOSTALGIA"):
        assert StatusInstance.from_dict({"id": name + "_POWER", "amount": 2}).status_id == StatusId[name]

def test_instanced_powers_read_their_damage_from_the_text_and_merge_copies():
    from sts2_lite.player import Player
    base = {"id": "THE_BOMB_POWER", "amount": 2, "description": "In 2 turns, deal 50 damage to ALL enemies."}
    panache = {"id": "PANACHE_POWER", "amount": 3, "description": "Every time you play 5 cards in a single turn, deal 14 damage to ALL enemies."}
    raw = {"max_hp": 50, "hp": 50, "block": 0, "status": [base, {**base, "amount": 3, "description": "In 3 turns, deal 40 damage to ALL enemies."}, panache],
           "hand": [], "draw_pile": [], "discard_pile": []}
    player = Player.from_dict(raw)
    assert player.status[StatusId.THE_BOMB].records == [[2, 50], [3, 40]] and player.status[StatusId.THE_BOMB].amount == 5
    assert player.status[StatusId.PANACHE].records == [[3, 14, 1]]

# ------------------------------------------------------------ captures: Tests/data/cards/colorless

def test_capture_two_automations_load_as_two_copies():
    player = CombatState.from_dict(capture("automation_two_stacks")).player
    assert player.status[StatusId.AUTOMATION].records == [[5], [10]]

def test_capture_two_panaches_read_cards_left_and_damage():
    player = CombatState.from_dict(capture("panache_two_instances")).player
    assert player.status[StatusId.PANACHE].records == [[4, 10, 1], [5, 14, 1]]

def test_capture_two_bombs_read_turns_and_damage():
    cs = CombatState.from_dict(capture("the_bomb_two_instances"))
    assert cs.player.status[StatusId.THE_BOMB].records == [[3, 40], [2, 40]]
    sim = end_turn(cs)
    sim.end_turn()
    assert cs.player.status[StatusId.THE_BOMB].records == [[1, 40]]

def test_capture_retain_no_block_nostalgia_mayhem_all_load():
    status_ids = set(CombatState.from_dict(capture("retain_no_block_nostalgia_mayhem")).player.status)
    assert {StatusId.RETAIN_HAND, StatusId.NO_BLOCK, StatusId.NOSTALGIA, StatusId.MAYHEM} <= status_ids

def test_capture_prolong_block_comes_back_next_turn():
    cs = CombatState.from_dict(capture("prolong_before"))
    assert cs.player.status_amount(StatusId.BLOCK_NEXT_TURN) == 10
    end_turn(cs)
    assert cs.player.block == 10 and StatusId.BLOCK_NEXT_TURN not in cs.player.status
    after = CombatState.from_dict(capture("prolong_after"))
    assert after.player.block == 10 and StatusId.BLOCK_NEXT_TURN not in after.player.status

def test_capture_bolas_returns_to_the_hand_next_turn():
    cs = CombatState.from_dict(capture("bolas_before"))
    cs.player.returning = [(CardId.BOLAS, False)]       # the bridge does not say it was played this turn
    end_turn(cs)
    assert [c.card_id for c in cs.player.hand].count(CardId.BOLAS) == 1 and len(cs.player.hand) == 6
    assert CardId.BOLAS in [c.card_id for c in CombatState.from_dict(capture("bolas_after")).player.hand]

def test_capture_dark_shackles_strength_comes_back():
    cs = CombatState.from_dict(capture("dark_shackles"))
    enemy = cs.enemies[0]
    assert enemy.status_amount(StatusId.DARK_SHACKLES) == 9 and enemy.status_amount(StatusId.STRENGTH) == -9
    end_turn(cs)
    assert enemy.status_amount(StatusId.STRENGTH) == 0 and StatusId.DARK_SHACKLES not in enemy.status


def one_enemy(hand, hp=100):
    return make_state(hand, enemy_count=1, enemy_hp=hp)

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim

def ids(pile):
    return [c.card_id for c in pile]

# ------------------------------------------------------------ Jackpot
def test_jackpot_hits_and_adds_three_free_cards():
    for upgraded, damage in ((False, 25), (True, 30)):
        cs = one_enemy([card(CardId.JACKPOT).upgraded_copy() if upgraded else card(CardId.JACKPOT)], hp=100)
        cs.energy = 3
        play(cs)
        assert hps(cs) == [100 - damage] and len(cs.player.hand) == 3
        for c in cs.player.hand:
            assert c.card_id in ZERO_COST_POOL and c.energy_cost == 0 and c.is_upgraded == upgraded

def test_zero_cost_pool_has_only_cost_zero_ironclad_cards():
    assert ZERO_COST_POOL and all(GENERATABLE_CARDS[c][2] == 0 for c in ZERO_COST_POOL)
    assert CardId.ANGER in ZERO_COST_POOL and CardId.CASCADE not in ZERO_COST_POOL

def test_jackpot_overflow_goes_to_the_discard_pile():
    cs = one_enemy([card(CardId.JACKPOT)] + [defend() for _ in range(8)])
    cs.energy = 3
    play(cs)
    assert len(cs.player.hand) == 10 and len(cs.player.discard_pile) == 2

# ------------------------------------------------------------ Calamity
def test_calamity_adds_attacks_after_each_attack():
    cs = one_enemy([card(CardId.CALAMITY), strike(), defend()])
    cs.energy = 5
    sim = play(cs)
    assert cs.player.status_amount(StatusId.CALAMITY) == 1
    sim.play_card(1, 0)                 # Defend: nothing
    assert len(cs.player.hand) == 1
    sim.play_card(0, 0)                 # the Strike is replaced by a random Attack
    assert len(cs.player.hand) == 1 and ids(cs.player.hand)[-1] in [c for c, v in GENERATABLE_CARDS.items() if v[1] == CardType.Attack]

def test_calamity_stacks_and_the_power_card_itself_adds_nothing():
    cs = one_enemy([card(CardId.CALAMITY)])
    cs.player.apply_status(StatusId.CALAMITY, 1)
    play(cs)
    assert not cs.player.hand
    cs.player.hand = [strike()]
    cs.energy = 1
    CombatSimulator(cs).play_card(0, 0)
    assert len(cs.player.hand) == 2         # two stacks: two Attacks

def test_calamity_upgrade_cost():
    assert card(CardId.CALAMITY).upgraded_copy().energy_cost == 2

# ------------------------------------------------------------ Jack of All Trades
def test_jack_of_all_trades_adds_distinct_colorless_cards_and_exhausts():
    assert CardId.JACK_OF_ALL_TRADES not in JACK_POOL and CardId.HAND_OF_GREED not in JACK_POOL
    for _ in range(20):
        cs = one_enemy([card(CardId.JACK_OF_ALL_TRADES).upgraded_copy()])
        play(cs)
        assert len(cs.player.hand) == 2 and len(set(ids(cs.player.hand))) == 2
        assert all(c.card_id in COLORLESS_CARDS for c in cs.player.hand) and cs.player.exhaust_pile

def test_jack_of_all_trades_makes_one_card():
    cs = one_enemy([card(CardId.JACK_OF_ALL_TRADES)])
    play(cs)
    assert len(cs.player.hand) == 1

# ------------------------------------------------------------ Catastrophe
def test_catastrophe_plays_random_cards_from_the_draw_pile():
    cs = one_enemy([card(CardId.CATASTROPHE)], hp=100)
    cs.player.draw_pile = [strike() for _ in range(5)]
    cs.energy = 3
    play(cs)
    assert hps(cs) == [88] and len(cs.player.draw_pile) == 3 and len(cs.player.discard_pile) == 3     # two Strikes and Catastrophe
    assert cs.energy == 1               # the Strikes were free

def test_catastrophe_upgrade_plays_three():
    cs = one_enemy([card(CardId.CATASTROPHE).upgraded_copy()], hp=100)
    cs.player.draw_pile = [strike() for _ in range(5)]
    play(cs)
    assert hps(cs) == [82]

def test_catastrophe_prefers_playable_cards():
    for _ in range(20):
        cs = one_enemy([card(CardId.CATASTROPHE)], hp=100)
        cs.player.draw_pile = [Card.create_dazed(), strike(), Card.create_dazed()]
        play(cs)
        assert len(cs.player.draw_pile) == 2 or hps(cs) == [94]
        assert hps(cs)[0] <= 94

def test_catastrophe_with_only_unplayable_cards_discards_them():
    cs = one_enemy([card(CardId.CATASTROPHE)])
    cs.player.draw_pile = [Card.create_dazed(), Card.create_dazed()]
    play(cs)
    assert not cs.player.draw_pile and len(cs.player.discard_pile) == 3

def test_catastrophe_with_an_empty_draw_pile_does_nothing():
    cs = one_enemy([card(CardId.CATASTROPHE)])
    play(cs)
    assert len(cs.player.discard_pile) == 1

# ------------------------------------------------------------ Beat Down
def test_beat_down_plays_attacks_from_the_discard_pile():
    cs = make_state([card(CardId.BEAT_DOWN)], enemy_count=1, enemy_hp=100)
    cs.player.discard_pile = [strike(), strike(), strike(), strike(), defend()]
    cs.energy = 3
    play(cs)
    assert hps(cs) == [82] and cs.energy == 0
    assert len(cs.player.discard_pile) == 6          # the four Strikes (three replayed), the Defend and Beat Down

def test_beat_down_upgrade_plays_four_and_skips_skills():
    cs = make_state([card(CardId.BEAT_DOWN).upgraded_copy()], enemy_count=1, enemy_hp=100)
    cs.player.discard_pile = [strike() for _ in range(6)] + [defend()]
    play(cs)
    assert hps(cs) == [76]

def test_beat_down_with_fewer_attacks_than_its_count():
    cs = make_state([card(CardId.BEAT_DOWN)], enemy_count=1, enemy_hp=100)
    cs.player.discard_pile = [strike(), defend()]
    play(cs)
    assert hps(cs) == [94]

def test_beat_down_stops_when_the_fight_is_won():
    cs = make_state([card(CardId.BEAT_DOWN)], enemy_count=1, enemy_hp=6)
    cs.player.discard_pile = [strike(), strike(), strike()]
    sim = play(cs)
    assert sim.is_over

def test_beat_down_is_not_manually_targeted():
    assert card(CardId.BEAT_DOWN).target_type.name == "RandomEnemy"

# ------------------------------------------------------------ Anointed
def test_anointed_brings_rares_from_the_draw_pile():
    cs = one_enemy([card(CardId.ANOINTED), defend()])
    rare = lambda: Card.create_generated(CardId.SALVO)
    cs.player.draw_pile = [strike(), rare(), strike(), rare(), rare()]
    play(cs)
    assert ids(cs.player.hand).count(CardId.SALVO) == 3 and len(cs.player.draw_pile) == 2
    assert cs.player.exhaust_pile

def test_anointed_is_limited_by_the_free_space_in_the_hand():
    cs = one_enemy([card(CardId.ANOINTED)] + [defend() for _ in range(7)])
    cs.player.draw_pile = [Card.create_generated(CardId.SALVO) for _ in range(5)]
    play(cs)
    assert len(cs.player.hand) == 10 and len(cs.player.draw_pile) == 2

def test_anointed_upgrade_retains():
    assert not card(CardId.ANOINTED).retains and card(CardId.ANOINTED).upgraded_copy().retains

def test_rare_table_matches_the_game_for_a_few_cards():
    assert {CardId.BARRICADE, CardId.SALVO, CardId.MAYHEM, CardId.THE_GAMBIT} <= RARE_CARDS
    assert not {CardId.STRIKE_IRONCLAD, CardId.BASH, CardId.ANGER, CardId.EQUILIBRIUM, CardId.AUTOMATION} & RARE_CARDS

# ------------------------------------------------------------ the verifier treats these as chance events
def test_verify_tags_random_card_plays_and_calamity_attacks():
    from sts2_lite.verify import is_random_step
    from sts2_lite.combat import CombatState
    cs = one_enemy([card(CardId.JACKPOT), strike()])
    assert is_random_step(cs, cs, [{"action": "play_card", "card_index": 0, "target": 0}])
    assert not is_random_step(cs, cs, [{"action": "play_card", "card_index": 1, "target": 0}])
    cs.player.apply_status(StatusId.CALAMITY, 1)
    assert is_random_step(cs, cs, [{"action": "play_card", "card_index": 1, "target": 0}])

def test_havoc_with_an_unseen_top_card_cannot_be_predicted_but_a_known_top_card_can():
    from sts2_lite.verify import is_unpredictable_step
    from sts2_lite.card import CardType, TargetType
    from sts2_lite.Tests.enemies.test_hive_simple import make_card
    havoc = make_card(CardId.HAVOC, "Havoc", CardType.Skill, 1, TargetType.Self)
    cs = one_enemy([havoc, strike()])
    play = lambda i: [{"action": "play_card", "card_index": i, "target": 0}]
    assert is_unpredictable_step(cs, play(0))
    assert not is_unpredictable_step(cs, play(1))
    cs.player.known_top = 1
    assert not is_unpredictable_step(cs, play(0))


def one_enemy(hand, hp=100):
    return make_state(hand, enemy_count=1, enemy_hp=hp)

def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim

# ------------------------------------------------------------ Discovery
def test_discovery_offers_three_different_ironclad_cards_and_can_be_skipped():
    cs = one_enemy([card(CardId.DISCOVERY)])
    sim = play(cs)
    pending = cs.pending_choice
    assert pending.kind == "discover" and pending.optional and pending.hidden and pending.pile == "offer"
    assert len(pending.offers) == 3 and len({c.card_id for c in pending.offers}) == 3
    assert all(c.card_id in GENERATABLE_CARDS for c in pending.offers)
    actions = sim.get_available_actions()
    assert [a["action"] for a in actions] == ["choose_card"] * 3 + ["confirm_choice"]
    sim.confirm_choice()
    assert cs.pending_choice is None and not cs.player.hand and cs.player.exhaust_pile

def test_discovery_pick_is_free_this_turn():
    cs = one_enemy([card(CardId.DISCOVERY)])
    sim = play(cs)
    offered = cs.pending_choice.offers[1]
    sim.choose_card(1)
    assert [c.card_id for c in cs.player.hand] == [offered.card_id]
    assert cs.player.hand[0].energy_cost == 0 and cs.player.hand[0].restore_cost == offered.energy_cost
    assert cs.pending_choice is None

def test_upgraded_discovery_does_not_exhaust():
    cs = one_enemy([card(CardId.DISCOVERY).upgraded_copy()])
    sim = play(cs)
    sim.confirm_choice()
    assert not cs.player.exhaust_pile and len(cs.player.discard_pile) == 1

def test_discovery_is_a_pick_before_anything_else():
    cs = one_enemy([card(CardId.DISCOVERY), strike()])
    sim = play(cs)
    with pytest.raises(Exception):
        sim.play_card(0, 0)

def test_capture_discovery_screen_replaces_the_sims_offer():
    cs = one_enemy([card(CardId.DISCOVERY)])
    sim = play(cs)
    cs.adopt_offer(capture("discovery_select")["cards"])
    assert [c.card_id for c in cs.pending_choice.offers] == [CardId.HEADBUTT, CardId.STONE_ARMOR, CardId.WHIRLWIND]
    assert not cs.pending_choice.hidden
    sim.choose_card(2)
    assert cs.player.hand[0].card_id == CardId.WHIRLWIND and cs.player.hand[0].energy_cost == "X"

# ------------------------------------------------------------ Entropy
def test_entropy_transforms_a_chosen_card_at_the_start_of_the_turn():
    cs = one_enemy([card(CardId.ENTROPY)])
    play(cs)
    cs.player.draw_pile = [defend() for _ in range(2)] + [strike(), Card.create_generated(CardId.ANGER), Card.create_generated(CardId.FINESSE), defend(), defend()]
    sim = CombatSimulator(cs)
    sim.end_turn()
    pending = cs.pending_choice
    assert pending.kind == "transform" and pending.amount == 1 and len(cs.player.hand) == 5
    before = [c.card_id for c in cs.player.hand]
    pick = pending.indices[0]
    sim.choose_card(pick)
    after = [c.card_id for c in cs.player.hand]
    assert len(after) == 5 and after[pick] != before[pick]
    assert [a for i, a in enumerate(after) if i != pick] == [b for i, b in enumerate(before) if i != pick]

def test_transform_options_follow_the_cards_pool():
    ironclad = transform_options(strike())
    assert ironclad and set(ironclad) <= set(GENERATABLE_CARDS) and CardId.STRIKE_IRONCLAD not in ironclad
    colorless = transform_options(card(CardId.FINESSE))
    assert colorless and set(colorless) <= set(COLORLESS_CARDS) and CardId.FINESSE not in colorless
    assert CardId.HAND_OF_GREED not in colorless
    assert transform_options(Card.create_dazed()) == []

def test_entropy_skips_statuses_and_picks_what_is_left():
    cs = one_enemy([Card.create_dazed(), strike()])
    cs.player.apply_status(StatusId.ENTROPY, 1)
    CombatSimulator(cs).request_transform(1)
    assert cs.player.hand[0].card_id == CardId.DAZED and cs.player.hand[1].card_id != CardId.STRIKE_IRONCLAD
    assert cs.pending_choice is None

def test_entropy_with_two_stacks_picks_two_different_cards():
    cs = one_enemy([strike(), defend(), Card.create_generated(CardId.ANGER)])
    cs.player.apply_status(StatusId.ENTROPY, 2)
    sim = CombatSimulator(cs)
    sim.request_transform(2)
    assert cs.pending_choice.amount == 2
    sim.choose_card(cs.pending_choice.indices[0])
    assert cs.pending_choice.amount == 1 and len(cs.pending_choice.picked) == 1 and cs.pending_choice.picked[0] not in cs.pending_choice.indices
    sim.choose_card(cs.pending_choice.indices[0])
    assert cs.pending_choice is None and len(cs.player.hand) == 3

def test_entropy_upgrade_is_innate():
    assert not card(CardId.ENTROPY).upgraded_copy().card_id == CardId.STRIKE_IRONCLAD
    assert card(CardId.ENTROPY).upgraded_copy()._mask & 4 and not card(CardId.ENTROPY)._mask & 4

def test_capture_entropy_screen_becomes_a_transform_choice():
    cs = CombatState.from_dict(capture("entropy_select"))
    assert cs.pending_choice.kind == "transform" and cs.pending_choice.amount == 1
    # Strike appears three times and counts once
    assert len(cs.pending_choice.indices) == 3
    sim = CombatSimulator(cs)
    sim.choose_card(cs.pending_choice.indices[0])
    assert cs.pending_choice is None and len(cs.player.hand) == 5

# ------------------------------------------------------------ Hidden Gem
def test_hidden_gem_gives_a_draw_pile_card_replay_two():
    cs = one_enemy([card(CardId.HIDDEN_GEM)])
    cs.player.draw_pile = [strike(), defend(), strike()]
    play(cs)
    gained = [c for c in cs.player.draw_pile if c.replay]
    assert len(gained) == 1 and gained[0].replay == 2 and len(cs.player.draw_pile) == 3

def test_hidden_gem_upgrade_gives_three_and_skips_cards_with_replay():
    cs = one_enemy([card(CardId.HIDDEN_GEM).upgraded_copy()])
    marked = strike().with_replay(2)
    cs.player.draw_pile = [marked, defend()]
    play(cs)
    assert cs.player.draw_pile[0].replay == 2 and cs.player.draw_pile[1].replay == 3

def test_hidden_gem_ignores_unplayable_cards_and_curses():
    cs = one_enemy([card(CardId.HIDDEN_GEM)])
    cs.player.draw_pile = [Card.create_dazed(), Card.create_curse(CardId.REGRET)]
    play(cs)
    assert all(c.replay == 0 for c in cs.player.draw_pile)

def test_hidden_gem_with_an_empty_draw_pile_does_nothing():
    cs = one_enemy([card(CardId.HIDDEN_GEM)])
    play(cs)
    assert len(cs.player.discard_pile) == 1

def test_replay_plays_a_card_extra_times():
    cs = one_enemy([strike().with_replay(2)], hp=100)
    play(cs)
    assert hps(cs) == [82]

def test_replay_survives_copying_and_upgrading():
    c = strike().with_replay(2)
    assert Card.create_copy(c).replay == 2 and c.upgraded_copy().replay == 2

def test_capture_hidden_gem_replay_is_read_from_the_card_text():
    cs = CombatState.from_dict(capture("hidden_gem"))
    assert [c.replay for c in cs.player.draw_pile] == [0, 0, 0, 2, 0]
    assert all(c.replay == 0 for c in cs.player.hand + cs.player.discard_pile)       # Hidden Gem's own tooltip is not a Replay
    cs.player.hand = [cs.player.draw_pile[3]]
    cs.enemies[0].current_hp = 100
    play(cs)
    assert hps(cs)[0] == 100 - 3 * 6
