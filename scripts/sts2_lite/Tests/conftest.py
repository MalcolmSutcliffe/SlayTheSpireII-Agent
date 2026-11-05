import pytest

from sts2_lite import rng


@pytest.fixture(autouse=True)
def seeded_rng():
    rng.seed(0)
