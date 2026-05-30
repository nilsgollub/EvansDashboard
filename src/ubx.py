"""Gemeinsame U-Blox NEO-7M UBX-Logik.

Einzige Quelle der Wahrheit fuer Paket-Framing und die NEO-7M-Konfiguration,
damit gps_reader.py und das Diagnose-Tool test_gps.py garantiert identische
Bytes senden.
"""

import struct
from datetime import datetime, timezone


def build_ubx_packet(msg_class, msg_id, payload):
    """Baut ein vollstaendiges UBX-Paket inkl. Sync-Bytes und Fletcher-Pruefsumme."""
    msg = bytes([msg_class, msg_id, len(payload) & 0xFF, (len(payload) >> 8) & 0xFF]) + payload
    cka = 0
    ckb = 0
    for b in msg:
        cka = (cka + b) & 0xFF
        ckb = (ckb + cka) & 0xFF
    return bytes([0xB5, 0x62]) + msg + bytes([cka, ckb])


def send_ubx_msg(serial_conn, msg_class, msg_id, payload):
    """Sendet ein UBX-Kommando ueber die serielle Verbindung (No-op ohne offene Verbindung)."""
    if not serial_conn or not serial_conn.is_open:
        return
    serial_conn.write(build_ubx_packet(msg_class, msg_id, payload))
    serial_conn.flush()


# --- NEO-7M Konfigurations-Payloads (Reihenfolge ist relevant) ---

# 1. CFG-NAV5: Automotive-Modus (DynModel 4)
NAV5_PAYLOAD = (
    b"\x01\x00"  # Mask (bit 0: DynModel only)
    b"\x04"  # DynModel (4 = Automotive)
    b"\x03"  # FixMode (3 = Auto 2D/3D)
    b"\x00\x00\x00\x00"  # FixedAlt
    b"\x00\x00\x00\x00"  # FixedAltVar
    b"\x0a"  # MinElev (10 Grad)
    b"\x00"  # DrLimit
    b"\x00\x00"  # pDop
    b"\x00\x00"  # tDop
    b"\x00\x00"  # pAcc
    b"\x00\x00"  # tAcc
    b"\x00"  # staticHoldThresh
    b"\x00"  # dgpsTimeOut
    # Reserved: explizites '+' statt impliziter Konkatenation, da '*' sonst den
    # gesamten Literal-Block multipliziert (CFG-NAV5 muss exakt 36 Byte sein).
    + b"\x00" * 12
)

# 2. CFG-SBAS: SBAS deaktivieren
SBAS_OFF_PAYLOAD = (
    b"\x00"  # mode: Disabled
    b"\x00"  # usage: None
    b"\x00"  # maxSBAS: 0
    b"\x00"  # scanmode2
    b"\x00\x00\x00\x00"  # scanmode1: None
)

# 2b. CFG-GNSS: GPS + GLONASS aktivieren (stabiler Doppler/Speed)
GNSS_PAYLOAD = (
    b"\x00"  # msgVer: 0
    b"\x20"  # numTrkChHw: 32
    b"\x20"  # numTrkChUse: 32
    b"\x02"  # numConfigBlocks: 2
    # Block 1: GPS
    b"\x00"  # gnssId: 0 (GPS)
    b"\x08"  # resTrkCh: 8
    b"\x10"  # maxTrkCh: 16
    b"\x01"  # flags: enabled
    # Block 2: GLONASS
    b"\x06"  # gnssId: 6 (GLONASS)
    b"\x08"  # resTrkCh: 8
    b"\x0e"  # maxTrkCh: 14
    b"\x01"  # flags: enabled
)

# 3. CFG-RATE: 2 Hz (500 ms) - 5 Hz fuehrt beim NEO-7M zu Pufferueberlaeufen
RATE_PAYLOAD = b"\xf4\x01\x01\x00\x00\x00"

# 4. CFG-MSG: NMEA-Datenmuell filtern (nur RMC/GGA/GSV behalten)
MSG_GLL_OFF = b"\xf0\x01\x00\x00\x00\x00\x00\x00"
MSG_GSA_OFF = b"\xf0\x02\x00\x00\x00\x00\x00\x00"
MSG_VTG_OFF = b"\xf0\x05\x00\x00\x00\x00\x00\x00"
MSG_GSV_RATE = b"\xf0\x03\x05\x05\x05\x05\x05\x05"  # GSV nur jeden 5. Zyklus

# 5. CFG-AOP: AssistNow Autonomous (schneller Fix ohne Internet)
AOP_PAYLOAD = b"\x01\x00\x00\x00"

# 6. CFG-CFG: Konfiguration dauerhaft im Flash sichern
CFG_SAVE_PAYLOAD = b"\x00\x00\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x01"


def configure_neo7m(serial_conn, log=print):
    """Sendet die komplette NEO-7M-Optimierungssequenz an das Modul.

    Jeder Schritt ist gekapselt, damit ein Fehler die uebrigen nicht blockiert.
    """
    steps = [
        (0x06, 0x24, NAV5_PAYLOAD, "CFG-NAV5 (Automotive, 10 Grad Elevation)"),
        (0x06, 0x16, SBAS_OFF_PAYLOAD, "CFG-SBAS (aus)"),
        # (0x06, 0x3E, GNSS_PAYLOAD, "CFG-GNSS (GPS+GLONASS)"), # Disabled: Neo-7M does not support concurrent GPS+GLONASS
        (0x06, 0x08, RATE_PAYLOAD, "CFG-RATE (2 Hz)"),
        (0x06, 0x01, MSG_GLL_OFF, "CFG-MSG (GLL off)"),
        (0x06, 0x01, MSG_GSA_OFF, "CFG-MSG (GSA off)"),
        (0x06, 0x01, MSG_VTG_OFF, "CFG-MSG (VTG off)"),
        (0x06, 0x01, MSG_GSV_RATE, "CFG-MSG (GSV rate=5)"),
        (0x06, 0x33, AOP_PAYLOAD, "CFG-AOP (AssistNow Autonomous)"),
        (0x06, 0x09, CFG_SAVE_PAYLOAD, "CFG-CFG (Save Config)"),
    ]
    for msg_class, msg_id, payload, label in steps:
        try:
            send_ubx_msg(serial_conn, msg_class, msg_id, payload)
            if log:
                log(f"[GPS] UBX {label} gesendet.")
        except Exception as e:  # noqa: BLE001 - ein Schritt darf den Rest nicht stoppen
            if log:
                log(f"[GPS] Fehler bei {label}: {e}")


# --- AID-INI: Warm-Start-Hinweis (UBX 0x0B 0x01) ---------------------------------
#
# Wir injizieren letzte bekannte Position + grobe UTC-Zeit ins NEO-7M, damit es
# nicht blind nach allen Satelliten suchen muss. Macht aus einem Cold Start einen
# Warm Start, voellig unabhaengig von der BBR-Stuetzbatterie des Moduls.

AID_INI_FLAG_POS = 1 << 0
AID_INI_FLAG_TIME = 1 << 1
AID_INI_FLAG_LLA = 1 << 5  # Position als geodaetisch (lat/lon/alt) statt ECEF
AID_INI_FLAG_UTC = 1 << 10  # Zeit als UTC (statt GPS week/TOW)


def build_aid_ini(
    lat_deg,
    lon_deg,
    alt_m=0.0,
    dt_utc=None,
    pos_acc_cm=1_000_000,  # 10 km - konservativ, GPS-Suchellipse darf nicht zu eng sein
    t_acc_ms=3_600_000,  # 1 h - faengt fake-hwclock-Drift ab
    inject_time=True,
):
    """Baut ein UBX-AID-INI-Paket (48 Byte Payload) im LLA/UTC-Modus.

    Position kommt aus der letzten gespeicherten Lage; Zeit aus der Pi-Systemuhr.
    Falls die Pi-Uhr offensichtlich unsicher ist, kann der Aufrufer
    ``inject_time=False`` setzen - dann wird nur die Position uebergeben.
    """
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)

    lat_i = int(round(lat_deg * 1e7))
    lon_i = int(round(lon_deg * 1e7))
    alt_cm = int(round(alt_m * 100.0))

    flags = AID_INI_FLAG_POS | AID_INI_FLAG_LLA
    if inject_time:
        flags |= AID_INI_FLAG_TIME | AID_INI_FLAG_UTC
        # wnoOrDate: yymm als (year_yy * 256 + month), LE in U2.
        year_yy = dt_utc.year % 100
        wno_or_date = (year_yy << 8) | dt_utc.month
        # towOrTime: day << 24 | hour << 16 | minute << 8 | second
        tow_or_time = (dt_utc.day << 24) | (dt_utc.hour << 16) | (dt_utc.minute << 8) | dt_utc.second
        t_acc_ms_used = int(t_acc_ms)
    else:
        wno_or_date = 0
        tow_or_time = 0
        t_acc_ms_used = 0

    payload = struct.pack(
        "<iiiIHHIiIIiII",
        lat_i,  # ecefXOrLat
        lon_i,  # ecefYOrLon
        alt_cm,  # ecefZOrAlt
        int(pos_acc_cm),  # posAcc
        0,  # tmCfg
        wno_or_date,  # wnoOrDate
        tow_or_time,  # towOrTime
        0,  # towNs
        t_acc_ms_used,  # tAccMs
        0,  # tAccNs
        0,  # clkDOrFreq
        0,  # clkDAccOrFreqAcc
        flags,  # flags
    )
    assert len(payload) == 48, f"AID-INI muss 48 Byte sein, ist {len(payload)}"
    return build_ubx_packet(0x0B, 0x01, payload)


def send_aid_ini(serial_conn, lat_deg, lon_deg, **kwargs):
    """Sendet AID-INI ueber die offene serielle Verbindung; No-op ohne Verbindung."""
    if not serial_conn or not serial_conn.is_open:
        return False
    packet = build_aid_ini(lat_deg, lon_deg, **kwargs)
    serial_conn.write(packet)
    serial_conn.flush()
    return True
