"""Run events of the game as small state machines on a RunSnapshot (hp, gold, deck, relics, potions)."""
from sts2_lite.event.core import CardPicker, Ctx, EventDef, EventSession, Option
from sts2_lite.event.events import EVENTS, available, modelled
from sts2_lite.event.run import RunSnapshot, card_entry
