import logging.config
import warnings
from itertools import chain
from typing import List, Union

import overpy
from tqdm.auto import tqdm

from pyridy.osm.utils import QueryResult, OSMRailwayLine

logger = logging.getLogger(__name__)


class OSMRegion:
    supported_railway_types = ["rail", "tram", "subway", "light_rail"]

    def __init__(self, lon_sw: float, lat_sw: float, lon_ne: float, lat_ne: float,
                 desired_railway_types: Union[List, str] = None, download: bool = True):

        if None in [lon_sw, lat_sw, lon_ne, lat_ne]:
            raise ValueError("One or more lat/lon values is None")

        if desired_railway_types is None:
            desired_railway_types = ["rail", "tram", "subway", "light_rail"]
        else:
            if type(desired_railway_types) == list:
                for desired in desired_railway_types:
                    if desired not in OSMRegion.supported_railway_types:
                        raise ValueError("Your desired railway type %s is not supported" % desired)
            elif type(desired_railway_types) == str:
                if desired_railway_types not in OSMRegion.supported_railway_types:
                    raise ValueError("Your desired railway type %s is not supported" % desired_railway_types)
            else:
                raise ValueError("desired_railway_types must be list or str")

        if lon_sw == lon_ne or lat_sw == lat_ne:
            raise ValueError("Invalid coordinates")

        if not (-90 <= lat_sw <= 90) or not (-90 <= lat_ne <= 90):
            raise ValueError("Lat. value outside valid range")

        if not (-180 <= lon_sw <= 180) or not (-180 <= lon_ne <= 180):
            raise ValueError("Lon. value outside valid range")

        self.overpass_api = overpy.Overpass()

        self.lon_sw = lon_sw
        self.lat_sw = lat_sw
        self.lon_ne = lon_ne
        self.lat_ne = lat_ne

        self.desired_railway_types = desired_railway_types
        self.ways: List[overpy.Way, overpy.RelationWay] = []
        self.railway_lines: List[OSMRailwayLine] = []

        self.query_results = {rw_type: {"track_query": QueryResult,
                                        "route_query": QueryResult} for rw_type in self.desired_railway_types}

        if download:
            self.download_track_data()

        logger.info("Initialized region: %f, %f (SW), %f, %f (NE)" % (self.lon_sw,
                                                                      self.lat_sw,
                                                                      self.lon_ne,
                                                                      self.lat_ne))

    def _create_query(self, railway_type: str):
        if railway_type not in OSMRegion.supported_railway_types:
            raise ValueError("Your desired railway type %s is not supported" % railway_type)

        track_query = """(node[""" + "railway" + """=""" + railway_type + """](""" + str(self.lat_sw) + """,""" + str(
            self.lon_sw) + """,""" + str(self.lat_ne) + """,""" + str(self.lon_ne) + """);
                         way[""" + "railway" + """=""" + railway_type + """](""" + str(self.lat_sw) + """,""" + str(
            self.lon_sw) + """,""" + str(self.lat_ne) + """,""" + str(self.lon_ne) + """);
                         relation[""" + "railway" + """=""" + railway_type + """](""" + str(
            self.lat_sw) + """,""" + str(self.lon_sw) + """,""" + str(self.lat_ne) + """,""" + str(self.lon_ne) + """););
                         (._;>;);
                         out body;
                      """

        route_query = """(node[""" + "route" + """=""" + railway_type + """](""" + str(self.lat_sw) + """,""" + str(
            self.lon_sw) + """,""" + str(self.lat_ne) + """,""" + str(self.lon_ne) + """);
                         way[""" + "route" + """=""" + railway_type + """](""" + str(self.lat_sw) + """,""" + str(
            self.lon_sw) + """,""" + str(self.lat_ne) + """,""" + str(self.lon_ne) + """);
                         relation[""" + "route" + """=""" + railway_type + """](""" + str(self.lat_sw) + """,""" + str(
            self.lon_sw) + """,""" + str(self.lat_ne) + """,""" + str(self.lon_ne) + """);
                         );
                         (._;>;);
                         out body;
                      """

        return track_query, route_query

    def download_track_data(self, railway_type: Union[List, str] = None):
        if railway_type:
            railway_types = [railway_type]
        else:
            railway_types = self.desired_railway_types

        # Download data for all desired railway types
        for railway_type in tqdm(railway_types):
            trk_query, rou_query = self._create_query(railway_type=railway_type)
            trk_result = QueryResult(self.query_overpass(trk_query), railway_type)
            rou_result = QueryResult(self.query_overpass(rou_query), railway_type)
            self.query_results[railway_type]["track_query"] = trk_result
            self.query_results[railway_type]["route_query"] = rou_result

            for rel in rou_result.result.relations:
                rel_way_ids = [mem.ref for mem in rel.members if type(mem) == overpy.RelationWay and not mem.role]
                rel_ways = [w for w in rou_result.result.ways if w.id in rel_way_ids]

                sort_order = {id: idx for id, idx in zip(rel_way_ids, range(len(rel_way_ids)))}
                rel_ways.sort(key=lambda w: sort_order[w.id])

                self.railway_lines.append(OSMRailwayLine(rel.id, rel_ways, rel.tags, rel.members))

    def query_overpass(self, query: str, attempts: int = 3):
        for a in range(attempts):
            try:
                logger.info("Trying to query OSM data, %d/%d tries" % (a, attempts))
                result = self.overpass_api.query(query)
                logger.info("Successfully gathers OSM Data")
                break
            except overpy.exception.OverpassTooManyRequests as e:
                logger.warning("OverpassTooManyRequest, retrying".format(e))
            except overpy.exception.OverpassGatewayTimeout as e:
                logger.warning("OverpassTooManyRequest, retrying".format(e))
            except overpy.exception.OverpassBadRequest as e:
                logger.warning("OverpassTooManyRequest, retrying".format(e))
        else:
            raise RuntimeError("Could download OSM data via Overpass after %d attempts." % attempts)
        return result

    def get_all_route_nodes(self) -> list:
        nodes = []

        for railway_type in self.desired_railway_types:
            nodes.append(self.query_results[railway_type]["route_query"].result.nodes)

        return list(chain.from_iterable(nodes))

    def search_osm_result(self, way_ids: List[int], railway_type="tram"):
        ways = []

        for way_id in way_ids:
            for way in self.query_results[railway_type].result.ways:
                if way_id == way.id:
                    ways.append(way)

        return ways

    @property
    def lon_sw(self):
        return self._lon_sw

    @lon_sw.setter
    def lon_sw(self, value: float):
        if -180 <= value <= 180:
            self._lon_sw = value
        else:
            warnings.warn("You are trying to set non plausible longitude value %f, keeping existing value"
                          % self.lon_sw, UserWarning)

    @property
    def lat_sw(self):
        return self._lat_sw

    @lat_sw.setter
    def lat_sw(self, value: float):
        if -90 <= value <= 90:
            self._lat_sw = value
        else:
            warnings.warn("You are trying to set non plausible latitude value %f, keeping existing value"
                          % self.lat_sw, UserWarning)

    @property
    def lon_ne(self):
        return self._lon_ne

    @lon_ne.setter
    def lon_ne(self, value: float):
        if -180 <= value <= 180:
            self._lon_ne = value
        else:
            warnings.warn("You are trying to set non plausible longitude value %f, keeping existing value"
                          % self.lon_ne, UserWarning)

    @property
    def lat_ne(self):
        return self._lat_ne

    @lat_ne.setter
    def lat_ne(self, value: float):
        if -90 <= value <= 90:
            self._lat_ne = value
        else:
            warnings.warn("You are trying to set non plausible latitude value %f, keeping existing value"
                          % self.lat_ne, UserWarning)

    def __repr__(self):
        return "Lat SW: %f, Lon SW: %f , Lat NE: %f, Lon NE: %f" % (self.lat_sw,
                                                                    self.lon_sw,
                                                                    self.lat_ne,
                                                                    self.lon_ne)
