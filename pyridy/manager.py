import os
from typing import List, Union

from .file import RDYFile


class CampaignManager:
    def __init__(self, name="", folder: Union[list, str] = None, recursive=True):
        """
        The Manager manages loading, processing etc of RDY files
        """
        self.folder = folder
        self.name = name
        self.files: List[RDYFile] = []

        if folder:
            self.import_folder(self.folder, recursive)

        pass

    def import_folder(self, folder: Union[list, str] = None, recursive=False):
        """

        :param recursive: If True, recursively opens subfolder and tries to load files
        :param folder: Path(s) to folder(s) that should be imported
        :return:
        """
        if type(folder) == list:
            for fdr in folder:
                self.import_folder(fdr)

        elif type(folder) == str:
            _, sub_folders, files = next(os.walk(folder))

            for sub_folder in sub_folders:
                sub_folder_path = os.path.join(folder, sub_folder)
                self.import_folder(os.path.join(sub_folder_path))

            for file in files:
                file_path = os.path.join(folder, file)
                _, ext = os.path.splitext(file_path)

                if ext not in [".rdy", ".sqlite"]:
                    continue
                else:
                    self.files.append(RDYFile(file_path))

        else:
            raise TypeError("folder argument must be list or str")

        pass
