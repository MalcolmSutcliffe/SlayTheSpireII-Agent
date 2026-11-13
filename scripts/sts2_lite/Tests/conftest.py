import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))      # `pytest` and xdist workers do not put scripts/ on the path

from sts2_lite import rng


@pytest.fixture(autouse=True)
def seeded_rng():
    rng.seed(0)
