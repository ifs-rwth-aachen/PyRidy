import logging

import pytest

import pyridy
from pyridy.utils import GNSSClockMeasurementSeries, TimeSeries, AccelerationSeries


@pytest.fixture
def my_campaign():
    return pyridy.Campaign()


def test_gnssclock_measurement_series():
    series = GNSSClockMeasurementSeries()
    assert True


def test_timeseries():
    series = AccelerationSeries()
    assert issubclass(type(series), TimeSeries)


def test_cut(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_files("files/sqlite/sample3.sqlite", sync_method="ntp_time")
    acc_dur_pre = my_campaign[0].measurements[AccelerationSeries].get_duration()
    my_campaign[0].measurements[AccelerationSeries].cut(5, 5)
    acc_dur_post = my_campaign[0].measurements[AccelerationSeries].get_duration()

    assert int(acc_dur_pre - acc_dur_post) == 10

    with pytest.raises(ValueError):
        my_campaign[0].measurements[AccelerationSeries].cut(5, 5)

