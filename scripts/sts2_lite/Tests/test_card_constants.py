from sts2_lite.card.constants import CARD_ENERGY_COST_AND_TARGET
from sts2_lite.card.tables import GENERATABLE_CARDS, COLORLESS_CARDS, ANCIENT_CARDS, EVENT_CARDS, TOKEN_CARDS, CARD_RARITY
from sts2_lite.card.ids import CardId


def test_matches_the_card_tables():
    for table in (GENERATABLE_CARDS, COLORLESS_CARDS, ANCIENT_CARDS, EVENT_CARDS, TOKEN_CARDS):
        for card, (_, _, cost, target) in table.items():
            assert CARD_ENERGY_COST_AND_TARGET[card] == (cost, target), card


def test_every_playable_ironclad_card_has_a_cost():
    for card, rarity in CARD_RARITY.items():
        if rarity.name in ("Basic", "Common", "Uncommon", "Rare"):
            assert card in CARD_ENERGY_COST_AND_TARGET, card
    assert CARD_ENERGY_COST_AND_TARGET[CardId.BASH][0] == 2
