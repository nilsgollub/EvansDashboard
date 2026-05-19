#!/bin/bash
# ==============================================================================
# Evans Dashboard - Fresh Raspberry Pi Setup Script
# ==============================================================================
# Dieses Skript konfiguriert einen frisch installierten Raspberry Pi (Lite OS 64-bit)
# für das Evans-Dashboard. Es installiert alle System-Abhängigkeiten, konfiguriert
# die serielle UART-Schnittstelle für das GPS-Modul, richtet das Adafruit 3.5" PiTFT
# Display ein und konfiguriert den automatischen Kiosk-Start via systemd.
# ==============================================================================

set -e

# Farben für Terminal-Ausgabe
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Standardwerte für Parameter
HOTSPOT_SSID=""
HOTSPOT_PW=""
AUTO_REBOOT="false"
NON_INTERACTIVE="false"

# Argumente parsen
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --hotspot-ssid) HOTSPOT_SSID="$2"; shift ;;
        --hotspot-pw) HOTSPOT_PW="$2"; shift ;;
        --reboot) AUTO_REBOOT="true" ;;
        --non-interactive) NON_INTERACTIVE="true" ;;
        *) echo "Unbekannter Parameter: $1"; exit 1 ;;
    esac
    shift
done

echo -e "${BLUE}================================================================${NC}"
echo -e "${GREEN}      Evans Co-Pilot Dashboard v1.1.0 - Fresh Setup Script      ${NC}"
echo -e "${BLUE}================================================================${NC}"

# 1. Sicherstellen, dass das Skript nicht als root, sondern als normaler User ausgeführt wird
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Fehler: Führe dieses Skript bitte NICHT als root (sudo) aus!${NC}"
    echo "Führe es einfach als normaler Benutzer aus: ./setup_fresh_pi.sh"
    exit 1
fi

CURRENT_USER=$(whoami)
HOME_DIR="/home/$CURRENT_USER"
REPO_DIR="$HOME_DIR/EvansDashboard"

echo -e "${BLUE}[1/7] System aktualisieren & Paketquellen laden...${NC}"
sudo apt update
sudo apt upgrade -y

echo -e "${BLUE}[2/7] System-Abhängigkeiten installieren...${NC}"
# Essenzielle Pakete für X-Server, Pygame, Git, SQLite und Python
sudo apt install -y \
    git \
    python3-pip \
    python3-venv \
    python3-pygame \
    xserver-xorg \
    xinit \
    xserver-xorg-video-fbdev \
    sqlite3 \
    libsdl2-2.0-0 \
    libsdl2-image-2.0-0 \
    libsdl2-mixer-2.0-0 \
    libsdl2-ttf-2.0-0 \
    network-manager

echo -e "${BLUE}[3/7] GPS UART/serielle Schnittstelle konfigurieren...${NC}"
# UART in config.txt aktivieren
CONFIG_FILE="/boot/firmware/config.txt"
[ -f "$CONFIG_FILE" ] || CONFIG_FILE="/boot/config.txt"

echo -e "${YELLOW}Konfiguriere UART in $CONFIG_FILE...${NC}"
if ! grep -q "enable_uart=1" "$CONFIG_FILE"; then
    echo "enable_uart=1" | sudo tee -a "$CONFIG_FILE"
fi

# Serielle Konsole in cmdline.txt deaktivieren (damit das GPS ungestört senden kann)
CMDLINE_FILE="/boot/firmware/cmdline.txt"
[ -f "$CMDLINE_FILE" ] || CMDLINE_FILE="/boot/cmdline.txt"

if [ -f "$CMDLINE_FILE" ]; then
    echo -e "${YELLOW}Deaktiviere serielle Konsole in $CMDLINE_FILE...${NC}"
    # Backup erstellen
    sudo cp "$CMDLINE_FILE" "${CMDLINE_FILE}.bak"
    # console=serial0,115200 oder console=ttyAMA0,115200 entfernen
    sudo sed -i 's/console=serial0,[0-9]* //g' "$CMDLINE_FILE"
    sudo sed -i 's/console=ttyAMA0,[0-9]* //g' "$CMDLINE_FILE"
fi

echo -e "${BLUE}[4/7] Adafruit 3.5\" PiTFT Display konfigurieren...${NC}"
if ! grep -q "pitft35-resistive" "$CONFIG_FILE"; then
    echo -e "${YELLOW}Füge PiTFT Device Tree Overlay hinzu...${NC}"
    # Display-Konfiguration anhängen
    echo "dtoverlay=pitft35-resistive,rotate=270,speed=20000000,fps=20" | sudo tee -a "$CONFIG_FILE"
fi

echo -e "${BLUE}[5/7] Python Virtual Environment (.venv) & Requirements einrichten...${NC}"
cd "$REPO_DIR"

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Erstelle .venv...${NC}"
    python3 -m venv .venv
fi

echo -e "${YELLOW}Installiere Python-Requirements...${NC}"
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo -e "${BLUE}[6/7] Autostart (~/.xinitrc) konfigurieren...${NC}"
XINIT_FILE="$HOME_DIR/.xinitrc"
echo -e "${YELLOW}Erstelle $XINIT_FILE mit robustem Netzwerk-Check...${NC}"

cat << 'EOF' > "$XINIT_FILE"
#!/bin/sh
# ==============================================================================
# Evans Dashboard Autostart
# ==============================================================================

cd ~/EvansDashboard

# Sicherstellen, dass das Netzwerk da ist, bevor wir versuchen ein Git Update zu machen.
# Verhindert Boot-Hänger bei fehlendem oder langsamem Netz.
for i in $(seq 1 15); do
    if ping -c 1 -W 2 github.com >/dev/null 2>&1; then
        echo "[BOOT] Netzwerk bereit. Ziehe Updates..." >> ~/git_pull.log
        git fetch --all >> ~/git_pull.log 2>&1
        git reset --hard origin/master >> ~/git_pull.log 2>&1
        break
    fi
    echo "[BOOT] Warte auf Netzwerk ($i/15)..." >> ~/git_pull.log
    sleep 1
done

# Starte das Dashboard im Kiosk-Modus
exec ~/.venv/bin/python -u src/main.py > ~/dashboard.log 2>&1
EOF

chmod +x "$XINIT_FILE"
chown "$CURRENT_USER:$CURRENT_USER" "$XINIT_FILE"

echo -e "${BLUE}[7/7] Systemd Service (evans-dashboard) einrichten...${NC}"
# Service Datei anpassen (User und Pfade dynamisch eintragen)
SERVICE_SRC="$REPO_DIR/evans-dashboard.service"
SERVICE_DEST="/etc/systemd/system/evans-dashboard.service"

echo -e "${YELLOW}Kopiere und aktiviere systemd-Service...${NC}"
# Falls User nicht standardmäßig 'nilsgollub' ist, ersetzen wir es im Service
sudo cp "$SERVICE_SRC" "$SERVICE_DEST"
sudo sed -i "s/User=nilsgollub/User=$CURRENT_USER/g" "$SERVICE_DEST"
sudo sed -i "s/Group=nilsgollub/Group=$CURRENT_USER/g" "$SERVICE_DEST"

# Service aktivieren
sudo systemctl daemon-reload
sudo systemctl enable evans-dashboard.service

# ==============================================================================
# WLAN / Hotspot-Konfiguration
# ==============================================================================
echo -e "${BLUE}================================================================${NC}"
echo -e "${GREEN}             Zusätzlichen WLAN-Hotspot einrichten                ${NC}"
echo -e "${BLUE}================================================================${NC}"
echo "Du kannst hier einen mobilen Hotspot (z.B. dein Smartphone) als Fallback"
echo "für unterwegs einrichten. Der Pi wechselt dann automatisch das WLAN."
echo

SETUP_HOTSPOT="false"
if [ "$NON_INTERACTIVE" = "true" ]; then
    if [ -n "$HOTSPOT_SSID" ] && [ -n "$HOTSPOT_PW" ]; then
        SETUP_HOTSPOT="true"
    fi
else
    read -p "Möchtest du jetzt einen Fallback-Hotspot einrichten? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        SETUP_HOTSPOT="true"
        read -p "Hotspot-Name (SSID) [z.B. NiniHotspot]: " HOTSPOT_SSID
        read -sp "Hotspot-Passwort: " HOTSPOT_PW
        echo
    fi
fi

if [ "$SETUP_HOTSPOT" = "true" ]; then
    if [ -n "$HOTSPOT_SSID" ] && [ -n "$HOTSPOT_PW" ]; then
        # Prüfen, ob der Hotspot in Reichweite ist (scan)
        if nmcli device wifi list | grep -q "$HOTSPOT_SSID"; then
            echo -e "${YELLOW}Hotspot gefunden. Verbinde mit $HOTSPOT_SSID...${NC}"
            if sudo nmcli device wifi connect "$HOTSPOT_SSID" password "$HOTSPOT_PW"; then
                echo -e "${GREEN}Erfolgreich mit $HOTSPOT_SSID verbunden und gespeichert!${NC}"
            else
                echo -e "${RED}Fehler beim Verbinden. Profil wird trotzdem offline gespeichert...${NC}"
            fi
        else
            # Offline-Profil anlegen, falls Hotspot nicht aktiv oder außer Reichweite
            echo -e "${YELLOW}Hotspot nicht aktiv/in Reichweite. Erstelle Profil offline...${NC}"
            if sudo nmcli connection add \
                type wifi \
                con-name "$HOTSPOT_SSID" \
                ifname wlan0 \
                ssid "$HOTSPOT_SSID" \
                -- \
                wifi-sec.key-mgmt wpa-psk \
                wifi-sec.psk "$HOTSPOT_PW" >/dev/null 2>&1; then
                echo -e "${GREEN}WLAN-Profil für $HOTSPOT_SSID wurde erfolgreich angelegt!${NC}"
            else
                echo -e "${RED}Fehler beim Erstellen des Offline-WLAN-Profils.${NC}"
            fi
        fi
    else
        echo -e "${RED}Eingabe unvollständig. Überspringe Hotspot-Einrichtung.${NC}"
    fi
fi

# ==============================================================================
# Offline-Datenbank Check
# ==============================================================================
echo -e "${BLUE}================================================================${NC}"
echo -e "${GREEN}               Datenbank-Check & Optimierung                     ${NC}"
echo -e "${BLUE}================================================================${NC}"

BOOT_MOUNT="/boot/firmware"
[ -d "$BOOT_MOUNT" ] || BOOT_MOUNT="/boot"

if [ -f "$BOOT_MOUNT/switzerland_roads.db" ]; then
    echo -e "${GREEN}Gefunden: switzerland_roads.db auf der Boot-Partition!${NC}"
    echo "Kopiere die Datenbank in das Projektverzeichnis (spart langsamen WLAN-Download)..."
    cp "$BOOT_MOUNT/switzerland_roads.db" "$REPO_DIR/"
    chown "$CURRENT_USER:$CURRENT_USER" "$REPO_DIR/switzerland_roads.db"
    echo -e "${GREEN}Datenbank erfolgreich kopiert!${NC}"
elif [ -f "$REPO_DIR/switzerland_roads.db" ]; then
    echo -e "${GREEN}Datenbank switzerland_roads.db bereits im Projektverzeichnis vorhanden.${NC}"
else
    echo -e "${YELLOW}Hinweis: switzerland_roads.db fehlt noch.${NC}"
    echo -e "Du kannst die Datei '${YELLOW}switzerland_roads.db${NC}' auf deinem PC einfach"
    echo -e "auf die Boot-Partition (die FAT32-Partition der SD-Karte) legen."
    echo -e "Das Skript hat sich gemerkt, diese beim nächsten Start automatisch zu importieren!"
fi

echo -e "${BLUE}================================================================${NC}"
echo -e "${GREEN}             Setup erfolgreich abgeschlossen! 🎉                 ${NC}"
echo -e "${BLUE}================================================================${NC}"
echo "Der Pi wird jetzt neu gestartet, um alle Änderungen (Display, UART, Service)"
echo "wirksam zu machen."
echo -e "Nach dem Neustart bootet das Dashboard automatisch! ${YELLOW}v1.1.0${NC}"
echo -e "${BLUE}================================================================${NC}"

DO_REBOOT="false"
if [ "$NON_INTERACTIVE" = "true" ]; then
    if [ "$AUTO_REBOOT" = "true" ]; then
        DO_REBOOT="true"
    fi
else
    read -p "Möchtest du den Pi jetzt neu starten? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        DO_REBOOT="true"
    fi
fi

if [ "$DO_REBOOT" = "true" ]; then
    echo -e "${YELLOW}Starte System neu...${NC}"
    sudo reboot
else
    echo -e "${YELLOW}Kein automatischer Neustart konfiguriert. Bitte starte den Pi manuell neu.${NC}"
fi
