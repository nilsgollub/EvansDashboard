# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Evans Co-Pilot Dashboard is a child-friendly car dashboard for a Raspberry Pi Zero WH + Adafruit 3.5" PiTFT (480×320px). It displays real-time GPS speed vs. the local speed limit (sourced offline from a local SQLite database of Swiss roads, with a live Overpass API fallback). The app is written entirely in Python and runs headless on Raspberry Pi OS.

## Running the App

```bash
# One-time setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the dashboard (from the repo root)
python src/main.py
```

The app opens a 480×320 Pygame window. Press `Escape` to quit.

## Module Self-Tests

Each of the following modules has a standalone `if __name__ == "__main__"` test block:

```bash
# Test speed limit lookup near Zurich HBf (requires switzerland_roads.db or network)
python src/osm_api.py

# Test sun elevation and display dimming calculations for Marly
python src/sun_calculator.py

# Inspect road segments in the offline database
python src/diagnose_db.py
```

## Building the Offline Database

The offline database (`switzerland_roads.db`, ~600 MB) is **not in the repo**. Build it on a machine with enough RAM and disk space:

```bash
pip install osmium   # not in requirements.txt; only needed for the build step
python build_offline_db.py
```

The script downloads `switzerland-latest.osm.pbf` from Geofabrik and parses it into a SQLite database with a bounding-box spatial index. Copy the resulting `switzerland_roads.db` to the repo root on the Pi before running the app.

## Architecture

The app uses five daemon threads plus the main UI thread, all sharing a single dict (current_state in src/main.py) for inter-thread communication. While individual dict key assignments are atomic in CPython, related updates (like lat/lon) are not synchronized; use a threading.Lock if strict consistency is required.

| Thread | Module | What it does |
|---|---|---|
| GPS | `src/gps_reader.py` | Reads NMEA sentences from serial port; on connect, sends binary UBX commands to configure the U-BLOX NEO-7M chip (Automotive mode, GPS-only [NEO-7M does not support concurrent GPS+GLONASS], 2 Hz, SBAS off, AssistNow AOP). Writes `speed`, `lat`, `lon`, `heading`, `altitude`, `sats`, `last_update`, `gps_connected` to state. |
| Simulation | `src/main.py:run_simulation` | Activates automatically if `SIMULATOR_ENABLED = True` and no real GPS fix for >10 s. Drives a loop route around Marly (Fribourg) and writes the same state keys as the GPS thread. |
| Speed limit | `src/osm_api.py:get_speed_limit` | Polls every 10 s. Tries `switzerland_roads.db` at progressive radii (30 m → 80 m → 150 m), then falls back to Overpass API. Writes `limit` and `road_type` to state. |
| Weather | `src/main.py:fetch_weather_data` | Polls Open-Meteo every 15 min using current GPS coords. Writes `weather_temp` and `weather_desc` (key strings like `"sun"`, `"rain"`) to state. |
| WiFi monitor | `src/main.py:wifi_monitor` | Polls `nmcli` every 15 s (no scan, read-only). Writes `wifi_ssid` and `wifi_signal` to state. |
| **Main / UI** | `src/ui.py` | Renders at 30 FPS via Pygame directly to the framebuffer. Reads from `current_state`. Also manages the hardware backlight (`/sys/class/backlight/`) and feeds the hardware watchdog (`/dev/watchdog`). |

### GPS Status Logic

`has_fix` = `last_update` is non-zero **and** < 10 s ago. The UI shows four states: `LIVE GPS` (green), `SUCHE GPS` (blue, pulsing), `SIMULATOR` (orange), `KEIN SENSOR` (gray). The `gps_connected` flag reflects serial port open/closed, separate from whether a satellite fix exists.

### Speed Limit Database Schema

Table `road_segments`: `(id, way_id, maxspeed, highway, name, lat1, lon1, lat2, lon2, min_lat, max_lat, min_lon, max_lon)`. Lookup uses a bounding-box SQL query then finds the geometrically nearest segment via `calculate_distance_to_segment` (flat planar projection, fast for short distances).

### Display Dimming

`src/sun_calculator.py` implements NOAA solar elevation math (no third-party library). Full brightness (1.0) when sun > 0°, minimum 15% at < −6°, linear in between. Hardware backlight is written to `/sys/class/backlight/*/brightness`; a software SDL overlay is applied as a fallback.

## Key Configuration (top of `src/main.py`)

```python
SIMULATOR_ENABLED = False  # True to enable Marly simulation when GPS is lost
DIMMING_ENABLED   = False  # True to auto-dim at night based on solar elevation
GPS_MODE          = 'serial'
GPS_PORT          = 20000  # for network GPS mode (unused in production)
```

## Language & Conventions

- All code comments, `print` log lines, and UI strings are in **German** (Swiss standard: always `ss`, never `ß`).
- Road type keys from OSM (`motorway`, `residential`, etc.) are translated to Swiss German in `DashboardUI.ROAD_TYPE_TRANSLATIONS`.
- `scratch/` holds one-off utility scripts; they are not part of the running application.

## Deployment on the Pi

The systemd service `evans-dashboard.service` starts an X server (`startx`), which runs `~/.xinitrc`. That file pulls the latest code from GitHub and then launches `src/main.py`. To install:

```bash
sudo cp evans-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable evans-dashboard.service
```

Run `setup_fresh_pi.sh` on a fresh Raspberry Pi OS Lite install to automate the full setup (UART, display overlay, venv, systemd service, WLAN hotspot).

Logs are written to `~/dashboard.log`. Monitor live with `tail -f ~/dashboard.log`.

## Diagnostic & Helper Scripts

- `test_gps.py`: Simples GPS-Diagnose- und Test-Skript. Liest die serielle Schnittstelle aus, sendet die UBX-Konfigurationssequenz aus `src/ubx.py` und gibt NMEA-Zeilen geparst auf stdout aus. Ideal zum Testen ohne Pygame.
- `reset_gps.py`: Ein Blind-Recovery-Skript zur Wiederherstellung des Werkszustands (9600 Baud, 1 Hz) über serielle Ports, indem ein `CFG-CFG`-Reset an diverse Schnittstellen und Baudraten gesendet wird.
- `setup_wifi.sh`: Bash-Skript zur Konfiguration von WiFi-Fallbacks und Autoconnect-Prioritäten über `nmcli` (Heim-WLAN `Skynet` = Priorität 10, Handy-Hotspot `NiniHotspot` = Priorität 5).

## Testing, Linting & Formatting

Use the following commands from the repository root:

```bash
# Run pytest test suite
pytest

# Ruff check (linting)
ruff check .

# Black (formatting check / format)
black --check .
black .
```

## Hardware Quirks & Gotchas

- **U-blox NEO-7M - No Concurrent GNSS**: Der NEO-7M Chip unterstützt **keinen** gleichzeitigen GPS- und GLONASS-Betrieb. Das Senden eines `CFG-GNSS`-Konfigurationspakets, das beide Netze aktiviert, kann zum Hängenbleiben führen. In `src/ubx.py` muss das Senden von `GNSS_PAYLOAD` auskommentiert bleiben.
- **CFG-NAV5 `pAcc` Trap**: Beim Konfigurieren von `CFG-NAV5` darf das Bit 4 (Position Mask) **nicht** gesetzt werden, wenn `pAcc` mit `0` belegt ist. Dies zwingt das GPS-Modul, auf eine physikalisch unmögliche Präzision von 0,0 Metern zu warten, wodurch das Modul niemals einen GPS-Fix deklariert (obwohl 12+ Satelliten in Sicht sind). Verwende immer die Maske `\x01\x00` (nur Dynamic Model Bit 0 aktiv).
- **Konfigurationspersistenz**: Einstellungen werden über `CFG-CFG` (Save Config) permanent in den Flash-Speicher des GPS-Moduls geschrieben und überleben Power-Cycles. Wenn fehlerhafte Werte eingespielt wurden, muss `reset_gps.py` zur Bereinigung ausgeführt werden.
- **WLAN-Frequenzband Pi Zero 2 W**: Der Raspberry Pi Zero 2 W besitzt ausschließlich ein **2,4 GHz** Funkmodul. Er kann 5-GHz-Netzwerke physikalisch nicht sehen. Daher müssen eventuelle Smartphone-Hotspots zwingend auf 2,4 GHz (z. B. Option "Maximale Kompatibilität" bei iPhones) eingestellt werden.

