import pytest

from weather import weather_code_to_desc


@pytest.mark.parametrize(
    "code,expected",
    [
        (0, "sun"),
        (1, "cloud_sun"),
        (2, "cloud_sun"),
        (3, "cloud"),
        (45, "cloud"),
        (48, "cloud"),
        (61, "rain"),
        (80, "rain"),
        (71, "snow"),
        (86, "snow"),
        (95, "storm"),
        (99, "storm"),
        (None, "unknown"),
        (12345, "unknown"),
    ],
)
def test_weather_code_to_desc(code, expected):
    assert weather_code_to_desc(code) == expected
