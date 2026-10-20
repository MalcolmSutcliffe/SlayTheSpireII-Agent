from sts2_lite.combat import CombatState, Combat

## Base class for an agent. Recieves a game state as an input and returns an action.
class BaseAgent:
    name = "Barkus"

    def __init__(self):
        pass

    def get_action(self, combat_state : CombatState):
        c = Combat(combat_state)
        actions = c.get_available_actions()
        return actions[0]