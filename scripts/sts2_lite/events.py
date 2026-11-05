# Events that status handlers hook into (see STATUS_HANDLERS).
from enum import Enum, auto


class EventType(Enum):
    PLAY_PHASE_END = auto()    # player ends their turn, before anything else happens
    END_TURN = auto()          # player ends their turn
    PLAYER_TURN_ENDED = auto() # the hand is discarded; the enemies have not acted yet
    ENEMY_TURN_END = auto()    # after every enemy has acted
    CARD_PLAYED = auto()       # args: (card,)
    CARD_EXHAUSTED = auto()    # args: (card,)
    CREATURE_KILLED = auto()   # args: (creature,); sent to every other creature's statuses
    DEATH = auto()             # sent only to the dying creature's own statuses
    BEFORE_PLAYER_TURN = auto()  # the new turn has begun but nothing has been drawn yet
    PLAYER_TURN_START = auto() # after the new hand is drawn
    BLOCK_GAINED = auto()      # args: (creature, amount)
    HP_LOST = auto()           # args: (amount,); the player lost hit points (reported after the action that did it)
    HP_CHANGED = auto()        # after any action, whether the player's hit points moved or not
    SHUFFLED = auto()          # the discard pile went into the draw pile
    HAND_EMPTIED = auto()      # the last card left the hand during the player's turn
    ETHEREAL_EXHAUSTED = auto()  # args: (count,); once, after the hand is discarded at end of turn
