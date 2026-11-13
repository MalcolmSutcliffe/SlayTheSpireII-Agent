"""Runs the agent against the live game.

runner.py         command line: builds a RunManager and runs it (`python -m agent_runner` from scripts/)
run_manager.py    RunManager: owns one whole run; routes each state to the combat session or to an out-of-combat Decision
decision_builders.py  a screen's state -> Decision (the legal Options on it)
executors.py      each action name -> the cli-anything-sts2 command that sends it
game_client.py    GameClient: everything that reads from or sends to the game through cli-anything-sts2
combat_session.py CombatSession: the fight in progress, the sim that shadows it, and the checks of the sim against the game
combat_logs.py    the decision log, fight summaries, captures and mismatch records of a combat run

Nothing is imported here on purpose: runner.py pulls in the agents, which the tests replace before importing it.
"""
