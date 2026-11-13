from agents.base_agent import BaseAgent
from agents.my_agent import MyAgent

from data_paths import RUNS
from .game_client import GameClient
from .run_manager import DEFAULT_LOG, RunManager

import argparse
import re
from pathlib import Path

RUNS_DIR = RUNS

def run_paths(run : str, decisions : bool = False, fights : bool = False, states : bool = False, captures : bool = False,
              append : bool = False, runs_dir : Path | None = None) -> dict:
    """Where one run keeps its data: data/runs/<run>/ holds mismatches.jsonl always, and decisions.jsonl, fights.jsonl, states/ and
    captures/ for the aspects asked for. A directory that already has files in it is refused unless `append` (a stopped run
    that carries on): the numbers of the saved states would otherwise start again at 1 and overwrite the old ones.
    Returns the keyword arguments of run_agent."""
    runs_dir = runs_dir or RUNS_DIR
    if not run or Path(run).name != run or run in (".", ".."):
        raise ValueError(f"a run is a folder name inside {runs_dir.name}/, not a path: {run!r}")
    directory = runs_dir / run
    if directory.exists() and any(directory.iterdir()) and not append:
        raise FileExistsError(f"{directory} already has data; pick another run name, or add --append to carry on in it")
    directory.mkdir(parents=True, exist_ok=True)
    first = 0
    if append:
        numbers = [int(m.group(1)) for p in (directory / "states").glob("decision_*.json") if (m := re.fullmatch(r"decision_(\d+)\.json", p.name))]
        log = directory / "decisions.jsonl"
        first = max(numbers + [sum(1 for _ in open(log)) if log.exists() else 0])
    return {
        "log_path": str(directory / "mismatches.jsonl"),
        "decision_log": str(directory / "decisions.jsonl") if decisions else None,
        "fight_log": str(directory / "fights.jsonl") if fights else None,
        "state_dir": str(directory / "states") if states else None,
        "capture_dir": str(directory / "captures") if captures else None,
        "first_decision": first,
    }


def run_agent(agent : BaseAgent, step : bool = False, verify : bool = True, log_path : str = DEFAULT_LOG, capture_dir : str | None = None,
              decision_log : str | None = None, state_dir : str | None = None, fight_log : str | None = None, first_decision : int = 0,
              client : GameClient | None = None):
    RunManager(agent, step, verify, log_path, capture_dir, decision_log, state_dir, fight_log, first_decision, client).run()

def main(argv : list[str] | None = None):
    parser = argparse.ArgumentParser(prog="python -m agent_runner", description="Let the agent play every combat; compare the sim with the game after each action. "
                                     "Name a run to keep its data in data/runs/<run>/ (mismatches.jsonl is always written there).")
    parser.add_argument("run", nargs="?", default=None, help="folder name for this run's data inside data/runs/, e.g. run3-a9")
    parser.add_argument("--decisions", action="store_true", help="save decisions.jsonl: every move with its sims, time, and each move's visits and mean reward")
    parser.add_argument("--fights", action="store_true", help="save fights.jsonl: one line per fight with enemies, HP at the start and end, rounds, outcome, search totals and the deepest tree")
    parser.add_argument("--states", action="store_true", help="save states/decision_NNNNN.json: the game state behind every decision (numbers match --decisions)")
    parser.add_argument("--captures", action="store_true", help="save captures/: the state at the start of every turn (benchmark material)")
    parser.add_argument("--all", action="store_true", help="save decisions, fights, states and captures")
    parser.add_argument("--append", action="store_true", help="carry on in a run folder that already has data (decision numbers continue)")
    parser.add_argument("--step", action="store_true", help="wait for Enter before every action")
    parser.add_argument("--no-verify", action="store_true", help="do not compare the sim with the game")
    args = parser.parse_args(argv)
    wanted = {"decisions": args.decisions or args.all, "fights": args.fights or args.all,
              "states": args.states or args.all, "captures": args.captures or args.all}
    if args.run is None and (any(wanted.values()) or args.append):
        parser.error("name the run (e.g. run3-a9) to save anything")
    if args.run is None:
        kwargs = {"log_path": DEFAULT_LOG}
    else:
        try:
            kwargs = run_paths(args.run, append=args.append, **wanted)
        except (ValueError, FileExistsError) as error:
            parser.error(str(error))
        print(f"saving to {RUNS_DIR / args.run}: mismatches" + "".join(f", {name}" for name, on in wanted.items() if on))
    agent = MyAgent()
    run_agent(agent, step=args.step, verify=not args.no_verify, **kwargs)

if __name__ == "__main__":
    main()
