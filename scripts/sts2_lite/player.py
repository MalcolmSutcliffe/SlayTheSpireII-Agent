from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sts2_lite.combat import Player

from sts2_lite import rng
from sts2_lite.creature import Creature
from sts2_lite.card import Card
from sts2_lite.status import StatusInstance, StatusId

class Player(Creature):
    hand : list[Card]
    draw_pile : list[Card]
    discard_pile : list[Card]
    exhaust_pile : list[Card]
    cards_drawn : int       # running total; compare before and after an action

    def __init__(self):
        super().__init__()
        self.hand = []
        self.draw_pile = []
        self.discard_pile = []
        self.exhaust_pile = []
        self.cards_drawn = 0

    @classmethod
    def from_dict(cls, player : dict):
        pl = cls()
        pl.max_hp = player["max_hp"]
        pl.current_hp = player["hp"]
        pl.block = player["block"]
        pl.is_minion = False
        pl.status = {}
        for s in player["status"]:
            pl.status[StatusId[s["id"][:-6]]] = StatusInstance.from_dict(s)
        pl.hand = []
        for card in player["hand"]:
            pl.hand.append(Card.from_dict(card))
        pl.draw_pile = []
        for card in player["draw_pile"]:
            pl.draw_pile.append(Card.from_dict(card))
        pl.discard_pile = []
        for card in player["discard_pile"]:
            pl.discard_pile.append(Card.from_dict(card))
        pl.exhaust_pile = [Card.from_dict(card) for card in player.get("exhaust_pile", [])]
        return pl

    @classmethod
    def deepcopy(cls, player : Player) -> Player:
        new_pl = cls()
        new_pl.max_hp = player.max_hp
        new_pl.current_hp = player.current_hp
        new_pl.block = player.block
        new_pl.is_minion = False
        new_pl.status = {}
        for s in player.status.values():
            new_pl.status[s.status_id] = StatusInstance.deepcopy(s)
        new_pl.hand = []
        for card in player.hand:
            new_pl.hand.append(card)
        new_pl.draw_pile = []
        for card in player.draw_pile:
            new_pl.draw_pile.append(card)
        new_pl.discard_pile = []
        for card in player.discard_pile:
            new_pl.discard_pile.append(card)
        new_pl.exhaust_pile = list(player.exhaust_pile)
        return new_pl
    
    def turn_start(self):
        super().turn_start()
        self.draw_cards(5)

        if StatusId.CRIMSON_MANTLE in self.status:
            self.apply_block(self.status[StatusId.CRIMSON_MANTLE].amount)
            self.lose_hp(1)
    
    def draw_cards(self, num_cards : int):
        for i in range(num_cards):
            self.draw_card()

    def draw_card(self):
        if len(self.hand) >= 10:
            return
        if len(self.draw_pile) == 0:
            self.shuffle_discard_into_draw()
        if len(self.draw_pile) == 0:
            return
        self.hand.append(self.draw_pile.pop())
        self.cards_drawn += 1

    def shuffle_draw_pile(self):
        rng.shuffle(self.draw_pile)

    def shuffle_discard_into_draw(self):
        if not self.discard_pile:
            return
        self.draw_pile.extend(self.discard_pile)
        self.discard_pile = []
        self.shuffle_draw_pile()

    def exhaust_card(self, card :Card):
        # the card being played is in none of the piles
        for pile in (self.hand, self.draw_pile, self.discard_pile):
            if card in pile:
                pile.remove(card)
                break
        self.exhaust_pile.append(card)

    def readable(self) -> str:
        output = ""
        output += super().readable()
        output += "\nHand : \n"
        for card in self.hand:
            output += str(card.card_id) + "\n"
        # output += "Draw : \n"
        # for card in self.draw_pile:
        #     output += str(card.card_id) + "\n"
        # output += "Discard : \n"
        # for card in self.discard_pile:
        #     output += str(card.card_id) + "\n"
        return output