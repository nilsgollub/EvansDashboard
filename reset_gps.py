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
                s = serial.Serial(port, baud, timeout=0.1)
                
                # Sende Factory Reset Kommando (Revert to default) an diesen Port/Baud
                reset_payload = (
                    b'\xff\xff\x00\x00'  # clearMask
                    b'\x00\x00\x00\x00'  # saveMask
                    b'\xff\xff\x00\x00'  # loadMask
                    b'\x07'              # deviceMask
                )
                packet = build_ubx_packet(0x06, 0x09, reset_payload)
                s.write(packet)
                s.flush()
                s.close()
                print(f"--> Blindes Reset-Kommando an {port} bei {baud} baud gesendet.")
            except Exception:
                pass

    print("\nAlle Reset-Kommandos wurden abgesetzt!")
    print("Warte 2 Sekunden, bis das Modul (hoffentlich) neustartet...")
    time.sleep(2)
    print("Das GPS-Modul sollte jetzt im Werkszustand (9600 Baud, 1 Hz) sein.")

if __name__ == '__main__':
    main()
