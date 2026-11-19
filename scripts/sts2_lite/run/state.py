"""`RunState`: one object for everything about a run that is not inside a fight.

It holds what a player can see (hit points, gold, deck, relics, potions, where they are, what they have been through) and, apart in `hidden`, what the game
knows and the player does not (the rarity offset of card rewards, the encounters still to come). The agent is only ever given `public()`; the simulator
keeps the full state. The first fields are those the events always used, so events play on a RunState as they did on the old `RunSnapshot`."""
from __future__ import annotations

import copy
from sts2_lite.datacopy import deepcopy_data
from dataclasses import dataclass, field

from sts2_lite.relic import RelicId
from sts2_lite.map import ActMap, UnknownRoomOdds
from sts2_lite.rewards.odds import BASE_RARITY_OFFSET

ASCENDERS_BANE_ASCENSION = 5
TIGHT_BELT_ASCENSION = 4
WEARY_TRAVELER_ASCENSION = 2        # start at 80% of max hit points
WEARY_TRAVELER_SHARE = 0.8


@dataclass
class Hidden:
    """What the player cannot see. Present only in the simulator's state; an agent that models it does so itself, from what it has seen."""
    rarity_offset : float = BASE_RARITY_OFFSET      # CardRarityOdds.current_value
    rooms : object | None = None                    # encounters.Rooms of the current act: the fights to come, in order
    normal_fought : int = 0                         # how many of rooms.normal have been used
    elite_fought : int = 0
    unknown_odds : UnknownRoomOdds = field(default_factory=UnknownRoomOdds)      # what a "?" will turn into
    potion_odds : float = 0.4                       # PotionRewardOdds.CurrentValue
    shop_removals : int = 0                         # ExtraFields.CardShopRemovalsUsed: card removals bought at merchants
    events : list | None = None                     # the act's event pool, shuffled when the act began (ActModel.GenerateRooms): RoomSet.events
    events_visited : int = 0                        # RoomSet.eventsVisited: the next event is events[events_visited % len]
    spoils_point : tuple | None = None              # SpoilsMap: the (col, row) of the first treasure room of act 2, where the quest pays out
    relic_bag : object | None = None                # relic.bag.RelicGrabBag; None outside the sandbox (relics the game would draw are then only counted)


@dataclass
class Visit:
    """One room entered: `room` is Monster / Elite / Boss / Shop / RestSite / Treasure / Event / Ancient, `id` the encounter or event."""
    act : int
    floor : int
    room : str
    id : str | None = None


@dataclass
class RunState:
    hp : int
    max_hp : int
    gold : int
    deck : list[dict]
    relics : list[dict] = field(default_factory=list)       # {"id": ..., "name": ...}; ids the combat sim does not know are kept too
    potions : list[dict] = field(default_factory=list)
    potion_slots : int = 3
    act : int = 1
    floor : int = 1
    pending_relics : int = 0        # relics an event gave whose kind is chosen by the game's relic bag (not modelled): a count, not an id
    relic_state : dict = field(default_factory=dict)      # what a relic counts: {relic_id: {...}} (combats seen, triggered, bought, ...)
    offers : list = field(default_factory=list)     # reward screens a relic or event queued: {'kind': 'cards', 'cards': [...]} | {'kind': 'potion'} | {'kind': 'relic'}; the run's player takes them
    pending_fight : str | None = None   # the fight an event option started (not played by the event)
    pending_fight_args : dict = field(default_factory=dict)     # how it is played: variant, turn_limit, extra (reward kinds on top of the usual ones), on_win (what winning does)
    dead : bool = False
    # --- the rest of the run
    ascension : int = 0
    character : str = "IRONCLAD"
    act_id : str | None = None          # OVERGROWTH / UNDERDOCKS / HIVE / GLORY
    boss : str | None = None            # the act's boss: the map shows it
    history : list[Visit] = field(default_factory=list)
    seen_events : list[str] = field(default_factory=list)
    map : ActMap | None = None          # the act's map: the player sees all of it
    position : tuple[int, int] | None = None        # (col, row) of the room the player is in
    hidden : Hidden | None = None

    def copy(self) -> "RunState":
        return copy.deepcopy(self)

    def public(self) -> "RunState":
        """What an agent may see: a copy with no hidden part."""
        out = self.copy()
        out.hidden = None
        return out

    @classmethod
    def from_player(cls, player : dict, deck : list[dict], act : int = 1, floor : int = 1, ascension : int = 0) -> "RunState":
        """From a bridge `player` dict plus the deck (a real run: nothing hidden is known)."""
        return cls(hp=player["hp"], max_hp=player["max_hp"], gold=player.get("gold", 0), deck=deepcopy_data(deck), relics=deepcopy_data(player.get("relics", [])),
                   potions=deepcopy_data([p for p in player.get("potions", []) if p]), potion_slots=player.get("potion_slots", 3), act=act, floor=floor, ascension=ascension)

    def sim_relics(self) -> list[dict]:
        """The relics the combat sim knows (the rest cannot change a fight it plays)."""
        return [r for r in self.relics if str(r.get("id", "")) in RelicId.__members__]

    def has_relic(self, relic_id : str) -> bool:
        return any(r.get("id") == relic_id and not r.get("melted") for r in self.relics)

    def visit(self, room : str, id : str | None = None):
        self.history.append(Visit(self.act, self.floor, room, id))
        if room == "Event" and id is not None:
            self.seen_events.append(id)

    def player_dict(self) -> dict:
        """The bridge's `player` shape (out of combat) for the part the agent reads."""
        return {"hp": self.hp, "max_hp": self.max_hp, "gold": self.gold, "relics": deepcopy_data(self.relics), "potions": deepcopy_data(self.potions),
                "potion_slots": self.potion_slots}


def new_run(ascension : int = 0, character : str = "IRONCLAD") -> RunState:
    """A fresh run at its start (before Neow and before the first act is drawn): the starter deck, relic, hit points and gold, with the ascension's changes."""
    from sts2_lite.character import character as character_info
    from sts2_lite.event.run import card_entry
    start = character_info(character)
    character = start.name
    deck = [card_entry(c) for c in start.deck]
    if ascension >= ASCENDERS_BANE_ASCENSION:
        deck.append(card_entry("ASCENDERS_BANE"))
    slots = start.potion_slots - (1 if ascension >= TIGHT_BELT_ASCENSION else 0)
    hp = int(start.hp * WEARY_TRAVELER_SHARE) if ascension >= WEARY_TRAVELER_ASCENSION else start.hp
    return RunState(hp=hp, max_hp=start.hp, gold=start.gold, deck=deck, relics=[{"id": start.relic, "name": start.relic_name}],
                    potion_slots=slots, act=0, floor=0, ascension=ascension, character=character, hidden=Hidden())
