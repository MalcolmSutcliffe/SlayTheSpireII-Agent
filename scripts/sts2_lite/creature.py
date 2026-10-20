from sts2_lite.status import Status, StatusId

class Creature:
    max_hp : int
    current_hp : int
    block : int
    status : dict[StatusId, Status] = {}
    is_minion : bool

    def __init__(self, max_hp=1, current_hp=1, block=0, status = {}, is_minion=False):
        self.max_hp=max_hp
        self.current_hp=current_hp
        self.block=block
        self.status=status
        self.is_minion=is_minion

    def apply_damage(self, damage: int):
        if self.block > 0:
            if self.block >= damage:
                self.block -= damage
                return
            else:
                damage -= self.block
                self.block = 0
        self.current_hp -= damage
        if self.current_hp <= 0:
            self.die()

    def apply_block(self, block: int):
        self.block += block

    def apply_status(self, status: StatusId, amount : int):
        if status in self.status:
            self.status[status].amount += amount
        else:
            self.status[status] = Status(status, amount)

    def die(self):
        return

    def readable(self) -> str:
        output = ""
        output += "max_hp : " + str(self.max_hp) + "\n"
        output += "current_hp : " + str(self.current_hp) + "\n"
        output += "block : " + str(self.block) + "\n"
        if len(self.status.keys()) > 0:
            output += "status : \n"
            for s in self.status.values():
                output += str(s.status_id) + " " + str(s.amount)
        return output