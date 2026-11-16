"""The comparable snapshot of a state (agents/verify.py) is built for any hand, also when logging a mismatch."""
from agents.verify import snapshot
from sts2_lite.card.ids import CardId, CardType, EnchantmentId, TargetType
from sts2_lite.Tests.card.test_card import make_card, make_state


def test_a_hand_of_identical_cards_with_and_without_an_enchantment_can_be_snapshotted():
    plain = make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)
    enchanted = make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)
    enchanted.enchantment = next(iter(EnchantmentId))
    for hand in ([plain, enchanted], [enchanted, plain]):
        shown = snapshot(make_state(hand))["hand"]
        assert [t[3] for t in shown] == [None, enchanted.enchantment.name]          # the same order whatever the hand's


def test_an_x_cost_card_sorts_beside_a_numbered_one_of_the_same_kind():
    x_cost = make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, "X", TargetType.AnyEnemy)
    one = make_card(CardId.STRIKE_IRONCLAD, "Strike", CardType.Attack, 1, TargetType.AnyEnemy)
    assert len(snapshot(make_state([x_cost, one]))["hand"]) == 2
