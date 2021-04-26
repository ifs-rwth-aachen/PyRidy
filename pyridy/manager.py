from typing import List

from .file import RDYFile


class Manager:
    def __init__(self):
        """
        The Manager manages loading, processing etc of RDY files
        """
        self.files: List[RDYFile] = []
        pass

    def import_folder(self, path):
        """

        :param path: path to Ridy files
        :return:
        """
        pass
