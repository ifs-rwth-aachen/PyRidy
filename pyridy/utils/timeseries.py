from abc import ABC
from typing import Union

import numpy as np
import pandas as pd


class TimeSeries(ABC):
    def __init__(self, time: Union[list, np.ndarray] = None):
        self.time: np.ndarray = np.array(time)

    def to_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.__dict__)

    def __repr__(self):
        duration = (self.time[-1] - self.time[0]) * 1e-9 if not np.array_equal(self.time, np.array(None)) and len(self.time) > 0 else 0
        sample_rate = len(self.time) / duration if not np.array_equal(self.time, np.array(None)) and duration > 0 else 0.0
        return "Length: %d, Duration: %.3f s, Mean Samplerate: %.3f Hz" % (len(self.time), duration, sample_rate)


class AccelerationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 acc_x: Union[list, np.ndarray] = None,
                 acc_y: Union[list, np.ndarray] = None,
                 acc_z: Union[list, np.ndarray] = None):
        super(AccelerationSeries, self).__init__(time=time)
        self.acc_x: np.ndarray = np.array(acc_x)
        self.acc_y: np.ndarray = np.array(acc_y)
        self.acc_z: np.ndarray = np.array(acc_z)


class LinearAccelerationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 lin_acc_x: Union[list, np.ndarray] = None,
                 lin_acc_y: Union[list, np.ndarray] = None,
                 lin_acc_z: Union[list, np.ndarray] = None):
        super(LinearAccelerationSeries, self).__init__(time=time)
        self.lin_acc_x: np.ndarray = np.array(lin_acc_x)
        self.lin_acc_y: np.ndarray = np.array(lin_acc_y)
        self.lin_acc_z: np.ndarray = np.array(lin_acc_z)


class MagnetometerSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 mag_x: Union[list, np.ndarray] = None,
                 mag_y: Union[list, np.ndarray] = None,
                 mag_z: Union[list, np.ndarray] = None):
        super(MagnetometerSeries, self).__init__(time=time)
        self.mag_x: np.ndarray = np.array(mag_x)
        self.mag_y: np.ndarray = np.array(mag_y)
        self.mag_z: np.ndarray = np.array(mag_z)


class OrientationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 azimuth: Union[list, np.ndarray] = None,
                 pitch: Union[list, np.ndarray] = None,
                 roll: Union[list, np.ndarray] = None):
        super(OrientationSeries, self).__init__(time=time)
        self.azimuth: np.ndarray = np.array(azimuth)
        self.pitch: np.ndarray = np.array(pitch)
        self.roll: np.ndarray = np.array(roll)


class GyroSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 w_x: Union[list, np.ndarray] = None,
                 w_y: Union[list, np.ndarray] = None,
                 w_z: Union[list, np.ndarray] = None):
        super(GyroSeries, self).__init__(time=time)
        self.w_x: np.ndarray = np.array(w_x)
        self.w_y: np.ndarray = np.array(w_y)
        self.w_z: np.ndarray = np.array(w_z)


class RotationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 rot_x: Union[list, np.ndarray] = None,
                 rot_y: Union[list, np.ndarray] = None,
                 rot_z: Union[list, np.ndarray] = None,
                 cos_phi: Union[list, np.ndarray] = None,
                 heading_acc: Union[list, np.ndarray] = None):
        super(RotationSeries, self).__init__(time=time)
        self.rot_x: np.ndarray = np.array(rot_x)
        self.rot_y: np.ndarray = np.array(rot_y)
        self.rot_z: np.ndarray = np.array(rot_z)
        self.cos_phi: np.ndarray = np.array(cos_phi)
        self.heading_acc: np.ndarray = np.array(heading_acc)


class GPSSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 lat: Union[list, np.ndarray] = None,
                 lon: Union[list, np.ndarray] = None,
                 altitude: Union[list, np.ndarray] = None,
                 bearing: Union[list, np.ndarray] = None,
                 speed: Union[list, np.ndarray] = None,
                 hor_acc: Union[list, np.ndarray] = None,
                 ver_acc: Union[list, np.ndarray] = None,
                 bear_acc: Union[list, np.ndarray] = None,
                 speed_acc: Union[list, np.ndarray] = None,
                 utc_time: Union[list, np.ndarray] = None):
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
    def __init__(self, time: Union[list, np.ndarray] = None,
                 pressure: Union[list, np.ndarray] = None):
        super(PressureSeries, self).__init__(time=time)
        self.pressure: np.ndarray = np.array(pressure)


class TemperatureSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 temperature: Union[list, np.ndarray] = None):
        super(TemperatureSeries, self).__init__(time=time)
        self.temperature: np.ndarray = np.array(temperature)


class HumiditySeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 humidity: Union[list, np.ndarray] = None):
        super(HumiditySeries, self).__init__(time=time)
        self.humidity: np.ndarray = np.array(humidity)


class LightSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 light: Union[list, np.ndarray] = None):
        super(LightSeries, self).__init__(time=time)
        self.light: np.ndarray = np.array(light)


class WzSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 wz_x: Union[list, np.ndarray] = None,
                 wz_y: Union[list, np.ndarray] = None,
                 wz_z: Union[list, np.ndarray] = None):
        super(WzSeries, self).__init__(time=time)
        self.wz_x: np.ndarray = np.array(wz_x)
        self.wz_y: np.ndarray = np.array(wz_y)
        self.wz_z: np.ndarray = np.array(wz_z)


class SubjectiveComfortSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 comfort: Union[list, np.ndarray] = None):
        super(SubjectiveComfortSeries, self).__init__(time=time)
        self.comfort: np.ndarray = np.array(comfort)
