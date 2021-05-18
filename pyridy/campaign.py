import logging
import os
from pathlib import Path
from typing import List, Union

from tqdm.auto import tqdm

from .file import RDYFile
from .utils import GPSSeries

logger = logging.getLogger(__name__)


class Campaign:
    def __init__(self, name="", folder: Union[list, str] = None, recursive=True, exclude: Union[list, str] = None,
                 sync_method: str = None, lat_sw: float = None, lon_sw: float = None, lat_ne: float = None,
                 lon_ne: float = None):
        """
        A measurement campaign manages loading, processing etc of RDY files
        :param sync_method: Must be "timestamp", "device_time" or "gps_time", "timestamp" uses the timestamp when the
        measurement started to adjust the timestamps (outputs nanoseconds), "device_time" transforms the time series to the
        datetime (outputs datetime), "gps_time" uses the utc gps time if available (outputs datetime), if no gps data
        is available it will fallback to the "device_time" method, "ntp_time" uses network time, if not available, it
        will fallback to the "device_time" methode
        :param name: Name of the Campaign
        :param folder: Path(s) to folder(s) where to search for measurement files
        :param recursive: If True also searches in subfolders
        :param exclude: List or str of folder(s) to exclude
        :param lat_sw: SW boundary Latitude of Campaign
        :param lon_sw: SW boundary Longitude of Campaign
        :param lat_ne: NE boundary Latitude of Campaign
        :param lon_ne: NE boundary Longitude of Campaign
        """
        self.folder = folder
        self.name = name
        self.files: List[RDYFile] = []
        self.lat_sw, self.lon_sw = lat_sw, lon_sw
        self.lat_ne, self.lon_ne = lat_ne, lon_ne

        if sync_method is not None and sync_method not in ["timestamp", "device_time", "gps_time", "ntp_time"]:
            raise ValueError(
                "synchronize argument must 'timestamp', 'device_time', 'gps_time' or 'ntp_time' not %s" % sync_method)

        self.sync_method = sync_method

        if folder:
            self.import_folder(self.folder, recursive, exclude)

        if not self.lat_sw or not self.lat_ne or not self.lon_sw or not self.lon_ne:
            self.determine_geographic_extent()

        pass

    def __call__(self, name):
        return list(filter(lambda file: file.name == name, self.files))

    def __getitem__(self, index):
        return self.files[index]

    def __len__(self):
        return len(self.files)

    def determine_geographic_extent(self):
        """
        Determines the geographic boundaries of the measurement files
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
        self.lat_ne = min(max_lats) if max_lats else None
        self.lon_sw = max(min_lons) if min_lons else None
        self.lon_ne = max(max_lons) if max_lons else None
        logging.info("Geographic boundaries of measurement campaign: Lat SW: %s, Lon SW: %s, Lat NE: %s, Lon NE: %s"
                     % (str(self.lat_sw), str(self.lon_sw), str(self.lat_ne), str(self.lon_ne)))
        pass

    def clear_files(self):
        """
        Clears all files
        :return:
        """
        self.files = []

    def import_folder(self, folder: Union[list, str] = None, recursive: bool = True, exclude: Union[list, str] = None,
                      sync_method: str = None, det_geo_extent: bool = True):
        """

        :param det_geo_extent: If True determines the current geographic extent of the campaign
        :param sync_method:
        :param exclude:
        :param recursive: If True, recursively opens subfolder and tries to load files
        :param folder: Path(s) to folder(s) that should be imported
        :return:
        """
        if exclude is None:
            exclude = []

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
                self.files.append(RDYFile(p, sync_method=sync_method))
            else:
                self.files.append(RDYFile(p, sync_method=self.sync_method))

        if det_geo_extent:
            self.determine_geographic_extent()
