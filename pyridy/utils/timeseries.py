from abc import ABC
from typing import Union

import numpy as np
import pandas as pd


class TimeSeries(ABC):
    def __init__(self, time: Union[list, np.ndarray] = None):
        self.time: np.ndarray = np.array(time)

    def to_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.__dict__)


class AccelerationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 acc_x: Union[list, np.ndarray],
                 acc_y: Union[list, np.ndarray],
                 acc_z: Union[list, np.ndarray]):
        super(AccelerationSeries, self).__init__(time=time)
        self.acc_x: np.ndarray = np.array(acc_x)
        self.acc_y: np.ndarray = np.array(acc_y)
        self.acc_z: np.ndarray = np.array(acc_z)


class LinearAccelerationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 lin_acc_x: Union[list, np.ndarray],
                 lin_acc_y: Union[list, np.ndarray],
                 lin_acc_z: Union[list, np.ndarray]):
        super(LinearAccelerationSeries, self).__init__(time=time)
        self.lin_acc_x: np.ndarray = np.array(lin_acc_x)
        self.lin_acc_y: np.ndarray = np.array(lin_acc_y)
        self.lin_acc_z: np.ndarray = np.array(lin_acc_z)


class MagnetometerSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 mag_x: Union[list, np.ndarray],
                 mag_y: Union[list, np.ndarray],
                 mag_z: Union[list, np.ndarray]):
        super(MagnetometerSeries, self).__init__(time=time)
        self.mag_x: np.ndarray = np.array(mag_x)
        self.mag_y: np.ndarray = np.array(mag_y)
        self.mag_z: np.ndarray = np.array(mag_z)


class OrientationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 azimuth: Union[list, np.ndarray],
                 pitch: Union[list, np.ndarray],
                 roll: Union[list, np.ndarray]):
        super(OrientationSeries, self).__init__(time=time)
        self.azimuth: np.ndarray = np.array(azimuth)
        self.pitch: np.ndarray = np.array(pitch)
        self.roll: np.ndarray = np.array(roll)


class GyroSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 w_x: Union[list, np.ndarray],
                 w_y: Union[list, np.ndarray],
                 w_z: Union[list, np.ndarray]):
        super(GyroSeries, self).__init__(time=time)
        self.w_x: np.ndarray = np.array(w_x)
        self.w_y: np.ndarray = np.array(w_y)
        self.w_z: np.ndarray = np.array(w_z)


class RotationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 rot_x: Union[list, np.ndarray],
                 rot_y: Union[list, np.ndarray],
                 rot_z: Union[list, np.ndarray],
                 cos_phi: Union[list, np.ndarray],
                 heading_acc: Union[list, np.ndarray]):
        super(RotationSeries, self).__init__(time=time)
        self.rot_x: np.ndarray = np.array(rot_x)
        self.rot_y: np.ndarray = np.array(rot_y)
        self.rot_z: np.ndarray = np.array(rot_z)
        self.cos_phi: np.ndarray = np.array(cos_phi)
        self.heading_acc: np.ndarray = np.array(heading_acc)


class GPSSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 lat: Union[list, np.ndarray],
                 lon: Union[list, np.ndarray],
                 altitude: Union[list, np.ndarray],
                 bearing: Union[list, np.ndarray],
                 speed: Union[list, np.ndarray],
                 hor_acc: Union[list, np.ndarray],
                 ver_acc: Union[list, np.ndarray],
                 bear_acc: Union[list, np.ndarray],
                 speed_acc: Union[list, np.ndarray],
                 utc_time: Union[list, np.ndarray]):
        super(GPSSeries, self).__init__(time=time)
        self.lat: np.ndarray = np.array(lat)
        self.lon: np.ndarray = np.array(lon)
        self.altitude: np.ndarray = np.array(altitude)
        self.bearing: np.ndarray = np.array(bearing)
        self.speed: np.ndarray = np.array(speed)
        self.hor_acc: np.ndarray = np.array(hor_acc)
        self.ver_acc: np.ndarray = np.array(ver_acc)
        self.bear_acc: np.ndarray = np.array(bear_acc)
        self.speed_acc: np.ndarray = np.array(speed_acc)
        self.utc_time: np.ndarray = np.array(utc_time)


class PressureSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 pressure: Union[list, np.ndarray]):
        super(PressureSeries, self).__init__(time=time)
        self.pressure: np.ndarray = np.array(pressure)


class TemperatureSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 temperature: Union[list, np.ndarray]):
        super(TemperatureSeries, self).__init__(time=time)
        self.temperature: np.ndarray = np.array(temperature)


class HumiditySeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 humidity: Union[list, np.ndarray]):
        super(HumiditySeries, self).__init__(time=time)
        self.humidity: np.ndarray = np.array(humidity)


class LightSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 light: Union[list, np.ndarray]):
        super(LightSeries, self).__init__(time=time)
        self.light: np.ndarray = np.array(light)


class WzSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 wz_x: Union[list, np.ndarray],
                 wz_y: Union[list, np.ndarray],
                 wz_z: Union[list, np.ndarray]):
        super(WzSeries, self).__init__(time=time)
        self.wz_x: np.ndarray = np.array(wz_x)
        self.wz_y: np.ndarray = np.array(wz_y)
        self.wz_z: np.ndarray = np.array(wz_z)


class SubjectiveComfortSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray],
                 comfort: Union[list, np.ndarray]):
        super(SubjectiveComfortSeries, self).__init__(time=time)
        self.comfort: np.ndarray = np.array(comfort)
