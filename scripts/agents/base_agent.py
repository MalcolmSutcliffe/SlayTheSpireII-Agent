from sts2_env.run.run_manager import RunManager
    

## Base class for an agent. Recieves a game state as an input and returns an action.
class BaseAgent:
    name = "Barkus"

    def __init__(self):
        pass

    def get_action(self, mgr : RunManager):
        actions = mgr.get_available_actions()
        return actions[0]