from enum import Enum, auto

class StatusId(Enum):
    STRENGTH = auto()
    WEAKNESS = auto()
    VULNERABLE = auto()
    FRAIL = auto()
    DEXTERITY = auto()


class Status:
    status_id : StatusId
    amount : int

    def __init__(self, status_id : StatusId, amount : int):
        self.status_id = status_id
        self.amount = amount

    @classmethod
    def from_dict(cls, status : dict):
        return cls(StatusId[status["id"][:-6]], status["amount"])

    @classmethod
    def deepcopy(cls, status : Status):
        return cls(status.status_id, status.amount)
