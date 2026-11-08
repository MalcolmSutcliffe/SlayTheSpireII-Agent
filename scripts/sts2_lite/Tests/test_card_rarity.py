import re
from pathlib import Path
import pytest
from sts2_lite.card import CARD_RARITY, RARE_CARDS, CardId, CardRarity

DECOMPILED = Path(__file__).resolve().parents[3] / "sts2_decompiled" / "MegaCrit.Sts2.Core.Models.Cards"

def _pascal(card_id : CardId) -> str:
    return "".join(part.capitalize() for part in card_id.name.split("_"))

def test_every_card_has_a_rarity():
    assert set(CARD_RARITY) == set(CardId)

def test_rarity_values_are_rarities():
    assert all(isinstance(r, CardRarity) for r in CARD_RARITY.values())

@pytest.mark.parametrize("cid,rarity", [(CardId.STRIKE_IRONCLAD, CardRarity.Basic), (CardId.DEFEND_IRONCLAD, CardRarity.Basic),
                                        (CardId.BASH, CardRarity.Basic), (CardId.ANGER, CardRarity.Common),
                                        (CardId.INFLAME, CardRarity.Uncommon), (CardId.BARRICADE, CardRarity.Rare),
                                        (CardId.ENTROPY, CardRarity.Rare), (CardId.HIDDEN_GEM, CardRarity.Rare),
                                        (CardId.DAZED, CardRarity.Status), (CardId.WRITHE, CardRarity.Curse),
                                        (CardId.NEOWS_FURY, CardRarity.Ancient), (CardId.TORIC_TOUGHNESS, CardRarity.Event)])
def test_known_rarities(cid, rarity):
    assert CARD_RARITY[cid] == rarity

def test_rare_cards_derive_from_the_table():
    assert RARE_CARDS == {c for c, r in CARD_RARITY.items() if r == CardRarity.Rare}
    assert {CardId.ENTROPY, CardId.HIDDEN_GEM, CardId.BARRICADE} <= RARE_CARDS
    assert not {CardId.BASH, CardId.NEOWS_FURY, CardId.CORRUPTION, CardId.BREAK} & RARE_CARDS

@pytest.mark.skipif(not DECOMPILED.is_dir(), reason="decompiled sources not present")
def test_matches_decompiled_source():
    for cid, rarity in CARD_RARITY.items():
        path = DECOMPILED / f"{_pascal(cid)}.cs"
        if not path.exists():
            assert cid == CardId.NOT_IMPLEMENTED
            continue
        found = re.search(r"CardRarity\.(\w+)", path.read_text())
        assert found and found.group(1) == rarity.name, cid
