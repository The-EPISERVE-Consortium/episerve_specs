import copy
import json
from importlib import resources

import pytest

from episerve_specs import validate
from episerve_specs.specs.fdo.checks import kind_of

EXAMPLES = resources.files("episerve_specs.specs.fdo").joinpath("examples")
NAMES = sorted(p.name for p in EXAMPLES.iterdir() if p.name.endswith(".json"))
KINDS = {"raw-dataset.json": "raw", "processed-dataset.json": "processed", "model-run.json": "run", "benchmark.json": "benchmark"}


def load(name):
    return json.loads(EXAMPLES.joinpath(name).read_text(encoding="utf-8"))


def errors(result):
    return [f"{i.path}: {i.message}" for i in result.errors]


def has(result, path, text, severity="error"):
    return any(i.path == path and text in i.message and i.severity == severity for i in result.issues)


@pytest.fixture
def raw():
    return copy.deepcopy(load("raw-dataset.json"))


@pytest.fixture
def processed():
    return copy.deepcopy(load("processed-dataset.json"))


@pytest.fixture
def run():
    return copy.deepcopy(load("model-run.json"))


@pytest.fixture
def benchmark():
    return copy.deepcopy(load("benchmark.json"))


@pytest.mark.parametrize("name", NAMES)
def test_examples_are_valid_without_warnings(name):
    result = validate(load(name))
    assert (result.spec, result.version) == ("fdo", "1")
    assert result.valid and not result.warnings, [str(i) for i in result.issues]


def test_there_is_an_example_of_every_kind():
    assert sorted(NAMES) == sorted(KINDS)
    assert {n: kind_of(load(n)) for n in NAMES} == KINDS


def test_conforms_to_names_the_spec():
    doc = load("raw-dataset.json") | {"conformsTo": "https://api.episerve.zib.de/schemas/fdo/v1.json"}
    result = validate(doc)
    assert result.valid and result.spec == "fdo"


def test_a_model_card_is_not_taken_for_an_fdo():
    assert validate(load("raw-dataset.json") | {"@type": "SoftwareApplication"}).spec is None


# ── envelope ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("key", ["@context", "@id", "kernel", "profile", "provenance"])
def test_required_keys(raw, key):
    del raw[key]
    assert f"'{key}' is a required property" in [i.message for i in validate(raw, spec="fdo").errors]


def test_identifiers_must_agree(raw):
    raw["profile"]["@id"] = "Q1"
    assert has(validate(raw), "@id", "the identifiers differ")


def test_digital_object_type_is_dataset(raw):
    raw["kernel"]["digitalObjectType"] = "https://schema.org/SoftwareApplication"
    assert not validate(raw).valid


def test_qid_form(raw):
    raw["@id"] = raw["kernel"]["@id"] = raw["kernel"]["primaryIdentifier"] = raw["profile"]["@id"] = "not-a-qid"
    assert not validate(raw).valid


def test_a_component_needs_an_id_and_a_component_id(raw):
    del raw["kernel"]["fdo:hasComponent"][0]["componentId"]
    assert not validate(raw).valid


def test_duplicate_component_ids_are_an_error(raw):
    raw["kernel"]["fdo:hasComponent"].append(dict(raw["kernel"]["fdo:hasComponent"][0]))
    assert has(validate(raw), "kernel/fdo:hasComponent", "two components with @id")


def test_the_same_file_name_in_different_folders_is_a_warning(run):
    first = copy.deepcopy(run["kernel"]["fdo:hasComponent"][0])
    first["@id"] = "components/output/other/" + first["componentId"]
    run["kernel"]["fdo:hasComponent"].append(first)
    result = validate(run)
    assert result.valid and has(result, "kernel/fdo:hasComponent", "several components are named", "warning")


def test_a_component_without_media_type_is_a_warning(raw):
    del raw["kernel"]["fdo:hasComponent"][0]["mediaType"]
    result = validate(raw)
    assert result.valid and any("no mediaType" in i.message for i in result.warnings)


def test_extra_keys_are_allowed(processed):
    processed["provenance"]["scrape_query"] = "x"
    processed["profile"]["jev"] = {"a": 1}
    assert validate(processed).valid


def test_access_rights_values(processed):
    processed["profile"]["accessRights"] = "restricted"
    assert validate(processed).valid
    processed["profile"]["accessRights"] = "secret"
    assert not validate(processed).valid


# ── kinds ─────────────────────────────────────────────────────────────────────

def test_a_dataset_without_license_url_distribution_warns(raw):
    for key in ("license", "url", "distribution"):
        del raw["profile"][key]
    result = validate(raw)
    assert result.valid and {i.path for i in result.warnings} == {"profile/license", "profile/url", "profile/distribution"}


def test_a_dataset_needs_generation_provenance(raw):
    del raw["provenance"]["prov:generatedAtTime"]
    assert has(validate(raw), "provenance/prov:generatedAtTime", "required for a raw object")


def test_a_processed_dataset_names_its_raw_source(processed):
    del processed["provenance"]["prov:wasDerivedFrom"]
    assert has(validate(processed), "provenance/prov:wasDerivedFrom", "required for a processed object")


@pytest.mark.parametrize("shape", ["object", "list"])
def test_was_derived_from_may_be_one_entry_or_a_list(processed, shape):
    entry = processed["provenance"]["prov:wasDerivedFrom"]
    entry = entry[0] if isinstance(entry, list) else entry
    processed["provenance"]["prov:wasDerivedFrom"] = entry if shape == "object" else [entry, dict(entry)]
    assert validate(processed).valid


def test_was_derived_from_must_name_a_qid(processed):
    processed["provenance"]["prov:wasDerivedFrom"] = {"@id": "somewhere"}
    assert not validate(processed).valid


def test_a_run_needs_its_activity(run):
    del run["provenance"]["prov:endedAtTime"]
    del run["prov:wasGeneratedBy"]
    result = validate(run)
    assert has(result, "provenance/prov:endedAtTime", "required for a run object")
    assert has(result, "prov:wasGeneratedBy", "required for a model run")


def test_the_run_activity_must_match_the_provenance_block(run):
    run["prov:wasGeneratedBy"] = {"@id": "#other"}
    assert has(validate(run), "prov:wasGeneratedBy", "names '#other'")


def test_every_input_of_a_run_has_an_id(run):
    run["provenance"]["prov:used"].append({"@type": "prov:Entity"})
    assert any("prov:used/" in i.path for i in validate(run).errors)


def test_a_benchmark_lists_its_sources_by_qid(benchmark):
    benchmark["provenance"]["prov:wasDerivedFrom"] = ["Q1", {"@id": "Q2"}, "nonsense"]
    result = validate(benchmark)
    assert [i.path for i in result.errors] == ["provenance/prov:wasDerivedFrom/2"]


def test_a_finalized_benchmark_should_be_immutable(benchmark):
    benchmark["kernel"]["immutable"] = False
    assert has(validate(benchmark), "kernel/immutable", "immutable", "warning")


def test_checks_cope_with_malformed_documents():
    for doc in ({"@type": "DigitalObject", "kernel": []}, {"@type": "DigitalObject", "kernel": {}, "provenance": 3, "profile": "x"}):
        assert validate(doc, spec="fdo").errors
