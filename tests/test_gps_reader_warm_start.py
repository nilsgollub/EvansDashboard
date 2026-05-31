import os
import time

import pytest

import gps_reader
from state_store import save_last_fix


class FakeSerial:
    def __init__(self):
        self.is_open = True
        self.writes = []

    def write(self, data):
        self.writes.append(bytes(data))

    def flush(self):
        pass


@pytest.fixture
def reader_with_serial():
    r = gps_reader.GPSReader()
    r.serial_conn = FakeSerial()
    return r


def _capture_aid_ini_kwargs(monkeypatch, tmp_path, age_seconds):
    """Speichert einen Fix mit einem Alter von `age_seconds` Sekunden und
    faengt die kwargs an `send_aid_ini` ein."""
    path = str(tmp_path / "last_fix.json")
    save_last_fix(46.0, 7.0, t=time.time() - age_seconds, path=path)
    monkeypatch.setenv("EVANS_STATE_DIR", str(tmp_path))
    # state_store.LAST_FIX_PATH wurde beim Import festgelegt - umbiegen
    monkeypatch.setattr(gps_reader, "load_last_fix", lambda: __import__("state_store").load_last_fix(path))

    captured = {}

    def fake_send(serial_conn, lat, lon, **kwargs):
        captured["lat"] = lat
        captured["lon"] = lon
        captured.update(kwargs)
        return True

    monkeypatch.setattr(gps_reader, "send_aid_ini", fake_send)
    return captured


def test_positive_age_within_window_injects_time(tmp_path, monkeypatch, reader_with_serial):
    captured = _capture_aid_ini_kwargs(monkeypatch, tmp_path, age_seconds=60)
    reader_with_serial._inject_warm_start_hint()
    assert captured["inject_time"] is True


def test_negative_age_skips_time_injection(tmp_path, monkeypatch, reader_with_serial):
    # Pi-Uhr lag vor dem gespeicherten Fix (fake-hwclock-Drift nach hartem Aus).
    # Wir duerfen dem GPS in dem Fall keine falsche Zeit unterschieben.
    captured = _capture_aid_ini_kwargs(monkeypatch, tmp_path, age_seconds=-200)
    reader_with_serial._inject_warm_start_hint()
    assert captured["inject_time"] is False
    # Position wird weiter mitgegeben
    assert captured["lat"] == 46.0
    assert captured["lon"] == 7.0


def test_too_old_fix_skips_time_injection(tmp_path, monkeypatch, reader_with_serial):
    # Aelter als 6 h -> Zeit waere ohnehin nicht mehr brauchbar.
    captured = _capture_aid_ini_kwargs(monkeypatch, tmp_path, age_seconds=7 * 3600)
    reader_with_serial._inject_warm_start_hint()
    assert captured["inject_time"] is False


def test_no_stored_fix_is_noop(tmp_path, monkeypatch, reader_with_serial):
    # Keine last_fix.json vorhanden -> kein send_aid_ini-Aufruf.
    monkeypatch.setattr(gps_reader, "load_last_fix", lambda: None)
    called = []
    monkeypatch.setattr(gps_reader, "send_aid_ini", lambda *a, **kw: called.append(1))
    reader_with_serial._inject_warm_start_hint()
    assert called == []


# kleines Aufraeumen falls Tests parallel laufen
@pytest.fixture(autouse=True)
def _cleanup_env(monkeypatch):
    monkeypatch.delenv("EVANS_TTFF_LOG", raising=False)
    yield
    if os.environ.get("EVANS_TTFF_LOG"):
        try:
            os.remove(os.environ["EVANS_TTFF_LOG"])
        except OSError:
            pass
