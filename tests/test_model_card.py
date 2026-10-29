import pytest

from episerve_specs import validate

from conftest import EXAMPLE_NAMES, load_example


def messages(result, severity="error"):
    return [f"{i.path}: {i.message}" for i in result.issues if i.severity == severity]


def has(result, path, text, severity="error"):
    return any(i.path == path and text in i.message and i.severity == severity for i in result.issues)


# ── examples ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_examples_are_valid(name):
    result = validate(load_example(name))
    assert result.valid, messages(result)


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_examples_only_warn_about_what_is_unknown(name):
    # Neither model repo has a license, and nobody has measured cpu/memory yet.
    assert sorted(i.path for i in validate(load_example(name)).warnings) == ["episerve:resources", "license"]


# ── required sections ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("key", ["episerve:task", "episerve:parameters", "episerve:inputs", "episerve:outputs", "url"])
def test_required_sections(timesfm, key):
    del timesfm[key]
    assert f"'{key}' is a required property" in [i.message for i in validate(timesfm).errors]


def test_unknown_episerve_key(timesfm):
    timesfm["episerve:extra"] = {}
    assert has(validate(timesfm), "episerve:extra", "unknown key")


def test_other_schema_org_keys_are_allowed(timesfm):
    timesfm["keywords"] = ["influenza"]
    assert validate(timesfm).valid


def test_image_with_tag_is_rejected(timesfm):
    timesfm["url"] += ":latest"
    assert any(i.path == "url" for i in validate(timesfm).errors)


# ── identity ──────────────────────────────────────────────────────────────────

def test_repository_name_must_match_image(timesfm):
    timesfm["codeRepository"] = "https://github.com/The-EPISERVE-Consortium/other"
    assert has(validate(timesfm), "codeRepository", "differs from the image name", "warning")


def test_non_ghcr_image_warns(timesfm):
    timesfm["url"] = "docker.io/someone/model__prediction__generic__timesfm"
    assert has(validate(timesfm), "url", "not a ghcr.io image", "warning")


# ── parameters ────────────────────────────────────────────────────────────────

def test_parameter_needs_description(timesfm):
    del timesfm["episerve:parameters"]["properties"]["prediction_length"]["description"]
    assert has(validate(timesfm), "episerve:parameters/properties/prediction_length", "'description' is a required property")


def test_parameter_type_is_restricted(timesfm):
    timesfm["episerve:parameters"]["properties"]["prediction_length"]["type"] = "array"
    assert any(i.path == "episerve:parameters/properties/prediction_length/type" for i in validate(timesfm).errors)


def test_parameter_name_pattern(timesfm):
    p = timesfm["episerve:parameters"]["properties"]
    p["Bad-Name"] = {"type": "integer", "description": "x", "default": 1}
    assert any(i.path == "episerve:parameters/properties" and "Bad-Name" in i.message for i in validate(timesfm).errors)


def test_required_must_be_declared(timesfm):
    timesfm["episerve:parameters"]["required"].append("nope")
    assert has(validate(timesfm), "episerve:parameters/required/2", "not declared")


def test_required_parameter_with_default(timesfm):
    timesfm["episerve:parameters"]["properties"]["history_length"]["default"] = 10
    assert has(validate(timesfm), "episerve:parameters/properties/history_length/default", "must not have a default")


def test_default_must_fit(timesfm):
    timesfm["episerve:parameters"]["properties"]["prediction_offset"]["default"] = -1
    assert has(validate(timesfm), "episerve:parameters/properties/prediction_offset/default", "does not fit")


def test_bounds_order(timesfm):
    p = timesfm["episerve:parameters"]["properties"]["prediction_length"]
    p["minimum"], p["maximum"] = 600, 512
    assert has(validate(timesfm), "episerve:parameters/properties/prediction_length", "lower bound is greater")


def test_optional_parameter_without_default_warns(timesfm):
    del timesfm["episerve:parameters"]["properties"]["prediction_offset"]["default"]
    assert has(validate(timesfm), "episerve:parameters/properties/prediction_offset", "without a default", "warning")


def test_open_parameters_warn(timesfm):
    timesfm["episerve:parameters"]["additionalProperties"] = True
    assert has(validate(timesfm), "episerve:parameters/additionalProperties", "misspelt", "warning")


# ── old parameter list ────────────────────────────────────────────────────────

def test_additional_property_is_rejected(timesfm):
    timesfm["additionalProperty"] = [{"name": "history_length"}]
    assert has(validate(timesfm), "additionalProperty", "declare the parameters in episerve:parameters")


# ── task ──────────────────────────────────────────────────────────────────────

def test_parameter_role_must_exist(timesfm):
    timesfm["episerve:task"]["parameterRoles"]["horizon"] = "steps"
    assert has(validate(timesfm), "episerve:task/parameterRoles/horizon", "not a declared parameter")


def test_horizon_role_is_required(timesfm):
    del timesfm["episerve:task"]["parameterRoles"]["horizon"]
    assert not validate(timesfm).valid


def test_probabilistic_must_match_outputs(baseline):
    baseline["episerve:task"]["probabilistic"] = True
    assert has(validate(baseline), "episerve:task/probabilistic", "no output column has role quantile")


def test_not_probabilistic_with_quantiles(timesfm):
    timesfm["episerve:task"]["probabilistic"] = False
    assert has(validate(timesfm), "episerve:task/probabilistic", "an output column has role quantile")


def test_covariates_must_match_inputs(timesfm):
    timesfm["episerve:task"]["covariates"] = True
    assert has(validate(timesfm), "episerve:task/covariates", "no input column has role covariate")


# ── inputs ────────────────────────────────────────────────────────────────────

def test_column_needs_name_or_position(timesfm):
    del timesfm["episerve:inputs"][0]["columns"][0]["position"]
    assert has(validate(timesfm), "episerve:inputs/0/columns/0", "needs a name or a position")


def test_duplicate_position(timesfm):
    timesfm["episerve:inputs"][0]["columns"][1]["position"] = 0
    assert has(validate(timesfm), "episerve:inputs/0/columns/1/position", "also used")


def test_duplicate_column_name(baseline):
    baseline["episerve:inputs"][0]["columns"][1]["name"] = "Kalenderwoche"
    assert has(validate(baseline), "episerve:inputs/0/columns/1/name", "also used")


def test_config_json_is_not_an_input(timesfm):
    timesfm["episerve:inputs"][0]["file"] = "config.json"
    assert has(validate(timesfm), "episerve:inputs/0/file", "written by the platform")


def test_two_time_columns(baseline):
    baseline["episerve:inputs"][0]["columns"][1]["role"] = "time"
    assert has(validate(baseline), "episerve:inputs/0/columns", "more than one column with role time")


def test_unknown_column_type(timesfm):
    timesfm["episerve:inputs"][0]["columns"][1]["type"] = "float"
    assert not validate(timesfm).valid


def test_exact_columns_need_contiguous_positions(timesfm):
    timesfm["episerve:inputs"][0]["columns"][1]["position"] = 2
    assert has(validate(timesfm), "episerve:inputs/0/columns", "without gaps")


# ── outputs ───────────────────────────────────────────────────────────────────

def test_quantile_needs_level(timesfm):
    del timesfm["episerve:outputs"][0]["columns"][3]["level"]
    assert has(validate(timesfm), "episerve:outputs/0/columns/3", "needs a level")


def test_level_only_on_quantile(baseline):
    baseline["episerve:outputs"][0]["columns"][2]["level"] = 0.5
    assert has(validate(baseline), "episerve:outputs/0/columns/2/level", "only a quantile column")


def test_level_range(timesfm):
    timesfm["episerve:outputs"][0]["columns"][3]["level"] = 10
    assert not validate(timesfm).valid


def test_duplicate_level(timesfm):
    timesfm["episerve:outputs"][0]["columns"][4]["level"] = 0.1
    assert has(validate(timesfm), "episerve:outputs/0/columns/4/level", "also used")


def test_name_or_name_from(timesfm):
    timesfm["episerve:outputs"][0]["columns"][0]["name"] = "x"
    assert has(validate(timesfm), "episerve:outputs/0/columns/0", "exactly one of name and nameFrom")


def test_name_from_unknown_input_role(timesfm):
    timesfm["episerve:outputs"][0]["columns"][0]["nameFrom"]["inputRole"] = "group"
    assert has(validate(timesfm), "episerve:outputs/0/columns/0/nameFrom/inputRole", "no input column has role group")


def test_run_log_is_not_an_output(timesfm):
    timesfm["episerve:outputs"][0]["file"] = "run.log"
    assert has(validate(timesfm), "episerve:outputs/0/file", "written by the platform")


def test_hubverse_roles_only(timesfm):
    timesfm["episerve:outputs"][0]["columns"][2]["role"] = "forecast"
    assert not validate(timesfm).valid


# ── resources / documentation ─────────────────────────────────────────────────

def test_memory_quantity(timesfm):
    timesfm["episerve:resources"]["memory"] = "4 GB"
    assert any(i.path == "episerve:resources/memory" for i in validate(timesfm).errors)


def test_measured_resources_silence_the_warning(timesfm):
    timesfm["episerve:resources"].update(cpu="2", memory="4Gi")
    assert not any(i.path == "episerve:resources" for i in validate(timesfm).warnings)


def test_missing_documentation_warns(timesfm):
    del timesfm["episerve:documentation"]
    result = validate(timesfm)
    assert result.valid
    assert has(result, "episerve:documentation/method", "missing", "warning")


# ── robustness ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("key", ["episerve:task", "episerve:parameters", "episerve:inputs", "episerve:outputs"])
@pytest.mark.parametrize("bad", [None, 3, "x", [1], {"a": 1}])
def test_malformed_sections_do_not_crash(timesfm, key, bad):
    timesfm[key] = bad
    validate(timesfm)  # reports errors, never raises


# ── optional input columns ────────────────────────────────────────────────────

def test_optional_input_column(timesfm):
    timesfm["episerve:inputs"][0]["columns"].append(
        {"position": 2, "role": "other", "type": "number", "required": False})
    timesfm["episerve:inputs"][0]["additionalColumns"] = True
    assert validate(timesfm).valid


def test_input_column_required_must_be_boolean(timesfm):
    timesfm["episerve:inputs"][0]["columns"][1]["required"] = "no"
    assert any(i.path == "episerve:inputs/0/columns/1/required" for i in validate(timesfm).errors)
