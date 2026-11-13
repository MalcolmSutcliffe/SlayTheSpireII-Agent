from __future__ import annotations

from sts2_lite.card.card import Card
from sts2_lite.card.constants import CURSE_CARDS
from sts2_lite.card.ids import CardId

GENERATED_CARDS = {
    CardId.SLIMED : Card.create_slimed,
    CardId.INFECTION : Card.create_infection,
    CardId.BURN : Card.create_burn,
    CardId.BECKON : Card.create_beckon,
    CardId.WITHER : Card.create_wither,
    CardId.DAZED : Card.create_dazed,
    CardId.WOUND : Card.create_wound,
    CardId.SOOT : Card.create_soot,
    CardId.TOXIC : Card.create_toxic,
    CardId.FRANTIC_ESCAPE : Card.create_frantic_escape,
}

for _curse in (CardId.DISINTEGRATION, CardId.MIND_ROT, CardId.SLOTH, CardId.WASTE_AWAY):
    GENERATED_CARDS[_curse] = lambda _curse=_curse: Card.create_knowledge_curse(_curse)

for _curse in CURSE_CARDS:
    GENERATED_CARDS[_curse] = lambda _curse=_curse: Card.create_curse(_curse)
