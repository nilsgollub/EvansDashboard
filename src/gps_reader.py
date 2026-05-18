import serial
import pynmea2
import time
import logging

logger = logging.getLogger(__name__)

class GPSReader:
    def __init__(self, ports=['/dev/ttyACM0', '/dev/ttyUSB0', '/dev/serial0'], baudrate=9600):
        self.ports = ports
        self.baudrate = baudrate
        self.serial_conn = None
        self.current_port = None
        
    def _send_ubx_msg(self, msg_class, msg_id, payload):
        """Hilfsfunktion zum Senden eines binären UBX-Kommandos an das U-Blox Modul."""
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
        for port in self.ports:
            try:
                self.serial_conn = serial.Serial(port, self.baudrate, timeout=2)
                self.current_port = port
                print(f"[GPS] Erfolgreich verbunden auf {port}")
                
                # Optimierung 1: Dynamisches Modell auf "Automotive" setzen (CFG-NAV5)
                try:
                    nav5_payload = bytearray(36)
                    nav5_payload[0:2] = b'\x01\x00' # mask: apply dynModel
                    nav5_payload[2] = 4             # dynModel: 4 (Automotive)
                    nav5_payload[3] = 3             # fixMode: 3 (Auto 2D/3D)
                    self._send_ubx_msg(0x06, 0x24, nav5_payload)
                    print("[GPS] UBX CFG-NAV5 (Automotive) gesendet.")
                except Exception as e:
                    print(f"[GPS] Fehler bei CFG-NAV5: {e}")

                # Optimierung 2: SBAS deaktivieren (CFG-SBAS)
                try:
                    payload_sbas_off = b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    self._send_ubx_msg(0x06, 0x16, payload_sbas_off)
                    print("[GPS] UBX CFG-SBAS (Disabled) gesendet.")
                except Exception as e:
                    print(f"[GPS] Fehler bei CFG-SBAS: {e}")

                # Optimierung 3: GLONASS aktivieren (CFG-GNSS)
                try:
                    payload_gnss = (
                        b'\x00\x20\x20\x02' # msgVer, numTrkChHw, numTrkChUse, numConfigBlocks
                        b'\x00\x08\x10\x01' # GPS block (gnssId=0)
                        b'\x06\x08\x0E\x01' # GLONASS block (gnssId=6)
                    )
                    self._send_ubx_msg(0x06, 0x3E, payload_gnss)
                    print("[GPS] UBX CFG-GNSS (GPS+GLONASS) gesendet.")
                except Exception as e:
                    print(f"[GPS] Fehler bei CFG-GNSS: {e}")

                # Optimierung 4: AssistNow Autonomous (AOP) aktivieren (CFG-AOP)
                try:
                    cfg_aop_payload = b'\x01\x00\x00\x00'
                    self._send_ubx_msg(0x06, 0x33, cfg_aop_payload)
                    print("[GPS] UBX CFG-AOP (AssistNow Autonomous) gesendet.")
                except Exception as e:
                    print(f"[GPS] Fehler bei CFG-AOP: {e}")

                # Konfiguration dauerhaft im u-blox NVRAM speichern (CFG-CFG)
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
            
    def read_data(self, state_dict):
        """
        Liest kontinuierlich NMEA Sätze und aktualisiert das state_dict.
        """
        print("[GPS] Thread gestartet. Suche nach Satelliten-Fix...")
        while True:
            if not self.serial_conn or not self.serial_conn.is_open:
                if not self.connect():
                    time.sleep(5)
                    continue
                    
            try:
                line = self.serial_conn.readline().decode('ascii', errors='replace').strip()
                
                # RMC (Recommended Minimum Navigation Information) liefert uns Geschwindigkeit & Position
                if line.startswith('$GPRMC') or line.startswith('$GNRMC'):
                    msg = pynmea2.parse(line)
                    if msg.status == 'A':  # 'A' bedeutet "Active" / Data Valid
                        # Geschwindigkeit in Knoten * 1.852 = km/h
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
                        
                # GGA (Global Positioning System Fix Data) liefert uns Satelliten & Höhe
                elif line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                    msg = pynmea2.parse(line)
                    if msg.gps_qual > 0:
                        state_dict['sats'] = int(msg.num_sats)
                        state_dict['altitude'] = float(msg.altitude)
                        state_dict['last_update'] = time.time()
                        print(f"[GPS] GGA Update -> Sats: {msg.num_sats}, Alt: {msg.altitude}m")
                        
            except pynmea2.ParseError:
                pass # Parse Errors passieren manchmal bei unvollständigen Sätzen
            except serial.SerialException as e:
                print(f"[GPS] Serielle Verbindung verloren: {e}")
                self.serial_conn.close()
            except Exception as e:
                print(f"[GPS] Unerwarteter Fehler: {e}")
                time.sleep(1)
