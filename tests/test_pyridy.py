import logging

import pytest

import pyridy


@pytest.fixture
def my_manager():
    return pyridy.Campaign()


def test_ridy_manager(my_manager):
    assert True


def test_loading_files(my_manager, caplog):
    caplog.set_level(logging.DEBUG)
    my_manager.import_folder("files")
    assert len(my_manager) == 3


def test_merging_data_frames(my_manager, caplog):
    caplog.set_level(logging.DEBUG)
    my_manager.import_folder("files")
    f = my_manager("sample.rdy")[0]
    f.to_df()
    assert True
