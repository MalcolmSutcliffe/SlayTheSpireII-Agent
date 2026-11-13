"""Where the project's data lives: <project root>/data/. Tests, benchmarks and the agent import their paths from here."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

ENEMIES = DATA / "enemies"             # <act>/<enemy>/<name>.json : bridge captures of enemy fights
CARDS = DATA / "cards"                 # card captures (cards/colorless/, cards/ironclad/) and card-selection screens
RELICS = DATA / "relics"
ENCHANTMENTS = DATA / "enchantments"
VERIFIER = DATA / "verifier"           # log_cases/ and mismatches/ for agents.verify and the agent tester
STATES = DATA / "states"               # whole-combat example states
SEARCH = DATA / "search"               # positions the MCTS tests search
BENCHMARKS = DATA / "benchmarks"       # <suite>/ state folders, puzzles_<suite>.json, reference_<suite>.jsonl
RUNS = DATA / "runs"                   # one folder per live agent run (agent_tester.py)
DECOMPILED = ROOT / "sts2_decompiled"
