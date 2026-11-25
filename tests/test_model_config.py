import pytest

from episerve_specs import InvalidParameterSchema, check_model_config, model_config_defaults


def paths(issues):
    return [(i.path, i.message) for i in issues]


def test_valid_config(timesfm):
    assert check_model_config(timesfm, {"history_length": 10, "prediction_length": 4}) == []


def test_takes_the_parameters_section_alone(timesfm):
    params = timesfm["episerve:parameters"]
    assert check_model_config(params, {"history_length": 10, "prediction_length": 4}) == []


def test_missing_required(timesfm):
    issues = check_model_config(timesfm, {"history_length": 10})
    assert paths(issues) == [("", "'prediction_length' is a required property")]


def test_bounds_and_types(timesfm):
    issues = check_model_config(timesfm, {"history_length": 2, "prediction_length": "4"})
    assert [i.path for i in issues] == ["history_length", "prediction_length"]
    assert all(i.severity == "error" for i in issues)


def test_null_is_not_a_value(timesfm):
    issues = check_model_config(timesfm, {"history_length": None, "prediction_length": 4})
    assert [i.path for i in issues] == ["history_length"]


def test_unknown_key(timesfm):
    issues = check_model_config(timesfm, {"history_length": 10, "prediction_length": 4, "horizon": 3})
    assert len(issues) == 1 and "'horizon' was unexpected" in issues[0].message


def test_config_must_be_an_object(timesfm):
    assert len(check_model_config(timesfm, [1])) == 1


def test_defaults(timesfm, baseline):
    assert model_config_defaults(timesfm) == {"prediction_offset": 0}
    assert model_config_defaults(baseline["episerve:parameters"]) == {"horizon_weeks": 4, "n_reference_weeks": 4}


@pytest.mark.parametrize("parameters", [[], None, {"properties": {"x": {"type": "typo"}}}])
def test_invalid_parameter_declarations_raise_a_distinct_error(parameters):
    with pytest.raises(InvalidParameterSchema, match="JSON Schema"):
        check_model_config({"episerve:parameters": parameters}, {"x": 1})


def test_invalid_schema_reference_is_reported_as_a_declaration_error():
    with pytest.raises(InvalidParameterSchema, match="unresolved schema reference"):
        check_model_config({"$ref": "#/$defs/missing"}, {})


def test_local_schema_references_still_validate():
    parameters = {"$defs": {"count": {"type": "integer"}}, "properties": {"x": {"$ref": "#/$defs/count"}}}
    assert not check_model_config(parameters, {"x": 1})
    assert check_model_config(parameters, {"x": "wrong"})[0].path == "x"
