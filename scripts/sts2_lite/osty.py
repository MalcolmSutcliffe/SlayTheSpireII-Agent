"""The Necrobinder's Osty (Models.Monsters.Osty, OstyCmd): a pet with hit points that fights for the player.

Osty has no Block of its own (it shares its owner's) and keeps no powers but DieForYou, which `Player._lose_hp_from_damage` plays: once Block is gone,
the unblocked part of an Attack goes to Osty, and what Osty cannot take goes on to the player. A dead Osty stays in the combat (`Player.osty` with 0 HP)
until the next Summon revives it. The bridge does not report Osty, so a state read from the game starts without one."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.card import Card
    from sts2_lite.player import Player


_OSTY_CLASS = None

def new_osty(hp : int = 1):
    """An Osty (the class is built on first use: Creature cannot be imported while the card tables load)."""
    global _OSTY_CLASS
    if _OSTY_CLASS is None:
        from sts2_lite.creature import Creature

        class Osty(Creature):
            owner = None        # the Necrobinder it belongs to

            def __init__(self, hp : int = 1):
                super().__init__(max_hp=hp, current_hp=hp, is_minion=True)

            @property
            def alive(self) -> bool:
                return self.current_hp > 0

            def insert_into_draw_pile(self, card):
                """PersonalHive and the like: what Osty's hits add goes to its owner's draw pile."""
                if self.owner is not None:
                    self.owner.insert_into_draw_pile(card)

            def copy(self):
                new = Osty(self.max_hp)
                new.current_hp, new.owner = self.current_hp, self.owner
                return new

        _OSTY_CLASS = Osty
    return _OSTY_CLASS(hp)


def osty_alive(player : Player) -> bool:
    """Player.IsOstyAlive."""
    osty = player.osty
    return osty is not None and osty.current_hp > 0


def summon(player : Player, amount : int):
    """OstyCmd.Summon: a living Osty gains `amount` Max HP (and as much HP); a dead or missing one comes back with `amount` HP."""
    if amount <= 0:
        return
    osty = player.osty
    if osty is not None and osty.current_hp > 0:
        osty.max_hp += amount
        osty.current_hp += amount
        return
    if osty is None:
        osty = player.osty = new_osty(amount)
        osty.owner = player
    osty.max_hp = osty.current_hp = amount
    osty.block = 0


def heal_osty(player : Player, amount : int):
    """CreatureCmd.Heal on a living Osty (a dead one is not healed)."""
    if osty_alive(player):
        osty = player.osty
        osty.current_hp = min(osty.max_hp, osty.current_hp + amount)


def hurt_osty(player : Player, amount : int) -> int:
    """HP lost by Osty; returns what was lost. NecroMastery (and the like) hear of it through `player.osty_hurt_hook`."""
    osty = player.osty
    if osty is None or osty.current_hp <= 0 or amount <= 0:
        return 0
    lost = min(amount, osty.current_hp)
    osty.current_hp -= lost
    osty.hp_loss_events += 1
    if player.osty_hurt_hook is not None:
        player.osty_hurt_hook(lost)
    return lost
