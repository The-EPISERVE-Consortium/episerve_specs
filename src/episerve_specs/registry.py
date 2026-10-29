"""Finds the specs in ``episerve_specs.specs`` and validates documents against them.

Each spec is a subpackage of ``episerve_specs.specs`` that defines

* ``SPEC_ID`` -- the spec's name in URLs and on the command line, e.g. ``model-card``
* ``CHECKS`` -- ``{version: function}``; the function takes the document and returns the
  extra issues JSON Schema cannot express (it must cope with malformed documents)

and holds one ``v<N>.schema.json`` per version next to its ``__init__.py``.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import re
from functools import lru_cache
from importlib import resources
from types import ModuleType

from jsonschema import Draft202012Validator, FormatChecker

from . import specs as _specs_pkg
from .result import Issue, Result

SCHEMA_BASE_URL = "https://api.episerve.zib.de/schemas"
_CONFORMS_TO = re.compile(re.escape(SCHEMA_BASE_URL) + r"/([a-z0-9-]+)/v(\d+)\.json$")


def schema_url(spec: str, version: str) -> str:
    """The URL a document names in ``conformsTo`` to say it follows this spec version."""
    return f"{SCHEMA_BASE_URL}/{spec}/v{version}.json"


@lru_cache(maxsize=None)
def _spec_modules() -> dict[str, ModuleType]:
    modules = {}
    for info in pkgutil.iter_modules(_specs_pkg.__path__):
        module = importlib.import_module(f"{_specs_pkg.__name__}.{info.name}")
        modules[module.SPEC_ID] = module
    return modules


def available_specs() -> dict[str, list[str]]:
    """Every spec and its versions, oldest first, e.g. ``{"model-card": ["1"]}``."""
    return {spec: sorted(m.CHECKS, key=int) for spec, m in sorted(_spec_modules().items())}


def _module(spec: str) -> ModuleType:
    try:
        return _spec_modules()[spec]
    except KeyError:
        known = ", ".join(sorted(_spec_modules())) or "none"
        raise ValueError(f"unknown spec '{spec}' (known: {known})") from None


@lru_cache(maxsize=None)
def load_schema(spec: str, version: str) -> dict:
    """The JSON Schema of one spec version."""
    module = _module(spec)
    if version not in module.CHECKS:
        raise ValueError(f"spec '{spec}' has no version {version} (known: {', '.join(available_specs()[spec])})")
    text = resources.files(module).joinpath(f"v{version}.schema.json").read_text(encoding="utf-8")
    return json.loads(text)


def detect_spec(document: object) -> tuple[str, str] | None:
    """``(spec, version)`` from the document's ``conformsTo``, or None if it names no EPISERVE spec."""
    if not isinstance(document, dict):
        return None
    conforms = document.get("conformsTo")
    for value in conforms if isinstance(conforms, list) else [conforms]:
        url = value.get("@id") if isinstance(value, dict) else value
        if isinstance(url, str):
            match = _CONFORMS_TO.match(url.strip())
            if match and match.group(1) in _spec_modules():
                return match.group(1), match.group(2)
    return None


def _path(parts) -> str:
    return "/".join(str(p) for p in parts)


def validate(document: object, spec: str | None = None, version: str | None = None) -> Result:
    """Validate a parsed document.

    Args:
        document: the parsed JSON document.
        spec: the spec to check against; taken from ``conformsTo`` when omitted.
        version: the spec version; taken from ``conformsTo`` when it names this spec, else the newest.

    Raises:
        ValueError: ``spec`` or ``version`` is unknown.
    """
    detected = detect_spec(document)
    if spec is None:
        if detected is None:
            return Result(None, None, [Issue(
                "error", "conformsTo",
                f"names no EPISERVE spec; expected e.g. {schema_url('model-card', '1')}",
            )])
        spec, detected_version = detected
        version = version or detected_version
    elif version is None:
        _module(spec)  # raises for an unknown spec
        version = detected[1] if detected and detected[0] == spec else available_specs()[spec][-1]

    schema = load_schema(spec, version)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    issues = [
        Issue("error", _path(e.absolute_path), e.message)
        for e in sorted(validator.iter_errors(document), key=lambda e: _path(e.absolute_path))
    ]
    if isinstance(document, dict):
        issues += _module(spec).CHECKS[version](document)
    return Result(spec, version, issues)
