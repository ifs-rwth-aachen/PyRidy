import logging

import pytest

import pyridy


@pytest.fixture
def my_manager():
    return pyridy.CampaignManager()


def test_ridy_manager(my_manager):
    assert True


def test_loading_files(my_manager, caplog):
    caplog.set_level(logging.DEBUG)
    my_manager.import_folder("files")
    assert len(my_manager) == 3
