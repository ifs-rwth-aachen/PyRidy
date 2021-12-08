import numpy as np

from pyridy.osm.utils import project_point_onto_line, is_point_within_line_projection


def test_project_point_onto_line():
    p, d = project_point_onto_line(line=[[0, 0], [1, 0]], point=[0.5, 0.5])
    assert d == 0.5
    assert np.array_equal(p, np.array([0.5, 0]))

    p, d = project_point_onto_line(line=[[0, 0], [1, 1]], point=[1, 0])
    assert d == 1 / np.sqrt(2)

    p, d = project_point_onto_line(line=[[0, 0], [1, 0]], point=[1100, .5])
    assert d == 0.5
    assert np.array_equal(p, np.array([1100, 0]))


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
