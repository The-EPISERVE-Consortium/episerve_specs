import json

from episerve_specs.cli import main


def write(tmp_path, name, doc):
    path = tmp_path / name
    path.write_text(json.dumps(doc) if not isinstance(doc, str) else doc)
    return str(path)


def test_valid_file_exits_0(tmp_path, timesfm, capsys):
    assert main([write(tmp_path, "fdo.json", timesfm)]) == 0
    assert "OK" in capsys.readouterr().out


def test_invalid_file_exits_1(tmp_path, timesfm, capsys):
    del timesfm["episerve:parameters"]
    assert main([write(tmp_path, "fdo.json", timesfm)]) == 1
    assert "FAILED" in capsys.readouterr().out


def test_strict_fails_on_warnings(tmp_path, timesfm):
    path = write(tmp_path, "fdo.json", timesfm)  # warns: license, resources
    assert main([path]) == 0
    assert main([path, "--strict"]) == 1


def test_json_output(tmp_path, timesfm, capsys):
    main([write(tmp_path, "fdo.json", timesfm), "--json"])
    [entry] = json.loads(capsys.readouterr().out)
    assert entry["spec"] == "model-card" and entry["valid"] is True and entry["ok"] is True


def test_explicit_spec(tmp_path, timesfm, capsys):
    del timesfm["conformsTo"]
    assert main([write(tmp_path, "fdo.json", timesfm), "--spec", "model-card"]) == 1
    assert "'conformsTo' is a required property" in capsys.readouterr().out


def test_unreadable_file_exits_2(tmp_path):
    assert main([write(tmp_path, "bad.json", "{not json")]) == 2
    assert main([str(tmp_path / "missing.json")]) == 2


def test_unknown_spec_exits_2(tmp_path, timesfm):
    assert main([write(tmp_path, "fdo.json", timesfm), "--spec", "nope"]) == 2


def test_list(capsys):
    assert main(["--list"]) == 0
    assert "model-card: v1" in capsys.readouterr().out
