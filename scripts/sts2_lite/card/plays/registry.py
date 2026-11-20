"""CardId -> play function, merged from each pool's table."""
from __future__ import annotations
from typing import Callable

from sts2_lite.card.ids import CardId
from sts2_lite.card.plays.ironclad import IRONCLAD_PLAYS
from sts2_lite.card.plays.colorless import COLORLESS_PLAYS
from sts2_lite.card.plays.silent import SILENT_PLAYS
from sts2_lite.card.plays.regent import REGENT_PLAYS
from sts2_lite.card.plays.necrobinder import NECROBINDER_PLAYS
from sts2_lite.card.plays.defect import DEFECT_PLAYS
from sts2_lite.card.plays.ancient_event import ANCIENT_EVENT_PLAYS
from sts2_lite.card.plays.curse_status import CURSE_STATUS_PLAYS

_ALL_PLAYS = {**IRONCLAD_PLAYS, **SILENT_PLAYS, **REGENT_PLAYS, **NECROBINDER_PLAYS, **DEFECT_PLAYS, **COLORLESS_PLAYS, **ANCIENT_EVENT_PLAYS, **CURSE_STATUS_PLAYS}

# sorted by card name, so a card is easy to find
GET_CARD_FUNCTION : dict[CardId, Callable] = dict(sorted(_ALL_PLAYS.items(), key=lambda item: item[0].name))
