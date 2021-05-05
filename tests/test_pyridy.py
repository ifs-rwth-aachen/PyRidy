import logging

import numpy as np
import matplotlib.pyplot as plt
import pytest

import pyridy
from pyridy.utils import AccelerationSeries, LinearAccelerationSeries

@pytest.fixture
def my_manager():
    return pyridy.Campaign()


def test_ridy_manager(my_manager):
    assert True


def test_loading_files(my_manager, caplog):
    caplog.set_level(logging.DEBUG)
    my_manager.import_folder("files")
    assert len(my_manager) == 5


def test_merging_data_frames(my_manager, caplog):
    caplog.set_level(logging.DEBUG)
    my_manager.import_folder("files")
    f = my_manager("sample.rdy")[0]
    f.to_df()
    assert True


def test_invalid_syncing_method(my_manager, caplog):
    with pytest.raises(ValueError):
        my_manager.import_folder("files", sync_method="foo")
    pass


def test_timestamp_syncing(my_manager, caplog):
    my_manager.import_folder("files", sync_method="timestamp")

    assert my_manager.files[0].measurements[AccelerationSeries].time[0] == 0
    assert my_manager.files[3].measurements[AccelerationSeries].time[0] == -2673398501
    assert my_manager.files[4].measurements[AccelerationSeries].time[0] == -86511141372
    pass


def test_device_time_syncing(my_manager, caplog):
    my_manager.import_folder("files", sync_method="device_time")

    assert my_manager.files[0].measurements[AccelerationSeries].time[0] == np.datetime64(
        "2021-05-05T18:51:56.285000000")
    assert my_manager.files[3].measurements[AccelerationSeries].time[0] == np.datetime64(
        "2021-04-27T13:08:45.246601499")
    assert my_manager.files[4].measurements[AccelerationSeries].time[0] == np.datetime64(
        "2021-04-28T07:51:54.583858628")

    df_acc_1 = my_manager.files[1].measurements[LinearAccelerationSeries].to_df()
    df_acc_2 = my_manager.files[2].measurements[LinearAccelerationSeries].to_df()

    fig, ax = plt.subplots(figsize=(11.69,8.27))
    ax.plot(df_acc_1["lin_acc_z"],
            label="Device 1", linewidth=1)
    ax.plot(df_acc_2["lin_acc_z"],
            label="Device 2", linewidth=1)

    ax.set(xlabel='Time [s]', ylabel='Acceleration [m/s^2]', title='Device time syncing test')
    ax.grid()
    ax.legend()

    fig.savefig("files/sqlite/sync/device_time_sync.png", dpi=300)

    plt.show()

    pass


def test_gps_time_syncing(my_manager, caplog):
    my_manager.import_folder("files", sync_method="gps_time")

    assert my_manager.files[0].measurements[AccelerationSeries].time[0] == 0
    assert my_manager.files[3].measurements[AccelerationSeries].time[0] == np.datetime64(
        "2021-04-27T13:08:45.246601499")
    assert my_manager.files[4].measurements[AccelerationSeries].time[0] == np.datetime64(
        "2021-04-28T07:51:56.892826255")

    df_acc_1 = my_manager.files[1].measurements[LinearAccelerationSeries].to_df()
    df_acc_2 = my_manager.files[2].measurements[LinearAccelerationSeries].to_df()

    fig, ax = plt.subplots(figsize=(11.69,8.27))
    ax.plot(df_acc_1["lin_acc_z"],
            label="Device 1", linewidth=1)
    ax.plot(df_acc_2["lin_acc_z"],
            label="Device 2", linewidth=1)

    ax.set(xlabel='Time [s]', ylabel='Acceleration [m/s^2]', title='GPS time syncing test')
    ax.grid()
    ax.legend()

    fig.savefig("files/sqlite/sync/gps_time_sync.png", dpi=300)

    plt.show()

    pass
