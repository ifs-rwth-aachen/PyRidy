import json
import os
import sqlite3
from sqlite3 import Connection
from typing import Optional, List

import pandas as pd
from pandas.io.sql import DatabaseError

from pyridy.utils import Sensor, AccelerationSeries, LinearAccelerationSeries, MagnetometerSeries, OrientationSeries, \
    GyroSeries, RotationSeries, GPSSeries, PressureSeries, HumiditySeries, TemperatureSeries, WzSeries, LightSeries, \
    SubjectiveComfortSeries
from pyridy.utils.device import Device


class RDYFile:
    def __init__(self, path: str = None):
        self.path = path
        self.filename: Optional[str] = None
        self.extension: Optional[str] = None

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
        self.acc_series: Optional[AccelerationSeries] = None
        self.lin_acc_series: Optional[LinearAccelerationSeries] = None
        self.mag_series: Optional[MagnetometerSeries] = None
        self.orient_series: Optional[OrientationSeries] = None
        self.gyro_series: Optional[GyroSeries] = None
        self.rot_series: Optional[RotationSeries] = None
        self.gps_series: Optional[GPSSeries] = None
        self.pressure_series: Optional[PressureSeries] = None
        self.temperature_series: Optional[TemperatureSeries] = None
        self.humidity_series: Optional[HumiditySeries] = None
        self.light_series: Optional[LightSeries] = None
        self.wz_series: Optional[WzSeries] = None
        self.subjective_comfort_series: Optional[SubjectiveComfortSeries] = None

        if self.path:
            self.load_file(self.path)
        pass

    def load_file(self, path: str):
        _, self.extension = os.path.splitext(path)
        _, self.filename = os.path.split(path)

        if self.extension == ".rdy":
            with open(path, 'r') as file:
                rdy = json.load(file)

            self.rdy_format_version = rdy['RDY_Format_Version']
            self.rdy_info_name = rdy['RDY_Info_Name']
            self.rdy_info_sex = rdy['RDY_Info_Sex']
            self.rdy_info_age = rdy['RDY_Info_Age']
            self.rdy_info_height = rdy['RDY_Info_Height']
            self.rdy_info_weight = rdy['RDY_Info_Weight']

            self.t0 = rdy['t0']
            self.timestamp_when_started = rdy['timestamp_when_started']
            self.timestamp_when_stopped = rdy['timestamp_when_stopped']

            self.device = Device(**rdy['device_info'])

            for sensor in rdy['sensors']:
                self.sensors.append(Sensor(**sensor))

            self.acc_series = AccelerationSeries(**rdy['acc_series'])
            self.lin_acc_series = LinearAccelerationSeries(**rdy['lin_acc_series'])
            self.mag_series = MagnetometerSeries(**rdy['mag_series'])
            self.orient_series = OrientationSeries(**rdy['orient_series'])
            self.gyro_series = GyroSeries(**rdy['gyro_series'])
            self.rot_series = RotationSeries(**rdy['rot_series'])
            self.gps_series = GPSSeries(**rdy['gps_series'])
            self.pressure_series = PressureSeries(**rdy['pressure_series'])
            self.temperature_series = TemperatureSeries(**rdy['temperature_series'])
            self.humidity_series = HumiditySeries(**rdy['humidity_series'])
            self.light_series = LightSeries(**rdy['light_series'])
            self.wz_series = WzSeries(**rdy['wz_series'])
            self.subjective_comfort_series = SubjectiveComfortSeries(**rdy['subjective_comfort_series'])
            pass

        elif self.extension == ".sqlite":
            self.db_con = sqlite3.connect(path)

            try:
                info = dict(pd.read_sql_query("SELECT * from measurement_information_table", self.db_con))
            except DatabaseError:
                info = dict(pd.read_sql_query("SELECT * from measurment_information_table", self.db_con))  # Older files can contain wrong table name

            sensor_df = pd.read_sql_query("SELECT * from sensor_descriptions_table", self.db_con)
            for _, row in sensor_df.iterrows():
                self.sensors.append(Sensor(**dict(row)))
                pass

            self.device = Device(**dict(pd.read_sql_query("SELECT * from device_information_table", self.db_con)))

            # Info
            self.rdy_format_version = info['rdy_format_version'][0]
            self.rdy_info_name = info['rdy_info_name'][0]
            self.rdy_info_sex = info['rdy_info_sex'][0]
            self.rdy_info_age = info['rdy_info_age'][0]
            self.rdy_info_height = info['rdy_info_height'][0]
            self.rdy_info_weight = info['rdy_info_weight'][0]

            self.t0 = info['t0'][0]
            self.timestamp_when_started = info['timestamp_when_started'][0]
            self.timestamp_when_stopped = info['timestamp_when_stopped'][0]

            # Measurements
            self.acc_series = AccelerationSeries(**dict(pd.read_sql_query("SELECT * from acc_measurements_table", self.db_con)))
            self.lin_acc_series = LinearAccelerationSeries(**dict(pd.read_sql_query("SELECT * from lin_acc_measurements_table", self.db_con)))
            self.mag_series = MagnetometerSeries(**dict(pd.read_sql_query("SELECT * from mag_measurements_table", self.db_con)))
            self.orient_series = OrientationSeries(**dict(pd.read_sql_query("SELECT * from orient_measurements_table", self.db_con)))
            self.gyro_series = GyroSeries(**dict(pd.read_sql_query("SELECT * from gyro_measurements_table", self.db_con)))
            self.rot_series = RotationSeries(**dict(pd.read_sql_query("SELECT * from rot_measurements_table", self.db_con)))
            self.gps_series = GPSSeries(**dict(pd.read_sql_query("SELECT * from gps_measurements_table", self.db_con)))
            self.pressure_series = PressureSeries(**dict(pd.read_sql_query("SELECT * from pressure_measurements_table", self.db_con)))
            self.temperature_series = TemperatureSeries(**dict(pd.read_sql_query("SELECT * from temperature_measurements_table", self.db_con)))
            self.humidity_series = HumiditySeries(**dict(pd.read_sql_query("SELECT * from humidity_measurements_table", self.db_con)))
            self.light_series = LightSeries(**dict(pd.read_sql_query("SELECT * from light_measurements_table", self.db_con)))
            self.wz_series = WzSeries(**dict(pd.read_sql_query("SELECT * from wz_measurements_table", self.db_con)))
            self.subjective_comfort_series = SubjectiveComfortSeries(**dict(pd.read_sql_query("SELECT * from subjective_comfort_measurements_table", self.db_con)))
            pass
        else:
            raise ValueError("File extension %s is not supported" % self.extension)

