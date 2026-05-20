import os
import sqlite3
import math
import requests
import logging
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Pfad zur Offline-Datenbank (liegt im Hauptverzeichnis des Projekts)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "switzerland_roads.db")

_local = threading.local()

def get_db_connection():
    """
    Gibt eine thread-lokale, optimierte SQLite-Verbindung zurück.
    Öffnet die Datenbank im reinen Read-Only-Modus für maximale SD-Kartenschonung.
    """
    if not hasattr(_local, "conn") or _local.conn is None:
        if os.path.exists(DB_PATH):
            try:
                # Zwingend im Read-Only-Modus öffnen
                _local.conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
                # Performance-PRAGMAs
                _local.conn.execute("PRAGMA cache_size = -20000;")  # ca. 20 MB Cache im RAM
                _local.conn.execute("PRAGMA temp_store = MEMORY;")   # Temp-Tabellen im RAM
                _local.conn.execute("PRAGMA query_only = ON;")       # Keine versehentlichen Writes erlauben
                logger.info("Optimierte Thread-lokale SQLite-Verbindung geöffnet.")
            except Exception as e:
                logger.error(f"Fehler beim Erstellen der DB-Verbindung: {e}")
                return None
        else:
            return None
    return _local.conn

def calculate_distance_to_segment(p_lat, p_lon, lat1, lon1, lat2, lon2):
    """
    Berechnet die rechtwinklige Distanz (in Metern) von einem GPS-Punkt (p_lat, p_lon)
    zu einem Liniensegment (lat1, lon1) -> (lat2, lon2).
    Verwendet eine flache Projektion für extrem schnelle Berechnung auf kurzen Distanzen.
    """
    try:
        # Breitengrad im Bogenmaß zur Längengrad-Skalierung
        lat_avg_rad = math.radians((lat1 + lat2 + p_lat) / 3.0)
        cos_lat = math.cos(lat_avg_rad)
        
        # Konvertiere in ein planares Koordinatensystem (in Grad)
        # x = lon * cos_lat, y = lat
        ax = lon1 * cos_lat
        ay = lat1
        bx = lon2 * cos_lat
        by = lat2
        px = p_lon * cos_lat
        py = p_lat
        
        # Vektor AB
        abx = bx - ax
        aby = by - ay
        
        # Vektor AP
        apx = px - ax
        apy = py - ay
        
        # Länge von AB quadriert
        ab_len_sq = abx * abx + aby * aby
        
        if ab_len_sq == 0:
            # Segment ist ein einzelner Punkt
            cx = ax
            cy = ay
        else:
            # Projektionsfaktor t (geklemmt zwischen 0 und 1)
            t = (apx * abx + apy * aby) / ab_len_sq
            t = max(0.0, min(1.0, t))
            
            # Nächster Punkt C auf dem Segment
            cx = ax + t * abx
            cy = ay + t * aby
        
        # Abstand in Grad-Einheiten berechnen
        dx = px - cx
        dy = py - cy
        
        # In Meter umrechnen (1 Grad Breitengrad ist ca. 111.000 Meter)
        dx_meters = dx * 111000.0
        dy_meters = dy * 111000.0
        
        return math.sqrt(dx_meters * dx_meters + dy_meters * dy_meters)
    except Exception as e:
        logger.error(f"Fehler bei Distanzberechnung: {e}")
        return float('inf')

def get_speed_limit_offline(lat, lon, radius=30):
    """
    Fragt die lokale SQLite-Datenbank nach der nächsten Straße ab.
    Gibt ein Tuple zurück: (Tempolimit als int (oder None), Straßentyp als string)
    """
    conn = get_db_connection()
    if not conn:
        return None, None

    try:
        # Bounding-Box für Vorauswahl berechnen (beschleunigt die Suche massiv)
        # 1 Grad Breitengrad ist ca. 111.000 Meter
        lat_delta = radius / 111000.0
        
        # Längengrad-Delta unter Einbezug der Erdkrümmung
        cos_lat = math.cos(math.radians(lat))
        if cos_lat > 0:
            lon_delta = radius / (111000.0 * cos_lat)
        else:
            lon_delta = radius / 111000.0
            
        min_lat = lat - lat_delta
        max_lat = lat + lat_delta
        min_lon = lon - lon_delta
        max_lon = lon + lon_delta
        
        cursor = conn.cursor()
        
        # Schnellabfrage aller Segmente, die mit unserer Bounding-Box überlappen
        cursor.execute("""
            SELECT way_id, maxspeed, highway, name, lat1, lon1, lat2, lon2 
            FROM road_segments 
            WHERE max_lat >= ? AND min_lat <= ? AND max_lon >= ? AND min_lon <= ?
        """, (min_lat, max_lat, min_lon, max_lon))
        
        rows = cursor.fetchall()
        
        if not rows:
            return None, "Unbekannt"
            
        min_dist = float('inf')
        best_speed = None
        highway_type = "Unbekannt"
        
        # Suche das mathematisch am nächsten gelegene Straßensegment
        for row in rows:
            way_id, maxspeed, highway, name, lat1, lon1, lat2, lon2 = row
            dist = calculate_distance_to_segment(lat, lon, lat1, lon1, lat2, lon2)
            if dist < min_dist and dist <= radius:
                min_dist = dist
                best_speed = maxspeed
                highway_type = highway
                
        # Wenn kein Segment nahe genug war
        if min_dist > radius:
            return None, "Unbekannt"
            
        return best_speed, highway_type
        
    except sqlite3.Error as e:
        logger.error(f"Fehler bei Offline-Datenbankabfrage: {e}")
        return None, "Fehler"

def get_speed_limit_online(lat, lon, radius=30):
    """
    Fallbacks: Fragt die Overpass API nach dem Tempolimit im angegebenen Radius ab.
    """
    query = f"""
    [out:json];
    way(around:{radius},{lat},{lon})["highway"];
    out tags;
    """
    
    headers = {
        'User-Agent': 'EvansDashboard/1.0 (Testprojekt für privates Dashboard)',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.post(OVERPASS_URL, data={'data': query}, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        elements = data.get('elements', [])
        if not elements:
            return None, "Unbekannt"
            
        best_speed = None
        highway_type = "Unbekannt"
        
        for element in elements:
            tags = element.get('tags', {})
            if 'maxspeed' in tags:
                try:
                    speed_str = tags['maxspeed']
                    if speed_str == 'none':
                        best_speed = 120  # Schweizer Autobahn-Standard
                    else:
                        best_speed = int(''.join(filter(str.isdigit, speed_str)))
                except ValueError:
                    pass
            
            if 'highway' in tags and highway_type == "Unbekannt":
                highway_type = tags['highway']
                
            if best_speed is not None:
                break
                
        return best_speed, highway_type
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Fehler bei der Overpass API Abfrage: {e}")
        return None, "Fehler"

def get_speed_limit(lat, lon, radius=30):
    """
    Prüft erst, ob die Offline-Datenbank existiert und nutzt diese mit einem
    progressiven Radius (30m -> 80m -> 150m) für maximale Ausfallsicherheit.
    Falls nicht, wird die Online Overpass API als Fallback abgefragt.
    """
    if os.path.exists(DB_PATH):
        # Stufe 1: Präzise Nahbereichssuche (30m)
        speed, h_type = get_speed_limit_offline(lat, lon, radius)
        if h_type != "Fehler" and h_type != "Unbekannt":
            return speed, h_type
            
        # Stufe 2: Erweiterte Suche (80m) bei GPS-Drift oder Simulations-Abweichungen
        speed, h_type = get_speed_limit_offline(lat, lon, 80)
        if h_type != "Fehler" and h_type != "Unbekannt":
            return speed, h_type
            
        # Stufe 3: Weitbereichs-Suche (150m) als letzter Rettungsanker
        speed, h_type = get_speed_limit_offline(lat, lon, 150)
        if h_type != "Fehler" and h_type != "Unbekannt":
            return speed, h_type
            
    # Online Fallback
    return get_speed_limit_online(lat, lon, radius)

if __name__ == "__main__":
    # Test-Abfrage (Zürich, Nähe Hauptbahnhof)
    print("=== EvansDashboard Speed-Engine Test ===")
    print(f"Offline-DB vorhanden: {os.path.exists(DB_PATH)}")
    limit, r_type = get_speed_limit(47.3769, 8.5417)
    print(f"Ergebnis -> Limit: {limit} km/h, Typ: {r_type}")
