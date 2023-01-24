import math
from math import radians, cos, sin, asin, sqrt
from typing import Union, List, Tuple

import numpy as np
import overpy
import scipy.interpolate as si
from numpy.linalg import norm
from shapely.geometry import LineString

from pyridy import config


def calc_unit_vector(v: Union[list, np.ndarray]) -> np.ndarray:
    """
    Returns the unit vector of the given vector v

    Parameters
    ----------
    v : array_like
        Vector of which the unit vector should be calculated
    Returns
        -------
        unit vector: np.ndarray
    """
    return v / np.linalg.norm(v)


def calc_angle_between(v1: Union[list, np.ndarray], v2: Union[list, np.ndarray]) -> np.ndarray:
    """
    Returns the angle in radians between vectors v1 and v2

    Parameters
    ----------
    v1 : array_like
        First vector
    v2 : array_like
        Second vector
    Returns
        -------
        angle: np.ndarray
    """
    v1_u = calc_unit_vector(v1)
    v2_u = calc_unit_vector(v2)
    return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0))


def calc_curvature(x: List[float], y: List[float]) -> List[float]:
    """
    Calculates the Menger curvature for a set of coordinates

    Parameters
    ----------
    x: List[float]
        x-coordinate
    y: List[float]
        y-coordinate
    Returns
    -------
    list of Menger curvature of the coordinates

    Raises
    -------
    ValueError: Raised if x and y are not of same length.
    """
    if len(x) != len(y):
        raise ValueError("x and y have to be same length")

    if len(x) > 0 and len(y) > 0:
        c = [0]

        for i in range(len(x)):
            if not (i == 0 or i == len(x) - 1):
                # Get three neighbored points
                x1 = x[i - 1]
                y1 = y[i - 1]

                x2 = x[i]
                y2 = y[i]

                x3 = x[i + 1]
                y3 = y[i + 1]

                # Get distance between each of the points
                s_a = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
                s_b = math.sqrt((x2 - x3) ** 2 + (y2 - y3) ** 2)
                s_c = math.sqrt((x3 - x1) ** 2 + (y3 - y1) ** 2)

                s = (s_a + s_b + s_c) / 2
                a = s * (s - s_a) * (s - s_b) * (s - s_c)

                if a > 0:
                    A = math.sqrt(a)
                else:
                    A = 0

                # Calculate sign
                dx12 = x2 - x1
                dy12 = y2 - y1

                dx23 = x3 - x2
                dy23 = y3 - y2

                sgn = np.sign(np.cross([dx12, dy12], [dx23, dy23]))

                # Menger Curvature
                res = sgn * 4 * A / (s_a * s_b * s_c)
                if not math.isnan(res):
                    c.append(res)
                else:
                    c.append(0.0)

        c.append(0)
        return c
    else:
        return []


def calc_distance_from_xy(x: List[float], y: List[float]) -> Tuple[list, list]:
    """
    Computes distances between a set of x y coordinates as well as the total distance

    Parameters
    ----------
    x: List[float]
        x-coordinate
    y: List[float]
        y-coordinate

    Returns
    -------
    Tuple
        List containing total distance, list of pairwise distances
    Raises
    -------
    ValueError: Raised if x and y are not of same length.
    """
    if len(x) != len(y):
        raise ValueError("x and y have to be same length")

    if x and y:
        s = [0]
        ds = []

        for i in range(len(x)):
            if i >= 1:
                x1 = x[i - 1]
                y1 = y[i - 1]

                x2 = x[i]
                y2 = y[1]

                ds.append(math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2))

        # Integrate ds
        s.extend(np.cumsum(ds))

        return s, ds
    else:
        return [], []


def calc_distance_from_lon_lat(lon: List[float], lat: List[float]):
    """ Computes pairwise and total distance using geodesic distance of individual lat/lon coordinates

    Parameters
    ----------
    lon: list
        Longitude
    lat: list
        Latitude

    Returns
    -------
    pairwise distance: list
    total distance: list

    Raises
    -------
    ValueError: Raised if x and y are not of same length.
    """
    if len(lon) != len(lat):
        raise ValueError("x and y have to be same length")

    if lon and lat:
        s = [0]
        ds = []

        for i in range(len(lon)):
            if i >= 1:
                ds.append(config.geod.inv(lon[i - 1], lat[i - 1], lon[i], lat[i])[2])

        # Integrate ds
        s.extend(np.cumsum(ds))

        return s, ds
    else:
        return [], []


def convert_way_to_line_string(w: overpy.Way, frmt: str = "lon,lat") -> LineString:
    """
    Converts a way to LineString; one-dimensional figure comprising one or more line segments.

    Parameters
    ----------
    w: overpy.Way
        The way to be converted
    frmt: str
        The location's format. Defaults to "lon,lat"

    Returns
    -------
    LineString

    Raises
    -------
    ValueError: Raised if the format is unknown.
    """
    if frmt == "lon,lat":
        coords = [(float(n.lon), float(n.lat)) for n in w.nodes]
        return LineString(coords)
    elif frmt == "x,y":
        lons, lats = [float(n.lon) for n in w.nodes], [float(n.lat) for n in w.nodes]
        xs, ys = config.proj(lons, lats)
        coords = [(x, y) for x, y in zip(xs, ys)]
        return LineString(coords)
    else:
        raise ValueError(f"Unknown format: {frmt}")


def convert_lon_lat_to_xy(lon: List[float], lat: List[float], adjust_zero_point: bool = False):
    """
    Convert lon/lat coordinates to a metric coordinate system. The first coordinate is used for zero-point in
    the metric coordinate system

    Parameters
    ----------
    lon: list[float]
        Longitude
    lat: list[float]
        Latitude
    adjust_zero_point: bool
        If True, first coordinate will be 0,0. Defaults to False.

    Returns
    -------
    x: list
    y: list
    """
    if lon and lat:
        x, y = config.proj(lon, lat)
        if adjust_zero_point:
            return [el - x[0] for el in x], [el - y[0] for el in y]
        else:
            return x, y
    else:
        return [], []


def bspline(cv, n=10000, degree=3, periodic=False):
    """
    Calculate n samples on a bspline

    Parameters
    ----------
     cv: array_like
        Array ov control vertices
    n: int
        Number of samples to return
    degree: int
        Curve degree
    periodic: bool
        True - Curve is closed, False - Curve is open
    Returns
    -------
    np.ndarray

        """

    # If periodic, extend the point array by count+degree+1
    cv = np.asarray(cv)
    count = len(cv)

    if periodic:
        factor, fraction = divmod(count + degree + 1, count)
        cv = np.concatenate((cv,) * factor + (cv[:fraction],))
        count = len(cv)
        degree = np.clip(degree, 1, degree)

    # If opened, prevent degree from exceeding count-1
    else:
        degree = np.clip(degree, 1, count - 1)

    # Calculate knot vector
    kv = None
    if periodic:
        kv = np.arange(0 - degree, count + degree + degree - 1, dtype='int')
    else:
        kv = np.concatenate(([0] * degree, np.arange(count - degree + 1), [count - degree] * degree))

    # Calculate query range
    u = np.linspace(periodic, (count - degree), n)

    # Calculate result
    return np.array(si.splev(u, (kv, cv.T, degree))).T


def project_point_onto_line(line: Union[np.ndarray, list], point: Union[np.ndarray, list]) -> tuple:
    """
    Returns a tuple with the point where the orthogonal projections of the given points intersects the given the
    line and secondly the (perpendicular) distance to this point
    Parameters
    ----------
    line: np.ndarray or list
        List of two points defining the line in the form of [[x1, y1],[x2, y2]]
    point: np.ndarray or list
        Point of which the distance perpendicular from the line should be calculated to
    Returns
    -------
    tuple

    Raises
    -------
    ValueError: Raised if the given line consists of two identical points.

    """
    if type(line) is list:
        line = np.array(line)

    if type(point) is list:
        point = np.array(point)

    p1 = line[0]
    p2 = line[1]
    p3 = point

    if np.array_equal(p1, p2):
        raise ValueError("Given line consists of two identical points!")

    d = norm(np.cross(p2 - p1, p1 - p3)) / norm(p2 - p1)

    n = p2 - p1
    n = n / norm(n, 2)

    p = p1 + n * np.dot(p3 - p1, n)

    return p, d


def boxes_to_edges(boxes):
    """
    Source: https://stackoverflow.com/questions/4842613/merge-lists-that-share-common-elements

    treat `l` as a Graph and returns it's edges
    to_edges(['a','b','c','d']) -> [(a,b), (b,c),(c,d)]
    Parameters
    -------
    boxes: list
    Returns
    -------
    None
    """
    it = iter(boxes)
    last = next(it)

    for current in it:
        yield last, current
        last = current


def overlap(b1: List[float], b2: List[float], thres: float = .8) -> bool:
    """
    Check whether two bounding boxes have an overlap larger than thres
    Each box must be of form x_min, y_min, x_max, y_max

    Parameters
    ----------
    b1: List[float]
        A box defined by its coordinates [x_min, y_min, x_max, y_max]
    b2: List[float]
        A box defined by its coordinates [x_min, y_min, x_max, y_max]
    thres: float
        Defaults to .8

    Returns
    -------
    bool
    """
    a1 = abs(b1[2] - b1[0]) * abs(b1[3] - b1[1])
    a2 = abs(b2[2] - b2[0]) * abs(b2[3] - b2[1])

    if b2[0] > b1[2] or b2[1] > b1[3]:  # Boxes not overlapping
        return False
    else:
        inter = (b1[2] - b2[0]) * (b1[3] - b2[1])

        r1 = inter / a1 if a1 > 0 else -1.0
        r2 = inter / a2 if a2 > 0 else -1.0

        if r1 > thres or r2 > thres:
            return True
        else:
            return False


def iou(b1: List[float], b2: List[float]):
    """
    Calculates the Intersection over Union metric for two bounding boxes
    Each box must be of form x_min, y_min, x_max, y_max

    Parameters
    ----------
    b1: List[float]
        A box defined by its coordinates [x_min, y_min, x_max, y_max]
    b2: List[float]
        A box defined by its coordinates [x_min, y_min, x_max, y_max]
    Returns
    -------
    iou: float
        Intersection over Union
    """
    b1_x0, b1_y0 = b1[0], b1[1]
    b1_x1, b1_y1 = b1[2], b1[3]

    b2_x0, b2_y0 = b2[0], b2[1]
    b2_x1, b2_y1 = b2[2], b2[3]

    b1_w = b1[2] - b1[0]
    b1_h = b1[3] - b1[1]

    b2_w = b2[2] - b2[0]
    b2_h = b2[3] - b2[1]

    a1 = abs(b1_w) * abs(b1_h)
    a2 = abs(b2_w) * abs(b2_h)

    x0 = max(min(b1_x0, b1_x1), min(b2_x0, b2_x1))
    y0 = max(min(b1_y0, b1_y1), min(b2_y0, b2_y1))
    x1 = min(max(b1_x0, b1_x1), max(b2_x0, b2_x1))
    y1 = min(max(b1_y0, b1_y1), max(b2_y0, b2_y1))

    if x1 < x0 or y1 < y0:
        return 0.0

    inter = (x1 - x0) * (y1 - y0)
    union = a1 + a2 - inter

    iou = inter / union if union > 0 else -1.0

    assert 0.0 <= iou <= 1.0
    return iou


def is_point_within_line_projection(line: Union[np.ndarray, list], point: Union[np.ndarray, list]) -> bool:
    """
    Checks whether a given points line projection falls within the points that the define the line

    Parameters
    ----------
    line: Union[np.ndarray, list]
        List of two points defining the line in the form of [[x1, y1],[x2, y2]]
    point: Union[np.ndarray, list]
        Point of which it should be determined whether the projection onto the line falls within the points that
        define the line
    Returns
    -------
    bool
    """
    if type(line) is list:
        line = np.array(line)

    if type(point) is list:
        point = np.array(point)

    p1 = line[0]
    p2 = line[1]
    p3 = point

    s = p2 - p1
    v = p3 - p1

    b = (0 <= np.inner(v, s) <= np.inner(s, s))

    return b


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Calculate the great circle distance in kilometers between two points on the earth (specified in decimal degrees)
    Source:
    https://stackoverflow.com/questions/4913349/haversine-formula-in-python-bearing-and-distance-between-two-gps-points

    Parameters
    ----------
    lon1: float
        Longitude of first point
    lat1: float
        Latitude of first point
    lon2: float
        Longitude of second point
    lat2: float
        Latitude of second point
    Returns
    -------
    float
        Distance between the points in meters

    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Radius of earth in meters
    return c * r
