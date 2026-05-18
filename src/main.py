import sys
import pygame
import threading
import time
from ui import DashboardUI
from osm_api import get_speed_limit
from gps_reader import GPSReader

# Globale Variablen für Threading-Datenaustausch
current_state = {
    'speed': 0.0,
    'limit': None,
    'road_type': "Warte auf GPS...",
    'sats': 0,
    'altitude': 0.0,
    'heading': 0.0,
    'lat': None,
    'lon': None
}

def fetch_overpass_data():
    """Simuliert den Thread, der alle 10 Sekunden das Tempolimit aktualisiert"""
    while True:
        # Nur abfragen wenn wir einen GPS Fix haben
        lat, lon = current_state['lat'], current_state['lon']
        if lat is not None and lon is not None:
            print(f"[API] [{time.strftime('%H:%M:%S')}] Frage Overpass API für Position {lat:.4f}, {lon:.4f} ab...")
            limit, r_type = get_speed_limit(lat, lon)
            
            if limit is not None:
                current_state['limit'] = limit
                print(f"[API] -> Neues Limit empfangen: {limit} km/h")
                
            if r_type:
                translation = {
                    'motorway': 'Autobahn',
                    'trunk': 'Schnellstraße',
                    'primary': 'Hauptstraße',
                    'secondary': 'Landstraße',
                    'residential': 'Wohngebiet',
                    'living_street': 'Spielstraße',
                    'pedestrian': 'Fußgängerzone',
                    'unclassified': 'Nebenstraße'
                }
                current_state['road_type'] = translation.get(r_type, r_type)
        else:
            print("[API] Warte auf validen GPS-Fix für Overpass-Abfrage...")
            
        time.sleep(10)

def main():
    # GPS Thread starten
    gps_reader = GPSReader()
    gps_thread = threading.Thread(target=gps_reader.read_data, args=(current_state,), daemon=True)
    gps_thread.start()
    
    # Overpass API Thread starten
    api_thread = threading.Thread(target=fetch_overpass_data, daemon=True)
    api_thread.start()
    
    # UI Initialisieren
    ui = DashboardUI(width=480, height=320, fullscreen=False)
    clock = pygame.time.Clock()
    
    running = True
    print("[MAIN] Dashboard gestartet. Beenden mit 'Escape'.")
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    
        # Aktuellen State an UI übergeben
        ui.render(
            current_speed=current_state['speed'],
            speed_limit=current_state['limit'],
            sats=current_state['sats'],
            road_type=current_state['road_type'],
            altitude=current_state['altitude'],
            heading=current_state['heading']
        )
        
        # 30 Frames per Second
        clock.tick(30)
        
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
