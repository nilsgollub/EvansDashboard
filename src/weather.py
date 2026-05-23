"""Reine Wetter-Hilfslogik (keine Netzwerk- oder GUI-Abhaengigkeiten)."""

# WMO Weather interpretation codes -> Schluessel fuer das Vektor-Rendering der Icons.
_WMO_CODE_TO_DESC = {
    0: "sun",  # Klar
    1: "cloud_sun",
    2: "cloud_sun",  # Heiter
    3: "cloud",
    45: "cloud",
    48: "cloud",  # Wolkig / Nebel
    51: "rain",
    53: "rain",
    55: "rain",
    56: "rain",
    57: "rain",
    61: "rain",
    63: "rain",
    65: "rain",
    66: "rain",
    67: "rain",
    80: "rain",
    81: "rain",
    82: "rain",  # Regen
    71: "snow",
    73: "snow",
    75: "snow",
    77: "snow",
    85: "snow",
    86: "snow",  # Schnee
    95: "storm",
    96: "storm",
    99: "storm",  # Gewitter
}


def weather_code_to_desc(code):
    """Bildet einen WMO-Wettercode auf einen Icon-Schluessel ab ('unknown' als Fallback)."""
    return _WMO_CODE_TO_DESC.get(code, "unknown")
