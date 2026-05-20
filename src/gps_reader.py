import serial
import pynmea2
import time
import logging

logger = logging.getLogger(__name__)

class GPSReader:
    def __init__(self, mode='serial', ip=None, port=20000, ports=['/dev/ttyACM0', '/dev/ttyUSB0', '/dev/serial0'], baudrate=9600):
        # Wir behalten die Parameter fuer Abwaertskompatibilitaet bei, erzwingen aber den seriellen Modus
        self.mode = 'serial'
        self.ports = ports
        self.baudrate = baudrate
        self.serial_conn = None
        self.current_port = None

    def _send_ubx_msg(self, msg_class, msg_id, payload):
        """Hilfsfunktion zum Senden eines binaeren UBX-Kommandos an das U-Blox Modul (nur im Seriell-Modus)."""
        if not self.serial_conn or not self.serial_conn.is_open:
            return
        msg = bytes([msg_class, msg_id, len(payload) & 0xFF, (len(payload) >> 8) & 0xFF]) + payload
        cka = 0
        ckb = 0
        for b in msg:
            cka = (cka + b) & 0xFF
            ckb = (ckb + cka) & 0xFF
        packet = bytes([0xB5, 0x62]) + msg + bytes([cka, ckb])
        self.serial_conn.write(packet)
        self.serial_conn.flush()

    def connect(self, state_dict=None):
        for port in self.ports:
            try:
                print(f"[GPS] Versuche serielle Verbindung zu {port} mit Baudrate {self.baudrate}...")
                self.serial_conn = serial.Serial(port, self.baudrate, timeout=2)
                self.current_port = port
                print(f"[GPS] Erfolgreich verbunden auf {port}")
                if state_dict is not None:
                    state_dict['gps_connected'] = True
                
                # Optimierte U-Blox NEO-7M Konfiguration (exakt wie in Worx_GPS)
                try:
                    # 1. CFG-NAV5: Automotive Modus (DynModel 4) und 10° Elevation Maske fuer stabile Fahrtdaten
                    nav5_payload = (
                        b'\x11\x00'          # Mask (bit 0 & 4: DynModel & MinElev)
                        b'\x04'              # DynModel (4 = Automotive)
                        b'\x03'              # FixMode (3 = Auto 2D/3D)
                        b'\x00\x00\x00\x00'  # FixedAlt
                        b'\x00\x00\x00\x00'  # FixedAltVar
                        b'\x0a'              # MinElev (10 Grad)
                        b'\x00'              # DrLimit
                        b'\x00\x00'          # pDop
                        b'\x00\x00'          # tDop
                        b'\x00\x00'          # pAcc
                        b'\x00\x00'          # tAcc
                        b'\x00'              # staticHoldThresh
                        b'\x00'              # dgpsTimeOut
                        b'\x00' * 12         # Reserved
                    )
                    self._send_ubx_msg(0x06, 0x24, nav5_payload)
                    print("[GPS] UBX CFG-NAV5 (Automotive, 10° Elevation) gesendet.")
                except Exception as e:
                    print(f"[GPS] Fehler bei CFG-NAV5: {e}")

                try:
                    # 2. CFG-SBAS: SBAS/EGNOS aktivieren mit den PRNs fuer Europa (120, 121, 123, 126) fuer 1-2m Praezision
                    sbas_payload = (
                        b'\x01'              # mode: Enabled
                        b'\x07'              # usage: Range + DiffCorr + Integrity
                        b'\x03'              # maxSBAS: 3
                        b'\x00'              # scanmode2
                        b'\x00\x62\x00\x00'  # scanmode1: EGNOS PRNs (120, 121, 123, 126)
                    )
                    self._send_ubx_msg(0x06, 0x16, sbas_payload)
                    print("[GPS] UBX CFG-SBAS (EGNOS Europe) gesendet.")
                except Exception as e:
                    print(f"[GPS] Fehler bei CFG-SBAS: {e}")

                try:
                    # 3. CFG-AOP: AssistNow Autonomous aktivieren (on-chip AGPS fuer schnellen Fix ohne Internet)
                    aop_payload = b'\x01\x00\x00\x00'
                    self._send_ubx_msg(0x06, 0x33, aop_payload)
                    print("[GPS] UBX CFG-AOP (AssistNow Autonomous) gesendet.")
                except Exception as e:
                    print(f"[GPS] Fehler bei CFG-AOP: {e}")

                try:
                    # 4. CFG-CFG: Konfiguration dauerhaft im EEPROM/Flash des Moduls sichern
                    cfg_save_payload = b'\x00\x00\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x01'
                    self._send_ubx_msg(0x06, 0x09, cfg_save_payload)
                    print("[GPS] UBX CFG-CFG (Save Config) gesendet.")
                except Exception as e:
                    print(f"[GPS] Fehler bei CFG-CFG: {e}")
                
                return True
            except serial.SerialException as e:
                print(f"[GPS] Fehler beim Verbindungsversuch auf {port}: {e}")
                
        print(f"[GPS] FEHLER: Kein GPS-Modul unter den Ports {self.ports} gefunden.")
        if state_dict is not None:
            state_dict['gps_connected'] = False
        return False

    def _parse_nmea_line(self, line, state_dict):
        """Interne Hilfsfunktion zur Verarbeitung einer einzelnen NMEA-Zeile."""
        try:
            # RMC (Recommended Minimum Navigation Information) liefert uns Geschwindigkeit & Position
            if line.startswith('$GPRMC') or line.startswith('$GNRMC'):
                msg = pynmea2.parse(line)
                if msg.status == 'A':  # 'A' bedeutet "Active" / Data Valid
                    speed_kmh = float(msg.spd_over_grnd) * 1.852
                    state_dict['speed'] = speed_kmh
                    state_dict['lat'] = msg.latitude
                    state_dict['lon'] = msg.longitude
                    state_dict['last_update'] = time.time()
                    if hasattr(msg, 'track') and msg.track is not None:
                        try:
                            state_dict['heading'] = float(msg.track)
                        except (ValueError, TypeError):
                            pass
                    print(f"[GPS] RMC Update -> Speed: {speed_kmh:.1f} km/h, Pos: {msg.latitude:.4f}, {msg.longitude:.4f}, Course: {state_dict.get('heading', 0.0)}°")
                else:
                    print("[GPS] Suche nach Satelliten... (Noch kein GPS-Fix)")
                    
            # GGA (Global Positioning System Fix Data) liefert uns Fix-Qualitaet & Hoehe
            elif line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                msg = pynmea2.parse(line)
                if msg.gps_qual > 0:
                    try:
                        state_dict['altitude'] = float(msg.altitude)
                    except (ValueError, TypeError):
                        pass
                    try:
                        if msg.num_sats:
                            state_dict['sats'] = int(msg.num_sats)
                    except (ValueError, TypeError):
                        pass
                    state_dict['last_update'] = time.time()
                    print(f"[GPS] GGA Update -> Sats: {msg.num_sats}, Alt: {msg.altitude}m")

            # GSV (GPS Satellites in View) – zeigt sichtbare Satelliten AUCH OHNE FIX
            elif line.startswith('$GPGSV') or line.startswith('$GNGSV'):
                msg = pynmea2.parse(line)
                if hasattr(msg, 'msg_num') and str(msg.msg_num) == '1':
                    try:
                        sats_in_view = int(msg.num_sv_in_view)
                        # GSV ueberschreibt die Sat-Zahl nur, wenn KEIN Fix vorliegt.
                        if state_dict.get('last_update', 0.0) == 0.0 or \
                           (time.time() - state_dict.get('last_update', 0.0)) >= 10.0:
                            state_dict['sats'] = sats_in_view
                        print(f"[GPS] GSV -> Satelliten in Sicht: {sats_in_view}")
                    except (ValueError, TypeError, AttributeError):
                        pass
                    
        except pynmea2.ParseError:
            pass # Parse Errors passieren manchmal bei unvollstaendigen Saetzen
        except Exception as e:
            print(f"[GPS] Parser-Fehler: {e}")

    def read_data(self, state_dict):
        """Liest kontinuierlich NMEA-Saetze aus der seriellen Schnittstelle und aktualisiert das state_dict."""
        print(f"[GPS] Thread gestartet (Modus: {self.mode}). Suche nach Satelliten-Fix...")
        
        # Initialen Status auf False setzen
        state_dict['gps_connected'] = False
        
        while True:
            # 1. Sicherstellen, dass die Verbindung offen ist
            if not self.serial_conn or not self.serial_conn.is_open:
                if not self.connect(state_dict):
                    time.sleep(5)
                    continue

            # 2. Daten lesen und parsen
            try:
                # Verbindung als aktiv markieren
                state_dict['gps_connected'] = True
                
                # Lese Zeile ueber die serielle Schnittstelle
                line = self.serial_conn.readline().decode('ascii', errors='replace').strip()
                if line:
                    self._parse_nmea_line(line, state_dict)
                        
            except serial.SerialException as e:
                print(f"[GPS] Serielle Verbindung verloren: {e}")
                if self.serial_conn:
                    self.serial_conn.close()
                self.serial_conn = None
                state_dict['gps_connected'] = False
                time.sleep(1)
            except Exception as e:
                print(f"[GPS] Unerwarteter Fehler im Reader: {e}")
                state_dict['gps_connected'] = False
                time.sleep(1)
