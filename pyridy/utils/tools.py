import random

import numpy as np
from ipyleaflet import Circle


def generate_random_color(format="RGB"):
    """

    :param seed: Seed for random generation
    :param format: Either "RGB" or "HEX"
    :return:
    """

    if format == "RGB":
        return list(np.random.choice(range(256), size=3))
    elif format == "HEX":
        return "#" + ''.join([random.choice('0123456789ABCDEF') for _ in range(6)])
    else:
        raise ValueError("Format %s is not valid, must be 'RGB' or 'HEX' " % format)


def create_map_circle(lat, lon, color="green"):
    circle = Circle()
    circle.location = (lat, lon)
    circle.radius = 2
    circle.color = color
    circle.fill_color = color

    return circle