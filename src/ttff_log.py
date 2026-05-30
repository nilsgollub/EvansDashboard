"""Schmaler TTFF-/Sat-Logger als JSON-Lines, damit wir spaeter analysieren koennen,
warum ein Fix auf der Fahrt ausbleibt (Antenne vs. Ephemeriden vs. Konfig).

Eine Zeile pro Event, append-only. Robuste, billige Diagnose ohne externe Deps.
"""

import json
import os
import time

from state_store import STATE_DIR

TTFF_LOG_PATH = os.environ.get("EVANS_TTFF_LOG") or os.path.join(STATE_DIR, "ttff.log")


class TTFFLogger:
    def __init__(self, path=TTFF_LOG_PATH):
        self.path = path
        self.session_start = time.time()
        self.first_fix_logged = False
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        except OSError:
            pass

    def _write(self, event):
        event.setdefault("ts", time.time())
        try:
            with open(self.path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except OSError:
            pass  # Diagnose darf das Dashboard nie blockieren

    def session_started(self, ini_injected, restored_lat=None, restored_lon=None, restored_age_s=None):
        self._write(
            {
                "event": "session_start",
                "ini_injected": bool(ini_injected),
                "restored_lat": restored_lat,
                "restored_lon": restored_lon,
                "restored_age_s": restored_age_s,
            }
        )

    def first_fix(self, lat, lon, sats):
        if self.first_fix_logged:
            return
        self.first_fix_logged = True
        ttff = time.time() - self.session_start
        self._write(
            {
                "event": "first_fix",
                "ttff_s": round(ttff, 2),
                "lat": lat,
                "lon": lon,
                "sats": sats,
            }
        )

    def sats_in_view(self, n):
        self._write({"event": "sats_in_view", "n": int(n)})

    def shutdown(self, reason):
        self._write(
            {
                "event": "shutdown",
                "reason": reason,
                "session_s": round(time.time() - self.session_start, 1),
                "had_fix": self.first_fix_logged,
            }
        )
