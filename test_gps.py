import serial
import pynmea2
import time

def send_ubx_msg(serial_conn, msg_class, msg_id, payload):
    if not serial_conn or not serial_conn.is_open:
        return
    msg = bytes([msg_class, msg_id, len(payload) & 0xFF, (len(payload) >> 8) & 0xFF]) + payload
    cka = 0
    ckb = 0
    for b in msg:
        cka = (cka + b) & 0xFF
        ckb = (ckb + cka) & 0xFF
    packet = bytes([0xB5, 0x62]) + msg + bytes([cka, ckb])
    serial_conn.write(packet)
    serial_conn.flush()

def main():
    print("="*50)
    print("  GPS DIAGNOSE TOOL (EVANS DASHBOARD)")
    print("="*50)
    
    ports = ['/dev/ttyACM0', '/dev/ttyUSB0', '/dev/serial0']
    baudrate = 9600
    serial_conn = None

    for port in ports:
        try:
            print(f"Versuche serielle Verbindung zu {port} mit {baudrate} baud...")
            serial_conn = serial.Serial(port, baudrate, timeout=2)
            print(f"--> Erfolgreich verbunden auf {port}!\n")
            break
        except Exception as e:
            print(f"--> Fehler bei {port}: {e}")

    if not serial_conn:
        print("\n[FEHLER] Konnte absolut kein GPS Modul auf den Ports finden.")
        print("Bitte ueberpruefe die Kabelverbindung und Berechtigungen (dialout).")
        return

    # Sende Konfiguration
    print("Sende exakt die gleiche UBX-Konfiguration wie das Dashboard...")
    try:
        # 1. NAV5
        nav5_payload = (
            b'\x11\x00\x04\x03\x00\x00\x00\x00\x00\x00\x00\x00\x0a\x00'
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        )
        send_ubx_msg(serial_conn, 0x06, 0x24, nav5_payload)
        
        # 2. SBAS off
        sbas_off_payload = b'\x00\x00\x00\x00\x00\x00\x00\x00'
        send_ubx_msg(serial_conn, 0x06, 0x16, sbas_off_payload)
        
        # 3. RATE 5Hz
        send_ubx_msg(serial_conn, 0x06, 0x08, b'\xc8\x00\x01\x00\x00\x00')
        
        # 4. MSG Filter
        send_ubx_msg(serial_conn, 0x06, 0x01, b'\xf0\x01\x00\x00\x00\x00\x00\x00') # GLL off
        send_ubx_msg(serial_conn, 0x06, 0x01, b'\xf0\x02\x00\x00\x00\x00\x00\x00') # GSA off
        send_ubx_msg(serial_conn, 0x06, 0x01, b'\xf0\x05\x00\x00\x00\x00\x00\x00') # VTG off
        send_ubx_msg(serial_conn, 0x06, 0x01, b'\xf0\x03\x05\x05\x05\x05\x05\x05') # GSV rate=5

        # 5. AOP
        send_ubx_msg(serial_conn, 0x06, 0x33, b'\x01\x00\x00\x00')
        
        print("Konfiguration erfolgreich gesendet.\n")
    except Exception as e:
        print(f"Fehler bei der Konfiguration: {e}\n")

    print("="*50)
    print(" LESE ROHDATEN VOM GPS (Abbruch mit Strg+C)")
    print("="*50)
    
    # Kurz Puffer leeren
    serial_conn.reset_input_buffer()
    
    while True:
        try:
            line_bytes = serial_conn.readline()
            if not line_bytes:
                continue
            
            # Dekodiere den rohen String
            line_str = line_bytes.decode('ascii', errors='replace').strip()
            
            # Faerbe den Raw-String zur besseren Lesbarkeit weiss (oder unformatiert)
            print(f"[RAW] {line_str}")
            
            # Versuche zu parsen
            if len(line_str) >= 6 and line_str.startswith('$'):
                msg_type = line_str[3:6]
                if msg_type in ['RMC', 'GGA', 'GSV', 'GLL', 'GSA', 'VTG']:
                    try:
                        msg = pynmea2.parse(line_str)
                        if msg_type == 'GSV':
                            print(f"      ---> [GSV] Constellation: {line_str[1:3]} | Satelliten in Sicht: {getattr(msg, 'num_sv_in_view', 'Unbekannt')}")
                            # Ausgabe der Signalstaerken der gefundenen Satelliten
                            sats = []
                            for i in range(1, 5):
                                prn = getattr(msg, f'sv_prn_num_{i}', '')
                                snr = getattr(msg, f'snr_{i}', '')
                                if prn and snr:
                                    sats.append(f"PRN:{prn}(SNR:{snr})")
                            if sats:
                                print(f"      --->       Sats details: {', '.join(sats)}")
                        elif msg_type == 'GGA':
                            print(f"      ---> [GGA] Fix Qualitaet: {msg.gps_qual} (0=Kein Fix, 1=GPS, 2=DGPS) | Sats genutzt: {getattr(msg, 'num_sats', 0)}")
                        elif msg_type == 'RMC':
                            print(f"      ---> [RMC] Status: {msg.status} (A=Active/Fix, V=Void/Kein Fix)")
                    except pynmea2.ParseError as e:
                        print(f"      ---> [! PARSE ERROR !] Konnte Zeile nicht lesen: {e}. (Evtl. Baudraten-Buffer-Overflow!)")
            
        except KeyboardInterrupt:
            print("\n[INFO] Skript vom Benutzer beendet.")
            break
        except Exception as e:
            print(f"[FEHLER] Fehler beim Lesen der seriellen Schnittstelle: {e}")
            time.sleep(1)

if __name__ == '__main__':
    main()
