import pytest

import pyridy


@pytest.fixture
def my_manager():
    return pyridy.CampaignManager()


def test_ridy_manager(my_manager):
    assert True


def test_loading_rdy_file(my_manager):
    my_manager.import_folder("files")
    assert True
