# Events that status handlers hook into (see STATUS_HANDLERS).
from enum import Enum, auto


class EventType(Enum):
    END_TURN = auto()          # player ends their turn
    ENEMY_TURN_END = auto()    # after every enemy has acted
    CARD_PLAYED = auto()       # args: (card,)
    CARD_EXHAUSTED = auto()    # args: (card,)
    CREATURE_KILLED = auto()
