# episerve_specs

Specifications, JSON Schemas and validators for the formats of the EPISERVE
platform. Each format is a **spec**; each spec version has a **schema** (the
machine-readable rules), extra checks for what a schema cannot express, the
spec text and examples.

| Spec | Versions | What it describes |
|---|---|---|
| [`model-card`](src/episerve_specs/specs/model_card/README.md) | v1 | a forecast model container (`fdo.json` in the model's repository) |

## Use

```bash
pip install "git+https://github.com/The-EPISERVE-Consortium/episerve_specs@v0.2.1"

episerve-validate fdo.json                     # spec from the file's conformsTo
episerve-validate --spec model-card fdo.json   # name it (e.g. for a card without conformsTo)
episerve-validate --strict fdo.json            # warnings fail too
episerve-validate --json fdo.json              # machine-readable result
episerve-validate --list                       # known specs and versions
```

Exit code 0 = valid, 1 = errors (or warnings with `--strict`), 2 = unreadable
file or unknown spec.

```python
from episerve_specs import validate

result = validate(card)            # or validate(card, spec="model-card", version="1")
result.valid                       # no errors (warnings allowed)
for issue in result.issues:        # Issue(severity, path, message)
    print(issue)
result.to_dict()                   # includes "validator": "episerve-specs 0.2.1"

from episerve_specs import check_model_config
check_model_config(card, config)   # a run's config.json against the card's episerve:parameters
```

As a dependency (no git needed):

```
episerve-specs @ https://github.com/The-EPISERVE-Consortium/episerve_specs/archive/refs/tags/v0.2.1.tar.gz
```

### In a model repository's CI

```yaml
- uses: actions/checkout@v4
- uses: The-EPISERVE-Consortium/episerve_specs@v0.2.1
  with:
    files: fdo.json        # default
    strict: "false"        # default
```

## Where validation runs

Every consumer uses this package directly and pins the same release, so they
all get the same result. The result records which validator produced it.

| Where | What | State |
|---|---|---|
| Model repository CI | the action above | available |
| Sync flow (`workflow-prefect__sync-lakefs-ckan`) | validates each model's card, stores the card sections and the result in CKAN | available |
| API server | checks a run's config with `check_model_config` | available |
| API server | `POST /validate/{spec}` for people, the UI and agents; serves the schemas at `/schemas/{spec}/v{N}.json` | planned |
| Writers of other formats | in their tests | planned |

Until the API serves the schemas, the `conformsTo` URLs are identifiers only;
the schemas themselves are in this repository.

Checks that need platform data (which card belongs to this image, does this
benchmark's data fit this model) belong to the API, not here.

Policy: an invalid card only produces a **warning**: the sync flow stores the
result in CKAN, and the model is still registered and runs.

## Versions

- Each spec version has a fixed schema URL,
  `https://api.episerve.zib.de/schemas/<spec>/v<N>.json`, named in the
  document's `conformsTo`. A released version is only extended compatibly; a
  breaking change is a new version next to it.
- Package releases (`v0.1.0`, …) add specs, spec versions and helpers.

## Adding a spec

1. Add a subpackage `src/episerve_specs/specs/<name>/` with
   - `__init__.py` defining `SPEC_ID` (e.g. `dataset-fdo`) and
     `CHECKS = {"1": check_v1}`,
   - `v1.schema.json` with `$id` = the schema URL,
   - `checks.py` (`check_v1(document) -> list[Issue]`; must not crash on a
     malformed document),
   - `README.md` (the spec text) and `examples/`.
2. Add tests in `tests/`. The registry finds the subpackage by itself.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
pytest
```
