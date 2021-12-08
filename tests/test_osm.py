import logging

import pytest

import pyridy


@pytest.fixture
def my_campaign():
    return pyridy.Campaign()


def test_get_switches_for_railway_line(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_folder("files/sqlite/osm_mapping_test",
                              download_osm_region=True,
                              railway_types=["tram"],
                              osm_recurse_type="<")

    rw_line = my_campaign.osm_region.railway_lines[0]
    sw = my_campaign.osm_region.get_switches_for_railway_line(rw_line)

    assert True
