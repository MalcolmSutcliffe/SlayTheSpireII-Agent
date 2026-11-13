"""How each action is sent to the game: the cli-anything-sts2 command and the action fields it takes as arguments.
An action name missing here is refused loudly: an agent cannot ask for something the runner does not know how to send."""

# action name -> (command, fields of the action that follow it)
COMMANDS = {
    "choose_map_node": ("choose-map", ("index",)),
    "choose_event_option": ("event", ("index",)),
    "advance_dialogue": ("advance-dialogue", ()),
    "choose_rest_option": ("rest", ("index",)),
    "shop_purchase": ("shop-buy", ("index",)),
    "claim_reward": ("claim-reward", ("index",)),
    "select_card_reward": ("pick-card-reward", ("card_index",)),
    "skip_card_reward": ("skip-card-reward", ()),
    "proceed": ("proceed", ()),
    "select_card": ("select-card", ("index",)),
    "confirm_selection": ("confirm-selection", ()),
    "cancel_selection": ("cancel-selection", ()),
    "select_relic": ("select-relic", ("index",)),
    "skip_relic_selection": ("skip-relic-selection", ()),
    "claim_treasure_relic": ("claim-treasure-relic", ("index",)),
}

def command_for(action : dict) -> list[str]:
    name = action["action"]
    if name not in COMMANDS:
        raise ValueError(f"no executor for action {name!r}")
    command, fields = COMMANDS[name]
    return [command, *(str(action[field]) for field in fields)]

def execute(client, action : dict):
    """Send one non-combat action through the GameClient."""
    return client.command(*command_for(action))
