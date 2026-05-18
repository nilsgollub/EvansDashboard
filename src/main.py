import sys
import pygame
import threading
import time
import math
import random
from ui import DashboardUI
from osm_api import get_speed_limit
from gps_reader import GPSReader

# Konfiguration
SIMULATOR_ENABLED = False  # Auf True setzen, um Marly-Simulation bei GPS-Verlust zu aktivieren

# Globale Variablen für Threading-Datenaustausch
current_state = {
    'speed': 0.0,
    'limit': None,
    'road_type': "Suche GPS...",
    'sats': 0,
    'altitude': 0.0,
    'heading': 0.0,
    'lat': None,
    'lon': None,
    'last_update': 0.0  # Timestamp des letzten echten GPS-Updates
}

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
        last_up = current_state.get('last_update', 0.0)
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
        target_speed = current_state['limit'] if current_state['limit'] is not None else 50.0
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
        current_state['speed'] = sim_speed
        current_state['lat'] = sim_lat
        current_state['lon'] = sim_lon
        current_state['heading'] = sim_heading
        current_state['altitude'] = sim_alt
        current_state['sats'] = 8  # 8 simulierte Satelliten
        
        time.sleep(dt)

def fetch_overpass_data():
    """Gewinnt Tempolimits und Strassennamen aus der Offline-Datenbank oder API"""
    while True:
        lat, lon = current_state['lat'], current_state['lon']
        if lat is not None and lon is not None:
            # Letztes GPS-Update prüfen, um zu wissen, ob wir simulieren
            last_up = current_state.get('last_update', 0.0)
            is_sim = SIMULATOR_ENABLED and (last_up == 0.0 or (time.time() - last_up) >= 10.0)
            
            prefix = "[API-SIM]" if is_sim else "[API]"
            print(f"{prefix} [{time.strftime('%H:%M:%S')}] Frage Tempolimit für Position {lat:.4f}, {lon:.4f} ab...")
            
            limit, r_type = get_speed_limit(lat, lon)
            
            if limit is not None:
                current_state['limit'] = limit
                print(f"{prefix} -> Tempolimit erhalten: {limit} km/h")
            else:
                current_state['limit'] = None
                
            if r_type:
                current_state['road_type'] = r_type
            else:
                current_state['road_type'] = "unbekannt"
        else:
            print("[API] Warte auf GPS-Fix oder Simulationsstart...")
            
        # Schnelleres Abfragen im Simulationsmodus am Anfang, sonst alle 10 Sekunden
        time.sleep(4 if current_state.get('last_update', 0.0) == 0.0 else 10)

def main():
    # GPS Thread starten
    gps_reader = GPSReader()
    gps_thread = threading.Thread(target=gps_reader.read_data, args=(current_state,), daemon=True)
    gps_thread.start()
    
    # Simulations-Thread starten
    sim_thread = threading.Thread(target=run_simulation, daemon=True)
    sim_thread.start()
    
    # Overpass API / Offline-DB Thread starten
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
                    
        # Prüfen, ob wir im Simulationsmodus sind (kein GPS-Update in den letzten 10s und Simulation aktiv)
        last_up = current_state.get('last_update', 0.0)
        is_sim = SIMULATOR_ENABLED and (last_up == 0.0 or (time.time() - last_up) >= 10.0)
        
        # Aktuellen State an UI übergeben
        ui.render(
            current_speed=current_state['speed'],
            speed_limit=current_state['limit'],
            sats=current_state['sats'],
            road_type=current_state['road_type'],
            altitude=current_state['altitude'],
            heading=current_state['heading'],
            is_simulated=is_sim
        )
        
        # 30 Frames per Second
        clock.tick(30)
        
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
