"""Specifications, JSON Schemas and validators for EPISERVE platform formats."""

__version__ = "0.3.0"

from .registry import available_specs, detect_spec, load_schema, schema_url, validate  # noqa: E402
from .result import Issue, Result  # noqa: E402
from .specs.model_card import check_config as check_model_config  # noqa: E402
from .specs.model_card import config_defaults as model_config_defaults  # noqa: E402

__all__ = [
    "Issue",
    "Result",
    "__version__",
    "available_specs",
    "check_model_config",
    "detect_spec",
    "load_schema",
    "model_config_defaults",
    "schema_url",
    "validate",
]
