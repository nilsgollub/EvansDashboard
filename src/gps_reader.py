import logging
import time
from datetime import datetime, timezone

import pynmea2
import serial

from state_store import load_last_fix
from ubx import configure_neo7m, send_aid_ini

logger = logging.getLogger(__name__)

# Maximales Alter eines gespeicherten Fixes, bei dem wir die UTC-Zeit noch
# mitinjizieren. Aelter -> nur Position, weil die Pi-Uhr nach so langer Pause
# vermutlich aus fake-hwclock kommt und stark daneben liegt.
_MAX_TIME_HINT_AGE_S = 6 * 3600


class GPSReader:
    def __init__(
        self,
        mode="serial",
        ip=None,
        port=20000,
        ports=["/dev/ttyACM0", "/dev/ttyUSB0", "/dev/serial0"],
        baudrate=9600,
        ttff_logger=None,
    ):
        # Wir behalten die Parameter fuer Abwaertskompatibilitaet bei, erzwingen aber den seriellen Modus
        self.mode = "serial"
        self.ports = ports
        self.baudrate = baudrate
        self.serial_conn = None
        self.current_port = None
        self.ttff_logger = ttff_logger
        self._ini_sent = False
        self._last_gsv_log = 0.0

    def _inject_warm_start_hint(self):
        """Schiebt die letzte bekannte Position (+ Zeit) als AID-INI ins NEO-7M.

        Wirkt auch ohne intakte V_BCKP-Stuetzbatterie: macht aus einem Cold
        Start einen Warm Start, weil das Modul nicht blind nach allen GPS-
        Satelliten suchen muss.
        """
        last = load_last_fix()
        if not last:
            if self.ttff_logger:
                self.ttff_logger.session_started(ini_injected=False)
            return
        age_s = time.time() - last["time"]
        # Zeit nur injizieren, wenn die Pi-Uhr plausibel zur gespeicherten Zeit passt.
        # Negativer age_s = Systemuhr liegt VOR der zuletzt gespeicherten Zeit (typisch
        # nach hartem Aus + fake-hwclock-Checkpoint vor dem letzten Fix-Write); zu
        # grosser age_s = der Hint ist sowieso veraltet. In beiden Faellen waere die
        # injizierte Zeit eher schaedlich als hilfreich.
        inject_time = 0 <= age_s < _MAX_TIME_HINT_AGE_S
        try:
            ok = send_aid_ini(
                self.serial_conn,
                last["lat"],
                last["lon"],
                alt_m=last.get("altitude") or 0.0,
                dt_utc=datetime.now(timezone.utc),
                inject_time=inject_time,
            )
        except Exception as e:  # noqa: BLE001 - AID-INI ist best effort
            print(f"[GPS] AID-INI fehlgeschlagen: {e}")
            ok = False
        if ok:
            print(
                f"[GPS] AID-INI gesendet: lat={last['lat']:.4f}, lon={last['lon']:.4f}, "
                f"age={age_s:.0f}s, time={'ja' if inject_time else 'nein'}"
            )
        if self.ttff_logger:
            self.ttff_logger.session_started(
                ini_injected=ok,
                restored_lat=last["lat"],
                restored_lon=last["lon"],
                restored_age_s=round(age_s, 1),
            )

    def connect(self, state_dict=None):
        for port in self.ports:
            try:
                print(f"[GPS] Versuche serielle Verbindung zu {port} mit Baudrate {self.baudrate}...")
                self.serial_conn = serial.Serial(port, self.baudrate, timeout=2)
                self.current_port = port
                print(f"[GPS] Erfolgreich verbunden auf {port}")
                if state_dict is not None:
                    state_dict["gps_connected"] = True

                # Optimierte U-Blox NEO-7M Konfiguration (gemeinsame Quelle: ubx.py)
                configure_neo7m(self.serial_conn)

                # Warm-Start-Hinweis nur einmal pro Prozess - bei spaeteren
                # Reconnects ist im Chip bereits frischere Info.
                if not self._ini_sent:
                    self._inject_warm_start_hint()
                    self._ini_sent = True

                return True
            except serial.SerialException as e:
                print(f"[GPS] Fehler beim Verbindungsversuch auf {port}: {e}")

        print(f"[GPS] FEHLER: Kein GPS-Modul unter den Ports {self.ports} gefunden.")
        if state_dict is not None:
            state_dict["gps_connected"] = False
        return False

    def _parse_nmea_line(self, line, state_dict):
        """Interne Hilfsfunktion zur Verarbeitung einer einzelnen NMEA-Zeile."""
        try:
            # Wir prüfen nur den Suffix (z.B. RMC), um alle Konstellationen ($GP, $GN, $GL) zu matchen.
            if len(line) >= 6 and line.startswith("$"):
                msg_type = line[3:6]

                # RMC (Recommended Minimum Navigation Information) liefert uns Geschwindigkeit & Position
                if msg_type == "RMC":
                    msg = pynmea2.parse(line)
                    if msg.status == "A":  # 'A' bedeutet "Active" / Data Valid
                        speed_kmh = float(msg.spd_over_grnd) * 1.852
                        state_dict["speed"] = speed_kmh
                        state_dict["lat"] = msg.latitude
                        state_dict["lon"] = msg.longitude
                        state_dict["last_update"] = time.time()
                        if hasattr(msg, "track") and msg.track is not None:
                            try:
                                state_dict["heading"] = float(msg.track)
                            except (ValueError, TypeError):
                                pass
                        if self.ttff_logger:
                            self.ttff_logger.first_fix(msg.latitude, msg.longitude, state_dict.get("sats", 0))
                        print(
                            f"[GPS] RMC Update -> Speed: {speed_kmh:.1f} km/h, Pos: {msg.latitude:.4f}, {msg.longitude:.4f}, Course: {state_dict.get('heading', 0.0)}°"
                        )
                    else:
                        print("[GPS] Suche nach Satelliten... (Noch kein GPS-Fix)")

                # GGA (Global Positioning System Fix Data) liefert uns Fix-Qualitaet & Hoehe
                elif msg_type == "GGA":
                    msg = pynmea2.parse(line)
                    if msg.gps_qual > 0:
                        try:
                            state_dict["altitude"] = float(msg.altitude)
                        except (ValueError, TypeError):
                            pass
                        try:
                            if msg.num_sats:
                                state_dict["sats"] = int(msg.num_sats)
                        except (ValueError, TypeError):
                            pass
                        state_dict["last_update"] = time.time()
                        print(f"[GPS] GGA Update -> Sats: {msg.num_sats}, Alt: {msg.altitude}m")

                # GSV (GPS Satellites in View) – zeigt sichtbare Satelliten AUCH OHNE FIX
                elif msg_type == "GSV":
                    msg = pynmea2.parse(line)
                    if hasattr(msg, "msg_num") and str(msg.msg_num) == "1":
                        try:
                            sats_in_view = int(msg.num_sv_in_view)
                            # GSV ueberschreibt die Sat-Zahl nur, wenn KEIN Fix vorliegt.
                            if (
                                state_dict.get("last_update", 0.0) == 0.0
                                or (time.time() - state_dict.get("last_update", 0.0)) >= 10.0
                            ):
                                state_dict["sats"] = sats_in_view
                            # TTFF-Diagnose: gedrosselt (max alle 60 s) sichtbare Sats loggen
                            now = time.time()
                            if self.ttff_logger and (now - self._last_gsv_log) >= 60.0:
                                self.ttff_logger.sats_in_view(sats_in_view)
                                self._last_gsv_log = now
                            print(f"[GPS] GSV ({line[1:3]}) -> Satelliten in Sicht: {sats_in_view}")
                        except (ValueError, TypeError, AttributeError):
                            pass

        except pynmea2.ParseError:
            pass  # Parse Errors passieren manchmal bei unvollstaendigen Saetzen
        except Exception as e:
            print(f"[GPS] Parser-Fehler: {e}")

    def read_data(self, state_dict):
        """Liest kontinuierlich NMEA-Saetze aus der seriellen Schnittstelle und aktualisiert das state_dict."""
        print(f"[GPS] Thread gestartet (Modus: {self.mode}). Suche nach Satelliten-Fix...")

        # Initialen Status auf False setzen
        state_dict["gps_connected"] = False

        while True:
            # 1. Sicherstellen, dass die Verbindung offen ist
            if not self.serial_conn or not self.serial_conn.is_open:
                if not self.connect(state_dict):
                    time.sleep(5)
                    continue

            # 2. Daten lesen und parsen
            try:
                # Verbindung als aktiv markieren
                state_dict["gps_connected"] = True

                # Lese Zeile ueber die serielle Schnittstelle
                line = self.serial_conn.readline().decode("ascii", errors="replace").strip()
                if line:
                    self._parse_nmea_line(line, state_dict)

            except serial.SerialException as e:
                print(f"[GPS] Serielle Verbindung verloren: {e}")
                if self.serial_conn:
                    self.serial_conn.close()
                self.serial_conn = None
                state_dict["gps_connected"] = False
                time.sleep(1)
            except Exception as e:
                print(f"[GPS] Unerwarteter Fehler im Reader: {e}")
                state_dict["gps_connected"] = False
                time.sleep(1)
