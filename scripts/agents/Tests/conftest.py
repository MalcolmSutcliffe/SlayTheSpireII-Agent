import sys
from pathlib import Path

# the tests import sts2_lite and agents from scripts/; `pytest` (unlike `python -m pytest`) and xdist workers do not put it on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: full searches that take 10+ seconds each; skip them in quick runs with -m 'not slow'")
