from abc import ABC

import overpy

from pyridy.osm.utils import OSMTrack
from pyridy.utils.tools import generate_random_color


class OSMRailwayElement(ABC):
    def __init__(self, n: overpy.Node):
        self.n = n
        self.attributes = n.attributes
        self.lat = float(n.lat)
        self.lon = float(n.lon)
        self.id = n.id

        if hasattr(n, "ways"):
            self.ways = n.ways
        else:
            self.ways = None

        self.__dict__.update(n.tags)


class OSMLevelCrossing(OSMRailwayElement):
    def __init__(self, n: overpy.Node):
        super(OSMLevelCrossing, self).__init__(n)

    def __repr__(self):
        return "Level Crossing at (%s, %s)" % (self.lon, self.lat)


class OSMRailwaySignal(OSMRailwayElement):
    def __init__(self, n: overpy.Node):
        super(OSMRailwaySignal, self).__init__(n)

    def __repr__(self):
        return "Signal at (%s, %s)" % (self.lon, self.lat)


class OSMRailwaySwitch(OSMRailwayElement):
    def __init__(self, n: overpy.Node):
        super(OSMRailwaySwitch, self).__init__(n)

    def __repr__(self):
        return "Switch at (%s, %s)" % (self.lon, self.lat)


class OSMRailwayLine(OSMTrack):
    def __init__(self, id: int, ways: list, tags: dict, members: list):
        super().__init__(id=id, ways=ways, name=tags.get("name", ""),
                         color=tags.get("colour", generate_random_color("HEX")))
        self.__dict__.update(tags)
        self.members = members

    def __repr__(self):
        return self.__dict__.get("name", "")
