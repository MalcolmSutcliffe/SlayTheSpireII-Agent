import sys
from pathlib import Path

# the tests import agent_runner, sts2_lite and agents from scripts/; `pytest` (unlike `python -m pytest`) and xdist workers do not put it on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
