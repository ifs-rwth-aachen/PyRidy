import json
import logging
import os
import sqlite3
from datetime import datetime
from functools import reduce
from sqlite3 import Connection, DatabaseError
from typing import Optional, List

import pandas as pd
from pandas.io.sql import DatabaseError as PandasDatabaseError

from pyridy.utils import Sensor, AccelerationSeries, LinearAccelerationSeries, MagnetometerSeries, OrientationSeries, \
    GyroSeries, RotationSeries, GPSSeries, PressureSeries, HumiditySeries, TemperatureSeries, WzSeries, LightSeries, \
    SubjectiveComfortSeries
from pyridy.utils.device import Device

logger = logging.getLogger(__name__)


class RDYFile:
    def __init__(self, path: str = ""):
        self.path = path
        self.name: Optional[str] = ""
        self.extension: Optional[str] = ""

        self.db_con: Optional[Connection] = None

        # RDY File Infos
        self.rdy_format_version: Optional[float] = None
        self.rdy_info_name: Optional[str] = None
        self.rdy_info_sex: Optional[str] = None
        self.rdy_info_age: Optional[int] = None
        self.rdy_info_height: Optional[float] = None
        self.rdy_info_weight: Optional[float] = None

        self.t0: Optional[str] = None
        self.timestamp_when_started: Optional[int] = None
        self.timestamp_when_stopped: Optional[int] = None
        self.device: Optional[Device] = None

        # Sensors
        self.sensors: Optional[List[Sensor]] = []

        # Measurement Series
        self.measurements = {AccelerationSeries: AccelerationSeries(),
                             LinearAccelerationSeries: LinearAccelerationSeries(),
                             MagnetometerSeries: MagnetometerSeries(),
                             OrientationSeries: OrientationSeries(),
                             GyroSeries: GyroSeries(),
                             RotationSeries: RotationSeries(),
                             GPSSeries: GPSSeries(),
                             PressureSeries: PressureSeries(),
                             TemperatureSeries: TemperatureSeries(),
                             HumiditySeries: HumiditySeries(),
                             LightSeries: LightSeries(),
                             WzSeries: WzSeries(),
                             SubjectiveComfortSeries: SubjectiveComfortSeries()}

        if self.path:
            self.load_file(self.path)
        pass

    def __iter__(self):
        """
        The FileIterator returns the measurements iteratively
        :return: FileIterator
        """
        return FileIterator(self)

    def __repr__(self):
        return "%s" % self.name

    def load_file(self, path: str):
        logger.info("Loading file: %s" % path)

        _, self.extension = os.path.splitext(path)
        _, self.name = os.path.split(path)

        if self.extension == ".rdy":
            with open(path, 'r') as file:
                rdy = json.load(file)

            if 'RDY_Format_Version' in rdy:
                self.rdy_format_version = rdy['RDY_Format_Version']
            else:
                logger.info("No RDY_Format_Version in file: %s" % self.name)
                self.rdy_format_version = None

            if 'RDY_Info_Name' in rdy:
                self.rdy_info_name = rdy['RDY_Info_Name']
            else:
                logger.info("No RDY_Info_Name in file: %s" % self.name)
                self.rdy_info_name = None

            if 'RDY_Info_Sex' in rdy:
                self.rdy_info_sex = rdy['RDY_Info_Sex']
            else:
                logger.info("No RDY_Info_Sex in file: %s" % self.name)
                self.rdy_info_sex = None

            if 'RDY_Info_Age' in rdy:
                self.rdy_info_age = rdy['RDY_Info_Age']
            else:
                logger.info("No RDY_Info_Age in file: %s" % self.name)
                self.rdy_info_age = None

            if 'RDY_Info_Height' in rdy:
                self.rdy_info_height = rdy['RDY_Info_Height']
            else:
                logger.info("No RDY_Info_Height in file: %s" % self.name)
                self.rdy_info_height = None

            if 'RDY_Info_Weight' in rdy:
                self.rdy_info_weight = rdy['RDY_Info_Weight']
            else:
                logger.info("No RDY_Info_Weight in file: %s" % self.name)
                self.rdy_info_weight = None

            if 't0' in rdy:
                self.t0 = datetime.fromisoformat(rdy['t0'])
            else:
                self.t0 = None
                logger.info("No t0 in file: %s" % self.name)

            if 'timestamp_when_started' in rdy:
                self.timestamp_when_started = rdy['timestamp_when_started']
            else:
                self.timestamp_when_started = None
                logger.info("No timestamp_when_started in file: %s" % self.name)

            if 'timestamp_when_stopped' in rdy:
                self.timestamp_when_stopped = rdy['timestamp_when_stopped']
            else:
                self.timestamp_when_stopped = None
                logger.info("No timestamp_when_stopped in file: %s" % self.name)

            if "device" in rdy:
                self.device = Device(**rdy['device_info'])
            else:
                logger.info("No device information in file: %s" % self.name)

            if "sensors" in rdy:
                for sensor in rdy['sensors']:
                    self.sensors.append(Sensor(**sensor))
            else:
                logger.info("No sensor descriptions in file: %s" % self.name)

            if "acc_series" in rdy:
                self.measurements[AccelerationSeries] = AccelerationSeries(**rdy['acc_series'])
            else:
                logger.info("No Acceleration Series in file: %s" % self.name)

            if "lin_acc_series" in rdy:
                self.measurements[LinearAccelerationSeries] = LinearAccelerationSeries(**rdy['lin_acc_series'])
            else:
                logger.info("No Linear Acceleration Series in file: %s" % self.name)

            if "mag_series" in rdy:
                self.measurements[MagnetometerSeries] = MagnetometerSeries(**rdy['mag_series'])
            else:
                logger.info("No Magnetometer Series in file: %s" % self.name)

            if "orient_series" in rdy:
                self.measurements[OrientationSeries] = OrientationSeries(**rdy['orient_series'])
            else:
                logger.info("No Orientation Series in file: %s" % self.name)

            if "gyro_series" in rdy:
                self.measurements[GyroSeries] = GyroSeries(**rdy['gyro_series'])
            else:
                logger.info("No Gyro Series in file: %s" % self.name)

            if "rot_series" in rdy:
                self.measurements[RotationSeries] = RotationSeries(**rdy['rot_series'])
            else:
                logger.info("No Rotation Series in file: %s" % self.name)

            if "gps_series" in rdy:
                self.measurements[GPSSeries] = GPSSeries(**rdy['gps_series'])
            else:
                logger.info("No GPS Series in file: %s" % self.name)

            if "pressure_series" in rdy:
                self.measurements[PressureSeries] = PressureSeries(**rdy['pressure_series'])
            else:
                logger.info("No Pressure Series in file: %s" % self.name)

            if "temperature_series" in rdy:
                self.measurements[TemperatureSeries] = TemperatureSeries(**rdy['temperature_series'])
            else:
                logger.info("No Temperature Series in file: %s" % self.name)

            if "humidity_series" in rdy:
                self.measurements[HumiditySeries] = HumiditySeries(**rdy['humidity_series'])
            else:
                logger.info("No Humidity Series in file: %s" % self.name)

            if "light_series" in rdy:
                self.measurements[LightSeries] = LightSeries(**rdy['light_series'])
            else:
                logger.info("No Light Series in file: %s" % self.name)

            if "wz_series" in rdy:
                self.measurements[WzSeries] = WzSeries(**rdy['wz_series'])
            else:
                logger.info("No Wz Series in file: %s" % self.name)

            if "subjective_comfort_series" in rdy:
                self.measurements[SubjectiveComfortSeries] = SubjectiveComfortSeries(**rdy['subjective_comfort_series'])
            else:
                logger.info("No Subjective Comfort Series in file: %s" % self.name)
            pass

        elif self.extension == ".sqlite":
            self.db_con = sqlite3.connect(path)

            try:
                info = dict(pd.read_sql_query("SELECT * from measurement_information_table", self.db_con))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing measurement_information_table, file: %s" % self.name)
                try:
                    info = dict(pd.read_sql_query("SELECT * from measurment_information_table",
                                                  self.db_con))  # Older files can contain wrong table name
                except (DatabaseError, PandasDatabaseError) as e:
                    info = None

            try:
                sensor_df = pd.read_sql_query("SELECT * from sensor_descriptions_table", self.db_con)
                for _, row in sensor_df.iterrows():
                    self.sensors.append(Sensor(**dict(row)))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing sensor_descriptions_table, file: %s" % self.name)

            try:
                device_df = pd.read_sql_query("SELECT * from device_information_table", self.db_con)
                self.device = Device(**dict(device_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing device_information_table, file: %s" % self.name)
                self.device = Device()

            # Info
            if info is not None:
                self.rdy_format_version = info['rdy_format_version'][0] if len(info['rdy_format_version']) > 0 else None
                self.rdy_info_name = info['rdy_info_name'][0] if len(info['rdy_info_name']) > 0 else None
                self.rdy_info_sex = info['rdy_info_sex'][0] if len(info['rdy_info_sex']) > 0 else None
                self.rdy_info_age = info['rdy_info_age'][0] if len(info['rdy_info_age']) > 0 else None
                self.rdy_info_height = info['rdy_info_height'][0] if len(info['rdy_info_height']) > 0 else None
                self.rdy_info_weight = info['rdy_info_weight'][0] if len(info['rdy_info_weight']) > 0 else None

                self.t0 = info['t0'][0] if len(info['t0']) > 0 else None
                self.timestamp_when_started = info['timestamp_when_started'][0] if len(
                    info['timestamp_when_started']) > 0 else None
                self.timestamp_when_stopped = info['timestamp_when_stopped'][0] if len(
                    info['timestamp_when_stopped']) > 0 else None

            # Measurements
            try:
                acc_df = pd.read_sql_query("SELECT * from acc_measurements_table", self.db_con)
                self.measurements[AccelerationSeries] = AccelerationSeries(**dict(acc_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing acc_measurements_table, file: %s" % self.name)

            try:
                lin_acc_df = pd.read_sql_query("SELECT * from lin_acc_measurements_table", self.db_con)
                self.measurements[LinearAccelerationSeries] = LinearAccelerationSeries(**dict(lin_acc_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing lin_acc_measurements_table, file: %s" % self.name)

            try:
                mag_df = pd.read_sql_query("SELECT * from mag_measurements_table", self.db_con)
                self.measurements[MagnetometerSeries] = MagnetometerSeries(**dict(mag_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing mag_measurements_table, file: %s" % self.name)

            try:
                orient_df = pd.read_sql_query("SELECT * from orient_measurements_table", self.db_con)
                self.measurements[OrientationSeries] = OrientationSeries(**dict(orient_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing orient_measurements_table, file: %s" % self.name)

            try:
                gyro_df = pd.read_sql_query("SELECT * from gyro_measurements_table", self.db_con)
                self.measurements[GyroSeries] = GyroSeries(**dict(gyro_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing gyro_measurements_table, file: %s" % self.name)

            try:
                rot_df = pd.read_sql_query("SELECT * from rot_measurements_table", self.db_con)
                self.measurements[RotationSeries] = RotationSeries(**dict(rot_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing rot_measurements_table, file: %s" % self.name)

            try:
                gps_df = pd.read_sql_query("SELECT * from gps_measurements_table", self.db_con)
                self.measurements[GPSSeries] = GPSSeries(**dict(gps_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing gps_measurements_table, file: %s" % self.name)

            try:
                pressure_df = pd.read_sql_query("SELECT * from pressure_measurements_table", self.db_con)
                self.measurements[PressureSeries] = PressureSeries(**dict(pressure_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing pressure_measurements_table, file: %s" % self.name)

            try:
                temperature_df = pd.read_sql_query("SELECT * from temperature_measurements_table", self.db_con)
                self.measurements[TemperatureSeries] = TemperatureSeries(**dict(temperature_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing temperature_measurements_table, file: %s" % self.name)

            try:
                humidity_df = pd.read_sql_query("SELECT * from humidity_measurements_table", self.db_con)
                self.measurements[HumiditySeries] = HumiditySeries(**dict(humidity_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing humidity_measurements_table, file: %s" % self.name)

            try:
                light_df = pd.read_sql_query("SELECT * from light_measurements_table", self.db_con)
                self.measurements[LightSeries] = LightSeries(**dict(light_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing light_measurements_table, file: %s" % self.name)

            try:
                wz_df = pd.read_sql_query("SELECT * from wz_measurements_table", self.db_con)
                self.measurements[WzSeries] = WzSeries(**dict(wz_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing wz_measurements_table, file: %s" % self.name)

            try:
                subjective_comfort_df = pd.read_sql_query("SELECT * from subjective_comfort_measurements_table",
                                                          self.db_con)
                self.measurements[SubjectiveComfortSeries] = SubjectiveComfortSeries(**dict(subjective_comfort_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing subjective_comfort_measurements_table, file: %s" % self.name)

        else:
            raise ValueError("File extension %s is not supported" % self.extension)

    def to_df(self) -> pd.DataFrame:
        """

        :return: DataFrame containing merged measurement series
        """
        data_frames = [series.to_df() for series in self.measurements.values()]

        # Concatenate dataframes and resort them ascending
        df_merged = pd.concat(data_frames).sort_index()

        # Merge identical indices by taking mean of column values and then interpolate NaN values
        df_merged = df_merged.groupby(level=0).mean().interpolate()
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
