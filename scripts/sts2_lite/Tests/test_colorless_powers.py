"""Colorless cards, group 3: powers, retained hands, temporary Strength and the cards that come back. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.card import Card, CardId, CardType, COLORLESS_CARDS
from sts2_lite.combat import CombatSimulator
from sts2_lite.status import StatusId, StatusInstance
from test_cards import make_card, make_state, hps
from test_colorless import card, strike, defend

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
def test_group3_cards_are_in_the_tables():
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
from sts2_lite.combat import CombatState
from test_colorless import capture

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
