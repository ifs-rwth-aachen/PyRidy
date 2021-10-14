import logging

import numpy as np
import matplotlib.pyplot as plt
import pytest

import pyridy
from pyridy.utils import AccelerationSeries, LinearAccelerationSeries, GPSSeries


@pytest.fixture
def my_campaign():
    return pyridy.Campaign()


def test_pyridy_campaign_manager(my_campaign):
    assert True


def test_loading_files(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_folder("files")
    assert len(my_campaign) == 11


def test_exclude_file(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_folder("files", exclude="device1.sqlite")
    assert len(my_campaign) == 10


def test_exclude_files(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_folder("files", exclude=["device1.sqlite", "osm_mapping_test.sqlite"])
    assert len(my_campaign) == 9


def test_exclude_folder(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_folder("files", exclude="sqlite")
    assert len(my_campaign) == 3


def test_load_single_file(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_files("files/sqlite/sample3.sqlite", sync_method="ntp_time")

    assert len(my_campaign) == 1

    # Plot acceleration data
    t = my_campaign.files[0].measurements[AccelerationSeries].time

    acc_x = my_campaign.files[0].measurements[AccelerationSeries].acc_x
    acc_y = my_campaign.files[0].measurements[AccelerationSeries].acc_y
    acc_z = my_campaign.files[0].measurements[AccelerationSeries].acc_z

    fig, ax = plt.subplots(3, 1, sharex="row", figsize=(11.69, 8.27))

    ax[0].plot(t, acc_x)
    ax[1].plot(t, acc_y)
    ax[2].plot(t, acc_z)

    ax[0].grid()
    ax[1].grid()
    ax[2].grid()

    ax[0].set_ylabel("Acc_x [m/s^2]")
    ax[1].set_ylabel("Acc_y [m/s^2]")
    ax[2].set_ylabel("Acc_z [m/s^2]")

    ax[2].set_xlabel("Time")

    # ax[0].set_ylim(-1, 1)

    plt.show()


def test_loading_files_non_recursive(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_folder("files/rdy/", recursive=False)
    assert len(my_campaign) == 3


def test_get_measurement(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)

    my_campaign.import_folder("files/rdy/", recursive=False)
    m = my_campaign[0].measurements[AccelerationSeries]

    assert type(m) == AccelerationSeries


def test_get_sub_series_names(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)

    my_campaign.import_folder("files/rdy/", recursive=False)
    sub_series_types = my_campaign[0].measurements[AccelerationSeries].get_sub_series_names()
    assert sub_series_types == ["acc_x", "acc_y", "acc_z"]


def test_load_additional_osm_data(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_folder("files/sqlite/osm_mapping_test", download_osm_region=True, railway_types=["tram"])
    assert True


def test_merging_data_frames(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_folder("files")
    f = my_campaign("sample1.rdy")
    f.to_df()
    assert True


def test_invalid_syncing_method(my_campaign, caplog):
    with pytest.raises(ValueError):
        my_campaign.import_folder("files", sync_method="foo")
    pass


def test_timestamp_syncing(my_campaign, caplog):
    my_campaign.import_folder("files", sync_method="timestamp", cutoff=False)

    assert my_campaign("sample1.rdy").measurements[AccelerationSeries].time[0] == 0
    assert my_campaign("sample1.sqlite").measurements[AccelerationSeries].time[0] == -2673398501
    assert my_campaign("sample2.sqlite").measurements[AccelerationSeries].time[0] == -86511141372
    pass


def test_device_time_syncing(my_campaign, caplog):
    my_campaign.import_folder("files", sync_method="device_time", cutoff=False)

    assert my_campaign("sample1.rdy").measurements[AccelerationSeries].time[0] == np.datetime64(
        "2021-05-05T20:51:56.285000000")
    assert my_campaign("sample1.sqlite").measurements[AccelerationSeries].time[0] == np.datetime64(
        "2021-04-27T15:08:45.246601499")
    assert my_campaign("sample2.sqlite").measurements[AccelerationSeries].time[0] == np.datetime64(
        "2021-04-28T09:51:54.583858628")

    df_acc_1 = my_campaign("device1.sqlite").measurements[AccelerationSeries].to_df()
    df_acc_2 = my_campaign("device2.sqlite").measurements[AccelerationSeries].to_df()

    t_start = "2021-05-06T14:51:40"
    t_end = "2021-05-06T14:51:50"

    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    ax.plot(df_acc_1[(df_acc_1.index >= t_start) & (df_acc_1.index < t_end)]["acc_z"],
            label="Device 1", linewidth=1)
    ax.plot(df_acc_2[(df_acc_2.index >= t_start) & (df_acc_2.index < t_end)]["acc_z"],
            label="Device 2", linewidth=1)

    ax.set(xlabel='Time [s]', ylabel='Acceleration [m/s^2]', title='Device time syncing test')
    ax.grid()
    ax.legend()

    fig.savefig("files/sqlite/sync/device_time_sync.png", dpi=300)

    plt.show()

    pass


def test_gps_time_syncing(my_campaign, caplog):
    my_campaign.import_folder("files", sync_method="gps_time", strip_timezone=False, cutoff=False)

    assert my_campaign("sample1.rdy").measurements[AccelerationSeries].time[0] == 0
    assert my_campaign("sample1.sqlite").measurements[AccelerationSeries].time[0] == np.datetime64(
        "2021-04-27T13:08:45.246601499")
    assert my_campaign("sample2.sqlite").measurements[AccelerationSeries].time[0] == np.datetime64(
        "2021-04-28T07:51:56.892826255")

    df_acc_1 = my_campaign("device1.sqlite").measurements[LinearAccelerationSeries].to_df()
    df_acc_2 = my_campaign("device2.sqlite").measurements[LinearAccelerationSeries].to_df()

    df_gps_1 = my_campaign("device1.sqlite").measurements[GPSSeries].to_df()
    df_gps_2 = my_campaign("device2.sqlite").measurements[GPSSeries].to_df()

    t_start = "2021-05-06T12:51:40"
    t_end = "2021-05-06T12:51:50"

    fig, ax = plt.subplots(2, 1, figsize=(11.69, 8.27))
    ax[0].plot(df_acc_1[(df_acc_1.index >= t_start) & (df_acc_1.index < t_end)]["lin_acc_z"],
               label="Device 1", linewidth=1)
    ax[0].plot(df_acc_2[(df_acc_2.index >= t_start) & (df_acc_2.index < t_end)]["lin_acc_z"],
               label="Device 2", linewidth=1)

    ax[0].set(xlabel='Time [s]', ylabel='Acceleration [m/s^2]', title='GPS time syncing test')
    ax[0].grid()
    ax[0].legend()

    ax[1].plot(df_gps_1[(df_gps_1.index >= t_start) & (df_gps_1.index < t_end)]["utc_time"],
               label="Device 1", linewidth=1)
    ax[1].plot(df_gps_2[(df_gps_2.index >= t_start) & (df_gps_2.index < t_end)]["utc_time"],
               label="Device 2", linewidth=1)

    fig.savefig("files/sqlite/sync/gps_time_sync.png", dpi=300)

    plt.show()

    pass


def test_ntp_time_syncing(my_campaign, caplog):
    my_campaign.import_folder("files", sync_method="ntp_time", cutoff=False)

    assert my_campaign("device1.sqlite").measurements[AccelerationSeries].time[0] == np.datetime64(
        "2021-05-06T14:51:13.321774591")
    assert my_campaign("device2.sqlite").measurements[AccelerationSeries].time[0] == np.datetime64(
        "2021-05-06T14:51:13.705642452")

    df_acc_1 = my_campaign("device1.sqlite").measurements[AccelerationSeries].to_df()
    df_acc_2 = my_campaign("device2.sqlite").measurements[AccelerationSeries].to_df()

    t_start = "2021-05-06T14:51:40"
    t_end = "2021-05-06T14:51:50"

    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    ax.plot(df_acc_1[(df_acc_1.index >= t_start) & (df_acc_1.index < t_end)]["acc_z"],
            label="Device 1", linewidth=1)
    ax.plot(df_acc_2[(df_acc_2.index >= t_start) & (df_acc_2.index < t_end)]["acc_z"],
            label="Device 2", linewidth=1)

    ax.set(xlabel='Time [s]', ylabel='Acceleration [m/s^2]', title='NTP time syncing test')
    ax.grid()
    ax.legend()

    fig.savefig("files/sqlite/sync/ntp_time_sync.png", dpi=300)

    plt.show()

    pass
