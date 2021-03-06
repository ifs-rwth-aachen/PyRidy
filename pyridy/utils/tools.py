import random
import socket
from typing import Optional, Union

import numpy as np
from ipyleaflet import Circle

from pyridy import config


def internet(host="8.8.8.8", port=53, timeout=None):
    """ Function that returns True if an internet connection is available, False if otherwise

    Based on https://stackoverflow.com/questions/3764291/how-can-i-see-if-theres-an-available-and-active-network-connection-in-python

    Parameters
    ----------
    host: str
        IP of the host, which should be used for checking the internet connections
    port: int
        Port that should be used
    timeout: int
        Timeout in seconds

    Returns
    -------
    bool
    """
    if not timeout:
        timeout = config.options["SOCKET_TIMEOUT"]

    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        print(ex)
        return False


def generate_random_color(color_format: str = "RGB") -> Union[list, str]:
    """
    Parameters
    ----------
    color_format: str
        Color format of the generated color, either "RGB" or "HEX". RGB values range from 0 to 255
    """

    if color_format == "RGB":
        return list(np.random.choice(range(256), size=3))
    elif color_format == "HEX":
        return "#" + ''.join([random.choice('0123456789ABCDEF') for _ in range(6)])
    else:
        raise ValueError("Format %s is not valid, must be 'RGB' or 'HEX' " % color_format)


def create_map_circle(lat: float, lon: float, color="green", radius: int = 2):
    """ Creates an ipyleaflet circle marker

    Parameters
    ----------
    lat: float
    lon: float
    color: str
    radius: int

    Returns
    -------
    Circle
    """
    circle = Circle()
    circle.location = (lat, lon)
    circle.radius = radius
    circle.color = color
    circle.fill_color = color

    return circle


def requires_internet(func):
    """ Decorator for functions that require internet

    Parameters
    ----------
    func: func
        Function that requires an active internet connection
    Returns
    -------

    """

    def inner(*args, **kwargs):
        if internet():
            return func(*args, **kwargs)
        else:
            raise ConnectionError("This function requires an internet connection")

    return inner()
