import logging
import os
from pathlib import Path
from typing import List, Union, Tuple

from ipyleaflet import Map, Polyline, Marker, Icon, FullScreenControl, ScaleControl, basemap_to_tiles
from ipywidgets import HTML
from tqdm.auto import tqdm

from .file import RDYFile
from .osm import OSMRegion, OSMRailwaySwitch, OSMRailwaySignal, OSMLevelCrossing
from .utils import GPSSeries
from .utils.tools import generate_random_color

logger = logging.getLogger(__name__)


class Campaign:
    def __init__(self, name="", folder: Union[list, str] = None, recursive=True, exclude: Union[list, str] = None,
                 sync_method: str = None, strip_timezone: bool = True, cutoff: bool = True, lat_sw: float = None,
                 lon_sw: float = None, lat_ne: float = None,
                 lon_ne: float = None, download_osm_region: bool = False, railway_types: Union[list, str] = None):
        """

        Parameters
        ----------
        name: str
            Name of the campaign
        folder: str or list of str
            Folder or list of folders that should be imported
        recursive: bool, default: True
            Flag if folders should be searched recursively
        exclude: str or list of str
            Name(s) of file or folder that should be excluded
        sync_method: str
            Method to use to sync timestamps of individual files
        strip_timezone: bool, default: True
            Strips timezone from timestamps as np.datetime64 does not support timezones
        cutoff: bool, default: True
            If True, cutoffs the measurements precisely to the timestamp when the measurement was started, respectively
            stopped. By default Ridy measurement files can contain several seconds of measurements from before/after
            the button press
        lat_sw: float
            South west Latitude of the campaign, if the geographic extent is not given via arguments, the library tries
            to determine the geographic extent based on the GPS tracks
        lon_sw: float
            South west longitude of the campaign
        lat_ne: float
            North east latitude of the campaign
        lon_ne: float
            North east longitude of the campaign
        download_osm_region: bool, default: False
            If True download OSM data via the Overpass API
        railway_types: list or list of str
            Railway type to be downloaded from OSM, e.g., "rail", "subway", "tram" or "light_rail"
        """
        self._colors = []  # Used colors

        self.folder = folder
        self.name = name
        self.files: List[RDYFile] = []
        self.lat_sw, self.lon_sw = lat_sw, lon_sw
        self.lat_ne, self.lon_ne = lat_ne, lon_ne
        self.osm_region = None

        if sync_method is not None and sync_method not in ["timestamp", "device_time", "gps_time", "ntp_time"]:
            raise ValueError(
                "synchronize argument must 'timestamp', 'device_time', 'gps_time' or 'ntp_time' not %s" % sync_method)

        self.sync_method = sync_method
        self.strip_timezone = strip_timezone
        self.cutoff = cutoff

        if folder:
            self.import_folder(self.folder, recursive, exclude)

        if not self.lat_sw or not self.lat_ne or not self.lon_sw or not self.lon_ne:
            self.determine_geographic_extent()

        if download_osm_region:
            self.osm_region = OSMRegion(lat_sw=self.lat_sw, lon_sw=self.lon_sw, lat_ne=self.lat_ne, lon_ne=self.lon_ne,
                                        desired_railway_types=railway_types)

    def __call__(self, name):
        results = list(filter(lambda file: file.name == name, self.files))
        if len(results) == 1:
            return results[0]
        else:
            return results

    def __getitem__(self, index):
        return self.files[index]

    def __len__(self):
        return len(self.files)

    def add_tracks_to_map(self, m: Map) -> Map:
        """ Add all GPS tracks from the campaign files to a Map

        Parameters
        ----------
        m: Map
            ipyleaflet Map

        Returns
        -------
        Map

        """
        for file in self.files:
            m = self.add_track_to_map(m, file=file)

        return m

    def add_track_to_map(self, m: Map, name: str = "", file: RDYFile = None) -> Map:
        """ Adds a GPS track from a file to the Map

        Parameters
        ----------
        m: Map
            ipyleaflet map
        name: str
            Name of the file that should be drawn onto the map
        file: RDYFile
            Alternatively, provide RDYFile that should be drawn on the map

        Returns
        -------
        Map

        """
        if name != "":
            files = [self(name)]
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
                start_message.value = "<p>Start:</p><p>" + f.name + "</p><p>" + f.device.manufacturer + "; " \
                                      + f.device.model + "</p>"
                end_message.value = "<p>End:</p><p>" + f.name + "</p><p>" + f.device.manufacturer + "; " \
                                    + f.device.model + "</p>"

                start_marker.popup = start_message
                end_marker.popup = end_message

                m.add_layer(start_marker)
                m.add_layer(end_marker)

        return m

    def add_osm_routes_to_map(self, m: Map) -> Map:
        """ Adds OSM Routes from the downloaded OSM Region

        Parameters
        ----------
        m: Map
            ipyleaflet Map

        Returns
        -------
        Map

        """
        if self.osm_region:
            for line in self.osm_region.railway_lines:
                coords = line.to_ipyleaflet()
                file_polyline = Polyline(locations=coords, color=line.color, fill=False, weight=4)
                m.add_layer(file_polyline)
        else:
            logger.warning("No OSM region downloaded!")

        return m

    def add_osm_railway_elements_to_map(self, m: Map) -> Map:
        """ Draws railway elements using markers on top of a map

        Parameters
        ----------
        m: Map
            Map where railway elements should be drawn onto

        Returns
        -------
        m: Map
            Map containing railway elements

        """
        if self.osm_region:
            for el in self.osm_region.railway_elements:
                if type(el) == OSMRailwaySwitch:
                    icon = Icon(
                        icon_url='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-black.png',
                        shadow_url='https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                        icon_size=[25, 41],
                        icon_anchor=[12, 41],
                        popup_anchor=[1, -34],
                        shadow_size=[41, 41])
                    marker = Marker(location=(el.lat, el.lon), draggable=False, icon=icon)

                    m.add_layer(marker)
                elif type(el) == OSMRailwaySignal:
                    pass
                elif type(el) == OSMLevelCrossing:
                    pass
                else:
                    pass
        return m

    def determine_geographic_extent(self):
        """ Determines the geographic extent of the campaign in terms of min/max lat/lon

        """
        min_lats = []
        max_lats = []
        min_lons = []
        max_lons = []

        for f in self.files:
            gps_series = f.measurements[GPSSeries]
            if gps_series.is_empty():
                continue
            else:
                min_lats.append(gps_series.lat.min())
                max_lats.append(gps_series.lat.max())
                min_lons.append(gps_series.lon.min())
                max_lons.append(gps_series.lon.max())

        self.lat_sw = min(min_lats) if min_lats else None
        self.lat_ne = max(max_lats) if max_lats else None
        self.lon_sw = min(min_lons) if min_lons else None
        self.lon_ne = max(max_lons) if max_lons else None
        logging.info("Geographic boundaries of measurement campaign: Lat SW: %s, Lon SW: %s, Lat NE: %s, Lon NE: %s"
                     % (str(self.lat_sw), str(self.lon_sw), str(self.lat_ne), str(self.lon_ne)))

    def clear_files(self):
        """
            Clear all files from the campaign
        """
        self.files = []

    def create_map(self, center: Tuple[float, float] = None, show_railway_elements=False) -> Map:
        """ Creates a ipyleaflet map showing the GPS tracks of measurement files

        Parameters
        ----------
        center
        show_railway_elements

        Returns
        -------

        """
        if not center:
            if self.lat_sw and self.lat_ne and self.lon_sw and self.lon_ne:
                center = (
                    (self.lat_sw + self.lat_ne) / 2,
                    (self.lon_sw + self.lon_ne) / 2)
            else:
                raise ValueError("Cant determine geographic center of campaign, enter manually using 'center' argument")

        open_street_map_bw = dict(
            url='https://{s}.tiles.wmflabs.org/bw-mapnik/{z}/{x}/{y}.png',
            max_zoom=19,
            name="OpenStreetMap BW"
        )

        open_railway_map = dict(
            url='https://{s}.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png',
            max_zoom=19,
            attribution='<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>, Style: <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA 2.0</a> <a href="http://www.openrailwaymap.org/">OpenRailwayMap</a> and OpenStreetMap',
            name='OpenRailwayMap'
        )

        m = Map(center=center, zoom=12, scroll_wheel_zoom=True, basemap=basemap_to_tiles(open_street_map_bw))
        m.add_control(ScaleControl(position='bottomleft'))
        m.add_control(FullScreenControl())

        # Add map
        osm_layer = basemap_to_tiles(open_railway_map)
        m.add_layer(osm_layer)

        # Plot GPS point for each measurement and OSM Tracks
        m = self.add_osm_routes_to_map(m)
        m = self.add_tracks_to_map(m)

        if show_railway_elements:
            m = self.add_osm_railway_elements_to_map(m)

        return m

    def import_files(self, paths: Union[list, str] = None, sync_method: str = None,
                     det_geo_extent: bool = True, download_osm_region: bool = False,
                     railway_types: Union[list, str] = None):
        """ Import files into the campaign

        Parameters
        ----------
        paths: str or list of str
            Individual file paths of the files that should be imported
        sync_method: str
            Method to use for timestamp syncing
        det_geo_extent: bool, default: True
            If True, determine the geographic extent of the imported files
        download_osm_region: bool, default: False
            If True, download OSM Data via the Overpass API
        railway_types: str or list of str
            Railway types to be downloaded via the Overpass API
        """
        if type(paths) == str:
            paths = [paths]
        elif type(paths) == list:
            pass
        else:
            raise TypeError("paths argument must be list of str or str")

        for p in tqdm(paths):
            if sync_method:
                self.sync_method = sync_method
                self.files.append(RDYFile(p, sync_method=sync_method))
            else:
                self.files.append(RDYFile(p, sync_method=self.sync_method))

        if det_geo_extent:
            self.determine_geographic_extent()

        if download_osm_region:
            self.osm_region = OSMRegion(lat_sw=self.lat_sw, lon_sw=self.lon_sw, lat_ne=self.lat_ne, lon_ne=self.lon_ne,
                                        desired_railway_types=railway_types)

    def import_folder(self, folder: Union[list, str] = None, recursive: bool = True, exclude: Union[list, str] = None,
                      sync_method: str = None, strip_timezone: bool = None, cutoff: bool = True,
                      det_geo_extent: bool = True, download_osm_region: bool = False,
                      railway_types: Union[list, str] = None):
        """ Imports folder(s) into the campaign

        Parameters
        ----------
        folder: str or list of str
            Folder(s) that should be imported
        recursive: bool, default: True
            Flag if folders should be imported recursively, i.e., whether subfolders should also be searched
        exclude: str or list of str
            Folder(s) or file(s) that should be excluded while importing
        sync_method:
            Method for timestamp syncing
        strip_timezone: bool, default: True
            If True, strips timezone from timestamp arrays
        cutoff: bool, default: True
            If True, cutoffs measurement precisely to timestamp when the measurement was started respectively stopped
        det_geo_extent: bool: default: True
            If True, tries to automatically determine the geographic extent of the imported files via their GPS tracks
        download_osm_region: bool, default: True
            If True, downloads OSM Data via the Overpass API
        railway_types: str or list of str
            Railway types to be downloaded via the Overpass API
        """
        if exclude is None:
            exclude = []
        elif type(exclude) == str:
            exclude = [exclude]

        if type(folder) == str:
            folder = [folder]
        elif type(folder) == list:
            pass
        else:
            raise TypeError("folder argument must be list or str")

        file_paths = []

        for fdr in folder:
            if recursive:
                all_paths = list(Path(fdr).rglob("*"))

                # File paths without excluded files or folder names
                for p in all_paths:
                    inter = set(p.parts).intersection(set(exclude))
                    if len(inter) > 0:
                        continue
                    else:
                        if p.suffix in [".rdy", ".sqlite"]:
                            file_paths.append(p)
                        else:
                            continue
            else:
                _, _, files = next(os.walk(fdr))
                for f in files:
                    file_path = os.path.join(fdr, f)
                    _, ext = os.path.splitext(file_path)
                    if f not in exclude and ext in [".rdy", ".sqlite"]:
                        file_paths.append(file_path)

                pass

        for p in tqdm(file_paths):
            if sync_method:
                self.sync_method = sync_method
                if strip_timezone is not None:
                    self.files.append(RDYFile(path=p, sync_method=sync_method, strip_timezone=strip_timezone,
                                              cutoff=cutoff))
                else:
                    self.files.append(RDYFile(path=p, sync_method=sync_method, strip_timezone=self.strip_timezone,
                                              cutoff=cutoff))
            else:
                if strip_timezone is not None:
                    self.files.append(RDYFile(path=p, sync_method=self.sync_method, strip_timezone=strip_timezone,
                                              cutoff=cutoff))
                else:
                    self.files.append(RDYFile(path=p, sync_method=self.sync_method, strip_timezone=self.strip_timezone,
                                              cutoff=cutoff))

        if det_geo_extent:
            self.determine_geographic_extent()

        if download_osm_region:
            self.osm_region = OSMRegion(lat_sw=self.lat_sw, lon_sw=self.lon_sw, lat_ne=self.lat_ne, lon_ne=self.lon_ne,
                                        desired_railway_types=railway_types)
