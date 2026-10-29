"""Model card checks that JSON Schema cannot express.

Every function here gets the whole document and must cope with a malformed one:
the schema errors are reported separately, so a check only reports what it can
see and skips values of the wrong type.
"""

from __future__ import annotations

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from ...result import Issue

KNOWN_KEYS = {
    "episerve:task",
    "episerve:parameters",
    "episerve:inputs",
    "episerve:outputs",
    "episerve:resources",
    "episerve:documentation",
}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def check_v1(card: dict) -> list[Issue]:
    issues: list[Issue] = []
    for check in (_unknown_keys, _identity, _parameters, _legacy_parameters, _task, _inputs, _outputs, _recommended):
        issues += check(card)
    return issues


def _unknown_keys(card: dict) -> list[Issue]:
    return [
        Issue("error", key, f"unknown key; version 1 defines {', '.join(sorted(KNOWN_KEYS))}")
        for key in sorted(card)
        if key.startswith("episerve:") and key not in KNOWN_KEYS
    ]


def _identity(card: dict) -> list[Issue]:
    """The platform finds the card through the image name: ghcr.io/<owner>/<repo> -> github.com/<owner>/<repo>."""
    issues = []
    url, repo, name = card.get("url"), card.get("codeRepository"), card.get("name")
    if not isinstance(url, str):
        return issues
    image_name = url.rstrip("/").rsplit("/", 1)[-1]
    if not url.startswith("ghcr.io/"):
        issues.append(Issue("warning", "url", "not a ghcr.io image; the platform can only find the card of a ghcr.io image"))
    if isinstance(repo, str) and repo.rstrip("/").rsplit("/", 1)[-1].lower() != image_name.lower():
        issues.append(Issue(
            "warning", "codeRepository",
            f"repository name differs from the image name '{image_name}'; the platform looks for the card in the repository named like the image",
        ))
    if isinstance(name, str) and name != image_name:
        issues.append(Issue("warning", "name", f"differs from the image name '{image_name}'"))
    return issues


def _parameters(card: dict) -> list[Issue]:
    if not isinstance(card.get("episerve:parameters"), dict):
        return []  # reported by the schema
    params = card["episerve:parameters"]
    props = _dict(params.get("properties"))
    base = "episerve:parameters"
    issues = []

    try:
        Draft202012Validator.check_schema(params)
    except SchemaError as e:
        issues.append(Issue("error", base, f"is not a valid JSON Schema: {e.message}"))
        return issues

    for i, name in enumerate(_list(params.get("required"))):
        if name not in props:
            issues.append(Issue("error", f"{base}/required/{i}", f"'{name}' is required but not declared in properties"))

    required = set(_list(params.get("required")))
    for name, spec in props.items():
        if not isinstance(spec, dict):
            continue
        path = f"{base}/properties/{name}"
        if "default" in spec:
            if name in required:
                issues.append(Issue("error", f"{path}/default", "a required parameter must not have a default"))
            else:
                for e in Draft202012Validator({k: v for k, v in spec.items() if k != "default"}).iter_errors(spec["default"]):
                    issues.append(Issue("error", f"{path}/default", f"default does not fit the declaration: {e.message}"))
        elif name not in required:
            issues.append(Issue("warning", path, "optional parameter without a default; say what the model does when it is left out"))
        low = spec.get("minimum", spec.get("exclusiveMinimum"))
        high = spec.get("maximum", spec.get("exclusiveMaximum"))
        if isinstance(low, (int, float)) and isinstance(high, (int, float)) and low > high:
            issues.append(Issue("error", path, "the lower bound is greater than the upper bound"))
        if spec.get("type") in ("string", "boolean") and any(k in spec for k in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")):
            issues.append(Issue("error", path, f"numeric bounds on a {spec.get('type')} parameter"))

    if params.get("additionalProperties") is not False:
        issues.append(Issue(
            "warning", f"{base}/additionalProperties",
            "not false: a misspelt config.json key is accepted without notice",
        ))
    return issues


def _legacy_parameters(card: dict) -> list[Issue]:
    """The platform still reads ``additionalProperty`` (CKAN model_parameters, API config check, the models'
    own config_schema.py); while it does, it must say the same as ``episerve:parameters``."""
    if not isinstance(card.get("episerve:parameters"), dict):
        return []  # nothing to compare with; reported by the schema
    params = _dict(card.get("episerve:parameters"))
    props = _dict(params.get("properties"))
    required = set(_list(params.get("required")))
    if "additionalProperty" not in card:
        return [Issue(
            "warning", "additionalProperty",
            "missing; until the platform reads episerve:parameters it takes the parameters from here only",
        )] if props else []

    issues = []
    seen = set()
    for i, entry in enumerate(_list(card.get("additionalProperty"))):
        path = f"additionalProperty/{i}"
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            issues.append(Issue("error", path, "entry without a string 'name'"))
            continue
        name = entry["name"]
        seen.add(name)
        spec = props.get(name)
        if not isinstance(spec, dict):
            issues.append(Issue("error", path, f"'{name}' is not declared in episerve:parameters"))
            continue
        pairs = [
            ("valueRequired", entry.get("valueRequired", False), name in required),
            ("valueType", entry.get("valueType", "integer"), spec.get("type")),
            ("minValue", entry.get("minValue"), spec.get("minimum")),
            ("maxValue", entry.get("maxValue"), spec.get("maximum")),
            ("value", entry.get("value"), spec.get("default")),
        ]
        for key, legacy, current in pairs:
            if legacy != current:
                issues.append(Issue(
                    "error", f"{path}/{key}",
                    f"'{name}': {key} is {legacy!r} here but episerve:parameters says {current!r}",
                ))
    for name in sorted(set(props) - seen):
        issues.append(Issue("error", "additionalProperty", f"'{name}' is declared in episerve:parameters but missing here"))
    return issues


def _task(card: dict) -> list[Issue]:
    task = _dict(card.get("episerve:task"))
    props = _dict(_dict(card.get("episerve:parameters")).get("properties"))
    issues = []
    for role, name in _dict(task.get("parameterRoles")).items():
        if isinstance(name, str) and name not in props:
            issues.append(Issue("error", f"episerve:task/parameterRoles/{role}", f"names '{name}', which is not a declared parameter"))
        elif isinstance(name, str) and _dict(props[name]).get("type") != "integer":
            issues.append(Issue("error", f"episerve:task/parameterRoles/{role}", f"'{name}' counts steps and must be an integer parameter"))

    roles = {_dict(c).get("role") for f in _list(card.get("episerve:outputs")) for c in _list(_dict(f).get("columns"))}
    probabilistic = task.get("probabilistic")
    if probabilistic is True and not roles & {"quantile", "sample"}:
        issues.append(Issue("error", "episerve:task/probabilistic", "true, but no output column has role quantile or sample"))
    if probabilistic is False and roles & {"quantile", "sample"}:
        issues.append(Issue("error", "episerve:task/probabilistic", "false, but an output column has role quantile or sample"))

    input_roles = {_dict(c).get("role") for f in _list(card.get("episerve:inputs")) for c in _list(_dict(f).get("columns"))}
    if task.get("covariates") is True and "covariate" not in input_roles:
        issues.append(Issue("error", "episerve:task/covariates", "true, but no input column has role covariate"))
    if task.get("covariates", False) is False and "covariate" in input_roles:
        issues.append(Issue("error", "episerve:task/covariates", "false, but an input column has role covariate"))
    return issues


def _columns(columns: list, path: str, *, positions: bool) -> list[Issue]:
    issues = []
    names, pos = {}, {}
    for i, column in enumerate(columns):
        if not isinstance(column, dict):
            continue
        cpath = f"{path}/{i}"
        name = column.get("name")
        if positions:
            if "name" not in column and "position" not in column:
                issues.append(Issue("error", cpath, "needs a name or a position"))
            p = column.get("position")
            if isinstance(p, int):
                if p in pos:
                    issues.append(Issue("error", f"{cpath}/position", f"position {p} is also used by column {pos[p]}"))
                pos[p] = i
        else:
            if ("name" in column) == ("nameFrom" in column):
                issues.append(Issue("error", cpath, "needs exactly one of name and nameFrom"))
        if isinstance(name, str):
            if name in names:
                issues.append(Issue("error", f"{cpath}/name", f"'{name}' is also used by column {names[name]}"))
            names[name] = i
    return issues


def _inputs(card: dict) -> list[Issue]:
    issues = []
    files = {}
    for i, f in enumerate(_list(card.get("episerve:inputs"))):
        if not isinstance(f, dict):
            continue
        path = f"episerve:inputs/{i}"
        name = f.get("file")
        if name == "config.json":
            issues.append(Issue("error", f"{path}/file", "config.json is written by the platform from episerve:parameters; do not list it as an input"))
        elif isinstance(name, str):
            if name in files:
                issues.append(Issue("error", f"{path}/file", f"'{name}' is also listed as input {files[name]}"))
            files[name] = i
        columns = _list(f.get("columns"))
        issues += _columns(columns, f"{path}/columns", positions=True)
        roles = [_dict(c).get("role") for c in columns]
        if "target" not in roles and "covariate" not in roles:
            issues.append(Issue("warning", f"{path}/columns", "no column with role target or covariate"))
        if roles.count("time") > 1:
            issues.append(Issue("error", f"{path}/columns", "more than one column with role time"))
        if f.get("additionalColumns") is False:
            p = [c.get("position") for c in columns if isinstance(c, dict) and isinstance(c.get("position"), int)]
            if p and sorted(p) != list(range(len(columns))):
                issues.append(Issue("error", f"{path}/columns", "with additionalColumns false, positions must be 0..n-1 without gaps"))
    return issues


def _outputs(card: dict) -> list[Issue]:
    issues = []
    input_roles = {_dict(c).get("role") for f in _list(card.get("episerve:inputs")) for c in _list(_dict(f).get("columns"))}
    files = {}
    for i, f in enumerate(_list(card.get("episerve:outputs"))):
        if not isinstance(f, dict):
            continue
        path = f"episerve:outputs/{i}"
        name = f.get("file")
        if name == "run.log":
            issues.append(Issue("error", f"{path}/file", "run.log is written by the platform; do not list it as an output"))
        elif isinstance(name, str):
            if name in files:
                issues.append(Issue("error", f"{path}/file", f"'{name}' is also listed as output {files[name]}"))
            files[name] = i
        columns = _list(f.get("columns"))
        issues += _columns(columns, f"{path}/columns", positions=False)
        levels = {}
        for j, column in enumerate(columns):
            if not isinstance(column, dict):
                continue
            cpath = f"{path}/columns/{j}"
            role = column.get("role")
            if role == "quantile" and "level" not in column:
                issues.append(Issue("error", cpath, "a quantile column needs a level"))
            if role != "quantile" and "level" in column:
                issues.append(Issue("error", f"{cpath}/level", "only a quantile column has a level"))
            level = column.get("level")
            if role == "quantile" and isinstance(level, (int, float)):
                if level in levels:
                    issues.append(Issue("error", f"{cpath}/level", f"level {level} is also used by column {levels[level]}"))
                levels[level] = j
            source = _dict(column.get("nameFrom")).get("inputRole")
            if isinstance(source, str) and source not in input_roles:
                issues.append(Issue("error", f"{cpath}/nameFrom/inputRole", f"no input column has role {source}"))
        roles = [_dict(c).get("role") for c in columns]
        if not {"mean", "median", "point", "quantile", "sample"} & set(roles):
            issues.append(Issue("warning", f"{path}/columns", "no forecast column (mean, median, point, quantile or sample)"))
    return issues


def _recommended(card: dict) -> list[Issue]:
    issues = []
    if "license" not in card:
        issues.append(Issue("warning", "license", "missing"))
    resources = card.get("episerve:resources")
    if not isinstance(resources, dict) or not {"cpu", "memory"} <= set(resources):
        issues.append(Issue("warning", "episerve:resources", "no cpu and memory; the platform cannot size the model's Kubernetes Job"))
    doc = _dict(card.get("episerve:documentation"))
    for key in ("method", "limitations"):
        if not doc.get(key):
            issues.append(Issue("warning", f"episerve:documentation/{key}", "missing"))
    return issues
