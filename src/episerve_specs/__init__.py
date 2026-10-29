"""Specifications, JSON Schemas and validators for EPISERVE platform formats."""

__version__ = "0.1.0"

from .registry import available_specs, detect_spec, load_schema, schema_url, validate  # noqa: E402
from .result import Issue, Result  # noqa: E402

__all__ = [
    "Issue",
    "Result",
    "__version__",
    "available_specs",
    "detect_spec",
    "load_schema",
    "schema_url",
    "validate",
]
