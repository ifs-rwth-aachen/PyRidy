import logging

import pytest

import pyridy
from pyridy.utils import GPSSeries


@pytest.fixture
def my_campaign():
    return pyridy.Campaign()


def test_load_additional_osm_data(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    pyridy.options["OSM_TIMEOUT"] = 200
    my_campaign.import_folder("files/sqlite/osm_mapping_test",
                              download_osm_region=True,
                              railway_types=["tram"],
                              osm_recurse_type="<")
    assert True


def test_load_additional_osm_data_for_many_files(my_campaign, caplog):  # TODO
    caplog.set_level(logging.DEBUG)
    pyridy.options["OSM_TIMEOUT"] = 300
    my_campaign.import_folder("D:/10_Daten/Ridy",
                              series=[GPSSeries],
                              download_osm_region=True,
                              railway_types=["rail"],
                              osm_recurse_type="<")
    assert True


def test_single_bounding_boxe(my_campaign, caplog):
    pyridy.options["OSM_SINGLE_BOUNDING_BOX"] = True
    my_campaign.import_folder("D:/10_Daten/Ridy",
                              series=[GPSSeries],
                              download_osm_region=True,
                              railway_types=["rail"],
                              osm_recurse_type="<")


def test_split_bounding_boxes(my_campaign, caplog):
    pyridy.options["OSM_BOUNDING_BOX_OPTIMIZATION"] = True
    pyridy.options["OSM_TIMEOUT"] = 300
    my_campaign.import_folder("D:/10_Daten/Ridy",
                              series=[GPSSeries],
                              download_osm_region=True,
                              railway_types=["rail"],
                              osm_recurse_type="<")


def test_dont_split_bounding_boxes(my_campaign, caplog):
    pyridy.options["BOUNDING_BOX_OPTIMIZATION"] = False
    pyridy.options["OSM_TIMEOUT"] = 300
    my_campaign.import_folder("D:/10_Daten/Ridy",
                              series=[GPSSeries],
                              download_osm_region=True,
                              railway_types=["rail"],
                              osm_recurse_type="<")
