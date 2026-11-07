"""Card.signature: cards with equal signatures play identically (used to cull identical actions)."""
import pytest

from sts2_lite.card import Card, CardId, CardKeyword, CardType, TargetType, EnchantmentId

def make(card_id=CardId.STRIKE_IRONCLAD, cost=1):
    c = Card()
    c.card_id, c.name, c.type = card_id, card_id.name, CardType.Attack
    c.energy_cost, c.target_type = cost, TargetType.AnyEnemy
    c.is_upgraded = c.is_unplayable = False
    c.restore_cost = None
    c.enchantment = None
    return c

def test_separate_copies_of_a_card_share_a_signature():
    assert make().signature() == make().signature()

def test_create_copy_keeps_the_signature():
    c = make()
    c.bonus_damage, c.replay, c.restore_cost = 3, 1, 2
    assert Card.create_copy(c).signature() == c.signature()

def test_the_signature_can_be_hashed():
    assert len({make().signature(), make().signature()}) == 1

def mutate_upgrade(c): c.is_upgraded = True
def mutate_cost(c): c.energy_cost = 0
def mutate_unplayable(c): c.is_unplayable = True
def mutate_restore(c): c.restore_cost = 1
def mutate_bonus(c): c.bonus_damage = 2
def mutate_replay(c): c.replay = 1
def mutate_enchant(c): c.enchantment = next(iter(EnchantmentId))
def mutate_enchant_amount(c): c.enchant_amount = 2
def mutate_enchant_bonus(c): c.enchant_bonus = 1
def mutate_keywords(c): c._keywords = c._mask ^ next(iter(CardKeyword)).value
def mutate_id(c): c.card_id = CardId.DEFEND_IRONCLAD

@pytest.mark.parametrize("mutate", [mutate_upgrade, mutate_cost, mutate_unplayable, mutate_restore, mutate_bonus,
                                    mutate_replay, mutate_enchant, mutate_enchant_amount, mutate_enchant_bonus,
                                    mutate_keywords, mutate_id])
def test_every_field_that_changes_how_a_card_plays_changes_the_signature(mutate):
    a, b = make(), make()
    mutate(b)
    assert a.signature() != b.signature()

def test_create_copy_fields_are_all_in_the_signature():
    """A field create_copy carries over but the signature ignores would let different cards be culled as identical."""
    import inspect
    src = inspect.getsource(Card.create_copy)
    copied = {line.split("new_card.")[1].split(" =")[0].split(",")[0] for line in src.splitlines() if "new_card." in line and "=" in line}
    not_in_signature = {"type", "name", "target_type"}          # follow from card_id
    sig_src = inspect.getsource(Card.signature)
    for field in copied - not_in_signature:
        assert field.lstrip("_") in sig_src or field == "_keywords", field
