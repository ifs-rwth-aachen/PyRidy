import logging

from pyridy.osm.utils import OSMResultNode


def test_osmresult_node(caplog):
    caplog.set_level(logging.DEBUG)
    n = OSMResultNode(lat=0.0, lon=0.0)
    assert True
