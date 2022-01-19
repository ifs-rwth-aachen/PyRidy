import logging

import pytest

import pyridy
from pyridy.processing import ExcitationProcessor


@pytest.fixture
def my_campaign():
    return pyridy.Campaign()


def test_execute_excitation_processor(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_folder("files")
    proc = ExcitationProcessor(my_campaign)
    proc.execute()
    assert True
