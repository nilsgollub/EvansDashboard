"""Laufzeit-Konfiguration mit Umgebungsvariablen-Overrides.

Defaults entsprechen exakt den bisherigen hartkodierten Werten aus main.py.
Per Env-Variable lassen sie sich ohne Code-Aenderung anpassen, z.B.:
    EVANS_SIMULATOR=1 EVANS_DIMMING=1 python src/main.py
"""

import os


def _env_bool(name, default):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# True: Marly-Simulation bei GPS-Verlust aktivieren.
SIMULATOR_ENABLED = _env_bool("EVANS_SIMULATOR", False)

# False: automatisches Dimmen deaktivieren (immer 100% Helligkeit).
DIMMING_ENABLED = _env_bool("EVANS_DIMMING", False)

# 'serial' fuer USB-Modul, 'network' fuer Smartphone-GPS ueber WLAN/Hotspot.
GPS_MODE = os.environ.get("EVANS_GPS_MODE", "serial")

# None fuer automatische Gateway-Ermittlung, oder feste IP (z.B. '192.168.43.1').
GPS_IP = os.environ.get("EVANS_GPS_IP") or None

# Standard-Port fuer GPS-Streaming-Apps (z.B. 20000 bei 'Share GPS' / 'GPS Tether').
GPS_PORT = int(os.environ.get("EVANS_GPS_PORT", "20000"))
