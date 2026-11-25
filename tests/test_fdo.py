import copy
import json
from importlib import resources

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from episerve_specs import detect_spec, load_schema, schema_url, validate
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


@pytest.mark.parametrize("as_object", [False, True])
@pytest.mark.parametrize("as_list", [False, True])
def test_conforms_to_names_the_spec(as_object, as_list):
    url = schema_url("fdo", "1")
    reference = {"@id": url} if as_object else url
    doc = load("raw-dataset.json") | {"conformsTo": [reference] if as_list else reference}
    result = validate(doc)
    assert result.valid and result.spec == "fdo"


def test_a_model_card_is_not_taken_for_an_fdo():
    assert validate(load("raw-dataset.json") | {"@type": "SoftwareApplication"}).spec is None


def test_a_model_fdo_without_conforms_to_is_not_auto_detected(raw):
    raw["kernel"]["digitalObjectType"] = "https://schema.org/SoftwareApplication"
    raw["profile"]["@type"] = "SoftwareApplication"
    assert detect_spec(raw) is None


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
    assert any(i.path == "kernel/digitalObjectType" for i in validate(raw, spec="fdo").errors)


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
    assert has(validate(raw), "provenance", "'prov:generatedAtTime' is a required property")


def test_generation_time_must_be_a_timestamp(raw):
    raw["provenance"]["prov:generatedAtTime"] = None
    assert has(validate(raw), "provenance/prov:generatedAtTime", "is not of type")


def test_published_schema_rejects_an_impossible_kernel_date(raw):
    raw["kernel"]["modified"] = "2026-02-30T00:00:00Z"
    validator = Draft202012Validator(load_schema("fdo", "1"), format_checker=FormatChecker())
    assert not validator.is_valid(raw)
    assert has(validate(raw), "kernel/modified", "is not a 'date-time'")


def test_a_processed_dataset_names_its_raw_source(processed):
    del processed["provenance"]["prov:wasDerivedFrom"]
    assert has(validate(processed), "provenance", "'prov:wasDerivedFrom' is a required property")


@pytest.mark.parametrize("shape", ["object", "list"])
def test_was_derived_from_may_be_one_entry_or_a_list(processed, shape):
    entry = processed["provenance"]["prov:wasDerivedFrom"]
    entry = entry[0] if isinstance(entry, list) else entry
    processed["provenance"]["prov:wasDerivedFrom"] = entry if shape == "object" else [entry, dict(entry)]
    assert validate(processed).valid


def test_was_derived_from_must_name_a_qid(processed):
    processed["provenance"]["prov:wasDerivedFrom"] = {"@id": "somewhere"}
    assert not validate(processed).valid


def test_a_processed_dataset_needs_at_least_one_source(processed):
    processed["provenance"]["prov:wasDerivedFrom"] = []
    assert has(validate(processed), "provenance/prov:wasDerivedFrom", "is not valid")


def test_a_run_needs_its_activity(run):
    del run["provenance"]["prov:endedAtTime"]
    del run["prov:wasGeneratedBy"]
    result = validate(run)
    assert has(result, "provenance", "'prov:endedAtTime' is a required property")
    assert has(result, "", "'prov:wasGeneratedBy' is a required property")


def test_the_run_activity_must_match_the_provenance_block(run):
    run["prov:wasGeneratedBy"] = {"@id": "#other"}
    assert has(validate(run), "prov:wasGeneratedBy", "names '#other'")


def test_every_input_of_a_run_has_an_id(run):
    run["provenance"]["prov:used"].append({"@type": "prov:Entity"})
    assert any("prov:used/" in i.path for i in validate(run).errors)


@pytest.mark.parametrize(("key", "value", "message"), [
    ("@type", "wrong", "'prov:Activity' was expected"),
    ("prov:used", None, "is not of type 'array'"),
    ("prov:startedAtTime", "2026-02-30T00:00:00Z", "is not a 'date-time'"),
    ("prov:endedAtTime", "2026-11-25T14:45:00", "is not a 'date-time'"),
])
def test_run_provenance_values_must_match_their_expected_types(run, key, value, message):
    run["provenance"][key] = value
    validator = Draft202012Validator(load_schema("fdo", "1"), format_checker=FormatChecker())
    assert not validator.is_valid(run)
    assert has(validate(run), f"provenance/{key}", message)


def test_a_run_can_have_no_inputs_and_use_a_timestamp_with_an_offset(run):
    run["provenance"]["prov:used"] = []
    run["provenance"]["prov:startedAtTime"] = "2026-09-02T19:27:17.125+02:00"
    assert validate(run).valid


@pytest.mark.parametrize("key", ["episerveBenchmark", "accessRights"])
def test_a_benchmark_requires_its_profile_fields(benchmark, key):
    del benchmark["profile"][key]
    assert has(validate(benchmark), "profile", f"'{key}' is a required property")


def test_a_benchmark_requires_identity_commit_and_file_metadata(benchmark):
    benchmark["profile"]["episerveBenchmark"] = {}
    result = validate(benchmark)
    for key in ("id", "data_commit", "files"):
        assert has(result, "profile/episerveBenchmark", f"'{key}' is a required property")


def test_a_benchmark_needs_input_and_reference_but_definition_is_optional(benchmark):
    files = benchmark["profile"]["episerveBenchmark"]["files"]
    del files["definition"]
    assert validate(benchmark).valid
    del files["reference"]
    del files["input"]["rows"]
    result = validate(benchmark)
    assert has(result, "profile/episerveBenchmark/files", "'reference' is a required property")
    assert has(result, "profile/episerveBenchmark/files/input", "'rows' is a required property")


def test_a_benchmark_lists_its_sources_by_qid(benchmark):
    benchmark["provenance"]["prov:wasDerivedFrom"] = ["Q1", {"@id": "Q2"}]
    assert validate(benchmark).valid
    benchmark["provenance"]["prov:wasDerivedFrom"].append("nonsense")
    result = validate(benchmark)
    assert [i.path for i in result.errors] == ["provenance/prov:wasDerivedFrom"]


def test_a_finalized_benchmark_should_be_immutable(benchmark):
    benchmark["kernel"]["immutable"] = False
    assert has(validate(benchmark), "kernel/immutable", "immutable", "warning")


def test_checks_cope_with_malformed_documents():
    for doc in ({"@type": "DigitalObject", "kernel": []}, {"@type": "DigitalObject", "kernel": {}, "provenance": 3, "profile": "x"}):
        assert validate(doc, spec="fdo").errors
