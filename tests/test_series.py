import pandas as pd
import pytest

from pyridy.utils import AccelerationSeries


@pytest.fixture
def my_acc_series():
    return AccelerationSeries(time=[1.1, 2, 3],
                              acc_x=[0.1, -2, 3],
                              acc_y=[-0.3, 0, 3.4],
                              acc_z=[0.6, 3, -3])


def test_acceleration_series(my_acc_series):
    assert True


def test_acceleration_series_to_df(my_acc_series):
    test_df = pd.DataFrame({"time": [1.1, 2, 3],
                            "acc_x": [0.1, -2, 3],
                            "acc_y": [-0.3, 0, 3.4],
                            "acc_z": [0.6, 3, -3]})

    acc_df = my_acc_series.to_df()
    assert acc_df.equals(test_df)
