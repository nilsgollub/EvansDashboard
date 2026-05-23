from osm_api import calculate_distance_to_segment


def test_point_on_segment_is_zero_distance():
    # Punkt liegt exakt auf der Strecke (46.0,7.0)->(46.0,7.01)
    dist = calculate_distance_to_segment(46.0, 7.005, 46.0, 7.0, 46.0, 7.01)
    assert dist < 1.0


def test_perpendicular_distance_in_meters():
    # Punkt 0.001 Grad noerdlich der Mitte der Strecke -> ca. 111 m
    dist = calculate_distance_to_segment(46.001, 7.005, 46.0, 7.0, 46.0, 7.01)
    assert abs(dist - 111.0) < 1.0


def test_degenerate_segment_uses_endpoint():
    # Strecke ist ein einzelner Punkt; Distanz = Abstand zum Punkt (~111 m)
    dist = calculate_distance_to_segment(46.001, 7.0, 46.0, 7.0, 46.0, 7.0)
    assert abs(dist - 111.0) < 1.0
