import logging

import pytest

from pyridy.osm.utils.overpass import Overpass


@pytest.fixture
def my_campaign():
    return pyridy.Campaign()


def test_get_switches_for_railway_line(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    query = """
[timeout:180];
(
    node[railway~"rail|tram|subway|light_rail"](52.371299743652344,9.664454460144043,52.37901306152344,9.742464065551758);
    way[railway~"rail|tram|subway|light_rail"](52.371299743652344,9.664454460144043,52.37901306152344,9.742464065551758);
);
(._;>;);
out body;   
"""
    overpass = Overpass()
    result = overpass.query(query)

    assert True