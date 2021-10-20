import random
import socket

import numpy as np
from ipyleaflet import Circle


def internet(host="8.8.8.8", port=53, timeout=3):
    """
    Host: 8.8.8.8 (google-public-dns-a.google.com)
    OpenPort: 53/tcp
    Service: domain (DNS/TCP)
    Based on https://stackoverflow.com/questions/3764291/how-can-i-see-if-theres-an-available-and-active-network-connection-in-python
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        print(ex)
        return False


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


def requires_internet(func):
    def inner(*args, **kwargs):
        if internet():
            return func(*args, **kwargs)
        else:
            raise ConnectionError("This function requires an internet connection")

    return inner()
