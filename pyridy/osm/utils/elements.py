import itertools
import logging
from abc import ABC
from typing import List

import networkx as nx
import overpy

from pyridy import config
from pyridy.osm.utils import convert_lon_lat_to_xy, calc_curvature, calc_distance_from_lon_lat
from pyridy.utils.tools import generate_random_color

logger = logging.getLogger(__name__)


class OSMResultNode:
    def __init__(self, lon: float, lat: float,
                 value=None, f=None, proc=None, direction: str = "", color: str = None):
        """
        Class representing a Node calculated by PyRidy

        Parameters
        ----------
        lat: float
            Latitude of node coordinate
        lon: float
            Longitude of node coordinate
        value:
            Node value
        f: RDYFile
        proc: processor
        direction: str
        color: str
            Node color. Defaults to None.

        Returns
        -------
        None
        """
        # TODO: complete doc for file, proc and direction
        self.lat = lat
        self.lon = lon
        self.value = value
        self.f = f
        self.proc = proc
        self.direction = direction
        self.color = '#CC071E' if not color else color

    def __repr__(self):
        return f'Result node at ({self.lon}, {self.lat} of value {self.value})'


class OSMResultWay:
    def __init(self, way, res: float = .5):
        """
        Class representing an element of type way

        Parameters
        ----------
        way : overpy.Way
        res : float
            Calculated result. Defaults to 0.5.

        Returns
        -------
        None
        """
        # TODO: add doc for parameter way
        self.way: overpy.Way = way
        self.res = res


class OSMRailwayElement(ABC):
    def __init__(self, n: overpy.Node):
        """
        Abstract Base Class for railway elements retrieved from OpenStreetMap

        Parameters
        ----------
        n : overpy.Node
            OpenStreetMap node queried by Overpy
        """
        self.n = n
        self.attributes = n.attributes
        self.tags = n.tags
        self.lat = float(n.lat)
        self.lon = float(n.lon)
        self.id = n.id

        if hasattr(n, "ways"):
            self.ways = n.ways
        else:
            self.ways = None

        self.__dict__.update(n.tags)  # Different elements contain different tags


class OSMLevelCrossing(OSMRailwayElement):
    def __init__(self, n: overpy.Node):
        """
        Class representing railway level crossings

        See https://wiki.openstreetmap.org/wiki/Tag:railway%3Dlevel_crossing for more information on available tags

        Parameters
        ----------
        n : overpy.Node
            OpenStreetMap Node retrieved using Overpy
        """
        super(OSMLevelCrossing, self).__init__(n)

    def __repr__(self):
        return "Level Crossing at (%s, %s)" % (self.lon, self.lat)


class OSMRailwayMilestone(OSMRailwayElement):
    def __init__(self, n: overpy.Node):
        """
        Class representing railway milestones (turnouts)

        Parameters
        ----------
        n : overpy.Node
            OpenStreetMap node retrieved using Overpy

        Raises
        ----------
        ValueError
            Error caused by unusual milestone position format
        """
        super(OSMRailwayMilestone, self).__init__(n)

        pos = n.tags.get("railway:position", "-1").replace(",", ".").split("+")

        try:
            self.position = float(pos[0])
        except ValueError:
            logger.debug("Unusual milestone position format: %s" % n.tags.get("railway:position", ""))
            self.position = None
            
        self.addition = "" if len(pos) == 1 else pos[1]

    def __repr__(self):
        return "Milestone at (%s, %s): %.3f" % (self.lon, self.lat, self.position)


class OSMRailwaySignal(OSMRailwayElement):
    def __init__(self, n: overpy.Node):
        """
        Class representing railway signals

        See https://wiki.openstreetmap.org/wiki/Tag:railway%3Dsignal for more information on available tags

        Parameters
        ----------
        n : overpy.Node
            OpenStreetMap node retrieved using Overpy
        """
        super(OSMRailwaySignal, self).__init__(n)

    def __repr__(self):
        return "Signal at (%s, %s)" % (self.lon, self.lat)


class OSMRailwaySwitch(OSMRailwayElement):
    def __init__(self, n: overpy.Node):
        """
        Class representing railway switches (turnouts)

        Parameters
        ----------
        n : overpy.Node
            OpenStreetMap node retrieved using Overpy
        """
        super(OSMRailwaySwitch, self).__init__(n)
        self.allowed_transits = []  # List of triples in form of (neighbor 1, switch id, neighbor 2)

    def __repr__(self):
        return "Switch at (%s, %s)" % (self.lon, self.lat)


class OSMRelation:
    def __init__(self, relation: overpy.Relation, ways=None, color=None):
        """
        Class Representing an OpenStreetMap relation. A relation can represent multiple tracks in some cases

        Parameters
        ----------
        relation: overpy.Relation
            Relation between the ways
        ways: List [overpy.Way]
            Ways part of the relation
        color:
            Color when used to draw the track e.g. using ipyleaflet
        """

        if ways is None:
            ways = []

        self.id = relation.id
        self.relation = relation
        self.name = relation.tags.get("name", "")
        self.ways = ways
        self.way_nodes = [way.nodes for way in self.ways]  # List of list of nodes
        self.nodes = list(itertools.chain.from_iterable(self.way_nodes))  # list of nodes

        logger.debug(f'Create Graph for relation[id={self.id},name="{self.name}"].')

        self.G = nx.MultiGraph()
        self.G.add_nodes_from([(n.id, n.__dict__) for n in self.nodes])

        # Add edges
        for w in self.ways:
            edges = [(n1.id, n2.id, config.geod.inv(float(n1.lon), float(n1.lat), float(n2.lon), float(n2.lat))[2])
                     for n1, n2 in zip(w.nodes, w.nodes[1:])]  # Edges have geodesic distances as edge weights
            self.G.add_weighted_edges_from(edges, weight="d", way_id=w.id)

        # Look up endpoints
        self.endpoints = []  # Node IDs of endpoints
        for n in self.G.nodes:
            if len(self.G.adj[n]) == 1:
                self.endpoints.append(n)

        # Search tracks within relation (double tracks have 2 physical tracks but 4 tracks are found through Graph
        # search since each track can be trafficked in both directions)
        self.tracks = []

        for s, t in itertools.combinations(self.endpoints, 2):
            try:
                sp_n = nx.shortest_path(self.G, source=s, target=t)  # List of node ids that make up shortest path
                nodes = [next(n for n in self.nodes if n.id == n_id) for n_id in sp_n]
                ways = list(set(list(itertools.chain.from_iterable([n.ways for n in nodes]))))
                self.tracks.append(OSMTrack(nodes, ways))
            except nx.NetworkXNoPath as e:
                logger.debug(e)

        logger.debug("Number of individual tracks: %d" % len(self.tracks))

        self.color = relation.tags.get("colour", generate_random_color("HEX")) if not color else color
        if self.nodes:
            self.lon_sw = min([float(n.lon) for n in self.nodes])
            self.lon_ne = max([float(n.lon) for n in self.nodes])
            self.lat_sw = min([float(n.lat) for n in self.nodes])
            self.lat_ne = max([float(n.lat) for n in self.nodes])
        else:
            self.lon_sw = self.lon_ne = self.lat_sw = self.lat_ne = None

    def to_ipyleaflef(self) -> List[list]:
        """
        A function to convert the nodes to a list of nodes' coordinates [latitude, longitude]

        Returns
        -------
        coordinates :  list [list]
            List of nodes' location [latitude, longitude]
        """
        return [[n.lat, n.lon] for n in self.nodes]


class OSMRailwayLine(OSMRelation):
    def __init__(self, relation: overpy.Relation, ways: List[overpy.Way] = None, color=None):
        """
        Class representing a railway line. See https://wiki.openstreetmap.org/wiki/Tag:railway%3Drail

        Parameters
        ----------
        relation : overpy.Relation
            Relation between the ways
        ways : list
            List of ways of the railway line
        color :
            Color when used to draw the line e.g. using ipyleaflet

        Returns
        -------
        None
        """
        super(OSMRailwayLine, self).__init__(relation=relation, ways=ways, color=color)

        self.tags = relation.tags

        self.members = relation.members
        self.milestones = [OSMRailwayMilestone(n) for n in self.nodes if n.tags.get("railway", "") == "milestone"]
        self.results = {}

    def __repr__(self):
        return self.__dict__.get("name", "")


class OSMTrack:
    def __init__(self, nodes: List[overpy.Node], ways: List[overpy.Way]):
        """
        Represents a single railway track

        Parameters
        ----------
        nodes : list [overpy.node]
            Nodes that make up the track
        ways : list [overpy.Way]
            Ways that make up the track

        Returns
        -------
        None
        """
        self.lat = []
        self.lon = []

        self.x = []
        self.y = []

        self.ds = []
        self.s = []
        self.c = []

        self.nodes = nodes
        self.ways = ways

    @property
    def nodes(self):
        return self._nodes

    @nodes.setter
    def nodes(self, nodes: List[overpy.Node]):
        """
        A setter function for nodes

        Parameters
        ----------
        nodes : list [overpy.Node]
            Nodes to be set.

        Returns
        -------
        None
        """
        self._nodes = nodes

        self.lon = [float(n.lon) for n in nodes]
        self.lat = [float(n.lat) for n in nodes]

        self.x, self.y = convert_lon_lat_to_xy(self.lon, self.lat)
        self.c = calc_curvature(self.x, self.y)
        self.s, self.ds = calc_distance_from_lon_lat(self.lon, self.lat)

    def flip_curvature(self):
        """
        Flips the calculated curvature upside down
        """
        self.c = [el * -1 for el in self.c]

    def to_ipyleaflet(self):
        """
        Converts the coordinates to the format required by ipyleaflet for drawing

        Returns
        -------
        coordinates : list
            list of coordinates in ipyleaflet format
        """
        if self.lat and self.lon:
            return [[float(lat), float(lon)] for lat, lon in zip(self.lat, self.lon)]
        else:
            return []

    def to_tuple_list(self, frmt: str = "lon,lat"):
        """
        Converts the coordinates to a list of tuples

        Parameters
        ----------
        frmt : str
            Format, lon,lat or x,y. Defaults to "lon,lat"

        Returns
        -------
        coordinates : list [tuple]
            List of coordinates as tuples

        Raises
        -------
        ValueError
            Error occurs if the format of coordinates is not supported
        """
        if frmt == "lon,lat":
            if self.lat and self.lon:
                return [[float(lat), float(lon)] for lat, lon in zip(self.lat, self.lon)]
            else:
                return [(None, None)]
        elif frmt == "x,y":
            if self.x and self.y:
                return [(x, y) for x, y in zip(self.x, self.y)]
            else:
                return [(None, None)]
        else:
            raise ValueError("frmt %s not supported" % frmt)

    def __repr__(self):
        return "Track from %d to %d, Length: %f" % (self.nodes[0].id,
                                                    self.nodes[-1].id,
                                                    self.s[-1])
