import socket

ips = [
    "192.168.1.3",
    "192.168.1.4",
    "192.168.1.5",
    "192.168.1.8",
    "192.168.1.27",
    "192.168.1.80",
    "192.168.1.141",
    "192.168.1.144",
    "192.168.1.155",
    "192.168.1.200",
    "192.168.1.202",
]

print("Scanning port 22...")
for ip in ips:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect((ip, 22))
        print(f"IP {ip}: Port 22 is OPEN!")
        s.close()
    except Exception:
        # print(f"IP {ip}: {e}")
        pass
print("Done.")
