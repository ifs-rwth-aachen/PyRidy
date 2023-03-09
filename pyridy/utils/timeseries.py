import copy
import datetime
import logging
from abc import ABC
from typing import Union, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TimeSeries(ABC):
    def __init__(self, **kwargs):
        """ Abstract Baseclass representing TimeSeries like measurements

        Parameters
        ----------
        kwargs
        """
        self.rdy_format_version = kwargs["rdy_format_version"]
        self.filename = kwargs['filename']
        kwargs.pop("rdy_format_version")
        kwargs.pop('filename')
        kwargs.pop("__class__")

        if 'time' not in kwargs:
            logger.warning('TimeSeries has no time!')

        for k, v in kwargs.items():  # Replaces None values arguments with empty lists
            if v is None and k != "rdy_format_version":
                kwargs[k] = np.array([])
            else:
                if type(v) == np.ndarray:
                    kwargs[k] = v
                else:
                    kwargs[k] = np.array(v)

            if 'time' in kwargs and kwargs['time'] is not None and v is not None:
                if k != "time" and 'time' in kwargs and len(kwargs["time"]) > 0 and len(v) == 0:
                    kwargs[k] = np.zeros(len(kwargs["time"]))

        self.__dict__.update(kwargs)

        self._time: np.ndarray = np.array(self.time)  # Original unadjusted timestamps
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
        return "(%s), Length: %d, Duration: %s, Mean sample rate: %.3f Hz" % (self.filename,
                                                                              len(self._time),
                                                                              str(datetime.timedelta(
                                                                                  seconds=self.get_duration())),
                                                                              self.get_sample_rate())

    def cut(self, start: float = 0, end: float = 0, inplace: bool = True):
        """
        Cuts off seconds after start and before end

        Parameters
        ----------
        start: float
            Seconds to cutoff after start
        end: float
            Seconds to cutoff before end
        inplace: bool, Default: True
            If True cuts data inplace, otherwise returns it

        Returns
        ----------
        time_series_copy: TimeSeries
            A copy of the timeseries without the interval
        """
        if (start + end) >= self.get_duration():
            raise ValueError(f'Trying to cut off more seconds than duration of {self.__class__.__name__}')

        if len(self.time) > 0 and self.time[0] != 0:
            if inplace:
                d = self.__dict__.copy()

                for key in ["filename", "rdy_format_version"]:
                    d.pop(key)

                t = d["time"]
                t_sec = (t - t[0]) / np.timedelta64(1, "s")

                idxs = np.where(np.logical_and(t_sec >= start, t_sec <= (t_sec[-1] - end)))

                for k, v in d.items():
                    if len(t) == len(v):
                        self.__setattr__(k, v[idxs])

                self._timedelta: np.ndarray = np.diff(self._time)
            else:
                time_series_copy: TimeSeries = copy.deepcopy(self)
                d = time_series_copy.__dict__.copy()

                for key in ["filename", "rdy_format_version"]:
                    d.pop(key)

                t = d["time"]
                t_sec = (t - t[0]) / np.timedelta64(1, "s")

                idxs = np.where(np.logical_and(t_sec >= start, t_sec <= (t_sec[-1] - end)))

                for k, v in d.items():
                    if len(t) == len(v):
                        time_series_copy.__setattr__(k, v[idxs])

                time_series_copy._timedelta: np.ndarray = np.diff(time_series_copy._time)

                return time_series_copy
        else:
            logger.debug("(%s) Cannot cut %s if timeseries is empty or series already starts at 0" %
                         (self.filename, self.__class__.__name__))

    def trim_ends(self, timestamp_when_started: int, timestamp_when_stopped: int):
        """
        Trims measurement values saved before/after the measurement was started/stopped

        Parameters
        ----------
        timestamp_when_started: int
            Timestamp when the measurement was started (i.e., when the recording button was pressed)
        timestamp_when_stopped: int
            Timestamp when the measurement was stopped (i.e., when the (stop) recording button was pressed)
        """
        if timestamp_when_started and timestamp_when_stopped:
            if timestamp_when_started >= timestamp_when_stopped:
                raise ValueError("(%s) timestamp_when_stopped must be greater than timestamp_when_started" %
                                 self.filename)

            if len(self.time) > 0 and self.time[0] != 0:
                d = self.__dict__.copy()

                for key in ["filename", "rdy_format_version"]:
                    d.pop(key)

                t = d["time"]
                idxs = np.where(np.logical_and(t >= timestamp_when_started, t <= timestamp_when_stopped))
                for k, v in d.items():
                    if len(t) == len(v):
                        self.__setattr__(k, v[idxs])

                self._timedelta: np.ndarray = np.diff(self._time)
            else:
                logger.debug("(%s) Cannot cutoff %s if timeseries is empty or series already starts at 0" %
                             (self.filename, self.__class__.__name__))
        else:
            logger.debug("(%s) Cannot cutoff %s, if timestamp_when_started " % (self.filename, self.__class__.__name__)
                         + "and/or timestamp_when_stopped are None")

        pass

    def to_df(self) -> pd.DataFrame:
        """
        Converts the Series to a Pandas DataFrame

        Returns
        -------
        pd.DataFrame : Pandas DataFrame
            Dataframe containing series measurements
        """
        d = self.__dict__.copy()
        d.pop("rdy_format_version")
        d.pop("filename")
        d.pop("_timedelta")
        return pd.DataFrame(dict([(k, pd.Series(v)) for k, v in d.items()])).set_index("time")

    def get_sub_series_names(self) -> list:
        """
        Returns names of subseries (e.g., acc_x, acc_y, acc_z)

        Returns
        -------
        names :  list
            List of subseries' names
        """
        d = self.__dict__.copy()

        for k in ["rdy_format_version", "time", "_time", "_timedelta", "filename"]:
            d.pop(k)

        return list(d.keys())

    def get_duration(self) -> float:
        """
        Calculates the duration of the TimeSeries in seconds

        Returns
        -------
        duration: float
            Duration of the TimeSeries
        """
        if not np.array_equal(self._time, np.array(None)) and len(self._time) > 0:
            if type(self._time[0]) == np.int64:
                duration: float = (self._time[-1] - self._time[0]) * 1e-9
            else:
                duration: float = (self._time[-1] - self._time[0])
        else:
            duration: float = 0.0

        return duration

    def get_sample_rate(self) -> float:
        """
        Calculates the sample rate of the TimeSeries

        Returns
        -------
        sample_rate: float
            Sample rate of the TimeSeries
        """
        if not np.array_equal(self._time, np.array(None)) and self.get_duration() > 0:
            mean_timedelta = self._timedelta.mean()
            sample_rate = 1 / (mean_timedelta * 1e-9) if mean_timedelta != 0.0 else 0.0
        else:
            sample_rate = 0.0

        return sample_rate

    def is_empty(self) -> bool:
        """
        Checks whether the TimeSeries contains any values

        Returns
        -------
        empty : bool
            True if Timeseries is empty else False
        """
        if len(self) == 0:
            return True
        else:
            return False

    def synchronize(self, method: str, sync_timestamp: Union[int, np.int64] = 0,
                    sync_time: np.datetime64 = np.datetime64(0, "s"), timedelta_unit='timedelta64[ns]'):
        """

        Parameters
        ----------
        method: str
            Sync method, must be either "timestamp", "seconds", "device_time", "gps_time" or "ntp_time".
        sync_timestamp: int
            Timestamp used to synchronize timeseries
        sync_time: np.datetime64
            Sync to be used for synchronizing
        timedelta_unit: str
            Timedelta unit

        Raises
        -------
        ValueError
            Raised if method is not supported or sync_time's type is not compatible with given method
        """
        if sync_timestamp and type(sync_timestamp) not in [int, np.int64]:
            raise ValueError(
                "(%s) sync_timestamp must be integer for method %s, not %s" % (self.filename,
                                                                               method,
                                                                               str(type(sync_timestamp))))

        if type(sync_time) != np.datetime64:
            raise ValueError(
                "(%s) sync_time must be np.datetime64 for method %s, not %s" % (self.filename,
                                                                                method,
                                                                                str(type(sync_timestamp))))

        if not np.array_equal(self._time, np.array(None)) and len(self._time) > 0:
            if method == "timestamp":
                if self._time[0] == 0:
                    logger.debug("(%s) %s already starts at 0, cant sync with t0" % (self.filename,
                                                                                     self.__class__.__name__))
                    self.time = self._time.astype(timedelta_unit)
                else:
                    if sync_timestamp:
                        self.time = (self._time - sync_timestamp).astype(timedelta_unit)
                    else:
                        logger.debug("(%s) sync_timestamp is None, using first timestamp syncing" % self.filename)
                        self.time = (self._time - self._time[0]).astype(timedelta_unit)
            elif method == "seconds":
                if self._time[0] == 0:
                    logger.debug("(%s) %s already starts at 0, cant sync with t0, only converting to seconds"
                                 % (self.filename, self.__class__.__name__))
                    self.time = self._time.astype(timedelta_unit) / np.timedelta64(1, "s")
                else:
                    if sync_timestamp:
                        self.time = (self._time - sync_timestamp).astype(timedelta_unit) / np.timedelta64(1, "s")
                    else:
                        logger.debug("(%s) sync_timestamp is None, using first timestamp syncing" % self.filename)
                        self.time = (self._time - self._time[0]).astype(timedelta_unit) / np.timedelta64(1, "s")
            elif method == "device_time":
                if self._time[0] == 0:
                    logger.debug("(%s) %s already starts at 0, timestamp syncing not appropriate"
                                 % (self.filename, self.__class__.__name__))

                    self.time = self._time.astype(timedelta_unit) + sync_time
                else:
                    self.time = (self._time - sync_timestamp).astype(timedelta_unit) + sync_time
            elif method == "gps_time" or method == "ntp_time":
                if self._time[0] == 0:
                    logger.debug("(%s) %s already starts at 0, cant sync to due to lack of proper timestamp"
                                 % (self.filename, self.__class__.__name__))
                else:
                    self.time = (self._time - sync_timestamp).astype(timedelta_unit) + sync_time
                pass
            else:
                raise ValueError("(%s) Method %s not supported" % (self.filename, method))
        else:
            logger.debug("(%s) Trying to synchronize timestamps on empty %s" % (self.filename,
                                                                                self.__class__.__name__))


class AccelerationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 acc_x: Union[list, np.ndarray] = None,
                 acc_y: Union[list, np.ndarray] = None,
                 acc_z: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing acceleration values
        See https://developer.android.com/guide/topics/sensors/sensors_overview for more information
        on Android sensors

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series' timestamps.
        acc_x: Union [list, np.ndarray]
            Acceleration according to x-axis.
        acc_y: Union [list, np.ndarray]
            Acceleration according to y-axis.
        acc_z: Union [list, np.ndarray]
            Acceleration according to z-axis.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(AccelerationSeries, self).__init__(**args)


class AccelerationUncalibratedSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 acc_uncal_x: Union[list, np.ndarray] = None,
                 acc_uncal_y: Union[list, np.ndarray] = None,
                 acc_uncal_z: Union[list, np.ndarray] = None,
                 acc_uncal_x_bias: Union[list, np.ndarray] = None,
                 acc_uncal_y_bias: Union[list, np.ndarray] = None,
                 acc_uncal_z_bias: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing uncalibrated acceleration values

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series' timestamps.
        acc_uncal_x: Union [list, np.ndarray]
            Uncalibrated acceleration according to x-axis without any bias compensation.
        acc_uncal_y: Union [list, np.ndarray]
            Uncalibrated acceleration according to y-axis without any bias compensation.
        acc_uncal_z: Union [list, np.ndarray]
            Uncalibrated acceleration according to z-axis without any bias compensation.
        acc_uncal_x_bias: Union [list, np.ndarray]
            Measured acceleration along the x-axis with estimated bias compensation.
        acc_uncal_y_bias: Union [list, np.ndarray]
            Measured acceleration along the y-axis with estimated bias compensation.
        acc_uncal_z_bias: Union [list, np.ndarray]
            Measured acceleration along the z-axis with estimated bias compensation.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(AccelerationUncalibratedSeries, self).__init__(**args)


class LinearAccelerationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 lin_acc_x: Union[list, np.ndarray] = None,
                 lin_acc_y: Union[list, np.ndarray] = None,
                 lin_acc_z: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = "",
                 **kwargs):
        """
        Series containing linear acceleration values (i.e. without g)

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series' timestamps.
        lin_acc_x: Union [list, np.ndarray]
            Linear acceleration force along x-axis.
        lin_acc_y: Union [list, np.ndarray]
            Linear acceleration force along y-axis.
        lin_acc_z: Union [list, np.ndarray]
            Linear acceleration force along z-axis.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        args.pop("kwargs")
        super(LinearAccelerationSeries, self).__init__(**args)

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
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing magnetic field values

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series' timestamps.
        mag_x: Union [list, np.ndarray]
            Geomagnetic field strength according to x-axis.
        mag_y: Union [list, np.ndarray]
            Geomagnetic field strength according to y-axis.
        mag_z: Union [list, np.ndarray]
            Geomagnetic field strength according to z-axis.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(MagnetometerSeries, self).__init__(**args)


class MagnetometerUncalibratedSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 mag_uncal_x: Union[list, np.ndarray] = None,
                 mag_uncal_y: Union[list, np.ndarray] = None,
                 mag_uncal_z: Union[list, np.ndarray] = None,
                 mag_uncal_x_bias: Union[list, np.ndarray] = None,
                 mag_uncal_y_bias: Union[list, np.ndarray] = None,
                 mag_uncal_z_bias: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """ Series containing uncalibrated magnetic field values

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series' timestamps.
        mag_uncal_x: Union [list, np.ndarray]
            Geomagnetic field strength (without hard iron calibration) along the x-axis.
        mag_uncal_y: Union [list, np.ndarray]
            Geomagnetic field strength (without hard iron calibration) along the y-axis.
        mag_uncal_z: Union [list, np.ndarray]
            Geomagnetic field strength (without hard iron calibration) along the z-axis.
        mag_uncal_x_bias: Union [list, np.ndarray]
            Iron bias estimation along the x-axis.
        mag_uncal_y_bias: Union [list, np.ndarray]
            Iron bias estimation along the y-axis.
        mag_uncal_z_bias: Union [list, np.ndarray]
            Iron bias estimation along the z-axis.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(MagnetometerUncalibratedSeries, self).__init__(**args)


class NMEAMessageSeries(TimeSeries):
    def __init__(self,
                 time: Union[list, np.ndarray] = None,
                 utc_time: Union[list, np.ndarray] = None,
                 msg: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing raw NMEA strings from GNSS chipset
        See https://www.wikiwand.com/en/NMEA_0183 for more information on NMEA messages

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series' timestamps.
        utc_time: Union [list, np.ndarray]
            Time of the observation, UTC time zone.
        msg: Union [list, np.ndarray]
            NMEA message from GNSS chipset
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(NMEAMessageSeries, self).__init__(**args)


class GNSSClockMeasurementSeries(TimeSeries):
    def __init__(self,
                 time: Union[list, np.ndarray] = None,
                 bias_nanos: Union[list, np.ndarray] = None,
                 bias_uncertainty_nanos: Union[list, np.ndarray] = None,
                 drift_nanos_per_second: Union[list, np.ndarray] = None,
                 drift_uncertainty_nanos_per_second: Union[list, np.ndarray] = None,
                 elapsed_realtime_nanos: Union[list, np.ndarray] = None,
                 elapsed_realtime_uncertainty_nanos: Union[list, np.ndarray] = None,
                 full_bias_nanos: Union[list, np.ndarray] = None,
                 hardware_clock_discontinuity_count: Union[list, np.ndarray] = None,
                 leap_second: Union[list, np.ndarray] = None,
                 reference_carrier_frequency_hz_for_isb: Union[list, np.ndarray] = None,
                 reference_code_type_for_isb: Union[list, np.ndarray] = None,
                 reference_constellation_type_for_isb: Union[list, np.ndarray] = None,
                 time_nanos: Union[list, np.ndarray] = None,
                 time_uncertainty_nanos: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing raw GNSS clock values
        See https://developer.android.com/reference/android/location/GnssClock for more information on individual
        parameters

        Parameters
        ----------
        time: Union [list, np.ndarray]:
            Timeseries's timestamps
        bias_nanos: Union [list, np.ndarray]
            The clock's sub-nanosecond bias.
        bias_uncertainty_nanos: Union [list, np.ndarray]
            The clock's Bias Uncertainty (1-Sigma) in nanoseconds.
        drift_nanos_per_second: Union [list, np.ndarray]
            The clock's Drift in nanoseconds per second.
        drift_uncertainty_nanos_per_second: Union [list, np.ndarray]
            The clock's Drift Uncertainty (1-Sigma) in nanoseconds per second.
        elapsed_realtime_nanos: Union [list, np.ndarray]
            The elapsed real-time of this clock since system boot, in nanoseconds.
        elapsed_realtime_uncertainty_nanos: Union [list, np.ndarray]
            The estimate of the relative precision of the alignment of the elapsed_realtime_nanos timestamp.
        full_bias_nanos: Union [list, np.ndarray]
            The difference between hardware clock inside GPS receiver and the true GPS time.
        hardware_clock_discontinuity_count: Union [list, np.ndarray]
            Count of hardware clock discontinuities.
        leap_second: Union [list, np.ndarray]
            The leap second associated with the clock's time
        reference_carrier_frequency_hz_for_isb: Union [list, np.ndarray]
            The reference carrier frequency in Hz for inter-signal bias.
        reference_code_type_for_isb: Union [list, np.ndarray]
            The reference code type for inter-signal bias.
        reference_constellation_type_for_isb: Union [list, np.ndarray]
            The reference constellation type for inter-signal bias.
        time_nanos: Union [list, np.ndarray]
            The GNSS receiver internal hardware clock value in nanoseconds.
        time_uncertainty_nanos: Union [list, np.ndarray]
            The clock's time Uncertainty (1-Sigma) in nanoseconds.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(GNSSClockMeasurementSeries, self).__init__(**args)


class GNSSMeasurementSeries(TimeSeries):
    # noinspection PyPep8Naming
    def __init__(self,
                 time: Union[list, np.ndarray] = None,
                 accumulated_delta_range_meters: Union[list, np.ndarray] = None,
                 accumulated_delta_range_state: Union[list, np.ndarray] = None,
                 accumulated_delta_range_uncertainty_meters: Union[list, np.ndarray] = None,
                 automatic_gain_control_level_db: Union[list, np.ndarray] = None,
                 baseband_cn0DbHz: Union[list, np.ndarray] = None,
                 carrier_cycles: Union[list, np.ndarray] = None,
                 carrier_frequency_hz: Union[list, np.ndarray] = None,
                 carrier_phase: Union[list, np.ndarray] = None,
                 carrier_phase_uncertainty: Union[list, np.ndarray] = None,
                 cn0DbHz: Union[list, np.ndarray] = None,
                 code_type: Union[list, np.ndarray] = None,
                 constellation_type: Union[list, np.ndarray] = None,
                 full_inter_signal_bias_nanos: Union[list, np.ndarray] = None,
                 full_inter_signal_bias_uncertainty_nanos: Union[list, np.ndarray] = None,
                 multipath_indicator: Union[list, np.ndarray] = None,
                 pseudorange_rate_meters_per_second: Union[list, np.ndarray] = None,
                 pseudorange_rate_uncertainty_meters_per_second: Union[list, np.ndarray] = None,
                 received_sv_time_nanos: Union[list, np.ndarray] = None,
                 received_sv_time_uncertainty_nanos: Union[list, np.ndarray] = None,
                 satellite_inter_signal_bias_nanos: Union[list, np.ndarray] = None,
                 satellite_inter_signal_bias_uncertainty_nanos: Union[list, np.ndarray] = None,
                 snrInDb: Union[list, np.ndarray] = None,
                 state: Union[list, np.ndarray] = None,
                 svid: Union[list, np.ndarray] = None,
                 time_offset_nanos: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """ Series containing raw GNSS measurements
        See https://developer.android.com/reference/android/location/GnssMeasurement for more information on
        specific values

        Parameters
        ----------
        time: Union [list, np.ndarray]
         Series's timestamps.
        accumulated_delta_range_meters: Union [list, np.ndarray]
            The accumulated delta range since the last channel reset, in meters.
        accumulated_delta_range_state: Union [list, np.ndarray]
            The state (availability of the value) of the accumulated_delta_range_meters measurement.
        accumulated_delta_range_uncertainty_meters: Union [list, np.ndarray]
            The accumulated delta range's uncertainty (1-Sigma) in meters.
        automatic_gain_control_level_db: Union [list, np.ndarray]
            The Automatic Gain Control level in dB.
        baseband_cn0DbHz: Union [list, np.ndarray]
            The baseband carrier-to-noise density in dB-Hz. Typical range: 10-50 dB-Hz.
        carrier_cycles: Union [list, np.ndarray]
            The number of full carrier cycles between the satellite and the receiver.
        carrier_frequency_hz: Union [list, np.ndarray]
            The carrier frequency of the tracked signal.
        carrier_phase: Union [list, np.ndarray]
            The RF phase detected by the receiver. Range: [0.0, 1.0].
        carrier_phase_uncertainty: Union [list, np.ndarray]
            The carrier-phase's uncertainty (1-Sigma).
        cn0DbHz: Union [list, np.ndarray]
            The Carrier-to-noise density in dB-Hz.
        code_type: Union [list, np.ndarray]
            The GNSS measurement's code type.
        constellation_type: Union [list, np.ndarray]
            The constellation type.
        full_inter_signal_bias_nanos: Union [list, np.ndarray]
            The GNSS measurement's inter-signal bias in nanoseconds with sub-nanosecond accuracy.
        full_inter_signal_bias_uncertainty_nanos: Union [list, np.ndarray]
            The GNSS measurement's inter-signal bias uncertainty (1 sigma) in nanoseconds with sub-nanosecond accuracy.
        multipath_indicator: Union [list, np.ndarray]
            Values indicating the 'multipath' state of the event.
        pseudorange_rate_meters_per_second: Union [list, np.ndarray]
            The Pseudorange rate at the timestamp in m/s.
        pseudorange_rate_uncertainty_meters_per_second: Union [list, np.ndarray]
            The pseudorange's rate uncertainty (1-Sigma) in m/s.
        received_sv_time_nanos: Union [list, np.ndarray]
            The received GNSS satellite time, at the measurement time, in nanoseconds.
        received_sv_time_uncertainty_nanos: Union [list, np.ndarray]
            The error estimate (1-sigma) for the received GNSS time, in nanoseconds.
        satellite_inter_signal_bias_nanos: Union [list, np.ndarray]
            The GNSS measurement's satellite inter-signal bias in nanoseconds with sub-nanosecond accuracy.
        satellite_inter_signal_bias_uncertainty_nanos: Union [list, np.ndarray]
            The GNSS measurement's satellite inter-signal bias uncertainty (1 sigma) in nanoseconds with sub-nanosecond accuracy.
        snrInDb: Union [list, np.ndarray]
            The (post-correlation & integration) Signal-to-Noise ratio (SNR) in dB.
        state: Union [list, np.ndarray]
            The per-satellite-signal sync state.
        svid: Union [list, np.ndarray]
            The satellite ID.
        time_offset_nanos: Union [list, np.ndarray]
            The time offset at which the measurement was taken in nanoseconds.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(GNSSMeasurementSeries, self).__init__(**args)


class OrientationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 azimuth: Union[list, np.ndarray] = None,
                 pitch: Union[list, np.ndarray] = None,
                 roll: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing orientation values

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series's timestamps.
        azimuth: Union [list, np.ndarray]
            Azimuth (angle around the z-axis).
        pitch: Union [list, np.ndarray]
            Pitch (angle around the x-axis).
        roll: Union [list, np.ndarray]
            Roll (angle around the y-axis).
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(OrientationSeries, self).__init__(**args)


class GyroSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 w_x: Union[list, np.ndarray] = None,
                 w_y: Union[list, np.ndarray] = None,
                 w_z: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing gyro values

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series's timestamps.
        w_x: Union [list, np.ndarray]
            Rate of rotation around x-axis.
        w_y: Union [list, np.ndarray]
            Rate of rotation around y-axis.
        w_z: Union [list, np.ndarray]
            Rate of rotation around z-axis.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(GyroSeries, self).__init__(**args)


class GyroUncalibratedSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 w_uncal_x: Union[list, np.ndarray] = None,
                 w_uncal_y: Union[list, np.ndarray] = None,
                 w_uncal_z: Union[list, np.ndarray] = None,
                 w_uncal_x_bias: Union[list, np.ndarray] = None,
                 w_uncal_y_bias: Union[list, np.ndarray] = None,
                 w_uncal_z_bias: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """ Series containing uncalibrated gyro values

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series's timestamps.
        w_uncal_x: Union [list, np.ndarray]
            Rate of rotation (without drift compensation) around x-axis.
        w_uncal_y: Union [list, np.ndarray]
            Rate of rotation (without drift compensation) around y-axis.
        w_uncal_z: Union [list, np.ndarray]
            Rate of rotation (without drift compensation) around z-axis.
        w_uncal_x_bias: Union [list, np.ndarray]
            Estimated drift around the x-axis.
        w_uncal_y_bias: Union [list, np.ndarray]
            Estimated drift around the y-axis.
        w_uncal_z_bias: Union [list, np.ndarray]
            Estimated drift around the z-axis.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(GyroUncalibratedSeries, self).__init__(**args)


class RotationSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 rot_x: Union[list, np.ndarray] = None,
                 rot_y: Union[list, np.ndarray] = None,
                 rot_z: Union[list, np.ndarray] = None,
                 cos_phi: Union[list, np.ndarray] = None,
                 heading_acc: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing rotation values

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series timestamps.
        rot_x: Union [list, np.ndarray]
            Rotation vector component along the x-axis.
        rot_y: Union [list, np.ndarray]
            Rotation vector component along the y-axis.
        rot_z: Union [list, np.ndarray]
            Rotation vector component along the y-axis.
        cos_phi: Union [list, np.ndarray]
            Scalar component of the rotation vector.
        heading_acc: Union [list, np.ndarray]
            Heading accuracy
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(RotationSeries, self).__init__(**args)


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
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing GPS values

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series's timestamps.
        lat: Union [list, np.ndarray]
            The latitude in degrees.
        lon: Union [list, np.ndarray]
            The longitude in degrees.
        altitude: Union [list, np.ndarray]
            The altitude of this location in meters
        bearing: Union [list, np.ndarray]
            The bearing at the time of this location in degrees.
        speed: Union [list, np.ndarray]
            The speed at the time of this location in meters per second.
        hor_acc: Union [list, np.ndarray]
            The estimated horizontal accuracy radius in meters of this location.
        ver_acc: Union [list, np.ndarray]
            The estimated altitude accuracy in meters of this location.
        bear_acc: Union [list, np.ndarray]
            The estimated bearing accuracy in degrees of this location.
        speed_acc: Union [list, np.ndarray]
            The estimated speed accuracy in meters per second of this location
        utc_time: Union [list, np.ndarray]
            UTC-Time received by GPS, accurate to 1 s
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(GPSSeries, self).__init__(**args)

    def to_ipyleaflef(self) -> List[list]:
        """
        Gives a list of coordinates of the form [latitude, longitude]

        Returns
        -------
        coordinates : list [list]
            List of coordinates

        """
        if np.array_equal(self.lat, np.array(None)) and np.array_equal(self.lat, np.array(None)):
            logger.warning("(%s) Coordinates are empty in GPSSeries" % self.filename)
            return []
        elif len(self.lat) == 0 and len(self.lon) == 0:
            logger.warning("(%s) Coordinates are empty in GPSSeries" % self.filename)
            return []
        else:
            return [[lat, lon] for lat, lon in zip(self.lat, self.lon)]


class PressureSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 pressure: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing the ambient air pressure and the timestamps

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series's timestamps.
        pressure: Union [list, np.ndarray]
            Ambient air pressure.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(PressureSeries, self).__init__(**args)


class TemperatureSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 temperature: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing ambient temperature and the corresponding timestamps

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series's timestamps.
        temperature: Union [list, np.ndarray]
            Ambient temperature.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(TemperatureSeries, self).__init__(**args)


class HumiditySeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 humidity: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series contaning the ambient relative humidity and the corresponding timestamps

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series's timestamps.
        humidity: Union [list, np.ndarray]
            Ambient relative humidity.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(HumiditySeries, self).__init__(**args)


class LightSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 light: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing the light measurements and the corresponding timestamps

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series's timestamps.
        light: Union[list, np.ndarray]
            Illuminance.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(LightSeries, self).__init__(**args)


class WzSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 wz_x: Union[list, np.ndarray] = None,
                 wz_y: Union[list, np.ndarray] = None,
                 wz_z: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Based on the Sperling's ride index to determine ride Comfort

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series's timestamps.
        wz_x: Union [list, np.ndarray]
            Sperling's ride index in y direction
        wz_y: Union [list, np.ndarray]
            Sperling's ride index in y direction
        wz_z: Union [list, np.ndarray]
            Sperling's ride index in y direction
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """

        args = locals().copy()
        args.pop("self")
        super(WzSeries, self).__init__(**args)


class SubjectiveComfortSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 comfort: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 filename: str = ""):
        """
        Series containing the subjective comfort measurements and their timestamps

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series's timestamps.
        comfort: Union[list, np.ndarray]
            Subjective ride comfort
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """
        args = locals().copy()
        args.pop("self")
        super(SubjectiveComfortSeries, self).__init__(**args)


class NTPDatetimeSeries(TimeSeries):
    def __init__(self, time: Union[list, np.ndarray] = None,
                 ntp_datetime: Union[list, np.ndarray] = None,
                 rdy_format_version: float = None,
                 strip_timezone: bool = False,
                 filename: str = ""):
        """
        Series containing the Date-time from NTP and their timestamps

        Parameters
        ----------
        time: Union [list, np.ndarray]
            Series's timestamps.
        ntp_datetime: Union [list, np.ndarray]
            Date-time from NTP(Network Time Protocol) server.
        rdy_format_version: float
            File format version
        filename: str
            Ridy File's name containing measurements
        """

        self.ntp_datetime = ntp_datetime

        args = locals().copy()
        args.pop("self")
        args.pop("strip_timezone")
        super(NTPDatetimeSeries, self).__init__(**args)

        if len(self.ntp_datetime) > 0:
            if strip_timezone:
                ntp_datetime = [datetime.datetime.fromisoformat(el).replace(tzinfo=None) for el in self.ntp_datetime]
                self.ntp_datetime = np.array([np.datetime64(el) for el in ntp_datetime])
            else:
                self.ntp_datetime = np.array([np.datetime64(el) for el in self.ntp_datetime])