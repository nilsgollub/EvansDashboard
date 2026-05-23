import pytest

from osm_api import parse_maxspeed


@pytest.mark.parametrize(
    "value,expected",
    [
        ("50", 50),
        ("none", 120),
        ("50 km/h", 50),
        ("30 mph", 30),
        ("", None),
        ("walk", None),
        (None, None),
        (80, 80),
    ],
)
def test_parse_maxspeed(value, expected):
    assert parse_maxspeed(value) == expected
