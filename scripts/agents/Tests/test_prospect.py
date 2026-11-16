"""The prospective-card bonus (agents/deck_eval/prospect.py)."""
import agents.deck_eval.prospect as prospect


def table(monkeypatch, **values):
    monkeypatch.setattr(prospect, "values", lambda *a: values)

def test_the_bonus_falls_with_the_run_and_needs_a_winning_deck(monkeypatch):
    table(monkeypatch, DEMON_FORM=1.0)
    card = {"id": "DEMON_FORM"}
    early, late = prospect.bonus(card, [], 2, 0.9), prospect.bonus(card, [], 30, 0.9)
    assert early > late > 0 and prospect.bonus(card, [], 45, 0.9) == 0
    assert prospect.bonus(card, [], 2, 0.4) == 0 and prospect.bonus(card, [], 2, 0.9) > prospect.bonus(card, [], 2, 0.6) > 0

def test_held_prospects_and_a_hurting_card_lower_the_bonus(monkeypatch):
    table(monkeypatch, DEMON_FORM=1.0, BARRICADE=1.0)
    card = {"id": "BARRICADE"}
    assert prospect.bonus(card, [{"id": "DEMON_FORM"}], 2, 0.9) == prospect.bonus(card, [], 2, 0.9) / 2
    assert prospect.bonus(card, [], 2, 0.9, gain=-0.1) == 0

def test_a_card_without_a_value_gets_nothing_and_the_shipped_table_loads(monkeypatch):
    table(monkeypatch)
    assert prospect.bonus({"id": "ANGER"}, [], 0, 1.0) == 0
    monkeypatch.undo()
    prospect.values.cache_clear()
    assert isinstance(prospect.values(), dict)          # empty until the table is filled in
