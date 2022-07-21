import datetime
import itertools
import json
import logging
import os
import sqlite3
from sqlite3 import DatabaseError
from typing import Optional, List, Dict, Tuple, Union, Type

import networkx as nx
import numpy as np
import overpy
import pandas as pd
from ipyleaflet import Map, ScaleControl, FullScreenControl, Polyline, Marker, Circle, LayerGroup
from ipywidgets import HTML
from pandas.io.sql import DatabaseError as PandasDatabaseError
from scipy.spatial import KDTree
from scipy.stats import norm

from pyridy import config
from pyridy.osm import OSM, OSMRailwayLine
from pyridy.osm.utils import is_point_within_line_projection, project_point_onto_line
from pyridy.utils import Sensor, AccelerationSeries, LinearAccelerationSeries, MagnetometerSeries, OrientationSeries, \
    GyroSeries, RotationSeries, GPSSeries, PressureSeries, HumiditySeries, TemperatureSeries, WzSeries, LightSeries, \
    SubjectiveComfortSeries, AccelerationUncalibratedSeries, MagnetometerUncalibratedSeries, GyroUncalibratedSeries, \
    GNSSClockMeasurementSeries, GNSSMeasurementSeries, NMEAMessageSeries, TimeSeries, NTPDatetimeSeries
from pyridy.utils.device import Device
from pyridy.utils.tools import generate_random_color

logger = logging.getLogger(__name__)


class RDYFile:
    def __init__(self, path: str = "", sync_method: str = "timestamp", trim_ends: bool = True,
                 timedelta_unit: str = 'timedelta64[ns]',
                 strip_timezone: bool = True,
                 filename="",
                 series: Union[List[Type[TimeSeries]], Type[TimeSeries]] = None,
                 color: str = None):
        """

        Parameters
        ----------
        path: str
            Path to the Ridy File
        sync_method: str
            Sync method to be applied
        trim_ends: bool, default: True
            If True, trims the measurements precisely to the timestamp when the measurement was started, respectively
            stopped. By default Ridy measurement files can contain several seconds of measurements from before/after
            the button press
        timedelta_unit: str
            NumPy timedelta unit to applied
        strip_timezone: bool, default: True
            Strips timezone from timestamps as np.datetime64 does not support timezones
        filename: str
            Name of the files, will be the filename if not provided
        """
        self.path = path

        # Sanity check if series is arg is valid
        if series:
            if type(series) is list:
                for s in series:
                    if not issubclass(s, TimeSeries):
                        raise ValueError("%s in %s is not a TimeSeries!" % (type(s), list(series)))
                self._series = series
            elif issubclass(series, TimeSeries):
                self._series = [series]
                pass
            else:
                raise ValueError("series argument must be list of TimeSeries or TimeSeries! not %s" % type(series))
        else:
            self._series = None

        if sync_method is not None and sync_method not in ["timestamp", "seconds", "device_time", "gps_time",
                                                           "ntp_time"]:
            raise ValueError(
                "synchronize argument must 'timestamp', 'seconds','device_time', 'gps_time' or 'ntp_time' not %s" %
                sync_method)

        self.sync_method = sync_method
        self.trim_ends = trim_ends
        self.timedelta_unit = timedelta_unit
        self.strip_timezone = strip_timezone

        # Ridy App Info
        self.ridy_version: Optional[str] = None
        self.ridy_version_code: Optional[int] = None

        # Geographic extent of file (can only be determined if GPSSeries was recorded
        self.lat_sw, self.lon_sw = None, None
        self.lat_ne, self.lon_ne = None, None
        self.bbox = None

        # RDY File Infos
        self.rdy_format_version: Optional[float] = None
        self.rdy_info_name: Optional[str] = None
        self.rdy_info_sex: Optional[str] = None
        self.rdy_info_age: Optional[int] = None
        self.rdy_info_height: Optional[float] = None
        self.rdy_info_weight: Optional[float] = None

        self.t0: Optional[np.datetime64] = None
        self.cs_matrix_string: Optional[str] = None
        self.cs_matrix: Optional[np.ndarray] = None  # TODO
        self.timestamp_when_started: Optional[int] = None
        self.timestamp_when_stopped: Optional[int] = None
        self.ntp_timestamp: Optional[int] = None
        self.ntp_date_time: Optional[np.datetime64] = None
        self.device: Optional[Device] = None

        self.duration: Optional[float] = None

        # Sensors
        self.sensors: Optional[List[Sensor]] = []

        # Measurement Series
        self.measurements = {AccelerationSeries: AccelerationSeries(),
                             AccelerationUncalibratedSeries: AccelerationUncalibratedSeries(),
                             LinearAccelerationSeries: LinearAccelerationSeries(),
                             MagnetometerSeries: MagnetometerSeries(),
                             MagnetometerUncalibratedSeries: MagnetometerUncalibratedSeries(),
                             OrientationSeries: OrientationSeries(),
                             GyroSeries: GyroSeries(),
                             GyroUncalibratedSeries: GyroUncalibratedSeries(),
                             RotationSeries: RotationSeries(),
                             GPSSeries: GPSSeries(),
                             GNSSClockMeasurementSeries: GNSSClockMeasurementSeries(),
                             GNSSMeasurementSeries: GNSSMeasurementSeries(),
                             NMEAMessageSeries: NMEAMessageSeries(),
                             PressureSeries: PressureSeries(),
                             TemperatureSeries: TemperatureSeries(),
                             HumiditySeries: HumiditySeries(),
                             LightSeries: LightSeries(),
                             WzSeries: WzSeries(),
                             SubjectiveComfortSeries: SubjectiveComfortSeries(),
                             NTPDatetimeSeries: NTPDatetimeSeries()}

        # Filename and extension
        self.filename: Optional[str] = filename
        self.extension: Optional[str] = ""

        # OSM Data (set by Campaign)
        self.osm: Optional[OSM] = None
        self.matched_nodes: Optional[List[overpy.Node]] = []  # Nodes from Map Matching
        self.matched_ways: Optional[List[overpy.Way]] = []  # Ways from Map Matching
        self.matched_line: Optional[OSMRailwayLine] = None  # Matched Railway Line

        if self.path:
            self.load_file(self.path)

            if self.timestamp_when_started and self.timestamp_when_stopped:
                self.duration = (self.timestamp_when_stopped - self.timestamp_when_started) * 1e-9

            if self.sync_method:
                self._synchronize()

            if len(self.measurements[GPSSeries]) > 0:
                self.lon_sw = self.measurements[GPSSeries].lon.min()
                self.lon_ne = self.measurements[GPSSeries].lon.max()

                self.lat_sw = self.measurements[GPSSeries].lat.min()
                self.lat_ne = self.measurements[GPSSeries].lat.max()

                self.bbox = [self.lon_sw, self.lat_sw, self.lon_ne, self.lat_ne]
        else:
            logging.warning("RDYFile instantiated without a path")

        # Unique color for each line
        if not color:
            while True:
                self.color = generate_random_color("HEX")
                if self.color not in config.colors:
                    config.colors.append(color)
                    break
                else:
                    continue
        else:
            self.color = color

    # def __getitem__(self, idx):
    #     key = list(self.measurements.keys())[idx]
    #     return self.measurements[key]

    def __iter__(self):
        """

        Returns
        -------
            FileIterator
        """
        return FileIterator(self)

    def __repr__(self):
        return "Filename: %s, T0: %s, Duration: %s" % (self.filename,
                                                       str(self.t0),
                                                       str(datetime.timedelta(seconds=self.duration)) if self.duration
                                                       else "N/A")

    def _do_candidate_search(self, osm_xy: np.ndarray, track_xy: np.ndarray, hor_acc: np.ndarray):
        """ Internal method to search for candidate edges for map matching

        """
        # Find the closest coordinates using KDTrees
        kd_tree_osm = KDTree(osm_xy)
        kd_tree_track = KDTree(track_xy)

        # Indices of OSM nodes that are close to each respective GPS point within radius r
        indices = kd_tree_track.query_ball_tree(kd_tree_osm, r=100)

        c_dict = {}  # Dict with node candidates for each GPS coord
        edges = []  # Candidate edges with emission probabilities

        # Perform search for node candidate on all GPS coords
        for i, idxs in enumerate(indices):
            # Get unique ways based on indices
            c_ways = list(set(list(itertools.chain(*[self.osm.nodes[idx].ways for idx in idxs]))))

            # Find candidate line segments
            c_segs = []
            for w in c_ways:
                n = w.nodes
                segs = []  # List of suitable line segments

                for n1, n2 in zip(n, n[1:]):
                    x1, y1 = n1.attributes["x"], n1.attributes["y"]
                    x2, y2 = n2.attributes["x"], n2.attributes["y"]

                    # Only take those line segment into consideration where the perpendicular projection
                    # of the GPS coords lies inside the line segment
                    b = is_point_within_line_projection(line=[[x1, y1], [x2, y2]], point=track_xy[i])
                    if b:
                        # Point of orthogonal intersection
                        p, d = project_point_onto_line(line=[[x1, y1], [x2, y2]], point=track_xy[i])
                        if d < hor_acc[i]:
                            p_lon, p_lat = self.osm.utm_proj(p[0], p[1], inverse=True)
                            segs.append([d, p_lon, p_lat, n1, n2, w.id, None, i])

                if segs:
                    segs = np.array(segs)
                    i_min = np.argmin(
                        segs[:, 0])  # Select candidate line segment based on smallest perpendicular distance
                    n1, n2 = segs[i_min, 3], segs[i_min, 4]

                    e1 = list(self.osm.G.edges(n1.id, keys=True))
                    e2 = list(self.osm.G.edges(n2.id, keys=True))

                    inter = list(set(e1).intersection(e2))
                    if len(inter) == 0:  # TODO
                        c_seg_e = e1[0]
                    else:
                        c_seg_e = inter[0]

                    c_seg = segs[i_min]
                    c_segs.append(c_seg)

                    edges.append([c_seg_e, hor_acc[i], c_seg[0]])

            c_dict[i] = {"c_ways": c_ways, "c_segs": c_segs}

        # Calculate emission probabilities for each edge candidate
        c_edges = {}
        if edges:
            edges = np.array(edges, dtype='object')
            e_probs = norm.pdf(edges[:, 2].astype(float), np.zeros(len(edges)), edges[:, 1].astype(float))

            for i, e_prob in enumerate(e_probs):
                if edges[i][0] not in c_edges:
                    c_edges[edges[i][0]] = {"e_prob": [e_prob]}
                else:
                    c_edges[edges[i][0]]["e_prob"].append(e_prob)

        return c_dict, c_edges

    def _synchronize(self):
        """ Internal method that synchronizes the timestamps to a given sync timestamp

        """
        if self.sync_method == "timestamp":
            for m in self.measurements.values():
                m.synchronize("timestamp", self.timestamp_when_started,
                              timedelta_unit=self.timedelta_unit)
        elif self.sync_method == 'seconds':
            for m in self.measurements.values():
                m.synchronize("seconds", self.timestamp_when_started,
                              timedelta_unit=self.timedelta_unit)
        elif self.sync_method == "device_time":
            if self.t0:
                for m in self.measurements.values():
                    m.synchronize("device_time", self.timestamp_when_started, self.t0,
                                  timedelta_unit=self.timedelta_unit)
            else:
                logger.warning("(%s) t0 is None, falling back to timestamp synchronization" % self.filename)
                self.sync_method = "timestamp"
                self._synchronize()
        elif self.sync_method == "gps_time":
            if len(self.measurements[GPSSeries]) > 0:
                sync_timestamp = self.measurements[GPSSeries].time[0]
                utc_sync_time = self.measurements[GPSSeries].utc_time[0]

                for i, t in enumerate(self.measurements[
                                          GPSSeries].utc_time):
                    # The first utc_time value ending with 000 is a real GPS measurement
                    if str(t)[-3:] == "000":
                        utc_sync_time = t
                        sync_timestamp = self.measurements[GPSSeries].time[i]
                        break

                sync_time = np.datetime64(int(utc_sync_time * 1e6), "ns")
                for m in self.measurements.values():
                    m.synchronize("gps_time", sync_timestamp, sync_time, timedelta_unit=self.timedelta_unit)
            else:
                logger.warning(
                    "(%s) No GPS time recording, falling back to device_time synchronization" % self.filename)
                self.sync_method = "device_time"
                self._synchronize()
        elif self.sync_method == "ntp_time":
            if self.ntp_timestamp and self.ntp_date_time:
                for m in self.measurements.values():
                    m.synchronize("ntp_time", self.ntp_timestamp, self.ntp_date_time,
                                  timedelta_unit=self.timedelta_unit)
            else:
                logger.warning("(%s) No NTP timestamp and datetime, falling back to device_time synchronization" %
                               self.filename)

                self.sync_method = "device_time"
                self._synchronize()
        else:
            raise ValueError(
                "sync_method must 'timestamp', 'device_time', 'gps_time' or 'ntp_time' not %s" % self.sync_method)
        pass

    def create_map(self, t_lim: Tuple[np.datetime64, np.datetime64] = None, show_hor_acc: bool = False) -> Map:
        """ Creates an ipyleaflet Map using OpenStreetMap and OpenRailwayMap to show the GPS track of the
        measurement file

        Parameters
        ----------
            t_lim: tuple, default: None
                Time limit as a tuple of np.datetime64 to show only parts of the GPS track that are within the specified
                time interval
            show_hor_acc : bool, default: False
                If true shows the horizontal accuracies for each measurement point using circles. The likelihood that
                that the real position is within the circle is defined as 68 %

        Returns
        -------
            Map
        """
        gps_series = self.measurements[GPSSeries]
        coords = gps_series.to_ipyleaflef()
        time = gps_series.time
        hor_acc = gps_series.hor_acc

        if not coords:
            logger.warning("(%s) Cant create map, GPSSeries is empty!" % self.filename)
        else:
            if t_lim:
                if type(t_lim) != tuple:
                    raise ValueError("t_lim must be a tuple of np.datetime64")

                if t_lim[0] > t_lim[1]:
                    raise ValueError("The first datetime for t_lim must be smaller than the second!")

                mask = (gps_series.time >= t_lim[0]) & (gps_series.time <= t_lim[1])

                coords = [c for i, c in enumerate(coords) if mask[i]]
                time = [t for i, t in enumerate(gps_series.time) if mask[i]]
                hor_acc = [h for i, h in enumerate(gps_series.hor_acc) if mask[i]]

            color = generate_random_color("HEX")

            m = Map(center=self.determine_track_center()[::-1],
                    zoom=12,
                    scroll_wheel_zoom=True,
                    basemap=config.OPEN_STREET_MAP_DE)

            m.add(ScaleControl(position='bottomleft'))
            m.add(FullScreenControl())

            # Add map
            m.add(config.OPEN_RAILWAY_MAP)

            file_polyline = Polyline(locations=coords, color=color, fill=False, weight=4, dash_array='10, 10')
            m.add(file_polyline)

            start_marker = Marker(location=tuple(coords[0]), draggable=False, icon=config.START_ICON)
            end_marker = Marker(location=tuple(coords[-1]), draggable=False, icon=config.END_ICON)

            start_message = HTML()
            end_message = HTML()
            start_message.value = "<p>Start:</p><p>" + self.filename + "</p><p>" \
                                  + str(time[0] or 'n/a') + "</p><p>" \
                                  + str(getattr(self.device, "manufacturer", "n/a")) + "; " \
                                  + str(getattr(self.device, "model", "n/a")) + "</p>"

            end_message.value = "<p>End:</p><p>" + self.filename + "</p><p>" \
                                + str(time[-1] or 'n/a') + "</p><p>" \
                                + str(getattr(self.device, "manufacturer", "n/a")) + "; " \
                                + str(getattr(self.device, "model", "n/a")) + "</p>"

            start_marker.popup = start_message
            end_marker.popup = end_message

            m.add(start_marker)
            m.add(end_marker)

            if show_hor_acc:
                circles = []
                for c, h in zip(coords, hor_acc):
                    circle = Circle()
                    circle.location = (c[0], c[1])
                    circle.radius = int(h)
                    circle.color = "#00549F"
                    circle.fill_color = "#00549F"
                    circle.weight = 3
                    circle.fill_opacity = 0.1

                    circles.append(circle)

                l_circles = LayerGroup(layers=circles)
                m.add(l_circles)

            return m

    def determine_track_center(self, gps_series: Optional[GPSSeries] = None) -> (float, float):
        """ Determines the geographical center of the GPSSeries, returns None if the GPSSeries is emtpy.

        Parameters
        ----------
            gps_series: GPSSeries, default: None
                If not None, takes the given GPSSeries to determine the track center

        Returns
        -------
            float, float
        """
        if not gps_series:
            gps_series = self.measurements[GPSSeries]

        if gps_series.is_empty():
            logger.warning("(%s) Cant determine track center, GPSSeries is empty!" % self.filename)
        else:
            center_lon = (gps_series.lon.max() + gps_series.lon.min()) / 2
            center_lat = (gps_series.lat.max() + gps_series.lat.min()) / 2

            logging.info("Geographic center of track: Lon: %s, Lat: %s" % (str(center_lon), str(center_lat)))

            return center_lon, center_lat

    def do_map_matching(self, v_thres: float = config.options["MAP_MATCHING_V_THRES"],
                        algorithm: str = config.options["MAP_MATCHING_DEFAULT_ALGORITHM"],
                        alpha: int = config.options["MAP_MATCHING_ALPHA"],
                        beta: int = config.options["MAP_MATCHING_BETA"]):
        """ Performs map matching of the GPS track to closest OSM nodes/ways

        Parameters
        ----------
        alpha: float, default: 1.0
            Weighting Parameter for the Map Matching Algorithm. Alpha represents the default lange of an edge in the
            Graph
        beta: float, default: 1.0
            Beta is a scaling factor for the emission probabilities.
        algorithm: str, default: nx
            Algorithm to be used, can be "pyridy" or "nx". The pyridy algorithm also incorporates how switches
            can be transited
        v_thres: float, default: 1.0
            Speed threshold, GPS points measured with a velocity below v_thres [m/s] will not be considered

        Returns
        -------

        """
        if algorithm not in ["nx", "pyridy"]:
            raise ValueError("(%s) Algorithm must be either nx or pyridy, not %s" % (self.filename, algorithm))

        if self.osm:
            # Prepare data
            gps_coords = self.measurements[GPSSeries]
            lon = gps_coords.lon[gps_coords.speed > v_thres]
            lat = gps_coords.lat[gps_coords.speed > v_thres]
            hor_acc = gps_coords.hor_acc[gps_coords.speed > v_thres]

            n_gps = len(lon)

            x, y = self.osm.utm_proj(lon, lat)

            track_xy = np.vstack([x, y]).T
            osm_xy = self.osm.get_coords(frmt="xy")

            c_dict, c_edges = self._do_candidate_search(osm_xy, track_xy, hor_acc)

            # Initialize edge weights
            for e in self.osm.G.edges:
                self.osm.G.edges[e]["c_weight"] = 1 * alpha

            for k in c_edges.keys():
                self.osm.G.edges[k]["c_weight"] = 1 / (1 + beta * sum(c_edges[k]["e_prob"]))

            # Perform map matching
            s_n = None
            for i in range(n_gps):
                if len(c_dict[i]["c_segs"]) > 0:
                    s_n = c_dict[i]["c_segs"][np.array(c_dict[i]["c_segs"])[:, 0].argmin()][3].id
                    break

            e_n = None
            for i in reversed(range(n_gps)):
                if len(c_dict[i]["c_segs"]) > 0:
                    e_n = c_dict[i]["c_segs"][np.array(c_dict[i]["c_segs"])[:, 0].argmin()][4].id
                    break

            if not s_n or not e_n:
                logger.warning("(%s) Map matching failed, no start or end node found!" % self.filename)
            else:
                # Use Dijkstra's shortest path to perform map matching, but use a weighting based on emission
                # probabilities instead of node distances
                if algorithm == 'pyridy':
                    # Matched node ids
                    _, _, m_n_ids = self.osm.get_shortest_path(source=s_n, target=e_n, weight="c_weight")
                else:
                    m_n_ids = nx.shortest_path(self.osm.G, source=s_n, target=e_n, weight="c_weight")

                self.matched_nodes = [self.osm.node_dict[n] for n in m_n_ids]  # Matched nodes

                m_w_ids = [self.osm.G[n1][n2][0]["way_id"] for n1, n2 in zip(m_n_ids, m_n_ids[1:])]
                self.matched_ways = list(set([self.osm.way_dict[w_id] for w_id in m_w_ids]))  # Mapped Ways
                logger.debug("(%s) Found %d nodes that match the files GPS track!" % (self.filename,
                                                                                      len(self.matched_nodes)))

                if len(self.matched_nodes) > 0:
                    m_ratios = [len(set(self.matched_nodes).intersection(line.nodes)) / len(self.matched_nodes) for line
                                in
                                self.osm.railway_lines if self]

                    if max(m_ratios) > config.options["MAP_MATCHING_MIN_LINE_MATCH_RATIO"]:
                        self.matched_line = self.osm.railway_lines[m_ratios.index(max(m_ratios))]
                        logger.debug("(%s) Matched Railway Line: %s (%.f Match Ratio)" % (self.filename,
                                                                                          self.matched_line.name,
                                                                                          max(m_ratios)))
                    else:
                        logger.debug("(%s) Could not match map matching results to a specific railway line" %
                                     self.filename)
                else:
                    logger.debug("(%s) Could not match map matching results to a specific railway line" %
                                 self.filename)
        else:
            logger.warning("(%s) Can't do map matching since no file contains no OSM data" % self.filename)
        pass

    def get_integrity_report(self):
        """ Returns a dict that contains information which measurement types are available in the file


        Returns
        -------
            dict
        """
        report = {}

        for k, v in self.measurements.items():
            if len(v) > 0:
                report[k.__name__] = True
            else:
                report[k.__name__] = False

        attr = self.__dict__.copy()
        attr.update(attr["device"].__dict__.copy())
        for a in ["measurements", "device", "sensors"]:
            attr.pop(a)
            pass

        report.update(attr)

        return report

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, v):
        for m in self.measurements.values():
            m.filename = v

        self._filename = v

    def load_file(self, path: str):
        """ Loads a single Ridy file located at path

        Parameters
        ----------
        path Path to the ridy file

        """
        logger.debug("Loading file: %s" % path)

        _, self.extension = os.path.splitext(path)
        _, self.filename = os.path.split(path)

        if self.extension == ".rdy":
            with open(path, 'r') as file:
                rdy = json.load(file)

            if 'Ridy_Version' in rdy:
                self.ridy_version = rdy['Ridy_Version']
            else:
                logger.debug("No Ridy_Version in file: %s" % self.filename)
                self.ridy_version = None

            if 'Ridy_Version_Code' in rdy:
                self.ridy_version_code = rdy['Ridy_Version_Code']
            else:
                logger.debug("No Ridy_Version_Code in file: %s" % self.filename)
                self.ridy_version_code = None

            if 'RDY_Format_Version' in rdy:
                self.rdy_format_version = rdy['RDY_Format_Version']
            else:
                logger.debug("No RDY_Format_Version in file: %s" % self.filename)
                self.rdy_format_version = None

            if 'RDY_Info_Name' in rdy:
                self.rdy_info_name = rdy['RDY_Info_Name']
            else:
                logger.debug("No RDY_Info_Name in file: %s" % self.filename)
                self.rdy_info_name = None

            if 'RDY_Info_Sex' in rdy:
                self.rdy_info_sex = rdy['RDY_Info_Sex']
            else:
                logger.debug("No RDY_Info_Sex in file: %s" % self.filename)
                self.rdy_info_sex = None

            if 'RDY_Info_Age' in rdy:
                self.rdy_info_age = rdy['RDY_Info_Age']
            else:
                logger.debug("No RDY_Info_Age in file: %s" % self.filename)
                self.rdy_info_age = None

            if 'RDY_Info_Height' in rdy:
                self.rdy_info_height = rdy['RDY_Info_Height']
            else:
                logger.debug("No RDY_Info_Height in file: %s" % self.filename)
                self.rdy_info_height = None

            if 'RDY_Info_Weight' in rdy:
                self.rdy_info_weight = rdy['RDY_Info_Weight']
            else:
                logger.debug("No RDY_Info_Weight in file: %s" % self.filename)
                self.rdy_info_weight = None

            if 't0' in rdy:
                if self.strip_timezone:
                    t0 = datetime.datetime.fromisoformat(rdy['t0']).replace(tzinfo=None)
                    self.t0 = np.datetime64(t0)
                else:
                    self.t0 = np.datetime64(rdy['t0'])
            else:
                self.t0 = None
                logger.debug("No t0 in file: %s" % self.filename)

            if 'cs_matrix_string' in rdy:
                self.cs_matrix_string = rdy['cs_matrix_string']
            else:
                self.cs_matrix_string = None
                logger.debug("No t0 in file: %s" % self.filename)

            if 'timestamp_when_started' in rdy:
                self.timestamp_when_started = rdy['timestamp_when_started']
            else:
                self.timestamp_when_started = None
                logger.debug("No timestamp_when_started in file: %s" % self.filename)

            if 'timestamp_when_stopped' in rdy:
                self.timestamp_when_stopped = rdy['timestamp_when_stopped']
            else:
                self.timestamp_when_stopped = None
                logger.debug("No timestamp_when_stopped in file: %s" % self.filename)

            if 'ntp_timestamp' in rdy:
                self.ntp_timestamp = rdy['ntp_timestamp']
            else:
                self.ntp_timestamp = None
                logger.debug("No ntp_timestamp in file: %s" % self.filename)

            if 'ntp_date_time' in rdy:
                if self.strip_timezone:
                    ntp_datetime_str = rdy['ntp_date_time']
                    if ntp_datetime_str:
                        ntp_date_time = datetime.datetime.fromisoformat(ntp_datetime_str).replace(tzinfo=None)
                        self.ntp_date_time = np.datetime64(ntp_date_time)
                    else:
                        self.ntp_date_time = None
                else:
                    self.ntp_date_time = np.datetime64(rdy['t0'])
            else:
                self.ntp_date_time = None
                logger.debug("No ntp_date_time in file: %s" % self.filename)

            if "device" in rdy:
                self.device = Device(**rdy['device_info'])
            else:
                self.device = Device()
                logger.debug("No device information in file: %s" % self.filename)

            if "sensors" in rdy:
                for sensor in rdy['sensors']:
                    self.sensors.append(Sensor(**sensor))
            else:
                logger.debug("No sensor descriptions in file: %s" % self.filename)

            if (self._series is not None and AccelerationSeries in self._series) or self._series is None:
                if "acc_series" in rdy:
                    self.measurements[AccelerationSeries] = \
                        AccelerationSeries(filename=self.filename,
                                           rdy_format_version=self.rdy_format_version,
                                           **rdy['acc_series'])
                else:
                    logger.debug("No Acceleration Series in file: %s" % self.filename)

            if (self._series is not None and AccelerationUncalibratedSeries in self._series) or self._series is None:
                if "acc_uncal_series" in rdy:
                    self.measurements[AccelerationUncalibratedSeries] = AccelerationUncalibratedSeries(
                        filename=self.filename, rdy_format_version=self.rdy_format_version, **rdy['acc_uncal_series'])
                else:
                    logger.debug("No uncalibrated Acceleration Series in file: %s" % self.filename)

            if (self._series is not None and LinearAccelerationSeries in self._series) or self._series is None:
                if "lin_acc_series" in rdy:
                    self.measurements[LinearAccelerationSeries] = LinearAccelerationSeries(
                        filename=self.filename,
                        rdy_format_version=self.rdy_format_version,
                        **rdy['lin_acc_series'])
                else:
                    logger.debug("No Linear Acceleration Series in file: %s" % self.filename)

            if (self._series is not None and MagnetometerSeries in self._series) or self._series is None:
                if "mag_series" in rdy:
                    self.measurements[MagnetometerSeries] = \
                        MagnetometerSeries(filename=self.filename,
                                           rdy_format_version=self.rdy_format_version,
                                           **rdy['mag_series'])
                else:
                    logger.debug("No Magnetometer Series in file: %s" % self.filename)

            if (self._series is not None and MagnetometerUncalibratedSeries in self._series) or self._series is None:
                if "mag_uncal_series" in rdy:
                    self.measurements[MagnetometerUncalibratedSeries] = MagnetometerUncalibratedSeries(
                        filename=self.filename, rdy_format_version=self.rdy_format_version, **rdy['mag_uncal_series'])
                else:
                    logger.debug("No uncalibrated Magnetometer Series in file: %s" % self.filename)

            if (self._series is not None and OrientationSeries in self._series) or self._series is None:
                if "orient_series" in rdy:
                    self.measurements[OrientationSeries] = OrientationSeries(filename=self.filename,
                                                                             rdy_format_version=self.rdy_format_version,
                                                                             **rdy['orient_series'])
                else:
                    logger.debug("No Orientation Series in file: %s" % self.filename)

            if (self._series is not None and GyroSeries in self._series) or self._series is None:
                if "gyro_series" in rdy:
                    self.measurements[GyroSeries] = GyroSeries(filename=self.filename,
                                                               rdy_format_version=self.rdy_format_version,
                                                               **rdy['gyro_series'])
                else:
                    logger.debug("No Gyro Series in file: %s" % self.filename)

            if (self._series is not None and GyroUncalibratedSeries in self._series) or self._series is None:
                if "gyro_uncal_series" in rdy:
                    self.measurements[GyroUncalibratedSeries] = GyroUncalibratedSeries(
                        filename=self.filename, rdy_format_version=self.rdy_format_version, **rdy['gyro_uncal_series'])
                else:
                    logger.debug("No uncalibrated Gyro Series in file: %s" % self.filename)

            if (self._series is not None and RotationSeries in self._series) or self._series is None:
                if "rot_series" in rdy:
                    self.measurements[RotationSeries] = RotationSeries(filename=self.filename,
                                                                       rdy_format_version=self.rdy_format_version,
                                                                       **rdy['rot_series'])
                else:
                    logger.debug("No Rotation Series in file: %s" % self.filename)

            if (self._series is not None and GPSSeries in self._series) or self._series is None:
                if "gps_series" in rdy:
                    self.measurements[GPSSeries] = GPSSeries(filename=self.filename,
                                                             rdy_format_version=self.rdy_format_version,
                                                             **rdy['gps_series'])
                else:
                    logger.debug("No GPS Series in file: %s" % self.filename)

            if (self._series is not None and GNSSMeasurementSeries in self._series) or self._series is None:
                if "gnss_series" in rdy:
                    self.measurements[GNSSMeasurementSeries] = GNSSMeasurementSeries(
                        filename=self.filename, rdy_format_version=self.rdy_format_version, **rdy['gnss_series'])
                else:
                    logger.debug("No GPS Series in file: %s" % self.filename)

            if (self._series is not None and GNSSClockMeasurementSeries in self._series) or self._series is None:
                if "gnss_clock_series" in rdy:
                    self.measurements[GNSSClockMeasurementSeries] = GNSSClockMeasurementSeries(
                        filename=self.filename, rdy_format_version=self.rdy_format_version, **rdy['gnss_clock_series'])
                else:
                    logger.debug("No GNSS Clock Series in file: %s" % self.filename)

            if (self._series is not None and NMEAMessageSeries in self._series) or self._series is None:
                if "nmea_series" in rdy:
                    self.measurements[NMEAMessageSeries] = NMEAMessageSeries(
                        filename=self.filename, rdy_format_version=self.rdy_format_version, **rdy['nmea_series'])
                else:
                    logger.debug("No GPS Series in file: %s" % self.filename)

            if (self._series is not None and PressureSeries in self._series) or self._series is None:
                if "pressure_series" in rdy:
                    self.measurements[PressureSeries] = PressureSeries(filename=self.filename,
                                                                       rdy_format_version=self.rdy_format_version,
                                                                       **rdy['pressure_series'])
                else:
                    logger.debug("No Pressure Series in file: %s" % self.filename)

            if (self._series is not None and TemperatureSeries in self._series) or self._series is None:
                if "temperature_series" in rdy:
                    self.measurements[TemperatureSeries] = TemperatureSeries(filename=self.filename,
                                                                             rdy_format_version=self.rdy_format_version,
                                                                             **rdy['temperature_series'])
                else:
                    logger.debug("No Temperature Series in file: %s" % self.filename)

            if (self._series is not None and HumiditySeries in self._series) or self._series is None:
                if "humidity_series" in rdy:
                    self.measurements[HumiditySeries] = HumiditySeries(filename=self.filename,
                                                                       rdy_format_version=self.rdy_format_version,
                                                                       **rdy['humidity_series'])
                else:
                    logger.debug("No Humidity Series in file: %s" % self.filename)

            if (self._series is not None and LightSeries in self._series) or self._series is None:
                if "light_series" in rdy:
                    self.measurements[LightSeries] = LightSeries(filename=self.filename,
                                                                 rdy_format_version=self.rdy_format_version,
                                                                 **rdy['light_series'])
                else:
                    logger.debug("No Light Series in file: %s" % self.filename)

            if (self._series is not None and WzSeries in self._series) or self._series is None:
                if "wz_series" in rdy:
                    self.measurements[WzSeries] = WzSeries(filename=self.filename,
                                                           rdy_format_version=self.rdy_format_version,
                                                           **rdy['wz_series'])
                else:
                    logger.debug("No Wz Series in file: %s" % self.filename)

            if (self._series is not None and SubjectiveComfortSeries in self._series) or self._series is None:
                if "subjective_comfort_series" in rdy:
                    self.measurements[SubjectiveComfortSeries] = SubjectiveComfortSeries(
                        filename=self.filename,
                        rdy_format_version=self.rdy_format_version,
                        **rdy['subjective_comfort_series'])
                else:
                    logger.debug("No Subjective Comfort Series in file: %s" % self.filename)

            if (self._series is not None and NTPDatetimeSeries in self._series) or self._series is None:
                if "ntp_series" in rdy:
                    self.measurements[NTPDatetimeSeries] = NTPDatetimeSeries(
                        filename=self.filename,
                        rdy_format_version=self.rdy_format_version,
                        strip_timezone=self.strip_timezone,
                        **rdy['ntp_series'])
                else:
                    logger.debug("No NTP Datetime Series in file: %s" % self.filename)

        elif self.extension == ".sqlite":
            db_con = sqlite3.connect(path)

            try:
                info: Dict = dict(pd.read_sql_query("SELECT * from measurement_information_table", db_con))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(e)
                # Older files can contain wrong table name
                try:
                    info = dict(pd.read_sql_query("SELECT * from measurment_information_table", db_con))
                    logger.debug("(%s) Older file containing measu(rm)ent_information_table" % self.filename)
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug(
                        "(%s) DatabaseError occurred when accessing measurement_information_table" % self.filename)
                    logger.debug(e)
                    info = {}

            try:
                sensor_df = pd.read_sql_query("SELECT * from sensor_descriptions_table", db_con)
                for _, row in sensor_df.iterrows():
                    self.sensors.append(Sensor(**dict(row)))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.debug(
                    "(%s) DatabaseError occurred when accessing sensor_descriptions_table" % self.filename)
                logger.debug(e)

            try:
                device_df = pd.read_sql_query("SELECT * from device_information_table", db_con)
                self.device = Device(**dict(device_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.debug("(%s) DatabaseError occurred when accessing device_information_table" % self.filename)
                logger.debug(e)
                self.device = Device()

            # Info
            if 'ridy_version' in info and len(info['ridy_version']) > 1:
                logger.debug("Measurement information table contains more than 1 row!")

            if 'ridy_version' in info and len(info['ridy_version']) > 0:
                self.ridy_version = info['ridy_version'].iloc[-1]

            if 'ridy_version_code' in info and len(info['ridy_version_code']) > 0:
                self.ridy_version_code = info['ridy_version_code'].iloc[-1]

            if 'rdy_format_version' in info and len(info['rdy_format_version']) > 0:
                self.rdy_format_version = info['rdy_format_version'].iloc[-1]

            if 'rdy_info_name' in info and len(info['rdy_info_name']) > 0:
                self.rdy_info_name = info['rdy_info_name'].iloc[-1]

            if 'rdy_info_sex' in info and len(info['rdy_info_sex']) > 0:
                self.rdy_info_sex = info['rdy_info_sex'].iloc[-1]

            if 'rdy_info_age' in info and len(info['rdy_info_age']) > 0:
                self.rdy_info_age = info['rdy_info_age'].iloc[-1]

            if 'rdy_info_height' in info and len(info['rdy_info_height']) > 0:
                self.rdy_info_height = info['rdy_info_height'].iloc[-1]

            if 'rdy_info_weight' in info and len(info['rdy_info_weight']) > 0:
                self.rdy_info_weight = info['rdy_info_weight'].iloc[-1]

            if 't0' in info and len(info['t0']) > 0:
                if self.strip_timezone:
                    t0 = datetime.datetime.fromisoformat(info['t0'].iloc[-1]).replace(tzinfo=None)
                    self.t0 = np.datetime64(t0)
                else:
                    self.t0 = np.datetime64(info['t0'].iloc[-1])

            if 'cs_matrix_string' in info and len(info['cs_matrix_string']) > 0:
                self.cs_matrix_string = info['cs_matrix_string'].iloc[-1]

            if 'timestamp_when_started' and len(info['timestamp_when_started']) > 0:
                self.timestamp_when_started = info['timestamp_when_started'].iloc[-1]

            if 'timestamp_when_stopped' in info and len(info['timestamp_when_stopped']) > 0:
                self.timestamp_when_stopped = info['timestamp_when_stopped'].iloc[-1]

            if 'ntp_timestamp' in info and len(info['ntp_timestamp']) > 0:
                self.ntp_timestamp = info['ntp_timestamp'].iloc[-1]

            if 'ntp_date_time' in info and len(info['ntp_date_time']) > 0:
                if self.strip_timezone:
                    ntp_datetime_str = info['ntp_date_time'].iloc[-1]
                    if ntp_datetime_str:
                        ntp_date_time = datetime.datetime.fromisoformat(ntp_datetime_str).replace(tzinfo=None)
                        self.ntp_date_time = np.datetime64(ntp_date_time)
                    else:
                        self.ntp_date_time = None
                else:
                    self.ntp_date_time = np.datetime64(info['ntp_date_time'].iloc[-1])

            # Measurements
            if (self._series is not None and AccelerationSeries in self._series) or self._series is None:
                try:
                    acc_df = pd.read_sql_query("SELECT * from acc_measurements_table", db_con)
                    self.measurements[AccelerationSeries] = \
                        AccelerationSeries(filename=self.filename,
                                           rdy_format_version=self.rdy_format_version,
                                           **dict(acc_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug("(%s) DatabaseError occurred when accessing acc_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and AccelerationUncalibratedSeries in self._series) or self._series is None:
                try:
                    acc_uncal_df = pd.read_sql_query("SELECT * from acc_uncal_measurements_table", db_con)
                    self.measurements[AccelerationUncalibratedSeries] = AccelerationUncalibratedSeries(
                        filename=self.filename, rdy_format_version=self.rdy_format_version, **dict(acc_uncal_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug(
                        "(%s) DatabaseError occurred when accessing acc_uncal_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and LinearAccelerationSeries in self._series) or self._series is None:
                try:
                    lin_acc_df = pd.read_sql_query("SELECT * from lin_acc_measurements_table", db_con)
                    self.measurements[LinearAccelerationSeries] = LinearAccelerationSeries(
                        filename=self.filename,
                        rdy_format_version=self.rdy_format_version,
                        **dict(lin_acc_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug(
                        "(%s) DatabaseError occurred when accessing lin_acc_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and MagnetometerSeries in self._series) or self._series is None:
                try:
                    mag_df = pd.read_sql_query("SELECT * from mag_measurements_table", db_con)
                    self.measurements[MagnetometerSeries] = MagnetometerSeries(filename=self.filename,
                                                                               rdy_format_version=self.rdy_format_version,
                                                                               **dict(mag_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug("(%s) DatabaseError occurred when accessing mag_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and MagnetometerUncalibratedSeries in self._series) or self._series is None:
                try:
                    mag_uncal_df = pd.read_sql_query("SELECT * from mag_uncal_measurements_table", db_con)
                    self.measurements[MagnetometerUncalibratedSeries] = MagnetometerUncalibratedSeries(
                        filename=self.filename, rdy_format_version=self.rdy_format_version, **dict(mag_uncal_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug(
                        "(%s) DatabaseError occurred when accessing mag_uncal_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and OrientationSeries in self._series) or self._series is None:
                try:
                    orient_df = pd.read_sql_query("SELECT * from orient_measurements_table", db_con)
                    self.measurements[OrientationSeries] = OrientationSeries(filename=self.filename,
                                                                             rdy_format_version=self.rdy_format_version,
                                                                             **dict(orient_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug(
                        "(%s) DatabaseError occurred when accessing orient_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and GyroSeries in self._series) or self._series is None:
                try:
                    gyro_df = pd.read_sql_query("SELECT * from gyro_measurements_table", db_con)
                    self.measurements[GyroSeries] = GyroSeries(filename=self.filename,
                                                               rdy_format_version=self.rdy_format_version,
                                                               **dict(gyro_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug("(%s) DatabaseError occurred when accessing gyro_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and GyroUncalibratedSeries in self._series) or self._series is None:
                try:
                    gyro_uncal_df = pd.read_sql_query("SELECT * from gyro_uncal_measurements_table", db_con)
                    self.measurements[GyroUncalibratedSeries] = GyroUncalibratedSeries(
                        filename=self.filename, rdy_format_version=self.rdy_format_version, **dict(gyro_uncal_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug(
                        "(%s) DatabaseError occurred when accessing gyro_uncal_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and RotationSeries in self._series) or self._series is None:
                try:
                    rot_df = pd.read_sql_query("SELECT * from rot_measurements_table", db_con)
                    self.measurements[RotationSeries] = RotationSeries(filename=self.filename,
                                                                       rdy_format_version=self.rdy_format_version,
                                                                       **dict(rot_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug("(%s) DatabaseError occurred when accessing rot_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and GPSSeries in self._series) or self._series is None:
                try:
                    gps_df = pd.read_sql_query("SELECT * from gps_measurements_table", db_con)
                    self.measurements[GPSSeries] = GPSSeries(filename=self.filename,
                                                             rdy_format_version=self.rdy_format_version,
                                                             **dict(gps_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug("(%s) DatabaseError occurred when accessing gps_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and GNSSMeasurementSeries in self._series) or self._series is None:
                try:
                    gnss_df = pd.read_sql_query("SELECT * from gnss_measurement_table", db_con)
                    self.measurements[GNSSMeasurementSeries] = GNSSMeasurementSeries(
                        filename=self.filename, rdy_format_version=self.rdy_format_version, **dict(gnss_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug("(%s) DatabaseError occurred when accessing gnss_measurement_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and GNSSClockMeasurementSeries in self._series) or self._series is None:
                try:
                    gnss_clock_df = pd.read_sql_query("SELECT * from gnss_clock_measurement_table", db_con)
                    self.measurements[GNSSClockMeasurementSeries] = GNSSClockMeasurementSeries(
                        filename=self.filename, rdy_format_version=self.rdy_format_version, **dict(gnss_clock_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug(
                        "(%s) DatabaseError occurred when accessing gnss_clock_measurement_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and NMEAMessageSeries in self._series) or self._series is None:
                try:
                    nmea_df = pd.read_sql_query("SELECT * from nmea_messages_table", db_con)
                    self.measurements[NMEAMessageSeries] = NMEAMessageSeries(
                        filename=self.filename, rdy_format_version=self.rdy_format_version, **dict(nmea_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug("(%s) DatabaseError occurred when accessing nmea_messages_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and PressureSeries in self._series) or self._series is None:
                try:
                    pressure_df = pd.read_sql_query("SELECT * from pressure_measurements_table", db_con)
                    self.measurements[PressureSeries] = PressureSeries(filename=self.filename,
                                                                       rdy_format_version=self.rdy_format_version,
                                                                       **dict(pressure_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug(
                        "(%s) DatabaseError occurred when accessing pressure_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and TemperatureSeries in self._series) or self._series is None:
                try:
                    temperature_df = pd.read_sql_query("SELECT * from temperature_measurements_table", db_con)
                    self.measurements[TemperatureSeries] = TemperatureSeries(filename=self.filename,
                                                                             rdy_format_version=self.rdy_format_version,
                                                                             **dict(temperature_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug(
                        "(%s) DatabaseError occurred when accessing temperature_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and HumiditySeries in self._series) or self._series is None:
                try:
                    humidity_df = pd.read_sql_query("SELECT * from humidity_measurements_table", db_con)
                    self.measurements[HumiditySeries] = HumiditySeries(filename=self.filename,
                                                                       rdy_format_version=self.rdy_format_version,
                                                                       **dict(humidity_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug(
                        "(%s) DatabaseError occurred when accessing humidity_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and LightSeries in self._series) or self._series is None:
                try:
                    light_df = pd.read_sql_query("SELECT * from light_measurements_table", db_con)
                    self.measurements[LightSeries] = LightSeries(filename=self.filename,
                                                                 rdy_format_version=self.rdy_format_version,
                                                                 **dict(light_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug("(%s) DatabaseError occurred when accessing light_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and WzSeries in self._series) or self._series is None:
                try:
                    wz_df = pd.read_sql_query("SELECT * from wz_measurements_table", db_con)
                    self.measurements[WzSeries] = WzSeries(filename=self.filename,
                                                           rdy_format_version=self.rdy_format_version,
                                                           **dict(wz_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug("(%s) DatabaseError occurred when accessing wz_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and SubjectiveComfortSeries in self._series) or self._series is None:
                try:
                    subjective_comfort_df = pd.read_sql_query("SELECT * from subjective_comfort_measurements_table",
                                                              db_con)
                    self.measurements[SubjectiveComfortSeries] = SubjectiveComfortSeries(
                        filename=self.filename,
                        rdy_format_version=self.rdy_format_version,
                        **dict(subjective_comfort_df))
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug(
                        "(%s) DatabaseError occurred when accessing subjective_comfort_measurements_table" % self.filename)
                    logger.debug(e)

            if (self._series is not None and NTPDatetimeSeries in self._series) or self._series is None:
                try:
                    ntp_datetime_df = pd.read_sql_query("SELECT * from ntp_measurements_table", db_con)
                    self.measurements[NTPDatetimeSeries] = NTPDatetimeSeries(
                        filename=self.filename,
                        rdy_format_version=self.rdy_format_version,
                        strip_timezone=self.strip_timezone,
                        **dict(ntp_datetime_df))

                except (DatabaseError, PandasDatabaseError) as e:
                    logger.debug(
                        "(%s) DatabaseError occurred when accessing subjective_comfort_measurements_table" % self.filename)
                    logger.debug(e)

            db_con.close()

        else:
            raise ValueError("File extension %s is not supported" % self.extension)

        if (self.ntp_date_time is None) and \
                (self.ntp_timestamp is None or self.ntp_timestamp == 0) and \
                len(self.measurements[NTPDatetimeSeries]) > 0:
            self.ntp_timestamp = self.measurements[NTPDatetimeSeries]._time[0]
            self.ntp_date_time = self.measurements[NTPDatetimeSeries].ntp_datetime[0]

        if self.trim_ends:
            for m in self.measurements.values():
                if len(m) > 0:
                    m.trim_ends(self.timestamp_when_started, self.timestamp_when_stopped)

    def to_df(self, interpolate: bool = True) -> pd.DataFrame:
        """ Merges the measurement series to a single DataFrame

        Parameters
        ----------
            interpolate : bool
                If true interpolates NaN values of concatenated measurement series

        Returns
        -------
            pd.DataFrame
        """
        data_frames = [series.to_df() for series in self.measurements.values()]

        # Concatenate dataframes and resort them ascending
        df_merged = pd.concat(data_frames).sort_index()

        # Merge identical indices by taking mean of column values and then interpolate NaN values
        if interpolate:
            df_merged = df_merged.groupby(level=0).mean().interpolate()
        else:
            df_merged = df_merged.groupby(level=0).mean()
        return df_merged


class FileIterator:
    def __init__(self, file: RDYFile):
        self._file = file
        self._series_types = list(self._file.measurements.keys())
        self._index = 0

    def __next__(self):
        if self._index < len(self._series_types):
            series_type = self._series_types[self._index]

            self._index += 1
            return self._file.measurements[series_type]
        else:
            raise StopIteration
