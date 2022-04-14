from pyridy.osm.utils import iou


def test_iou():
    b1 = [0, 0, 1, 1]
    b2 = [.5, .5, 1.5, 1.5]

    assert iou(b1, b2) == 0.25 / 1.75

    b1 = [0, 0, 1, 1]
    b2 = [0, 0, 1, 1]

    assert iou(b1, b2) == 1

    b1 = [0, 0, 1, 1]
    b2 = [1.2, 1.2, 1.5, 1.5]

    assert iou(b1, b2) == 0.0

    b1 = [0, 0, 1, 1]
    b2 = [1.2, 1.2, 1.5, 1.5]

    assert iou(b2, b1) == 0.0

    b1 = [0, 0, 100, 100]
    b2 = [1, 1, 2, 2]

    assert iou(b1, b2) == 0.0001

    b1 = [0, 0, 1, 1]
    b2 = [3, 3, 4, 4]

    assert iou(b1, b2) == 0

    b1 = [-1, -1, 0, 0]
    b2 = [-4, -4, -3, -3]

    assert iou(b1, b2) == 0
