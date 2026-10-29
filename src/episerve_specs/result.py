"""The result of validating one document."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Issue:
    """One problem found in a document.

    ``path`` points at the offending value, e.g. ``episerve:parameters/properties/horizon``
    (empty for the document itself). ``severity`` is ``error`` (the document does not
    conform) or ``warning`` (it conforms, but something is likely wrong or missing).
    """

    severity: str
    path: str
    message: str

    def __str__(self) -> str:
        where = f"{self.path}: " if self.path else ""
        return f"{self.severity.upper()}: {where}{self.message}"

    def to_dict(self) -> dict:
        return {"severity": self.severity, "path": self.path, "message": self.message}


@dataclass
class Result:
    """All issues found in a document, and which spec version it was checked against."""

    spec: str | None
    version: str | None
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def valid(self) -> bool:
        """True when there are no errors (warnings are allowed)."""
        return not self.errors

    def to_dict(self) -> dict:
        from . import __version__

        return {
            "spec": self.spec,
            "version": self.version,
            "valid": self.valid,
            "validator": f"episerve-specs {__version__}",
            "issues": [i.to_dict() for i in self.issues],
        }
