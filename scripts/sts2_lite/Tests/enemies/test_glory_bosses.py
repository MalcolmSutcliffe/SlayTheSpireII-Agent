"""Act 3 (Glory) bosses: the Queen and her Torch Head Amalgam, the Test Subject, Aeonglass.
Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite import enemy as enemy_module
from sts2_lite import rng
from sts2_lite.card import Card, CardId
from sts2_lite.combat import CombatSimulator
from sts2_lite.enemy_moves import MOVE_TABLES
from sts2_lite.status import StatusId, StatusInstance
from sts2_lite.Tests.enemies.test_bridge_moves import attack, raw_enemy
from sts2_lite.Tests.enemies.test_glory_simple import at, moves_over, status, turn
from sts2_lite.Tests.enemies.test_hive_simple import defend, strike


@pytest.fixture(autouse=True)
def strict(monkeypatch):
    monkeypatch.setattr(enemy_module, "STRICT_BRIDGE_CHECKS", True)


def other(monster, move, hp=200, max_hp=None, intents=(), status=()):
    raw = raw_enemy(monster, move + "_MOVE", [move + "_MOVE"], list(intents), status=list(status))
    raw["hp"], raw["max_hp"] = hp, max_hp or hp
    return raw

def queen_fight(queen_move, amalgam_move="TACKLE", ascension=0, amalgam_hp=199):
    """[Torch Head Amalgam, Queen]: the order of the encounter's slots."""
    queen = other("QUEEN", queen_move, hp=400)
    cs = at("TORCH_HEAD_AMALGAM", amalgam_move, ascension=ascension, hp=amalgam_hp, max_hp=199, status=[status("MINION")], extra=[queen])
    cs.enemies[1].moves = MOVE_TABLES["QUEEN"](ascension)
    return cs


@pytest.mark.parametrize("monster, move, base, deadly, hits", [
    ("QUEEN", "OFF_WITH_YOUR_HEAD", 3, 4, 5), ("QUEEN", "EXECUTION", 15, 18, 1),
    ("TORCH_HEAD_AMALGAM", "TACKLE", 18, 19, 1), ("TORCH_HEAD_AMALGAM", "TACKLE_3", 14, 15, 1), ("TORCH_HEAD_AMALGAM", "BEAM", 8, 8, 3),
    ("TEST_SUBJECT", "BITE", 20, 22, 1), ("TEST_SUBJECT", "SKULL_BASH", 14, 16, 1), ("TEST_SUBJECT", "MULTI_CLAW", 10, 11, 3),
    ("TEST_SUBJECT", "PHASE3_LACERATE", 10, 11, 3), ("TEST_SUBJECT", "BIG_POUNCE", 45, 45, 1),
    ("AEONGLASS", "EBB", 26, 32, 1), ("AEONGLASS", "EYE_LASERS", 11, 12, 2),
])
def test_damage_rises_on_deadly_ascension(monster, move, base, deadly, hits):
    for ascension, damage in ((0, base), (9, deadly)):
        m = MOVE_TABLES[monster](ascension)[move]
        assert (m.damage, m.hits) == (damage, hits)


# ---------------------------------------------------------------- the Queen
def test_the_queen_chains_the_player_then_curses_them_for_good():
    cs = queen_fight("PUPPET_STRINGS")
    queen = cs.enemies[1]
    turn(cs)
    assert cs.player.status_amount(StatusId.CHAINS_OF_BINDING) == 3 and queen.move_id == "YOU_ARE_MINE"
    turn(cs)
    assert [cs.player.status_amount(s) for s in (StatusId.FRAIL, StatusId.WEAK, StatusId.VULNERABLE)] == [99, 99, 99]
    assert queen.move_id == "BURN_BRIGHT_FOR_ME"

def test_burn_bright_for_me_strengthens_the_amalgam_and_blocks_while_it_lives():
    cs = queen_fight("BURN_BRIGHT_FOR_ME")
    queen = cs.enemies[1]
    for strength in (1, 2, 3):
        turn(cs)
        assert (queen.block, cs.enemies[0].status_amount(StatusId.STRENGTH), queen.move_id) == (20, strength, "BURN_BRIGHT_FOR_ME")
    assert queen.status_amount(StatusId.STRENGTH) == 0

def test_the_amalgam_dying_turns_a_coming_burn_bright_into_enrage():
    cs = queen_fight("BURN_BRIGHT_FOR_ME", amalgam_hp=1)
    sim = CombatSimulator(cs)
    cs.player.hand = [strike()]
    sim.play_card(0, 0)
    assert [e.enemy_id for e in cs.enemies] == ["QUEEN_0"] and cs.enemies[0].move_id == "ENRAGE"
    turn(cs)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 2 and cs.enemies[0].move_id == "OFF_WITH_YOUR_HEAD"

def test_without_the_amalgam_the_queen_goes_on_a_loop_of_head_execution_and_rage():
    cs = queen_fight("BURN_BRIGHT_FOR_ME", amalgam_hp=1)
    cs.player.hand = [strike()]
    CombatSimulator(cs).play_card(0, 0)
    queen = cs.enemies[0]
    assert moves_over(cs, 6) == ["ENRAGE", "OFF_WITH_YOUR_HEAD", "EXECUTION", "ENRAGE", "OFF_WITH_YOUR_HEAD", "EXECUTION", "ENRAGE"]

def test_you_are_mine_leads_straight_to_the_head_when_the_amalgam_is_already_gone():
    cs = at("QUEEN", "YOU_ARE_MINE")
    cs.enemies[0].counter = 1
    turn(cs)
    assert cs.enemies[0].move_id == "OFF_WITH_YOUR_HEAD"

def test_the_queen_read_without_her_amalgam_remembers_it_is_dead():
    cs = at("QUEEN", "YOU_ARE_MINE")
    assert cs.enemies[0].counter == 1

def test_the_amalgam_s_moves():
    cs = at("TORCH_HEAD_AMALGAM", "TACKLE")
    assert moves_over(cs, 7) == ["TACKLE", "TACKLE_2", "BEAM", "TACKLE_3", "TACKLE_4", "BEAM", "TACKLE_3", "TACKLE_4"]

def test_the_queen_s_death_ends_the_fight_even_with_the_amalgam_alive():
    cs = queen_fight("EXECUTION")
    cs.enemies[1].current_hp = 1
    cs.player.hand = [strike()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 1)
    assert sim.is_over


# ---------------------------------------------------------------- Chains of Binding
def bound_hand(cs, cards):
    cs.player.status[StatusId.CHAINS_OF_BINDING] = StatusInstance(StatusId.CHAINS_OF_BINDING, 3)
    cs.player.hand = []
    cs.player.draw_pile = list(cards)
    cs.player.binding = True
    cs.player.draw_cards(len(cards))

def test_the_first_three_cards_drawn_are_bound_and_only_one_of_them_can_be_played():
    cs = at("QUEEN", "OFF_WITH_YOUR_HEAD")
    bound_hand(cs, [strike(), strike(), strike(), strike(), defend()])
    sim = CombatSimulator(cs)
    assert [c.bound for c in cs.player.hand] == [True, True, True, False, False]
    assert all(c.can_play_card(sim, 0) for c in cs.player.hand)
    sim.play_card(0, 0)
    assert [c.can_play_card(sim, 0) for c in cs.player.hand] == [False, False, True, True]

def test_bound_cards_are_free_again_when_the_turn_ends_and_bound_afresh_when_drawn():
    cs = at("QUEEN", "OFF_WITH_YOUR_HEAD")
    bound_hand(cs, [strike(), strike(), strike(), defend(), defend(), defend()])
    cs.player.hand[0].bound_played = True
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    cs.player.draw_pile = [defend(), defend(), defend(), defend()]
    sim.end_turn()
    assert not any(c.bound for c in cs.player.discard_pile)         # the three that were bound last turn are plain in the discard pile
    assert [c.bound for c in cs.player.hand] == [True, True, True, False, False] and not cs.player.bound_played


# ---------------------------------------------------------------- the Test Subject
def subject(move="BITE", status_list=None, hp=100, max_hp=100, ascension=0):
    status_list = status_list if status_list is not None else [status("ADAPTABLE"), status("ENRAGE", 2)]
    cs = at("TEST_SUBJECT", move, status=status_list, hp=hp, max_hp=max_hp, ascension=ascension)
    cs.enemies[0].moves = MOVE_TABLES["TEST_SUBJECT"](ascension)
    cs.player.current_hp = cs.player.max_hp = 400
    return cs

def kill(cs, damage_card=None):
    cs.player.hand = [damage_card or strike()]
    cs.player.energy = 3
    cs.enemies[0].current_hp = 1
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    return sim

def test_the_first_form_bites_and_bashes_in_turn_and_every_skill_enrages_it():
    cs = subject()
    assert moves_over(cs, 3) == ["BITE", "SKULL_BASH", "BITE", "SKULL_BASH"]
    cs = subject()
    cs.player.hand = [defend(), defend()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.play_card(0, 0)
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 4

def test_skull_bash_leaves_vulnerable():
    cs = subject("SKULL_BASH")
    turn(cs)
    assert cs.player.current_hp == 400 - 14 and cs.player.status_amount(StatusId.VULNERABLE) == 1

def test_killing_the_first_form_does_not_end_the_fight():
    cs = subject()
    sim = kill(cs)
    assert not sim.is_over and cs.enemies == [] and len(cs.dormant) == 1
    assert StatusId.ADAPTABLE in cs.dormant[0].status and StatusId.ENRAGE not in cs.dormant[0].status

def test_it_respawns_on_the_enemy_turn_after_with_more_hit_points_painful_stabs_and_claws():
    cs = subject()
    kill(cs)
    sim = CombatSimulator(cs)
    sim.end_turn()
    e = cs.enemies[0]
    assert (e.current_hp, e.max_hp, e.move_id) == (200, 200, "MULTI_CLAW") and e.num_attacks == 3
    assert e.status_amount(StatusId.PAINFUL_STABS) == 1 and StatusId.ADAPTABLE in e.status
    assert cs.dormant == [] and not sim.is_over

def test_ascended_forms_have_more_hit_points():
    cs = subject(ascension=8)
    kill(cs)
    CombatSimulator(cs).end_turn()
    assert cs.enemies[0].max_hp == 212

def test_the_claws_gain_a_hit_every_time_and_each_connecting_hit_adds_a_wound():
    cs = subject("MULTI_CLAW", status_list=[status("ADAPTABLE"), status("PAINFUL_STABS")], hp=200, max_hp=200)
    e = cs.enemies[0]
    for hits in (3, 4, 5):
        assert e.num_attacks == hits
        wounds = sum(c.card_id == CardId.WOUND for c in cs.player.discard_pile)
        hp = cs.player.current_hp
        turn(cs)
        assert cs.player.current_hp == hp - 10 * hits
        assert sum(c.card_id == CardId.WOUND for c in cs.player.discard_pile) == wounds + hits

def test_blocked_hits_do_not_add_wounds():
    cs = subject("MULTI_CLAW", status_list=[status("ADAPTABLE"), status("PAINFUL_STABS")], hp=200, max_hp=200)
    cs.player.block = 30
    turn(cs)
    assert cs.player.current_hp == 400 and not any(c.card_id == CardId.WOUND for c in cs.player.discard_pile)

def test_the_second_death_brings_the_final_form_with_nemesis():
    cs = subject("MULTI_CLAW", status_list=[status("ADAPTABLE"), status("PAINFUL_STABS")], hp=200, max_hp=200)
    kill(cs)
    CombatSimulator(cs).end_turn()
    e = cs.enemies[0]
    assert (e.current_hp, e.max_hp, e.move_id) == (300, 300, "PHASE3_LACERATE")
    assert StatusId.NEMESIS in e.status and StatusId.ADAPTABLE not in e.status and StatusId.PAINFUL_STABS not in e.status

def test_the_final_form_is_intangible_every_other_turn_and_loops_lacerate_pounce_growl():
    cs = subject("PHASE3_LACERATE", status_list=[status("NEMESIS")], hp=300, max_hp=300)
    e = cs.enemies[0]
    seen, intangible = [e.move_id], []
    for _ in range(6):
        turn_sim = CombatSimulator(cs)
        turn_sim.end_turn()
        seen.append(e.move_id)
        intangible.append(StatusId.INTANGIBLE in e.status)
    assert seen == ["PHASE3_LACERATE", "BIG_POUNCE", "BURNING_GROWL", "PHASE3_LACERATE", "BIG_POUNCE", "BURNING_GROWL", "PHASE3_LACERATE"]
    assert intangible == [True, False, True, False, True, False]

def test_intangible_caps_every_hit_at_one():
    cs = subject("PHASE3_LACERATE", status_list=[status("NEMESIS"), status("INTANGIBLE")], hp=300, max_hp=300)
    cs.player.hand = [strike()]
    CombatSimulator(cs).play_card(0, 0)
    assert cs.enemies[0].current_hp == 299

def test_burning_growl_adds_burns_and_strength():
    cs = subject("BURNING_GROWL", status_list=[status("NEMESIS")], hp=300, max_hp=300)
    turn(cs)
    assert sum(c.card_id == CardId.BURN for c in cs.player.discard_pile) == 3 and cs.enemies[0].status_amount(StatusId.STRENGTH) == 2
    cs = subject("BURNING_GROWL", status_list=[status("NEMESIS")], hp=300, max_hp=300, ascension=9)
    turn(cs)
    assert sum(c.card_id == CardId.BURN for c in cs.player.discard_pile) == 5 and cs.enemies[0].status_amount(StatusId.STRENGTH) == 3

def test_killing_the_final_form_wins():
    cs = subject("PHASE3_LACERATE", status_list=[status("NEMESIS")], hp=300, max_hp=300)
    assert kill(cs).is_over


# ---------------------------------------------------------------- Aeonglass
def aeonglass(move="EBB", ascension=0, cards_left=6, counter=0):
    cs = at("AEONGLASS", move, status=[status("ARTIFACT", 3)], hp=512, max_hp=512, ascension=ascension)
    cs.enemies[0].moves = MOVE_TABLES["AEONGLASS"](ascension)
    cs.enemies[0].status[StatusId.WITHERING_PRESENCE] = StatusInstance(StatusId.WITHERING_PRESENCE, cards_left)      # on Aeonglass, counting the player's cards
    cs.enemies[0].counter = counter
    return cs

def test_ebb_then_lasers_then_intensity():
    assert moves_over(aeonglass(), 3) == ["EBB", "EYE_LASERS", "INCREASING_INTENSITY", "EBB"]

def test_ebb_gains_33_block():
    cs = aeonglass()
    turn(cs)
    assert cs.enemies[0].block == 33 and cs.player.current_hp == 80 - 26

def test_the_sixth_card_played_puts_a_wither_in_hand_and_the_count_restarts():
    cs = aeonglass(cards_left=2)
    cs.player.hand = [defend(), defend(), defend()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.enemies[0].status_amount(StatusId.WITHERING_PRESENCE) == 1
    sim.play_card(0, 0)
    assert [c.card_id for c in cs.player.hand] == [CardId.DEFEND_IRONCLAD, CardId.WITHER]
    assert cs.enemies[0].status_amount(StatusId.WITHERING_PRESENCE) == 6

def test_a_wither_costs_three_hit_points_at_the_end_of_the_turn_before_block():
    cs = aeonglass()
    cs.player.hand = [Card.create_wither()]
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 80 - 3 - 26         # the Wither at the end of the turn, then Ebb

def test_increasing_intensity_upgrades_every_wither_adds_one_and_strengthens():
    cs = aeonglass("INCREASING_INTENSITY")
    cs.player.hand, cs.player.discard_pile = [Card.create_wither()], [Card.create_wither(1)]
    turn(cs)
    levels = sorted(c.wither_level for c in cs.player.hand + cs.player.discard_pile)
    assert levels == [1, 1, 2]          # the two that were there, one step up; the new one made at the new level
    assert cs.enemies[0].status_amount(StatusId.STRENGTH) == 3 and cs.enemies[0].counter == 1

def test_the_strength_it_gains_grows_each_time_and_two_withers_come_on_deadly_ascension():
    cs = aeonglass("INCREASING_INTENSITY", ascension=9)
    gains = []
    for _ in range(3):
        before = cs.enemies[0].status_amount(StatusId.STRENGTH)
        e = cs.enemies[0]
        e.move_id = "INCREASING_INTENSITY"
        turn(cs)
        gains.append(cs.enemies[0].status_amount(StatusId.STRENGTH) - before)
    assert gains == [4, 5, 6]
    assert len([c for c in cs.player.discard_pile if c.card_id == CardId.WITHER]) == 6

def test_new_withers_are_made_at_the_current_level():
    cs = aeonglass(counter=2, cards_left=1)
    cs.player.hand = [defend()]
    CombatSimulator(cs).play_card(0, 0)
    assert [c.wither_level for c in cs.player.hand if c.card_id == CardId.WITHER] == [2]
    assert Card.create_wither(2).wither_level == 2


def test_with_the_subject_dead_the_player_can_only_end_the_turn_and_a_copy_keeps_the_respawn():
    from sts2_lite.combat import CombatState
    from agents.sts2_MCTS.state_key import state_key
    cs = subject()
    sim = kill(cs)
    assert [a["action"] for a in sim.get_available_actions()] == ["end_turn"]
    copy = CombatState.deepcopy(cs)
    assert state_key(copy) == state_key(cs)
    CombatSimulator(copy).end_turn()
    assert copy.enemies[0].max_hp == 200 and len(cs.dormant) == 1


# ---------------------------------------------------------------- captured from the game (data/enemies/act3_glory)
from agents import verify
from sts2_lite.Tests import captures


def glory(enemy, name):
    return captures.load(enemy, name, captures.GLORY)

def enemy_diffs(cs, want):
    return [d for d in verify.compare(cs, want) if (d.startswith("enemy") or "dormant" in d) and "hp" not in d]

def test_every_boss_capture_loads_with_moves_and_damage_agreeing():
    for enemy, name in (("queen", "turn_1"), ("queen", "turn_2"), ("queen", "turn_2_bound_played"), ("queen", "minion_killed"),
                        ("test_subject", "phase_1"), ("test_subject", "phase_2"), ("test_subject", "phase_3"), ("test_subject", "between_phases"),
                        ("aeonglass", "capture_1"), ("aeonglass", "capture_2")):
        glory(enemy, name)

def test_queen_turn_one_to_two_chains_the_player_and_moves_the_amalgam_on():
    cs = glory("queen", "turn_1")
    turn(cs)
    want = glory("queen", "turn_2")
    assert enemy_diffs(cs, want) == []
    assert cs.player.status_amount(StatusId.CHAINS_OF_BINDING) == 3

def test_the_first_three_cards_of_the_captured_hand_are_bound():
    cs = glory("queen", "turn_2")
    assert [c.bound for c in cs.player.hand] == [True, True, True, False, False]
    assert cs.player.bound_cards == 3 and not cs.player.bound_played

def test_after_a_bound_card_is_played_the_other_bound_cards_cannot_be():
    cs = glory("queen", "turn_2_bound_played")
    sim = CombatSimulator(cs)
    assert cs.player.bound_played
    assert [c.can_play_card(sim, 0) for c in cs.player.hand] == [False, False, True, True]

def test_playing_a_bound_card_in_the_simulator_gives_the_state_the_game_shows():
    cs = glory("queen", "turn_2")
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert [c.can_play_card(sim, 0) for c in cs.player.hand] == [False, False, True, True]

def test_the_queen_without_her_amalgam_attacks_with_strength_two():
    cs = glory("queen", "minion_killed")
    assert cs.enemies[0].counter == 1 and cs.enemies[0].move_id == "OFF_WITH_YOUR_HEAD"
    assert moves_over(cs, 3) == ["OFF_WITH_YOUR_HEAD", "EXECUTION", "ENRAGE", "OFF_WITH_YOUR_HEAD"]

def test_the_unlisted_dead_subject_is_waiting_to_respawn_and_returns_as_the_second_form():
    cs = glory("test_subject", "between_phases")
    assert cs.enemies == [] and len(cs.dormant) == 1
    sim = CombatSimulator(cs)
    actions = sim.get_available_actions()
    assert not sim.is_over and actions[-1]["action"] == "end_turn"
    assert all(cs.player.hand[a["card_index"]].card_id == CardId.DEFEND_IRONCLAD for a in actions[:-1])        # nothing to attack
    sim.end_turn()
    assert enemy_diffs(cs, glory("test_subject", "phase_2")) == []

def test_killing_the_second_form_gives_the_third_with_intangible_as_captured():
    cs = glory("test_subject", "phase_2")
    cs.enemies[0].current_hp = 1
    cs.player.hand = [strike()]
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    sim.end_turn()
    assert enemy_diffs(cs, glory("test_subject", "phase_3")) == []

def test_aeonglass_after_one_intensity_has_strength_three_and_the_game_s_moves():
    cs = glory("aeonglass", "capture_1")
    assert cs.enemies[0].counter == 0
    sim = CombatSimulator(cs)
    sim.end_turn()
    sim.end_turn()
    want = glory("aeonglass", "capture_2")
    diffs = [d for d in enemy_diffs(cs, want) if "WITHERING_PRESENCE" not in d]       # cards played in between
    assert diffs == []
    assert want.enemies[0].counter == 1

def test_the_captured_upgraded_wither_reads_its_level_from_its_text():
    cs = glory("aeonglass", "capture_2")
    from sts2_lite.card import Card
    raw = captures.raw("aeonglass", "capture_2", captures.GLORY)
    withers = [Card.from_dict(c) for c in raw["player"]["draw_pile"] + raw["player"]["discard_pile"] if c["id"] == "WITHER"]
    assert [w.wither_level for w in withers] == [1, 1]


def test_aeonglass_tier_three_capture_loads_with_its_counter_and_leveled_withers():
    cs = glory("aeonglass", "tier_3_wither")
    e = cs.enemies[0]
    assert (e.counter, e.status_amount(StatusId.STRENGTH), e.move_id) == (2, 7, "EBB")
    withers = [c for c in cs.player.draw_pile if c.card_id is CardId.WITHER]
    assert len(withers) == 4 and {w.wither_level for w in withers} == {2}

def test_aeonglass_tier_three_withers_hurt_for_nine_and_the_next_one_is_made_at_level_two():
    cs = glory("aeonglass", "tier_3_wither")
    sim = CombatSimulator(cs)
    assert sim.wither_level() == 2
    cs.player.hand = [Card.create_wither(2)]
    hp = cs.player.current_hp
    sim.end_turn()
    assert cs.player.current_hp <= hp - 9
    assert Card.create_wither(sim.wither_level()).wither_level == 2
