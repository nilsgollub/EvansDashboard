import struct
from datetime import datetime, timezone

import ubx


class FakeSerial:
    """Minimaler serieller Stub, der geschriebene Bytes mitschneidet."""

    def __init__(self):
        self.is_open = True
        self.writes = []

    def write(self, data):
        self.writes.append(bytes(data))

    def flush(self):
        pass


def _checksum(payload_msg):
    cka = ckb = 0
    for b in payload_msg:
        cka = (cka + b) & 0xFF
        ckb = (ckb + cka) & 0xFF
    return cka, ckb


def test_build_ubx_packet_framing_and_checksum():
    payload = b"\x01\x02\x03"
    packet = ubx.build_ubx_packet(0x06, 0x24, payload)
    # Sync-Bytes
    assert packet[:2] == b"\xb5\x62"
    # Class / ID / Length (little-endian)
    assert packet[2] == 0x06
    assert packet[3] == 0x24
    assert packet[4] == len(payload) & 0xFF
    assert packet[5] == (len(payload) >> 8) & 0xFF
    # Pruefsumme ueber class..payload
    cka, ckb = _checksum(packet[2:-2])
    assert packet[-2] == cka
    assert packet[-1] == ckb


def test_nav5_payload_is_36_bytes():
    # CFG-NAV5 muss exakt 36 Byte Payload haben (haeufige Copy-Paste-Fehlerquelle)
    assert len(ubx.NAV5_PAYLOAD) == 36


def test_configure_neo7m_sends_full_sequence():
    fake = FakeSerial()
    ubx.configure_neo7m(fake, log=None)
    # 9 Konfigurationsschritte (NAV5, SBAS, RATE, 4x MSG, AOP, CFG - GNSS ist deaktiviert)
    assert len(fake.writes) == 9
    # Jedes Paket beginnt mit den UBX-Sync-Bytes
    assert all(pkt[:2] == b"\xb5\x62" for pkt in fake.writes)


def test_configure_neo7m_noop_without_connection():
    ubx.configure_neo7m(None, log=None)  # darf nicht werfen


# --- AID-INI -------------------------------------------------------------------


def _unpack_aid_ini(packet):
    """Liefert (header_dict, payload_fields) fuer ein AID-INI-Paket."""
    assert packet[:2] == b"\xb5\x62"
    assert packet[2] == 0x0B
    assert packet[3] == 0x01
    length = packet[4] | (packet[5] << 8)
    assert length == 48
    payload = packet[6:-2]
    assert len(payload) == 48
    fields = struct.unpack("<iiiIHHIiIIiII", payload)
    keys = [
        "lat",
        "lon",
        "alt_cm",
        "pos_acc",
        "tm_cfg",
        "wno_or_date",
        "tow_or_time",
        "tow_ns",
        "t_acc_ms",
        "t_acc_ns",
        "clk_d",
        "clk_d_acc",
        "flags",
    ]
    return dict(zip(keys, fields))


def test_aid_ini_payload_is_48_bytes_and_well_framed():
    dt = datetime(2026, 5, 30, 12, 34, 56, tzinfo=timezone.utc)
    packet = ubx.build_aid_ini(46.779, 7.152, alt_m=620.0, dt_utc=dt)
    fields = _unpack_aid_ini(packet)
    # Pruefsumme
    cka, ckb = _checksum(packet[2:-2])
    assert packet[-2] == cka
    assert packet[-1] == ckb
    # Position
    assert fields["lat"] == round(46.779 * 1e7)
    assert fields["lon"] == round(7.152 * 1e7)
    assert fields["alt_cm"] == 62000
    # Flags: pos + time + lla + utc
    expected_flags = ubx.AID_INI_FLAG_POS | ubx.AID_INI_FLAG_TIME | ubx.AID_INI_FLAG_LLA | ubx.AID_INI_FLAG_UTC
    assert fields["flags"] == expected_flags


def test_aid_ini_utc_time_packing():
    dt = datetime(2026, 5, 30, 12, 34, 56, tzinfo=timezone.utc)
    packet = ubx.build_aid_ini(46.779, 7.152, dt_utc=dt)
    fields = _unpack_aid_ini(packet)
    # wnoOrDate: (yy << 8) | mm  --> (26 << 8) | 5 = 0x1A05
    assert fields["wno_or_date"] == (26 << 8) | 5
    # towOrTime: (day<<24) | (hour<<16) | (min<<8) | sec
    assert fields["tow_or_time"] == (30 << 24) | (12 << 16) | (34 << 8) | 56


def test_aid_ini_without_time_clears_time_fields_and_flags():
    dt = datetime(2026, 5, 30, 12, 34, 56, tzinfo=timezone.utc)
    packet = ubx.build_aid_ini(46.0, 7.0, dt_utc=dt, inject_time=False)
    fields = _unpack_aid_ini(packet)
    assert fields["wno_or_date"] == 0
    assert fields["tow_or_time"] == 0
    assert fields["t_acc_ms"] == 0
    assert fields["flags"] & ubx.AID_INI_FLAG_TIME == 0
    assert fields["flags"] & ubx.AID_INI_FLAG_UTC == 0
    # Position-Flags bleiben gesetzt
    assert fields["flags"] & ubx.AID_INI_FLAG_POS
    assert fields["flags"] & ubx.AID_INI_FLAG_LLA


def test_send_aid_ini_writes_to_serial():
    fake = FakeSerial()
    ok = ubx.send_aid_ini(fake, 46.0, 7.0, inject_time=False)
    assert ok is True
    assert len(fake.writes) == 1
    assert fake.writes[0][:4] == b"\xb5\x62\x0b\x01"


def test_send_aid_ini_noop_without_connection():
    assert ubx.send_aid_ini(None, 46.0, 7.0) is False
