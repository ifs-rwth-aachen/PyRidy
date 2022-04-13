import itertools
import logging.config
import math
import re
import socket
import time
from itertools import chain
from typing import List, Union

import networkx as nx
import numpy as np
import overpy
import pyproj
from heapdict import heapdict
from overpy import Result
from tqdm.auto import tqdm

from pyridy import config
from pyridy.osm.utils import QueryResult, OSMLevelCrossing, OSMRailwaySwitch, OSMRailwaySignal, OSMRailwayLine, \
    OSMRailwayElement, OSMRailwayMilestone, calc_angle_between
from pyridy.utils.tools import internet

logger = logging.getLogger(__name__)


class OSM:
    supported_railway_types = ["rail", "tram", "subway", "light_rail"]

    def __init__(self, bbox: List[Union[List, float]],
                 desired_railway_types: Union[List, str] = None,
                 download: bool = True,
                 recurse: str = ">"):
        """

        Parameters
        ----------
        bbox: List[List, float]
            Single bounding box or list of bounding boxes of which OSM data should be downloaded. In case of a list
            of bounding boxes data will be downloaded for each single bounding box and finally unified to a single
            result. Each bounding box must have the format lon_sw, lat_sw, lon_ne, lat_ne
        desired_railway_types: List[str] or str
            Railway type that should be queried. Can be 'rail', 'tram', 'subway' or 'light_rail'
        download: bool, default: True
            If True, starts downloading the OSM data
        recurse: str, default: '>'
            Type of recursion used on Overpass query. (Recurse up < or down >)
        """

        # Sanity check for bbox argument
        if type(bbox[0]) == float:
            self._check_bbox(bbox)
            self.bbox = [bbox]
        elif type(bbox[0]) == list:
            for b in bbox:
                self._check_bbox(b)

            self.bbox = bbox
        else:
            raise ValueError("Bounding box must be a list with coordinates or list of bounding boxes")

        # Sanity check for railway type argument
        if desired_railway_types is None:
            desired_railway_types = ["rail", "tram", "subway", "light_rail"]
        else:
            if type(desired_railway_types) == list:
                for desired in desired_railway_types:
                    if desired not in OSM.supported_railway_types:
                        raise ValueError("Your desired railway type %s is not supported" % desired)
            elif type(desired_railway_types) == str:
                if desired_railway_types not in OSM.supported_railway_types:
                    raise ValueError("Your desired railway type %s is not supported" % desired_railway_types)
            else:
                raise ValueError("desired_railway_types must be list or str")

        if recurse not in ["<", ">"]:
            raise ValueError("Recurse must be either < (up) or > (down), not %s" % recurse)
        self.recurse = recurse

        self.overpass_api = overpy.Overpass()
        self.overpass_api_alt = overpy.Overpass(url="https://overpass.kumi.systems/api/interpreter")
        self.overpass_api_ifs = overpy.Overpass(url="http://134.130.76.80:12345/api/interpreter")

        self.utm_proj = pyproj.Proj(proj='utm', zone=32, ellps='WGS84', preserve_units=True)
        self.geod = pyproj.Geod(ellps='WGS84')

        self.desired_railway_types = desired_railway_types

        self.nodes: List[overpy.Node, overpy.RelationNode] = []
        self.node_dict = {}

        self.ways: List[overpy.Way, overpy.RelationWay] = []
        self.way_dict = {}

        self.railway_lines: List[OSMRailwayLine] = []
        self.railway_elements: List[OSMRailwayElement] = []

        self.overpass_results = []  # List of all results returned from overpass queries

        self.G = nx.MultiGraph()

        if download:
            self._download_track_data()

            # Add nodes to Graph
            self.G.add_nodes_from([(n.id, n.__dict__) for n in self.nodes])

            # Add edges, use node distances as weight
            for w in self.ways:
                edges = [(n1.id, n2.id, self.geod.inv(float(n1.lon), float(n1.lat), float(n2.lon), float(n2.lat))[2])
                         for n1, n2 in zip(w.nodes, w.nodes[1:])]
                self.G.add_weighted_edges_from(edges, weight="d", way_id=w.id)

            if len(self.G.nodes) > 0:
                self._check_allowed_switch_transits()
            else:
                logger.warning("Can't check allowed switch transits, because the Graph has no nodes!")

    @staticmethod
    def _check_bbox(bbox: List[float]):
        """ Sanity check for bounding box

        Parameters
        ----------
        bbox: List[float]
            Bounding box with coordinate format lon_sw, lat_sw, lon_ne, lat_ne
        """
        if len(bbox) != 4:
            raise ValueError("Bounding box must have 4 coordinates, not %d" % len(bbox))

        if bbox[0] == bbox[2] or bbox[1] == bbox[3]:
            raise ValueError("Invalid coordinates")

        if not (-90 <= bbox[1] <= 90) or not (-90 <= bbox[3] <= 90):
            raise ValueError("Lat. value outside valid range")

        if not (-180 <= bbox[0] <= 180) or not (-180 <= bbox[2] <= 180):
            raise ValueError("Lon. value outside valid range")

    @staticmethod
    def _create_query(bbox: List[float], railway_type: str, recurse: str = ">"):
        """ Internal method

        Parameters
        ----------
        bbox: List[float]
            Bounding box must have the format lon_sw, lat_sw, lon_ne, lat_ne
        railway_type: str
            Railway type that should be queried. Can be 'rail', 'tram', 'subway' or 'light_rail'
        recurse: str, default: '>'
            Type of recursion used on Overpass query. (Recurse up < or down >)

        Returns
        -------

        """
        if recurse not in [">", ">>", "<", "<<"]:
            raise ValueError("recurse type %s not supported" % recurse)

        if railway_type not in OSM.supported_railway_types:
            raise ValueError("The desired railway type %s is not supported" % railway_type)

        track_query = """[timeout:""" + str(config.options["OSM_TIMEOUT"]) + """];(node[""" + "railway" + """=""" \
                      + railway_type + """](""" + str(bbox[1]) + """,""" + str(bbox[0]) + """,""" + str(bbox[3]) \
                      + """,""" + str(bbox[2]) + """);way[""" + "railway" + """=""" + railway_type + """](""" \
                      + str(bbox[1]) + """,""" + str(bbox[0]) + """,""" + str(bbox[3]) + """,""" + str(bbox[2]) \
                      + """););(._;>;);
                         out body;
                      """

        if railway_type == "rail":  # Railway routes use train instead of rail
            railway_type = "train"

        route_query = """[timeout:""" + str(config.options["OSM_TIMEOUT"]) + """];(relation[""" + "route" + """=""" \
                      + railway_type + """](""" + str(bbox[1]) + """,""" + str(bbox[0]) + """,""" + str(bbox[3]) \
                      + """,""" + str(bbox[2]) + """););(._;""" + recurse + """;);
                         out body;
                      """

        return track_query, route_query

    def _check_allowed_switch_transits(self):
        """ Checks in what ways a switch can be transited, i.e. what combination of neighbouring nodes are allowed

        """
        if not len(self.G.nodes):
            raise ValueError("Can't determine allowed switch transits if Graph G has no nodes")

        for sw in self.get_switches():
            sw_x, sw_y = self.utm_proj(sw.lon, sw.lat)
            sw_nbs = list(self.G.adj[sw.id])

            allowed_transits = []
            for n1, n2 in itertools.product(sw_nbs, repeat=2):
                if n1 == n2:
                    continue
                else:
                    n1_x, n1_y = self.G.nodes[n1]['attributes'].get('x', 0), self.G.nodes[n1]['attributes'].get('y', 0)
                    n2_x, n2_y = self.G.nodes[n2]['attributes'].get('x', 0), self.G.nodes[n2]['attributes'].get('y', 0)

                    v1 = [n1_x - sw_x, n1_y - sw_y]
                    v2 = [n2_x - sw_x, n2_y - sw_y]

                    ang = calc_angle_between(v1, v2)
                    if ang > math.pi / 2:
                        allowed_transits.append((n1, sw.id, n2))

            sw.allowed_transits = allowed_transits
            self.G.nodes[sw.id]['attributes']['allowed_transits'] = allowed_transits
        pass

    def _download_track_data(self):
        # Download data for all desired railway types
        if internet():
            for b in tqdm(self.bbox):
                logger.debug("Querying data for bounding box: %s" % str(b))
                for railway_type in tqdm(self.desired_railway_types):
                    # Create Overpass queries and try downloading them
                    logger.debug("Querying data for railway type: %s" % railway_type)

                    trk_query, rou_query = self._create_query(bbox=b,
                                                              railway_type=railway_type,
                                                              recurse=self.recurse)

                    trk_result = QueryResult(self.query_overpass(trk_query), railway_type)
                    rou_result = QueryResult(self.query_overpass(rou_query), railway_type)

                    # Convert relation result to OSMRailwayLine objects
                    if rou_result.result:
                        for rel in rou_result.result.relations:
                            rel_way_ids = [mem.ref for mem in rel.members if
                                           type(mem) == overpy.RelationWay and not mem.role]

                            if trk_result.result:
                                rel_ways = [w for w in trk_result.result.ways if w.id in rel_way_ids]

                                sort_order = {w_id: idx for w_id, idx in zip(rel_way_ids, range(len(rel_way_ids)))}
                                rel_ways.sort(key=lambda w: sort_order[w.id])

                                railway_line = OSMRailwayLine(rel.id, rel_ways, rel.tags, rel.members)
                                if railway_line not in self.railway_lines:
                                    self.railway_lines.append(railway_line)

                    if trk_result.result:
                        for n in trk_result.result.nodes:
                            if n not in self.nodes:
                                self.nodes.append(n)

                            if "railway" in n.tags:
                                if n.tags["railway"] == "level_crossing":
                                    self.railway_elements.append(OSMLevelCrossing(n))
                                elif n.tags["railway"] == "signal":
                                    self.railway_elements.append(OSMRailwaySignal(n))
                                elif n.tags["railway"] == "switch":
                                    self.railway_elements.append(OSMRailwaySwitch(n))
                                elif n.tags["railway"] == "milestone":
                                    self.railway_elements.append(OSMRailwayMilestone(n))
                                else:
                                    pass

                        for w in trk_result.result.ways:
                            if w not in self.ways:
                                self.ways.append(w)

            # Create dictionaries for easy node/way access
            self.node_dict = {n.id: n for n in self.nodes}  # Dict that returns node based on node id
            self.way_dict = {w.id: w for w in self.ways}  # Dict that returns way based on way id

            # Add XY coordinate to each node
            osm_xy = self.get_coords(frmt="xy")
            for i, xy in enumerate(osm_xy):
                self.nodes[i].attributes["x"] = xy[0]
                self.nodes[i].attributes["y"] = xy[1]
        else:
            logger.warning("Could not download OSM data because of no internet connection!")

    def query_overpass(self, query: str, attempts: int = None) -> Result:
        if attempts is None:
            attempts = config.options["OSM_RETRIES"]

        if internet(host="134.130.76.80", port=12345):  # IFS internal Overpass instance
            for a in range(attempts):
                time.sleep(a)
                try:
                    logger.debug("Trying to query OSM data, %d/%d tries" % (a, attempts))
                    result = self.overpass_api_ifs.query(query)
                    logger.debug("Successfully queried OSM Data using IFS Overpass instance")
                    return result
                except overpy.exception.OverpassTooManyRequests as e:
                    logger.warning("OverpassTooManyRequest (IFS Overpass instance), retrying".format(e))
                except overpy.exception.OverpassRuntimeError as e:
                    logger.warning("OverpassRuntimeError (IFS Overpass instance), retrying".format(e))
                except overpy.exception.OverpassGatewayTimeout as e:
                    logger.warning("OverpassTooManyRequest (IFS Overpass instance), retrying".format(e))
                except overpy.exception.OverpassBadRequest as e:
                    logger.warning("OverpassTooManyRequest (IFS Overpass instance), retrying".format(e))
                except socket.timeout as e:
                    logger.warning("Socket timeout (IFS Overpass instance), retrying".format(e))

        for a in range(attempts):  # Default Overpass instance
            time.sleep(a)
            try:
                logger.debug("Trying to query OSM data, %d/%d tries" % (a, attempts))
                result = self.overpass_api.query(query)
                logger.debug("Successfully queried OSM Data using default Overpass instance")
                return result
            except overpy.exception.OverpassTooManyRequests as e:
                logger.warning("OverpassTooManyRequest (Default Overpass instance), retrying".format(e))
            except overpy.exception.OverpassRuntimeError as e:
                logger.warning("OverpassRuntimeError (Default Overpass instance), retrying".format(e))
            except overpy.exception.OverpassGatewayTimeout as e:
                logger.warning("OverpassTooManyRequest (Default Overpass instance), retrying".format(e))
            except overpy.exception.OverpassBadRequest as e:
                logger.warning("OverpassTooManyRequest (Default Overpass instance), retrying".format(e))
            except socket.timeout as e:
                logger.warning("Socket timeout (Default Overpass instance), retrying".format(e))

        logger.debug("Using alternative Overpass API url")
        for a in range(attempts):
            time.sleep(a)
            try:
                logger.debug("Trying to query OSM data, %d/%d tries" % (a, attempts))
                result = self.overpass_api_alt.query(query)
                logger.debug("Successfully queried OSM Data using alternative instance")
                return result
            except overpy.exception.OverpassTooManyRequests as e:
                logger.warning("OverpassTooManyRequest (Alternative Overpass instance), retrying".format(e))
            except overpy.exception.OverpassRuntimeError as e:
                logger.warning("OverpassRuntimeError (Alternative Overpass instance), retrying".format(e))
            except overpy.exception.OverpassGatewayTimeout as e:
                logger.warning("OverpassTooManyRequest (Alternative Overpass instance), retrying".format(e))
            except overpy.exception.OverpassBadRequest as e:
                logger.warning("OverpassTooManyRequest (Alternative Overpass instance), retrying".format(e))
            except socket.timeout as e:
                logger.warning("Socket timeout (Alternative Overpass instance), retrying".format(e))
        else:
            logger.warning("Could download OSM data via Overpass after %d attempts with query: %s" % (attempts,
                                                                                                      query))
            return None

    def get_all_route_nodes(self) -> list:
        """ Retrieves a list of nodes part of any relation/route

        Returns
        -------
        List[overpy.node]
        """
        nodes = []

        for railway_type in self.desired_railway_types:
            nodes.append(self.query_results[railway_type]["route_query"].result.nodes)

        return list(chain.from_iterable(nodes))

    def get_shortest_path(self, source: int, target: int, weight: str, method="dijkstra") -> List[int]:
        """ Calculates the shortest path between a source and target node. Also considers how switches can be transited
        Based on: https://en.wikipedia.org/wiki/Dijkstra

        Parameters
        ----------
        source: int
            ID of source node
        target: int
            ID of target node
        weight: str
            Weight to be used for shortest path calculation, e.g. the length of the edges
        method: str
            Can be 'dijkstra' or 'A*'

        Returns
        -------
        List[int]
            List of node ids that represent the shortest path between source and target
        """
        dist = {n: np.inf for n in self.G.nodes}
        prev = {n: None for n in self.G.nodes}

        if method == "dijkstra":
            dist[source] = 0

            Q = heapdict()
            for v in self.G.nodes:
                Q[v] = dist[v]

            while Q:
                u = Q.popitem()[0]

                if u == target:
                    break

                u_is_switch = True if self.G.nodes[u]['tags'].get('railway') == 'switch' else False

                for v in set(self.G.adj[u]).intersection(set(Q.keys())):  # Neighbors of u that are still in Q
                    if u_is_switch:
                        u_prev = prev[u]
                        allowed = True if (u_prev, u, v) in self.G.nodes[u]['attributes'].get('allowed_transits',
                                                                                              []) else False
                    else:
                        allowed = True

                    alt = dist[u] + self.G[u][v][0][weight]
                    if allowed and alt < dist[v]:
                        dist[v] = alt
                        prev[v] = u
                        Q[v] = alt

        elif method == 'A*':
            s_lon, s_lat = float(self.G.nodes[source]['lon']), float(self.G.nodes[source]['lat'])
            t_lon, t_lat = float(self.G.nodes[target]['lon']), float(self.G.nodes[target]['lat'])

            dist[source] = 0 + self.geod.inv(s_lon, s_lat, t_lon, t_lat)[2]

            Q = heapdict()
            for v in self.G.nodes:
                Q[v] = dist[v]

            while Q:
                u = Q.popitem()[0]

                if u == target:
                    break

                u_is_switch = True if self.G.nodes[u]['tags'].get('railway') == 'switch' else False

                for v in set(self.G.adj[u]).intersection(set(Q.keys())):  # Neighbors of u that are still in Q
                    v_lon, v_lat = float(self.G.nodes[v]['lon']), float(self.G.nodes[v]['lat'])

                    if u_is_switch:
                        u_prev = prev[u]
                        allowed = True if (u_prev, u, v) in self.G.nodes[u]['attributes'].get('allowed_transits',
                                                                                              []) else False
                    else:
                        allowed = True

                    alt = dist[u] + self.G[u][v][0][weight] + self.geod.inv(v_lon, v_lat, t_lon, t_lat)[2]
                    if allowed and alt < dist[v]:
                        dist[v] = alt
                        prev[v] = u
                        Q[v] = alt
        else:
            raise ValueError("Method not supported")

        S = []  # Shortest path sequence
        u = target

        if prev[u] or u == source:
            while u:
                S.append(u)
                u = prev[u]

        S.reverse()

        return dist, prev, S

    def search_osm_result(self, way_ids: List[int], railway_type="tram"):
        ways = []

        for way_id in way_ids:
            for way in self.query_results[railway_type].result.ways:
                if way_id == way.id:
                    ways.append(way)

        return ways

    def get_coords(self, frmt: str = "lon/lat") -> np.ndarray:
        """ Get the coordinates in lon/lat format for all nodes

        Parameters
        ----------
            frmt: str, default: lon/lat
                Format in which the coordinates are being returned. Can be lon/lat or x/y

        Returns
        -------
            np.ndarray
        """
        if frmt not in ["lon/lat", "xy"]:
            raise ValueError("fmrt must be lon/lat or xy")

        if self.nodes:
            if frmt == "lon/lat":
                return np.array([[float(n.lon), float(n.lat)] for n in self.nodes])
            else:
                lat_lon_coords = np.array([[float(n.lon), float(n.lat)] for n in self.nodes])
                x, y = self.utm_proj(lat_lon_coords[:, 0], lat_lon_coords[:, 1])
                return np.vstack([x, y]).T
        else:
            logger.warning("No nodes get coordinates of!")
            return np.array([])

    def get_switches(self) -> List[OSMRailwayElement]:
        """ Returns a list of railway switches found in the downloaded OSM region

        Returns
        -------
            list
        """
        return [el for el in self.railway_elements if type(el) == OSMRailwaySwitch]

    def get_switches_for_railway_line(self, line: OSMRailwayLine) -> List[OSMRailwaySwitch]:
        """ Get switches part of a given railway line

        Parameters
        ----------
        line: OSMRailwayLine

        Returns
        -------
            list
        """
        switches = self.get_switches()

        line_switches = []
        for w in line.ways:
            n_ids = [n.id for n in w.nodes]
            for sw in switches:
                if sw.id in n_ids:
                    line_switches.append(sw)

        return line_switches

    def get_signals(self) -> List[OSMRailwayElement]:
        """ Returns a list of railway signals found in the downloaded OSM region

        Returns
        -------
            list
        """
        return [el for el in self.railway_elements if type(el) == OSMRailwaySignal]

    def get_milestones(self) -> List[OSMRailwayElement]:
        """ Returns a list of railway milestones found in the downloaded OSM region

        Returns
        -------
            list
        """
        return [el for el in self.railway_elements if type(el) == OSMRailwayMilestone]

    def get_level_crossings(self) -> List[OSMRailwayElement]:
        """ Returns a list of railway level crossings found in the downloaded OSM region

        Returns
        -------
            list
        """
        return [el for el in self.railway_elements if type(el) == OSMLevelCrossing]

    def get_railway_line(self, name) -> [OSMRailwayLine]:
        """ Get railway line by name. Always returns a list, even if only one line is found that matches the name

        Parameters
        ----------
        name: str
            Name of the railway line that should be searched

        Returns
        -------
            list
        """
        return [line for line in self.railway_lines if re.search(r'\b{0}\b'.format(name), line.name)]

    def __repr__(self):
        return "OSM region with bounding boxes: %s" % (str(self.bbox))
