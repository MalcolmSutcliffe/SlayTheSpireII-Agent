"""The Defect's relics that act during a fight. Cracked Core, Infused Core, Symbiotic Virus, Runic Capacitor, Data Disk and Power Cell are in combat_start.py;
Gold Plated Cables, Infused Core's extra damage and Metronome are in orbs.py."""
from __future__ import annotations

from sts2_lite import orbs
from sts2_lite.helpers import player_of


def _emotion_chip_hurt(combat, relic, amount):
    """EmotionChip.AfterDamageReceived: it wakes up (an HP loss stands in for unblocked damage)."""
    relic.value = 1

def _emotion_chip_turn_start(combat, relic):
    """EmotionChip.AfterPlayerTurnStart: after a turn that cost HP, every orb's Passive triggers once more."""
    woken, relic.value = relic.value, 0
    if woken and player_of(combat).orbs:
        orbs.trigger_all_passives(combat)
        combat.resolve_deaths()
