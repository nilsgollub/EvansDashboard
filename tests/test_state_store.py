import os

from state_store import load_last_fix, save_last_fix


def test_roundtrip(tmp_path):
    path = str(tmp_path / "last_fix.json")
    assert save_last_fix(46.779, 7.152, altitude=620.0, sats=8, t=1234.5, path=path) is True
    loaded = load_last_fix(path)
    assert loaded == {
        "lat": 46.779,
        "lon": 7.152,
        "altitude": 620.0,
        "sats": 8,
        "time": 1234.5,
    }


def test_missing_file_returns_none(tmp_path):
    assert load_last_fix(str(tmp_path / "nope.json")) is None


def test_malformed_file_returns_none(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("not json {")
    assert load_last_fix(str(path)) is None


def test_non_dict_json_returns_none(tmp_path):
    # Gueltiges JSON, aber kein Objekt -> data.get(...) wuerde sonst AttributeError werfen.
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]")
    assert load_last_fix(str(path)) is None


def test_save_without_position_is_noop(tmp_path):
    path = str(tmp_path / "x.json")
    assert save_last_fix(None, 7.152, path=path) is False
    assert not os.path.exists(path)


def test_save_does_not_leave_tmp(tmp_path):
    # Erfolgreiches Speichern darf keine ".tmp"-Restdatei hinterlassen.
    path = str(tmp_path / "fix.json")
    save_last_fix(46.0, 7.0, t=1.0, path=path)
    assert os.path.exists(path)
    assert not os.path.exists(path + ".tmp")


def test_save_creates_parent_directory(tmp_path):
    # state_store legt fehlende Verzeichnisse an (z.B. ~/.evans-dashboard).
    path = str(tmp_path / "new_dir" / "fix.json")
    assert save_last_fix(46.0, 7.0, t=1.0, path=path) is True
    assert os.path.exists(path)
