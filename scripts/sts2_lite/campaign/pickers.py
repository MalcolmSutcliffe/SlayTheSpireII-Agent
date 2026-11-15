"""Card choices inside an event or at a rest site, put to the agent as the bridge's card-select screens."""
from __future__ import annotations

from sts2_lite.event import CardPicker

from sts2_lite.campaign import screens


class AgentPicker(CardPicker):
    """`CardPicker` whose answers come from the agent: one `card_select` screen per choice, with the cards `allowed` and a confirm once enough are picked."""
    def __init__(self, simulator):
        self.sim = simulator

    def select(self, screen_type : str, deck : list[dict], n : int, allowed : list[int], cancel : bool = False) -> list[int]:
        n = min(n, len(allowed))
        if n <= 0:
            return []
        chosen : list[int] = []
        while True:
            if len(chosen) > n:             # an agent that keeps picking past the limit: the first n stand
                return chosen[:n]
            cards = [deck[i] for i in allowed]
            picked = [allowed.index(i) for i in chosen]
            state = screens.card_select(self.sim.run_state, screen_type, cards, picked, len(chosen) == n, cancel)
            option = self.sim.ask(state)
            action = option.action
            if action["action"] == "confirm_selection":
                return chosen
            if action["action"] == "cancel_selection":
                return []
            chosen.append(allowed[action["index"]])         # a card's index on the screen is its place in `allowed`, whatever was picked before

    def remove(self, deck, n, allowed, cancel : bool = False):
        return self.select("remove", deck, n, allowed, cancel)

    def upgrade(self, deck, n, allowed, cancel : bool = False):
        return self.select("upgrade", deck, n, allowed, cancel)

    def transform(self, deck, n, allowed):
        return self.select("transform", deck, n, allowed)

    def enchant(self, deck, allowed, n : int = 1):
        return self.select("enchant", deck, n, allowed)

    def take(self, offered, n):
        """The cards of an event's reward: the card reward screen, one pick at a time (a skip ends it)."""
        left = list(range(len(offered)))
        taken : list[int] = []
        while left and len(taken) < n:
            option = self.sim.ask(screens.card_reward(self.sim.run_state, [offered[i] for i in left]))
            if option.action["action"] != "select_card_reward":
                break
            taken.append(left.pop(option.action["card_index"]))
        return taken
