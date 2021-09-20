import datetime
import logging
from abc import ABC
from typing import Union, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TimeSeries(ABC):
    def __init__(self, time: Union[list, np.ndarray] = None, rdy_format_version: float = None):
        self.rdy_format_version = rdy_format_version

        if time is None:
            time = []

        self._time: np.ndarray = np.array(time)  # Original unadjusted timestamps
        self._timedelta: np.ndarray = np.diff(self._time)

        if self.rdy_format_version and self.rdy_format_version <= 1.2:
            self._time = (self._time * 1e9).astype(np.int64)

        self.time = self._time.copy()

    def __len__(self):
        if np.array_equal(self.time, np.array(None)):
            return 0
        else:
            return len(self.time)

    def __repr__(self):
        return "Length: %d, Duration: %s, Mean sample rate: %.3f Hz" % (len(self._time),
                                                                        str(datetime.timedelta(seconds=self.get_duration())),
                                                                        self.get_sample_rate())

    def to_df(self) -> pd.DataFrame:
        d = self.__dict__.copy()
        d.pop("rdy_format_version")
        return pd.DataFrame(dict([(k, pd.Series(v)) for k, v in d.items()])).set_index("time")

    def get_sub_series_names(self) -> list:
        """

        Returns
        -------
            List of names of sub series (e.g., acc_x, acc_y, acc_z)
        """
        d = self.__dict__.copy()

        for k in ["rdy_format_version", "time", "_time", "_timedelta"]:
            d.pop(k)

        return list(d.keys())

    def get_duration(self):
        """

        Returns the duration in seconds
        -------

        """
        if not np.array_equal(self._time, np.array(None)) and len(self._time) > 0:
            if type(self._time[0]) == np.int64:
                duration = (self._time[-1] - self._time[0]) * 1e-9
            else:
                duration = (self._time[-1] - self._time[0])
        else:
            duration = 0

        return duration

    def get_sample_rate(self):
        if not np.array_equal(self._time, np.array(None)) and self.get_duration() > 0:
            mean_timedelta = self._timedelta.mean()
            sample_rate = 1 / (mean_timedelta * 1e-9) if mean_timedelta != 0.0 else 0.0
        else:
            sample_rate = 0.0

        return sample_rate

    def is_empty(self):
        if len(self) == 0:
            return True
        else:
            return False

    def synchronize(self, method: str, sync_timestamp: Union[int, np.int64] = 0,
                    sync_time: np.datetime64 = np.datetime64(0, "s"), timedelta_unit='timedelta64[ns]'):
        if sync_timestamp and type(sync_timestamp) not in [int, np.int64]:
            raise ValueError(
                "sync_timestamp must be integer for method %s, not %s" % (method, str(type(sync_timestamp))))

        if type(sync_time) != np.datetime64:
            raise ValueError(
                "sync_time must be np.datetime64 for method %s, not %s" % (method, str(type(sync_timestamp))))

        if not np.array_equal(self._time, np.array(None)) and len(self._time) > 0:
            if method == "timestamp":
                if self._time[0] == 0:
                    logger.warning("Timeseries already starts at 0, timestamp syncing not appropriate")
                else:
                    if sync_timestamp:
                        self.time = (self._time - sync_timestamp).astype(timedelta_unit)
                    else:
                        logger.warning("sync_timestamp is None, using first timestamp for timeseries syncing")
                        self.time = (self._time - self._time[0]).astype(timedelta_unit)

            elif method == "device_time":
                if self._time[0] == 0:
                    logger.warning("Timeseries already starts at 0, timestamp syncing not appropriate")
                    self.time = self._time.astype(timedelta_unit) + sync_time
                else:
                    self.time = (self._time - sync_timestamp).astype(timedelta_unit) + sync_time
            elif method == "gps_time":
                if self._time[0] == 0:
                    logger.warning("Timeseries already starts at 0, cant sync to due to lack of proper timestamp")
                else:
                    self.time = (self._time - sync_timestamp).astype(timedelta_unit) + sync_time
                pass
            else:
                raise ValueError("Method %s not supported" % method)
        else:
            logger.warning("Trying to synchronize timestamps on empty %s" % self.__class__.__name__)


class AccelerationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 acc_x: Union[list, np.ndarray] = None,
                 acc_y: Union[list, np.ndarray] = None,
                 acc_z: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None):
        super(AccelerationSeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if acc_x is None:
            acc_x = []

        if acc_y is None:
            acc_y = []

        if acc_z is None:
            acc_z = []

        self.acc_x: np.ndarray = np.array(acc_x)
        self.acc_y: np.ndarray = np.array(acc_y)
        self.acc_z: np.ndarray = np.array(acc_z)


class LinearAccelerationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 lin_acc_x: Union[list, np.ndarray] = None,
                 lin_acc_y: Union[list, np.ndarray] = None,
                 lin_acc_z: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None, **kwargs):
        super(LinearAccelerationSeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if lin_acc_x is None:
            lin_acc_x = []

        if lin_acc_y is None:
            lin_acc_y = []

        if lin_acc_z is None:
            lin_acc_z = []

        if "acc_x" in kwargs and kwargs["acc_x"] is None:
            kwargs["acc_x"] = []

        if "acc_y" in kwargs and kwargs["acc_y"] is None:
            kwargs["acc_y"] = []

        if "acc_z" in kwargs and kwargs["acc_z"] is None:
            kwargs["acc_z"] = []

        self.lin_acc_x: np.ndarray = np.array(kwargs["acc_x"]) if "acc_x" in kwargs else np.array(lin_acc_x)
        self.lin_acc_y: np.ndarray = np.array(kwargs["acc_y"]) if "acc_y" in kwargs else np.array(lin_acc_y)
        self.lin_acc_z: np.ndarray = np.array(kwargs["acc_z"]) if "acc_z" in kwargs else np.array(lin_acc_z)


class MagnetometerSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 mag_x: Union[list, np.ndarray] = None,
                 mag_y: Union[list, np.ndarray] = None,
                 mag_z: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None):
        super(MagnetometerSeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if mag_x is None:
            mag_x = []

        if mag_y is None:
            mag_y = []

        if mag_z is None:
            mag_z = []

        self.mag_x: np.ndarray = np.array(mag_x)
        self.mag_y: np.ndarray = np.array(mag_y)
        self.mag_z: np.ndarray = np.array(mag_z)


class OrientationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 azimuth: Union[list, np.ndarray] = None,
                 pitch: Union[list, np.ndarray] = None,
                 roll: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None):
        super(OrientationSeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if azimuth is None:
            azimuth = []

        if pitch is None:
            pitch = []

        if roll is None:
            roll = []

        self.azimuth: np.ndarray = np.array(azimuth)
        self.pitch: np.ndarray = np.array(pitch)
        self.roll: np.ndarray = np.array(roll)


class GyroSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 w_x: Union[list, np.ndarray] = None,
                 w_y: Union[list, np.ndarray] = None,
                 w_z: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None):
        super(GyroSeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if w_x is None:
            w_x = []

        if w_y is None:
            w_y = []

        if w_z is None:
            w_z = []

        self.w_x: np.ndarray = np.array(w_x)
        self.w_y: np.ndarray = np.array(w_y)
        self.w_z: np.ndarray = np.array(w_z)


class RotationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 rot_x: Union[list, np.ndarray] = None,
                 rot_y: Union[list, np.ndarray] = None,
                 rot_z: Union[list, np.ndarray] = None,
                 cos_phi: Union[list, np.ndarray] = None,
                 heading_acc: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None):
        super(RotationSeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if rot_x is None:
            rot_x = []

        if rot_y is None:
            rot_y = []

        if rot_z is None:
            rot_z = []

        if cos_phi is None:
            cos_phi = []

        if heading_acc is None:
            heading_acc = []

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
                 utc_time: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None):
        super(GPSSeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if lat is None:
            lat = []

        if lon is None:
            lon = []

        if altitude is None:
            altitude = []

        if bearing is None:
            bearing = []

        if speed is None:
            speed = []

        if hor_acc is None:
            hor_acc = []

        if ver_acc is None:
            ver_acc = []

        if bear_acc is None:
            bear_acc = []

        if speed_acc is None:
            speed_acc = []

        if utc_time is None:
            utc_time = []

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

    def to_ipyleaflef(self) -> List[list]:
        """

        :return: Returns the lat/lon coordinates as list of list for easy visualization using ipyleaflet
        """
        if np.array_equal(self.lat, np.array(None)) and np.array_equal(self.lat, np.array(None)):
            logger.warning("Coordinates are empty")
            return [[]]
        elif len(self.lat) == 0 and len(self.lon) == 0:
            logger.warning("Coordinates are empty")
            return [[]]
        else:
            return [[lat, lon] for lat, lon in zip(self.lat, self.lon)]


class PressureSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 pressure: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None):
        super(PressureSeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if pressure is None:
            pressure = []

        self.pressure: np.ndarray = np.array(pressure)


class TemperatureSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 temperature: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None):
        super(TemperatureSeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if temperature is None:
            temperature = []

        self.temperature: np.ndarray = np.array(temperature)


class HumiditySeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 humidity: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None):
        super(HumiditySeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if humidity is None:
            humidity = []

        self.humidity: np.ndarray = np.array(humidity)


class LightSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 light: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None):
        super(LightSeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if light is None:
            light = []

        self.light: np.ndarray = np.array(light)


class WzSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 wz_x: Union[list, np.ndarray] = None,
                 wz_y: Union[list, np.ndarray] = None,
                 wz_z: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None):
        super(WzSeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if wz_x is None:
            wz_x = []

        if wz_y is None:
            wz_y = []

        if wz_z is None:
            wz_z = []

        self.wz_x: np.ndarray = np.array(wz_x)
        self.wz_y: np.ndarray = np.array(wz_y)
        self.wz_z: np.ndarray = np.array(wz_z)


class SubjectiveComfortSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 comfort: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None):
        super(SubjectiveComfortSeries, self).__init__(time=time, rdy_format_version=rdy_format_version)

        if comfort is None:
            comfort = []

        self.comfort: np.ndarray = np.array(comfort)
