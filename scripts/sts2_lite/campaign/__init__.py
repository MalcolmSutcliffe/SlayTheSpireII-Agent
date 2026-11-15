"""A campaign simulator: plays whole runs for an agent. The engine (sts2_lite) is the game, `RunSimulator` is the loop around it.

    result = RunSimulator(agent, seed=1, ascension=5).run()

The agent sees what it would see through the bridge (the same screens, options and actions as `agent_runner`) and a fight with the order of its
draw pile hidden. What really happens (rewards, shuffles, events, the map) comes from `GameRng`; the agent's own look-ahead from `SearchRng`."""
from sts2_lite.campaign.simulator import RunSimulator, RunResult
