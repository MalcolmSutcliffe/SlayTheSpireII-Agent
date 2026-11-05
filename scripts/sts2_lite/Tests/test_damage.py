"""Damage maths tests. Run from scripts/: python -m pytest sts2_lite/Tests"""
import itertools

import pytest

from sts2_lite.creature import Creature
from sts2_lite.damage import base_from_displayed, modify_damage
from sts2_lite.status import StatusId


def make(strength=0, weak=False, vulnerable=False):
    c = Creature()
    if strength:
        c.apply_status(StatusId.STRENGTH, strength)
    if weak:
        c.apply_status(StatusId.WEAK, 1)
    return c

def make_target(vulnerable=False):
    t = Creature()
    if vulnerable:
        t.apply_status(StatusId.VULNERABLE, 1)
    return t


# ---------------------------------------------------------------- modify_damage
def test_no_modifiers():
    assert modify_damage(6, make(), make_target()) == 6

def test_strength_adds_before_multipliers():
    assert modify_damage(6, make(strength=3, weak=True), make_target()) == 6      # 9 * 0.75 = 6.75

def test_weak_truncates():
    assert modify_damage(6, make(weak=True), make_target()) == 4                  # 4.5

def test_vulnerable_truncates():
    assert modify_damage(7, make(), make_target(vulnerable=True)) == 10           # 10.5

def test_weak_and_vulnerable_truncate_once_at_the_end():
    # 9 * 0.75 * 1.5 = 10.125; truncating after each step would give 9
    assert modify_damage(9, make(weak=True), make_target(vulnerable=True)) == 10

def test_negative_strength_cannot_go_below_zero():
    assert modify_damage(4, make(strength=-9), make_target()) == 0


# ---------------------------------------------------------------- base_from_displayed
def test_no_modifiers_is_identity():
    assert base_from_displayed(12, make(), make_target()) == 12

@pytest.mark.parametrize("displayed, base", [(9, 6), (10, 7), (12, 8), (15, 10)])
def test_vulnerable_target(displayed, base):
    assert base_from_displayed(displayed, make(), make_target(vulnerable=True)) == base

def test_strength_and_vulnerable():
    # (6 + 3) * 1.5 = 13.5 -> 13
    assert base_from_displayed(13, make(strength=3), make_target(vulnerable=True)) == 6

def test_strength_only():
    assert base_from_displayed(11, make(strength=4), make_target()) == 7

def test_weak_ambiguity_returns_the_largest_base():
    # bases 4 and 5 both display as 3 under Weak
    assert modify_damage(3, make(weak=True), make_target()) == 2
    assert modify_damage(4, make(weak=True), make_target()) == 3
    assert modify_damage(5, make(weak=True), make_target()) == 3
    assert modify_damage(6, make(weak=True), make_target()) == 4
    assert base_from_displayed(3, make(weak=True), make_target()) == 5

def test_unreachable_value_falls_back_to_displayed():
    # no base displays as 8 under Vulnerable (7 -> 10, 6 -> 9, 5 -> 7)
    assert base_from_displayed(8, make(), make_target(vulnerable=True)) == 8

def test_zero_displayed_with_no_modifiers():
    assert base_from_displayed(0, make(), make_target()) == 0

def test_round_trip_over_all_small_cases():
    for strength, weak, vulnerable, base in itertools.product(
            range(-3, 7), (False, True), (False, True), range(0, 81)):
        attacker, target = make(strength, weak), make_target(vulnerable)
        displayed = modify_damage(base, attacker, target)
        recovered = base_from_displayed(displayed, attacker, target)
        case = (strength, weak, vulnerable, base, displayed, recovered)
        assert modify_damage(recovered, attacker, target) == displayed, case
        assert recovered >= base, case
        multiplier_at_least_one = not weak or vulnerable
        if displayed > 0 and multiplier_at_least_one:
            assert recovered == base, case
