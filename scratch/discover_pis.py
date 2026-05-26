import subprocess
import threading

print("Starting subnet discovery (192.168.1.1 - 254)...")


def ping_ip(ip):
    try:
        # Ping with 1 packet, 500ms timeout
        subprocess.run(["ping", "-n", "1", "-w", "500", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


threads = []
for i in range(1, 255):
    ip = f"192.168.1.{i}"
    t = threading.Thread(target=ping_ip, args=(ip,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("Subnet scan done. Querying ARP table...")

# Get ARP table
try:
    output = subprocess.check_output(["arp", "-a"]).decode("cp1252", errors="ignore")
    print(output)

    # Search for Pi MAC addresses
    # Raspberry Pi OUIs: b8-27-eb, 3a-35-41, c8-3a-35, d8-3a-dd, e4-5f-01, dc-a6-32
    pi_ouis = ["b8-27-eb", "3a-35-41", "c8-3a-35", "d8-3a-dd", "e4-5f-01", "dc-a6-32"]

    lines = output.splitlines()
    found_pis = []
    for line in lines:
        for oui in pi_ouis:
            if oui in line.lower():
                found_pis.append(line.strip())
                break

    if found_pis:
        print("\n=== Found potential Raspberry Pi devices ===")
        for pi in found_pis:
            print(pi)
    else:
        print("\nNo Raspberry Pi devices found in ARP table.")
except Exception as e:
    print(f"Error: {e}")
