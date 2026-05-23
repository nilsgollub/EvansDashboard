from datetime import datetime, timezone

from sun_calculator import get_dimming_factor, get_solar_elevation

# Marly (Freiburg, Schweiz) - Referenzkoordinaten des Projekts
MARLY_LAT = 46.779
MARLY_LON = 7.152


def test_daytime_returns_full_brightness():
    dt = datetime(2026, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
    assert get_dimming_factor(MARLY_LAT, MARLY_LON, dt) == 1.0


def test_deep_night_returns_minimum_brightness():
    dt = datetime(2026, 12, 21, 0, 0, 0, tzinfo=timezone.utc)
    assert get_dimming_factor(MARLY_LAT, MARLY_LON, dt) == 0.15


def test_solar_elevation_sign_day_vs_night():
    noon = datetime(2026, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
    midnight = datetime(2026, 12, 21, 0, 0, 0, tzinfo=timezone.utc)
    assert get_solar_elevation(MARLY_LAT, MARLY_LON, noon) > 0
    assert get_solar_elevation(MARLY_LAT, MARLY_LON, midnight) < -6


def test_dimming_factor_always_within_bounds():
    for hour in range(24):
        dt = datetime(2026, 3, 21, hour, 0, 0, tzinfo=timezone.utc)
        factor = get_dimming_factor(MARLY_LAT, MARLY_LON, dt)
        assert 0.15 <= factor <= 1.0
