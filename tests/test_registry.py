import pytest
from jsonschema import Draft202012Validator

from episerve_specs import available_specs, detect_spec, load_schema, schema_url, validate


def test_model_card_is_registered():
    assert available_specs()["model-card"] == ["1"]


@pytest.mark.parametrize("spec,versions", list(available_specs().items()))
def test_every_schema_is_valid_json_schema_with_matching_id(spec, versions):
    for version in versions:
        schema = load_schema(spec, version)
        Draft202012Validator.check_schema(schema)
        assert schema["$id"] == schema_url(spec, version)


def test_detect_spec_from_string_list_and_object():
    url = schema_url("model-card", "1")
    assert detect_spec({"conformsTo": url}) == ("model-card", "1")
    assert detect_spec({"conformsTo": ["https://example.org/x", url]}) == ("model-card", "1")
    assert detect_spec({"conformsTo": {"@id": url}}) == ("model-card", "1")


def test_detect_spec_none():
    assert detect_spec({}) is None
    assert detect_spec({"conformsTo": "https://api.episerve.zib.de/schemas/unknown-thing/v1.json"}) is None
    assert detect_spec(["not", "a", "dict"]) is None


def test_validate_without_conforms_to_is_an_error():
    result = validate({"name": "x"})
    assert not result.valid
    assert result.spec is None
    assert result.errors[0].path == "conformsTo"


def test_explicit_spec_overrides_detection(timesfm):
    del timesfm["conformsTo"]
    result = validate(timesfm, spec="model-card")
    assert result.spec == "model-card" and result.version == "1"
    assert any(e.message == "'conformsTo' is a required property" for e in result.errors)


def test_unknown_spec_or_version_raises():
    with pytest.raises(ValueError, match="unknown spec"):
        validate({}, spec="nope")
    with pytest.raises(ValueError, match="no version 9"):
        validate({}, spec="model-card", version="9")


def test_non_object_document():
    result = validate([1, 2], spec="model-card")
    assert not result.valid


def test_result_dict_names_the_validator(timesfm):
    d = validate(timesfm).to_dict()
    assert d["valid"] is True
    assert d["validator"].startswith("episerve-specs ")
    assert {i["severity"] for i in d["issues"]} <= {"error", "warning"}
