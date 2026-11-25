# episerve_specs

Specifications, JSON Schemas and validators for the formats of the EPISERVE
platform. Each format is a **spec**; each spec version has a **schema** (the
machine-readable rules), extra checks for what a schema cannot express, the
spec text and examples.

| Spec | Versions | What it describes |
|---|---|---|
| [`model-card`](src/episerve_specs/specs/model_card/README.md) | v1 | a forecast model container (`fdo.json` in the model's repository) |
| [`fdo`](src/episerve_specs/specs/fdo/README.md) | v1 | the metadata record (`<QID>.fdo.json`) of a raw or processed dataset, a model run or a benchmark |

## Use

```bash
pip install "git+https://github.com/The-EPISERVE-Consortium/episerve_specs@v0.7.1"

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
result.to_dict()                   # includes "validator": "episerve-specs 0.7.1"

from episerve_specs import check_model_config
check_model_config(card, config)   # a run's config.json against the card's episerve:parameters
```

`check_model_config` raises `InvalidParameterSchema` if the declared parameter
schema cannot be used, for example when it contains an unresolved reference.

As a dependency (no git needed):

```
episerve-specs @ https://github.com/The-EPISERVE-Consortium/episerve_specs/archive/refs/tags/v0.7.1.tar.gz
```

### In a model repository's CI

```yaml
- uses: actions/checkout@v4
- uses: The-EPISERVE-Consortium/episerve_specs@v0.7.1
  with:
    files: fdo.json        # default
    strict: "false"        # default
```

## Where validation runs

Consumers pin a package release. The validation result records the release that
produced it.

| Where | What | State |
|---|---|---|
| Model repository CI | the action above | available |
| Sync flow (`workflow-prefect__sync-lakefs-ckan`) | validates each model's card, stores the card sections and the result in CKAN | available |
| API server | checks a run's config with `check_model_config` (`POST /model-runs`, and `POST /models/{model}/check-config` without starting a run) | available |
| API server | `POST /validate/{spec}` for people, agents and the CLI (`episerve validate`); serves the schemas at `/schemas/{spec}/v{N}.json` and lists them at `/schemas` | available |
| CKAN | the model page's "Model card" tab shows the card sections and the stored result | available |
| Writers of FDOs (dataset downloader, model runner, API server for benchmarks) | in their tests, against the `fdo` spec | available |

The `conformsTo` URLs resolve: `https://api.episerve.zib.de/schemas/model-card/v1.json`
serves the schema from the release the API server pins.

Checks that need platform data (which card belongs to this image, does this
benchmark's data fit this model) belong to the API, not here.

The sync flow registers a model even if its card is invalid and stores the
validation result in CKAN. The API rejects a run request if the model's declared
parameter schema cannot validate its configuration.

## Versions

- Each spec version has a fixed schema URL,
  `https://api.episerve.zib.de/schemas/<spec>/v<N>.json`, named in the
  document's `conformsTo`. A breaking change to a stable spec requires a new
  version. An internal draft can tighten its rules after checking known
  platform records and downstream tests.
- Package versions track releases of the validator, schemas, and helpers.

## Adding a spec

1. Add a subpackage `src/episerve_specs/specs/<name>/` with
   - `__init__.py` defining `SPEC_ID` (e.g. `dataset-fdo`) and
     `CHECKS = {"1": check_v1}`,
   - `v1.schema.json` with `$id` = the schema URL,
   - `checks.py` (`check_v1(document) -> list[Issue]`; must not crash on a
     malformed document),
   - `README.md` (the spec text) and `examples/`.
2. Add tests in `tests/`. The registry finds the subpackage by itself.

A new *section* of an existing spec: add it to the spec's `SECTIONS` list (model-card: `specs/model_card/checks.py`) and to its schema. The sync flow and the API server import that list; the CKAN theme has a test that compares its own list with it.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
pytest
```
