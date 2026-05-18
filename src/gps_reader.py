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
        
    def connect(self):
        for port in self.ports:
            try:
                self.serial_conn = serial.Serial(port, self.baudrate, timeout=2)
                self.current_port = port
                print(f"[GPS] Erfolgreich verbunden auf {port}")
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
                        print(f"[GPS] GGA Update -> Sats: {msg.num_sats}, Alt: {msg.altitude}m")
                        
            except pynmea2.ParseError:
                pass # Parse Errors passieren manchmal bei unvollständigen Sätzen
            except serial.SerialException as e:
                print(f"[GPS] Serielle Verbindung verloren: {e}")
                self.serial_conn.close()
            except Exception as e:
                print(f"[GPS] Unerwarteter Fehler: {e}")
                time.sleep(1)
