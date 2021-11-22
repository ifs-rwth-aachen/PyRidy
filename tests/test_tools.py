import numpy as np

from pyridy.osm.utils import calc_perpendicular_distance, is_point_within_line_projection


def test_calc_perpendicular_distance():
    d = calc_perpendicular_distance(line=[[0, 0], [1, 0]], point=[0.5, 0.5])
    assert d == 0.5

    d = calc_perpendicular_distance(line=np.array([[0, 0], [1, 0]]), point=np.array([0.5, 0.5]))
    assert d == 0.5

    d = calc_perpendicular_distance(line=[[0, 0], [1, 1]], point=[1, 0])
    assert d == 1 / np.sqrt(2)

    d = calc_perpendicular_distance(line=[[0, 0], [1, 0]], point=[1100, .5])
    assert d == 0.5


def test_is_point_within_line_projection():
    b = is_point_within_line_projection(line=[[0, 0], [1, 0]], point=[1100, .5])
    assert not b

    b = is_point_within_line_projection(line=[[0, 0], [1, 0]], point=[0.5, 0.5])
    assert b

    b = is_point_within_line_projection(line=[[0, 0], [-1, 0]], point=[0.5, 0.5])
    assert not b

    b = is_point_within_line_projection(line=[[0, 0], [1, 1]], point=[2, 2])
    assert not b

    b = is_point_within_line_projection(line=[[0, 0], [1, 1]], point=[.5, .5])
    assert b
