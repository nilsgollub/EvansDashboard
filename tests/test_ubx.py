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
