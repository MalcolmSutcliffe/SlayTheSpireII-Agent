import pytest

from sts2_lite.card import tables
from sts2_lite.card.card import Card
from sts2_lite.card.effects import _printed_damage
from sts2_lite.card.ids import CardType
from sts2_lite.player import Player
from types import SimpleNamespace


def attacks():
    for table in (tables.GENERATABLE_CARDS, tables.COLORLESS_CARDS, tables.ANCIENT_CARDS, tables.EVENT_CARDS, tables.TOKEN_CARDS):
        for card, (_, ctype, _, _) in table.items():
            if ctype == CardType.Attack:
                yield card


@pytest.mark.parametrize("card_id", sorted(set(attacks()), key=lambda c: c.name))
def test_every_attack_has_a_printed_damage(card_id):
    """Thrash exhausts an attack from the hand and adds its printed damage: no attack of the game may be missing from that lookup."""
    combat = SimpleNamespace(combat_state=SimpleNamespace(player=Player()))
    for upgraded in (False, True):
        card = Card.from_dict({"id": card_id.name, "name": card_id.name, "type": "Attack", "cost": 1, "target_type": "AnyEnemy", "is_upgraded": False, "can_play": True})
        if upgraded and card.is_upgradable:
            card = card.upgraded_copy()
        assert isinstance(_printed_damage(card, combat), int)
