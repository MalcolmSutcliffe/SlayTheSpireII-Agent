# Events that status handlers hook into (see STATUS_HANDLERS).
from enum import Enum, auto


class EventType(Enum):
    PLAY_PHASE_END = auto()    # player ends their turn, before anything else happens
    END_TURN = auto()          # player ends their turn
    ENEMY_TURN_END = auto()    # after every enemy has acted
    CARD_PLAYED = auto()       # args: (card,)
    CARD_EXHAUSTED = auto()    # args: (card,)
    CREATURE_KILLED = auto()   # args: (creature,); sent to every other creature's statuses
    DEATH = auto()             # sent only to the dying creature's own statuses
    BEFORE_PLAYER_TURN = auto()  # the new turn has begun but nothing has been drawn yet
    PLAYER_TURN_START = auto() # after the new hand is drawn
    BLOCK_GAINED = auto()      # args: (creature, amount)
    ETHEREAL_EXHAUSTED = auto()  # args: (count,); once, after the hand is discarded at end of turn
