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


# potions the game lets be drunk outside a fight (PotionUsage.AnyTime): the screens list a "use" for these only; any potion can be thrown away
USABLE_OUT_OF_COMBAT = ("FRUIT_JUICE", "BLOOD_POTION", "FOUL_POTION")

def potion_option(verb : str, entry : dict) -> Option:
    """`verb` "use" or "discard" for the potion of `entry` (a belt entry: its id, name and slot). The screens list these (agent_runner/decision_builders.py) and agents/potion_cycle.py chooses them."""
    name = entry.get("name") or entry.get("id")
    return Option("%s %s" % ("drink" if verb == "use" else "discard", name), {"action": "%s_potion" % verb, "slot": entry["slot"], "potion_id": entry.get("id")}, entry)

def potion_options(state : dict) -> list[Option]:
    """The potion actions a screen offers out of combat, one per potion on the belt."""
    belt = [p for p in (state.get("player") or {}).get("potions") or [] if p and p.get("slot") is not None]
    return ([potion_option("use", p) for p in belt if p.get("id") in USABLE_OUT_OF_COMBAT] + [potion_option("discard", p) for p in belt])


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
