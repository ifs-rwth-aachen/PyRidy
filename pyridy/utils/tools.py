import random

import numpy as np


def generate_random_color(color_format="RGB"):
    """
    :param color_format: Either "RGB" or "HEX"
    :return:
    """

    if color_format == "RGB":
        return list(np.random.choice(range(256), size=3))
    elif color_format == "HEX":
        return "#" + ''.join([random.choice('0123456789ABCDEF') for _ in range(6)])
    else:
        raise ValueError("Format %s is not valid, must be 'RGB' or 'HEX' " % color_format)
