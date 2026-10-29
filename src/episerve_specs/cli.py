"""``episerve-validate``: validate files against EPISERVE specs.

Exit code 0 when every file is valid, 1 when a file has errors (or warnings with
``--strict``), 2 for a usage problem (unreadable file, unknown spec).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .registry import available_specs, validate


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="episerve-validate",
        description="Validate files against EPISERVE specs. The spec is read from each file's conformsTo unless --spec is given.",
    )
    p.add_argument("files", nargs="*", type=Path, help="JSON files to validate")
    p.add_argument("--spec", help="spec to validate against, e.g. model-card")
    p.add_argument("--spec-version", help="spec version, e.g. 1 (default: from conformsTo, else the newest)")
    p.add_argument("--strict", action="store_true", help="treat warnings as errors")
    p.add_argument("--json", action="store_true", help="print the results as JSON")
    p.add_argument("--list", action="store_true", help="list the known specs and exit")
    p.add_argument("--version", action="version", version=f"episerve-specs {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.list:
        for spec, versions in available_specs().items():
            print(f"{spec}: v{', v'.join(versions)}")
        return 0
    if not args.files:
        _parser().error("no files given")

    results = []
    failed = False
    for path in args.files:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"{path}: cannot read: {e}", file=sys.stderr)
            return 2
        try:
            result = validate(document, spec=args.spec, version=args.spec_version)
        except ValueError as e:
            print(f"{path}: {e}", file=sys.stderr)
            return 2
        ok = result.valid and not (args.strict and result.warnings)
        failed |= not ok
        results.append((path, result, ok))

    if args.json:
        print(json.dumps([{"file": str(p), **r.to_dict(), "ok": ok} for p, r, ok in results], indent=2))
    else:
        for path, result, ok in results:
            spec = f"{result.spec} v{result.version}" if result.spec else "no spec"
            status = "OK" if ok else "FAILED"
            counts = f"{len(result.errors)} error(s), {len(result.warnings)} warning(s)"
            print(f"{path} ({spec}): {status}, {counts}")
            for issue in result.issues:
                print(f"  {issue}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
