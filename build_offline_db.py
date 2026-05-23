#!/usr/bin/env python3
import logging
import os
import sqlite3
import sys
import time
import urllib.request

# Logging-Konfiguration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Standardpfade
PBF_URL = "https://download.geofabrik.de/europe/switzerland-latest.osm.pbf"
PBF_FILE = "switzerland-latest.osm.pbf"
DB_FILE = "switzerland_roads.db"

# Schweizer Standard-Tempolimits falls kein maxspeed-Tag in OSM existiert
DEFAULT_SPEEDS = {
    "motorway": 120,  # Autobahn
    "motorway_link": 80,
    "trunk": 100,  # Autostrasse
    "trunk_link": 80,
    "primary": 80,  # Hauptstrasse (Ausserorts)
    "primary_link": 80,
    "secondary": 80,  # Verbindungsstrasse
    "secondary_link": 80,
    "tertiary": 80,
    "tertiary_link": 80,
    "unclassified": 80,
    "residential": 50,  # Innerorts
    "living_street": 20,  # Begegnungszone
}


def download_pbf():
    """Lädt die aktuelle OSM-PBF-Datei für die Schweiz herunter, falls nicht vorhanden."""
    if os.path.exists(PBF_FILE):
        logger.info(f"'{PBF_FILE}' existiert bereits. Überspringe Download.")
        return True

    logger.info(f"Starte Download von {PBF_URL}...")
    start_time = time.time()

    try:

        def progress_callback(block_num, block_size, total_size):
            read_so_far = block_num * block_size
            if total_size > 0:
                percent = read_so_far * 100 / total_size
                # Nur alle 10% loggen um Flut im Log zu vermeiden
                if int(percent) % 10 == 0 and int(percent - (block_size * 100 / total_size)) % 10 != 0:
                    logger.info(
                        f"Download-Fortschritt: {percent:.1f}% ({read_so_far / (1024*1024):.1f} MB von {total_size / (1024*1024):.1f} MB)"
                    )

        urllib.request.urlretrieve(PBF_URL, PBF_FILE, progress_callback)
        duration = time.time() - start_time
        logger.info(f"Download erfolgreich beendet in {duration:.1f} Sekunden.")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Download der PBF-Datei: {e}")
        return False


def build_database():
    """Parst die PBF-Datei und erstellt die SQLite-Datenbank."""
    try:
        import osmium
    except ImportError:
        logger.error(
            "Das Python-Modul 'osmium' ist nicht installiert.\n"
            "Bitte installiere es mit:\n"
            "  - Auf dem Raspberry Pi: sudo apt install python3-osmium\n"
            "  - Auf dem PC (Windows/Mac): pip install osmium"
        )
        sys.exit(1)

    logger.info(f"Erstelle SQLite-Datenbank '{DB_FILE}'...")

    # Falls die DB existiert, löschen wir sie für einen sauberen Build
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Tabellen-Schema erstellen
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS road_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            way_id INTEGER,
            maxspeed INTEGER,
            highway TEXT,
            name TEXT,
            lat1 REAL,
            lon1 REAL,
            lat2 REAL,
            lon2 REAL,
            min_lat REAL,
            max_lat REAL,
            min_lon REAL,
            max_lon REAL
        )
    """)

    # Metadaten-Tabelle
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()

    class RoadSegmentHandler(osmium.SimpleHandler):
        def __init__(self):
            super(RoadSegmentHandler, self).__init__()
            self.segments = []
            self.total_ways_processed = 0
            self.total_segments_saved = 0

        def way(self, w):
            if "highway" not in w.tags:
                return

            highway = w.tags["highway"]
            if highway not in DEFAULT_SPEEDS:
                return

            self.total_ways_processed += 1

            # Maxspeed ermitteln (OSM Tag oder Fallback)
            maxspeed = None
            if "maxspeed" in w.tags:
                try:
                    speed_str = w.tags["maxspeed"]
                    if speed_str == "none":
                        maxspeed = 120
                    else:
                        # Extrahiere Ziffern
                        digits = "".join(filter(str.isdigit, speed_str))
                        if digits:
                            maxspeed = int(digits)
                except ValueError:
                    pass

            if maxspeed is None:
                maxspeed = DEFAULT_SPEEDS[highway]

            name = w.tags.get("name")

            # Koordinaten der Knotenpunkte extrahieren
            nodes = []
            try:
                for node in w.nodes:
                    nodes.append((node.lat, node.lon))
            except osmium.InvalidLocationError:
                # Knotenpunkte lagen außerhalb des Caches
                return

            if len(nodes) < 2:
                return

            # Zerlege den Weg in gerade Liniensegmente
            for i in range(len(nodes) - 1):
                lat1, lon1 = nodes[i]
                lat2, lon2 = nodes[i + 1]

                min_lat = min(lat1, lat2)
                max_lat = max(lat1, lat2)
                min_lon = min(lon1, lon2)
                max_lon = max(lon1, lon2)

                self.segments.append(
                    (w.id, maxspeed, highway, name, lat1, lon1, lat2, lon2, min_lat, max_lat, min_lon, max_lon)
                )

            # Batch-Schreiben in SQLite um RAM zu sparen und Geschwindigkeit zu maximieren
            if len(self.segments) >= 50000:
                self.save_batch()

        def save_batch(self):
            if not self.segments:
                return
            cursor.executemany(
                """
                INSERT INTO road_segments (
                    way_id, maxspeed, highway, name,
                    lat1, lon1, lat2, lon2,
                    min_lat, max_lat, min_lon, max_lon
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                self.segments,
            )
            self.total_segments_saved += len(self.segments)
            conn.commit()
            logger.info(
                f"Fortschritt: {self.total_ways_processed:,} Wege verarbeitet, {self.total_segments_saved:,} Straßensegmente in DB gespeichert."
            )
            self.segments = []

    logger.info("Starte OSM PBF-Parsing. Dies kann auf dem Pi Zero einige Minuten dauern...")
    start_time = time.time()

    handler = RoadSegmentHandler()
    # locations=True sorgt dafür, dass osmium die Koordinaten der Nodes zwischenspeichert
    handler.apply_file(PBF_FILE, locations=True)

    # Letzten Batch speichern
    handler.save_batch()

    # Indizes erstellen für extrem schnelle Bounding-Box Abfragen im Fahrbetrieb
    logger.info("Erstelle räumliche Datenbank-Indizes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bbox ON road_segments(min_lat, max_lat, min_lon, max_lon)")

    # Metadaten schreiben
    cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ("region", "Switzerland"))
    cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ("created_at", str(time.time())))
    cursor.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("ways_processed", str(handler.total_ways_processed)),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("segments_saved", str(handler.total_segments_saved)),
    )

    conn.commit()
    conn.close()

    duration = time.time() - start_time
    logger.info(f"Datenbank erfolgreich erstellt in {duration:.1f} Sekunden!")
    logger.info(f"Gespeicherte Segmente: {handler.total_segments_saved:,}")
    logger.info(f"Dateigröße von '{DB_FILE}': {os.path.getsize(DB_FILE) / (1024*1024):.1f} MB")


def verify_database():
    """Führt eine schnelle Testabfrage aus, um die Datenbankfunktion zu verifizieren."""
    if not os.path.exists(DB_FILE):
        return

    logger.info("Verifiziere Datenbank mit Test-Abfrage...")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Zürich Hauptbahnhof Koordinaten (47.3769, 8.5417)
        lat, lon = 47.3769, 8.5417
        delta = 0.0005  # ca. 50 Meter Box

        cursor.execute(
            """
            SELECT name, highway, maxspeed
            FROM road_segments
            WHERE max_lat >= ? AND min_lat <= ? AND max_lon >= ? AND min_lon <= ?
            LIMIT 5
        """,
            (lat - delta, lat + delta, lon - delta, lon + delta),
        )

        rows = cursor.fetchall()
        logger.info("Gefundene Straßen nahe Zürich HB:")
        for row in rows:
            logger.info(f"  - Name: {row[0]}, Typ: {row[1]}, Speedlimit: {row[2]} km/h")

        conn.close()
    except Exception as e:
        logger.error(f"Fehler bei der Datenbank-Verifikation: {e}")


if __name__ == "__main__":
    logger.info("=== EvansDashboard Offline-DB-Builder ===")

    # 1. Download
    if download_pbf():
        # 2. Parse & Build
        build_database()
        # 3. Test
        verify_database()
        logger.info("Fertig! Du kannst die Datei 'switzerland_roads.db' nun auf das Dashboard kopieren.")
    else:
        logger.error("Vorgang abgebrochen wegen Download-Fehler.")
