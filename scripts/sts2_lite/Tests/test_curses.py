"""Curse cards. Run from scripts/: python -m pytest sts2_lite/Tests"""
import pytest

from sts2_lite.card import Card, CardId, CardType, CardKeyword, CURSE_CARDS, GENERATED_CARDS
from sts2_lite.combat import CombatSimulator
from sts2_lite.status import StatusId
from test_cards import make_card, make_state, TargetType

def curse(card_id):
    return Card.create(card_id)

def strike():
    return make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)

def defend():
    return make_card(CardId.DEFEND_IRONCLAD, "Defend", CardType.Skill, 1, TargetType.NONE)

def end_turn(hand):
    cs = make_state(hand, enemy_count=1)
    CombatSimulator(cs).end_turn()
    return cs


def test_every_curse_is_a_curse_type_and_generatable():
    assert len(CURSE_CARDS) == 15
    for cid in CURSE_CARDS:
        assert GENERATED_CARDS[cid]().type == CardType.Curse

@pytest.mark.parametrize("cid", sorted(CURSE_CARDS - {CardId.SPORE_MIND}, key=lambda c: c.name))
def test_curses_are_unplayable_and_cost_nothing(cid):
    c = curse(cid)
    assert c.unplayable and c.is_unplayable and c.energy_cost == 0
    cs = make_state([c], enemy_count=1)
    assert not c.can_play_card(CombatSimulator(cs), 0)

def test_curses_cannot_be_upgraded():
    assert not curse(CardId.REGRET).is_upgradable

def test_canonical_keywords():
    kw = lambda cid: {k for k in curse(cid).keywords}
    assert CardKeyword.ETHEREAL in kw(CardId.CLUMSY)
    assert kw(CardId.ASCENDERS_BANE) >= {CardKeyword.ETHEREAL, CardKeyword.ETERNAL, CardKeyword.UNPLAYABLE}
    assert kw(CardId.POOR_SLEEP) >= {CardKeyword.RETAIN, CardKeyword.UNPLAYABLE}
    assert kw(CardId.WRITHE) >= {CardKeyword.INNATE, CardKeyword.UNPLAYABLE}
    assert kw(CardId.SPORE_MIND) == {CardKeyword.EXHAUST}
    assert CardKeyword.ETERNAL in kw(CardId.GREED) and CardKeyword.ETERNAL in kw(CardId.CURSE_OF_THE_BELL)

def test_from_dict_reads_curse_type():
    d = {"id": "WRITHE", "type": "Curse", "name": "Writhe", "can_play": False, "cost": "0", "is_upgraded": False,
         "target_type": "None", "description": "", "card_keywords": ["Unplayable", "Innate"]}
    c = Card.from_dict(d)
    assert c.type == CardType.Curse and c.unplayable and c.is_unplayable


# ---- end-of-turn effects
def test_regret_loses_one_hp_per_card_in_hand_including_itself():
    cs = end_turn([curse(CardId.REGRET), strike(), defend()])
    assert cs.player.current_hp == 50 - 3

def test_regret_ignores_block():
    cs = make_state([curse(CardId.REGRET), strike()], enemy_count=1)
    cs.player.block = 10
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 48 and cs.player.block == 0       # block drops at the next turn start

def test_regret_counts_the_hand_before_discard():
    cs = end_turn([curse(CardId.REGRET), curse(CardId.REGRET)])
    assert cs.player.current_hp == 50 - 2 - 2

def test_decay_deals_two_damage_and_block_absorbs_it():
    assert end_turn([curse(CardId.DECAY)]).player.current_hp == 48
    cs = make_state([curse(CardId.DECAY)], enemy_count=1)
    cs.player.block = 5
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 50

def test_two_decays_stack():
    assert end_turn([curse(CardId.DECAY), curse(CardId.DECAY)]).player.current_hp == 46

def hand_end(card):
    cs = make_state([card], enemy_count=1)
    card.on_turn_end_in_hand(CombatSimulator(cs))
    return cs

def hand_end(card, **status):
    cs = make_state([card], enemy_count=1)
    for sid, amount in status.items():
        cs.player.apply_status(StatusId[sid], amount)
    card.on_turn_end_in_hand(CombatSimulator(cs))
    return cs

def test_shame_and_doubt_apply_two_stacks_when_absent_else_one():
    assert hand_end(curse(CardId.SHAME)).player.status[StatusId.FRAIL].amount == 2
    assert hand_end(curse(CardId.DOUBT)).player.status[StatusId.WEAK].amount == 2
    assert hand_end(curse(CardId.SHAME), FRAIL=1).player.status[StatusId.FRAIL].amount == 2
    assert hand_end(curse(CardId.DOUBT), WEAK=3).player.status[StatusId.WEAK].amount == 4

def test_shame_leaves_one_frail_for_the_next_player_turn():
    assert end_turn([curse(CardId.SHAME)]).player.status[StatusId.FRAIL].amount == 1
    assert end_turn([curse(CardId.DOUBT)]).player.status[StatusId.WEAK].amount == 1

def test_shame_is_blocked_by_artifact():
    cs = make_state([curse(CardId.SHAME)], enemy_count=1)
    cs.player.apply_status(StatusId.ARTIFACT, 1)
    cs.player.hand[0].on_turn_end_in_hand(CombatSimulator(cs))
    assert StatusId.FRAIL not in cs.player.status and StatusId.ARTIFACT not in cs.player.status

def test_dead_curses_do_nothing_at_turn_end():
    for cid in (CardId.INJURY, CardId.WRITHE, CardId.GREED, CardId.CURSE_OF_THE_BELL, CardId.GUILTY, CardId.NORMALITY):
        assert end_turn([curse(cid)]).player.current_hp == 50

def test_curse_in_discard_does_nothing():
    cs = make_state([strike()], enemy_count=1)
    cs.player.discard_pile.append(curse(CardId.DECAY))
    CombatSimulator(cs).end_turn()
    assert cs.player.current_hp == 50


# ---- Ethereal / Retain
def test_ethereal_curses_exhaust_at_turn_end_after_taking_effect():
    cs = end_turn([curse(CardId.CLUMSY), curse(CardId.ASCENDERS_BANE), curse(CardId.FOLLY)])
    ids = {c.card_id for c in cs.player.exhaust_pile}
    assert {CardId.CLUMSY, CardId.ASCENDERS_BANE, CardId.FOLLY} <= ids
    assert not any(c.type == CardType.Curse for c in cs.player.discard_pile)

def test_poor_sleep_is_retained():
    cs = make_state([curse(CardId.POOR_SLEEP), strike()], enemy_count=1)
    sim = CombatSimulator(cs)
    sim.end_turn()
    assert any(c.card_id == CardId.POOR_SLEEP for c in cs.player.hand) or \
        any(c.card_id == CardId.POOR_SLEEP for c in cs.player.draw_pile + cs.player.discard_pile)
    assert not any(c.card_id == CardId.POOR_SLEEP for c in cs.player.discard_pile)

def test_a_regular_unplayable_curse_is_discarded():
    cs = end_turn([curse(CardId.INJURY)])
    assert any(c.card_id == CardId.INJURY for c in cs.player.discard_pile + cs.player.hand + cs.player.draw_pile)


# ---- Spore Mind
def test_spore_mind_costs_one_and_exhausts_when_played():
    c = curse(CardId.SPORE_MIND)
    assert c.energy_cost == 1 and not c.is_unplayable
    cs = make_state([c], enemy_count=1)
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.energy == 2
    assert [x.card_id for x in cs.player.exhaust_pile] == [CardId.SPORE_MIND]
    assert cs.player.hand == []


# ---- Normality
def test_normality_limits_a_turn_to_three_cards():
    cs = make_state([curse(CardId.NORMALITY)] + [strike() for _ in range(5)], enemy_count=1)
    cs.energy = cs.max_energy = 10
    sim = CombatSimulator(cs)
    for _ in range(3):
        sim.play_card(1, 0)
    assert not cs.player.hand[1].can_play_card(sim, 0)

def test_without_normality_there_is_no_limit():
    cs = make_state([strike() for _ in range(5)], enemy_count=1)
    cs.energy = cs.max_energy = 10
    sim = CombatSimulator(cs)
    for _ in range(4):
        sim.play_card(0, 0)
    assert cs.player.hand[0].can_play_card(sim, 0)

def test_normality_counts_cards_played_before_it_was_drawn():
    cs = make_state([curse(CardId.NORMALITY), strike()], enemy_count=1)
    cs.cards_played = 3
    assert not cs.player.hand[1].can_play_card(CombatSimulator(cs), 0)


def bridge_card(cid, can_play, cost=1, ctype="Attack", target="AnyEnemy", keywords=()):
    return {"id": cid, "type": ctype, "name": cid.title(), "can_play": can_play, "cost": str(cost), "is_upgraded": False,
            "target_type": target, "description": "", "card_keywords": list(keywords)}

def loaded_hand(*cards, energy=3):
    """Mirror of what load does after reading the hand: apply the Normality inference."""
    cs = make_state([Card.from_dict(c) for c in cards], enemy_count=1)
    cs.energy = energy
    cs._infer_normality_plays()
    return cs

NORMALITY = bridge_card("NORMALITY", False, 0, "Curse", "None", ["Unplayable"])

def test_normality_inferred_when_an_affordable_card_is_shown_unplayable():
    cs = loaded_hand(NORMALITY, bridge_card("STRIKE_IRONCLAD", False))
    assert cs.cards_played == 3
    assert not cs.player.hand[1].is_unplayable          # the sim now derives playability itself
    assert not cs.player.hand[1].can_play_card(CombatSimulator(cs), 0)

def test_normality_not_inferred_when_a_card_is_playable():
    cs = loaded_hand(NORMALITY, bridge_card("STRIKE_IRONCLAD", True))
    assert cs.cards_played == 0

def test_normality_not_inferred_when_the_card_is_just_too_expensive():
    cs = loaded_hand(NORMALITY, bridge_card("BLUDGEON", False, 3), energy=1)
    assert cs.cards_played == 0

def test_normality_not_inferred_for_a_dead_hand():
    cs = loaded_hand(NORMALITY, bridge_card("WOUND", False, 0, "Status", "None", ["Unplayable"]))
    assert cs.cards_played == 0

def test_no_inference_without_normality():
    cs = loaded_hand(bridge_card("STRIKE_IRONCLAD", False))
    assert cs.cards_played == 0
