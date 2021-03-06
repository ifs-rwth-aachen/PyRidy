import itertools
import logging
from abc import ABC
from typing import List

import networkx as nx
import overpy
from ipyleaflet import Map, ScaleControl, FullScreenControl, Polyline, Circle, LayerGroup

from pyridy import config
from pyridy.osm.utils import convert_lon_lat_to_xy, calc_curvature, calc_distance_from_lon_lat
from pyridy.utils.tools import generate_random_color

logger = logging.getLogger(__name__)


class OSMResultNode:
    def __init__(self, lon: float, lat: float,
                 value=None, f=None, proc=None, dir: str = "", color: str = None):
        """ Class representing a Node calculated by PyRidy

        Parameters
        ----------
        color: str
            Node colors
        lat: float
            Latitude of node coordinate
        lon: float
            Longitude of node coordinate
        """

        self.lat = lat
        self.lon = lon
        self.value = value
        self.f = f
        self.proc = proc
        self.dir = dir
        self.color = '#CC071E' if not color else color

    def __repr__(self):
        return "Result node at (%s, %s)" % (self.lon, self.lat)


class OSMResultWay:
    def __init(self, way, res: float = .5):
        self.way: overpy.Way = way
        self.res = res
        pass


class OSMRailwayElement(ABC):
    def __init__(self, n: overpy.Node):
        """ Abstract Base Class for railway elements retrieved from OpenStreetMap

        Parameters
        ----------
        n: overpy.Node
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
        """ Class representing railway level crossings

        See https://wiki.openstreetmap.org/wiki/Tag:railway%3Dlevel_crossing for more information on available tags

        Parameters
        ----------
        n: overpy.Node
            OpenStreetMap Node retrieved using Overpy
        """
        super(OSMLevelCrossing, self).__init__(n)

    def __repr__(self):
        return "Level Crossing at (%s, %s)" % (self.lon, self.lat)


class OSMRailwayMilestone(OSMRailwayElement):
    def __init__(self, n: overpy.Node):
        """ Class representing railway milestones (turnouts)

        Parameters
        ----------
        n: overpy.Node
            OpenStreetMap node retrieved using Overpy
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
        """ Class representing railway signals

        See https://wiki.openstreetmap.org/wiki/Tag:railway%3Dsignal for more information on available tags

        Parameters
        ----------
        n: overpy.Node
            OpenStreetMap node retrieved using Overpy
        """
        super(OSMRailwaySignal, self).__init__(n)

    def __repr__(self):
        return "Signal at (%s, %s)" % (self.lon, self.lat)


class OSMRailwaySwitch(OSMRailwayElement):
    def __init__(self, n: overpy.Node):
        """ Class representing railway switches (turnouts)

        Parameters
        ----------
        n: overpy.Node
            OpenStreetMap node retrieved using Overpy
        """
        super(OSMRailwaySwitch, self).__init__(n)
        self.allowed_transits = []  # List of triples in form of (neighbor 1, switch id, neighbor 2)

    def __repr__(self):
        return "Switch at (%s, %s)" % (self.lon, self.lat)


class OSMRelation:
    def __init__(self, relation: overpy.Relation, ways=None, color=None):
        """ Class Representing an OpenStreetMap relation. A relation can represent multiple tracks in some cases

        Parameters
        ----------
        relation: overpy.Relation
            Relation
        ways: List[overpy.Way]
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
        self.nodes = list(itertools.chain.from_iterable(self.way_nodes)) if self.way_nodes else None  # list of nodes

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
        self.lon_sw = min([float(n.lon) for n in self.nodes])
        self.lon_ne = max([float(n.lon) for n in self.nodes])
        self.lat_sw = min([float(n.lat) for n in self.nodes])
        self.lat_ne = max([float(n.lat) for n in self.nodes])

    def to_ipyleaflef(self) -> List[list]:
        """

        Returns
        -------

        """
        if self.nodes:
            logger.warning("Relation has no nodes!")
            return [[n.lat, n.lon] for n in self.nodes]
        else:
            return [[]]

    def create_map(self, show_result_nodes: bool = False, use_file_color: bool = False) -> Map:
        center = ((self.lat_sw + self.lat_ne) / 2, (self.lon_sw + self.lon_ne) / 2)

        m = Map(center=center, zoom=12, scroll_wheel_zoom=True, basemap=config.OPEN_STREET_MAP_DE)
        m.add_control(ScaleControl(position='bottomleft'))
        m.add_control(FullScreenControl())

        # Add map
        m.add_layer(config.OPEN_RAILWAY_MAP)

        for track in self.tracks:
            coords = track.to_ipyleaflet()
            file_polyline = Polyline(locations=coords, color=self.color, fill=False, weight=4)
            m.add_layer(file_polyline)

        if show_result_nodes:
            nodes = list(itertools.chain.from_iterable([w.attributes.get("results", []) for w in self.ways]))
            circles = []
            for n in nodes:
                circle = Circle()
                circle.location = n.lon, n.lat
                circle.radius = 2
                circle.color = n.f.color if use_file_color else n.color
                circle.fill_color = n.f.color if use_file_color else n.color
                circle.weight = 3
                circle.fill_opacity = 0.1
                circles.append(circle)

            l_circles = LayerGroup(layers=circles)
            m.add_layer(l_circles)

        return m


class OSMRailwayLine(OSMRelation):
    def __init__(self, relation: overpy.Relation, ways: List[overpy.Way] = None, color=None):
        """ Class representing a railway line

        See https://wiki.openstreetmap.org/wiki/Tag:railway%3Drail

        Parameters
        ----------
        id: int
            ID of the railway line
        ways: list
            List of ways of the railway line
        tags: dict
            Tags associated with the railway line
        members: list
            list of nodes and ways associated with the railway line
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
        """ Represents a single railway track

        Parameters
        ----------
        nodes: List[overpy.node]
            Nodes that make up the track
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
        """ Converts the coordinates to the format required by ipyleaflet for drawing
        Returns
        -------
            list
        """
        if self.lat and self.lon:
            return [[float(lat), float(lon)] for lat, lon in zip(self.lat, self.lon)]
        else:
            return [[]]

    def to_tuple_list(self, frmt: str = "lon,lat"):
        """ Converts the coordinates to a list of tuples
        Parameters
        ----------
            frmt : str, default: "lon,lat"
                Format, lon,lat or x,y

        Returns
        -------
            list
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
