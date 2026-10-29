# Model card, version 1

A model card describes a forecast model container: what it is, which
parameters it accepts in `config.json`, which files it reads from
`/work/input/`, which files it writes to `/work/output/`, and what it needs
to run. It is the file `fdo.json` in the root of the model's repository.

- Schema: [`v1.schema.json`](v1.schema.json), published at
  `https://api.episerve.zib.de/schemas/model-card/v1.json`
- Extra checks the schema cannot express: [`checks.py`](checks.py)
- Complete examples: [`examples/`](examples/)

A card says it follows this version with

```json
"conformsTo": "https://api.episerve.zib.de/schemas/model-card/v1.json"
```

The card stays a schema.org `SoftwareApplication`. The EPISERVE sections are
keys with the prefix `episerve:`; other schema.org keys (`keywords`,
`applicationCategory`, …) are allowed and ignored.

Problems come in two severities. An **error** means the card does not follow
the spec. A **warning** means it does, but something is missing or likely
wrong (no license, no memory figure, …).

## Identity

| Key | Required | Meaning |
|---|---|---|
| `@context` | yes | `["https://schema.org/", {"episerve": "https://api.episerve.zib.de/schemas/model-card/v1#"}]` |
| `@type` | yes | `SoftwareApplication` |
| `conformsTo` | yes | the URL above (or a list containing it) |
| `name` | yes | the repository name, `model__<type>__<dataset>__<variant>` |
| `description` | yes | what the model does, at least 20 characters |
| `url` | yes | the container image **without a tag**, e.g. `ghcr.io/the-episerve-consortium/<repo>` |
| `codeRepository` | yes | `https://github.com/<owner>/<repo>` |
| `author` | yes | a `Person` or `Organization` with `name`, or a list of them |
| `softwareVersion` | no | the image tag the card describes; leave it out on the default branch |
| `license` | no (warning) | SPDX identifier, e.g. `Apache-2.0` |
| `citation` | no | DOI URL(s) of the method's paper(s) |

The platform finds a model's card through its image:
`ghcr.io/<owner>/<repo>` → `github.com/<owner>/<repo>/fdo.json`. So the image
name, `codeRepository` and `name` should all end in the same repository name
(a warning otherwise), and the image should be on `ghcr.io`.

## `episerve:task`

What kind of model this is.

| Key | Required | Meaning |
|---|---|---|
| `type` | yes | `forecast` (the only type in version 1) |
| `frequency` | yes | time step the model expects: `daily`, `weekly`, `monthly`, or `any` (inferred from the data) |
| `probabilistic` | yes | `true` when the outputs contain quantiles or samples; must match `episerve:outputs` |
| `covariates` | no, default `false` | `true` when the model uses input columns with role `covariate`; must match `episerve:inputs` |
| `maxHorizon` | no | the largest number of steps the model can forecast |
| `parameterRoles` | yes | which parameters play the standard roles (below) |

`parameterRoles` lets the platform fill parameters without knowing each
model's names, e.g. when a run starts from a benchmark:

| Role | Required | The parameter that … |
|---|---|---|
| `horizon` | yes | sets the number of steps to forecast |
| `history` | no | sets the number of past steps the model uses |
| `offset` | no | sets how many of the most recent steps to leave out (back-testing) |

Each names a declared integer parameter.

## `episerve:parameters`

A [JSON Schema](https://json-schema.org/) of `config.json`. The platform
uses it to build the parameter form, to check a config before a run starts,
and the model can use it to check its own config. To keep it renderable as a
form, it is restricted to flat parameters:

```json
"episerve:parameters": {
  "type": "object",
  "required": ["prediction_length"],
  "additionalProperties": false,
  "properties": {
    "prediction_length": {
      "type": "integer", "minimum": 1, "maximum": 512, "unit": "steps",
      "description": "Number of steps to forecast ahead."
    },
    "prediction_offset": {
      "type": "integer", "minimum": 0, "default": 0, "unit": "steps",
      "description": "Rows to skip at the end before the history window."
    }
  },
  "rules": ["history_length + prediction_offset must not exceed the number of input rows."]
}
```

- Parameter names: lower case, digits and `_`, starting with a letter.
- Each parameter needs `type` (`integer`, `number`, `string`, `boolean`) and
  `description`. Allowed further keywords: `title`, `default`, `enum`,
  `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf`,
  `minLength`, `maxLength`, `pattern`, `examples`, `unit`.
- A required parameter has no `default`. An optional one should have one
  (warning otherwise), and the default must satisfy the declaration.
- `additionalProperties: false` is recommended (warning otherwise): a
  misspelt key is then an error instead of being silently ignored.
- `rules` lists, in words, constraints between parameters or between
  parameters and the data. They are shown to users, not checked; the model
  checks them at run time.
- `additionalProperty` (the schema.org parameter list) is not part of the
  card and is an error; the parameters are only in `episerve:parameters`.

A config is checked against the card with

```python
from episerve_specs import check_model_config, model_config_defaults

issues = check_model_config(card, config)   # card or only its episerve:parameters
defaults = model_config_defaults(card)      # {name: default}
```

Each issue is an error with the parameter as its path (empty for a missing
required parameter). A `null` value is not a value: it fails the type.

## `episerve:inputs`

One entry per file the model reads from `/work/input/` (not `config.json`,
which the platform writes).

| Key | Required | Meaning |
|---|---|---|
| `file` | yes | file name, e.g. `input.parquet` |
| `format` | yes | `application/vnd.apache.parquet`, `text/tab-separated-values`, `text/csv` or `application/json` |
| `columns` | yes | the columns the model uses (below) |
| `description` | no | |
| `required` | no, default `true` | `false` for an optional file |
| `minRows` | no | the fewest rows the model accepts |
| `additionalColumns` | no, default `true` | `false`: the file must have exactly the listed columns |

A column is found by `name`, or by `position` (0 = first) when its name does
not matter. Each needs one of the two, a `role` and a `type`:

| `role` | Meaning |
|---|---|
| `time` | the time axis (at most one per file) |
| `target` | the series to forecast |
| `group` | splits the data into separate series, e.g. one per disease |
| `covariate` | an extra predictor |
| `filter` | the model keeps only some of its values; list them in `requiredValues` |
| `other` | read, but none of the above |

`type` is one of `date`, `datetime`, `isoWeek` (`YYYY-Www`), `integer`,
`number`, `string`, `boolean`, or a list of them. Optional: `description`,
`nullable` (default `false`), `required` (default `true`; `false` for a column
the file may lack, e.g. optional covariates), `values` (the only values
allowed), `requiredValues` (values that must occur).

A model that takes any number of columns of one kind (e.g. "every further
column is a covariate") lists the first of them by position with
`required: false`, says so in its `description`, and leaves
`additionalColumns` at `true`.

## `episerve:outputs`

One entry per file the model writes to `/work/output/` (not `run.log`, which
the platform writes). Same `file`, `format`, `description` and `columns` as
inputs.

An output column has either a fixed `name`, or `nameFrom`: it is named after
the input column with the given role, plus an optional suffix:

```json
{ "nameFrom": { "inputRole": "target", "suffix": "_q10" }, "role": "quantile", "level": 0.1 }
```

The forecast roles follow the [Hubverse](https://hubverse.io/) output types:

| `role` | Meaning |
|---|---|
| `time`, `group` | as for inputs |
| `mean` | mean of the forecast distribution |
| `median` | median |
| `quantile` | a quantile; `level` (between 0 and 1) is required and unique per file |
| `sample` | one sample path |
| `point` | a point forecast whose statistic is not specified; use `mean` or `median` when known |
| `other` | anything else |

Optional: `type`, `description`, `required` (default `true`; `false` for a
column written only in some cases, say which in `description`).

## `episerve:resources`

What the container needs. Without `cpu` and `memory` the card gets a
warning, because the platform cannot size the Kubernetes Job.

| Key | Meaning |
|---|---|
| `cpu` | Kubernetes CPU quantity, e.g. `2` or `500m` |
| `memory` | Kubernetes memory quantity, e.g. `4Gi` |
| `gpu` | number of GPUs |
| `network` | `true` when the container needs internet access at run time (e.g. to download weights) |
| `typicalRuntimeSeconds` | how long a typical run takes |

## `episerve:documentation`

The prose of a model card, as named fields. `method` and `limitations` give
a warning when missing.

| Key | Meaning |
|---|---|
| `method` | how the model works |
| `intendedUse` | what it is meant for |
| `limitations` | what it cannot do, known failure cases |
| `trainingData` | what it was trained on, or that it is not trained |
| `references` | URLs of papers, documentation, code |

## Changes to this spec

Version 1 is only ever extended compatibly: new optional keys, new enum
values. Anything that would make a valid version-1 card invalid is version 2,
a new `v2.schema.json` next to this one.
