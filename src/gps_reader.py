import serial
import pynmea2
import time
import logging
import socket

logger = logging.getLogger(__name__)

class GPSReader:
    def __init__(self, mode='serial', ip=None, port=20000, ports=['/dev/ttyACM0', '/dev/ttyUSB0', '/dev/serial0'], baudrate=9600):
        self.mode = mode
        self.ip = ip
        self.port = port
        self.ports = ports
        self.baudrate = baudrate
        self.serial_conn = None
        self.socket_conn = None
        self.current_port = None

    def _get_default_gateway(self):
        """Versucht, die IP-Adresse des Standard-Gateways (Smartphone-Hotspot) unter Linux zu ermitteln."""
        try:
            with open("/proc/net/route") as f:
                for line in f:
                    fields = line.strip().split()
                    if len(fields) >= 3 and fields[1] == '00000000':
                        hex_gw = fields[2]
                        # Hex-Wert (Little-Endian) in IP konvertieren (z.B. "012CA8C0" -> 192.168.43.1)
                        b1 = int(hex_gw[6:8], 16)
                        b2 = int(hex_gw[4:6], 16)
                        b3 = int(hex_gw[2:4], 16)
                        b4 = int(hex_gw[0:2], 16)
                        gw_ip = f"{b1}.{b2}.{b3}.{b4}"
                        print(f"[GPS] Standard-Gateway automatisch ermittelt: {gw_ip}")
                        return gw_ip
        except Exception as e:
            print(f"[GPS] Fehler bei Gateway-Ermittlung: {e}")
        return "192.168.43.1" # Standard-Fallback fuer Android-Hotspots

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

    def connect(self):
        if self.mode == 'network':
            # Falls keine IP konfiguriert ist, ermitteln wir sie dynamisch
            target_ip = self.ip if self.ip else self._get_default_gateway()
            try:
                print(f"[GPS] Verbinde mit Netzwerk-GPS-Server auf {target_ip}:{self.port}...")
                self.socket_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket_conn.settimeout(5)
                self.socket_conn.connect((target_ip, self.port))
                print(f"[GPS] Erfolgreich verbunden mit Netzwerk-GPS auf {target_ip}:{self.port}")
                return True
            except Exception as e:
                print(f"[GPS] Verbindung mit Netzwerk-GPS fehlgeschlagen: {e}")
                self.socket_conn = None
                return False
        else:
            for port in self.ports:
                try:
                    self.serial_conn = serial.Serial(port, self.baudrate, timeout=2)
                    self.current_port = port
                    print(f"[GPS] Erfolgreich verbunden auf {port}")
                    
                    # Optimierungen fuer u-blox NEO-7M
                    try:
                        nav5_payload = bytearray(36)
                        nav5_payload[0:2] = b'\x01\x00' # mask: apply dynModel
                        nav5_payload[2] = 4             # dynModel: 4 (Automotive)
                        nav5_payload[3] = 3             # fixMode: 3 (Auto 2D/3D)
                        self._send_ubx_msg(0x06, 0x24, nav5_payload)
                        print("[GPS] UBX CFG-NAV5 (Automotive) gesendet.")
                    except Exception as e:
                        print(f"[GPS] Fehler bei CFG-NAV5: {e}")

                    try:
                        payload_sbas_off = b'\x00\x00\x00\x00\x00\x00\x00\x00'
                        self._send_ubx_msg(0x06, 0x16, payload_sbas_off)
                        print("[GPS] UBX CFG-SBAS (Disabled) gesendet.")
                    except Exception as e:
                        print(f"[GPS] Fehler bei CFG-SBAS: {e}")

                    try:
                        cfg_aop_payload = b'\x01\x00\x00\x00'
                        self._send_ubx_msg(0x06, 0x33, cfg_aop_payload)
                        print("[GPS] UBX CFG-AOP (AssistNow Autonomous) gesendet.")
                    except Exception as e:
                        print(f"[GPS] Fehler bei CFG-AOP: {e}")

                    try:
                        cfg_save_payload = b'\x00\x00\x00\x00\xff\xff\x00\x00\x00\x00\x00\x00\x01'
                        self._send_ubx_msg(0x06, 0x09, cfg_save_payload)
                        print("[GPS] UBX CFG-CFG (Save Config) gesendet.")
                    except Exception as e:
                        print(f"[GPS] Fehler bei CFG-CFG: {e}")
                    
                    return True
                except serial.SerialException:
                    pass
                    
            print(f"[GPS] FEHLER: Kein GPS-Modul unter den Ports {self.ports} gefunden.")
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
        """Liest kontinuierlich NMEA-Saetze (entweder aus dem Netzwerk oder seriell) und aktualisiert das state_dict."""
        print(f"[GPS] Thread gestartet (Modus: {self.mode}). Suche nach Satelliten-Fix...")
        
        network_buffer = ""
        
        while True:
            # 1. Sicherstellen, dass die Verbindung offen ist
            if self.mode == 'network':
                if not self.socket_conn:
                    if not self.connect():
                        time.sleep(5)
                        continue
            else:
                if not self.serial_conn or not self.serial_conn.is_open:
                    if not self.connect():
                        time.sleep(5)
                        continue

            # 2. Daten lesen und parsen
            try:
                if self.mode == 'network':
                    # Lese Datenbloecke ueber das Netzwerk-Socket
                    data = self.socket_conn.recv(4096).decode('ascii', errors='ignore')
                    if not data:
                        print("[GPS] Netzwerk-Verbindung vom Smartphone getrennt.")
                        self.socket_conn.close()
                        self.socket_conn = None
                        continue
                    
                    network_buffer += data
                    while "\n" in network_buffer:
                        line, network_buffer = network_buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            self._parse_nmea_line(line, state_dict)
                else:
                    # Lese Zeile ueber die serielle Schnittstelle
                    line = self.serial_conn.readline().decode('ascii', errors='replace').strip()
                    if line:
                        self._parse_nmea_line(line, state_dict)
                        
            except socket.timeout:
                pass # Timeout ist normal bei periodischen Empfangsluecken, einfach weiterlesen
            except socket.error as e:
                print(f"[GPS] Netzwerk-Fehler: {e}")
                if self.socket_conn:
                    self.socket_conn.close()
                self.socket_conn = None
                time.sleep(1)
            except serial.SerialException as e:
                print(f"[GPS] Serielle Verbindung verloren: {e}")
                if self.serial_conn:
                    self.serial_conn.close()
                self.serial_conn = None
                time.sleep(1)
            except Exception as e:
                print(f"[GPS] Unerwarteter Fehler im Reader: {e}")
                time.sleep(1)
