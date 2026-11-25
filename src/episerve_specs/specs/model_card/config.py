"""Check a model run's config.json against the parameters a model card declares."""

from __future__ import annotations

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from referencing import Registry
from referencing.exceptions import Unresolvable

from ...result import Issue


class InvalidParameterSchema(ValueError):
    """The model's declared parameter schema cannot be used to validate a config."""


def _parameters(card_or_parameters: object) -> object:
    if isinstance(card_or_parameters, dict):
        return card_or_parameters.get("episerve:parameters", card_or_parameters)
    return card_or_parameters


def parameter_validator(parameters: object) -> Draft202012Validator:
    if not isinstance(parameters, dict):
        raise InvalidParameterSchema("must be a JSON Schema object")
    try:
        Draft202012Validator.check_schema(parameters)
    except SchemaError as exc:
        raise InvalidParameterSchema(f"is not a valid JSON Schema: {exc.message}") from exc
    return Draft202012Validator(parameters, format_checker=FormatChecker(), registry=Registry())


def check_config(card_or_parameters: object, config) -> list[Issue]:
    """Return one error per rule ``config`` breaks.

    ``card_or_parameters`` is a whole model card or only its ``episerve:parameters``.
    The ``rules`` of the parameters are text and are not checked.
    Raises ``InvalidParameterSchema`` if the declaration cannot be used.
    """
    validator = parameter_validator(_parameters(card_or_parameters))
    try:
        errors = sorted(validator.iter_errors(config), key=lambda e: [str(p) for p in e.absolute_path])
    except Unresolvable as exc:
        raise InvalidParameterSchema("contains an unresolved schema reference") from exc
    return [Issue("error", "/".join(str(p) for p in e.absolute_path), e.message) for e in errors]


def config_defaults(card_or_parameters: object) -> dict:
    """The declared defaults, by parameter name (parameters without a default are left out)."""
    parameters = _parameters(card_or_parameters)
    props = parameters.get("properties") if isinstance(parameters, dict) else None
    if not isinstance(props, dict):
        return {}
    return {name: spec["default"] for name, spec in props.items() if isinstance(spec, dict) and "default" in spec}
