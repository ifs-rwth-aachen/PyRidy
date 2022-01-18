import logging
from typing import List, Tuple

import pandas as pd
from ipyleaflet import Map, Polyline, Marker, Icon, FullScreenControl, ScaleControl, LocalTileLayer, \
    CircleMarker, LayerGroup
from ipywidgets import HTML
from tqdm.notebook import tqdm

from pyridy import Campaign
from pyridy.file import RDYFile
from pyridy.processing.condition import ConditionProcessor
from pyridy.utils import GPSSeries
from pyridy.utils.tools import generate_random_color

logger = logging.getLogger(__name__)


class PostProcessor:
    def __init__(self, campaign: Campaign, thres_lo: float = 0.15, thres_hi: float = 0.25, v_thres: float = 1.0,
                 sampling_period: str = "1000ms", method="acc"):
        self._colors = []  # Used colors
        self.campaign = campaign

        self.con_proc = ConditionProcessor(thres_lo, thres_hi, v_thres, sampling_period)
        self.trk_conds: List[pd.DataFrame] = []

        for f in tqdm(self.campaign.files):
            self.trk_conds.append(self.con_proc.process_file(f, method))

    def create_map(self, center: Tuple[float, float] = None, hide_good_sections: bool = False,
                   path_to_offline_tiles: str = "", show_osm_routes: bool = False) -> Map:
        if not center:
            if self.campaign.lat_sw and self.campaign.lat_ne and self.campaign.lon_sw and self.campaign.lon_ne:
                center = (
                    (self.campaign.lat_sw + self.campaign.lat_ne) / 2,
                    (self.campaign.lon_sw + self.campaign.lon_ne) / 2)
            else:
                raise ValueError("Cant determine geographic center of campaign, enter manually using 'center' argument")

        m = Map(center=center, zoom=13, scroll_wheel_zoom=True)

        m.add_control(ScaleControl(position='bottomleft'))
        m.add_control(FullScreenControl())

        local_layer = LocalTileLayer(path=path_to_offline_tiles, url=path_to_offline_tiles)
        m.add_layer(local_layer)

        # Plot OSM routes, tracks and track condition for each measurement
        if show_osm_routes:
            m = self.add_osm_routes_to_map(m)

        m = self.add_tracks_to_map(m)
        m = self.add_track_condition_to_map(m, hide_good_sections)

        return m

    def add_osm_routes_to_map(self, m: Map) -> Map:
        if self.campaign.osm:
            for line in self.campaign.osm.railway_lines:
                coords = line.to_ipyleaflet()
                file_polyline = Polyline(locations=coords, color=line.color, fill=False, weight=4)
                m.add_layer(file_polyline)

        return m

    def add_track_condition_to_map(self, m: Map, hide_good_sections: bool = False) -> Map:
        for trk_con in self.trk_conds:
            # GOOD Points
            if not hide_good_sections:
                trk_con_good = trk_con[trk_con["condition"] == "GOOD"]
                good_markers = [CircleMarker(location=(lat, lon),
                                             radius=5,
                                             fill_opacity=0.9,
                                             fill_color='#57AB27',
                                             weight=1,
                                             color='#000000')
                                for lat, lon in zip(trk_con_good['lat'], trk_con_good['lon'])]

                l_group_good = LayerGroup(layers=good_markers)
                m.add_layer(l_group_good)

            # SATISFACTORY Points
            trk_con_okay = trk_con[trk_con["condition"] == "SATISFACTORY"]
            okay_markers = [CircleMarker(location=(lat, lon),
                                         radius=5,
                                         fill_opacity=0.9,
                                         fill_color='#F6A800',
                                         weight=1,
                                         color='#000000')
                            for lat, lon in zip(trk_con_okay['lat'], trk_con_okay['lon'])]

            l_group_okay = LayerGroup(layers=okay_markers)
            m.add_layer(l_group_okay)

            # INSUFFICIENT Points
            trk_con_bad = trk_con[trk_con["condition"] == "INSUFFICIENT"]
            bad_markers = [CircleMarker(location=(lat, lon),
                                        radius=5,
                                        fill_opacity=0.9,
                                        fill_color='#CC071E',
                                        weight=1,
                                        color='#000000')
                           for lat, lon in zip(trk_con_bad['lat'], trk_con_bad['lon'])]

            l_group_bad = LayerGroup(layers=bad_markers)
            m.add_layer(l_group_bad)

        return m

    def add_tracks_to_map(self, m: Map) -> Map:
        """
        Adds all tracks(files) in campaign to map m
        :param m:
        :return:
        """
        for file in self.campaign:
            m = self.add_track_to_map(m, file=file)

        return m

    def add_track_to_map(self, m: Map, name: str = "", file: RDYFile = None) -> Map:
        """
        Adds a single track to the map given by m. If name and file are given, name will be used
        :param file:
        :param m:
        :param name:
        :return:
        """

        if name != "":
            files = self.campaign(name)
        elif file is not None:
            files = [file]

        else:
            raise ValueError("You must provide either a filename or the file")

        for f in files:
            while True:
                color = generate_random_color("HEX")
                if color not in self._colors:
                    self._colors.append(color)
                    break
                else:
                    continue

            gps_series = f.measurements[GPSSeries]
            coords = gps_series.to_ipyleaflef()

            if coords == [[]]:
                logger.warning("Coordinates are empty in file: %s" % f.name)
            else:
                file_polyline = Polyline(locations=coords, color=color, fill=False, weight=4,
                                         dash_array='10, 10')
                m.add_layer(file_polyline)

                # Add Start/End markers
                start_icon = Icon(
                    icon_url='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
                    shadow_url='https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                    icon_size=[25, 41],
                    icon_anchor=[12, 41],
                    popup_anchor=[1, -34],
                    shadow_size=[41, 41])

                end_icon = Icon(
                    icon_url='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
                    shadow_url='https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                    icon_size=[25, 41],
                    icon_anchor=[12, 41],
                    popup_anchor=[1, -34],
                    shadow_size=[41, 41])

                start_marker = Marker(location=tuple(coords[0]), draggable=False, icon=start_icon)
                end_marker = Marker(location=tuple(coords[-1]), draggable=False, icon=end_icon)

                start_message = HTML()
                end_message = HTML()
                start_message.value = "<p>Start:</p><p>" + f.name + "</p>"
                end_message.value = "<p>End:</p><p>" + f.name + "</p>"

                start_marker.popup = start_message
                end_marker.popup = end_message

                m.add_layer(start_marker)
                m.add_layer(end_marker)
        return m

    @staticmethod
    def add_marker_to_map(m: Map, pos: Tuple[float, float], text: str = "") -> Map:
        # Add Start/End markers
        icon = Icon(
            icon_url='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-orange.png',
            shadow_url='https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            icon_size=[25, 41],
            icon_anchor=[12, 41],
            popup_anchor=[1, -34],
            shadow_size=[41, 41])

        message = HTML()
        message.value = text

        marker = Marker(location=pos, draggable=False, icon=icon)
        marker.popup = message

        m.add_layer(marker)

        return m
