"""The ten cards Trash Heap hands out (event rarity; Clash, Dual Wield and Entrench are Ironclad's, the rest Silent's and Defect's)."""
import pytest

from sts2_lite.card import Card, CardId, CardType, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.hooks import HookType
from sts2_lite.status import StatusId
from sts2_lite.Tests.card.test_card import make_card, make_state


def card(card_id, upgraded=False):
    return Card.create_generated(card_id, upgraded)


def strike():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)


def defend():
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.Self)


def play(cs, index=0, target=0):
    sim = CombatSimulator(cs)
    sim.play_card(index, target)
    return sim


@pytest.mark.parametrize("upgraded,damage", [(False, 14), (True, 18)])
def test_clash_deals_14_or_18(upgraded, damage):
    cs = make_state([card(CardId.CLASH, upgraded), strike()], enemy_count=1, enemy_hp=40)
    play(cs)
    assert cs.enemies[0].current_hp == 40 - damage and cs.energy == 3


def test_clash_needs_a_hand_of_only_attacks():
    cs = make_state([card(CardId.CLASH), strike(), defend()], enemy_count=1)
    assert not cs.player.hand[0].can_play_card(CombatSimulator(cs), 0)
    cs = make_state([card(CardId.CLASH), strike()], enemy_count=1)
    assert cs.player.hand[0].can_play_card(CombatSimulator(cs), 0)


@pytest.mark.parametrize("upgraded,copies", [(False, 1), (True, 2)])
def test_dual_wield_copies_an_attack_or_power(upgraded, copies):
    cs = make_state([card(CardId.DUAL_WIELD, upgraded), strike(), defend()], enemy_count=1)
    play(cs)
    ids = [c.card_id for c in cs.player.hand]
    assert ids.count(CardId.STRIKE_IRONCLAD) == 1 + copies and ids.count(CardId.DEFEND_IRONCLAD) == 1 and cs.energy == 2


def test_dual_wield_asks_when_there_is_a_choice_and_a_skill_cannot_be_copied():
    cs = make_state([card(CardId.DUAL_WIELD), strike(), make_card(CardId.BASH, "Bash", CardType.Attack, 2, TargetType.AnyEnemy), defend()], enemy_count=1)
    sim = play(cs)
    assert cs.pending_choice is not None and set(cs.pending_choice.indices) == {0, 1}
    sim.choose_card(1)
    assert [c.card_id for c in cs.player.hand].count(CardId.BASH) == 2


def test_entrench_doubles_block_without_dexterity_or_frail_and_costs_one_upgraded():
    cs = make_state([card(CardId.ENTRENCH)], enemy_count=1)
    cs.player.block = 7
    cs.player.apply_status(StatusId.DEXTERITY, 3)
    play(cs)
    assert cs.player.block == 14 and cs.energy == 1
    assert card(CardId.ENTRENCH, True).energy_cost == 1


@pytest.mark.parametrize("upgraded,thorns", [(False, 3), (True, 5)])
def test_caltrops_gives_thorns(upgraded, thorns):
    cs = make_state([card(CardId.CALTROPS, upgraded)], enemy_count=1)
    play(cs)
    assert cs.player.status_amount(StatusId.THORNS) == thorns


def test_distraction_adds_a_free_skill_exhausts_and_costs_nothing_upgraded():
    cs = make_state([card(CardId.DISTRACTION)], enemy_count=1)
    play(cs)
    assert len(cs.player.hand) == 1 and cs.player.hand[0].type == CardType.Skill and cs.player.hand[0].current_cost(cs.player) == 0
    assert [c.card_id for c in cs.player.exhaust_pile] == [CardId.DISTRACTION] and not cs.player.discard_pile
    assert card(CardId.DISTRACTION, True).energy_cost == 0


@pytest.mark.parametrize("upgraded,energy", [(False, 2), (True, 3)])
def test_outmaneuver_gives_energy_next_turn(upgraded, energy):
    cs = make_state([card(CardId.OUTMANEUVER, upgraded)], enemy_count=1)
    play(cs)
    assert cs.player.status_amount(StatusId.ENERGY_NEXT_TURN) == energy


def test_hello_world_adds_a_common_card_each_turn_and_is_innate_upgraded():
    from sts2_lite.card.tables import CARD_RARITY, CardRarity
    cs = make_state([card(CardId.HELLO_WORLD)], enemy_count=1)
    sim = play(cs)
    assert cs.player.status_amount(StatusId.HELLO_WORLD) == 1 and not cs.player.hand
    sim.fire(HookType.PLAYER_TURN_START)
    assert len(cs.player.hand) == 1 and CARD_RARITY[cs.player.hand[0].card_id] == CardRarity.Common
    from sts2_lite.card import CardKeyword
    assert CardKeyword.INNATE not in card(CardId.HELLO_WORLD).keywords and CardKeyword.INNATE in card(CardId.HELLO_WORLD, True).keywords


@pytest.mark.parametrize("upgraded,damage", [(False, 9), (True, 12)])
def test_rebound_hits_and_puts_the_next_card_on_top_of_the_draw_pile(upgraded, damage):
    cs = make_state([card(CardId.REBOUND, upgraded), strike(), strike(), defend()], enemy_count=1, enemy_hp=50)
    sim = play(cs)
    assert cs.enemies[0].current_hp == 50 - damage and cs.player.status_amount(StatusId.REBOUND) == 1
    sim.play_card(0, 0)                                # the next card: back on top of the draw pile
    assert cs.player.draw_pile[-1].card_id == CardId.STRIKE_IRONCLAD and [c.card_id for c in cs.player.discard_pile] == [CardId.REBOUND]
    assert cs.player.status_amount(StatusId.REBOUND) == 0
    sim.play_card(0, 0)                                # the one after goes to the discard pile as usual
    assert [c.card_id for c in cs.player.discard_pile] == [CardId.REBOUND, CardId.STRIKE_IRONCLAD] and len(cs.player.draw_pile) == 1


def test_rebound_is_used_up_by_a_power_or_an_exhausting_card_which_then_does_not_go_on_top():
    cs = make_state([card(CardId.REBOUND), card(CardId.CALTROPS)], enemy_count=1)
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.REBOUND) == 0 and not cs.player.draw_pile
    cs = make_state([card(CardId.REBOUND), card(CardId.DISTRACTION)], enemy_count=1)
    sim = play(cs)
    sim.play_card(0, 0)
    assert cs.player.status_amount(StatusId.REBOUND) == 0 and not cs.player.draw_pile and [c.card_id for c in cs.player.exhaust_pile] == [CardId.DISTRACTION]


@pytest.mark.parametrize("upgraded,damage", [(False, 7), (True, 9)])
def test_rip_and_tear_hits_twice_at_random_enemies(upgraded, damage):
    cs = make_state([card(CardId.RIP_AND_TEAR, upgraded)], enemy_count=1, enemy_hp=50)
    play(cs)
    assert cs.enemies[0].current_hp == 50 - 2 * damage


@pytest.mark.parametrize("upgraded,extra", [(False, 0), (True, 3)])
def test_stack_blocks_the_discard_pile_size_and_takes_dexterity_and_frail(upgraded, extra):
    cs = make_state([card(CardId.STACK, upgraded)], enemy_count=1)
    cs.player.discard_pile = [strike() for _ in range(4)]
    cs.player.apply_status(StatusId.DEXTERITY, 2)
    play(cs)
    assert cs.player.block == 4 + extra + 2
    cs = make_state([card(CardId.STACK, upgraded)], enemy_count=1)
    cs.player.discard_pile = [strike() for _ in range(8)]
    cs.player.apply_status(StatusId.FRAIL, 2)
    play(cs)
    assert cs.player.block == int((8 + extra) * 0.75)


def test_rebound_does_not_last_between_turns():
    cs = make_state([card(CardId.REBOUND), strike()], enemy_count=1)
    sim = play(cs)
    sim.fire(HookType.PLAYER_TURN_ENDED)
    assert cs.player.status_amount(StatusId.REBOUND) == 0


def test_dual_wield_clones_of_a_free_card_are_free_too():
    for free in (lambda c: c.free_this_turn(), lambda c: c.free_this_combat()):
        pick = free(strike())
        cs = make_state([card(CardId.DUAL_WIELD), pick], enemy_count=1)
        play(cs)
        clone = [c for c in cs.player.hand if c is not pick][0]
        assert pick.current_cost(cs.player) == 0 and clone.current_cost(cs.player) == 0
