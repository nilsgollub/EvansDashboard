import serial
import time
import sys

def build_ubx_packet(msg_class, msg_id, payload):
    msg = bytes([msg_class, msg_id, len(payload) & 0xFF, (len(payload) >> 8) & 0xFF]) + payload
    cka = 0
    ckb = 0
    for b in msg:
        cka = (cka + b) & 0xFF
        ckb = (ckb + cka) & 0xFF
    return bytes([0xB5, 0x62]) + msg + bytes([cka, ckb])

def main():
    print("="*50)
    print("  GPS FACTORY RESET TOOL")
    print("="*50)
    
    ports = ['/dev/ttyACM0', '/dev/ttyUSB0', '/dev/serial0']
    baudrates = [9600, 38400, 115200, 4800]
    serial_conn = None

    for port in ports:
        for baud in baudrates:
            try:
                print(f"Versuche serielle Verbindung zu {port} mit {baud} baud...")
                s = serial.Serial(port, baud, timeout=1)
                # Teste ob Daten kommen
                line = s.readline()
                if line:
                    serial_conn = s
                    print(f"--> Erfolgreich verbunden auf {port} bei {baud} baud!\n")
                    break
                else:
                    s.close()
            except Exception:
                pass
        if serial_conn:
            break

    if not serial_conn:
        print("\n[FEHLER] Konnte kein aktives GPS Modul finden.")
        sys.exit(1)

    print("Sende Factory Reset Kommando (Revert to default)...")
    try:
        # CFG-CFG: Clear Mask=0xFFFF, Save Mask=0x0000, Load Mask=0xFFFF, Device Mask=0x07 (BBR, Flash, EEPROM)
        reset_payload = (
            b'\xff\xff\x00\x00'  # clearMask
            b'\x00\x00\x00\x00'  # saveMask
            b'\xff\xff\x00\x00'  # loadMask
            b'\x07'              # deviceMask
        )
        packet = build_ubx_packet(0x06, 0x09, reset_payload)
        serial_conn.write(packet)
        serial_conn.flush()
        print("Kommando erfolgreich gesendet!")
        print("Warte 2 Sekunden...")
        time.sleep(2)
        print("Das GPS-Modul ist jetzt im Werkszustand (9600 Baud, 1 Hz).")
        print("Du kannst das Dashboard jetzt normal starten.")
    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == '__main__':
    main()
