import random

from sts2_lite.creature import Creature
from sts2_lite.card import Card
from sts2_lite.status import Status, StatusId

class Player(Creature):
    hand : list[Card] = []
    draw_pile : list[Card] = []
    discard_pile : list[Card] = []

    def __init__(self):
        super().__init__()

    @classmethod
    def from_dict(cls, player : dict):
        pl = cls()
        pl.max_hp = player["max_hp"]
        pl.current_hp = player["hp"]
        pl.block = player["block"]
        pl.is_minion = False
        pl.status = {}
        for s in player["status"]:
            pl.status[StatusId[s["id"][:-6]]] = Status.from_dict(s)
        pl.hand = []
        for card in player["hand"]:
            pl.hand.append(Card.from_dict(card))
        pl.draw_pile = []
        for card in player["draw_pile"]:
            pl.draw_pile.append(Card.from_dict(card))
        pl.discard_pile = []
        for card in player["discard_pile"]:
            pl.discard_pile.append(Card.from_dict(card))
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
            new_pl.status[s.status_id] = Status.deepcopy(s)
        new_pl.hand = []
        for card in player.hand:
            new_pl.hand.append(card)
        new_pl.draw_pile = []
        for card in player.draw_pile:
            new_pl.draw_pile.append(card)
        new_pl.discard_pile = []
        for card in player.discard_pile:
            new_pl.discard_pile.append(card)
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

    def shuffle_discard_into_draw(self):
        self.draw_pile.extend(self.discard_pile)
        random.shuffle(self.draw_pile)

    def exhaust_card(self, card :Card):
        if card in self.hand:
            self.hand.remove(card)
            return
        if card in self.draw_pile:
            self.draw_pile.remove(card)
            return
        if card in self.discard_pile:
            self.discard_pile.remove(card)
            return

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