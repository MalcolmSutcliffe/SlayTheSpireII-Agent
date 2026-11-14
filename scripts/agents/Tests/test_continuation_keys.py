from types import SimpleNamespace

from agents.sts2_MCTS.state_key import _continuations
from sts2_lite.card.card import Card


def card(card_id="BASH"):
    return Card.from_dict({"id": card_id, "name": card_id, "type": "Attack", "cost": 2, "target_type": "AnyEnemy", "is_upgraded": False, "can_play": True})


def key(*continuations):
    return _continuations(SimpleNamespace(continuations=list(continuations)))


def test_every_continuation_kind_has_a_hashable_key():
    c = card()
    saved = (5, {"ANCHOR": (0, False, 0, False)})
    keys = key(("finish", c, 3, False, None, False), ("play", (c, card("STRIKE_IRONCLAD"))), ("random", 2), ("replay", c, 0, None, 2, saved, 1))
    assert len(keys) == 4
    hash(keys)


def test_equal_states_have_equal_keys_and_different_ones_differ():
    assert key(("replay", card(), 0, None, 2, None, 1)) == key(("replay", card(), 0, None, 2, None, 1))
    assert key(("replay", card(), 0, None, 2, None, 1)) != key(("replay", card(), 0, None, 1, None, 1))
    assert key(("random", 1)) != key(("random", 2))
