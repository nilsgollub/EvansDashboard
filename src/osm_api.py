import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def get_speed_limit(lat, lon, radius=30):
    """
    Fragt die Overpass API nach dem Tempolimit im angegebenen Radius ab.
    Gibt ein Tuple zurück: (Tempolimit als int (oder None), Straßentyp als string)
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
        # POST Request ist bei Overpass oft stabiler und unterstützt den User-Agent besser
        response = requests.post(OVERPASS_URL, data={'data': query}, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        elements = data.get('elements', [])
        if not elements:
            return None, "Unbekannt"
            
        # Durchsuche die gefundenen Wege nach einem Tempolimit
        best_speed = None
        highway_type = "Unbekannt"
        
        for element in elements:
            tags = element.get('tags', {})
            if 'maxspeed' in tags:
                try:
                    speed_str = tags['maxspeed']
                    if speed_str == 'none':
                        best_speed = 130 # Oder was in CH üblich ist
                    else:
                        # Extrahiere nur Zahlen (falls "50 mph" o.ä.)
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

if __name__ == "__main__":
    # Test-Abfrage (Zürich, Nähe Hauptbahnhof)
    print("Teste Overpass API...")
    limit, r_type = get_speed_limit(47.3769, 8.5417)
    print(f"Limit: {limit} km/h, Typ: {r_type}")
