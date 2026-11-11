# Events that status handlers hook into (see STATUS_HANDLERS).
from enum import Enum, auto


class EventType(Enum):
    __hash__ = object.__hash__      # members are singletons; Enum.__hash__ is pure Python
    PLAY_PHASE_END = auto()    # player ends their turn, before anything else happens
    TURN_END_EARLY = auto()    # after the end-of-turn auto-plays, before END_TURN (BeforeSideTurnEndEarly)
    END_TURN = auto()          # player ends their turn
    PLAYER_TURN_ENDED = auto() # the hand is discarded; the enemies have not acted yet
    ENEMY_TURN_START = auto()  # the enemies are about to act (BeforeSideTurnStart for their side)
    ENEMY_TURN_END = auto()    # after every enemy has acted
    CARD_PLAYED = auto()       # args: (card,)
    CARD_EXHAUSTED = auto()    # args: (card,)
    CREATURE_KILLED = auto()   # args: (creature,); sent to every other creature's statuses
    DEATH = auto()             # sent only to the dying creature's own statuses
    BEFORE_PLAYER_TURN = auto()  # the new turn has begun but nothing has been drawn yet
    BLOCK_CLEARED = auto()     # block cleared, hand not drawn yet (AfterBlockCleared)
    PLAYER_TURN_START = auto() # after the new hand is drawn
    AUTO_PRE_PLAY = auto()     # turn setup is done, before the player can act (AfterAutoPrePlayPhaseEntered)
    BLOCK_GAINED = auto()      # args: (creature, amount)
    HP_LOST = auto()           # args: (amount,); the player lost hit points (reported after the action that did it)
    HP_CHANGED = auto()        # after any action, whether the player's hit points moved or not
    SHUFFLED = auto()          # the discard pile went into the draw pile
    HAND_EMPTIED = auto()      # the last card left the hand during the player's turn
    ETHEREAL_EXHAUSTED = auto()  # args: (count,); once, after the hand is discarded at end of turn


class HandlerTable(dict):
    """(id, event) -> handler, also indexed as by_event[event][id] so firing an event hashes one Enum, not one per pair.
    Edits keep the index in sync (tests swap handlers)."""
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.by_event = {}
        self.update(*args, **kwargs)

    def __setitem__(self, key, handler):
        super().__setitem__(key, handler)
        self.by_event.setdefault(key[1], {})[key[0]] = handler

    def __delitem__(self, key):
        super().__delitem__(key)
        self.by_event[key[1]].pop(key[0], None)

    def update(self, *args, **kwargs):
        for key, handler in dict(*args, **kwargs).items():
            self[key] = handler

    def pop(self, key, *default):
        if key in self:
            handler = self[key]
            del self[key]
            return handler
        if default:
            return default[0]
        raise KeyError(key)
