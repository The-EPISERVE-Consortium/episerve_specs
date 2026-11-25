"""FDO checks that JSON Schema cannot express.

Every function gets the whole document and must cope with a malformed one: the schema errors are
reported separately, so a check only reports what it can see and skips values of the wrong type.
"""

from __future__ import annotations

from ...result import Issue

def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def detect(document) -> str | None:
    """Version 1 for a DigitalObject with the Dataset kernel type."""
    if (
        isinstance(document, dict)
        and document.get("@type") == "DigitalObject"
        and _dict(document.get("kernel")).get("digitalObjectType") == "https://schema.org/Dataset"
    ):
        return "1"
    return None


def kind_of(fdo: dict) -> str:
    """``run``, ``benchmark``, ``raw`` or ``processed``: what the object is, from what it carries."""
    if "prov:wasGeneratedBy" in fdo or _dict(fdo.get("provenance")).get("@type") == "prov:Activity":
        return "run"
    profile = _dict(fdo.get("profile"))
    if profile.get("additionalType") == "benchmarks" or "episerveBenchmark" in profile:
        return "benchmark"
    return "raw" if str(fdo.get("@id", "")).endswith("-raw") else "processed"


def check_v1(fdo: dict) -> list[Issue]:
    issues: list[Issue] = []
    kind = kind_of(fdo)
    for check in (_identity, _components, _profile, _activity_reference):
        issues += check(fdo, kind)
    return issues


def _identity(fdo: dict, kind: str) -> list[Issue]:
    kernel, profile = _dict(fdo.get("kernel")), _dict(fdo.get("profile"))
    ids = {"@id": fdo.get("@id"), "kernel/@id": kernel.get("@id"), "kernel/primaryIdentifier": kernel.get("primaryIdentifier"),
           "profile/@id": profile.get("@id")}
    ids = {k: v for k, v in ids.items() if isinstance(v, str)}
    if len(set(ids.values())) > 1:
        return [Issue("error", "@id", "the identifiers differ: " + ", ".join(f"{k} = {v}" for k, v in ids.items()))]
    issues = []
    if kind == "benchmark" and kernel.get("immutable") is False:
        issues.append(Issue("warning", "kernel/immutable", "a benchmark is finalized and should be immutable"))
    return issues


def _components(fdo: dict, kind: str) -> list[Issue]:
    issues = []
    components = [c for c in _list(_dict(fdo.get("kernel")).get("fdo:hasComponent")) if isinstance(c, dict)]
    ids = [c["@id"] for c in components if isinstance(c.get("@id"), str)]
    for duplicate in sorted({v for v in ids if ids.count(v) > 1}):
        issues.append(Issue("error", "kernel/fdo:hasComponent", f"two components with @id {duplicate!r}"))
    names = [c["componentId"] for c in components if isinstance(c.get("componentId"), str)]
    for duplicate in sorted({v for v in names if names.count(v) > 1}):
        issues.append(Issue(
            "warning", "kernel/fdo:hasComponent",
            f"several components are named {duplicate!r}; they can only be told apart by their @id (the path below the object)",
        ))
    for index, component in enumerate(components):
        if "mediaType" not in component:
            issues.append(Issue("warning", f"kernel/fdo:hasComponent/{index}", f"component {component.get('componentId', index)!r} has no mediaType"))
    return issues


def _profile(fdo: dict, kind: str) -> list[Issue]:
    profile = _dict(fdo.get("profile"))
    issues = []
    if kind in ("raw", "processed"):
        if not profile.get("license"):
            issues.append(Issue("warning", "profile/license", "missing; the catalog shows the dataset without a licence"))
        if not profile.get("url"):
            issues.append(Issue("warning", "profile/url", "missing; the source of the data is not recorded"))
        if not _list(profile.get("distribution")):
            issues.append(Issue("warning", "profile/distribution", "missing; the download location is not recorded"))
    if kind == "run" and not profile.get("url"):
        issues.append(Issue("warning", "profile/url", "missing; the model image is not recorded"))
    return issues


def _activity_reference(fdo: dict, kind: str) -> list[Issue]:
    if kind != "run":
        return []
    activity = _dict(fdo.get("prov:wasGeneratedBy")).get("@id")
    provenance_id = _dict(fdo.get("provenance")).get("@id")
    if isinstance(activity, str) and isinstance(provenance_id, str) and activity != provenance_id:
        return [Issue("error", "prov:wasGeneratedBy", f"names {activity!r}, but the provenance block is {provenance_id!r}")]
    return []
