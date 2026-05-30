import glob
import math
import os
import random
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import pygame
import requests

from config import (
    DIMMING_ENABLED,
    GPS_IP,
    GPS_MODE,
    GPS_PORT,
    SIMULATOR_ENABLED,
)
from gps_reader import GPSReader
from osm_api import get_speed_limit
from state_store import save_last_fix
from sun_calculator import get_dimming_factor
from ttff_log import TTFFLogger
from ui import DashboardUI
from version import VERSION
from weather import weather_code_to_desc

# Globale Variablen für Threading-Datenaustausch
current_state = {
    "speed": 0.0,
    "limit": None,
    "road_type": "Suche GPS...",
    "sats": 0,
    "altitude": 0.0,
    "heading": 0.0,
    "lat": 46.779,  # Startwert Marly, damit Wetter sofort geladen wird
    "lon": 7.152,
    "last_update": 0.0,  # Timestamp des letzten echten GPS-Updates
    "wifi_ssid": None,  # Aktuell verbundenes WLAN
    "wifi_signal": 0,  # Signalstaerke in % (0-100)
    "weather_temp": None,
    "weather_desc": None,
    "dim_factor": 1.0,  # Dynamischer Dimmfaktor (1.0 = voll, 0.15 = gedimmt)
    "gps_connected": False,  # Zeigt an, ob das GPS-Modul oder der Netzwerk-Server verbunden ist
}

# --- Hardware Backlight-Steuerung ---
_backlight_path = None
_max_brightness = 255


def init_hardware_backlight():
    global _backlight_path, _max_brightness
    paths = glob.glob("/sys/class/backlight/*")
    if paths:
        _backlight_path = paths[0]
        try:
            with open(os.path.join(_backlight_path, "max_brightness"), "r") as f:
                _max_brightness = int(f.read().strip())
            print(f"[SYSTEM] Hardware-Backlight gefunden unter {_backlight_path} (Max Helligkeit: {_max_brightness})")
        except Exception:
            _max_brightness = 255


def set_hardware_backlight(dim_factor):
    global _backlight_path, _max_brightness
    if _backlight_path is None:
        return False
    try:
        val = int(max(0.1, dim_factor) * _max_brightness)
        # Wert im gültigen Bereich halten
        val = max(0, min(val, _max_brightness))
        with open(os.path.join(_backlight_path, "brightness"), "w") as f:
            f.write(str(val))
        return True
    except PermissionError:
        # Kein Schreibrecht (z. B. wenn nicht als sudo gestartet)
        return False
    except Exception as e:
        print(f"[SYSTEM] Fehler beim Schreiben des Backlights: {e}")
        return False


# --- Hardware & Software Watchdog ---
_watchdog_fd = None


def init_hardware_watchdog():
    global _watchdog_fd
    if os.path.exists("/dev/watchdog"):
        try:
            _watchdog_fd = os.open("/dev/watchdog", os.O_WRONLY)
            print("[SYSTEM] Hardware-Watchdog (/dev/watchdog) erfolgreich initialisiert.")
        except Exception as e:
            print(f"[SYSTEM] Hardware-Watchdog konnte nicht geöffnet werden: {e}")
            _watchdog_fd = None


def feed_watchdogs():
    global _watchdog_fd
    # 1. Hardware Watchdog füttern (falls initialisiert)
    if _watchdog_fd is not None:
        try:
            os.write(_watchdog_fd, b"\x00")
        except Exception as e:
            print(f"[SYSTEM] Fehler beim Füttern des Hardware-Watchdogs: {e}")

    # 2. Software Watchdog-Heartbeat-Datei schreiben (für externe Kontrollskripte)
    try:
        with open("/tmp/dashboard_heartbeat", "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def close_hardware_watchdog():
    """Deaktiviert den Watchdog kontrolliert (Magic-Close 'V'), damit der Kernel
    den Pi nach `systemctl stop` nicht zwangsrebootet."""
    global _watchdog_fd
    if _watchdog_fd is None:
        return
    try:
        os.write(_watchdog_fd, b"V")
        os.close(_watchdog_fd)
        print("[SYSTEM] Hardware-Watchdog sauber geschlossen (Magic-Close 'V').")
    except Exception as e:
        print(f"[SYSTEM] Fehler beim Schliessen des Watchdogs: {e}")
    finally:
        _watchdog_fd = None


def persist_current_fix():
    """Schreibt die zuletzt bekannte Position atomar auf Disk, sobald ein Fix da ist."""
    last_up = current_state.get("last_update", 0.0)
    if last_up <= 0.0:
        return False
    return save_last_fix(
        lat=current_state.get("lat"),
        lon=current_state.get("lon"),
        altitude=current_state.get("altitude"),
        sats=current_state.get("sats"),
        t=last_up,
    )


def run_simulation():
    """
    Simuliert eine Autofahrt durch Marly (Schweiz), wenn kein echtes GPS-Signal da ist.
    Die Simulation stoppt sofort und nahtlos, wenn echte GPS-Daten empfangen werden.
    """
    if not SIMULATOR_ENABLED:
        return
    # Marly-Rundkurs Koordinaten (Latitude, Longitude)
    marly_route = [
        (46.7836, 7.1643),  # Start: Route de Fribourg (Brücke)
        (46.7865, 7.1630),  # Route de Fribourg (Zentrum)
        (46.7890, 7.1615),  # Route de Fribourg (Nord)
        (46.7880, 7.1670),  # Route des Préts
        (46.7845, 7.1685),  # Route de la Gruyère (Ost)
        (46.7800, 7.1710),  # Route de la Gruyère (Süd)
        (46.7765, 7.1735),  # Route de la Gruyère / Route de Corbaraye
        (46.7760, 7.1680),  # Route de la Singine
        (46.7785, 7.1610),  # Route du Midi (Süd)
        (46.7840, 7.1600),  # Route du Midi (Nord)
    ]

    current_wp_idx = 0
    sim_lat, sim_lon = marly_route[0]
    sim_speed = 0.0
    sim_heading = 0.0
    sim_alt = 620.0

    # Warte 8 Sekunden, um dem GPS Zeit für den Verbindungsaufbau zu geben
    time.sleep(8)

    dt = 0.1  # Update alle 100ms (10 Hz)

    while True:
        # Falls echtes GPS-Signal vorhanden ist (letztes Update vor weniger als 10 Sekunden)
        last_up = current_state.get("last_update", 0.0)
        if last_up > 0.0 and (time.time() - last_up) < 10.0:
            # Echtes GPS ist aktiv, schlafe kurz und prüfe erneut
            time.sleep(1.0)
            continue

        # Simulation läuft! Wegpunkt-Navigation
        next_wp_idx = (current_wp_idx + 1) % len(marly_route)
        target_lat, target_lon = marly_route[next_wp_idx]

        # Richtung und Distanz berechnen
        lat_diff = target_lat - sim_lat
        lon_diff = target_lon - sim_lon

        d_lat_m = lat_diff * 111000.0
        d_lon_m = lon_diff * 76000.0  # Cosinusfaktor bei 46.78° lat
        distance = math.sqrt(d_lat_m**2 + d_lon_m**2)

        if distance < 8.0:
            # Wegpunkt erreicht!
            current_wp_idx = next_wp_idx
            continue

        # Richtungswinkel (Heading) berechnen
        sim_heading = math.degrees(math.atan2(d_lon_m, d_lat_m)) % 360

        # Zielgeschwindigkeit basierend auf dem aktuellen Tempolimit
        target_speed = current_state["limit"] if current_state["limit"] is not None else 50.0
        target_speed += random.uniform(-1.0, 1.0)

        # Sanftes Beschleunigen / Abbremsen
        if sim_speed < target_speed:
            sim_speed += 0.8
        elif sim_speed > target_speed:
            sim_speed -= 0.6

        sim_speed = max(10.0, min(sim_speed, 120.0))

        # Distanzschritt in Metern
        step_m = (sim_speed / 3.6) * dt

        # In Grad konvertieren
        lat_step = (step_m / 111000.0) * (d_lat_m / distance if distance > 0 else 0)
        lon_step = (step_m / 76000.0) * (d_lon_m / distance if distance > 0 else 0)

        sim_lat += lat_step
        sim_lon += lon_step

        # Höhe leicht schwanken lassen
        sim_alt += random.uniform(-0.1, 0.1)
        sim_alt = max(610.0, min(sim_alt, 640.0))

        # State updaten (wird von UI und OSM-Thread gelesen)
        current_state["speed"] = sim_speed
        current_state["lat"] = sim_lat
        current_state["lon"] = sim_lon
        current_state["heading"] = sim_heading
        current_state["altitude"] = sim_alt
        current_state["sats"] = 8  # 8 simulierte Satelliten

        time.sleep(dt)


def fetch_overpass_data():
    """Gewinnt Tempolimits und Strassennamen aus der Offline-Datenbank oder API"""
    while True:
        lat, lon = current_state["lat"], current_state["lon"]
        if lat is not None and lon is not None:
            # Letztes GPS-Update prüfen, um zu wissen, ob wir simulieren
            last_up = current_state.get("last_update", 0.0)
            is_sim = SIMULATOR_ENABLED and (last_up == 0.0 or (time.time() - last_up) >= 10.0)

            prefix = "[API-SIM]" if is_sim else "[API]"
            print(f"{prefix} [{time.strftime('%H:%M:%S')}] Frage Tempolimit für Position {lat:.4f}, {lon:.4f} ab...")

            limit, r_type = get_speed_limit(lat, lon)

            if limit is not None:
                current_state["limit"] = limit
                print(f"{prefix} -> Tempolimit erhalten: {limit} km/h")
            else:
                current_state["limit"] = None

            if r_type:
                current_state["road_type"] = r_type
            else:
                current_state["road_type"] = "unbekannt"
        else:
            print("[API] Warte auf GPS-Fix oder Simulationsstart...")

        # Schnelleres Abfragen im Simulationsmodus am Anfang, sonst alle 10 Sekunden
        time.sleep(4 if current_state.get("last_update", 0.0) == 0.0 else 10)


def fetch_weather_data():
    """Holt das aktuelle Wetter von Open-Meteo (kostenlos, kein API Key) für die aktuelle Position"""
    while True:
        success = False
        lat, lon = current_state.get("lat"), current_state.get("lon")
        if lat is not None and lon is not None:
            try:
                # API Call Open-Meteo
                url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    weather = data.get("current_weather", {})
                    temp = weather.get("temperature")
                    code = weather.get("weathercode")

                    weather_desc = weather_code_to_desc(code)

                    if temp is not None:
                        current_state["weather_temp"] = temp
                        current_state["weather_desc"] = weather_desc
                        print(f"[WEATHER] Wetter geupdatet: {temp}°C | {weather_desc}")
                        success = True
            except Exception as e:
                print(f"[WEATHER] Fehler beim Abrufen des Wetters: {e}")

        if success:
            # Bei Erfolg 15 Minuten warten
            time.sleep(15 * 60)
        else:
            # Bei Fehler oder fehlendem GPS alle 10 Sekunden neu versuchen
            time.sleep(10)


def wifi_monitor():
    """
    Überwacht den WLAN-Status per nmcli (NetworkManager CLI).
    Nutzt 'connection show --active' statt 'device wifi' um keinen
    teuren WLAN-Scan auszulösen (kritisch für Pi Zero WH Performance).
    """
    # Warten bis das System vollständig gebootet ist
    time.sleep(15)
    print("[WIFI] WiFi-Monitor gestartet")

    while True:
        try:
            # Aktive WLAN-Verbindung abfragen (KEIN Scan!)
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            ssid = None
            for line in result.stdout.strip().split("\n"):
                parts = line.split(":")
                if len(parts) >= 2 and parts[1] == "802-11-wireless":
                    ssid = parts[0]
                    break

            # Signalstärke separat abfragen (liest nur cached Werte)
            signal = 0
            if ssid:
                sig_result = subprocess.run(
                    ["nmcli", "-t", "-f", "SIGNAL", "device", "wifi", "list", "--rescan", "no"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                # Erste Zeile mit Wert nehmen (aktives Netz steht oben)
                for line in sig_result.stdout.strip().split("\n"):
                    try:
                        signal = int(line.strip())
                        if signal > 0:
                            break
                    except ValueError:
                        continue

            current_state["wifi_ssid"] = ssid
            current_state["wifi_signal"] = signal
            if ssid:
                print(f"[WIFI] Verbunden: {ssid} ({signal}%)")
            else:
                print("[WIFI] Nicht verbunden")
        except FileNotFoundError:
            # nmcli nicht verfügbar (z.B. unter Windows beim Entwickeln)
            current_state["wifi_ssid"] = None
            current_state["wifi_signal"] = 0
        except subprocess.TimeoutExpired:
            print("[WIFI] nmcli Timeout - überspringe")
        except Exception as e:
            print(f"[WIFI] Fehler: {e}")
        time.sleep(15)


def _install_shutdown_handler(ttff_logger):
    """Faengt SIGTERM/SIGINT ab, flusht den letzten Fix und gibt den Watchdog frei.

    Bei hartem Stromabriss (Zuendung aus) bringt das nichts - aber jedes
    'systemctl stop', 'Ctrl-C' oder OOM-Kill kommt jetzt sauber durch.
    """

    def _handler(signum, _frame):
        name = signal.Signals(signum).name
        print(f"[MAIN] Shutdown-Signal {name} empfangen.")
        persist_current_fix()
        if ttff_logger:
            ttff_logger.shutdown(reason=name)
        close_hardware_watchdog()
        # pygame.quit() vor sys.exit, sonst kann das TTY auf dem Pi-Framebuffer
        # nach systemctl stop in unbrauchbarem Zustand zurueckbleiben.
        pygame.quit()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def main():
    print(f"[MAIN] Evans Co-Pilot Dashboard v{VERSION}")
    print("[MAIN] Dashboard gestartet. Beenden mit 'Escape'.")

    # Hardware-Subsysteme initialisieren
    init_hardware_backlight()
    set_hardware_backlight(1.0)  # Zu Beginn explizit auf 100% Helligkeit setzen
    init_hardware_watchdog()

    # TTFF-Diagnose und Shutdown-Handler
    ttff_logger = TTFFLogger()
    _install_shutdown_handler(ttff_logger)

    # GPS Thread starten
    gps_reader = GPSReader(mode=GPS_MODE, ip=GPS_IP, port=GPS_PORT, ttff_logger=ttff_logger)
    gps_thread = threading.Thread(target=gps_reader.read_data, args=(current_state,), daemon=True)
    gps_thread.start()

    # Simulations-Thread starten
    sim_thread = threading.Thread(target=run_simulation, daemon=True)
    sim_thread.start()

    # Overpass API / Offline-DB Thread starten
    api_thread = threading.Thread(target=fetch_overpass_data, daemon=True)
    api_thread.start()

    # Wetter Thread starten
    weather_thread = threading.Thread(target=fetch_weather_data, daemon=True)
    weather_thread.start()

    # WiFi-Monitor Thread starten
    wifi_thread = threading.Thread(target=wifi_monitor, daemon=True)
    wifi_thread.start()

    # UI Initialisieren
    ui = DashboardUI(width=480, height=320, fullscreen=False)
    clock = pygame.time.Clock()

    running = True
    frame_count = 0
    dim_factor = 1.0

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # Watchdogs füttern (in jeder Iteration der Rendering-Schleife)
        feed_watchdogs()

        # Letzte bekannte Position alle ~30 s persistieren (atomar). Falls die
        # Zuendung unmittelbar danach ausgeht, ist die Position auf der SD-Karte
        # und steht beim naechsten Start als AID-INI-Hint zur Verfuegung.
        # 30 FPS * 30 s = 900 Frames.
        if frame_count % 900 == 0:
            persist_current_fix()

        # Prüfen, ob wir im Simulationsmodus sind (kein GPS-Update in den letzten 10s und Simulation aktiv)
        last_up = current_state.get("last_update", 0.0)

        # Ein Fix liegt vor, wenn das letzte Update weniger als 10 Sekunden alt ist
        # und mindestens ein Latitude-Wert vorhanden ist
        time_since_last_update = time.time() - last_up
        has_fix = last_up > 0.0 and time_since_last_update < 10.0 and current_state.get("lat") is not None

        is_sim = SIMULATOR_ENABLED and not has_fix

        # Helligkeit berechnen und anwenden (alle 90 Frames = ca. 3 Sek bei 30 FPS)
        frame_count += 1
        if frame_count % 90 == 0:
            if DIMMING_ENABLED:
                lat = current_state.get("lat")
                lon = current_state.get("lon")
                if lat is not None and lon is not None:
                    dim_factor = get_dimming_factor(lat, lon, datetime.now(timezone.utc))
                    current_state["dim_factor"] = dim_factor
                    # Versuche, das Hardware-Backlight anzupassen
                    set_hardware_backlight(dim_factor)
            else:
                dim_factor = 1.0
                current_state["dim_factor"] = 1.0
                set_hardware_backlight(1.0)

        # Aktuellen State an UI uebergeben (inkl. Dimmfaktor)
        ui.render(
            current_speed=current_state["speed"],
            speed_limit=current_state["limit"],
            sats=current_state["sats"],
            road_type=current_state["road_type"],
            altitude=current_state["altitude"],
            heading=current_state["heading"],
            is_simulated=is_sim,
            has_fix=has_fix,
            weather_temp=current_state.get("weather_temp"),
            weather_desc=current_state.get("weather_desc"),
            wifi_ssid=current_state.get("wifi_ssid"),
            wifi_signal=current_state.get("wifi_signal", 0),
            version=VERSION,
            dim_factor=dim_factor,
            gps_connected=current_state.get("gps_connected", False),
        )

        # 30 Frames per Second
        clock.tick(30)

    # Normale Beendigung (ESC): letzten Fix flushen und Watchdog sauber schliessen.
    persist_current_fix()
    ttff_logger.shutdown(reason="esc")
    close_hardware_watchdog()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
