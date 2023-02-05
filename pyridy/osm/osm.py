import itertools
import logging.config
import math
import re
import socket
import time
from itertools import chain
from typing import List, Union
from urllib.error import URLError

import networkx as nx
import numpy as np
import overpy
import pyproj
from heapdict import heapdict
from overpy import Result
from tqdm.auto import tqdm

from requests_cache import CachedSession

from pyridy import config
from pyridy.osm.utils.overpass import Overpass  # Overpass with caching support
from pyridy.osm.utils import QueryResult, OSMLevelCrossing, OSMRailwaySwitch, OSMRailwaySignal, OSMRailwayLine, \
    OSMRailwayElement, OSMRailwayMilestone, calc_angle_between
from pyridy.utils.tools import internet, test_connection_to_url

logger = logging.getLogger(__name__)


def upsample_way(self, res: float = config.options["TRACK_RESOLUTION"]):
    self.res = 1
    pass


overpy.Way.upsample_way = upsample_way


class CouldNotConnect(Exception):
    pass


class QueryToOverpassApiFailed(Exception):
    pass


class OSM:
    supported_railway_types = ["rail", "tram", "subway", "light_rail"]

    def __init__(self, bbox: List[Union[List, float, np.float64]],
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

        Raises
        -------
        ValueError: Raised if bounding boxes are empty, the bounding box is not a list with coordinates or list of bounding boxes,
        desired_railway_type is not supported or recurse type is invalid

        """

        # Sanity check for bbox argument
        if not bbox:
            raise ValueError("Can't retrieve OSM Data because bounding boxes are empty!")

        if (type(bbox[0]) == float) or (type(bbox[0]) == np.float64):
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
            desired_railway_types = OSM.supported_railway_types
        else:
            if type(desired_railway_types) == str:
                desired_railway_types = list(desired_railway_types)
            if type(desired_railway_types) == list:
                for desired in desired_railway_types:
                    if desired not in OSM.supported_railway_types:
                        raise ValueError("Your desired railway type %s is not supported" % desired)
            else:
                raise ValueError("desired_railway_types must be list or str")

        if recurse not in ["<", ">"]:
            raise ValueError("Recurse must be either < (up) or > (down), not %s" % recurse)
        self.recurse = recurse

        # use caching
        cached_session = CachedSession(cache_name=config.OSM_OVERPASS_CACHE, backend='filesystem')
        # overpass API instances
        self.overpass_api = Overpass(session=cached_session)
        self.overpass_api_alt = Overpass(url="https://overpass.kumi.systems/api/interpreter", session=cached_session)
        self.overpass_api_ifs = Overpass(url="http://134.130.76.80:12345/api/interpreter", session=cached_session)
        self.overpass_api_local = Overpass(url="http://localhost:12345/api/interpreter", session=cached_session)

        # prioritized list of the overpass API instances
        self.overpass_api_list = [
            self.overpass_api,  # fastest
            self.overpass_api_alt,  # fallback
            self.overpass_api_local,  # local fallback
            self.overpass_api_ifs,  # institute fallback
        ]

        self.utm_proj = pyproj.Proj(proj='utm', zone=32, ellps='WGS84', preserve_units=True)
        self.geod = pyproj.Geod(ellps='WGS84')

        self.desired_railway_types = desired_railway_types

        self.nodes: List[overpy.Node, overpy.RelationNode] = []
        self.node_dict = {}

        self.ways: List[overpy.Way, overpy.RelationWay] = []
        self.way_dict = {}

        self.relations: List[overpy.Relation] = []
        self.relation_dict = {}

        self.railway_lines: List[OSMRailwayLine] = []
        self.railway_elements: List[OSMRailwayElement] = []

        self.overpass_results = []  # List of all results returned from overpass queries

        self.G = nx.MultiGraph()

        if download:
            self._download_track_data_and_populate_graph()

    def _download_track_data_and_populate_graph(self):
        self._check_connection_and_download_track_data()
        self._populate_graph()

    def _populate_graph(self):

        """
        Add nodes to Graph. Edges added use node distances as weights.
        Returns
        -------
        None
        """
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
        # noinspection PyUnresolvedReferences
        """
        Sanity check for bounding box

        Parameters
        ----------
        bbox: List[float]
            Bounding box with coordinate format lon_sw, lat_sw, lon_ne, lat_ne

        Raises
        -------
        ValueError: Raised if coordinates are invalid
        """
        if len(bbox) != 4:
            raise ValueError("Bounding box must have 4 coordinates, not %d" % len(bbox))

        lon_sw, lat_sw, lon_ne, lat_ne = bbox

        if lon_sw == lon_ne or lat_sw == lat_ne:
            raise ValueError("Invalid coordinates")

        if not (-90 <= lat_sw <= 90) or not (-90 <= lat_ne <= 90):
            raise ValueError("Lat. value outside valid range")

        if not (-180 <= lon_sw <= 180) or not (-180 <= lon_ne <= 180):
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
        track query: query
        route query: query

        Raises
        -------
        ValueError: Raised if the desired_railway_type is not supported or recurse type is invalid
        """
        if recurse not in [">", ">>", "<", "<<"]:
            raise ValueError("recurse type %s not supported" % recurse)

        if railway_type not in OSM.supported_railway_types:
            raise ValueError("The desired railway type %s is not supported" % railway_type)

        bbox_str = f"{str(bbox[1])},{str(bbox[0])},{str(bbox[3])},{str(bbox[2])}"

        track_query = f"""
                        [timeout:{str(config.options["OSM_TIMEOUT"])}];
                        (
                            node[railway={railway_type}]({bbox_str});
                            way[railway={railway_type}]({bbox_str});
                        );
                        (._;>;);
                        out body;"""

        if railway_type == "rail":  # Railway routes use train instead of rail
            railway_type = "train"

        route_query = f"""
                        [timeout:{str(config.options["OSM_TIMEOUT"])}];
                        (
                            relation[route={railway_type}]({bbox_str});
                        );
                        (._;{recurse};);
                        out body;"""

        return track_query, route_query

    def _check_allowed_switch_transits(self):
        """
        Checks in what ways a switch can be transited, i.e. what combination of neighboring nodes are allowed

        Raises
        -------
        ValueError: Raised if graph G has no nodes
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

    def get_live_overpass_api_instances(self):
        """
        The function returns live instances by testing the connection to the api_instances' list.

        Returns
        -------
        live_instances: list
            A list of current live instances.
        """
        live_instances = []
        for i in self.overpass_api_list:
            logger.debug(f"Test connection to {i.url}.")
            if test_connection_to_url(i.url):
                logger.info(f"Connection to {i.url} was successful.")
                live_instances.append(i)
            else:
                logger.info(f"Connection to {i.url} failed.")
        return live_instances

    def _check_connection_and_download_track_data(self):
        """
        Download track data if there is a working internet connection
        Returns
        -------
        None
        """
        logger.debug("Check connectivity before starting download.")
        live_overpass_instances = self.get_live_overpass_api_instances()

        if len(live_overpass_instances) == 0:
            logger.warning("Could not download OSM data: No connection to an Overpass API could be established.")
        else:
            return self._download_track_data(overpass_instances=live_overpass_instances)

    def _query_data_for_bbox(self, b, overpass_instances=None):
        """
        Query data for a bounding box.

        Stores returned data in self.relations, self.nodes and self.ways.
        Parameters
        ----------
        b: List[float]
            Bounding box must have the format lon_sw, lat_sw, lon_ne, lat_ne
        overpass_instances: List[Overpass]
        """


        for railway_type in tqdm(self.desired_railway_types, desc="Railway Types"):
            # Create Overpass queries and try downloading them
            logger.debug("Querying data for railway type: %s" % railway_type)

            trk_query, rou_query = self._create_query(bbox=b,
                                                      railway_type=railway_type,
                                                      recurse=self.recurse)

            trk_result = QueryResult(
                self.query_overpass(trk_query, overpass_instances=overpass_instances), railway_type)
            rou_result = QueryResult(
                self.query_overpass(rou_query, overpass_instances=overpass_instances), railway_type)

            # Convert relation result to OSMRailwayLine objects
            if rou_result.result:
                for rel in rou_result.result.relations:
                    if rel not in self.relations:
                        self.relations.append(rel)

            if trk_result.result:
                for n in trk_result.result.nodes:
                    if n not in self.nodes:
                        self.nodes.append(n)

                for w in trk_result.result.ways:
                    if w not in self.ways:
                        self.ways.append(w)

    def _postprocessing_of_downloaded_data(self):
        """
        Performs postprocessing of downloaded track data (e.g. add coordinates of nodes, create railway lines ...)

        Returns
        -------
        None
        """
        logger.info("Start postprocessing of downloaded data.")

        # Create dictionaries for easy node/way access
        logger.debug("Create dictionaries from nodes, ways and relations.")
        self.node_dict = {n.id: n for n in self.nodes}  # Dict that returns node based on node id
        self.way_dict = {w.id: w for w in self.ways}  # Dict that returns way based on way id
        self.relation_dict = {rel.id: rel for rel in self.relations}

        # Add XY coordinate to each node
        logger.debug("Add XY coordinates to each node.")
        osm_xy = self.get_coords(frmt="xy")
        for i, xy in enumerate(osm_xy):
            self.nodes[i].attributes["x"] = xy[0]
            self.nodes[i].attributes["y"] = xy[1]

        # Search through results for railway stuff
        logger.debug("Create railway elements from nodes.")
        for n in self.nodes:
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

        logger.debug("Create railway lines from relations.")
        for rel in self.relations:
            rel_way_ids = [mem.ref for mem in rel.members if type(mem) == overpy.RelationWay and not mem.role]
            rel_ways = [w for w in self.ways if w.id in rel_way_ids]

            sort_order = {w_id: idx for w_id, idx in zip(rel_way_ids, range(len(rel_way_ids)))}
            rel_ways.sort(key=lambda way: sort_order[way.id])

            # rel_ways = [self.way_dict[rel_id] for rel_id in rel_way_ids]

            railway_line = OSMRailwayLine(relation=rel, ways=rel_ways)
            if railway_line not in self.railway_lines:
                self.railway_lines.append(railway_line)

        logger.info("Postprocessing finished.")

    def _download_track_data(self, overpass_instances=None):
        """
        Downloads the track data by querying data for bounding boxes.
        Parameters
        ----------
        overpass_instances: list[Overpass]

        Returns
        -------
        None
        """
        logger.info("Start downloading track data.")
        for i, b in enumerate(tqdm(self.bbox, desc="Bounding Boxes")):
            logger.debug("Querying data for bounding box (%d / %d): %s" % (i + 1, len(self.bbox), str(b)))
            self._query_data_for_bbox(b, overpass_instances=overpass_instances)
        logger.info("Finished downloading track data.")

        self._postprocessing_of_downloaded_data()

    def _query_overpass_instance(self, query: str, attempts: int, overpass_api_instance: Overpass):
        """

        Parameters
        ----------
        query: str
            The query string in Overpass QL
        attempts: int
            Number of attempts of the query.
        overpass_api_instance: Overpass
            Overpass API instance
        Returns
        -------
        The parsed result

        Raises
        -------
        overpy.exception.OverpassBadRequest: Raised if the Overpass API service returns a syntax error
        overpy.exception.OverpassTooManyRequests: Raised if the Overpass API service returns a 429 status code
        overpy.exception.OverpassGatewayTimeout: Raised if load of the Overpass API service is too high and it can’t handle the request
        overpy.exception.OverpassRuntimeError: Raised if the server returns a remark-tag(xml) or remark element(json) with a message starting with ‘runtime error:’
        QueryToOverpassApiFailed: Raised when query to overpass fails
        """
        for a in range(attempts):
            # increase waiting time between attempts
            wait_seconds = 3 * a
            if wait_seconds > 0:
                logger.debug(f"Wait {wait_seconds} s before next retry...")
                time.sleep(3 * a)

            logger.debug("Trying to query OSM data, attempt %d of %d." % (a + 1, attempts))
            try:
                result = overpass_api_instance.query(query)
                logger.debug(f"Successfully queried OSM Data using {overpass_api_instance.url}")
                return result
            except overpy.exception.OverpassTooManyRequests as e:
                logger.warning("OverpassTooManyRequest, retrying".format(e))
            except overpy.exception.OverpassRuntimeError as e:
                logger.warning("OverpassRuntimeError, retrying".format(e))
                logger.warning(e)
            except overpy.exception.OverpassGatewayTimeout as e:
                logger.warning("OverpassGatewayTimeout, retrying".format(e))
            except overpy.exception.OverpassBadRequest as e:
                logger.warning("OverpassBadRequest, retrying".format(e))
                logger.warning(e)
            except URLError as e:
                # for example due to connection errors
                logger.warning(e)
            except socket.timeout as e:
                logger.warning("Socket timeout, retrying".format(e))

        logger.warning("No attempts left, giving up.")
        raise QueryToOverpassApiFailed()

    def query_overpass(self, query: str,
                       attempts: int = None,
                       overpass_instances: List[Overpass] = None) -> Result:
        """

        Parameters
        ----------
        query: str
        attempts: int
            Number of attempts
        overpass_instances: List[Overpass]
            A list of Overpass API instances

        Returns
        -------
        None

        Raises
        -------
        QueryToOverpassApiFailed: Raised when query to overpass fails
        """
        if attempts is None:
            attempts = config.options["OSM_RETRIES"]

        logger.debug(f"Overpass query: {query}")

        if overpass_instances is None:
            overpass_instances = self.overpass_api_list

        for i, overpass_api_instance in enumerate(overpass_instances):
            logger.debug(
                f"Try to query Overpass API {i + 1} of {len(overpass_instances)}: {overpass_api_instance.url}.")
            try:
                return self._query_overpass_instance(query, attempts, overpass_api_instance)
            except QueryToOverpassApiFailed:
                continue

        logger.warning("Could not download OSM data via Overpass after %d attempts with query: %s" % (attempts, query))
        return None

    def get_all_route_nodes(self) -> list:
        """
        Retrieves a list of nodes part of any relation/route

        Returns
        -------
        List[overpy.node]
        """
        nodes = []

        for railway_type in self.desired_railway_types:
            nodes.append(self.query_results[railway_type]["route_query"].result.nodes)

        return list(chain.from_iterable(nodes))

    def get_shortest_path(self, source: int, target: int, weight: str, method="dijkstra") -> List[int]:
        """
        Calculates the shortest path between a source and target node. Also considers how switches can be transited
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

        Raises
        -------
        ValueError: Raised when given method is not supported
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
        """
        Queries ways using their ids and railway type
        Parameters
        ----------
        way_ids: List[int]
            List of IDs of ways.
        railway_type: str
            Type of railway. Defaults to 'tram'

        Returns
        -------
        ways: list
            The ways resulting from the query
        """
        ways = []

        for way_id in way_ids:
            for way in self.query_results[railway_type].result.ways:
                if way_id == way.id:
                    ways.append(way)

        return ways

    def get_coords(self, frmt: str = "lon/lat") -> np.ndarray:
        """
        Get the coordinates in lon/lat format for all nodes

        Parameters
        ----------
        frmt: str, default: lon/lat
            Format in which the coordinates are being returned. Can be lon/lat or x/y

        Returns
        -------
            np.ndarray
        Raises
        -------
        ValueError: Raised when format is not lon/lat or xy
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

    def get_switches(self, line: OSMRailwayLine = None) -> List[OSMRailwayElement]:
        """
        Returns a list of railway switches found in the downloaded OSM region
        Parameters
        ----------
        line: OSMRailwayLine
        Returns
        -------
        line_switches: list[OSMRailwayElement]
            list of railway switches found in the downloaded OSM region
        """
        sws = [el for el in self.railway_elements if type(el) == OSMRailwaySwitch]

        if line:
            line_switches = []

            for w in line.ways:
                n_ids = [n.id for n in w.nodes]
                for sw in sws:
                    if sw.id in n_ids:
                        line_switches.append(sw)

            return line_switches
        else:
            return sws

    def get_switches_for_railway_line(self, line: OSMRailwayLine) -> List[OSMRailwaySwitch]:
        """
        Get switches part of a given railway line

        Parameters
        ----------
        line: OSMRailwayLine

        Returns
        -------
        line_switches: list[OSMRailwayElement]
            list of railway switches found in the downloaded OSM region

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
        """
        Returns a list of railway signals found in the downloaded OSM region

        Returns
        -------
        list[OSMRailwayElement]
            list of railway signals
        """
        return [el for el in self.railway_elements if type(el) == OSMRailwaySignal]

    def get_milestones(self) -> List[OSMRailwayElement]:
        """
        Returns a list of railway milestones found in the downloaded OSM region

        Returns
        -------
        list[OSMRailwayElement]
            List of railway milestones
        """
        return [el for el in self.railway_elements if type(el) == OSMRailwayMilestone]

    def get_level_crossings(self) -> List[OSMRailwayElement]:
        """
        Returns a list of railway level crossings found in the downloaded OSM region

        Returns
        -------
        list[OSMRailwayElement]
            List of railway level crossings
        """
        return [el for el in self.railway_elements if type(el) == OSMLevelCrossing]

    def get_railway_line(self, name) -> List[OSMRailwayLine]:
        """
        Get railway line by name. Always returns a list, even if only one line is found that matches the name

        Parameters
        ----------
        name: str
            Name of the railway line that should be searched

        Returns
        -------
        list[OSMRailwayElement]
            List of railway lines
        """
        return [line for line in self.railway_lines if re.search(r'\b{0}\b'.format(name), line.name)]

    def reset_way_attributes(self):
        """
        Deletes all attributes of each way. E.g results are saved

        """
        for w in self.ways:
            w.attributes = {}

    def __repr__(self):
        return "OSM region with bounding boxes: %s" % (str(self.bbox))
