"""FDO checks that JSON Schema cannot express.

Every function gets the whole document and must cope with a malformed one: the schema errors are
reported separately, so a check only reports what it can see and skips values of the wrong type.
"""

from __future__ import annotations

import re

from ...result import Issue

_QID = re.compile(r"Q[0-9]+")


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def detect(document) -> str | None:
    """Version 1 for a document that looks like an FDO but does not name its spec."""
    if isinstance(document, dict) and document.get("@type") == "DigitalObject" and isinstance(document.get("kernel"), dict):
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
    for check in (_identity, _components, _profile, _provenance):
        issues += check(fdo, kind_of(fdo))
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


def _provenance(fdo: dict, kind: str) -> list[Issue]:
    prov = _dict(fdo.get("provenance"))
    if "provenance" in fdo and not isinstance(fdo["provenance"], dict):
        return []
    issues = []

    def need(*keys):
        for key in keys:
            if key not in prov:
                issues.append(Issue("error", f"provenance/{key}", f"required for a {kind} object"))

    if kind in ("raw", "processed"):
        need("prov:generatedAtTime", "prov:wasAttributedTo")
    if kind in ("processed", "benchmark"):
        need("prov:wasDerivedFrom")
        issues += _derived_from(prov.get("prov:wasDerivedFrom"), kind)
    if kind == "benchmark":
        need("prov:generatedAtTime", "prov:wasAttributedTo")
    if kind == "run":
        need("@id", "@type", "prov:startedAtTime", "prov:endedAtTime", "prov:used", "prov:wasAssociatedWith")
        activity = _dict(fdo.get("prov:wasGeneratedBy")).get("@id")
        if isinstance(activity, str) and isinstance(prov.get("@id"), str) and activity != prov["@id"]:
            issues.append(Issue("error", "prov:wasGeneratedBy", f"names {activity!r}, but the provenance block is {prov['@id']!r}"))
        if "prov:wasGeneratedBy" not in fdo:
            issues.append(Issue("error", "prov:wasGeneratedBy", "required for a model run"))
        for index, used in enumerate(_list(prov.get("prov:used"))):
            if not isinstance(used, dict) or not isinstance(used.get("@id"), str):
                issues.append(Issue("error", f"provenance/prov:used/{index}", "must be an object with an @id"))
        agent = _dict(prov.get("prov:wasAssociatedWith"))
        if "prov:wasAssociatedWith" in prov and not isinstance(agent.get("@id"), str):
            issues.append(Issue("error", "provenance/prov:wasAssociatedWith", "must be an object with an @id (the model image)"))
    return issues


def _derived_from(value, kind: str) -> list[Issue]:
    """``prov:wasDerivedFrom``: one entry or a list. An entry is ``{"@id": <QID>, ...}``; a benchmark's list may
    also hold bare QIDs (older benchmarks)."""
    issues = []
    entries = value if isinstance(value, list) else [value]
    for index, entry in enumerate(entries):
        qid = entry if isinstance(entry, str) and kind == "benchmark" else _dict(entry).get("@id")
        if not isinstance(qid, str) or not _QID.fullmatch(qid.removesuffix("-raw")):
            issues.append(Issue("error", f"provenance/prov:wasDerivedFrom{'/' + str(index) if isinstance(value, list) else ''}",
                                "must name the source object by its QID (an object with an @id)"))
    return issues
