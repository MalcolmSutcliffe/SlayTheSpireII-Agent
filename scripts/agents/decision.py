"""What the agent is asked outside of combat: a Decision (the screen the game is on) with the list of legal Options on it.
The agent returns one of the options; the runner sends its `action` to the game. Combat has its own path (CombatState in, action out)."""
from dataclasses import dataclass, field

# decision kinds, one per screen
MAP = "map"
CARD_REWARD = "card_reward"
REWARDS = "rewards"
REST = "rest"
SHOP = "shop"
EVENT = "event"
CARD_SELECT = "card_select"
RELIC = "relic"
TREASURE = "treasure"

KINDS = (MAP, CARD_REWARD, REWARDS, REST, SHOP, EVENT, CARD_SELECT, RELIC, TREASURE)


@dataclass(frozen=True)
class Option:
    """One legal thing to do on a screen. `action` is what is sent to the game ({"action": "choose_map_node", "index": 2});
    `data` is the screen's entry behind it (a map node, a shop item, a card) for an agent that wants to look at it."""
    label: str
    action: dict
    data: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def name(self) -> str:
        return self.action["action"]


@dataclass
class Decision:
    kind: str
    state: dict                 # the normalized state of the screen: its "player" holds hp, gold, relics, potions and the deck
    options: list[Option]

    @property
    def player(self) -> dict:
        return self.state.get("player") or {}

    def options_named(self, name : str) -> list[Option]:
        return [o for o in self.options if o.name == name]
