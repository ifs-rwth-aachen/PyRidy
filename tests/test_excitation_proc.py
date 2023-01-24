import logging

import pytest

import pyridy
from pyridy.processing import ExcitationProcessor


@pytest.fixture
def my_campaign():
    return pyridy.Campaign()


def test_excitation_proc_osm_integration(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_folder("files/sqlite/osm_mapping_test",
                              download_osm_data=True,
                              railway_types=["tram"],
                              osm_recurse_type="<")

    my_campaign.do_map_matching()
    ExcitationProcessor(my_campaign).execute()
    assert False
