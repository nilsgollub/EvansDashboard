import math
from datetime import datetime, timezone


def get_solar_elevation(lat, lon, dt_utc):
    """
    Berechnet die Sonnenhöhe (Solar Elevation) in Grad für gegebene Koordinaten und UTC-Zeit.
    Basiert auf den mathematischen Standard-Formeln der NOAA (offline, keine Bibliotheken nötig).
    """
    # 1. Tag des Jahres und Stunde in UTC ermitteln
    day_of_year = dt_utc.timetuple().tm_yday
    hour_utc = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0

    # 2. Fractional Year in Bogenmass berechnen
    gamma = (2 * math.pi / 365.0) * (day_of_year - 1 + (hour_utc - 12) / 24.0)

    # 3. Deklination der Sonne in Bogenmass berechnen
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )

    # 4. Equation of Time (Zeitgleichung) in Minuten berechnen
    eqt = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )

    # 5. Wahre Sonnenzeit in Minuten berechnen (UTC-basiert)
    # Längengrad-Korrektur: 4 Minuten pro Grad Längengrad
    time_offset = eqt + 4.0 * lon
    true_solar_time = hour_utc * 60.0 + time_offset

    # Hour angle (Stundenwinkel) in Grad berechnen
    ha = (true_solar_time / 4.0) - 180.0

    # In Bogenmass konvertieren
    lat_rad = math.radians(lat)
    ha_rad = math.radians(ha)

    # 6. Kosinus des Zenitwinkels berechnen
    cos_zenith = math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(decl) * math.cos(ha_rad)

    # Klemmen auf [-1, 1], um Rechenfehler bei arccos zu vermeiden
    cos_zenith = max(-1.0, min(1.0, cos_zenith))

    zenith_rad = math.acos(cos_zenith)
    elevation = 90.0 - math.degrees(zenith_rad)

    return elevation


def get_dimming_factor(lat, lon, dt_utc=None):
    """
    Berechnet den Dimm-Faktor basierend auf der Sonnenhöhe.
    Gibt einen Wert zwischen 0.15 (Nacht, maximal gedimmt) und 1.0 (Tag, volle Helligkeit) zurück.
    Der Übergang erfolgt stufenlos während der bürgerlichen Dämmerung (0° bis -6°).
    """
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)

    elevation = get_solar_elevation(lat, lon, dt_utc)

    # Stufenlose Transition
    if elevation > 0.0:
        # Voller Tag -> 100% Helligkeit
        return 1.0
    elif elevation < -6.0:
        # Volle Nacht -> 15% Helligkeit (schont Evans Augen perfekt)
        return 0.15
    else:
        # Dämmerungsbereich: Linearer Übergang zwischen 0° (1.0) und -6° (0.15)
        # Formel: 1.0 - (0.85 * (elevation / -6.0))
        factor = 1.0 - 0.85 * (elevation / -6.0)
        return max(0.15, min(1.0, factor))


if __name__ == "__main__":
    # Testläufe für Marly (Freiburg, Schweiz)
    # Latitude: 46.779, Longitude: 7.152
    marly_lat = 46.779
    marly_lon = 7.152

    print("=== Sonnenstands- und Dimm-Simulator-Test ===")

    # 20. Mai (heute), Mittags (12:00 UTC = 14:00 Schweizer Sommerzeit)
    dt_noon = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
    el_noon = get_solar_elevation(marly_lat, marly_lon, dt_noon)
    dim_noon = get_dimming_factor(marly_lat, marly_lon, dt_noon)
    print(f"Mittags (UTC 12:00) -> Sonnenhöhe: {el_noon:.2f}°, Helligkeit: {dim_noon * 100:.1f}%")

    # 20. Mai (heute), Abends zur Dämmerung (19:30 UTC = 21:30 Schweizer Sommerzeit)
    dt_twilight = datetime(2026, 5, 20, 19, 45, 0, tzinfo=timezone.utc)
    el_twilight = get_solar_elevation(marly_lat, marly_lon, dt_twilight)
    dim_twilight = get_dimming_factor(marly_lat, marly_lon, dt_twilight)
    print(f"Dämmerung (UTC 19:45) -> Sonnenhöhe: {el_twilight:.2f}°, Helligkeit: {dim_twilight * 100:.1f}%")

    # 20. Mai (heute), Nachts (23:00 UTC = 01:00 Schweizer Sommerzeit)
    dt_night = datetime(2026, 5, 20, 23, 0, 0, tzinfo=timezone.utc)
    el_night = get_solar_elevation(marly_lat, marly_lon, dt_night)
    dim_night = get_dimming_factor(marly_lat, marly_lon, dt_night)
    print(f"Nachts (UTC 23:00) -> Sonnenhöhe: {el_night:.2f}°, Helligkeit: {dim_night * 100:.1f}%")
