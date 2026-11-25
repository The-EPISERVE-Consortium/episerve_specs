# FDO, version 1

**Since** package 0.6.0 · **Status:** draft. The dataset downloader, model runner, and API server test the records they write against this spec. Draft validation rules may tighten within v1 after checking existing platform records and downstream tests.

The metadata record (`<QID>.fdo.json`) of an object on the EPISERVE platform: a
**raw dataset**, a **processed dataset**, a **model run** or a **benchmark**. The
platform's writers (dataset downloader, model runner, benchmark designer) create
it; the sync flow, the DOIP server, the lineage view and the catalog read it.

The schema is at `https://api.episerve.zib.de/schemas/fdo/v1.json`. Documents may name it in
`conformsTo` using the schema URL, an object with that URL as `@id`, or a list
containing either form. Automatic detection checks for `@type: DigitalObject` and a
`kernel.digitalObjectType` of `https://schema.org/Dataset`.

The published JSON Schema describes required fields, types, and formats. Use a
schema validator with format assertions enabled to check timestamps. The full
EPISERVE validator also checks relationships between fields, such as matching
identifiers and unique component IDs, and reports warnings.

## Envelope (all kinds)

| Key | Content |
|---|---|
| `@context` | `["https://w3id.org/fdo/context/v1", {schema, prov, fdo prefixes}]` |
| `@id`, `@type` | the object's QID (a raw dataset's ends in `-raw`); `DigitalObject` |
| `kernel` | `@id`, `primaryIdentifier` (both the QID), `digitalObjectType`, `kernelVersion`, `immutable`, `modified`, `fdo:hasComponent` |
| `profile` | a schema.org `Dataset`: `@id`, `name`, `description`, and the keys below |
| `provenance` | PROV; its keys depend on the kind |
| `prov:wasGeneratedBy` | model runs only: `{"@id": "#run"}`, naming the provenance block |

The four identifiers (`@id`, `kernel/@id`, `kernel/primaryIdentifier` and `profile/@id`) are equal.
Use UTC with whole seconds and a trailing `Z` for `kernel.modified`. Provenance
timestamps may include fractional seconds and UTC offsets.

### Decisions of version 1

- **`kernel.digitalObjectType` is always `https://schema.org/Dataset`.** Every object is a set of files;
  what kind of object it is shows in the profile and the provenance (see Kinds).
- **`kernel.immutable`** is `true` for a finalized benchmark and `false` for everything else.
- **`profile.display_name`** is the title shown in the catalog. It is not a schema.org term but an EPISERVE
  addition, read by the sync flow, the lineage view and the catalog; readers fall back to `name`.
- **Distribution URLs are `contentUrl`.** No other spelling is written.
- **A component's identity is its `@id`**, which is unique within the object. Two forms exist:
  `#<componentId>` (raw datasets and benchmarks: the file sits next to the record) and
  `components/<path>` (processed datasets and model runs: the file's path below the object, which is also
  how DOIP addresses it). `componentId` is the file name; in a model run it can repeat
  (`output/observed/x.tsv`, `output/scenario/x.tsv`), which gives a warning.
- Additional keys are allowed everywhere: writers such as the X scraper add their own to `provenance`.

## Kinds

| Kind | Recognised by | `provenance` requires | Profile |
|---|---|---|---|
| raw dataset | `@id` ends in `-raw` | `prov:generatedAtTime`, `prov:wasAttributedTo` | `url` (the source), `distribution`, `license`, `creditText`, `additionalType` (category) |
| processed dataset | any other dataset | the same, and `prov:wasDerivedFrom`: `{"@id": <raw QID>, "prov:hadPrimarySource": <URL>}`, or a list of them for a dataset of several files | as raw |
| model run | `prov:wasGeneratedBy` | `@id`, `@type: prov:Activity`, `prov:startedAtTime`, `prov:endedAtTime`, `prov:used` (the inputs, each with an `@id`), `prov:wasAssociatedWith` (the model image, with an `@id`) | `url` is the model image |
| benchmark | `profile.episerveBenchmark` or `additionalType: benchmarks` | `prov:generatedAtTime`, `prov:wasAttributedTo`, `prov:wasDerivedFrom` (a list of the source objects) | `episerveBenchmark` (the pinned files), `accessRights` |

A benchmark's `episerveBenchmark` metadata contains its `id`, `data_commit`,
and `files`. Both `files.input` and `files.reference` require a `component`
name, `sha256` checksum, `rows` count, and `columns` list. A
`files.definition` entry is optional and requires its component name and checksum
when present. Older benchmark provenance can name source objects by bare QID.

## Warnings

A record is valid with these, but something is likely missing: a component without `mediaType`, several
components with the same file name, a dataset without `license`, `url` or `distribution`, a benchmark that
is not `immutable`.

## Examples

`examples/` holds one record of each kind, taken from the platform.
