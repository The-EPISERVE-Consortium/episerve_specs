"""Check a model run's config.json against the parameters a model card declares."""

from __future__ import annotations

from jsonschema import Draft202012Validator, FormatChecker

from ...result import Issue


def _parameters(card_or_parameters: dict) -> dict:
    if "episerve:parameters" in card_or_parameters:
        return card_or_parameters["episerve:parameters"]
    return card_or_parameters


def check_config(card_or_parameters: dict, config) -> list[Issue]:
    """Return one error per rule ``config`` breaks.

    ``card_or_parameters`` is a whole model card or only its ``episerve:parameters``.
    The ``rules`` of the parameters are text and are not checked.
    """
    validator = Draft202012Validator(_parameters(card_or_parameters), format_checker=FormatChecker())
    return [
        Issue("error", "/".join(str(p) for p in e.absolute_path), e.message)
        for e in sorted(validator.iter_errors(config), key=lambda e: [str(p) for p in e.absolute_path])
    ]


def config_defaults(card_or_parameters: dict) -> dict:
    """The declared defaults, by parameter name (parameters without a default are left out)."""
    props = _parameters(card_or_parameters).get("properties") or {}
    return {name: spec["default"] for name, spec in props.items() if isinstance(spec, dict) and "default" in spec}
