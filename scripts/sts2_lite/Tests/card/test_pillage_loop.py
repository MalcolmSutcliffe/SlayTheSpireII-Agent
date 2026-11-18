"""Pillage draws until a non-Attack or a full hand; under Hellraiser a drawn Strike plays itself and leaves the hand, so against an enemy that cannot die
the game's loop never ends. The engine stops it after PILLAGE_MAX_DRAWS draws."""
from types import SimpleNamespace

from sts2_lite.card.ids import CardType
from sts2_lite.card.plays import ironclad


def test_pillage_stops_drawing_when_the_drawn_attacks_never_stay_in_hand(monkeypatch):
    monkeypatch.setattr(ironclad, "enemy_at", lambda combat, i: None)
    monkeypatch.setattr(ironclad, "_attack", lambda combat, damage, target: None)
    strike = SimpleNamespace(type=CardType.Attack)
    draws = []
    player = SimpleNamespace(hand=[], draw_card=lambda: draws.append(1) or strike)          # every card drawn is an Attack that leaves the hand at once
    combat = SimpleNamespace(combat_state=SimpleNamespace(player=player))
    ironclad.play_pillage(None, combat)
    assert len(draws) == ironclad.PILLAGE_MAX_DRAWS


def test_pillage_still_stops_at_the_first_non_attack(monkeypatch):
    monkeypatch.setattr(ironclad, "enemy_at", lambda combat, i: None)
    monkeypatch.setattr(ironclad, "_attack", lambda combat, damage, target: None)
    cards = [SimpleNamespace(type=CardType.Attack)] * 3 + [SimpleNamespace(type=CardType.Skill)] + [SimpleNamespace(type=CardType.Attack)] * 5
    hand = []
    player = SimpleNamespace(hand=hand, draw_card=lambda: hand.append(cards[len(hand)]) or hand[-1])
    ironclad.play_pillage(None, SimpleNamespace(combat_state=SimpleNamespace(player=player)))
    assert len(hand) == 4
