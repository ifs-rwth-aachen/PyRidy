import logging
import os
from pathlib import Path
from typing import List, Union

from tqdm.auto import tqdm

from .file import RDYFile

logger = logging.getLogger(__name__)


class Campaign:
    def __init__(self, name="", folder: Union[list, str] = None, recursive=True, exclude: Union[list, str] = None,
                 sync_method: str = None):
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
        """
        self.folder = folder
        self.name = name
        self.files: List[RDYFile] = []

        if sync_method is not None and sync_method not in ["timestamp", "device_time", "gps_time", "ntp_time"]:
            raise ValueError("synchronize argument must 'timestamp', 'device_time', 'gps_time' or 'ntp_time' not %s" % sync_method)

        self.sync_method = sync_method

        if folder:
            self.import_folder(self.folder, recursive, exclude)

        pass

    def __call__(self, name):
        return list(filter(lambda file: file.name == name, self.files))

    def __getitem__(self, index):
        return self.files[index]

    def __len__(self):
        return len(self.files)

    def reset(self):
        """
        Resets the Campaign
        :return:
        """
        self.__init__()

    def import_folder(self, folder: Union[list, str] = None, recursive: bool = True, exclude: Union[list, str] = None,
                      sync_method: str = None):
        """

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

        pass
