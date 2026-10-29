import copy
import json
from importlib import resources

import pytest

EXAMPLES = resources.files("episerve_specs.specs.model_card").joinpath("examples")
EXAMPLE_NAMES = sorted(p.name for p in EXAMPLES.iterdir() if p.name.endswith(".json"))


def load_example(name: str) -> dict:
    return json.loads(EXAMPLES.joinpath(name).read_text(encoding="utf-8"))


@pytest.fixture
def timesfm() -> dict:
    return copy.deepcopy(load_example("model__prediction__generic__timesfm.json"))


@pytest.fixture
def baseline() -> dict:
    return copy.deepcopy(load_example("model__prediction__grippeweb__baseline-nullmodel.json"))
