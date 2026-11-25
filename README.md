# episerve_specs

JSON Schemas, examples, and validators for EPISERVE platform formats.

| Spec | Version | What it describes |
|---|---|---|
| [Model card](src/episerve_specs/specs/model_card/README.md) | v1 | A forecast model's `fdo.json` |
| [FDO](src/episerve_specs/specs/fdo/README.md) | v1 (draft) | A lakeFS metadata record for a dataset, model run, or benchmark |

The [EPISERVE specs playbook](https://github.com/The-EPISERVE-Consortium/episerve_playbooks/blob/main/pb__specs/playbook.md) covers validation in CI and through the API, changing specs, and releasing and rolling out updates.

## Quick start

Requires Python 3.10 or newer.

```bash
pip install "episerve-specs @ https://github.com/The-EPISERVE-Consortium/episerve_specs/archive/refs/tags/v0.7.1.tar.gz"
episerve-validate fdo.json
episerve-validate --spec model-card fdo.json
```

In Python, use `validate(document)` to check a record and
`check_model_config(card, config)` to check a run configuration.
The [API schema index](https://api.episerve.zib.de/schemas) lists the published schemas.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
pytest
```
