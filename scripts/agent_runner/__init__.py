"""Runs the agent against the live game.

runner.py         AgentRun: polls the game and routes each state (run with `python -m agent_runner` from scripts/)
game_client.py    GameClient: everything that reads from or sends to the game through cli-anything-sts2
combat_session.py CombatSession: the fight in progress, the sim that shadows it, and the checks of the sim against the game
combat_logs.py    the decision log, fight summaries, captures and mismatch records of a combat run

Nothing is imported here on purpose: runner.py pulls in the agents, which the tests replace before importing it.
"""
