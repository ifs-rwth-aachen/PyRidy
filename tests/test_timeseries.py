from pyridy.utils import GNSSClockMeasurementSeries, TimeSeries, AccelerationSeries


def test_gnssclock_measurement_series():
    series = GNSSClockMeasurementSeries()
    assert True


def test_timeseries():
    series = AccelerationSeries()
    assert issubclass(type(series), TimeSeries)
