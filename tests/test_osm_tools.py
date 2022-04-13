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
