#!/bin/bash
# ==============================================================================
# WLAN Konfigurations-Skript fuer Evans Dashboard
# ==============================================================================
# Konfiguriert das Heim-WLAN (Skynet) und den Hotspot (NiniHotspot) mit Prioritaeten
# ==============================================================================

set -e

echo "Konfiguriere Heim-Netzwerk (Skynet) mit Prioritaet 10..."
sudo nmcli connection delete "Skynet" >/dev/null 2>&1 || true
sudo nmcli connection add \
    type wifi \
    con-name "Skynet" \
    ifname wlan0 \
    ssid "Skynet" \
    -- \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "JhiswenP3003!" \
    connection.autoconnect-priority 10

echo "Konfiguriere Hotspot (NiniHotspot) mit Prioritaet 5..."
sudo nmcli connection delete "NiniHotspot" >/dev/null 2>&1 || true
sudo nmcli connection add \
    type wifi \
    con-name "NiniHotspot" \
    ifname wlan0 \
    ssid "NiniHotspot" \
    -- \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "JhiswenP3003!" \
    connection.autoconnect-priority 5

echo "Lade Netzwerk-Konfiguration neu..."
sudo nmcli connection reload

echo "Fertig! Der Pi wird sich jetzt bevorzugt mit 'Skynet' verbinden,"
echo "und andernfalls auf 'NiniHotspot' zurueckgreifen."
