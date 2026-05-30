"""Atomares Speichern und Laden der letzten bekannten GPS-Position.

Hintergrund: Das NEO-7M verliert Ephemeriden/Almanach/letzte Position bei
Spannungsverlust, wenn die V_BCKP-Stuetzbatterie schwach oder leer ist. Wir
halten daher selbst eine Kopie der letzten Position + Zeit auf der SD-Karte
und injizieren sie beim naechsten Boot per UBX AID-INI ins GPS, um einen
Cold Start in einen Warm Start zu verwandeln.

Schreibvorgaenge sind atomar (tmp + fsync + rename), damit ein harter
Stromabriss (Zuendung aus) die Datei niemals halb beschrieben hinterlaesst.
"""

import json
import os
import time

# Verzeichnis fuer persistente Laufzeitdaten; ueber EVANS_STATE_DIR ueberschreibbar.
STATE_DIR = os.environ.get("EVANS_STATE_DIR") or os.path.expanduser("~/.evans-dashboard")
LAST_FIX_PATH = os.path.join(STATE_DIR, "last_fix.json")


def _ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass


def save_last_fix(lat, lon, altitude=None, sats=None, t=None, path=LAST_FIX_PATH):
    """Schreibt die letzte Position atomar auf Disk. Gibt True/False zurueck."""
    if lat is None or lon is None:
        return False
    if t is None:
        t = time.time()
    data = {
        "lat": float(lat),
        "lon": float(lon),
        "altitude": float(altitude) if altitude is not None else None,
        "sats": int(sats) if sats is not None else None,
        "time": float(t),
    }
    _ensure_dir(os.path.dirname(path))
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return True
    except OSError:
        # Disk voll / kein Schreibrecht: das Dashboard darf deswegen nicht crashen.
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


def load_last_fix(path=LAST_FIX_PATH):
    """Liest die letzte Position oder gibt None zurueck, wenn nichts brauchbares vorliegt."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if data.get("lat") is None or data.get("lon") is None or data.get("time") is None:
        return None
    return data
