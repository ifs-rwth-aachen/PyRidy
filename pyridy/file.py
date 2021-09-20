import datetime
import json
import logging
import os
import sqlite3
from sqlite3 import Connection, DatabaseError
from typing import Optional, List

import numpy as np
import pandas as pd
from pandas.io.sql import DatabaseError as PandasDatabaseError

from pyridy.utils import Sensor, AccelerationSeries, LinearAccelerationSeries, MagnetometerSeries, OrientationSeries, \
    GyroSeries, RotationSeries, GPSSeries, PressureSeries, HumiditySeries, TemperatureSeries, WzSeries, LightSeries, \
    SubjectiveComfortSeries
from pyridy.utils.device import Device

logger = logging.getLogger(__name__)


class RDYFile:
    def __init__(self, name: str = "", path: str = "", sync_method: str = None):
        """

        :param sync_method: Must be "timestamp", "device_time" or "gps_time", "timestamp" uses the timestamp when the
        measurement started to adjust the timestamps (outputs nanoseconds), "device_time" transforms the time series to the
        datetime (outputs datetime), "gps_time" uses the utc gps time if available (outputs datetime), if no gps data
        is available it will fallback to the "device_time" method, "ntp_time" uses network time, if not available, it
        will fallback to the "device_time" methode
        :param path: Path to the Ridy file to be imported (can be .sqlite or .rdy)
        """
        self.path = path
        self.name: Optional[str] = name
        self.extension: Optional[str] = ""

        if sync_method is not None and sync_method not in ["timestamp", "device_time", "gps_time", "ntp_time"]:
            raise ValueError(
                "synchronize argument must 'timestamp', 'device_time', 'gps_time' or 'ntp_time' not %s" % sync_method)

        self.sync_method = sync_method
        self.timedelta_unit = 'timedelta64[ns]'

        self.db_con: Optional[Connection] = None

        # Ridy App Info
        self.ridy_version: Optional[str] = None
        self.ridy_version_code: Optional[int] = None

        # RDY File Infos
        self.rdy_format_version: Optional[float] = None
        self.rdy_info_name: Optional[str] = None
        self.rdy_info_sex: Optional[str] = None
        self.rdy_info_age: Optional[int] = None
        self.rdy_info_height: Optional[float] = None
        self.rdy_info_weight: Optional[float] = None

        self.t0: Optional[np.datetime64] = None
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

            if self.timestamp_when_started and self.timestamp_when_stopped:
                self.duration = (self.timestamp_when_stopped - self.timestamp_when_started) * 1e-9

            if self.sync_method:
                self._synchronize()
        else:
            logging.warning("RDYFile instantiated without a path")

        pass

    # def __getitem__(self, idx):
    #     key = list(self.measurements.keys())[idx]
    #     return self.measurements[key]

    def __iter__(self):
        """
        The FileIterator returns the measurements iteratively
        :return: FileIterator
        """
        return FileIterator(self)

    def __repr__(self):
        return "Filename: %s, T0: %s, Duration: %s" % (self.name,
                                                       str(self.t0),
                                                       str(datetime.timedelta(seconds=self.duration)))

    def _synchronize(self):
        if self.sync_method == "timestamp":
            for m in self.measurements.values():
                m.synchronize("timestamp", self.timestamp_when_started, timedelta_unit=self.timedelta_unit)
        elif self.sync_method == "device_time":
            if self.t0:
                for m in self.measurements.values():
                    m.synchronize("device_time", self.timestamp_when_started, self.t0,
                                  timedelta_unit=self.timedelta_unit)
            else:
                logger.warning("t0 is None, falling back to timestamp synchronization")
                self.sync_method = "timestamp"
                self._synchronize()
        elif self.sync_method == "gps_time":
            if len(self.measurements[GPSSeries]) > 0:
                sync_timestamp = self.measurements[GPSSeries].time[0]
                utc_sync_time = self.measurements[GPSSeries].utc_time[0]

                for i, t in enumerate(self.measurements[
                                          GPSSeries].utc_time):  # The first utc_time value ending with 000 is a real GPS measurement
                    if str(t)[-3:] == "000":
                        utc_sync_time = t
                        sync_timestamp = self.measurements[GPSSeries].time[i]
                        break

                sync_time = np.datetime64(int(utc_sync_time * 1e6), "ns")
                for m in self.measurements.values():
                    m.synchronize("gps_time", sync_timestamp, sync_time, timedelta_unit=self.timedelta_unit)
            else:
                logger.warning("No GPS time recording, falling back to device_time synchronization")
                self.sync_method = "device_time"
                self._synchronize()
        elif self.sync_method == "ntp_time":
            if self.ntp_timestamp and self.ntp_date_time:
                for m in self.measurements.values():
                    m.synchronize("gps_time", self.ntp_timestamp, self.ntp_date_time,
                                  timedelta_unit=self.timedelta_unit)
            else:
                logger.warning("No ntp timestamp and datetime, falling back to device_time synchronization")
                self.sync_method = "device_time"
                self._synchronize()
        else:
            raise ValueError(
                "sync_method must 'timestamp', 'device_time', 'gps_time' or 'ntp_time' not %s" % self.sync_method)
        pass

    def get_integrity_report(self):
        """
        Returns a dict object with information of the rdy file
        Returns
        -------
        Data Integrity Report
        """
        report = {}

        for k, v in self.measurements.items():
            if len(v) > 0:
                report[k.__name__] = True
            else:
                report[k.__name__] = False

        attr = self.__dict__.copy()
        attr.update(attr["device"].__dict__.copy())
        for a in ["db_con", "measurements", "device", "sensors"]:
            attr.pop(a)
            pass

        report.update(attr)

        return report

    def load_file(self, path: str):
        """
        Loads a single Ridy file located at path

        Parameters
        ----------
        path Path to the ridy file

        """
        logger.info("Loading file: %s" % path)

        _, self.extension = os.path.splitext(path)
        _, self.name = os.path.split(path)

        if self.extension == ".rdy":
            with open(path, 'r') as file:
                rdy = json.load(file)

            if 'Ridy_Version' in rdy:
                self.ridy_version = rdy['Ridy_Version']
            else:
                logger.info("No Ridy_Version in file: %s" % self.name)
                self.ridy_version = None

            if 'Ridy_Version_Code' in rdy:
                self.ridy_version_code = rdy['Ridy_Version_Code']
            else:
                logger.info("No Ridy_Version_Code in file: %s" % self.name)
                self.ridy_version_code = None

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
                self.t0 = np.datetime64(rdy['t0'])
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

            if 'ntp_timestamp' in rdy:
                self.ntp_timestamp = rdy['ntp_timestamp']
            else:
                self.ntp_timestamp = None
                logger.info("No ntp_timestamp in file: %s" % self.name)

            if 'ntp_date_time' in rdy:
                self.ntp_date_time = np.datetime64(rdy['ntp_date_time'])
            else:
                self.ntp_date_time = None
                logger.info("No ntp_date_time in file: %s" % self.name)

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
                self.measurements[AccelerationSeries] = AccelerationSeries(rdy_format_version=self.rdy_format_version,
                                                                           **rdy['acc_series'])
            else:
                logger.info("No Acceleration Series in file: %s" % self.name)

            if "lin_acc_series" in rdy:
                self.measurements[LinearAccelerationSeries] = LinearAccelerationSeries(
                    rdy_format_version=self.rdy_format_version,
                    **rdy['lin_acc_series'])
            else:
                logger.info("No Linear Acceleration Series in file: %s" % self.name)

            if "mag_series" in rdy:
                self.measurements[MagnetometerSeries] = MagnetometerSeries(rdy_format_version=self.rdy_format_version,
                                                                           **rdy['mag_series'])
            else:
                logger.info("No Magnetometer Series in file: %s" % self.name)

            if "orient_series" in rdy:
                self.measurements[OrientationSeries] = OrientationSeries(rdy_format_version=self.rdy_format_version,
                                                                         **rdy['orient_series'])
            else:
                logger.info("No Orientation Series in file: %s" % self.name)

            if "gyro_series" in rdy:
                self.measurements[GyroSeries] = GyroSeries(rdy_format_version=self.rdy_format_version,
                                                           **rdy['gyro_series'])
            else:
                logger.info("No Gyro Series in file: %s" % self.name)

            if "rot_series" in rdy:
                self.measurements[RotationSeries] = RotationSeries(rdy_format_version=self.rdy_format_version,
                                                                   **rdy['rot_series'])
            else:
                logger.info("No Rotation Series in file: %s" % self.name)

            if "gps_series" in rdy:
                self.measurements[GPSSeries] = GPSSeries(rdy_format_version=self.rdy_format_version,
                                                         **rdy['gps_series'])
            else:
                logger.info("No GPS Series in file: %s" % self.name)

            if "pressure_series" in rdy:
                self.measurements[PressureSeries] = PressureSeries(rdy_format_version=self.rdy_format_version,
                                                                   **rdy['pressure_series'])
            else:
                logger.info("No Pressure Series in file: %s" % self.name)

            if "temperature_series" in rdy:
                self.measurements[TemperatureSeries] = TemperatureSeries(rdy_format_version=self.rdy_format_version,
                                                                         **rdy['temperature_series'])
            else:
                logger.info("No Temperature Series in file: %s" % self.name)

            if "humidity_series" in rdy:
                self.measurements[HumiditySeries] = HumiditySeries(rdy_format_version=self.rdy_format_version,
                                                                   **rdy['humidity_series'])
            else:
                logger.info("No Humidity Series in file: %s" % self.name)

            if "light_series" in rdy:
                self.measurements[LightSeries] = LightSeries(rdy_format_version=self.rdy_format_version,
                                                             **rdy['light_series'])
            else:
                logger.info("No Light Series in file: %s" % self.name)

            if "wz_series" in rdy:
                self.measurements[WzSeries] = WzSeries(rdy_format_version=self.rdy_format_version,
                                                       **rdy['wz_series'])
            else:
                logger.info("No Wz Series in file: %s" % self.name)

            if "subjective_comfort_series" in rdy:
                self.measurements[SubjectiveComfortSeries] = SubjectiveComfortSeries(
                    rdy_format_version=self.rdy_format_version,
                    **rdy['subjective_comfort_series'])
            else:
                logger.info("No Subjective Comfort Series in file: %s" % self.name)
            pass

        elif self.extension == ".sqlite":
            self.db_con = sqlite3.connect(path)

            try:
                info = dict(pd.read_sql_query("SELECT * from measurement_information_table", self.db_con))
            except (DatabaseError, PandasDatabaseError) as e:
                try:
                    info = dict(pd.read_sql_query("SELECT * from measurment_information_table",
                                                  self.db_con))  # Older files can contain wrong table name
                except (DatabaseError, PandasDatabaseError) as e:
                    logger.warning(
                        "DatabaseError occurred when accessing measurement_information_table, file: %s" % self.name)
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
                if 'ridy_version' in info and len(info['ridy_version']) > 0:
                    self.ridy_version = info['ridy_version'][0]

                if 'ridy_version_code' in info and len(info['ridy_version_code']) > 0:
                    self.ridy_version_code = info['ridy_version_code'][0]

                if 'rdy_format_version' in info and len(info['rdy_format_version']) > 0:
                    self.rdy_format_version = info['rdy_format_version'][0]

                if 'rdy_info_name' in info and len(info['rdy_info_name']) > 0:
                    self.rdy_info_name = info['rdy_info_name'][0]

                if 'rdy_info_sex' in info and len(info['rdy_info_sex']) > 0:
                    self.rdy_info_sex = info['rdy_info_sex'][0]

                if 'rdy_info_age' in info and len(info['rdy_info_age']) > 0:
                    self.rdy_info_age = info['rdy_info_age'][0]

                if 'rdy_info_height' in info and len(info['rdy_info_height']) > 0:
                    self.rdy_info_height = info['rdy_info_height'][0]

                if 'rdy_info_weight' in info and len(info['rdy_info_weight']) > 0:
                    self.rdy_info_weight = info['rdy_info_weight'][0]

                if 't0' in info and len(info['t0']) > 0:
                    self.t0 = np.datetime64(info['t0'][0])

                if 'timestamp_when_started' and len(info['timestamp_when_started']) > 0:
                    self.timestamp_when_started = info['timestamp_when_started'][0]

                if 'timestamp_when_stopped' in info and len(info['timestamp_when_stopped']) > 0:
                    self.timestamp_when_stopped = info['timestamp_when_stopped'][0]

                if 'ntp_timestamp' in info and len(info['ntp_timestamp']) > 0:
                    self.ntp_timestamp = info['ntp_timestamp'][0]

                if 'ntp_date_time' in info and len(info['ntp_date_time']) > 0:
                    self.ntp_date_time = np.datetime64(info['ntp_date_time'][0])

            # Measurements
            try:
                acc_df = pd.read_sql_query("SELECT * from acc_measurements_table", self.db_con)
                self.measurements[AccelerationSeries] = AccelerationSeries(rdy_format_version=self.rdy_format_version,
                                                                           **dict(acc_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing acc_measurements_table, file: %s" % self.name)

            try:
                lin_acc_df = pd.read_sql_query("SELECT * from lin_acc_measurements_table", self.db_con)
                self.measurements[LinearAccelerationSeries] = LinearAccelerationSeries(
                    rdy_format_version=self.rdy_format_version,
                    **dict(lin_acc_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing lin_acc_measurements_table, file: %s" % self.name)

            try:
                mag_df = pd.read_sql_query("SELECT * from mag_measurements_table", self.db_con)
                self.measurements[MagnetometerSeries] = MagnetometerSeries(rdy_format_version=self.rdy_format_version,
                                                                           **dict(mag_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing mag_measurements_table, file: %s" % self.name)

            try:
                orient_df = pd.read_sql_query("SELECT * from orient_measurements_table", self.db_con)
                self.measurements[OrientationSeries] = OrientationSeries(rdy_format_version=self.rdy_format_version,
                                                                         **dict(orient_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing orient_measurements_table, file: %s" % self.name)

            try:
                gyro_df = pd.read_sql_query("SELECT * from gyro_measurements_table", self.db_con)
                self.measurements[GyroSeries] = GyroSeries(rdy_format_version=self.rdy_format_version,
                                                           **dict(gyro_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing gyro_measurements_table, file: %s" % self.name)

            try:
                rot_df = pd.read_sql_query("SELECT * from rot_measurements_table", self.db_con)
                self.measurements[RotationSeries] = RotationSeries(rdy_format_version=self.rdy_format_version,
                                                                   **dict(rot_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing rot_measurements_table, file: %s" % self.name)

            try:
                gps_df = pd.read_sql_query("SELECT * from gps_measurements_table", self.db_con)
                self.measurements[GPSSeries] = GPSSeries(rdy_format_version=self.rdy_format_version,
                                                         **dict(gps_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing gps_measurements_table, file: %s" % self.name)

            try:
                pressure_df = pd.read_sql_query("SELECT * from pressure_measurements_table", self.db_con)
                self.measurements[PressureSeries] = PressureSeries(rdy_format_version=self.rdy_format_version,
                                                                   **dict(pressure_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing pressure_measurements_table, file: %s" % self.name)

            try:
                temperature_df = pd.read_sql_query("SELECT * from temperature_measurements_table", self.db_con)
                self.measurements[TemperatureSeries] = TemperatureSeries(rdy_format_version=self.rdy_format_version,
                                                                         **dict(temperature_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing temperature_measurements_table, file: %s" % self.name)

            try:
                humidity_df = pd.read_sql_query("SELECT * from humidity_measurements_table", self.db_con)
                self.measurements[HumiditySeries] = HumiditySeries(rdy_format_version=self.rdy_format_version,
                                                                   **dict(humidity_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing humidity_measurements_table, file: %s" % self.name)

            try:
                light_df = pd.read_sql_query("SELECT * from light_measurements_table", self.db_con)
                self.measurements[LightSeries] = LightSeries(rdy_format_version=self.rdy_format_version,
                                                             **dict(light_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing light_measurements_table, file: %s" % self.name)

            try:
                wz_df = pd.read_sql_query("SELECT * from wz_measurements_table", self.db_con)
                self.measurements[WzSeries] = WzSeries(rdy_format_version=self.rdy_format_version,
                                                       **dict(wz_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error("DatabaseError occurred when accessing wz_measurements_table, file: %s" % self.name)

            try:
                subjective_comfort_df = pd.read_sql_query("SELECT * from subjective_comfort_measurements_table",
                                                          self.db_con)
                self.measurements[SubjectiveComfortSeries] = SubjectiveComfortSeries(
                    rdy_format_version=self.rdy_format_version,
                    **dict(subjective_comfort_df))
            except (DatabaseError, PandasDatabaseError) as e:
                logger.error(
                    "DatabaseError occurred when accessing subjective_comfort_measurements_table, file: %s" % self.name)

            self.db_con.close()
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
