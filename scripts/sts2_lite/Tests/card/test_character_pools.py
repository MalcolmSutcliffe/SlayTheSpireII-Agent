"""Combat card generation draws from the owner's Character.CardPool (CardFactory.FilterForCombat), and Splash from the other characters'."""
import pytest

from sts2_lite.card import Card, CardId, CardType
from sts2_lite.card.tables import (CARD_RARITY, CardRarity, GENERATABLE_CARDS, SILENT_CARDS, combat_pool, splash_pool, transform_options,
                                   zero_cost_pool)
from sts2_lite.combat import CombatSimulator
from sts2_lite.player import Player
from sts2_lite.Tests.card.test_card import make_state


def silent_state(hand):
    cs = make_state(hand)
    cs.player.character = "SILENT"
    return cs


def test_silent_combat_pool():
    pool = set(combat_pool("SILENT"))
    assert pool <= set(SILENT_CARDS)
    assert CardId.NIGHTMARE not in pool and CardId.THE_HUNT not in pool         # CanBeGeneratedInCombat => false
    assert not {CardId.STRIKE_SILENT, CardId.DEFEND_SILENT, CardId.NEUTRALIZE, CardId.SURVIVOR} & pool
    assert len(pool) == 78
    assert set(combat_pool("SILENT", CardType.Attack)) <= {c for c in pool if SILENT_CARDS[c][1] == CardType.Attack}
    assert all(CARD_RARITY[c] == CardRarity.Common for c in combat_pool("SILENT", rarity=CardRarity.Common))
    assert all(SILENT_CARDS[c][2] == 0 for c in zero_cost_pool("SILENT"))

def test_ironclad_pool_is_unchanged():
    assert set(combat_pool("IRONCLAD")) == set(GENERATABLE_CARDS)
    assert set(combat_pool("SOMEONE_ELSE")) == set(GENERATABLE_CARDS)

def test_player_reads_its_character():
    assert Player.from_dict({"character": "The Silent", "max_hp": 70, "hp": 70, "block": 0, "status": [], "hand": [], "draw_pile": [],
                             "discard_pile": [], "exhaust_pile": [], "relics": [], "energy": 3, "max_energy": 3}).character == "SILENT"
    assert Player().character == "IRONCLAD"

def test_character_survives_copying():
    from copy import deepcopy
    assert deepcopy(silent_state([])).player.character == "SILENT"

def test_distraction_makes_a_silent_skill():
    cs = silent_state([Card.create_generated(CardId.DISTRACTION)])
    CombatSimulator(cs).play_card(0, 0)
    made = cs.player.hand[-1]
    assert made.card_id in combat_pool("SILENT") and made.type == CardType.Skill

def test_discovery_offers_silent_cards():
    cs = silent_state([Card.create_generated(CardId.DISCOVERY)])
    CombatSimulator(cs).play_card(0, 0)
    assert all(c.card_id in combat_pool("SILENT") for c in cs.pending_choice.offers)

def test_transform_stays_in_the_cards_own_pool():
    assert set(transform_options(Card.create_generated(CardId.SLICE))) == set(combat_pool("SILENT")) - {CardId.SLICE} | {CardId.NIGHTMARE, CardId.THE_HUNT}
    assert set(transform_options(Card.create_generated(CardId.ANGER))) == set(GENERATABLE_CARDS) - {CardId.ANGER}


# ------------------------------------------------------------ Splash
def test_splash_table():
    card = Card.create_generated(CardId.SPLASH)
    assert (card.energy_cost, card.type, CARD_RARITY[CardId.SPLASH]) == (1, CardType.Skill, CardRarity.Rare)
    assert not card.exhausts

def test_splash_pool_is_the_other_characters_attacks():
    attacks = {name: set(combat_pool(name, CardType.Attack)) for name in ("IRONCLAD", "SILENT", "REGENT", "NECROBINDER")}
    assert set(splash_pool("SILENT")) == attacks["IRONCLAD"] | attacks["REGENT"] | attacks["NECROBINDER"]
    assert set(splash_pool("IRONCLAD")) == attacks["SILENT"] | attacks["REGENT"] | attacks["NECROBINDER"]
    assert set(splash_pool("REGENT")) == attacks["IRONCLAD"] | attacks["SILENT"] | attacks["NECROBINDER"]
    assert set(splash_pool("NECROBINDER")) == attacks["IRONCLAD"] | attacks["SILENT"] | attacks["REGENT"]

@pytest.mark.parametrize("upgraded", [False, True])
def test_splash_offers_three_other_attacks_and_the_pick_is_free(upgraded):
    cs = silent_state([Card.create_generated(CardId.SPLASH, upgraded)])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    offers = cs.pending_choice.offers
    assert len({c.card_id for c in offers}) == 3
    assert all(c.card_id in set(splash_pool("SILENT")) and c.type == CardType.Attack and c.is_upgraded == upgraded for c in offers)
    sim.choose_card(cs.pending_choice.indices[0])
    picked = cs.player.hand[-1]
    assert picked.card_id in set(splash_pool("SILENT")) and picked.current_cost(cs.player) in (0, "X")

def test_splash_can_be_skipped():
    cs = silent_state([Card.create_generated(CardId.SPLASH)])
    sim = CombatSimulator(cs)
    sim.play_card(0, 0)
    assert cs.pending_choice.optional and [a["action"] for a in sim.get_available_actions()][-1] == "confirm_choice"
    sim.confirm_choice()
    assert cs.pending_choice is None and not cs.player.hand and [c.card_id for c in cs.player.discard_pile] == [CardId.SPLASH]
